"use client";

import { useState } from "react";
import type { CSSProperties } from "react";
import type { EloTeam, EloTimeline } from "@/lib/types";
import { formatElo } from "@/lib/format";
import { TeamCrest } from "@/components/TeamCrest";

const WIDTH = 960;
const HEIGHT = 380;
const MARGIN = { top: 18, right: 18, bottom: 34, left: 54 };
const SHORT_DATE = new Intl.DateTimeFormat("es-ES", {
  month: "short",
  year: "2-digit",
});
const LONG_DATE = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

function toTime(value: string): number {
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function formatShort(value: string): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : SHORT_DATE.format(date);
}

function formatLong(value: string): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : LONG_DATE.format(date);
}

export function EloTimelineChart({
  teams,
  timeline,
}: {
  teams: EloTeam[];
  timeline: EloTimeline;
}) {
  const lastIndex = Math.max(0, timeline.dates.length - 1);
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(teams.map((team) => team.id)),
  );
  const [rangeStart, setRangeStart] = useState(0);
  const [rangeEnd, setRangeEnd] = useState(lastIndex);

  if (timeline.dates.length === 0 || timeline.series.length === 0) {
    return null;
  }

  const start = Math.min(rangeStart, rangeEnd);
  const end = Math.max(rangeStart, rangeEnd);
  const visibleDates = timeline.dates.slice(start, end + 1);
  const seriesById = new Map(
    timeline.series.map((series) => [series.team_id, series.values]),
  );
  const lineSeries = teams
    .filter((team) => selected.has(team.id))
    .map((team) => ({
      team,
      values: (seriesById.get(team.id) ?? []).slice(start, end + 1),
    }))
    .filter((item) => item.values.some((value) => value != null));

  const allValues = lineSeries
    .flatMap((item) => item.values)
    .filter((value): value is number => value != null);

  const rawMin = Math.min(...allValues, 1500);
  const rawMax = Math.max(...allValues, 1500);
  const padding = Math.max(12, (rawMax - rawMin) * 0.06);
  const min = rawMin - padding;
  const max = rawMax + padding;
  const chartWidth = WIDTH - MARGIN.left - MARGIN.right;
  const chartHeight = HEIGHT - MARGIN.top - MARGIN.bottom;

  const startTime = toTime(visibleDates[0] ?? "");
  const endTime = toTime(visibleDates[visibleDates.length - 1] ?? "");
  const x = (date: string) => {
    if (endTime === startTime) return MARGIN.left + chartWidth / 2;
    return (
      MARGIN.left +
      ((toTime(date) - startTime) / (endTime - startTime)) * chartWidth
    );
  };
  const y = (value: number) =>
    MARGIN.top + (1 - (value - min) / (max - min)) * chartHeight;

  const yTicks = Array.from({ length: 5 }, (_, index) => {
    const value = max - (index * (max - min)) / 4;
    return { value, y: y(value) };
  });
  const xTickIndices = Array.from(
    new Set(
      Array.from({ length: 5 }, (_, index) =>
        Math.round((index * (visibleDates.length - 1)) / 4),
      ),
    ),
  );

  function toggle(teamId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(teamId)) {
        next.delete(teamId);
      } else {
        next.add(teamId);
      }
      return next;
    });
  }

  function pathFor(values: (number | null)[]): string {
    let path = "";
    let open = false;
    values.forEach((value, index) => {
      if (value == null) {
        open = false;
        return;
      }
      const pointX = x(visibleDates[index]);
      const pointY = y(value);
      path += `${open ? "L" : "M"}${pointX.toFixed(1)},${pointY.toFixed(1)} `;
      open = true;
    });
    return path.trim();
  }

  function lastPoint(values: (number | null)[]): { x: number; y: number } | null {
    for (let index = values.length - 1; index >= 0; index -= 1) {
      const value = values[index];
      if (value != null) {
        return { x: x(visibleDates[index]), y: y(value) };
      }
    }
    return null;
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Evolución comparada</h2>
          <span className="panel-note">
            Todos los equipos en un solo gráfico. Ajusta el rango y oculta los
            que no te interesen.
          </span>
        </div>
        <span className="chip">
          {formatShort(timeline.dates[start])} → {formatShort(timeline.dates[end])}
        </span>
      </div>
      <div className="panel-body">
        <div className="elo-team-picker">
          <button
            type="button"
            className="chip elo-team-toggle"
            onClick={() => setSelected(new Set(teams.map((team) => team.id)))}
          >
            Todos
          </button>
          <button
            type="button"
            className="chip elo-team-toggle"
            onClick={() => setSelected(new Set())}
          >
            Ninguno
          </button>
          {teams.map((team) => {
            const isSelected = selected.has(team.id);
            return (
              <button
                key={team.id}
                type="button"
                className={`chip elo-team-toggle ${isSelected ? "is-on" : ""}`}
                style={{ "--team-color": team.color } as CSSProperties}
                aria-pressed={isSelected}
                title={team.name}
                onClick={() => toggle(team.id)}
              >
                <TeamCrest team={team} size={14} />
                {team.short_name}
              </button>
            );
          })}
        </div>

        <div className="elo-range">
          <label className="elo-range-row">
            <span>Desde</span>
            <input
              type="range"
              min={0}
              max={lastIndex}
              value={rangeStart}
              disabled={lastIndex === 0}
              aria-label="Fecha inicial del rango"
              onChange={(event) => {
                const value = Number(event.target.value);
                setRangeStart(Math.min(value, rangeEnd));
              }}
            />
            <span className="elo-range-value">{formatLong(timeline.dates[start])}</span>
          </label>
          <label className="elo-range-row">
            <span>Hasta</span>
            <input
              type="range"
              min={0}
              max={lastIndex}
              value={rangeEnd}
              disabled={lastIndex === 0}
              aria-label="Fecha final del rango"
              onChange={(event) => {
                const value = Number(event.target.value);
                setRangeEnd(Math.max(value, rangeStart));
              }}
            />
            <span className="elo-range-value">{formatLong(timeline.dates[end])}</span>
          </label>
        </div>

        {lineSeries.length === 0 ? (
          <p className="elo-chart-empty">
            Selecciona al menos un equipo con datos en el rango.
          </p>
        ) : (
          <svg
            className="elo-combined-chart"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-label="Evolución del ELO de los equipos seleccionados"
          >
            <g className="elo-chart-grid">
              {yTicks.map((tick) => (
                <line
                  key={`y-${tick.value}`}
                  x1={MARGIN.left}
                  x2={WIDTH - MARGIN.right}
                  y1={tick.y}
                  y2={tick.y}
                />
              ))}
              {xTickIndices.map((index) => (
                <line
                  key={`x-${index}`}
                  x1={x(visibleDates[index])}
                  x2={x(visibleDates[index])}
                  y1={MARGIN.top}
                  y2={HEIGHT - MARGIN.bottom}
                />
              ))}
            </g>
            <g className="elo-chart-axis">
              {yTicks.map((tick) => (
                <text
                  key={`y-label-${tick.value}`}
                  x={MARGIN.left - 8}
                  y={tick.y}
                  textAnchor="end"
                  dominantBaseline="middle"
                >
                  {formatElo(tick.value)}
                </text>
              ))}
              {xTickIndices.map((index) => (
                <text
                  key={`x-label-${index}`}
                  x={x(visibleDates[index])}
                  y={HEIGHT - MARGIN.bottom + 16}
                  textAnchor="middle"
                >
                  {formatShort(visibleDates[index])}
                </text>
              ))}
            </g>
            <line
              className="elo-chart-origin"
              x1={MARGIN.left}
              x2={WIDTH - MARGIN.right}
              y1={y(1500)}
              y2={y(1500)}
            />
            <text
              className="elo-chart-origin-label"
              x={WIDTH - MARGIN.right}
              y={y(1500) - 5}
              textAnchor="end"
            >
              1500
            </text>
            {lineSeries.map(({ team, values }) => {
              const last = lastPoint(values);
              return (
                <g key={team.id}>
                  <path
                    d={pathFor(values)}
                    fill="none"
                    stroke={team.color}
                    strokeWidth={2}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    opacity={0.88}
                  >
                    <title>{team.name}</title>
                  </path>
                  {last ? (
                    <circle cx={last.x} cy={last.y} r={2.6} fill={team.color} />
                  ) : null}
                </g>
              );
            })}
          </svg>
        )}

        <p className="panel-note" style={{ marginTop: 8 }}>
          El histórico 2020/21–2024/25 usa snapshots mensuales; 2025/26 y
          2026/27 añaden jornadas. La línea discontinua marca 1500.
        </p>
      </div>
    </section>
  );
}
