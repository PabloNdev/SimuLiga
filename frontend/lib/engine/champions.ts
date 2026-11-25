import type {
  ChampionsBracketEntry,
  ChampionsMatchItem,
  ChampionsMatchPrediction,
  ChampionsMatchup,
  ChampionsProjectionPayload,
  ChampionsProjectionTeam,
  ChampionsStanding,
  ChampionsTeam,
} from "@/lib/champions-types";
import type { Mode } from "@/lib/types";
import {
  createRng,
  davidsonProbabilities,
  expectedGoals,
  percentileFromHistogram,
  prepareScoreline,
  roundTo,
  sampleFlatIndexFromCdf,
  type DavidsonParams,
  type MatchProbabilities,
  type PreparedScoreline,
  type ScorelineParams,
} from "./math.ts";

export interface ChampionsMatchInput {
  id: string;
  matchday: number;
  homeId: string;
  awayId: string;
  played: boolean;
  homeGoals: number | null;
  awayGoals: number | null;
  outcome: "H" | "D" | "A" | null;
}

export interface ChampionsSimConfig {
  teams: ChampionsTeam[];
  matches: ChampionsMatchInput[];
  baseStandings: ChampionsStanding[];
  mode: Mode;
  nSims: number;
  seed: number | null;
  davidson: DavidsonParams;
  scoreline: ScorelineParams;
  dataVersion: string;
  source: string;
  demo: boolean;
  fallback: boolean;
  dataNote: string | null;
}

export interface ChampionsChunkOutput {
  nSims: number;
  teamCount: number;
  histogramSize: number;
  directCutoff: number;
  playoffCutoff: number;
  positionHistogram: Uint32Array;
  pointsHistogram: Uint32Array;
  pointsSum: Float64Array;
  pointsSquaredSum: Float64Array;
  advanceCounts: Uint32Array;
  opponentCounts: Uint32Array;
  pairCounts: Uint32Array;
  slotCounts: Uint32Array;
}

interface PendingChampionsModel {
  homeSlot: number;
  awaySlot: number;
  cdf: Float64Array | null;
  width: number;
  homeProb: number;
  homePlusDrawProb: number;
}

export function championsMatchItemsToInput(
  items: ChampionsMatchItem[],
): ChampionsMatchInput[] {
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

export function qualificationCuts(teamCount: number): [number, number] {
  if (teamCount >= 36) return [8, 24];
  const direct = Math.max(1, Math.floor(teamCount / 4));
  const playoffCutoff = Math.max(direct + 1, Math.floor(teamCount / 2));
  return [direct, Math.min(teamCount, playoffCutoff)];
}

function predictPendingMatches(
  pendingMatches: ChampionsMatchInput[],
  teams: ChampionsTeam[],
  teamIndex: Map<string, number>,
  config: ChampionsSimConfig,
): {
  predictions: ChampionsMatchPrediction[];
  models: PendingChampionsModel[];
} {
  const predictions: ChampionsMatchPrediction[] = [];
  const models: PendingChampionsModel[] = [];

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
      cdf = prepared.cdf;
      width = prepared.width;
    } else {
      probs = davidsonProbabilities(home.elo, away.elo, config.davidson);
    }

    models.push({
      homeSlot,
      awaySlot,
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
 * Run a chunk of Champions League Monte Carlo simulations (league phase + two-legged playoff).
 */
export function runChampionsChunk(
  config: ChampionsSimConfig,
  chunkSims: number,
  chunkSeed: number | null,
  onProgress?: (completed: number, total: number) => void,
  progressInterval = 2_000,
): ChampionsChunkOutput {
  const teams = config.teams;
  const teamCount = teams.length;
  const teamIndex = new Map<string, number>();
  for (let i = 0; i < teamCount; i++) {
    teamIndex.set(teams[i].id, i);
  }

  const playedMatches: ChampionsMatchInput[] = [];
  const pendingMatches: ChampionsMatchInput[] = [];
  const matchesPerTeam = new Int32Array(teamCount);

  for (const m of config.matches) {
    const hSlot = teamIndex.get(m.homeId);
    const aSlot = teamIndex.get(m.awayId);
    if (hSlot === undefined || aSlot === undefined) continue;
    matchesPerTeam[hSlot] += 1;
    matchesPerTeam[aSlot] += 1;
    if (m.played) playedMatches.push(m);
    else pendingMatches.push(m);
  }

  const basePoints = new Int32Array(teamCount);
  const baseGoalsFor = new Int32Array(teamCount);
  const baseGoalsAgainst = new Int32Array(teamCount);
  const baseAwayGoals = new Int32Array(teamCount);
  const baseWins = new Int32Array(teamCount);
  const baseAwayWins = new Int32Array(teamCount);

  for (const m of playedMatches) {
    const hSlot = teamIndex.get(m.homeId)!;
    const aSlot = teamIndex.get(m.awayId)!;
    const hg = m.homeGoals ?? 0;
    const ag = m.awayGoals ?? 0;
    baseGoalsFor[hSlot] += hg;
    baseGoalsAgainst[hSlot] += ag;
    baseGoalsFor[aSlot] += ag;
    baseGoalsAgainst[aSlot] += hg;
    baseAwayGoals[aSlot] += ag;

    const outcome =
      m.outcome ?? (hg > ag ? "H" : hg < ag ? "A" : "D");
    if (outcome === "H") {
      baseWins[hSlot] += 1;
      basePoints[hSlot] += 3;
    } else if (outcome === "A") {
      baseWins[aSlot] += 1;
      baseAwayWins[aSlot] += 1;
      basePoints[aSlot] += 3;
    } else {
      basePoints[hSlot] += 1;
      basePoints[aSlot] += 1;
    }
  }

  let maxBasePoints = 0;
  let maxMatchesPerTeam = 0;
  for (let i = 0; i < teamCount; i++) {
    if (basePoints[i] > maxBasePoints) maxBasePoints = basePoints[i];
    if (matchesPerTeam[i] > maxMatchesPerTeam) maxMatchesPerTeam = matchesPerTeam[i];
  }
  const histogramSize = maxBasePoints + 3 * maxMatchesPerTeam + 1;

  const [directCutoff, playoffCutoff] = qualificationCuts(teamCount);
  const playoffSlotCount = Math.max(0, playoffCutoff - directCutoff);
  const pairCountPerSim = Math.floor(playoffSlotCount / 2);

  const { models } = predictPendingMatches(
    pendingMatches,
    teams,
    teamIndex,
    config,
  );
  const pendingCount = models.length;
  const isScoreMode = config.mode === "score";

  // Lazy flat caches for playoff scoreline CDFs (normal leg and extra time 1/3)
  const scorelineWidth = config.scoreline.max_goals + 1;
  const regularCdfCache: (Float64Array | undefined)[] = new Array(
    teamCount * teamCount,
  );
  const extraCdfCache: (Float64Array | undefined)[] = new Array(
    teamCount * teamCount,
  );

  const getPlayoffCdf = (
    homeSlot: number,
    awaySlot: number,
    extraTime: boolean,
  ): Float64Array => {
    const key = homeSlot * teamCount + awaySlot;
    const cache = extraTime ? extraCdfCache : regularCdfCache;
    let cdf = cache[key];
    if (!cdf) {
      const [lh, la] = expectedGoals(
        teams[homeSlot].elo,
        teams[awaySlot].elo,
        config.scoreline,
      );
      const scale = extraTime ? 1 / 3 : 1;
      cdf = prepareScoreline(lh * scale, la * scale, config.scoreline).cdf;
      cache[key] = cdf;
    }
    return cdf;
  };

  // Output accumulators
  const positionHistogram = new Uint32Array(teamCount * teamCount);
  const pointsHistogram = new Uint32Array(teamCount * histogramSize);
  const pointsSum = new Float64Array(teamCount);
  const pointsSquaredSum = new Float64Array(teamCount);
  const advanceCounts = new Uint32Array(teamCount);
  const opponentCounts = new Uint32Array(teamCount * teamCount);
  const pairCounts = new Uint32Array(teamCount * teamCount);
  const slotCounts = new Uint32Array(playoffSlotCount * teamCount);

  // Per-simulation reusable buffers
  const points = new Int32Array(teamCount);
  const goalsFor = new Int32Array(teamCount);
  const goalsAgainst = new Int32Array(teamCount);
  const goalDiff = new Int32Array(teamCount);
  const awayGoals = new Int32Array(teamCount);
  const wins = new Int32Array(teamCount);
  const awayWins = new Int32Array(teamCount);
  const randomKeys = new Float64Array(teamCount);
  const order = new Int32Array(teamCount);

  const rng = createRng(chunkSeed);

  const betterBefore = (a: number, b: number): boolean => {
    if (points[a] !== points[b]) return points[a] > points[b];
    if (goalDiff[a] !== goalDiff[b]) return goalDiff[a] > goalDiff[b];
    if (goalsFor[a] !== goalsFor[b]) return goalsFor[a] > goalsFor[b];
    if (awayGoals[a] !== awayGoals[b]) return awayGoals[a] > awayGoals[b];
    if (wins[a] !== wins[b]) return wins[a] > wins[b];
    if (awayWins[a] !== awayWins[b]) return awayWins[a] > awayWins[b];
    if (randomKeys[a] !== randomKeys[b]) return randomKeys[a] > randomKeys[b];
    return a < b;
  };

  for (let sim = 0; sim < chunkSims; sim++) {
    points.set(basePoints);
    goalsFor.set(baseGoalsFor);
    goalsAgainst.set(baseGoalsAgainst);
    awayGoals.set(baseAwayGoals);
    wins.set(baseWins);
    awayWins.set(baseAwayWins);

    for (let m = 0; m < pendingCount; m++) {
      const model = models[m];
      const hSlot = model.homeSlot;
      const aSlot = model.awaySlot;

      if (isScoreMode) {
        const flat = sampleFlatIndexFromCdf(model.cdf!, rng());
        const hg = (flat / model.width) | 0;
        const ag = flat - hg * model.width;
        goalsFor[hSlot] += hg;
        goalsAgainst[hSlot] += ag;
        goalsFor[aSlot] += ag;
        goalsAgainst[aSlot] += hg;
        awayGoals[aSlot] += ag;
        if (hg > ag) {
          points[hSlot] += 3;
          wins[hSlot] += 1;
        } else if (hg < ag) {
          points[aSlot] += 3;
          wins[aSlot] += 1;
          awayWins[aSlot] += 1;
        } else {
          points[hSlot] += 1;
          points[aSlot] += 1;
        }
      } else {
        const draw = rng();
        if (draw < model.homeProb) {
          points[hSlot] += 3;
          wins[hSlot] += 1;
        } else if (draw < model.homePlusDrawProb) {
          points[hSlot] += 1;
          points[aSlot] += 1;
        } else {
          points[aSlot] += 3;
          wins[aSlot] += 1;
          awayWins[aSlot] += 1;
        }
      }
    }

    for (let i = 0; i < teamCount; i++) {
      goalDiff[i] = goalsFor[i] - goalsAgainst[i];
      randomKeys[i] = rng();
      order[i] = i;
    }

    // Insertion sort on 36 teams by UCL tiebreakers
    for (let i = 1; i < teamCount; i++) {
      const key = order[i];
      let j = i - 1;
      while (j >= 0 && betterBefore(key, order[j])) {
        order[j + 1] = order[j];
        j--;
      }
      order[j + 1] = key;
    }

    // Update position & points histograms
    for (let pos = 0; pos < teamCount; pos++) {
      const slot = order[pos];
      positionHistogram[slot * teamCount + pos] += 1;
      const p = points[slot];
      pointsSum[slot] += p;
      pointsSquaredSum[slot] += p * p;
      if (p >= 0 && p < histogramSize) {
        pointsHistogram[slot * histogramSize + p] += 1;
      }
    }

    // Simulate two-legged knockout playoff for positions directCutoff..playoffCutoff-1
    for (let idx = 0; idx < pairCountPerSim; idx++) {
      const betterPosOffset = idx;
      const worsePosOffset = playoffSlotCount - 1 - idx;
      const betterSlot = order[directCutoff + betterPosOffset];
      const worseSlot = order[directCutoff + worsePosOffset];

      // Leg 1: worse seed hosts
      const leg1Flat = sampleFlatIndexFromCdf(
        getPlayoffCdf(worseSlot, betterSlot, false),
        rng(),
      );
      const worseHome = (leg1Flat / scorelineWidth) | 0;
      const betterAway = leg1Flat - worseHome * scorelineWidth;

      // Leg 2: better seed hosts
      const leg2Flat = sampleFlatIndexFromCdf(
        getPlayoffCdf(betterSlot, worseSlot, false),
        rng(),
      );
      const betterHome = (leg2Flat / scorelineWidth) | 0;
      const worseAway = leg2Flat - betterHome * scorelineWidth;

      const aggBetter = betterAway + betterHome;
      const aggWorse = worseHome + worseAway;

      let winner: number;
      if (aggBetter !== aggWorse) {
        winner = aggBetter > aggWorse ? betterSlot : worseSlot;
      } else {
        const extraFlat = sampleFlatIndexFromCdf(
          getPlayoffCdf(betterSlot, worseSlot, true),
          rng(),
        );
        const extraHome = (extraFlat / scorelineWidth) | 0;
        const extraAway = extraFlat - extraHome * scorelineWidth;
        if (extraHome !== extraAway) {
          winner = extraHome > extraAway ? betterSlot : worseSlot;
        } else {
          winner = rng() < 0.5 ? betterSlot : worseSlot;
        }
      }

      const loser = winner === betterSlot ? worseSlot : betterSlot;
      advanceCounts[winner] += 1;
      opponentCounts[winner * teamCount + loser] += 1;
      opponentCounts[loser * teamCount + winner] += 1;
      pairCounts[betterSlot * teamCount + worseSlot] += 1;
      slotCounts[betterPosOffset * teamCount + betterSlot] += 1;
      slotCounts[worsePosOffset * teamCount + worseSlot] += 1;
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
    directCutoff,
    playoffCutoff,
    positionHistogram,
    pointsHistogram,
    pointsSum,
    pointsSquaredSum,
    advanceCounts,
    opponentCounts,
    pairCounts,
    slotCounts,
  };
}

export function mergeChampionsChunks(
  chunks: ChampionsChunkOutput[],
): ChampionsChunkOutput {
  const first = chunks[0];
  const { teamCount, histogramSize, directCutoff, playoffCutoff } = first;
  const playoffSlotCount = Math.max(0, playoffCutoff - directCutoff);

  const positionHistogram = new Uint32Array(teamCount * teamCount);
  const pointsHistogram = new Uint32Array(teamCount * histogramSize);
  const pointsSum = new Float64Array(teamCount);
  const pointsSquaredSum = new Float64Array(teamCount);
  const advanceCounts = new Uint32Array(teamCount);
  const opponentCounts = new Uint32Array(teamCount * teamCount);
  const pairCounts = new Uint32Array(teamCount * teamCount);
  const slotCounts = new Uint32Array(playoffSlotCount * teamCount);
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
      advanceCounts[i] += chunk.advanceCounts[i];
    }
    for (let i = 0; i < opponentCounts.length; i++) {
      opponentCounts[i] += chunk.opponentCounts[i];
      pairCounts[i] += chunk.pairCounts[i];
    }
    for (let i = 0; i < slotCounts.length; i++) {
      slotCounts[i] += chunk.slotCounts[i];
    }
  }

  return {
    nSims: totalSims,
    teamCount,
    histogramSize,
    directCutoff,
    playoffCutoff,
    positionHistogram,
    pointsHistogram,
    pointsSum,
    pointsSquaredSum,
    advanceCounts,
    opponentCounts,
    pairCounts,
    slotCounts,
  };
}

export function finalizeChampionsProjection(
  config: ChampionsSimConfig,
  merged: ChampionsChunkOutput,
  elapsedSeconds: number,
): ChampionsProjectionPayload {
  const teams = config.teams;
  const teamCount = teams.length;
  const teamIndex = new Map<string, number>();
  for (let i = 0; i < teamCount; i++) {
    teamIndex.set(teams[i].id, i);
  }

  const pendingMatches = config.matches.filter((m) => !m.played);
  const { predictions } = predictPendingMatches(
    pendingMatches,
    teams,
    teamIndex,
    config,
  );

  const {
    nSims,
    histogramSize,
    directCutoff,
    playoffCutoff,
    positionHistogram,
    pointsHistogram,
    pointsSum,
    pointsSquaredSum,
    advanceCounts,
    opponentCounts,
    pairCounts,
    slotCounts,
  } = merged;
  const playoffSlotCount = Math.max(0, playoffCutoff - directCutoff);

  const teamProjections: ChampionsProjectionTeam[] = [];
  const advanceProbabilities: Record<string, number> = {};
  const playoffOpponentProbs: Record<string, Record<string, number>> = {};

  for (let slot = 0; slot < teamCount; slot++) {
    const team = teams[slot];
    const expPoints = pointsSum[slot] / nSims;
    const variance = Math.max(
      pointsSquaredSum[slot] / nSims - expPoints * expPoints,
      0,
    );
    const stdPoints = Math.sqrt(variance);

    const posOffset = slot * teamCount;
    const posProbs: number[] = new Array(teamCount);
    let expPosition = 0;
    let bestPosIdx = 0;
    let bestPosProb = -1;
    let top8 = 0;
    let playoffProb = 0;
    let eliminated = 0;
    let playoffAppearances = 0;

    for (let p = 0; p < teamCount; p++) {
      const count = positionHistogram[posOffset + p];
      const prob = count / nSims;
      posProbs[p] = prob;
      expPosition += (p + 1) * prob;
      if (prob > bestPosProb) {
        bestPosProb = prob;
        bestPosIdx = p;
      }
      if (p < directCutoff) {
        top8 += prob;
      } else if (p < playoffCutoff) {
        playoffProb += prob;
        playoffAppearances += count;
      } else {
        eliminated += prob;
      }
    }

    const opponents: Record<string, number> = {};
    const summaryOpponents: Record<string, number> = {};
    const oppRowOffset = slot * teamCount;
    let oppSum = 0;
    for (let other = 0; other < teamCount; other++) {
      oppSum += opponentCounts[oppRowOffset + other];
    }
    const denom = Math.max(1, oppSum);
    for (let other = 0; other < teamCount; other++) {
      const count = opponentCounts[oppRowOffset + other];
      if (count > 0) {
        const otherId = teams[other].id;
        if (playoffAppearances > 0) {
          opponents[otherId] = count / playoffAppearances;
        }
        summaryOpponents[otherId] = count / denom;
      }
    }
    playoffOpponentProbs[team.id] = summaryOpponents;

    const playoffWin = advanceCounts[slot] / nSims;
    advanceProbabilities[team.id] = playoffWin;

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
      top8_probability: top8,
      playoff_probability: playoffProb,
      eliminated_probability: eliminated,
      playoff_win_probability: playoffWin,
      round_of_16_probability: top8 + playoffWin,
      position_probabilities: posProbs,
      opponent_probabilities: opponents,
      points_histogram: ptsDist,
    });
  }

  teamProjections.sort((a, b) => {
    if (a.expected_position !== b.expected_position) {
      return a.expected_position - b.expected_position;
    }
    return a.team.name < b.team.name ? -1 : a.team.name > b.team.name ? 1 : 0;
  });

  // Build bracket (best vs worst across playoff slots)
  const bracket: ChampionsBracketEntry[] = [];
  const halfSlots = Math.floor(playoffSlotCount / 2);
  for (let idx = 0; idx < halfSlots; idx++) {
    const betterPosOffset = idx;
    const worsePosOffset = playoffSlotCount - 1 - idx;

    let betterBest = -1;
    let betterBestCount = -1;
    let betterTotal = 0;
    const betterRowOffset = betterPosOffset * teamCount;
    for (let t = 0; t < teamCount; t++) {
      const c = slotCounts[betterRowOffset + t];
      betterTotal += c;
      if (c > betterBestCount) {
        betterBestCount = c;
        betterBest = t;
      }
    }

    let worseBest = -1;
    let worseBestCount = -1;
    let worseTotal = 0;
    const worseRowOffset = worsePosOffset * teamCount;
    for (let t = 0; t < teamCount; t++) {
      const c = slotCounts[worseRowOffset + t];
      worseTotal += c;
      if (c > worseBestCount) {
        worseBestCount = c;
        worseBest = t;
      }
    }

    bracket.push({
      better_slot: directCutoff + 1 + betterPosOffset,
      worse_slot: directCutoff + 1 + worsePosOffset,
      better_team:
        betterBest >= 0 && betterTotal > 0
          ? { ...teams[betterBest], elo: roundTo(teams[betterBest].elo, 1) }
          : null,
      better_probability:
        betterBest >= 0 && betterTotal > 0
          ? betterBestCount / betterTotal
          : 0,
      worse_team:
        worseBest >= 0 && worseTotal > 0
          ? { ...teams[worseBest], elo: roundTo(teams[worseBest].elo, 1) }
          : null,
      worse_probability:
        worseBest >= 0 && worseTotal > 0 ? worseBestCount / worseTotal : 0,
    });
  }

  // Top 20 most probable matchups
  const rawMatchups: { betterIdx: number; worseIdx: number; count: number }[] = [];
  for (let b = 0; b < teamCount; b++) {
    const rowOffset = b * teamCount;
    for (let w = 0; w < teamCount; w++) {
      const c = pairCounts[rowOffset + w];
      if (c > 0) {
        rawMatchups.push({ betterIdx: b, worseIdx: w, count: c });
      }
    }
  }
  rawMatchups.sort((a, b) => b.count - a.count);

  const matchups: ChampionsMatchup[] = rawMatchups.slice(0, 20).map((entry) => ({
    better_id: teams[entry.betterIdx].id,
    worse_id: teams[entry.worseIdx].id,
    probability: entry.count / nSims,
    better_team: {
      ...teams[entry.betterIdx],
      elo: roundTo(teams[entry.betterIdx].elo, 1),
    },
    worse_team: {
      ...teams[entry.worseIdx],
      elo: roundTo(teams[entry.worseIdx].elo, 1),
    },
  }));

  return {
    mode: config.mode,
    n_sims: nSims,
    seed: config.seed,
    elapsed_seconds: roundTo(elapsedSeconds, 3),
    goals_available: config.mode === "score",
    data_version: config.dataVersion,
    source: config.source,
    demo: config.demo,
    fallback: config.fallback,
    data_note: config.dataNote,
    base_standings: config.baseStandings,
    teams: teamProjections,
    match_predictions: predictions,
    playoff: {
      bracket,
      advance_probabilities: advanceProbabilities,
      opponent_probabilities: playoffOpponentProbs,
      matchups,
    },
  };
}

export function simulateChampions(
  config: ChampionsSimConfig,
  onProgress?: (completed: number, total: number) => void,
): ChampionsProjectionPayload {
  const started = performance.now();
  const chunk = runChampionsChunk(config, config.nSims, config.seed, onProgress);
  const elapsed = (performance.now() - started) / 1000;
  return finalizeChampionsProjection(config, chunk, elapsed);
}
