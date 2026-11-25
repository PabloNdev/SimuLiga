"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getJob,
  getProjection,
  getSeason,
  postFullProjection,
  STATIC_DATA,
} from "@/lib/api";
import {
  DEFAULT_SIMS,
  LALIGA_MAX_SIMS,
  LALIGA_SIM_PRESETS,
  LALIGA_SYNC_API_LIMIT,
  type SimulationProgress,
} from "@/lib/sim-config";
import type { Mode, ProjectionPayload, SeasonPayload } from "@/lib/types";
import { formatProbability, formatUpdatedAt } from "@/lib/format";
import { FavoriteCard } from "@/components/FavoriteCard";
import { Fixtures } from "@/components/Fixtures";
import { Heatmap } from "@/components/Heatmap";
import { LeagueTable, type Metric } from "@/components/LeagueTable";
import { PointsDistribution } from "@/components/PointsDistribution";
import {
  SimSizeControl,
  SimulationProgressNotice,
} from "@/components/SimSizeControl";
import { TitleRace } from "@/components/TitleRace";
import { ErrorState, SkeletonPanel } from "@/components/States";

export function Dashboard() {
  const [season, setSeason] = useState<SeasonPayload | null>(null);
  const [projection, setProjection] = useState<ProjectionPayload | null>(null);
  const [mode, setMode] = useState<Mode>("score");
  const [sims, setSims] = useState<number>(DEFAULT_SIMS);
  const [metric, setMetric] = useState<Metric>("champion");
  const [startMatchday, setStartMatchday] = useState<number | null>(null);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<SimulationProgress | null>(null);

  const pollRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const previousSimsRef = useRef<number>(DEFAULT_SIMS);

  function clearActiveRun() {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }

  function beginRunState(nextSims: number) {
    const showProgress = nextSims >= 20_000;
    setError(null);
    setSimulating(true);
    if (showProgress) {
      setJobProgress({
        completed: 0,
        total: nextSims,
        progress: 0,
        elapsedSeconds: 0,
      });
      setJobMessage(
        STATIC_DATA
          ? `Simulando ${nextSims.toLocaleString("es-ES")} temporadas en tu navegador…`
          : `Simulando ${nextSims.toLocaleString("es-ES")} temporadas en el servidor…`,
      );
    } else {
      setJobProgress(null);
      setJobMessage(null);
    }
  }

  useEffect(() => {
    clearActiveRun();
    const controller = new AbortController();
    abortRef.current = controller;

    const showProgress = sims >= 20_000;
    const isAsyncBackendJob = !STATIC_DATA && sims > LALIGA_SYNC_API_LIMIT;

    const run = async () => {
      try {
        const seasonPayload = await getSeason(controller.signal);
        if (controller.signal.aborted) return;
        setSeason(seasonPayload);
        const effectiveStart = startMatchday ?? seasonPayload.current_matchday;
        if (startMatchday === null) {
          setStartMatchday(effectiveStart);
        }

        if (isAsyncBackendJob) {
          const created = await postFullProjection(
            {
              mode,
              sims,
              seed: 42,
              start_matchday: effectiveStart,
            },
            controller.signal,
          );
          if (controller.signal.aborted) return;

          await new Promise<void>((resolve, reject) => {
            const onAbort = () => {
              if (pollRef.current !== null) {
                window.clearInterval(pollRef.current);
                pollRef.current = null;
              }
              reject(new DOMException("Cancelado", "AbortError"));
            };
            controller.signal.addEventListener("abort", onAbort, { once: true });

            pollRef.current = window.setInterval(async () => {
              try {
                const job = await getJob(created.job_id, controller.signal);
                setJobProgress({
                  completed: job.completed_sims,
                  total: sims,
                  progress: job.progress,
                  elapsedSeconds: job.elapsed_seconds,
                });
                if (job.status === "done" && job.result) {
                  if (pollRef.current !== null) {
                    window.clearInterval(pollRef.current);
                    pollRef.current = null;
                  }
                  controller.signal.removeEventListener("abort", onAbort);
                  setProjection(job.result);
                  previousSimsRef.current = job.result.n_sims;
                  setSelectedTeam(
                    (current) =>
                      current ?? job.result?.teams[0]?.team.id ?? null,
                  );
                  setJobProgress(null);
                  setJobMessage(
                    `Listo: ${job.result.n_sims.toLocaleString("es-ES")} temporadas en ${job.result.elapsed_seconds.toFixed(1)} s.`,
                  );
                  resolve();
                } else if (job.status === "error") {
                  if (pollRef.current !== null) {
                    window.clearInterval(pollRef.current);
                    pollRef.current = null;
                  }
                  controller.signal.removeEventListener("abort", onAbort);
                  reject(
                    new Error(job.error ?? "La simulación completa falló."),
                  );
                }
              } catch (caught) {
                if (pollRef.current !== null) {
                  window.clearInterval(pollRef.current);
                  pollRef.current = null;
                }
                controller.signal.removeEventListener("abort", onAbort);
                reject(caught);
              }
            }, 1500);
          });
        } else {
          const projectionPayload = await getProjection(
            mode,
            sims,
            effectiveStart,
            controller.signal,
            showProgress
              ? (progress) => {
                  if (!controller.signal.aborted) {
                    setJobProgress(progress);
                  }
                }
              : undefined,
          );
          if (controller.signal.aborted) return;
          setProjection(projectionPayload);
          previousSimsRef.current = projectionPayload.n_sims;
          setSelectedTeam(
            (current) =>
              current ?? projectionPayload.teams[0]?.team.id ?? null,
          );
          setJobProgress(null);
          if (showProgress) {
            setJobMessage(
              `Listo: ${projectionPayload.n_sims.toLocaleString("es-ES")} temporadas en ${projectionPayload.elapsed_seconds.toFixed(2)} s.`,
            );
          }
        }
        setLoading(false);
        setSimulating(false);
      } catch (caught: unknown) {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        setJobProgress(null);
        setSimulating(false);
        const message =
          caught instanceof ApiError || caught instanceof Error
            ? caught.message
            : "Error inesperado";
        if (projection) {
          setJobMessage(message);
        } else {
          setError(message);
          setLoading(false);
        }
      }
    };

    run();

    return () => {
      clearActiveRun();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, sims, startMatchday, reloadKey]);

  function changeStart(nextStart: number) {
    if (nextStart === startMatchday) return;
    beginRunState(sims);
    setStartMatchday(nextStart);
  }

  function changeMode(nextMode: Mode) {
    if (nextMode === mode) return;
    beginRunState(sims);
    setMode(nextMode);
  }

  function changeSims(nextSims: number) {
    if (nextSims === sims) return;
    beginRunState(nextSims);
    setSims(nextSims);
  }

  function cancelRun() {
    clearActiveRun();
    setSimulating(false);
    setJobProgress(null);
    setJobMessage("Simulación cancelada.");
    if (sims !== previousSimsRef.current) {
      setSims(previousSimsRef.current);
    }
  }

  if (loading && !season) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">Panel de proyecciones</span>
            <h1 className="page-title">
              LaLiga, jugada <em>{DEFAULT_SIMS.toLocaleString("es-ES")}</em> veces.
            </h1>
          </div>
        </div>
        <div className="hero-grid">
          <SkeletonPanel height={260} />
          <SkeletonPanel height={260} />
        </div>
        <SkeletonPanel height={420} />
      </div>
    );
  }

  if (error || !season || !projection) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">Panel de proyecciones</span>
            <h1 className="page-title">
              LaLiga, jugada {sims.toLocaleString("es-ES")} veces.
            </h1>
          </div>
        </div>
        <ErrorState
          message={error ?? "No se pudo cargar la temporada."}
          onRetry={() => {
            setLoading(true);
            setError(null);
            setReloadKey((value) => value + 1);
          }}
        />
      </div>
    );
  }

  const favorite = [...projection.teams].sort(
    (a, b) => b.champion_probability - a.champion_probability,
  )[0];
  const selected = selectedTeam ?? projection.teams[0]?.team.id ?? "";
  const simulations = projection.n_sims.toLocaleString("es-ES");

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <span className="kicker">Panel de proyecciones · LaLiga 2026/27</span>
          <h1 className="page-title">
            LaLiga, jugada <em>{simulations}</em> veces.
          </h1>
          <p className="page-sub">
            Cada porcentaje nace de repetir la temporada entera. Mira quién
            manda hoy, qué rango de puntos le espera y qué puede cambiar si
            ajustas una fuerza o fuerzas un resultado.
          </p>
        </div>
        <div className="status-row">
          <span className="chip">
            Jornada actual <strong>{season.current_matchday}</strong>
          </span>
          <span className="chip chip-accent">
            Simulando desde <strong>J{startMatchday ?? season.current_matchday}</strong>
          </span>
          <span className="chip">
            Jugados <strong>{season.played_matches}</strong> /{" "}
            {season.played_matches + season.pending_matches}
          </span>
          <span className="chip chip-accent">
            <strong>{simulations}</strong> temporadas
          </span>
        </div>
      </div>

      <div className="hero-grid">
        <section className="hero-copy rise">
          <span className="kicker">Lectura rápida</span>
          <h2 className="hero-headline">
            El favorito es <span>{favorite.team.name}</span>.
          </h2>
          <p className="hero-text">
            No es una promesa: es la proporción de veces que el modelo lo deja
            primero. La tabla de abajo combina los puntos reales con lo que aún
            puede pasar.
          </p>
          <div className="hero-stats">
            <div className="hero-stat">
              <strong>{formatProbability(favorite.champion_probability)}</strong>
              <span>campeón</span>
            </div>
            <div className="hero-stat">
              <strong>{favorite.expected_points.toFixed(0)}</strong>
              <span>puntos esperados</span>
            </div>
            <div className="hero-stat">
              <strong>
                {favorite.p10_points}–{favorite.p90_points}
              </strong>
              <span>rango probable</span>
            </div>
            <div className="hero-stat">
              <strong>{formatUpdatedAt(season.updated_at)}</strong>
              <span>última actualización</span>
            </div>
          </div>
        </section>
        <FavoriteCard season={season} projection={projection} />
      </div>

      <div className="controls" role="toolbar" aria-label="Controles de proyección">
        <span className="controls-label">Resultado</span>
        <div className="segmented" role="group" aria-label="Modo de simulación">
          <button
            type="button"
            aria-pressed={mode === "score"}
            onClick={() => changeMode("score")}
            title="Simula marcadores exactos y aplica todos los criterios de desempate de LaLiga."
          >
            Marcador exacto
          </button>
          <button
            type="button"
            aria-pressed={mode === "1x2"}
            onClick={() => changeMode("1x2")}
            title="Simula solo victoria local, empate o victoria visitante."
          >
            Solo 1X2
          </button>
        </div>

        <span className="controls-label">Desde J</span>
        <select
          className="matchday-select"
          value={startMatchday ?? season.current_matchday}
          onChange={(event) => changeStart(Number(event.target.value))}
          aria-label="Jornada de inicio de la simulación"
          title="Se conservan los resultados reales anteriores y se simula desde esta jornada."
        >
          {Array.from(
            { length: season.total_matchdays },
            (_, index) => index + 1,
          ).map((matchday) => (
            <option key={matchday} value={matchday}>
              {matchday}
              {matchday === season.current_matchday
                ? " · actual"
                : matchday === 1
                  ? " · pretemporada"
                  : ""}
            </option>
          ))}
        </select>

        <span className="controls-label">Simulaciones</span>
        <SimSizeControl
          id="laliga-sim-size"
          value={sims}
          presets={LALIGA_SIM_PRESETS}
          maxSims={LALIGA_MAX_SIMS}
          onChange={changeSims}
        />

        <span className="controls-label">Métrica</span>
        <div className="segmented" role="group" aria-label="Métrica de la tabla">
          <button
            type="button"
            aria-pressed={metric === "champion"}
            onClick={() => setMetric("champion")}
          >
            Campeón
          </button>
          <button
            type="button"
            aria-pressed={metric === "top4"}
            onClick={() => setMetric("top4")}
          >
            Top 4
          </button>
          <button
            type="button"
            aria-pressed={metric === "relegation"}
            onClick={() => setMetric("relegation")}
          >
            Descenso
          </button>
        </div>

        <span className="controls-spacer" />
        <Link href="/escenario" className="btn btn-primary">
          Abrir laboratorio
        </Link>
      </div>

      <p className="controls-hint">
        {startMatchday === 1
          ? "Proyección desde cero: no se usa ningún resultado real; todos los partidos se simulan con el Elo inicial."
          : `Se conservan los resultados reales anteriores a la jornada ${startMatchday ?? season.current_matchday}; desde ahí se simula con el Elo de ese momento.`}
        {" "}Por defecto se usan {DEFAULT_SIMS.toLocaleString("es-ES")} temporadas pensando en móviles; puedes subir el tamaño o introducir uno propio.
      </p>

      {STATIC_DATA ? (
        <div className="notice" style={{ marginBottom: 18 }}>
          <strong>Simulación en tu navegador.</strong>
          <span>
            Resultados reales actualizados el {formatUpdatedAt(season.updated_at)}.
            El cálculo Monte Carlo corre en tu dispositivo ({projection.elapsed_seconds.toFixed(2)} s).
          </span>
        </div>
      ) : null}

      {season.demo ? (
        <div className="notice" style={{ marginBottom: 18 }}>
          <strong>Datos de demostración.</strong>
          <span>
            Las 8 jornadas jugadas se generaron con el propio modelo para que el
            panel sea explorable. Al configurar <code>API_FOOTBALL_KEY</code>, el
            backend sustituye esta base por calendario y resultados reales.
          </span>
        </div>
      ) : null}

      {jobMessage ? (
        <SimulationProgressNotice
          message={jobMessage}
          progress={jobProgress}
          running={simulating}
          onCancel={simulating ? cancelRun : undefined}
        />
      ) : null}

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="panel-title">Tabla aumentada</h2>
              <span className="panel-note">
                Posición actual, proyección media y{" "}
                {metric === "champion"
                  ? "probabilidad de título"
                  : metric === "top4"
                    ? "probabilidad de Top 4"
                    : "riesgo de descenso"}
                .
              </span>
            </div>
            <span className="chip">Ordenada por posición esperada</span>
          </div>
          <div className="panel-body" style={{ paddingTop: 0 }}>
            <LeagueTable
              season={season}
              projection={projection.teams}
              metric={metric}
              selectedTeam={selected}
              onSelect={setSelectedTeam}
              baseStandings={projection.base_standings}
              baseLabel={
                startMatchday == null || startMatchday >= season.current_matchday
                  ? "Hoy"
                  : startMatchday === 1
                    ? "Pretemporada"
                    : `Hasta J${startMatchday - 1}`
              }
            />
          </div>
        </section>

        <div className="side-stack">
          <TitleRace teams={projection.teams} />
          <Fixtures season={season} predictions={projection.match_predictions} />
        </div>
      </div>

      <Heatmap teams={projection.teams} />

      <div className="section-gap">
        <PointsDistribution
          teams={projection.teams}
          selectedTeam={selected}
          onSelect={setSelectedTeam}
        />
      </div>

      <div className="section-gap">
        <section className="panel">
          <div className="panel-body" style={{ display: "grid", gap: 10 }}>
            <span className="kicker">Cómo leerlo</span>
            <p className="lead">
              Una probabilidad del 30% no significa que ocurrirá tres de cada
              diez veces en la realidad: significa que ocurrió en el 30% de las
              temporadas simuladas con los datos y el modelo actuales. Si dos
              equipos terminan con los mismos puntos, se aplican los criterios
              de LaLiga: primero los duelos directos y después la diferencia de
              goles.
            </p>
            <div className="page-actions">
              <Link href="/metodologia" className="link-arrow">
                Ver el método completo
              </Link>
              <Link href="/escenario" className="link-arrow">
                Probar un escenario
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
