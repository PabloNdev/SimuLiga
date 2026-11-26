"use client";

import { Fragment, useState } from "react";

import type {
  ChampionsMatchItem,
  ChampionsProjectionTeam,
} from "@/lib/champions-types";
import { formatProbability } from "@/lib/format";
import { InfoTip } from "@/components/InfoTip";
import { ProbabilityBar } from "@/components/ProbabilityBar";
import { RangeBar } from "@/components/RangeBar";
import { TeamBadge } from "@/components/TeamBadge";
import { TeamCrest } from "@/components/TeamCrest";

type MatchResult = "win" | "draw" | "loss" | null;

function resultForTeam(
  match: ChampionsMatchItem,
  teamId: string,
): MatchResult {
  if (match.status !== "played" || !match.outcome) return null;
  const isHome = match.home.id === teamId;
  if (match.outcome === "D") return "draw";
  if (
    (isHome && match.outcome === "H") ||
    (!isHome && match.outcome === "A")
  ) {
    return "win";
  }
  return "loss";
}

function resultClass(result: MatchResult): string {
  if (result === "win") return "is-win";
  if (result === "draw") return "is-draw";
  if (result === "loss") return "is-loss";
  return "is-pending";
}

function resultLabel(result: MatchResult): string {
  if (result === "win") return "Victoria";
  if (result === "draw") return "Empate";
  if (result === "loss") return "Derrota";
  return "Pendiente";
}

function expectedSign(match: ChampionsMatchItem): string | null {
  const home = match.home_probability;
  const draw = match.draw_probability;
  const away = match.away_probability;
  if (home == null || draw == null || away == null) return null;
  if (home >= draw && home >= away) return match.home.short_name;
  if (draw >= away) return "Empate";
  return match.away.short_name;
}

export function ProjectionTable({
  teams,
  matches,
}: {
  teams: ChampionsProjectionTeam[];
  matches: ChampionsMatchItem[];
}) {
  const [openTeamId, setOpenTeamId] = useState<string | null>(null);
  const byId = new Map(teams.map((projection) => [projection.team.id, projection]));

  return (
    <div className="table-wrap">
      <table className="league-table champions-table champions-projection-table">
        <thead>
          <tr>
            <th scope="col">Equipo</th>
            <th scope="col">
              <span className="tooltip-wrap">
                Pts esp. <InfoTip text="Puntos esperados en la fase de liga." />
              </span>
            </th>
            <th scope="col">
              <span className="tooltip-wrap">
                Rango <InfoTip text="Percentiles 10-90 de puntos simulados." />
              </span>
            </th>
            <th scope="col">
              <span className="tooltip-wrap">
                Top 8 <InfoTip text="Probabilidad de acabar entre los 8 primeros y pasar directamente a octavos." />
              </span>
            </th>
            <th scope="col">
              <span className="tooltip-wrap">
                Playoff <InfoTip text="Probabilidad de acabar entre los puestos 9 y 24." />
              </span>
            </th>
            <th scope="col">
              <span className="tooltip-wrap">
                Eliminado <InfoTip text="Probabilidad de acabar entre los puestos 25 y 36." />
              </span>
            </th>
            <th scope="col">
              <span className="tooltip-wrap">
                Octavos <InfoTip text="Top 8 más probabilidad de ganar el playoff." />
              </span>
            </th>
            <th scope="col">Rival probable</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((projection) => {
            const opponents = Object.entries(projection.opponent_probabilities)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 1);
            const [opponentId, opponentProbability] = opponents[0] ?? [];
            const opponent = opponentId ? byId.get(opponentId)?.team : null;
            const isOpen = openTeamId === projection.team.id;
            const detailId = `projection-detail-${projection.team.id}`;
            const teamMatches = isOpen
              ? matches
                  .filter(
                    (match) =>
                      match.home.id === projection.team.id ||
                      match.away.id === projection.team.id,
                  )
                  .sort((a, b) => a.matchday - b.matchday)
              : [];
            const playedCount = teamMatches.filter(
              (match) => match.status === "played",
            ).length;
            return (
              <Fragment key={projection.team.id}>
                <tr className={isOpen ? "is-expanded" : undefined}>
                  <td className="team-cell">
                    <button
                      type="button"
                      className="projection-team-toggle"
                      aria-expanded={isOpen}
                      aria-controls={isOpen ? detailId : undefined}
                      onClick={() =>
                        setOpenTeamId(isOpen ? null : projection.team.id)
                      }
                      title={
                        isOpen
                          ? "Ocultar partido a partido"
                          : "Ver partido a partido"
                      }
                    >
                      <span
                        className={`projection-caret ${
                          isOpen ? "is-open" : ""
                        }`}
                        aria-hidden="true"
                      >
                        ›
                      </span>
                      <TeamBadge team={projection.team} />
                    </button>
                  </td>
                  <td className="num">
                    {projection.expected_points.toFixed(1)}
                  </td>
                  <td className="num champions-range-cell">
                    <RangeBar
                      p10={projection.p10_points}
                      median={projection.median_points}
                      p90={projection.p90_points}
                      max={24}
                    />
                  </td>
                  <td className="num">
                    <ProbabilityBar
                      value={projection.top8_probability}
                      tone="good"
                      label={`${projection.team.name} top 8`}
                    />
                    <span className="prob-label">
                      {formatProbability(projection.top8_probability)}
                    </span>
                  </td>
                  <td className="num">
                    <ProbabilityBar
                      value={projection.playoff_probability}
                      tone="accent"
                      label={`${projection.team.name} playoff`}
                    />
                    <span className="prob-label">
                      {formatProbability(projection.playoff_probability)}
                    </span>
                  </td>
                  <td className="num">
                    <ProbabilityBar
                      value={projection.eliminated_probability}
                      tone="danger"
                      label={`${projection.team.name} eliminado`}
                    />
                    <span className="prob-label">
                      {formatProbability(projection.eliminated_probability)}
                    </span>
                  </td>
                  <td className="num">
                    <ProbabilityBar
                      value={projection.round_of_16_probability}
                      tone="good"
                      label={`${projection.team.name} octavos`}
                    />
                    <span className="prob-label">
                      {formatProbability(projection.round_of_16_probability)}
                    </span>
                  </td>
                  <td className="num champions-opponent">
                    {opponent && opponentProbability ? (
                      <>
                        <TeamCrest team={opponent} size={14} />
                        {opponent.short_name}{" "}
                        <span className="muted">
                          {formatProbability(opponentProbability)}
                        </span>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
                {isOpen ? (
                  <tr className="projection-detail-row" id={detailId}>
                    <td colSpan={8}>
                      <div className="projection-detail">
                        <div className="projection-detail-head">
                          <span className="kicker">
                            Partido a partido · {projection.team.name}
                          </span>
                          <span className="projection-detail-count">
                            {playedCount} jugados ·{" "}
                            {teamMatches.length - playedCount} pendientes
                          </span>
                        </div>
                        <div className="projection-match-list">
                          {teamMatches.map((match) => {
                            const isHome =
                              match.home.id === projection.team.id;
                            const rival = isHome ? match.away : match.home;
                            const result = resultForTeam(
                              match,
                              projection.team.id,
                            );
                            const sign = expectedSign(match);
                            const score = match.score;
                            const scoreLabel =
                              match.status === "played" &&
                              score &&
                              score[0] != null &&
                              score[1] != null
                                ? `${score[0]}–${score[1]}`
                                : "—";
                            const hasProbabilities =
                              match.home_probability != null &&
                              match.draw_probability != null &&
                              match.away_probability != null;
                            const homeProbability =
                              match.home_probability ?? 0;
                            const drawProbability =
                              match.draw_probability ?? 0;
                            const awayProbability =
                              match.away_probability ?? 0;
                            return (
                              <article
                                className="projection-match"
                                key={match.id}
                              >
                                <div className="projection-match-meta">
                                  <span>J{match.matchday}</span>
                                  <span>
                                    {isHome ? "Local" : "Visitante"}
                                  </span>
                                </div>
                                <div className="projection-match-opponent">
                                  <TeamCrest team={rival} size={16} />
                                  <span className="projection-match-name">
                                    {rival.name}
                                  </span>
                                </div>
                                <div className="projection-match-result">
                                  <span className="projection-match-score">
                                    <strong>{scoreLabel}</strong>
                                    <span className="projection-match-score-teams">
                                      {match.home.short_name}–
                                      {match.away.short_name}
                                    </span>
                                  </span>
                                  <span
                                    className={`projection-result ${
                                      match.status === "played"
                                        ? resultClass(result)
                                        : "is-pending"
                                    }`}
                                  >
                                    {match.status === "played"
                                      ? resultLabel(result)
                                      : "Pendiente"}
                                  </span>
                                </div>
                                <div className="projection-match-forecast">
                                  {match.status === "played"
                                    ? "Resultado real"
                                    : hasProbabilities
                                      ? `C ${formatProbability(
                                          homeProbability,
                                        )} · E ${formatProbability(
                                          drawProbability,
                                        )} · V ${formatProbability(
                                          awayProbability,
                                        )}${
                                          sign ? ` · Signo: ${sign}` : ""
                                        }`
                                      : "Previsión pendiente"}
                                </div>
                              </article>
                            );
                          })}
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
