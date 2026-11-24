import type {
  ChampionsMatchItem,
  ChampionsStanding,
} from "@/lib/champions-types";
import { TeamBadge } from "@/components/TeamBadge";

type PotResult = "win" | "draw" | "loss" | null;

interface PotOpponent {
  name: string;
  matchday: number;
  home: boolean;
  result: PotResult;
  score: [number | null, number | null] | null;
}

function zoneClass(position: number): string {
  if (position <= 8) return "is-direct";
  if (position <= 24) return "is-playoff";
  return "is-out";
}

function resultClass(result: PotResult): string {
  if (result === "win") return "is-win";
  if (result === "draw") return "is-draw";
  if (result === "loss") return "is-loss";
  return "is-pending";
}

function resultLabel(result: PotResult): string {
  if (result === "win") return "Victoria";
  if (result === "draw") return "Empate";
  if (result === "loss") return "Derrota";
  return "Pendiente";
}

function opponentGroups(
  teamId: string,
  matchesByTeam: Map<string, ChampionsMatchItem[]>,
): Record<number, PotOpponent[]> {
  const groups: Record<number, PotOpponent[]> = { 1: [], 2: [], 3: [], 4: [] };
  for (const match of matchesByTeam.get(teamId) ?? []) {
    const isHome = match.home.id === teamId;
    const opponent = isHome ? match.away : match.home;
    const pot = opponent.pot;
    if (pot == null || pot < 1 || pot > 4) continue;
    let result: PotResult = null;
    if (match.status === "played" && match.outcome) {
      if (match.outcome === "D") result = "draw";
      else if (
        (isHome && match.outcome === "H") ||
        (!isHome && match.outcome === "A")
      ) {
        result = "win";
      } else {
        result = "loss";
      }
    }
    groups[pot].push({
      name: opponent.name,
      matchday: match.matchday,
      home: isHome,
      result,
      score: match.score,
    });
  }
  for (const pot of [1, 2, 3, 4]) {
    groups[pot].sort((a, b) => a.matchday - b.matchday);
  }
  return groups;
}

export function LeaguePhaseTable({
  standings,
  matches,
}: {
  standings: ChampionsStanding[];
  matches: ChampionsMatchItem[];
}) {
  const matchesByTeam = new Map<string, ChampionsMatchItem[]>();
  for (const match of matches) {
    for (const teamId of [match.home.id, match.away.id]) {
      const list = matchesByTeam.get(teamId);
      if (list) list.push(match);
      else matchesByTeam.set(teamId, [match]);
    }
  }
  return (
    <div className="table-wrap">
      <table className="league-table champions-table">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Equipo</th>
            <th scope="col" title="Resultados contra los bombos 1 a 4">
              Bombos
            </th>
            <th scope="col">PJ</th>
            <th scope="col">G</th>
            <th scope="col">E</th>
            <th scope="col">P</th>
            <th scope="col">GF</th>
            <th scope="col">GC</th>
            <th scope="col">DG</th>
            <th scope="col">Pts</th>
          </tr>
        </thead>
        <tbody>
          {standings.map((row) => {
            const groups = opponentGroups(row.team.id, matchesByTeam);
            return (
              <tr key={row.team.id} className={zoneClass(row.position)}>
                <td className="pos-cell">{row.position}</td>
                <td className="team-cell">
                  <TeamBadge team={row.team} />
                </td>
                <td className="pot-cell">
                  <div className="pot-grid">
                    {[1, 2, 3, 4].map((pot) => (
                      <div className="pot-group" key={pot}>
                        <span className="pot-label">B{pot}</span>
                        <span className="pot-squares">
                          {[0, 1].map((index) => {
                            const opponent = groups[pot][index];
                            const label = opponent
                              ? `B${pot} · ${opponent.name} · ${
                                  opponent.home ? "Local" : "Visitante"
                                } · ${resultLabel(opponent.result)}${
                                  opponent.result && opponent.score
                                    ? ` (${opponent.score[0]}–${opponent.score[1]})`
                                    : ""
                                }`
                              : `B${pot} · Sin rival asignado`;
                            return (
                              <span
                                key={`${pot}-${index}`}
                                className={`pot-square ${
                                  opponent
                                    ? resultClass(opponent.result)
                                    : "is-pending"
                                }`}
                                title={label}
                                aria-label={label}
                                role="img"
                              />
                            );
                          })}
                        </span>
                      </div>
                    ))}
                  </div>
                </td>
                <td className="num">{row.played}</td>
                <td className="num">{row.won}</td>
                <td className="num">{row.drawn}</td>
                <td className="num">{row.lost}</td>
                <td className="num">{row.goals_for}</td>
                <td className="num">{row.goals_against}</td>
                <td className="num">{row.goal_difference}</td>
                <td className="num">
                  <strong>{row.points}</strong>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="champions-legend">
        <span>
          <i className="zone-dot zone-dot-direct" /> 1-8 · octavos
        </span>
        <span>
          <i className="zone-dot zone-dot-playoff" /> 9-24 · playoff
        </span>
        <span>
          <i className="zone-dot zone-dot-out" /> 25-36 · eliminado
        </span>
        <span>
          <i className="pot-dot pot-dot-win" /> victoria
        </span>
        <span>
          <i className="pot-dot pot-dot-draw" /> empate
        </span>
        <span>
          <i className="pot-dot pot-dot-loss" /> derrota
        </span>
        <span>
          <i className="pot-dot pot-dot-pending" /> pendiente
        </span>
      </div>
    </div>
  );
}
