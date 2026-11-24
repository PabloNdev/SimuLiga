"use client";

import { useState, type CSSProperties } from "react";

import type { ChampionsMatchItem } from "@/lib/champions-types";
import { formatProbability } from "@/lib/format";
import { TeamBadge } from "@/components/TeamBadge";

function expectedSign(match: ChampionsMatchItem): string | null {
  const home = match.home_probability;
  const draw = match.draw_probability;
  const away = match.away_probability;
  if (home == null || draw == null || away == null) return null;
  if (home >= draw && home >= away) return "Casa";
  if (draw >= away) return "Empate";
  return "Visitante";
}

export function ChampionsMatches({
  matches,
  currentMatchday,
}: {
  matches: ChampionsMatchItem[];
  currentMatchday: number;
}) {
  const matchdays = Array.from(
    new Set(matches.map((match) => match.matchday)),
  ).sort((a, b) => a - b);
  const initial =
    matchdays.find((matchday) => matchday >= currentMatchday) ??
    matchdays[0] ??
    1;
  const [matchday, setMatchday] = useState(initial);
  const visible = matches.filter((match) => match.matchday === matchday);
  const played = visible.filter((match) => match.status === "played");
  const pending = visible.filter((match) => match.status === "pending");

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Partidos</h2>
          <span className="panel-note">
            Fase de liga · jornada {matchday} · C casa · E empate · V visitante
            <br />
            Jugado: resultado real · Pendiente: marcador probable y signo
            esperado
          </span>
        </div>
        <select
          className="matchday-select"
          value={matchday}
          onChange={(event) => setMatchday(Number(event.target.value))}
          aria-label="Jornada de Champions"
        >
          {matchdays.map((value) => (
            <option key={value} value={value}>
              J{value}
            </option>
          ))}
        </select>
      </div>
      <div className="panel-body">
        {played.length > 0 ? (
          <div className="champions-matches">
            {played.map((match) => (
              <div className="champions-match" key={match.id}>
                <div className="champions-match-team">
                  <TeamBadge team={match.home} short />
                </div>
                <div className="champions-match-center">
                  <strong title="Resultado real">
                    {match.score?.[0]}–{match.score?.[1]}
                  </strong>
                  <span className="champions-match-probs">Final</span>
                </div>
                <div className="champions-match-team champions-match-team-away">
                  <TeamBadge team={match.away} short />
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {pending.length > 0 ? (
          <div
            className="fixture-list"
            style={played.length > 0 ? { marginTop: 18 } : undefined}
          >
            {pending.map((match) => {
              const sign = expectedSign(match);
              const score = match.most_likely_score;
              const scoreLabel = score ? `${score[0]}–${score[1]}` : "vs";
              const homeProbability = match.home_probability ?? 0;
              const drawProbability = match.draw_probability ?? 0;
              const awayProbability = match.away_probability ?? 0;
              const hasProbabilities =
                match.home_probability != null &&
                match.draw_probability != null &&
                match.away_probability != null;
              return (
                <article className="fixture" key={match.id}>
                  <div className="fixture-meta">
                    <span>
                      {match.home.short_name} vs {match.away.short_name}
                    </span>
                    <span>
                      {score
                        ? `Marcador probable ${scoreLabel}`
                        : "Previsión 1X2"}
                    </span>
                  </div>
                  <div className="fixture-teams">
                    <span>{match.home.name}</span>
                    <span className="fixture-score" title="Marcador más probable">
                      {scoreLabel}
                    </span>
                    <span className="away">{match.away.name}</span>
                  </div>
                  <div
                    className="tri-bar"
                    style={
                      {
                        "--team-home": match.home.color,
                        "--team-away": match.away.color,
                      } as CSSProperties
                    }
                    aria-label={
                      hasProbabilities
                        ? `Casa ${formatProbability(
                            homeProbability,
                          )}, empate ${formatProbability(
                            drawProbability,
                          )}, visitante ${formatProbability(awayProbability)}`
                        : "Probabilidades pendientes"
                    }
                  >
                    <span
                      className="tri-home"
                      style={{ width: `${homeProbability * 100}%` }}
                    />
                    <span
                      className="tri-draw"
                      style={{ width: `${drawProbability * 100}%` }}
                    />
                    <span
                      className="tri-away"
                      style={{ width: `${awayProbability * 100}%` }}
                    />
                  </div>
                  <div className="fixture-probs">
                    <span>
                      {hasProbabilities
                        ? `C ${formatProbability(
                            homeProbability,
                          )} · E ${formatProbability(
                            drawProbability,
                          )} · V ${formatProbability(awayProbability)}`
                        : "Pendiente"}
                    </span>
                    {sign ? (
                      <span className="fixture-sign">
                        Signo esperado: {sign}
                      </span>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}

        {visible.length === 0 ? (
          <p className="muted">No hay partidos en esta jornada.</p>
        ) : null}
      </div>
    </section>
  );
}
