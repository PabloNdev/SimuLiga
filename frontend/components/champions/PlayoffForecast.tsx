"use client";

import { useEffect, useRef, useState } from "react";

import { STATIC_DATA } from "@/lib/api";
import { getChampionsProjection } from "@/lib/champions-api";
import {
  CHAMPIONS_MAX_SIMS_API,
  CHAMPIONS_MAX_SIMS_BROWSER,
  CHAMPIONS_SIM_PRESETS,
  DEFAULT_SIMS,
  type SimulationProgress,
} from "@/lib/sim-config";
import type { ChampionsProjectionPayload } from "@/lib/champions-types";
import type { Mode } from "@/lib/types";
import { formatProbability } from "@/lib/format";
import { ErrorState, LoadingState } from "@/components/States";
import { ProbabilityBar } from "@/components/ProbabilityBar";
import {
  SimSizeControl,
  SimulationProgressNotice,
} from "@/components/SimSizeControl";
import { TeamBadge } from "@/components/TeamBadge";
import { TeamCrest } from "@/components/TeamCrest";
import { PlayoffBracket } from "@/components/champions/PlayoffBracket";

const SIMULATION_MODE: Mode = "1x2";

export function PlayoffForecast() {
  const [projection, setProjection] =
    useState<ChampionsProjectionPayload | null>(null);
  const [sims, setSims] = useState<number>(DEFAULT_SIMS);
  const [simulating, setSimulating] = useState(false);
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<SimulationProgress | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

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
          ? `Simulando ${nextSims.toLocaleString("es-ES")} eliminatorias en tu navegador…`
          : `Simulando ${nextSims.toLocaleString("es-ES")} eliminatorias en el servidor…`,
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

    getChampionsProjection(
      sims,
      SIMULATION_MODE,
      controller.signal,
      showProgress
        ? (progress) => {
            if (!controller.signal.aborted) setJobProgress(progress);
          }
        : undefined,
    )
      .then((payload) => {
        if (controller.signal.aborted) return;
        setProjection(payload);
        previousSimsRef.current = payload.n_sims;
        setSimulating(false);
        setJobProgress(null);
        if (showProgress) {
          setJobMessage(
            `Listo: ${payload.n_sims.toLocaleString("es-ES")} simulaciones en ${payload.elapsed_seconds.toFixed(2)} s.`,
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
        }
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sims]);

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
        <span className="chip">
          {projection.n_sims.toLocaleString("es-ES")} simulaciones
        </span>
      </div>

      <div className="controls" role="toolbar" aria-label="Controles de playoff">
        <span className="controls-label">Simulaciones</span>
        <SimSizeControl
          id="playoff-sim-size"
          value={sims}
          presets={CHAMPIONS_SIM_PRESETS}
          maxSims={maxSims}
          onChange={changeSims}
        />
      </div>

      {jobMessage ? (
        <SimulationProgressNotice
          message={jobMessage}
          progress={jobProgress}
          running={simulating}
          onCancel={simulating ? cancelRun : undefined}
        />
      ) : null}

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
                    const opponent = opponentId
                      ? byId.get(opponentId)?.team
                      : null;
                    return (
                      <tr key={item.team.id}>
                        <td className="team-cell">
                          <TeamBadge team={item.team} />
                        </td>
                        <td className="num">
                          <ProbabilityBar
                            value={item.playoff_probability}
                            tone="accent"
                          />
                          <span className="prob-label">
                            {formatProbability(item.playoff_probability)}
                          </span>
                        </td>
                        <td className="num">
                          <ProbabilityBar
                            value={item.playoff_win_probability}
                            tone="good"
                          />
                          <span className="prob-label">
                            {formatProbability(item.playoff_win_probability)}
                          </span>
                        </td>
                        <td className="num">
                          <ProbabilityBar
                            value={item.round_of_16_probability}
                            tone="good"
                          />
                          <span className="prob-label">
                            {formatProbability(item.round_of_16_probability)}
                          </span>
                        </td>
                        <td className="num champions-opponent">
                          {opponent && probability ? (
                            <>
                              <TeamCrest team={opponent} size={14} />
                              {opponent.short_name}{" "}
                              <span className="muted">
                                {formatProbability(probability)}
                              </span>
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
                  {matchup.better_team ? (
                    <TeamBadge team={matchup.better_team} short />
                  ) : null}
                  <span className="muted">vs</span>
                  {matchup.worse_team ? (
                    <TeamBadge team={matchup.worse_team} short />
                  ) : null}
                </div>
                <strong>{formatProbability(matchup.probability)}</strong>
              </div>
            ))}
            {projection.playoff.matchups.length === 0 ? (
              <p className="muted">
                No hay emparejamientos con probabilidad suficiente.
              </p>
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
