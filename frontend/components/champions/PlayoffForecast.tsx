"use client";

import { useEffect, useState } from "react";

import { getChampionsProjection } from "@/lib/champions-api";
import type { ChampionsProjectionPayload } from "@/lib/champions-types";
import { formatProbability } from "@/lib/format";
import { ErrorState, LoadingState } from "@/components/States";
import { ProbabilityBar } from "@/components/ProbabilityBar";
import { TeamBadge } from "@/components/TeamBadge";
import { TeamCrest } from "@/components/TeamCrest";
import { PlayoffBracket } from "@/components/champions/PlayoffBracket";

export function PlayoffForecast() {
  const [projection, setProjection] = useState<ChampionsProjectionPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getChampionsProjection(10_000, "score", controller.signal)
      .then(setProjection)
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

  if (!projection) {
    return (
      <div className="container">
        <LoadingState
          title="Simulando el playoff"
          note="Cruzando posiciones 9-24 y resolviendo las eliminatorias."
        />
      </div>
    );
  }

  const byId = new Map(projection.teams.map((item) => [item.team.id, item]));
  const playoffTeams = [...projection.teams]
    .sort((a, b) => b.playoff_win_probability - a.playoff_win_probability)
    .filter((item) => item.playoff_probability > 0);

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <span className="kicker">Previsión · playoff 9-24</span>
          <h1 className="page-title">
            El camino a <em>octavos</em>.
          </h1>
          <p className="page-sub">
            Los puestos 9-24 juegan una eliminatoria a dos partidos. El mejor
            clasificado cierra en casa. Sin goles fuera: si persiste el empate,
            prórroga y penaltis.
          </p>
        </div>
        <span className="chip">{projection.n_sims.toLocaleString("es-ES")} simulaciones</span>
      </div>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Llaves 9-24 y octavos</h2>
            <span className="panel-note">
              Cada eliminatoria y el cruce proyectado del cabeza de serie que le
              toca en octavos.
            </span>
          </div>
          <span className="chip">Ida y vuelta</span>
        </div>
        <div className="panel-body">
          <PlayoffBracket projection={projection} />
        </div>
      </section>

      <div className="section-gap">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="panel-title">Probabilidad de avanzar</h2>
              <span className="panel-note">
                Primero la probabilidad de jugar el playoff y después la de
                ganarlo.
              </span>
            </div>
          </div>
          <div className="panel-body" style={{ paddingTop: 0 }}>
            <div className="table-wrap">
              <table className="league-table champions-table">
                <thead>
                  <tr>
                    <th scope="col">Equipo</th>
                    <th scope="col">Jugar playoff</th>
                    <th scope="col">Ganar playoff</th>
                    <th scope="col">Octavos</th>
                    <th scope="col">Rival más probable</th>
                  </tr>
                </thead>
                <tbody>
                  {playoffTeams.map((item) => {
                    const [opponentId, probability] =
                      Object.entries(item.opponent_probabilities)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 1)[0] ?? [];
                    const opponent = opponentId ? byId.get(opponentId)?.team : null;
                    return (
                      <tr key={item.team.id}>
                        <td className="team-cell">
                          <TeamBadge team={item.team} />
                        </td>
                        <td className="num">
                          <ProbabilityBar value={item.playoff_probability} tone="accent" />
                          <span className="prob-label">
                            {formatProbability(item.playoff_probability)}
                          </span>
                        </td>
                        <td className="num">
                          <ProbabilityBar value={item.playoff_win_probability} tone="good" />
                          <span className="prob-label">
                            {formatProbability(item.playoff_win_probability)}
                          </span>
                        </td>
                        <td className="num">
                          <ProbabilityBar value={item.round_of_16_probability} tone="good" />
                          <span className="prob-label">
                            {formatProbability(item.round_of_16_probability)}
                          </span>
                        </td>
                        <td className="num champions-opponent">
                          {opponent && probability ? (
                            <>
                              <TeamCrest team={opponent} size={14} />
                              {opponent.short_name}{" "}
                              <span className="muted">{formatProbability(probability)}</span>
                            </>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>

      <div className="section-gap">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="panel-title">Emparejamientos más probables</h2>
              <span className="panel-note">
                Combinaciones de mejor y peor clasificado que más veces aparecen
                en las simulaciones.
              </span>
            </div>
          </div>
          <div className="panel-body champions-matchups">
            {projection.playoff.matchups.slice(0, 8).map((matchup) => (
              <div
                className="champions-matchup"
                key={`${matchup.better_id}-${matchup.worse_id}`}
              >
                <div className="champions-matchup-teams">
                  {matchup.better_team ? <TeamBadge team={matchup.better_team} short /> : null}
                  <span className="muted">vs</span>
                  {matchup.worse_team ? <TeamBadge team={matchup.worse_team} short /> : null}
                </div>
                <strong>{formatProbability(matchup.probability)}</strong>
              </div>
            ))}
            {projection.playoff.matchups.length === 0 ? (
              <p className="muted">No hay emparejamientos con probabilidad suficiente.</p>
            ) : null}
          </div>
        </section>
      </div>

      <div className="section-gap">
        <section className="panel method-card">
          <h2>Cómo se resuelve</h2>
          <p>
            Cada eliminatoria se juega a dos partidos. El equipo mejor
            clasificado recibe en la vuelta. Si el agregado queda empatado, se
            simulan 30 minutos de prórroga con los goles esperados reducidos a un
            tercio; si sigue el empate, los penaltis se resuelven al 50%.
          </p>
          <p>
            La probabilidad de octavos de cada equipo es la de acabar entre los
            ocho primeros más la de jugar el playoff y ganarlo.
          </p>
        </section>
      </div>
    </div>
  );
}
