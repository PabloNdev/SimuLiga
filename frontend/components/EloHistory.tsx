"use client";

import type { EloHistory, EloTeam, EloVerification } from "@/lib/types";
import { deltaTone, formatElo, formatSignedPoints } from "@/lib/format";
import { InfoTip } from "@/components/InfoTip";
import { TeamBadge } from "@/components/TeamBadge";

const CHART_WIDTH = 240;
const CHART_HEIGHT = 84;
const PAD_X = 8;
const PAD_Y = 10;

type ChartPoint = { x: number; y: number; value: number };

export function EloHistoryPanel({
  teams,
  history,
}: {
  teams: EloTeam[];
  history: EloHistory;
}) {
  if (!history.seasons.length || !history.series.length) return null;

  const byTeam = new Map(history.series.map((entry) => [entry.team_id, entry.values]));
  const allValues = history.series
    .flatMap((entry) => entry.values)
    .filter((value): value is number => value != null);
  if (allValues.length === 0) return null;

  const min = Math.min(...allValues, history.origin) - 12;
  const max = Math.max(...allValues, history.origin) + 12;
  const span = max - min || 1;
  const x = (index: number) =>
    PAD_X + (index * (CHART_WIDTH - PAD_X * 2)) / Math.max(1, history.seasons.length - 1);
  const y = (value: number) =>
    CHART_HEIGHT - PAD_Y - ((value - min) / span) * (CHART_HEIGHT - PAD_Y * 2);
  const originY = y(history.origin);
  const lastSeason = history.seasons[history.seasons.length - 1];
  const previousSeason = history.seasons[history.seasons.length - 2];

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Evolución del ELO</h2>
          <span className="panel-note">
            Inicio de cada temporada, desde 1500 hasta {lastSeason}. El tramo
            grueso es {previousSeason}. Las líneas planas indican que el equipo no
            jugó esa temporada y conservó su rating.
          </span>
        </div>
        <span className="chip">
          Escala compartida · {formatElo(min)}–{formatElo(max)}
        </span>
      </div>
      <div className="panel-body">
        <div className="elo-history-grid">
          {teams.map((team) => {
            const values = byTeam.get(team.id) ?? [];
            const points: (ChartPoint | null)[] = values.map((value, index) =>
              value == null ? null : { x: x(index), y: y(value), value },
            );
            const firstIndex = points.findIndex((point) => point !== null);
            const first =
              points.find((point): point is ChartPoint => point !== null) ?? null;
            const last =
              [...points]
                .reverse()
                .find((point): point is ChartPoint => point !== null) ?? null;
            const singlePoint = points.filter((point) => point !== null).length === 1;
            const delta = first && last && !singlePoint ? last.value - first.value : null;
            const segments: {
              x1: number;
              y1: number;
              x2: number;
              y2: number;
              highlight: boolean;
            }[] = [];

            for (let index = 1; index < points.length; index += 1) {
              const previous = points[index - 1];
              const current = points[index];
              if (!previous || !current) continue;
              segments.push({
                x1: previous.x,
                y1: previous.y,
                x2: current.x,
                y2: current.y,
                highlight: index === points.length - 1,
              });
            }

            return (
              <div className="elo-history-card" key={team.id}>
                <div className="elo-history-head">
                  <TeamBadge team={team} />
                  <strong className="elo-history-value">
                    {formatElo(last?.value ?? team.elo)}
                  </strong>
                </div>
                <svg
                  className="elo-history-chart"
                  viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
                  role="img"
                  aria-label={`Evolución del ELO de ${team.name}`}
                >
                  <line
                    className="elo-history-origin"
                    x1={PAD_X}
                    x2={CHART_WIDTH - PAD_X}
                    y1={originY}
                    y2={originY}
                  />
                  {segments.map((segment, index) => (
                    <line
                      key={`segment-${index}`}
                      x1={segment.x1}
                      y1={segment.y1}
                      x2={segment.x2}
                      y2={segment.y2}
                      stroke={team.color}
                      strokeWidth={segment.highlight ? 2.6 : 1.4}
                      strokeLinecap="round"
                      opacity={segment.highlight ? 1 : 0.5}
                    />
                  ))}
                  {points.map((point, index) =>
                    point ? (
                      <circle
                        key={`point-${index}`}
                        cx={point.x}
                        cy={point.y}
                        r={1.8}
                        fill={team.color}
                        opacity={0.9}
                      />
                    ) : null,
                  )}
                  {last ? (
                    <circle cx={last.x} cy={last.y} r={3} fill={team.color} />
                  ) : null}
                </svg>
                <div className="elo-history-foot">
                  <span>
                    {firstIndex === history.seasons.length - 1
                      ? "Entrada"
                      : first
                        ? `${history.seasons[firstIndex]} · ${formatElo(first.value)}`
                        : "Sin datos"}
                  </span>
                  {delta != null ? (
                    <span className={`delta ${deltaTone(delta)}`}>
                      {formatSignedPoints(delta)}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function EloVerificationPanel({
  teams,
  verification,
  season,
}: {
  teams: EloTeam[];
  verification: EloVerification;
  season: string;
}) {
  if (!verification.available) {
    return (
      <section className="panel method-card">
        <h2>Verificación 2025/26</h2>
        <p>
          La verificación histórica solo está disponible con datos reales. La
          demostración no reconstruye 2020–2025.
        </p>
      </section>
    );
  }

  const baseline = verification.baseline ?? {};
  const played = verification.played_previous_season ?? {};
  const total = verification.matches_total ?? 0;
  const applied = verification.matches_applied ?? 0;
  const missing = verification.matches_missing ?? 0;
  const unresolved = verification.matches_unresolved ?? 0;
  const complete = total > 0 && applied === total && missing === 0 && unresolved === 0;

  const rows = teams
    .map((team) => {
      const base = baseline[team.id] ?? null;
      return {
        team,
        base,
        delta: base == null ? null : team.start_elo - base,
        played: played[team.id] ?? false,
      };
    })
    .sort((a, b) => (b.delta ?? Number.NEGATIVE_INFINITY) - (a.delta ?? Number.NEGATIVE_INFINITY));

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Verificación {verification.previous_season}</h2>
          <span className="panel-note">
            Replay completo de la temporada anterior: de {verification.baseline_label} al
            inicio de {season}.
          </span>
        </div>
        <span className={`chip ${complete ? "chip-good" : "chip-danger"}`}>
          {applied}/{total} partidos
        </span>
      </div>
      <div className="panel-body" style={{ paddingTop: 0 }}>
        <div className="elo-verification-summary">
          <span className="chip">
            <strong>
              {verification.teams_resolved}/{verification.teams_total}
            </strong>{" "}
            equipos
          </span>
          <span className="chip">
            <strong>{verification.matches_filled_from_football_data ?? 0}</strong>{" "}
            rellenados
          </span>
          <span className="chip">
            <strong>{verification.matches_without_score ?? 0}</strong> sin marcador
            en OpenFootball
          </span>
          {verification.promoted_baseline_2025 != null ? (
            <span className="chip">
              Ascenso 2025/26{" "}
              <strong>{verification.promoted_baseline_2025.toFixed(1)}</strong>
            </span>
          ) : null}
          {verification.promoted_baseline_2026 != null ? (
            <span className="chip">
              Ascenso 2026/27{" "}
              <strong>{verification.promoted_baseline_2026.toFixed(1)}</strong>
            </span>
          ) : null}
        </div>
        <div className="table-wrap">
          <table className="league-table">
            <thead>
              <tr>
                <th scope="col">Equipo</th>
                <th scope="col">
                  <span className="tooltip-wrap">
                    Final 2024/25{" "}
                    <InfoTip text="Rating al terminar la temporada anterior, antes de aplicar 2025/26." />
                  </span>
                </th>
                <th scope="col">
                  <span className="tooltip-wrap">
                    Inicio {season}{" "}
                    <InfoTip text="Rating al arrancar la temporada actual, después de aplicar 2025/26." />
                  </span>
                </th>
                <th scope="col">
                  <span className="tooltip-wrap">
                    Δ 2025/26{" "}
                    <InfoTip text="Diferencia entre el inicio actual y el final de 2024/25. Mide el efecto de la temporada 2025/26." />
                  </span>
                </th>
                <th scope="col">2025/26</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ team, base, delta, played: playedSeason }) => (
                <tr key={team.id}>
                  <td className="team-cell">
                    <TeamBadge team={team} />
                  </td>
                  <td className="num">{base == null ? "—" : formatElo(base)}</td>
                  <td className="num">{formatElo(team.start_elo)}</td>
                  <td className="num">
                    {delta == null ? (
                      "—"
                    ) : (
                      <span className={`delta ${deltaTone(delta)}`}>
                        {formatSignedPoints(delta)}
                      </span>
                    )}
                  </td>
                  <td className="num">{playedSeason ? "Jugó" : "Ascendido"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!complete ? (
          <div className="method-note" style={{ marginTop: 14 }}>
            Quedan {Math.max(0, total - applied)} partidos sin aplicar y {missing} sin
            marcador. Revisa la fuente antes de interpretar la tabla.
          </div>
        ) : null}
      </div>
    </section>
  );
}
