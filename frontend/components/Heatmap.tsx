import { Fragment, type CSSProperties } from "react";
import type { TeamProjection } from "@/lib/types";
import { formatProbability } from "@/lib/format";
import { InfoTip } from "@/components/InfoTip";
import { TeamCrest } from "@/components/TeamCrest";

export function Heatmap({ teams }: { teams: TeamProjection[] }) {
  return (
    <section className="panel heatmap-panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Mapa de posiciones</h2>
          <span className="panel-note">
            Probabilidad de terminar en cada puesto. La columna iluminada es la
            posición más probable.
          </span>
        </div>
        <div className="heatmap-legend">
          <span>Menos</span>
          <span className="legend-gradient" aria-hidden="true" />
          <span>Más</span>
          <InfoTip text="Cada fila suma 100%. Se lee: probabilidad de que el equipo acabe en esa posición." />
        </div>
      </div>
      <div className="panel-body">
        <div className="heatmap-wrap">
          <div
            className="heatmap"
            role="table"
            aria-label="Probabilidad de posición final por equipo"
          >
            <div className="heatmap-corner" aria-hidden="true" />
            {teams.map((_, index) => (
              <div className="heatmap-col-label" key={`col-${index}`} aria-hidden="true">
                {index + 1}
              </div>
            ))}
            {teams.map((team) => (
              <Fragment key={team.team.id}>
                <div className="heatmap-row-label" title={team.team.name}>
                  <TeamCrest team={team.team} size={14} />
                  {team.team.short_name}
                </div>
                {team.position_probabilities.map((probability, index) => {
                  const heat = Math.min(100, Math.round(probability * 320));
                  const isModal = index + 1 === team.most_likely_position;
                  return (
                    <div
                      key={`${team.team.id}-${index}`}
                      className={`heatmap-cell${isModal ? " is-modal" : ""}`}
                      style={{ "--heat": `${heat}%` } as CSSProperties}
                      title={`${team.team.name} · ${index + 1}.º: ${formatProbability(probability)}`}
                      role="cell"
                      aria-label={`${team.team.name}, posición ${index + 1}: ${formatProbability(probability)}`}
                    />
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
