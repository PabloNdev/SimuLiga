import type { Team } from "@/lib/types";
import { TeamCrest } from "@/components/TeamCrest";

export function TeamBadge({
  team,
  short = false,
}: {
  team: Team;
  short?: boolean;
}) {
  return (
    <span className="team-inline">
      <TeamCrest team={team} />
      <span className="team-name">{short ? team.short_name : team.name}</span>
    </span>
  );
}
