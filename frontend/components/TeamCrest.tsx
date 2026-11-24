import Image from "next/image";
import type { CSSProperties } from "react";

import { teamCrestUrl } from "@/lib/crests";
import type { Team } from "@/lib/types";

export function TeamCrest({
  team,
  size = 18,
  className,
}: {
  team: Pick<Team, "id" | "color">;
  size?: number;
  className?: string;
}) {
  const crest = teamCrestUrl(team.id);
  if (crest) {
    return (
      <Image
        className={className ? `team-crest ${className}` : "team-crest"}
        src={crest}
        alt=""
        width={size}
        height={size}
        style={{ width: size, height: size }}
      />
    );
  }

  const style = {
    "--team-color": team.color,
    width: size,
    height: size,
  } as CSSProperties;
  return (
    <span
      className={className ? `team-dot ${className}` : "team-dot"}
      style={style}
      aria-hidden="true"
    />
  );
}
