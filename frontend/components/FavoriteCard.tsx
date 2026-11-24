import type { ProjectionPayload, SeasonPayload } from "@/lib/types";
import { formatProbability } from "@/lib/format";
import { ProbabilityBar } from "@/components/ProbabilityBar";
import { TeamBadge } from "@/components/TeamBadge";
import { TeamCrest } from "@/components/TeamCrest";

export function FavoriteCard({
  season,
  projection,
}: {
  season: SeasonPayload;
  projection: ProjectionPayload;
}) {
  const ranked = [...projection.teams].sort(
    (a, b) => b.champion_probability - a.champion_probability,
  );
  const favorite = ranked[0];
  const contenders = ranked.slice(0, 4);

  return (
    <section className="favorite-card rise rise-2" aria-label="Favorito del modelo">
      <div className="favorite-top">
        <div>
          <span className="favorite-label">Favorito del modelo</span>
          <div className="favorite-team" style={{ marginTop: 8 }}>
            <TeamBadge team={favorite.team} />
          </div>
        </div>
        <span className="chip chip-accent">
          {season.competition} {season.season}
        </span>
      </div>

      <div>
        <div className="favorite-number">
          {formatProbability(favorite.champion_probability).replace("%", "")}
          <small>%</small>
        </div>
        <span className="favorite-label">
          de salir campeón · {projection.n_sims.toLocaleString("es-ES")} temporadas
        </span>
      </div>

      <div className="favorite-race">
        {contenders.map((team) => (
          <div className="race-row" key={team.team.id}>
            <TeamCrest team={team.team} size={16} />
            <ProbabilityBar
              value={team.champion_probability}
              color={team.team.color}
              tone="team"
              label={`${team.team.name} campeón`}
            />
            <strong>{formatProbability(team.champion_probability)}</strong>
          </div>
        ))}
      </div>

      <div className="status-row">
        <span className="chip">
          Jornada <strong>{season.current_matchday}</strong>
        </span>
        <span className="chip">
          Rango favorito{" "}
          <strong>
            {favorite.p10_points}–{favorite.p90_points} pts
          </strong>
        </span>
      </div>
    </section>
  );
}
