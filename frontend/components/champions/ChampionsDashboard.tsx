"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  getChampionsMatches,
  getChampionsProjection,
  getChampionsSeason,
} from "@/lib/champions-api";
import type {
  ChampionsMatchesPayload,
  ChampionsProjectionPayload,
  ChampionsSeasonPayload,
} from "@/lib/champions-types";
import type { Mode } from "@/lib/types";
import { formatProbability, formatUpdatedAt } from "@/lib/format";
import { ErrorState, SkeletonPanel } from "@/components/States";
import { ChampionsMatches } from "@/components/champions/ChampionsMatches";
import { LeaguePhaseTable } from "@/components/champions/LeaguePhaseTable";
import { PositionHeatmap } from "@/components/champions/PositionHeatmap";
import { ProjectionTable } from "@/components/champions/ProjectionTable";

const SIMS = 10_000;

export function ChampionsDashboard() {
  const [season, setSeason] = useState<ChampionsSeasonPayload | null>(null);
  const [projection, setProjection] = useState<ChampionsProjectionPayload | null>(null);
  const [matches, setMatches] = useState<ChampionsMatchesPayload | null>(null);
  const [mode, setMode] = useState<Mode>("score");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  function changeMode(next: Mode) {
    if (next === mode) return;
    setLoading(true);
    setError(null);
    setMode(next);
  }

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getChampionsSeason(controller.signal),
      getChampionsProjection(SIMS, mode, controller.signal),
      getChampionsMatches(mode, controller.signal),
    ])
      .then(([seasonPayload, projectionPayload, matchesPayload]) => {
        setSeason(seasonPayload);
        setProjection(projectionPayload);
        setMatches(matchesPayload);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught.message : "Error inesperado");
        setLoading(false);
      });
    return () => controller.abort();
  }, [mode, reloadKey]);

  if (loading && !season) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">Panel de proyecciones · Champions League</span>
            <h1 className="page-title">
              La Champions, jugada <em>10.000</em> veces.
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
            <span className="kicker">Panel de proyecciones · Champions League</span>
            <h1 className="page-title">La Champions, jugada 10.000 veces.</h1>
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
            Panel de proyecciones · Champions League {season.target_season ?? season.season}
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
        <span className="controls-label">Resultado</span>
        <div className="segmented" role="group" aria-label="Modo de simulación">
          <button
            type="button"
            aria-pressed={mode === "score"}
            onClick={() => changeMode("score")}
            title="Simula marcadores exactos y usa goles para los desempates."
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
        <span className="controls-spacer" />
        <Link href="/champions/playoff" className="btn">
          Ver playoff
        </Link>
        <Link href="/champions/metodologia" className="btn btn-primary">
          Cómo se calcula
        </Link>
      </div>
      <p className="controls-hint">
        {mode === "score"
          ? "Se simulan marcadores exactos para aplicar puntos, diferencia de goles, goles a favor y goles fuera."
          : "Solo se simula el 1X2: los desempates usan puntos, victorias y sorteo determinista."}
      </p>

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
              <strong>{formatProbability(favorite.round_of_16_probability)}</strong>
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
              <strong>{formatProbability(favorite.eliminated_probability)}</strong>
            </div>
            <div className="champions-favorite-row">
              <span>Ganar playoff</span>
              <strong>{formatProbability(favorite.playoff_win_probability)}</strong>
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
              temporadas simuladas con los datos y el modelo actuales. La fase
              de liga no tiene duelos directos para todos: los desempates son
              puntos, diferencia de goles, goles, goles fuera, victorias,
              victorias fuera y sorteo.
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

