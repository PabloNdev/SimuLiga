import type { CSSProperties } from "react";
import type { TeamProjection } from "@/lib/types";
import { formatProbability } from "@/lib/format";
import { TeamCrest } from "@/components/TeamCrest";

const WIDTH = 760;
const HEIGHT = 230;
const MARGIN = { top: 12, right: 12, bottom: 26, left: 30 };

export function PointsDistribution({
  teams,
  selectedTeam,
  onSelect,
}: {
  teams: TeamProjection[];
  selectedTeam: string;
  onSelect: (teamId: string) => void;
}) {
  const selected =
    teams.find((team) => team.team.id === selectedTeam) ?? teams[0];
  const histogram = selected.points_histogram;
  const maxPoints = Math.min(
    histogram.length - 1,
    Math.max(selected.p90_points + 6, 60),
  );
  const visible = histogram.slice(0, maxPoints + 1);
  const peak = Math.max(...visible, 0.0001);
  const plotWidth = WIDTH - MARGIN.left - MARGIN.right;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const barWidth = plotWidth / visible.length;
  const x = (points: number) =>
    MARGIN.left + (points / Math.max(1, maxPoints)) * plotWidth;
  const bandStart = x(selected.p10_points);
  const bandEnd = x(selected.p90_points);
  const medianX = x(selected.median_points);
  const ticks = [];
  for (let point = 0; point <= maxPoints; point += 10) ticks.push(point);

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Distribución de puntos</h2>
          <span className="panel-note">
            Elige un equipo para ver dónde suele terminar. La banda clara
            concentra el 80% central de las simulaciones.
          </span>
        </div>
        <span className="chip">
          {selected.team.name} <strong>{formatProbability(selected.champion_probability)}</strong>
        </span>
      </div>
      <div className="panel-body">
        <div className="team-picker" role="group" aria-label="Elegir equipo">
          {teams.map((team) => (
            <button
              key={team.team.id}
              type="button"
              className="team-chip"
              aria-pressed={team.team.id === selected.team.id}
              onClick={() => onSelect(team.team.id)}
            >
              <TeamCrest team={team.team} size={14} />
              {team.team.short_name}
            </button>
          ))}
        </div>

        <div className="distribution-grid">
          <svg
            className="distribution-chart"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-label={`Distribución de puntos de ${selected.team.name}: mediana ${selected.median_points}, rango ${selected.p10_points} a ${selected.p90_points}`}
          >
            <rect
              x={bandStart}
              y={MARGIN.top}
              width={Math.max(1, bandEnd - bandStart)}
              height={plotHeight}
              className="range-band"
              rx={4}
            />
            {ticks.map((point) => (
              <g key={point}>
                <line
                  x1={x(point)}
                  x2={x(point)}
                  y1={MARGIN.top}
                  y2={MARGIN.top + plotHeight}
                  className="grid-line"
                />
                <text x={x(point)} y={HEIGHT - 8} textAnchor="middle">
                  {point}
                </text>
              </g>
            ))}
            {visible.map((probability, points) => {
              const height = (probability / peak) * (plotHeight - 8);
              return (
                <rect
                  key={points}
                  x={MARGIN.left + points * barWidth + 0.5}
                  y={MARGIN.top + plotHeight - height}
                  width={Math.max(1, barWidth - 1)}
                  height={Math.max(0, height)}
                  rx={1.5}
                  className="bar-shape"
                  style={{ fill: selected.team.color, opacity: 0.62 } as CSSProperties}
                >
                  <title>
                    {points} puntos · {formatProbability(probability)}
                  </title>
                </rect>
              );
            })}
            <line
              x1={medianX}
              x2={medianX}
              y1={MARGIN.top - 3}
              y2={MARGIN.top + plotHeight}
              className="median-line"
            />
            <text x={medianX + 4} y={MARGIN.top + 9}>
              mediana {selected.median_points}
            </text>
            <line
              x1={MARGIN.left}
              x2={WIDTH - MARGIN.right}
              y1={MARGIN.top + plotHeight}
              y2={MARGIN.top + plotHeight}
              className="axis"
            />
          </svg>

          <div className="team-summary">
            <div className="summary-line">
              <span>Puntos esperados</span>
              <strong>{selected.expected_points.toFixed(1)}</strong>
            </div>
            <div className="summary-line">
              <span>Rango probable</span>
              <strong>
                {selected.p10_points}–{selected.p90_points}
              </strong>
            </div>
            <div className="summary-line">
              <span>Posición esperada</span>
              <strong>{selected.expected_position.toFixed(1)}</strong>
            </div>
            <div className="summary-line">
              <span>Posición más probable</span>
              <strong>{selected.most_likely_position}.º</strong>
            </div>
            <div className="summary-line">
              <span>Campeón</span>
              <strong>{formatProbability(selected.champion_probability)}</strong>
            </div>
            <div className="summary-line">
              <span>Top 4</span>
              <strong>{formatProbability(selected.top4_probability)}</strong>
            </div>
            <div className="summary-line">
              <span>Descenso</span>
              <strong>{formatProbability(selected.relegation_probability)}</strong>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
