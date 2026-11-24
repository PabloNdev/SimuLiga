"use client";

import { useEffect, useState } from "react";

import { getChampionsElo } from "@/lib/champions-api";
import type { ChampionsEloPayload } from "@/lib/champions-types";
import { deltaTone, formatElo, formatSignedPoints } from "@/lib/format";
import { ErrorState, LoadingState } from "@/components/States";
import { EloTimelineChart } from "@/components/EloTimelineChart";
import { TeamBadge } from "@/components/TeamBadge";

export function ChampionsElo() {
  const [elo, setElo] = useState<ChampionsEloPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getChampionsElo(controller.signal)
      .then(setElo)
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught.message : "Error inesperado");
      });
    return () => controller.abort();
  }, []);

  if (error) {
    return (
      <div className="container">
        <ErrorState message={error} />
      </div>
    );
  }

  if (!elo) {
    return (
      <div className="container">
        <LoadingState
          title="Cargando ELO"
          note="Recalculando ratings, replay de 5 temporadas y prior ClubElo."
        />
      </div>
    );
  }

  const verification = elo.verification;
  const validation = verification.params?.validation;
  const historySeasons =
    verification.history_seasons_loaded?.length ??
    verification.history_seasons ??
    0;
  const regression = Math.round(
    (verification.season_regression ?? 0.2) * 100,
  );
  const clubeloWeight = Math.round(
    (verification.clubelo_prior_weight ?? 0.75) * 100,
  );
  const clubeloText = verification.clubelo_prior
    ? ` y prior ClubElo del ${clubeloWeight} %`
    : "";
  const historyChip =
    verification.history_complete === true
      ? { label: "histórico completo", className: "chip chip-good" }
      : verification.history_complete === false
        ? { label: "histórico parcial", className: "chip chip-danger" }
        : { label: "histórico sin verificar", className: "chip" };

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <span className="kicker">ELO · Champions League</span>
          <h1 className="page-title">
            La fuerza de los <em>36</em>.
          </h1>
          <p className="page-sub">
            Rating reconstruido con el replay de las últimas 5 temporadas
            (2021/22–2025/26), regresión del {regression} %{clubeloText} al
            inicio de cada temporada. Los partidos de 2026/27 ya jugados se
            aplican después.
          </p>
        </div>
        <div className="status-row">
          <span className="chip">
            Fuente <strong>{elo.source}</strong>
          </span>
          <span className="chip">
            Replay{" "}
            <strong>
              {verification.history_matches_applied ??
                verification.matches_applied ??
                0}
            </strong>
            /
            {verification.history_matches_total ??
              verification.matches_total ??
              0}
          </span>
          <span className="chip">
            Temporadas <strong>{historySeasons}</strong>
          </span>
          <span className="chip">
            Semilla <strong>{verification.seed_source ?? "—"}</strong>
          </span>
          {verification.clubelo_prior ? (
            <span className="chip">
              Prior ClubElo <strong>{clubeloWeight}%</strong>
            </span>
          ) : null}
          <span className="chip">
            Regresión <strong>{regression}%</strong>
          </span>
        </div>
      </div>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Verificación del replay</h2>
            {verification.history_start ? (
              <span className="panel-note">
                Histórico: {verification.history_start}–
                {verification.history_end ?? "—"} · equipos históricos{" "}
                {verification.teams_resolved ?? 0}/
                {verification.teams_total ?? 0}
              </span>
            ) : null}
          </div>
          <span className={historyChip.className}>
            {historyChip.label}
          </span>
        </div>
        <div className="panel-body">
          <div className="elo-verification-summary">
            <span className="chip">
              Jugados <strong>{verification.current_matches_played ?? 0}</strong>/
              {verification.current_matches_total ?? 0}
            </span>
            <span className="chip">
              Sin marcador <strong>{verification.matches_without_score ?? 0}</strong>
            </span>
            {verification.clubelo_prior ? (
              <span className="chip">
                ClubElo{" "}
                <strong>{verification.clubelo_teams_matched ?? 0}</strong>{" "}
                equipos históricos
              </span>
            ) : null}
            <span className="chip">
              H <strong>{elo.params.home_advantage.toFixed(1)}</strong>
            </span>
            <span className="chip">
              K <strong>{elo.params.k}</strong>
            </span>
            <span className="chip">
              Escala <strong>{elo.params.elo_scale}</strong>
            </span>
          </div>
          {validation ? (
            <div className="elo-verification-summary" style={{ marginTop: 10 }}>
              <span className="chip">
                Validación <strong>{validation.matches}</strong> partidos
              </span>
              <span className="chip">
                Accuracy <strong>{(validation.accuracy * 100).toFixed(1)}%</strong>
              </span>
              <span className="chip">
                Log-loss <strong>{validation.log_loss.toFixed(3)}</strong>
              </span>
              <span className="chip">
                Brier <strong>{validation.brier.toFixed(3)}</strong>
              </span>
            </div>
          ) : null}
        </div>
      </section>

      {elo.timeline.dates.length ? (
        <div className="section-gap">
          <EloTimelineChart teams={elo.teams} timeline={elo.timeline} />
        </div>
      ) : null}

      <div className="section-gap">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="panel-title">Rating actual</h2>
              <span className="panel-note">
                Ordenado por ELO. El delta compara con el inicio de la temporada
                mostrada.
              </span>
            </div>
            <span className="chip">{elo.played_matches} partidos jugados</span>
          </div>
          <div className="panel-body" style={{ paddingTop: 0 }}>
            <div className="table-wrap">
              <table className="league-table champions-table">
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Equipo</th>
                    <th scope="col">ELO</th>
                    <th scope="col">Inicio</th>
                    <th scope="col">Δ</th>
                    <th scope="col">PJ</th>
                  </tr>
                </thead>
                <tbody>
                  {elo.teams.map((team) => (
                    <tr key={team.id}>
                      <td className="pos-cell">{team.position}</td>
                      <td className="team-cell">
                        <TeamBadge team={team} />
                      </td>
                      <td className="num">
                        <strong>{formatElo(team.elo)}</strong>
                      </td>
                      <td className="num">{formatElo(team.start_elo)}</td>
                      <td className="num">
                        <span className={`delta ${deltaTone(team.delta)}`}>
                          {formatSignedPoints(team.delta)}
                        </span>
                      </td>
                      <td className="num">{team.played}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>

      <div className="section-gap">
        <section className="panel method-card">
          <h2>Modelo</h2>
          <p>
            El ELO se actualiza con <code>K = {elo.params.k}</code>, ventaja de
            casa <code>H = {elo.params.home_advantage.toFixed(2)}</code> y
            multiplicador por margen de goles. La final se trata como sede
            neutral. Davidson usa <code>nu = {verification.params?.nu?.toFixed(4) ?? "—"}</code>{" "}
            para convertir la diferencia de ELO en probabilidades 1X2.
          </p>
          <p className="muted">
            {elo.data_note}
          </p>
        </section>
      </div>
    </div>
  );
}
