import type {
  EloPayload,
  MatchItem,
  MatchPrediction,
  Mode,
  ModelInfo,
  Outcome,
  ProjectionPayload,
  SeasonPayload,
  Standing,
  Team,
  TeamProjection,
} from "@/lib/types";
import {
  buildConditionedCdf,
  createRng,
  davidsonProbabilities,
  expectedGoals,
  percentileFromHistogram,
  prepareScoreline,
  roundTo,
  sampleFlatIndexFromCdf,
  updateEloRatings,
  type DavidsonParams,
  type MatchProbabilities,
  type PreparedScoreline,
  type ScorelineParams,
} from "./math.ts";

export interface LaLigaMatchInput {
  id: string;
  matchday: number;
  homeId: string;
  awayId: string;
  played: boolean;
  homeGoals: number | null;
  awayGoals: number | null;
  outcome: Outcome | null;
}

export interface LaLigaSimConfig {
  teams: Team[];
  matches: LaLigaMatchInput[];
  mode: Mode;
  nSims: number;
  seed: number | null;
  davidson: DavidsonParams;
  scoreline: ScorelineParams;
  eloDelta?: Record<string, number>;
  forcedResults?: Record<string, Outcome>;
  forcedScores?: Record<string, [number, number]>;
  fairPlay?: Record<string, number>;
  startMatchday?: number | null;
  eloByMatchday?: Record<number, Record<string, number>>;
  dataVersion: string;
  source: string;
}

export interface LaLigaChunkOutput {
  nSims: number;
  teamCount: number;
  histogramSize: number;
  positionHistogram: Uint32Array;
  pointsHistogram: Uint32Array;
  pointsSum: Float64Array;
  pointsSquaredSum: Float64Array;
}

interface PendingMatchModel {
  match: LaLigaMatchInput;
  homeSlot: number;
  awaySlot: number;
  forcedScore: [number, number] | null;
  forcedOutcome: Outcome | null;
  cdf: Float64Array | null;
  width: number;
  homeProb: number;
  homePlusDrawProb: number;
}

interface PairEntry {
  matchIdx: number;
  homeSlot: number;
  awaySlot: number;
  played: boolean;
  baseHomeGoals: number;
  baseAwayGoals: number;
  baseOutcome: number;
  pendingIdx: number;
}

const OUTCOME_TO_CODE: Record<Outcome, number> = { H: 0, D: 1, A: 2 };

function outcomeCodeFromGoals(h: number, a: number): number {
  return h > a ? 0 : h === a ? 1 : 2;
}

export function matchItemsToEngineInput(items: MatchItem[]): LaLigaMatchInput[] {
  return items.map((item) => {
    const hasScore =
      item.score !== null &&
      item.score[0] !== null &&
      item.score[1] !== null;
    return {
      id: item.id,
      matchday: item.matchday,
      homeId: item.home.id,
      awayId: item.away.id,
      played: item.status === "played",
      homeGoals: hasScore ? item.score![0] : null,
      awayGoals: hasScore ? item.score![1] : null,
      outcome: item.outcome,
    };
  });
}

/**
 * Reconstruct per-matchday Elo ratings matching backend/app/data/real_league.py.
 */
export function buildEloByMatchday(
  season: SeasonPayload,
  matches: LaLigaMatchInput[],
  eloPayload?: EloPayload | null,
): Record<number, Record<string, number>> {
  const ratings: Record<string, number> = {};
  const historySeries = eloPayload?.history?.series ?? [];
  const lastSeasonIdx = (eloPayload?.history?.seasons?.length ?? 0) - 1;
  const historyStart = new Map<string, number>();
  if (lastSeasonIdx >= 0) {
    for (const entry of historySeries) {
      const value = entry.values[lastSeasonIdx];
      if (typeof value === "number" && Number.isFinite(value)) {
        historyStart.set(entry.team_id, value);
      }
    }
  }

  const eloTeamMap = new Map(
    (eloPayload?.teams ?? []).map((team) => [team.id, team.start_elo]),
  );

  for (const team of season.teams) {
    ratings[team.id] =
      historyStart.get(team.id) ?? eloTeamMap.get(team.id) ?? team.elo;
  }

  const k = eloPayload?.params?.k ?? 20.0;
  const homeAdvantage = eloPayload?.params?.home_advantage ?? 60.0;
  const eloScale = eloPayload?.params?.elo_scale ?? 400.0;

  const byMatchday: Record<number, Record<string, number>> = {
    1: Object.fromEntries(
      Object.entries(ratings).map(([id, val]) => [id, roundTo(val, 2)]),
    ),
  };

  const matchdays = Array.from(new Set(matches.map((m) => m.matchday))).sort(
    (a, b) => a - b,
  );

  for (const md of matchdays) {
    const playedGroup = matches.filter(
      (m) =>
        m.matchday === md &&
        m.played &&
        m.homeGoals !== null &&
        m.awayGoals !== null,
    );
    if (playedGroup.length === 0) continue;
    for (const m of playedGroup) {
      const homeRating = ratings[m.homeId];
      const awayRating = ratings[m.awayId];
      if (homeRating === undefined || awayRating === undefined) continue;
      const [nextHome, nextAway] = updateEloRatings(
        homeRating,
        awayRating,
        m.homeGoals!,
        m.awayGoals!,
        k,
        homeAdvantage,
        eloScale,
      );
      ratings[m.homeId] = nextHome;
      ratings[m.awayId] = nextAway;
    }
    byMatchday[md + 1] = Object.fromEntries(
      Object.entries(ratings).map(([id, val]) => [id, roundTo(val, 2)]),
    );
  }

  return byMatchday;
}

export function resolveTeamsForStart(
  teams: Team[],
  startMatchday: number | null | undefined,
  eloByMatchday?: Record<number, Record<string, number>>,
  eloDelta?: Record<string, number>,
): Team[] {
  let baseTeams = teams;
  if (startMatchday != null && eloByMatchday) {
    const available = Object.keys(eloByMatchday)
      .map(Number)
      .filter((md) => Number.isFinite(md) && md <= startMatchday)
      .sort((a, b) => a - b);
    if (available.length > 0) {
      const ratings = eloByMatchday[available[available.length - 1]];
      baseTeams = teams.map((team) => ({
        ...team,
        elo: ratings[team.id] ?? team.elo,
      }));
    }
  }
  if (!eloDelta || Object.keys(eloDelta).length === 0) {
    return baseTeams;
  }
  return baseTeams.map((team) => {
    const delta = eloDelta[team.id] ?? 0;
    if (delta === 0) return team;
    return {
      ...team,
      elo: Math.min(2600, Math.max(800, team.elo + delta)),
    };
  });
}

function getEffectiveMatches(
  matches: LaLigaMatchInput[],
  startMatchday: number | null | undefined,
): LaLigaMatchInput[] {
  if (startMatchday == null) return matches;
  return matches.map((match) =>
    match.matchday >= startMatchday
      ? {
          ...match,
          played: false,
          homeGoals: null,
          awayGoals: null,
          outcome: null,
        }
      : match,
  );
}

interface TeamRecord {
  played: number;
  won: number;
  drawn: number;
  lost: number;
  points: number;
  goalsFor: number;
  goalsAgainst: number;
  hasGoals: boolean;
  goalsMatches: number;
  fairPlay: number;
}

function buildRecords(
  teams: Team[],
  playedMatches: LaLigaMatchInput[],
  fairPlay: Record<string, number>,
): Map<string, TeamRecord> {
  const records = new Map<string, TeamRecord>();
  for (const team of teams) {
    records.set(team.id, {
      played: 0,
      won: 0,
      drawn: 0,
      lost: 0,
      points: 0,
      goalsFor: 0,
      goalsAgainst: 0,
      hasGoals: false,
      goalsMatches: 0,
      fairPlay: fairPlay[team.id] ?? 0,
    });
  }
  for (const match of playedMatches) {
    const result =
      match.outcome ??
      (match.homeGoals !== null && match.awayGoals !== null
        ? match.homeGoals > match.awayGoals
          ? "H"
          : match.homeGoals < match.awayGoals
            ? "A"
            : "D"
        : null);
    if (!result) continue;
    const home = records.get(match.homeId);
    const away = records.get(match.awayId);
    if (!home || !away) continue;
    home.played += 1;
    away.played += 1;
    if (result === "H") {
      home.won += 1;
      away.lost += 1;
      home.points += 3;
    } else if (result === "A") {
      away.won += 1;
      home.lost += 1;
      away.points += 3;
    } else {
      home.drawn += 1;
      away.drawn += 1;
      home.points += 1;
      away.points += 1;
    }
    if (match.homeGoals !== null && match.awayGoals !== null) {
      home.hasGoals = true;
      away.hasGoals = true;
      home.goalsFor += match.homeGoals;
      home.goalsAgainst += match.awayGoals;
      away.goalsFor += match.awayGoals;
      away.goalsAgainst += match.homeGoals;
      home.goalsMatches += 1;
      away.goalsMatches += 1;
    }
  }
  return records;
}

function rankBaseGroup(
  group: string[],
  records: Map<string, TeamRecord>,
  matches: LaLigaMatchInput[],
  expectedMeetings = 2,
): string[] {
  if (group.length <= 1) return group;
  const members = new Set(group);
  const meetingCounts = new Map<string, number>();
  for (const match of matches) {
    if (!match.played) continue;
    if (members.has(match.homeId) && members.has(match.awayId)) {
      const pair =
        match.homeId < match.awayId
          ? `${match.homeId}|${match.awayId}`
          : `${match.awayId}|${match.homeId}`;
      meetingCounts.set(pair, (meetingCounts.get(pair) ?? 0) + 1);
    }
  }
  let complete = true;
  for (let i = 0; i < group.length && complete; i++) {
    for (let j = i + 1; j < group.length; j++) {
      const a = group[i];
      const b = group[j];
      const pair = a < b ? `${a}|${b}` : `${b}|${a}`;
      if ((meetingCounts.get(pair) ?? 0) < expectedMeetings) {
        complete = false;
        break;
      }
    }
  }

  if (complete) {
    const h2hPoints = new Map<string, number>();
    const h2hGf = new Map<string, number>();
    const h2hGa = new Map<string, number>();
    for (const id of group) {
      h2hPoints.set(id, 0);
      h2hGf.set(id, 0);
      h2hGa.set(id, 0);
    }
    let playedCount = 0;
    let goalsAvailable = true;
    for (const match of matches) {
      if (!match.played) continue;
      if (!members.has(match.homeId) || !members.has(match.awayId)) continue;
      playedCount += 1;
      const result =
        match.outcome ??
        (match.homeGoals !== null && match.awayGoals !== null
          ? match.homeGoals > match.awayGoals
            ? "H"
            : match.homeGoals < match.awayGoals
              ? "A"
              : "D"
          : null);
      if (result === "H") {
        h2hPoints.set(match.homeId, (h2hPoints.get(match.homeId) ?? 0) + 3);
      } else if (result === "A") {
        h2hPoints.set(match.awayId, (h2hPoints.get(match.awayId) ?? 0) + 3);
      } else if (result === "D") {
        h2hPoints.set(match.homeId, (h2hPoints.get(match.homeId) ?? 0) + 1);
        h2hPoints.set(match.awayId, (h2hPoints.get(match.awayId) ?? 0) + 1);
      }
      if (match.homeGoals !== null && match.awayGoals !== null) {
        h2hGf.set(match.homeId, (h2hGf.get(match.homeId) ?? 0) + match.homeGoals);
        h2hGa.set(match.homeId, (h2hGa.get(match.homeId) ?? 0) + match.awayGoals);
        h2hGf.set(match.awayId, (h2hGf.get(match.awayId) ?? 0) + match.awayGoals);
        h2hGa.set(match.awayId, (h2hGa.get(match.awayId) ?? 0) + match.homeGoals);
      } else {
        goalsAvailable = false;
      }
    }
    if (playedCount > 0) {
      const keyOf = (id: string): [number, number, number] => [
        h2hPoints.get(id) ?? 0,
        goalsAvailable ? (h2hGf.get(id) ?? 0) - (h2hGa.get(id) ?? 0) : 0,
        goalsAvailable ? (h2hGf.get(id) ?? 0) : 0,
      ];
      const ordered = [...group].sort((a, b) => {
        const ka = keyOf(a);
        const kb = keyOf(b);
        if (ka[0] !== kb[0]) return kb[0] - ka[0];
        if (ka[1] !== kb[1]) return kb[1] - ka[1];
        if (ka[2] !== kb[2]) return kb[2] - ka[2];
        return a < b ? -1 : a > b ? 1 : 0;
      });
      const partitions: string[][] = [];
      for (const id of ordered) {
        const k = keyOf(id);
        const last = partitions[partitions.length - 1];
        if (last) {
          const lk = keyOf(last[0]);
          if (lk[0] === k[0] && lk[1] === k[1] && lk[2] === k[2]) {
            last.push(id);
            continue;
          }
        }
        partitions.push([id]);
      }
      if (partitions.length > 1) {
        return partitions.flatMap((part) =>
          part.length === 1
            ? part
            : rankBaseGroup(part, records, matches, expectedMeetings),
        );
      }
    }
  }

  const goalsAvailable = group.every((id) => {
    const rec = records.get(id)!;
    return rec.hasGoals && rec.goalsMatches === rec.played;
  });

  return [...group].sort((a, b) => {
    const ra = records.get(a)!;
    const rb = records.get(b)!;
    if (goalsAvailable) {
      const gda = ra.goalsFor - ra.goalsAgainst;
      const gdb = rb.goalsFor - rb.goalsAgainst;
      if (gda !== gdb) return gdb - gda;
      if (ra.goalsFor !== rb.goalsFor) return rb.goalsFor - ra.goalsFor;
    }
    if (ra.fairPlay !== rb.fairPlay) return ra.fairPlay - rb.fairPlay;
    return a < b ? -1 : a > b ? 1 : 0;
  });
}

export function computeLaLigaStandings(
  teams: Team[],
  playedMatches: LaLigaMatchInput[],
  fairPlay: Record<string, number> = {},
): Standing[] {
  const teamMap = new Map(teams.map((t) => [t.id, t]));
  const records = buildRecords(teams, playedMatches, fairPlay);
  const teamIds = teams.map((t) => t.id);
  const sortedByPoints = [...teamIds].sort(
    (a, b) => (records.get(b)?.points ?? 0) - (records.get(a)?.points ?? 0),
  );

  const groups: string[][] = [];
  for (const id of sortedByPoints) {
    const pts = records.get(id)!.points;
    const last = groups[groups.length - 1];
    if (last && records.get(last[0])!.points === pts) {
      last.push(id);
    } else {
      groups.push([id]);
    }
  }

  const ordered = groups.flatMap((group) =>
    rankBaseGroup(group, records, playedMatches),
  );

  return ordered.map((id, idx) => {
    const rec = records.get(id)!;
    const team = teamMap.get(id)!;
    return {
      position: idx + 1,
      team: { ...team, elo: roundTo(team.elo, 1) },
      played: rec.played,
      won: rec.won,
      drawn: rec.drawn,
      lost: rec.lost,
      goals_for: rec.goalsFor,
      goals_against: rec.goalsAgainst,
      goal_difference: rec.goalsFor - rec.goalsAgainst,
      points: rec.points,
    };
  });
}

function predictPendingMatches(
  pendingMatches: LaLigaMatchInput[],
  teams: Team[],
  teamIndex: Map<string, number>,
  config: LaLigaSimConfig,
): {
  predictions: MatchPrediction[];
  models: PendingMatchModel[];
} {
  const predictions: MatchPrediction[] = [];
  const models: PendingMatchModel[] = [];
  const forcedResults = config.forcedResults ?? {};
  const forcedScores = config.forcedScores ?? {};

  for (const match of pendingMatches) {
    const homeSlot = teamIndex.get(match.homeId)!;
    const awaySlot = teamIndex.get(match.awayId)!;
    const home = teams[homeSlot];
    const away = teams[awaySlot];

    let probs: MatchProbabilities;
    let mostLikelyScore: [number, number] | null = null;
    let mostLikelyScoreProb: number | null = null;
    let cdf: Float64Array | null = null;
    let width = config.scoreline.max_goals + 1;

    const forcedScore = forcedScores[match.id] ?? null;
    const forcedOutcome = forcedResults[match.id] ?? null;

    if (config.mode === "score") {
      const [lh, la] = expectedGoals(home.elo, away.elo, config.scoreline);
      const prepared: PreparedScoreline = prepareScoreline(
        lh,
        la,
        config.scoreline,
      );
      probs = prepared.probabilities;
      mostLikelyScore = [prepared.mostLikely[0], prepared.mostLikely[1]];
      mostLikelyScoreProb = prepared.mostLikely[2];
      width = prepared.width;
      if (forcedScore === null) {
        cdf =
          forcedOutcome !== null
            ? buildConditionedCdf(prepared, forcedOutcome)
            : prepared.cdf;
      }
    } else {
      probs = davidsonProbabilities(home.elo, away.elo, config.davidson);
    }

    models.push({
      match,
      homeSlot,
      awaySlot,
      forcedScore,
      forcedOutcome,
      cdf,
      width,
      homeProb: probs.home,
      homePlusDrawProb: probs.home + probs.draw,
    });

    predictions.push({
      match_id: match.id,
      matchday: match.matchday,
      home_id: match.homeId,
      away_id: match.awayId,
      home_probability: probs.home,
      draw_probability: probs.draw,
      away_probability: probs.away,
      most_likely_score: mostLikelyScore,
      most_likely_score_probability: mostLikelyScoreProb,
    });
  }

  predictions.sort((a, b) => {
    if (a.matchday !== b.matchday) return a.matchday - b.matchday;
    return a.match_id < b.match_id ? -1 : a.match_id > b.match_id ? 1 : 0;
  });

  return { predictions, models };
}

/**
 * Run a chunk of LaLiga Monte Carlo simulations with zero-allocation inner loops.
 */
export function runLaLigaChunk(
  config: LaLigaSimConfig,
  chunkSims: number,
  chunkSeed: number | null,
  onProgress?: (completed: number, total: number) => void,
  progressInterval = 2_000,
): LaLigaChunkOutput {
  const teams = resolveTeamsForStart(
    config.teams,
    config.startMatchday,
    config.eloByMatchday,
    config.eloDelta,
  );
  const teamCount = teams.length;
  const teamIndex = new Map<string, number>();
  for (let i = 0; i < teamCount; i++) {
    teamIndex.set(teams[i].id, i);
  }

  const effectiveMatches = getEffectiveMatches(
    config.matches,
    config.startMatchday,
  );
  const playedMatches: LaLigaMatchInput[] = [];
  const pendingMatches: LaLigaMatchInput[] = [];
  for (const m of effectiveMatches) {
    if (m.played) playedMatches.push(m);
    else pendingMatches.push(m);
  }

  const fairPlayMap = config.fairPlay ?? {};
  const baseRecords = buildRecords(teams, playedMatches, fairPlayMap);
  const goalsAvailable =
    config.mode === "score" &&
    playedMatches.every((m) => m.homeGoals !== null && m.awayGoals !== null);

  const basePoints = new Int32Array(teamCount);
  const baseGoalsFor = new Int32Array(teamCount);
  const baseGoalsAgainst = new Int32Array(teamCount);
  const fairPlay = new Int32Array(teamCount);
  for (let i = 0; i < teamCount; i++) {
    const rec = baseRecords.get(teams[i].id)!;
    basePoints[i] = rec.points;
    if (goalsAvailable) {
      baseGoalsFor[i] = rec.goalsFor;
      baseGoalsAgainst[i] = rec.goalsAgainst;
    }
    fairPlay[i] = fairPlayMap[teams[i].id] ?? 0;
  }

  const pendingIndexMap = new Map<string, number>();
  for (let i = 0; i < pendingMatches.length; i++) {
    pendingIndexMap.set(pendingMatches[i].id, i);
  }

  // Pair lookup table indexed by minSlot * teamCount + maxSlot
  const pairTable: PairEntry[][] = Array.from(
    { length: teamCount * teamCount },
    () => [],
  );
  const matchesPerTeam = new Int32Array(teamCount);

  for (let idx = 0; idx < effectiveMatches.length; idx++) {
    const m = effectiveMatches[idx];
    const hSlot = teamIndex.get(m.homeId)!;
    const aSlot = teamIndex.get(m.awayId)!;
    matchesPerTeam[hSlot] += 1;
    matchesPerTeam[aSlot] += 1;
    const minSlot = hSlot < aSlot ? hSlot : aSlot;
    const maxSlot = hSlot < aSlot ? aSlot : hSlot;
    const baseOutcome = m.played
      ? m.outcome !== null
        ? OUTCOME_TO_CODE[m.outcome]
        : m.homeGoals !== null && m.awayGoals !== null
          ? outcomeCodeFromGoals(m.homeGoals, m.awayGoals)
          : -1
      : -1;
    pairTable[minSlot * teamCount + maxSlot].push({
      matchIdx: idx,
      homeSlot: hSlot,
      awaySlot: aSlot,
      played: m.played,
      baseHomeGoals: m.homeGoals !== null ? m.homeGoals : -1,
      baseAwayGoals: m.awayGoals !== null ? m.awayGoals : -1,
      baseOutcome,
      pendingIdx: m.played ? -1 : (pendingIndexMap.get(m.id) ?? -1),
    });
  }

  let maxMatchesPerTeam = 0;
  let maxBasePoints = 0;
  for (let i = 0; i < teamCount; i++) {
    if (matchesPerTeam[i] > maxMatchesPerTeam) maxMatchesPerTeam = matchesPerTeam[i];
    if (basePoints[i] > maxBasePoints) maxBasePoints = basePoints[i];
  }
  const histogramSize = Math.max(maxBasePoints, 3 * maxMatchesPerTeam) + 1;

  const { models } = predictPendingMatches(
    pendingMatches,
    teams,
    teamIndex,
    config,
  );
  const pendingCount = models.length;
  const isScoreMode = config.mode === "score";

  const positionHistogram = new Uint32Array(teamCount * teamCount);
  const pointsHistogram = new Uint32Array(teamCount * histogramSize);
  const pointsSum = new Float64Array(teamCount);
  const pointsSquaredSum = new Float64Array(teamCount);

  // Reusable per-simulation buffers (stay in L1 cache)
  const points = new Int32Array(teamCount);
  const goalsFor = new Int32Array(teamCount);
  const goalsAgainst = new Int32Array(teamCount);
  const simHomeGoals = new Int16Array(pendingCount);
  const simAwayGoals = new Int16Array(pendingCount);
  const simOutcomes = new Int8Array(pendingCount);
  const randomKeys = new Float64Array(teamCount);
  const order = new Int32Array(teamCount);

  // Reusable H2H scratch arrays
  const h2hPoints = new Int32Array(teamCount);
  const h2hGf = new Int32Array(teamCount);
  const h2hGa = new Int32Array(teamCount);

  const rankTieGroup = (group: number[]): number[] => {
    const len = group.length;
    if (len <= 1) return group;

    for (let i = 0; i < len; i++) {
      const t = group[i];
      h2hPoints[t] = 0;
      h2hGf[t] = 0;
      h2hGa[t] = 0;
    }

    let h2hGoalsAvailable = true;
    for (let i = 0; i < len; i++) {
      const first = group[i];
      for (let j = i + 1; j < len; j++) {
        const second = group[j];
        const minSlot = first < second ? first : second;
        const maxSlot = first < second ? second : first;
        const entries = pairTable[minSlot * teamCount + maxSlot];
        for (let e = 0; e < entries.length; e++) {
          const entry = entries[e];
          let outcome: number;
          let hg = -1;
          let ag = -1;
          if (entry.played) {
            outcome = entry.baseOutcome;
            if (outcome < 0) continue;
            if (entry.baseHomeGoals >= 0) {
              hg = entry.baseHomeGoals;
              ag = entry.baseAwayGoals;
            }
          } else if (!isScoreMode) {
            outcome = simOutcomes[entry.pendingIdx];
          } else {
            hg = simHomeGoals[entry.pendingIdx];
            ag = simAwayGoals[entry.pendingIdx];
            outcome = hg > ag ? 0 : hg === ag ? 1 : 2;
          }

          if (outcome === 0) {
            h2hPoints[entry.homeSlot] += 3;
          } else if (outcome === 2) {
            h2hPoints[entry.awaySlot] += 3;
          } else {
            h2hPoints[entry.homeSlot] += 1;
            h2hPoints[entry.awaySlot] += 1;
          }

          if (hg < 0 || ag < 0) {
            h2hGoalsAvailable = false;
          } else {
            h2hGf[entry.homeSlot] += hg;
            h2hGa[entry.homeSlot] += ag;
            h2hGf[entry.awaySlot] += ag;
            h2hGa[entry.awaySlot] += hg;
          }
        }
      }
    }

    // Snapshot H2H keys for this recursion level before recursing
    const snapPts = new Int32Array(len);
    const snapGd = new Int32Array(len);
    const snapGf = new Int32Array(len);
    const idxOrder: number[] = new Array(len);
    for (let i = 0; i < len; i++) {
      const t = group[i];
      snapPts[i] = h2hPoints[t];
      snapGd[i] = h2hGoalsAvailable ? h2hGf[t] - h2hGa[t] : 0;
      snapGf[i] = h2hGoalsAvailable ? h2hGf[t] : 0;
      idxOrder[i] = i;
    }

    idxOrder.sort((ia, ib) => {
      if (snapPts[ia] !== snapPts[ib]) return snapPts[ib] - snapPts[ia];
      if (snapGd[ia] !== snapGd[ib]) return snapGd[ib] - snapGd[ia];
      if (snapGf[ia] !== snapGf[ib]) return snapGf[ib] - snapGf[ia];
      return group[ib] - group[ia];
    });

    // Partition by identical H2H key
    const partitions: number[][] = [];
    for (let i = 0; i < len; i++) {
      const curIdx = idxOrder[i];
      if (i > 0) {
        const prevIdx = idxOrder[i - 1];
        if (
          snapPts[curIdx] === snapPts[prevIdx] &&
          snapGd[curIdx] === snapGd[prevIdx] &&
          snapGf[curIdx] === snapGf[prevIdx]
        ) {
          partitions[partitions.length - 1].push(group[curIdx]);
          continue;
        }
      }
      partitions.push([group[curIdx]]);
    }

    if (partitions.length > 1) {
      const ranked: number[] = [];
      for (let p = 0; p < partitions.length; p++) {
        const part = partitions[p];
        if (part.length === 1) {
          ranked.push(part[0]);
        } else {
          const sub = rankTieGroup(part);
          for (let s = 0; s < sub.length; s++) ranked.push(sub[s]);
        }
      }
      return ranked;
    }

    // Overall criteria fallback
    return [...group].sort((a, b) => {
      if (goalsAvailable) {
        const gda = goalsFor[a] - goalsAgainst[a];
        const gdb = goalsFor[b] - goalsAgainst[b];
        if (gda !== gdb) return gdb - gda;
        if (goalsFor[a] !== goalsFor[b]) return goalsFor[b] - goalsFor[a];
      }
      if (fairPlay[a] !== fairPlay[b]) return fairPlay[a] - fairPlay[b];
      if (randomKeys[a] !== randomKeys[b]) return randomKeys[a] - randomKeys[b];
      return a - b;
    });
  };

  const rng = createRng(chunkSeed);

  for (let sim = 0; sim < chunkSims; sim++) {
    points.set(basePoints);
    if (isScoreMode) {
      goalsFor.set(baseGoalsFor);
      goalsAgainst.set(baseGoalsAgainst);
    }

    for (let m = 0; m < pendingCount; m++) {
      const model = models[m];
      const hSlot = model.homeSlot;
      const aSlot = model.awaySlot;

      if (isScoreMode) {
        let hg: number;
        let ag: number;
        if (model.forcedScore !== null) {
          hg = model.forcedScore[0];
          ag = model.forcedScore[1];
        } else {
          const flat = sampleFlatIndexFromCdf(model.cdf!, rng());
          hg = (flat / model.width) | 0;
          ag = flat - hg * model.width;
        }
        simHomeGoals[m] = hg;
        simAwayGoals[m] = ag;
        if (hg > ag) {
          points[hSlot] += 3;
        } else if (hg < ag) {
          points[aSlot] += 3;
        } else {
          points[hSlot] += 1;
          points[aSlot] += 1;
        }
        goalsFor[hSlot] += hg;
        goalsAgainst[hSlot] += ag;
        goalsFor[aSlot] += ag;
        goalsAgainst[aSlot] += hg;
      } else {
        let outcome: number;
        if (model.forcedOutcome !== null) {
          outcome = OUTCOME_TO_CODE[model.forcedOutcome];
        } else if (model.forcedScore !== null) {
          outcome = outcomeCodeFromGoals(
            model.forcedScore[0],
            model.forcedScore[1],
          );
        } else {
          const draw = rng();
          outcome =
            draw < model.homeProb ? 0 : draw < model.homePlusDrawProb ? 1 : 2;
        }
        simOutcomes[m] = outcome;
        if (outcome === 0) {
          points[hSlot] += 3;
        } else if (outcome === 2) {
          points[aSlot] += 3;
        } else {
          points[hSlot] += 1;
          points[aSlot] += 1;
        }
      }
    }

    for (let i = 0; i < teamCount; i++) {
      randomKeys[i] = rng();
      order[i] = i;
    }

    // Insertion sort by points descending (stable, ultra-fast for 20 teams)
    for (let i = 1; i < teamCount; i++) {
      const keySlot = order[i];
      const keyPts = points[keySlot];
      let j = i - 1;
      while (j >= 0 && points[order[j]] < keyPts) {
        order[j + 1] = order[j];
        j--;
      }
      order[j + 1] = keySlot;
    }

    // Assign final positions, resolving point ties via LaLiga H2H rules
    let pos = 0;
    while (pos < teamCount) {
      let end = pos + 1;
      const tiedPts = points[order[pos]];
      while (end < teamCount && points[order[end]] === tiedPts) {
        end++;
      }
      if (end - pos === 1) {
        const slot = order[pos];
        positionHistogram[slot * teamCount + pos] += 1;
      } else {
        const group: number[] = new Array(end - pos);
        for (let k = pos; k < end; k++) {
          group[k - pos] = order[k];
        }
        const resolved = rankTieGroup(group);
        for (let k = 0; k < resolved.length; k++) {
          const slot = resolved[k];
          positionHistogram[slot * teamCount + (pos + k)] += 1;
        }
      }
      pos = end;
    }

    for (let i = 0; i < teamCount; i++) {
      const p = points[i];
      pointsSum[i] += p;
      pointsSquaredSum[i] += p * p;
      if (p >= 0 && p < histogramSize) {
        pointsHistogram[i * histogramSize + p] += 1;
      }
    }

    if (onProgress && (sim + 1) % progressInterval === 0) {
      onProgress(sim + 1, chunkSims);
    }
  }

  if (onProgress) {
    onProgress(chunkSims, chunkSims);
  }

  return {
    nSims: chunkSims,
    teamCount,
    histogramSize,
    positionHistogram,
    pointsHistogram,
    pointsSum,
    pointsSquaredSum,
  };
}

export function mergeLaLigaChunks(chunks: LaLigaChunkOutput[]): LaLigaChunkOutput {
  const first = chunks[0];
  const teamCount = first.teamCount;
  const histogramSize = first.histogramSize;
  const positionHistogram = new Uint32Array(teamCount * teamCount);
  const pointsHistogram = new Uint32Array(teamCount * histogramSize);
  const pointsSum = new Float64Array(teamCount);
  const pointsSquaredSum = new Float64Array(teamCount);
  let totalSims = 0;

  for (const chunk of chunks) {
    totalSims += chunk.nSims;
    for (let i = 0; i < positionHistogram.length; i++) {
      positionHistogram[i] += chunk.positionHistogram[i];
    }
    for (let i = 0; i < pointsHistogram.length; i++) {
      pointsHistogram[i] += chunk.pointsHistogram[i];
    }
    for (let i = 0; i < teamCount; i++) {
      pointsSum[i] += chunk.pointsSum[i];
      pointsSquaredSum[i] += chunk.pointsSquaredSum[i];
    }
  }

  return {
    nSims: totalSims,
    teamCount,
    histogramSize,
    positionHistogram,
    pointsHistogram,
    pointsSum,
    pointsSquaredSum,
  };
}

export function finalizeLaLigaProjection(
  config: LaLigaSimConfig,
  merged: LaLigaChunkOutput,
  elapsedSeconds: number,
): ProjectionPayload {
  const teams = resolveTeamsForStart(
    config.teams,
    config.startMatchday,
    config.eloByMatchday,
    config.eloDelta,
  );
  const teamCount = teams.length;
  const teamIndex = new Map<string, number>();
  for (let i = 0; i < teamCount; i++) {
    teamIndex.set(teams[i].id, i);
  }

  const effectiveMatches = getEffectiveMatches(
    config.matches,
    config.startMatchday,
  );
  const playedMatches = effectiveMatches.filter((m) => m.played);
  const pendingMatches = effectiveMatches.filter((m) => !m.played);
  const goalsAvailable =
    config.mode === "score" &&
    playedMatches.every((m) => m.homeGoals !== null && m.awayGoals !== null);

  const { predictions } = predictPendingMatches(
    pendingMatches,
    teams,
    teamIndex,
    config,
  );

  const nSims = merged.nSims;
  const { histogramSize, positionHistogram, pointsHistogram, pointsSum, pointsSquaredSum } =
    merged;

  const teamProjections: TeamProjection[] = [];
  for (let slot = 0; slot < teamCount; slot++) {
    const team = teams[slot];
    const expPoints = pointsSum[slot] / nSims;
    const variance = Math.max(
      pointsSquaredSum[slot] / nSims - expPoints * expPoints,
      0,
    );
    const stdPoints = Math.sqrt(variance);

    const posProbs: number[] = new Array(teamCount);
    let expPosition = 0;
    let bestPosIdx = 0;
    let bestPosProb = -1;
    let top4 = 0;
    let relegation = 0;
    const top4Limit = Math.min(4, teamCount);
    const relStart = Math.max(0, teamCount - 3);
    const posOffset = slot * teamCount;

    for (let p = 0; p < teamCount; p++) {
      const prob = positionHistogram[posOffset + p] / nSims;
      posProbs[p] = prob;
      expPosition += (p + 1) * prob;
      if (prob > bestPosProb) {
        bestPosProb = prob;
        bestPosIdx = p;
      }
      if (p < top4Limit) top4 += prob;
      if (p >= relStart) relegation += prob;
    }

    const ptsOffset = slot * histogramSize;
    const ptsDist: number[] = new Array(histogramSize);
    for (let p = 0; p < histogramSize; p++) {
      ptsDist[p] = pointsHistogram[ptsOffset + p] / nSims;
    }

    teamProjections.push({
      team: { ...team, elo: roundTo(team.elo, 1) },
      expected_points: roundTo(expPoints, 2),
      points_std: roundTo(stdPoints, 2),
      median_points: percentileFromHistogram(
        pointsHistogram,
        ptsOffset,
        histogramSize,
        0.5,
        nSims,
      ),
      p10_points: percentileFromHistogram(
        pointsHistogram,
        ptsOffset,
        histogramSize,
        0.1,
        nSims,
      ),
      p90_points: percentileFromHistogram(
        pointsHistogram,
        ptsOffset,
        histogramSize,
        0.9,
        nSims,
      ),
      expected_position: roundTo(expPosition, 2),
      most_likely_position: bestPosIdx + 1,
      champion_probability: posProbs[0] ?? 0,
      top4_probability: top4,
      relegation_probability: relegation,
      position_probabilities: posProbs,
      points_histogram: ptsDist,
    });
  }

  teamProjections.sort((a, b) => {
    if (a.expected_position !== b.expected_position) {
      return a.expected_position - b.expected_position;
    }
    return a.team.name < b.team.name ? -1 : a.team.name > b.team.name ? 1 : 0;
  });

  // Base standings use un-deltaed snapshot teams (matching backend/app/api/serializers.py)
  const baseMatches = config.matches.filter(
    (m) =>
      m.played &&
      (config.startMatchday == null || m.matchday < config.startMatchday),
  );
  const baseStandings = computeLaLigaStandings(
    config.teams,
    baseMatches,
    config.fairPlay ?? {},
  );

  return {
    mode: config.mode,
    n_sims: nSims,
    seed: config.seed,
    elapsed_seconds: roundTo(elapsedSeconds, 3),
    goals_available: goalsAvailable,
    start_matchday: config.startMatchday ?? null,
    base_played_matches: baseMatches.length,
    base_standings: baseStandings,
    data_version: config.dataVersion,
    source: config.source,
    teams: teamProjections,
    match_predictions: predictions,
  };
}

export function simulateLaLiga(
  config: LaLigaSimConfig,
  onProgress?: (completed: number, total: number) => void,
): ProjectionPayload {
  const started = performance.now();
  const chunk = runLaLigaChunk(config, config.nSims, config.seed, onProgress);
  const elapsed = (performance.now() - started) / 1000;
  return finalizeLaLigaProjection(config, chunk, elapsed);
}

export function modelParamsFromSeason(
  model: ModelInfo,
  overrides?: { home_advantage?: number; nu?: number; rho?: number },
): { davidson: DavidsonParams; scoreline: ScorelineParams } {
  const homeAdvantage = overrides?.home_advantage;
  return {
    davidson: {
      home_advantage:
        homeAdvantage !== undefined
          ? homeAdvantage
          : model.davidson.home_advantage,
      nu: overrides?.nu !== undefined ? overrides.nu : model.davidson.nu,
      elo_scale: model.davidson.elo_scale,
    },
    scoreline: {
      home_base: model.scoreline.home_base,
      away_base: model.scoreline.away_base,
      elo_slope: model.scoreline.elo_slope,
      home_advantage:
        homeAdvantage !== undefined
          ? homeAdvantage
          : model.scoreline.home_advantage,
      rho: overrides?.rho !== undefined ? overrides.rho : model.scoreline.rho,
      max_goals: model.scoreline.max_goals,
    },
  };
}
