"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { STATIC_DATA } from "@/lib/api";
import {
  getChampionsMatches,
  getChampionsProjection,
  getChampionsSeason,
} from "@/lib/champions-api";
import {
  CHAMPIONS_MAX_SIMS_API,
  CHAMPIONS_MAX_SIMS_BROWSER,
  CHAMPIONS_SIM_PRESETS,
  DEFAULT_SIMS,
  type SimulationProgress,
} from "@/lib/sim-config";
import type {
  ChampionsMatchesPayload,
  ChampionsProjectionPayload,
  ChampionsSeasonPayload,
} from "@/lib/champions-types";
import type { Mode } from "@/lib/types";
import { formatProbability, formatUpdatedAt } from "@/lib/format";
import { ErrorState, SkeletonPanel } from "@/components/States";
import {
  SimSizeControl,
  SimulationProgressNotice,
} from "@/components/SimSizeControl";
import { ChampionsMatches } from "@/components/champions/ChampionsMatches";
import { LeaguePhaseTable } from "@/components/champions/LeaguePhaseTable";
import { PositionHeatmap } from "@/components/champions/PositionHeatmap";
import { ProjectionTable } from "@/components/champions/ProjectionTable";

const SIMULATION_MODE: Mode = "1x2";

export function ChampionsDashboard() {
  const [season, setSeason] = useState<ChampionsSeasonPayload | null>(null);
  const [projection, setProjection] =
    useState<ChampionsProjectionPayload | null>(null);
  const [matches, setMatches] = useState<ChampionsMatchesPayload | null>(null);
  const [sims, setSims] = useState<number>(DEFAULT_SIMS);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<SimulationProgress | null>(
    null,
  );

  const abortRef = useRef<AbortController | null>(null);
  const previousSimsRef = useRef<number>(DEFAULT_SIMS);
  const maxSims = STATIC_DATA
    ? CHAMPIONS_MAX_SIMS_BROWSER
    : CHAMPIONS_MAX_SIMS_API;

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
          ? `Simulando ${nextSims.toLocaleString("es-ES")} Champions en tu navegador…`
          : `Simulando ${nextSims.toLocaleString("es-ES")} Champions en el servidor…`,
      );
    } else {
      setJobProgress(null);
      setJobMessage(null);
    }
  }

  function changeSims(nextSims: number) {
    if (nextSims === sims) return;
    beginRunState(nextSims);
    setSims(nextSims);
  }

  function cancelRun() {
    abortRef.current?.abort();
    abortRef.current = null;
    setSimulating(false);
    setJobProgress(null);
    setJobMessage("Simulación cancelada.");
    if (sims !== previousSimsRef.current) {
      setSims(previousSimsRef.current);
    }
  }

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const showProgress = sims >= 20_000;

    Promise.all([
      getChampionsSeason(controller.signal),
      getChampionsProjection(
        sims,
        SIMULATION_MODE,
        controller.signal,
        showProgress
          ? (progress) => {
              if (!controller.signal.aborted) setJobProgress(progress);
            }
          : undefined,
      ),
      getChampionsMatches(SIMULATION_MODE, controller.signal),
    ])
      .then(([seasonPayload, projectionPayload, matchesPayload]) => {
        if (controller.signal.aborted) return;
        setSeason(seasonPayload);
        setProjection(projectionPayload);
        previousSimsRef.current = projectionPayload.n_sims;
        setMatches(matchesPayload);
        setLoading(false);
        setSimulating(false);
        setJobProgress(null);
        if (showProgress) {
          setJobMessage(
            `Listo: ${projectionPayload.n_sims.toLocaleString("es-ES")} Champions en ${projectionPayload.elapsed_seconds.toFixed(2)} s.`,
          );
        }
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setSimulating(false);
        setJobProgress(null);
        const message =
          caught instanceof Error ? caught.message : "Error inesperado";
        if (projection) {
          setJobMessage(message);
        } else {
          setError(message);
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sims, reloadKey]);

  if (loading && !season) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">
              Panel de proyecciones · Champions League
            </span>
            <h1 className="page-title">
              La Champions, jugada{" "}
              <em>{DEFAULT_SIMS.toLocaleString("es-ES")}</em> veces.
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

  if (error || !season || !projection || !matches) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">
              Panel de proyecciones · Champions League
            </span>
            <h1 className="page-title">
              La Champions, jugada {sims.toLocaleString("es-ES")} veces.
            </h1>
          </div>
        </div>
        <ErrorState
          message={error ?? "No se pudo cargar la temporada de Champions."}
          onRetry={() => {
            setError(null);
            setLoading(true);
            setReloadKey((value) => value + 1);
          }}
        />
      </div>
    );
  }

  const favorite = [...projection.teams].sort(
    (a, b) => b.round_of_16_probability - a.round_of_16_probability,
  )[0];
  const simulations = projection.n_sims.toLocaleString("es-ES");
  const fallbackNotice = season.demo
    ? "Datos de demostración: calendario generado y resultados simulados."
    : season.fallback
      ? "La temporada 2026/27 todavía no está disponible en las fuentes. Se muestra 2025/26 con las primeras jornadas reales y el resto simulado."
      : null;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <span className="kicker">
            Panel de proyecciones · Champions League{" "}
            {season.target_season ?? season.season}
          </span>
          <h1 className="page-title">
            La Champions, jugada <em>{simulations}</em> veces.
          </h1>
          <p className="page-sub">
            36 equipos, 8 jornadas y una única tabla. Mira quién entra directo a
            octavos, quién cae al playoff y qué rival le espera.
          </p>
        </div>
        <div className="status-row">
          <span className="chip">
            Jornada actual <strong>{season.current_matchday}</strong>
          </span>
          <span className="chip chip-accent">
            Jugados <strong>{season.played_matches}</strong> /{" "}
            {season.played_matches + season.pending_matches}
          </span>
          <span className="chip">
            Fuente <strong>{season.source}</strong>
          </span>
          <span className="chip">
            <strong>{formatUpdatedAt(season.updated_at)}</strong>
          </span>
        </div>
      </div>

      {fallbackNotice ? (
        <div className="notice" style={{ marginBottom: 18 }}>
          <strong>{season.demo ? "Demostración." : "Temporada en espera."}</strong>
          <span>{fallbackNotice}</span>
        </div>
      ) : null}

      <div className="controls" role="toolbar" aria-label="Controles de proyección">
        <span className="controls-label">Simulaciones</span>
        <SimSizeControl
          id="champions-sim-size"
          value={sims}
          presets={CHAMPIONS_SIM_PRESETS}
          maxSims={maxSims}
          onChange={changeSims}
        />

        <span className="controls-spacer" />
        <Link href="/champions/playoff" className="btn">
          Ver playoff
        </Link>
        <Link href="/champions/metodologia" className="btn btn-primary">
          Cómo se calcula
        </Link>
      </div>
      <p className="controls-hint">
        Se simula el resultado 1X2 de cada partido pendiente: los desempates
        usan puntos, victorias y sorteo determinista. Por defecto{" "}
        {DEFAULT_SIMS.toLocaleString("es-ES")} simulaciones pensando en móviles;
        ajusta el tamaño si quieres más precisión.
      </p>

      {STATIC_DATA ? (
        <div className="notice" style={{ marginBottom: 18 }}>
          <strong>Simulación en tu navegador.</strong>
          <span>
            Resultados reales actualizados el {formatUpdatedAt(season.updated_at)}.
            Fase de liga y playoff calculados en tu dispositivo ({projection.elapsed_seconds.toFixed(2)} s).
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

      <div className="hero-grid">
        <section className="hero-copy rise">
          <span className="kicker">Lectura rápida</span>
          <h2 className="hero-headline">
            El favorito para octavos es <span>{favorite.team.name}</span>.
          </h2>
          <p className="hero-text">
            No es una promesa: es la proporción de simulaciones en las que
            termina entre los ocho primeros o gana su eliminatoria de playoff.
          </p>
          <div className="hero-stats">
            <div className="hero-stat">
              <strong>
                {formatProbability(favorite.round_of_16_probability)}
              </strong>
              <span>octavos</span>
            </div>
            <div className="hero-stat">
              <strong>{formatProbability(favorite.top8_probability)}</strong>
              <span>top 8</span>
            </div>
            <div className="hero-stat">
              <strong>{favorite.expected_points.toFixed(1)}</strong>
              <span>puntos esperados</span>
            </div>
            <div className="hero-stat">
              <strong>
                {favorite.p10_points}–{favorite.p90_points}
              </strong>
              <span>rango probable</span>
            </div>
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="panel-title">El favorito</h2>
              <span className="panel-note">{favorite.team.name}</span>
            </div>
            <span className="chip">J{season.current_matchday}</span>
          </div>
          <div className="panel-body champions-favorite">
            <div className="champions-favorite-row">
              <span>Top 8</span>
              <strong>{formatProbability(favorite.top8_probability)}</strong>
            </div>
            <div className="champions-favorite-row">
              <span>Playoff</span>
              <strong>{formatProbability(favorite.playoff_probability)}</strong>
            </div>
            <div className="champions-favorite-row">
              <span>Eliminado</span>
              <strong>
                {formatProbability(favorite.eliminated_probability)}
              </strong>
            </div>
            <div className="champions-favorite-row">
              <span>Ganar playoff</span>
              <strong>
                {formatProbability(favorite.playoff_win_probability)}
              </strong>
            </div>
            <div className="champions-favorite-row">
              <span>Posición más probable</span>
              <strong>{favorite.most_likely_position}.º</strong>
            </div>
          </div>
        </section>
      </div>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="panel-title">Fase de liga</h2>
              <span className="panel-note">
                Tabla única de 36 equipos. Los resultados reales se conservan y
                los pendientes se simulan.
              </span>
            </div>
            <span className="chip">Jornada {season.current_matchday}</span>
          </div>
          <div className="panel-body" style={{ paddingTop: 0 }}>
            <LeaguePhaseTable
              standings={season.standings}
              matches={matches.matches}
            />
          </div>
        </section>
        <div className="side-stack">
          <ChampionsMatches
            matches={matches.matches}
            currentMatchday={matches.current_matchday}
          />
        </div>
      </div>

      <div className="section-gap">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="panel-title">Proyección por equipo</h2>
              <span className="panel-note">
                Puntos esperados, probabilidades de clasificación y rival más
                probable en el playoff.
              </span>
            </div>
            <span className="chip">{simulations} simulaciones</span>
          </div>
          <div className="panel-body" style={{ paddingTop: 0 }}>
            <ProjectionTable
              teams={projection.teams}
              matches={matches.matches}
            />
          </div>
        </section>
      </div>

      <div className="section-gap">
        <PositionHeatmap teams={projection.teams} />
      </div>

      <div className="section-gap">
        <section className="panel">
          <div className="panel-body" style={{ display: "grid", gap: 10 }}>
            <span className="kicker">Cómo leerlo</span>
            <p className="lead">
              Una probabilidad del 40% no significa que ocurrirá cuatro de cada
              diez veces en la realidad: significa que ocurrió en el 40% de las
              temporadas simuladas con los datos y el modelo actuales. Los
              partidos pendientes se simulan en formato 1X2 (sin goles
              simulados), manteniendo los goles reales ya disputados y
              resolviendo los empates por puntos, victorias y sorteo
              determinista.
            </p>
            <div className="page-actions">
              <Link href="/champions/playoff" className="link-arrow">
                Ver la previsión del playoff
              </Link>
              <Link href="/champions/elo" className="link-arrow">
                Ver el ELO de los 36 equipos
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
