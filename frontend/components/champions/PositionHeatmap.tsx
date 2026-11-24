import { Fragment, type CSSProperties } from "react";

import type { ChampionsProjectionTeam } from "@/lib/champions-types";
import { formatProbability } from "@/lib/format";
import { InfoTip } from "@/components/InfoTip";
import { TeamCrest } from "@/components/TeamCrest";

export function PositionHeatmap({
  teams,
}: {
  teams: ChampionsProjectionTeam[];
}) {
  const columns = teams[0]?.position_probabilities.length ?? 36;
  return (
    <section className="panel heatmap-panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Mapa de posiciones</h2>
          <span className="panel-note">
            Probabilidad de terminar en cada puesto de la fase de liga. La
            columna iluminada es la posición más probable.
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
        <div className="heatmap-wrap champions-heatmap-wrap">
          <div
            className="heatmap champions-heatmap"
            style={
              {
                "--heatmap-columns": `100px repeat(${columns}, minmax(16px, 1fr))`,
              } as CSSProperties
            }
            role="table"
            aria-label="Probabilidad de posición final por equipo"
          >
            <div className="heatmap-corner" aria-hidden="true" />
            {Array.from({ length: columns }, (_, index) => (
              <div className="heatmap-col-label" key={`col-${index}`} aria-hidden="true">
                {index + 1}
              </div>
            ))}
            {teams.map((projection) => (
              <Fragment key={projection.team.id}>
                <div className="heatmap-row-label" title={projection.team.name}>
                  <TeamCrest team={projection.team} size={14} />
                  {projection.team.short_name}
                </div>
                {projection.position_probabilities.map((probability, index) => {
                  const heat = Math.min(100, Math.round(probability * 420));
                  const isModal = index + 1 === projection.most_likely_position;
                  return (
                    <div
                      key={`${projection.team.id}-${index}`}
                      className={`heatmap-cell${isModal ? " is-modal" : ""}`}
                      style={{ "--heat": `${heat}%` } as CSSProperties}
                      title={`${projection.team.name} · ${index + 1}.º: ${formatProbability(probability)}`}
                      role="cell"
                      aria-label={`${projection.team.name}, posición ${index + 1}: ${formatProbability(probability)}`}
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
