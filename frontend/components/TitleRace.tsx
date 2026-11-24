import type { TeamProjection } from "@/lib/types";
import { formatProbability } from "@/lib/format";
import { ProbabilityBar } from "@/components/ProbabilityBar";
import { TeamCrest } from "@/components/TeamCrest";

export function TitleRace({ teams }: { teams: TeamProjection[] }) {
  const ranked = [...teams]
    .sort((a, b) => b.champion_probability - a.champion_probability)
    .slice(0, 6);

  return (
    <section className="panel side-panel">
      <div className="side-title">
        <h3>Carrera por el título</h3>
        <span>Campeón</span>
      </div>
      <div className="race-list">
        {ranked.map((team) => (
          <div className="race-item" key={team.team.id}>
            <TeamCrest team={team.team} size={16} />
            <div>
              <div className="team-short">{team.team.name}</div>
              <ProbabilityBar
                value={team.champion_probability}
                color={team.team.color}
                tone="team"
                label={`${team.team.name} campeón`}
              />
            </div>
            <strong>{formatProbability(team.champion_probability)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
