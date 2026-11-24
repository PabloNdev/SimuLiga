"use client";

import type { Standing, TeamProjection } from "@/lib/types";
import type { SeasonPayload } from "@/lib/types";
import { formatProbability } from "@/lib/format";
import { InfoTip } from "@/components/InfoTip";
import { ProbabilityBar } from "@/components/ProbabilityBar";
import { RangeBar } from "@/components/RangeBar";
import { TeamBadge } from "@/components/TeamBadge";

export type Metric = "champion" | "top4" | "relegation";

const METRICS: Record<
  Metric,
  { label: string; tone: "good" | "europe" | "danger"; help: string }
> = {
  champion: {
    label: "Campeón",
    tone: "good",
    help: "Porcentaje de temporadas simuladas en las que el equipo termina 1.º.",
  },
  top4: {
    label: "Top 4",
    tone: "europe",
    help: "Porcentaje de temporadas simuladas en las que el equipo termina entre los cuatro primeros.",
  },
  relegation: {
    label: "Descenso",
    tone: "danger",
    help: "Porcentaje de temporadas simuladas en las que el equipo termina en los tres últimos puestos.",
  },
};

function metricValue(projection: TeamProjection, metric: Metric): number {
  if (metric === "champion") return projection.champion_probability;
  if (metric === "top4") return projection.top4_probability;
  return projection.relegation_probability;
}

export function LeagueTable({
  season,
  projection,
  metric,
  selectedTeam,
  onSelect,
  baseStandings,
  baseLabel = "Hoy",
}: {
  season: SeasonPayload;
  projection: TeamProjection[];
  metric: Metric;
  selectedTeam: string | null;
  onSelect: (teamId: string) => void;
  baseStandings?: Standing[];
  baseLabel?: string;
}) {
  const standings = new Map(
    (baseStandings ?? season.standings).map((row) => [row.team.id, row]),
  );
  const config = METRICS[metric];

  return (
    <div className="table-wrap">
      <table className="league-table">
        <thead>
          <tr>
            <th scope="col">{baseLabel}</th>
            <th scope="col">
              <span className="tooltip-wrap">
                Proy. <InfoTip text="Posición media esperada al final de la temporada." />
              </span>
            </th>
            <th scope="col">Equipo</th>
            <th scope="col">
              <span className="tooltip-wrap">
                Pts <InfoTip text="Puntos reales ya conseguidos en los partidos jugados." />
              </span>
            </th>
            <th scope="col" className="optional">
              PJ
            </th>
            <th scope="col" className="optional">
              DG
            </th>
            <th scope="col" className="prob-cell">
              <span className="tooltip-wrap">
                {config.label} <InfoTip text={config.help} />
              </span>
            </th>
            <th scope="col">
              <span className="tooltip-wrap">
                Pts esp. <InfoTip text="Media de puntos al final de la temporada en todas las simulaciones." />
              </span>
            </th>
            <th scope="col" className="range-cell">
              <span className="tooltip-wrap">
                Rango <InfoTip text="P10–P90: el 80% central de las temporadas simuladas cae dentro de este rango de puntos." />
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {projection.map((row) => {
            const standing = standings.get(row.team.id);
            const value = metricValue(row, metric);
            const projectedEurope = row.expected_position <= 4;
            const projectedRelegation = row.expected_position >= 18;
            return (
              <tr
                key={row.team.id}
                className={[
                  selectedTeam === row.team.id ? "is-selected" : "",
                  projectedRelegation ? "is-relegation" : projectedEurope ? "is-europe" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => onSelect(row.team.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(row.team.id);
                  }
                }}
                tabIndex={0}
                aria-label={`${row.team.name}, probabilidad de ${config.label.toLowerCase()} ${formatProbability(value)}`}
              >
                <td className="pos-cell">{standing?.position ?? "—"}</td>
                <td className="pos-cell">{row.expected_position.toFixed(1)}</td>
                <td className="team-cell">
                  <TeamBadge team={row.team} />
                </td>
                <td className="num">{standing?.points ?? "—"}</td>
                <td className="num optional">{standing?.played ?? "—"}</td>
                <td className="num optional">
                  {standing ? (standing.goal_difference > 0 ? "+" : "") + standing.goal_difference : "—"}
                </td>
                <td className="prob-cell">
                  <span className="prob-inline">
                    <ProbabilityBar
                      value={value}
                      tone={config.tone}
                      label={`${row.team.name} ${config.label}`}
                    />
                    <span className="prob-value">{formatProbability(value)}</span>
                  </span>
                </td>
                <td className="num">{row.expected_points.toFixed(1)}</td>
                <td className="range-cell">
                  <RangeBar
                    p10={row.p10_points}
                    median={row.median_points}
                    p90={row.p90_points}
                    max={Math.max(100, row.p90_points + 4)}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
