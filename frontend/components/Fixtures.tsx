import type { CSSProperties } from "react";
import type { MatchPrediction, SeasonPayload, Team } from "@/lib/types";

export function Fixtures({
  season,
  predictions,
}: {
  season: SeasonPayload;
  predictions: MatchPrediction[];
}) {
  const teamMap = new Map(season.teams.map((team) => [team.id, team]));
  const current = season.current_matchday;
  const upcoming = predictions
    .filter((prediction) => prediction.matchday === current)
    .slice(0, 5);

  return (
    <section className="panel side-panel">
      <div className="side-title">
        <h3>Próxima jornada</h3>
        <span>J{current}</span>
      </div>
      <div className="fixture-list">
        {upcoming.map((prediction) => {
          const home = teamMap.get(prediction.home_id) as Team | undefined;
          const away = teamMap.get(prediction.away_id) as Team | undefined;
          if (!home || !away) return null;
          const score = prediction.most_likely_score;
          return (
            <article className="fixture" key={prediction.match_id}>
              <div className="fixture-meta">
                <span>{home.short_name} vs {away.short_name}</span>
                <span>{score ? `Marcador probable ${score[0]}-${score[1]}` : "1X2"}</span>
              </div>
              <div className="fixture-teams">
                <span>{home.name}</span>
                <span className="fixture-score">
                  {score ? `${score[0]}–${score[1]}` : "vs"}
                </span>
                <span className="away">{away.name}</span>
              </div>
              <div
                className="tri-bar"
                style={
                  {
                    "--team-home": home.color,
                    "--team-away": away.color,
                  } as CSSProperties
                }
                aria-label={`${home.name} ${Math.round(prediction.home_probability * 100)}%, empate ${Math.round(prediction.draw_probability * 100)}%, ${away.name} ${Math.round(prediction.away_probability * 100)}%`}
              >
                <span
                  className="tri-home"
                  style={{ width: `${prediction.home_probability * 100}%` }}
                />
                <span
                  className="tri-draw"
                  style={{ width: `${prediction.draw_probability * 100}%` }}
                />
                <span
                  className="tri-away"
                  style={{ width: `${prediction.away_probability * 100}%` }}
                />
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
