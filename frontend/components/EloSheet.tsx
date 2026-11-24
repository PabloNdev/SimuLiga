"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getElo } from "@/lib/api";
import type { EloPayload } from "@/lib/types";
import { deltaTone, formatElo, formatSignedPoints, formatUpdatedAt } from "@/lib/format";
import { EloHistoryPanel, EloVerificationPanel } from "@/components/EloHistory";
import { EloTimelineChart } from "@/components/EloTimelineChart";
import { ErrorState, SkeletonPanel } from "@/components/States";
import { InfoTip } from "@/components/InfoTip";
import { ProbabilityBar } from "@/components/ProbabilityBar";
import { TeamBadge } from "@/components/TeamBadge";

export function EloSheet() {
  const [data, setData] = useState<EloPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getElo(controller.signal)
      .then((payload) => {
        setData(payload);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught.message : "Error inesperado");
        setLoading(false);
      });
    return () => controller.abort();
  }, [reloadKey]);

  function retry() {
    setLoading(true);
    setError(null);
    setData(null);
    setReloadKey((value) => value + 1);
  }

  if (loading && !data) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">Ratings Elo</span>
            <h1 className="page-title">
              La fuerza de cada equipo, <em>en números</em>.
            </h1>
          </div>
        </div>
        <SkeletonPanel height={520} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">Ratings Elo</span>
            <h1 className="page-title">La fuerza de cada equipo, en números.</h1>
          </div>
        </div>
        <ErrorState
          message={error ?? "No se pudieron cargar los ratings Elo."}
          onRetry={retry}
        />
      </div>
    );
  }

  const ratings = data.teams.map((team) => team.elo);
  const lowest = Math.min(...ratings);
  const span = Math.max(...ratings) - lowest || 1;
  const params = data.params;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <span className="kicker">Ratings Elo · LaLiga {data.season}</span>
          <h1 className="page-title">
            La fuerza de cada equipo, <em>en números</em>.
          </h1>
          <p className="page-sub">
            El Elo es una puntuación de fuerza que se actualiza partido a
            partido. Aquí tienes el rating vigente de los {data.teams.length}{" "}
            equipos, el punto de partida de la temporada y cuánto se ha movido
            cada uno.
          </p>
        </div>
        <div className="status-row">
          <span className="chip">
            Jornada actual <strong>{data.current_matchday}</strong>
          </span>
          <span className="chip">
            Jugados <strong>{data.played_matches}</strong> /{" "}
            {data.total_matchdays * (data.teams.length / 2)}
          </span>
          <span className="chip chip-accent">
            {data.demo ? "Demostración" : "Datos reales"}
          </span>
          <span className="chip">
            Actualizado <strong>{formatUpdatedAt(data.updated_at)}</strong>
          </span>
        </div>
      </div>

      {data.demo ? (
        <div className="notice" style={{ marginBottom: 18 }}>
          <strong>Datos de demostración.</strong>
          <span>
            Los ratings parten de las semillas de los clubes y se actualizan con
            las jornadas simuladas de esta temporada. Al conectar una fuente
            real, la tabla se reconstruye con resultados auténticos.
          </span>
        </div>
      ) : data.data_note ? (
        <div className="notice" style={{ marginBottom: 18 }}>
          <strong>Fuente.</strong>
          <span>{data.data_note}</span>
        </div>
      ) : null}

      <div className="section-gap">
        <EloVerificationPanel
          teams={data.teams}
          verification={data.verification}
          season={data.season}
        />
      </div>

      {data.timeline.dates.length > 0 ? (
        <div className="section-gap">
          <EloTimelineChart teams={data.teams} timeline={data.timeline} />
        </div>
      ) : null}

      <div className="section-gap">
        <EloHistoryPanel teams={data.teams} history={data.history} />
      </div>

      <section className="panel section-gap">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">ELO por equipo</h2>
            <span className="panel-note">
              Ordenado de mayor a menor rating. El inicial es el valor antes de
              jugar la temporada cargada.
            </span>
          </div>
          <span className="chip">Escala Elo · 400 puntos = 10 a 1</span>
        </div>
        <div className="panel-body" style={{ paddingTop: 0 }}>
          <div className="table-wrap">
            <table className="league-table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Equipo</th>
                  <th scope="col" className="optional">
                    Escala
                  </th>
                  <th scope="col">
                    <span className="tooltip-wrap">
                      ELO <InfoTip text="Rating vigente: el que usan los modelos para calcular probabilidades." />
                    </span>
                  </th>
                  <th scope="col" className="optional">
                    <span className="tooltip-wrap">
                      Inicial{" "}
                      <InfoTip text="Rating al empezar la temporada cargada, antes de sus partidos." />
                    </span>
                  </th>
                  <th scope="col">
                    <span className="tooltip-wrap">
                      Δ{" "}
                      <InfoTip text="Diferencia entre el ELO actual y el inicial de la temporada." />
                    </span>
                  </th>
                  <th scope="col" className="optional">
                    <span className="tooltip-wrap">
                      PJ <InfoTip text="Partidos de esta temporada ya contabilizados en el rating." />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.teams.map((team) => {
                  const relative = 0.12 + 0.88 * ((team.elo - lowest) / span);
                  return (
                    <tr
                      key={team.id}
                      className={
                        team.position <= 4
                          ? "is-europe"
                          : team.position >= data.teams.length - 2
                            ? "is-relegation"
                            : undefined
                      }
                    >
                      <td className="pos-cell">{team.position}</td>
                      <td className="team-cell">
                        <TeamBadge team={team} />
                      </td>
                      <td className="optional" style={{ width: 96 }}>
                        <span className="elo-scale">
                          <ProbabilityBar
                            value={relative}
                            tone="accent"
                            label={`${team.name} respecto al resto`}
                          />
                        </span>
                      </td>
                      <td className="num">
                        <strong>{formatElo(team.elo)}</strong>
                      </td>
                      <td className="num optional muted">
                        {formatElo(team.start_elo)}
                      </td>
                      <td className="num">
                        <span className={`delta ${deltaTone(team.delta)}`}>
                          {team.delta === 0 ? "0.0" : formatSignedPoints(team.delta)}
                        </span>
                      </td>
                      <td className="num optional">{team.played}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <div className="method section-gap">
        <div className="method-grid">
          <section className="panel method-card">
            <h2>1 · De dónde sale el rating</h2>
            {data.demo ? (
              <>
                <p>
                  Cada club arranca con una semilla de fuerza propia. Después se
                  aplican, jornada a jornada, los resultados ya disputados de la
                  temporada cargada. El ELO inicial de la tabla es el valor antes
                  de esa primera jornada; el actual incorpora los partidos
                  jugados que aparecen en PJ.
                </p>
              </>
            ) : (
              <>
                <p>
                  Los ratings se reconstruyen desde cero: todos los equipos parten
                  de {formatElo(params.start_rating)} y se aplican los partidos del
                  histórico 2020–2024 (cinco temporadas) con la misma fórmula de
                  actualización.
                </p>
                <p>
                  Ese rating final es la semilla de la temporada anterior
                  (2025/26), que se reaplica completa:{" "}
                  {data.verification.matches_applied}/{data.verification.matches_total}{" "}
                  partidos, incluidos los de Girona, Mallorca y Oviedo. Los{" "}
                  {data.verification.matches_without_score} encuentros sin marcador
                  en OpenFootball se rellenan con football-data.co.uk.
                </p>
                {data.verification.promoted_baseline_2025 != null &&
                data.verification.promoted_baseline_2026 != null ? (
                  <p>
                    Los equipos que no jugaron la temporada anterior entran con la
                    media de los tres descendidos:{" "}
                    {data.verification.promoted_baseline_2025.toFixed(1)} en
                    2025/26 y{" "}
                    {data.verification.promoted_baseline_2026.toFixed(1)} en
                    2026/27.
                  </p>
                ) : null}
                <p>
                  El resultado es el ELO inicial de la temporada cargada. Por
                  último se aplican las jornadas ya disputadas de {data.season}.
                </p>
              </>
            )}
            <div className="method-note">
              El ELO no es una probabilidad: es una escala relativa. La
              diferencia entre dos equipos es lo que alimenta el modelo, no el
              número absoluto.
            </div>
          </section>

          <section className="panel method-card">
            <h2>2 · Cómo se actualiza</h2>
            <h3>Expectativa de victoria</h3>
            <pre className="formula">{`E_local = 1 / (1 + 10^(-((Elo_local + ${params.home_advantage}) - Elo_visitante)/${params.elo_scale}))`}</pre>
            <h3>Cambio tras el partido</h3>
            <pre className="formula">{`ΔElo = ${params.k} · multiplicador_margen · (resultado − E_local)

resultado: 1 victoria · 0,5 empate · 0 derrota`}</pre>
            <h3>Multiplicador por margen</h3>
            <pre className="formula">{`margen 0–1  → ×1,0
margen 2    → ×1,5
margen ≥3   → ×(11 + margen) / 8`}</pre>
            <p>
              Un resultado inesperado mueve más el rating que uno previsto, y una
              goleada más que un triunfo ajustado. Los puntos que gana un equipo
              los pierde el rival: el total se conserva.
            </p>
          </section>
        </div>

        <section className="panel method-card">
          <h2>3 · Cómo leer la tabla</h2>
          <ul>
            <li>
              <strong>ELO</strong>: rating vigente. Es el que se usa para estimar
              los partidos pendientes y proyectar la temporada.
            </li>
            <li>
              <strong>Inicial</strong>: rating al comienzo de {data.season}. Sirve
              para separar la fuerza heredada de lo conseguido este año.
            </li>
            <li>
              <strong>Δ</strong>: variación acumulada. En verde si el equipo ha
              ganado fuerza; en rojo si la ha perdido.
            </li>
            <li>
              <strong>PJ</strong>: partidos de la temporada que ya han movido el
              rating.
            </li>
          </ul>
          <p style={{ marginTop: 14 }}>
            Para traducir el rating a probabilidades, SimuLiga combina la
            diferencia de ELO con la ventaja de casa y el modelo Davidson. Puedes
            ver el detalle en la página de método.
          </p>
          <div className="page-actions">
            <Link href="/metodologia" className="link-arrow">
              Ver el método completo
            </Link>
            <Link href="/" className="link-arrow">
              Volver al panel
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
