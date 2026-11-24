import type {
  ChampionsProjectionPayload,
  ChampionsProjectionTeam,
  ChampionsTeam,
} from "@/lib/champions-types";
import { formatProbability } from "@/lib/format";
import { TeamCrest } from "@/components/TeamCrest";

const TOP_SEED_TIES: Record<number, [number, number]> = {
  1: [15, 18],
  2: [16, 17],
  3: [13, 20],
  4: [14, 19],
  5: [11, 22],
  6: [12, 21],
  7: [9, 24],
  8: [10, 23],
};

type SlotTeam = {
  projection: ChampionsProjectionTeam;
  probability: number;
};

type Favorite = {
  team: ChampionsTeam;
  probability: number;
};

type BracketRow = {
  seed: number;
  seedTeam: ChampionsProjectionTeam;
  seedProbability: number;
  betterSlot: number;
  worseSlot: number;
  better: SlotTeam | null;
  worse: SlotTeam | null;
  favorite: Favorite | null;
  opponent: Favorite | null;
};

function projectPlayoff(
  projection: ChampionsProjectionPayload,
  excludedIds: Set<string>,
): Map<number, SlotTeam> {
  const candidates: {
    position: number;
    projection: ChampionsProjectionTeam;
    probability: number;
  }[] = [];

  for (const team of projection.teams) {
    if (excludedIds.has(team.team.id)) continue;
    for (let position = 9; position <= 24; position += 1) {
      const probability = team.position_probabilities[position - 1] ?? 0;
      if (probability > 0) {
        candidates.push({ position, projection: team, probability });
      }
    }
  }

  candidates.sort((a, b) => b.probability - a.probability);

  const usedPositions = new Set<number>();
  const usedTeams = new Set<string>();
  const table = new Map<number, SlotTeam>();

  for (const candidate of candidates) {
    if (
      usedPositions.has(candidate.position) ||
      usedTeams.has(candidate.projection.team.id)
    ) {
      continue;
    }
    usedPositions.add(candidate.position);
    usedTeams.add(candidate.projection.team.id);
    table.set(candidate.position, {
      projection: candidate.projection,
      probability: candidate.probability,
    });
    if (table.size === 16) break;
  }

  return table;
}

function favoriteOf(
  better: SlotTeam | null,
  worse: SlotTeam | null,
  advance: Record<string, number>,
): Favorite | null {
  if (!better) {
    return worse
      ? {
          team: worse.projection.team,
          probability: advance[worse.projection.team.id] ?? 0,
        }
      : null;
  }
  if (!worse) {
    return {
      team: better.projection.team,
      probability: advance[better.projection.team.id] ?? 0,
    };
  }

  const betterProbability = advance[better.projection.team.id] ?? 0;
  const worseProbability = advance[worse.projection.team.id] ?? 0;
  return betterProbability >= worseProbability
    ? { team: better.projection.team, probability: betterProbability }
    : { team: worse.projection.team, probability: worseProbability };
}

function buildRows(projection: ChampionsProjectionPayload): BracketRow[] {
  const advance = projection.playoff.advance_probabilities;
  const topSeeds = [...projection.teams]
    .sort(
      (a, b) =>
        a.expected_position - b.expected_position ||
        a.team.name.localeCompare(b.team.name),
    )
    .slice(0, 8);
  const topSeedIds = new Set(topSeeds.map((item) => item.team.id));
  const playoff = projectPlayoff(projection, topSeedIds);

  return topSeeds.map((seedTeam, index) => {
    const seed = index + 1;
    const [betterSlot, worseSlot] = TOP_SEED_TIES[seed];
    const better = playoff.get(betterSlot) ?? null;
    const worse = playoff.get(worseSlot) ?? null;
    const favorite = favoriteOf(better, worse, advance);
    let opponent = favorite;
    if (opponent && opponent.team.id === seedTeam.team.id) {
      const alternative =
        better?.projection.team.id === seedTeam.team.id ? worse : better;
      opponent = alternative
        ? {
            team: alternative.projection.team,
            probability: advance[alternative.projection.team.id] ?? 0,
          }
        : null;
    }

    return {
      seed,
      seedTeam,
      seedProbability: seedTeam.position_probabilities[seed - 1] ?? 0,
      betterSlot,
      worseSlot,
      better,
      worse,
      favorite,
      opponent,
    };
  });
}

function TeamRow({
  slot,
  slotLabel,
  team,
  probability,
  probabilityLabel = "Probabilidad",
  highlight = false,
}: {
  slot: string;
  slotLabel?: string;
  team: ChampionsTeam | null;
  probability: number | null;
  probabilityLabel?: string;
  highlight?: boolean;
}) {
  const probabilityText =
    team && probability != null
      ? `${probabilityLabel}: ${formatProbability(probability)}`
      : undefined;

  return (
    <div
      className={`champions-bracket-team${highlight ? " is-highlight" : ""}`}
    >
      <span className="champions-bracket-slot" aria-label={slotLabel}>
        {slot}
      </span>
      {team ? (
        <TeamCrest team={team} size={18} />
      ) : (
        <span className="champions-bracket-crest" aria-hidden="true" />
      )}
      <span className="champions-bracket-name">
        {team?.name ?? "Por confirmar"}
      </span>
      <span
        className="champions-bracket-prob"
        title={probabilityText}
        aria-label={probabilityText}
      >
        {team && probability != null ? formatProbability(probability) : "—"}
      </span>
    </div>
  );
}

export function PlayoffBracket({
  projection,
}: {
  projection: ChampionsProjectionPayload;
}) {
  const rows = buildRows(projection);

  return (
    <div className="champions-bracket-board">
      <div className="champions-bracket-axis" aria-hidden="true">
        <span>Playoff 9-24</span>
        <span>Octavos</span>
      </div>

      {rows.map((row) => (
        <div className="champions-bracket-row" key={row.seed}>
          <article
            className="champions-tie-card"
            aria-label={`Llave ${row.betterSlot} contra ${row.worseSlot}`}
          >
            <header className="champions-bracket-head">
              <span className="champions-bracket-kicker">Playoff</span>
              <span className="champions-bracket-meta">
                {row.betterSlot}.º vs {row.worseSlot}.º
              </span>
            </header>

            <TeamRow
              slot={`${row.betterSlot}.º`}
              team={row.better?.projection.team ?? null}
              probability={row.better?.probability ?? null}
              probabilityLabel="Probabilidad de ocupar el puesto"
              highlight={row.favorite?.team.id === row.better?.projection.team.id}
            />
            <div className="champions-bracket-vs" aria-hidden="true">
              vs
            </div>
            <TeamRow
              slot={`${row.worseSlot}.º`}
              team={row.worse?.projection.team ?? null}
              probability={row.worse?.probability ?? null}
              probabilityLabel="Probabilidad de ocupar el puesto"
              highlight={row.favorite?.team.id === row.worse?.projection.team.id}
            />

            <footer className="champions-bracket-foot">
              {row.favorite ? (
                <>
                  <span className="champions-bracket-foot-label">Favorito</span>
                  <span className="champions-bracket-foot-name">
                    {row.favorite.team.short_name}
                  </span>
                  <span className="champions-bracket-foot-prob">
                    {formatProbability(row.favorite.probability)} a octavos
                  </span>
                </>
              ) : (
                <span className="champions-bracket-foot-label">
                  Por confirmar
                </span>
              )}
            </footer>
          </article>

          <div className="champions-bracket-link" aria-hidden="true">
            <span className="champions-bracket-node" />
          </div>

          <article
            className="champions-r16-card"
            aria-label={`Octavos: ${row.seedTeam.team.name} contra ${
              row.opponent?.team.name ?? "por confirmar"
            }`}
          >
            <header className="champions-bracket-head">
              <span className="champions-bracket-kicker">Octavos</span>
              <span className="champions-bracket-meta">
                Cabeza de serie {row.seed}.º
              </span>
            </header>

            <TeamRow
              slot={`${row.seed}.º`}
              team={row.seedTeam.team}
              probability={row.seedProbability}
              probabilityLabel="Probabilidad de acabar en este puesto"
            />
            <div className="champions-bracket-vs" aria-hidden="true">
              vs
            </div>
            <TeamRow
              slot="G"
              slotLabel="Ganador de la eliminatoria"
              team={row.opponent?.team ?? null}
              probability={row.opponent?.probability ?? null}
              probabilityLabel="Probabilidad de superar la eliminatoria"
              highlight={row.opponent != null}
            />

            <footer className="champions-bracket-foot">
              <span className="champions-bracket-foot-label">
                Ganador de {row.betterSlot}.º-{row.worseSlot}.º
              </span>
            </footer>
          </article>
        </div>
      ))}

      <p className="champions-bracket-footnote">
        <strong>Cómo se lee.</strong> Los cabezas de serie son los ocho primeros
        por posición esperada. Los puestos 9-24 se asignan al equipo con mayor
        probabilidad disponible, sin repetir equipos. Cada llave avanza hacia el
        cabeza de serie de su bloque oficial: 1/2 con 15-18 y 16-17, 3/4 con
        13-20 y 14-19, 5/6 con 11-22 y 12-21, 7/8 con 9-24 y 10-23. Como el
        sorteo real es aleatorio, aquí asignamos el mejor clasificado de cada
        bloque al mejor cabeza de serie. Los porcentajes de la llave indican la
        probabilidad de ocupar ese puesto; en octavos, el del cabeza de serie es
        la de acabar en ese puesto y el del ganador, la de superar la
        eliminatoria.
      </p>
    </div>
  );
}
