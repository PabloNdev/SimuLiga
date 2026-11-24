"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getProjection, getSeason, postScenario } from "@/lib/api";
import type {
  Mode,
  Outcome,
  ProjectionPayload,
  SeasonPayload,
} from "@/lib/types";
import {
  DEFAULT_SCENARIO,
  buildScenarioParams,
  modelParamDefaults,
  parseScenario,
  type ScenarioState,
} from "@/lib/scenario";
import {
  deltaTone,
  formatProbability,
  formatSignedPoints,
  formatSignedProbability,
} from "@/lib/format";
import { ErrorState, LoadingState } from "@/components/States";
import { PointsDistribution } from "@/components/PointsDistribution";
import { TeamBadge } from "@/components/TeamBadge";

const BASELINE_SIMS = 10_000;

export function ScenarioLab() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [state, setState] = useState<ScenarioState>(() =>
    parseScenario(new URLSearchParams(searchParams.toString())),
  );
  const [season, setSeason] = useState<SeasonPayload | null>(null);
  const [baseline, setBaseline] = useState<ProjectionPayload | null>(null);
  const [result, setResult] = useState<ProjectionPayload | null>(null);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [shareMessage, setShareMessage] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getSeason(controller.signal),
      getProjection(
        state.mode,
        BASELINE_SIMS,
        state.startMatchday,
        controller.signal,
      ),
    ])
      .then(([seasonPayload, baselinePayload]) => {
        setSeason(seasonPayload);
        setBaseline(baselinePayload);
        setSelectedTeam(
          (current) => current ?? baselinePayload.teams[0]?.team.id ?? null,
        );
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setLoadError(caught instanceof Error ? caught.message : "Error inesperado");
        setLoading(false);
      });
    return () => controller.abort();
  }, [state.mode, state.startMatchday, reloadKey]);

  const hasChanges = useMemo(() => {
    return (
      Object.keys(state.elo).length > 0 ||
      Object.keys(state.forced).length > 0 ||
      state.homeAdvantage !== null ||
      state.nu !== null ||
      state.rho !== null
    );
  }, [state]);

  useEffect(() => {
    if (
      !season ||
      !baseline ||
      baseline.mode !== state.mode ||
      baseline.start_matchday !== state.startMatchday
    ) {
      return;
    }

    const params = buildScenarioParams(state);
    const url = `/escenario?${params.toString()}`;
    if (!hasChanges) {
      router.replace(url, { scroll: false });
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setRunning(true);
      setRunError(null);
      try {
        const payload = await postScenario(
          {
            mode: state.mode,
            sims: state.sims,
            seed: 42,
            start_matchday: state.startMatchday,
            elo_delta: state.elo,
            forced_results: state.forced,
            ...(state.homeAdvantage !== null
              ? { home_advantage: state.homeAdvantage }
              : {}),
            ...(state.nu !== null ? { nu: state.nu } : {}),
            ...(state.rho !== null ? { rho: state.rho } : {}),
          },
          controller.signal,
        );
        setResult(payload);
        router.replace(url, { scroll: false });
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setRunError(caught instanceof Error ? caught.message : "Error inesperado");
      } finally {
        setRunning(false);
      }
    }, 650);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [state, hasChanges, season, baseline, router]);

  const activeResult =
    result?.mode === state.mode &&
    result?.start_matchday === state.startMatchday
      ? result
      : null;
  const activeBaseline =
    baseline?.mode === state.mode &&
    baseline?.start_matchday === state.startMatchday
      ? baseline
      : null;
  const displayResult = hasChanges ? activeResult : activeBaseline;
  const isRunning = running && hasChanges;

  function changeMode(nextMode: Mode) {
    if (nextMode === state.mode) return;
    setLoadError(null);
    setState((current) => ({ ...current, mode: nextMode }));
  }

  const teamMap = useMemo(
    () => new Map((season?.teams ?? []).map((team) => [team.id, team])),
    [season],
  );

  const modelDefaults = useMemo(
    () => (season ? modelParamDefaults(season.model) : null),
    [season],
  );

  const baselineMap = useMemo(
    () =>
      new Map(
        (activeBaseline?.teams ?? []).map((team) => [team.team.id, team]),
      ),
    [activeBaseline],
  );

  const projectionTeams = useMemo(
    () => displayResult?.teams ?? activeBaseline?.teams ?? [],
    [displayResult, activeBaseline],
  );
  const currentFavorite = [...projectionTeams].sort(
    (a, b) => b.champion_probability - a.champion_probability,
  )[0];

  const movers = useMemo(() => {
    return projectionTeams
      .map((team) => {
        const base = baselineMap.get(team.team.id);
        return {
          team,
          delta: team.champion_probability - (base?.champion_probability ?? 0),
        };
      })
      .sort((a, b) => b.delta - a.delta);
  }, [projectionTeams, baselineMap]);

  const riser = movers[0];
  const faller = movers[movers.length - 1];
  const selected = selectedTeam ?? projectionTeams[0]?.team.id ?? "";
  const selectedProjection = projectionTeams.find(
    (team) => team.team.id === selected,
  );

  function updateElo(teamId: string, value: number) {
    setState((current) => ({
      ...current,
      elo: { ...current.elo, [teamId]: value },
    }));
  }

  function toggleForced(matchId: string, outcome: Outcome) {
    setState((current) => {
      const forced = { ...current.forced };
      if (forced[matchId] === outcome) {
        delete forced[matchId];
      } else {
        forced[matchId] = outcome;
      }
      return { ...current, forced };
    });
  }

  function resetScenario() {
    setState((current) => ({
      ...DEFAULT_SCENARIO,
      mode: current.mode,
      startMatchday: current.startMatchday,
    }));
    setResult(baseline);
    setShareMessage(null);
    router.replace(`/escenario?mode=${state.mode}`, { scroll: false });
  }

  async function copyShareLink() {
    const params = buildScenarioParams(state);
    const url = `${window.location.origin}/escenario?${params.toString()}`;
    try {
      await navigator.clipboard.writeText(url);
      setShareMessage("Enlace copiado. Al abrirlo se reconstruye este escenario.");
    } catch {
      setShareMessage("No se pudo copiar automáticamente. Copia la barra de direcciones.");
    }
  }

  if (loading && !season) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">Laboratorio</span>
            <h1 className="page-title">Escenarios.</h1>
          </div>
        </div>
        <LoadingState
          title="Cargando el laboratorio"
          note="Preparando la temporada y la proyección base."
        />
      </div>
    );
  }

  if (loadError || !season || !baseline) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">Laboratorio</span>
            <h1 className="page-title">Escenarios.</h1>
          </div>
        </div>
        <ErrorState
          message={loadError ?? "No se pudo cargar el laboratorio."}
          onRetry={() => {
            setLoading(true);
            setLoadError(null);
            setReloadKey((value) => value + 1);
          }}
        />
      </div>
    );
  }

  const currentMatches =
    baseline.match_predictions
      .filter((prediction) => prediction.matchday === season.current_matchday)
      .slice(0, 10) ?? [];

  const effectiveModel = modelDefaults ?? {
    homeAdvantage: 60,
    nu: 0.9,
    rho: -0.05,
  };
  const homeAdvantage = state.homeAdvantage ?? effectiveModel.homeAdvantage;
  const nu = state.nu ?? effectiveModel.nu;
  const rho = state.rho ?? effectiveModel.rho;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <span className="kicker">Laboratorio de escenarios</span>
          <h1 className="page-title">
            ¿Y si cambia <em>algo</em>?
          </h1>
          <p className="page-sub">
            Ajusta la fuerza de un equipo o fuerza un resultado de la próxima
            jornada. La tabla se recalcula y compara cada cambio contra la
            proyección base.
          </p>
        </div>
        <div className="status-row">
          <span className="chip">
            Base J<strong>{state.startMatchday}</strong> ·{" "}
            {BASELINE_SIMS.toLocaleString("es-ES")} sims
          </span>
          <span className={`chip ${running ? "chip-accent" : ""}`}>
            {running ? "Recalculando…" : hasChanges ? "Escenario activo" : "Sin cambios"}
          </span>
          <Link href="/" className="btn">
            Volver al panel
          </Link>
        </div>
      </div>

      <div className="scenario-layout">
        <aside className="panel scenario-controls">
          <div className="control-block">
            <h3>Modo</h3>
            <p className="control-hint">
              El marcador exacto aplica goles y todos los desempates. El modo
              1X2 solo usa victoria, empate o derrota.
            </p>
            <div className="segmented" role="group" aria-label="Modo del escenario">
              <button
                type="button"
                aria-pressed={state.mode === "score"}
                onClick={() => changeMode("score")}
              >
                Marcador exacto
              </button>
              <button
                type="button"
                aria-pressed={state.mode === "1x2"}
                onClick={() => changeMode("1x2")}
              >
                Solo 1X2
              </button>
            </div>
          </div>

          <div className="control-block">
            <h3>Jornada de inicio</h3>
            <p className="control-hint">
              Conserva los resultados reales anteriores a esta jornada y simula
              desde aquí. La jornada 1 equivale a una proyección de pretemporada.
            </p>
            <select
              className="control-select"
              value={state.startMatchday}
              onChange={(event) =>
                setState((current) => ({
                  ...current,
                  startMatchday: Number(event.target.value),
                }))
              }
              aria-label="Jornada de inicio del escenario"
            >
              {Array.from(
                { length: season.total_matchdays },
                (_, index) => index + 1,
              ).map((matchday) => (
                <option key={matchday} value={matchday}>
                  Jornada {matchday}
                  {matchday === season.current_matchday
                    ? " · actual"
                    : matchday === 1
                      ? " · pretemporada"
                      : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="control-block">
            <h3>Fuerza por equipo</h3>
            <p className="control-hint">
              Mueve el Elo de cada equipo. +100 lo hace claramente más fuerte;
              −100, más débil. Los cambios se aplican al instante tras una
              pausa breve.
            </p>
            <div className="slider-list">
              {season.teams.map((team) => {
                const value = state.elo[team.id] ?? 0;
                return (
                  <div className="slider-row" key={team.id}>
                    <label htmlFor={`elo-${team.id}`} title={team.name}>
                      {team.short_name}
                    </label>
                    <input
                      id={`elo-${team.id}`}
                      type="range"
                      min={-200}
                      max={200}
                      step={5}
                      value={value}
                      onChange={(event) =>
                        updateElo(team.id, Number(event.target.value))
                      }
                      aria-valuetext={`${value > 0 ? "+" : ""}${value} Elo`}
                    />
                    <output htmlFor={`elo-${team.id}`}>
                      {value > 0 ? "+" : ""}
                      {value}
                    </output>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="control-block">
            <h3>Forzar jornada {season.current_matchday}</h3>
            <p className="control-hint">
              Elige un resultado y el modelo simulará el resto de la temporada
              desde ahí. Vuelve a pulsar para quitarlo.
            </p>
            <div className="force-list">
              {currentMatches.map((prediction) => {
                const home = teamMap.get(prediction.home_id);
                const away = teamMap.get(prediction.away_id);
                if (!home || !away) return null;
                const forced = state.forced[prediction.match_id];
                return (
                  <div className="force-match" key={prediction.match_id}>
                    <div className="force-teams">
                      <span>{home.short_name}</span>
                      <span className="vs">vs</span>
                      <span>{away.short_name}</span>
                    </div>
                    <div className="force-buttons" role="group" aria-label={`${home.name} contra ${away.name}`}>
                      <button
                        type="button"
                        aria-pressed={forced === "H"}
                        onClick={() => toggleForced(prediction.match_id, "H")}
                        title={`Gana ${home.name}`}
                      >
                        1
                      </button>
                      <button
                        type="button"
                        aria-pressed={forced === "D"}
                        onClick={() => toggleForced(prediction.match_id, "D")}
                        title="Empate"
                      >
                        X
                      </button>
                      <button
                        type="button"
                        aria-pressed={forced === "A"}
                        onClick={() => toggleForced(prediction.match_id, "A")}
                        title={`Gana ${away.name}`}
                      >
                        2
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <details className="advanced">
            <summary>Ajustes avanzados</summary>
            <div className="advanced-body">
              <div className="slider-row">
                <label htmlFor="home-advantage">Local</label>
                <input
                  id="home-advantage"
                  type="range"
                  min={0}
                  max={120}
                  step={5}
                  value={homeAdvantage}
                  onChange={(event) =>
                    setState((current) => ({
                      ...current,
                      homeAdvantage: Number(event.target.value),
                    }))
                  }
                />
                <output htmlFor="home-advantage">
                  {homeAdvantage.toFixed(0)}
                </output>
              </div>
              <div className="slider-row">
                <label htmlFor="nu">Empate</label>
                <input
                  id="nu"
                  type="range"
                  min={0.2}
                  max={2}
                  step={0.05}
                  value={nu}
                  onChange={(event) =>
                    setState((current) => ({
                      ...current,
                      nu: Number(event.target.value),
                    }))
                  }
                />
                <output htmlFor="nu">{nu.toFixed(2)}</output>
              </div>
              <div className="slider-row">
                <label htmlFor="rho">ρ goles</label>
                <input
                  id="rho"
                  type="range"
                  min={-0.15}
                  max={0.05}
                  step={0.01}
                  value={rho}
                  onChange={(event) =>
                    setState((current) => ({
                      ...current,
                      rho: Number(event.target.value),
                    }))
                  }
                />
                <output htmlFor="rho">{rho.toFixed(2)}</output>
              </div>
              <div style={{ marginTop: 14 }}>
                <span className="controls-label">Simulaciones</span>
                <div className="segmented" style={{ marginTop: 6 }} role="group" aria-label="Simulaciones del escenario">
                  {[5000, 10000, 30000].map((value) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={state.sims === value}
                      onClick={() =>
                        setState((current) => ({ ...current, sims: value }))
                      }
                    >
                      {value >= 1000 ? `${value / 1000}k` : value}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </details>

          <div className="control-block">
            <div className="page-actions">
              <button type="button" className="btn btn-primary" onClick={copyShareLink}>
                Compartir escenario
              </button>
              <button type="button" className="btn btn-danger" onClick={resetScenario}>
                Restablecer
              </button>
            </div>
            {shareMessage ? (
              <p className="control-hint" style={{ marginTop: 10, marginBottom: 0 }} role="status">
                {shareMessage}
              </p>
            ) : null}
          </div>
        </aside>

        <div className="scenario-main">
          {!activeBaseline ? (
            <div className="notice" role="status" aria-live="polite">
              <strong>Actualizando base.</strong>
              <span>
                Calculando la proyección desde la jornada {state.startMatchday}…
              </span>
            </div>
          ) : null}

          {runError ? (
            <div className="notice" role="alert">
              <strong>El escenario no se pudo recalcular.</strong>
              <span>{runError}</span>
            </div>
          ) : null}

          <div className="summary-grid">
            <div className="summary-card">
              <span>Favorito del escenario</span>
              <strong>
                {currentFavorite ? formatProbability(currentFavorite.champion_probability) : "—"}
              </strong>
              <small>{currentFavorite?.team.name ?? "Sin datos"}</small>
            </div>
            <div className="summary-card">
              <span>Mayor subida</span>
              <strong style={{ color: "var(--good)" }}>
                {riser ? formatSignedProbability(riser.delta) : "—"}
              </strong>
              <small>{riser?.team.team.name ?? "Sin cambios"}</small>
            </div>
            <div className="summary-card">
              <span>Mayor caída</span>
              <strong style={{ color: "var(--danger)" }}>
                {faller ? formatSignedProbability(faller.delta) : "—"}
              </strong>
              <small>{faller?.team.team.name ?? "Sin cambios"}</small>
            </div>
          </div>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2 className="panel-title">Base vs escenario</h2>
                <span className="panel-note">
                  Deltas en puntos porcentuales. Verde sube, rojo baja.
                </span>
              </div>
              <span className={`chip ${running ? "chip-accent" : ""}`}>
                {isRunning ? "Calculando" : `${(displayResult?.n_sims ?? 0).toLocaleString("es-ES")} sims`}
              </span>
            </div>
            <div className="panel-body" style={{ paddingTop: 0 }}>
              <div className="table-wrap">
                <table className="league-table comparison-table">
                  <thead>
                    <tr>
                      <th scope="col">Equipo</th>
                      <th scope="col">Campeón base</th>
                      <th scope="col">Campeón esc.</th>
                      <th scope="col">Δ</th>
                      <th scope="col" className="optional">Top 4 base</th>
                      <th scope="col">Top 4 esc.</th>
                      <th scope="col">Δ</th>
                      <th scope="col">Descenso esc.</th>
                      <th scope="col">Pts esp.</th>
                      <th scope="col">Δ pts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {projectionTeams.map((team) => {
                      const base = baselineMap.get(team.team.id);
                      const deltaChampion =
                        team.champion_probability - (base?.champion_probability ?? 0);
                      const deltaTop4 =
                        team.top4_probability - (base?.top4_probability ?? 0);
                      const deltaPoints =
                        team.expected_points - (base?.expected_points ?? 0);
                      return (
                        <tr key={team.team.id}>
                          <td className="team-cell">
                            <TeamBadge team={team.team} />
                          </td>
                          <td className="num">{base ? formatProbability(base.champion_probability) : "—"}</td>
                          <td className="num">{formatProbability(team.champion_probability)}</td>
                          <td>
                            <span className={`delta ${deltaTone(deltaChampion)}`}>
                              {formatSignedProbability(deltaChampion)}
                            </span>
                          </td>
                          <td className="num optional">
                            {base ? formatProbability(base.top4_probability) : "—"}
                          </td>
                          <td className="num">{formatProbability(team.top4_probability)}</td>
                          <td>
                            <span className={`delta ${deltaTone(deltaTop4)}`}>
                              {formatSignedProbability(deltaTop4)}
                            </span>
                          </td>
                          <td className="num">{formatProbability(team.relegation_probability)}</td>
                          <td className="num">{team.expected_points.toFixed(1)}</td>
                          <td>
                            <span className={`delta ${deltaPoints > 0.05 ? "up" : deltaPoints < -0.05 ? "down" : "flat"}`}>
                              {formatSignedPoints(deltaPoints)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {displayResult && displayResult.teams.length > 0 ? (
            <PointsDistribution
              teams={displayResult.teams}
              selectedTeam={selected}
              onSelect={setSelectedTeam}
            />
          ) : null}

          {selectedProjection ? (
            <section className="panel">
              <div className="panel-body" style={{ display: "grid", gap: 10 }}>
                <span className="kicker">Detalle del escenario</span>
                <p className="lead">
                  {selectedProjection.team.name}: {formatProbability(selectedProjection.champion_probability)} de
                  título, {formatProbability(selectedProjection.top4_probability)} de Top 4 y{" "}
                  {formatProbability(selectedProjection.relegation_probability)} de descenso.
                  Rango de puntos {selectedProjection.p10_points}–{selectedProjection.p90_points}.
                </p>
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
