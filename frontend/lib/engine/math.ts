import type { Outcome } from "@/lib/types";

export interface DavidsonParams {
  home_advantage: number;
  nu: number;
  elo_scale: number;
}

export interface ScorelineParams {
  home_base: number;
  away_base: number;
  elo_slope: number;
  home_advantage: number;
  rho: number;
  max_goals: number;
}

export interface MatchProbabilities {
  home: number;
  draw: number;
  away: number;
}

export interface PreparedScoreline {
  homeLambda: number;
  awayLambda: number;
  width: number;
  matrix: Float64Array;
  cdf: Float64Array;
  probabilities: MatchProbabilities;
  mostLikely: [number, number, number];
}

export type Rng = () => number;

/**
 * Deterministic xoshiro128** PRNG seeded with SplitMix32.
 * Fast, 128-bit state, and statistically solid for 1M+ Monte Carlo runs.
 */
export function createRng(seed: number | null): Rng {
  let state =
    seed === null
      ? ((Math.random() * 0x100000000) ^ Date.now()) >>> 0
      : seed >>> 0;

  const nextSeed = (): number => {
    state = (state + 0x9e3779b9) >>> 0;
    let z = state;
    z = Math.imul(z ^ (z >>> 16), 0x85ebca6b) >>> 0;
    z = Math.imul(z ^ (z >>> 13), 0xc2b2ae35) >>> 0;
    return (z ^ (z >>> 16)) >>> 0;
  };

  let s0 = nextSeed();
  let s1 = nextSeed();
  let s2 = nextSeed();
  let s3 = nextSeed();
  if ((s0 | s1 | s2 | s3) === 0) {
    s0 = 1;
  }

  return () => {
    const t = (s1 << 9) >>> 0;
    let r = Math.imul(s1, 5) >>> 0;
    r = ((r << 7) | (r >>> 25)) >>> 0;
    r = Math.imul(r, 9) >>> 0;

    s2 = (s2 ^ s0) >>> 0;
    s3 = (s3 ^ s1) >>> 0;
    s1 = (s1 ^ s2) >>> 0;
    s0 = (s0 ^ s3) >>> 0;
    s2 = (s2 ^ t) >>> 0;
    s3 = ((s3 << 11) | (s3 >>> 21)) >>> 0;

    return r / 4294967296;
  };
}

/** Derive an independent deterministic worker seed from a base seed and worker index. */
export function deriveWorkerSeed(baseSeed: number | null, workerIndex: number): number | null {
  if (baseSeed === null) return null;
  let z = ((baseSeed >>> 0) + Math.imul(workerIndex + 1, 0x9e3779b9)) >>> 0;
  z = Math.imul(z ^ (z >>> 16), 0x85ebca6b) >>> 0;
  z = Math.imul(z ^ (z >>> 13), 0xc2b2ae35) >>> 0;
  return (z ^ (z >>> 16)) >>> 0;
}

export function davidsonProbabilities(
  homeElo: number,
  awayElo: number,
  params: DavidsonParams,
): MatchProbabilities {
  const delta = homeElo - awayElo;
  const strength = Math.pow(
    10,
    (delta + params.home_advantage) / params.elo_scale,
  );
  const root = Math.sqrt(strength);
  const denominator = strength + 1 + params.nu * root;
  return {
    home: strength / denominator,
    draw: (params.nu * root) / denominator,
    away: 1 / denominator,
  };
}

export function expectedGoals(
  homeElo: number,
  awayElo: number,
  params: ScorelineParams,
): [number, number] {
  const gap = homeElo - awayElo + params.home_advantage;
  const rawHome = params.home_base * Math.exp(params.elo_slope * gap);
  const rawAway = params.away_base * Math.exp(-params.elo_slope * gap);
  const clamp = (value: number) => Math.min(6.0, Math.max(0.05, value));
  return [clamp(rawHome), clamp(rawAway)];
}

function tau(
  homeGoals: number,
  awayGoals: number,
  lh: number,
  la: number,
  rho: number,
): number {
  if (homeGoals === 0 && awayGoals === 0) return 1 - lh * la * rho;
  if (homeGoals === 1 && awayGoals === 0) return 1 + la * rho;
  if (homeGoals === 0 && awayGoals === 1) return 1 + lh * rho;
  if (homeGoals === 1 && awayGoals === 1) return 1 - rho;
  return 1;
}

function poissonPmf(lambda: number, size: number): Float64Array {
  const rate = Math.max(lambda, 1e-6);
  const pmf = new Float64Array(size);
  let current = Math.exp(-rate);
  pmf[0] = current;
  for (let k = 1; k < size; k++) {
    current = (current * rate) / k;
    pmf[k] = current;
  }
  return pmf;
}

export function prepareScoreline(
  homeLambda: number,
  awayLambda: number,
  params: ScorelineParams,
): PreparedScoreline {
  const width = params.max_goals + 1;
  const homePmf = poissonPmf(homeLambda, width);
  const awayPmf = poissonPmf(awayLambda, width);
  const totalCells = width * width;
  const matrix = new Float64Array(totalCells);

  let sum = 0;
  for (let h = 0; h < width; h++) {
    const hp = homePmf[h];
    const rowOffset = h * width;
    for (let a = 0; a < width; a++) {
      let prob = hp * awayPmf[a];
      if (h < 2 && a < 2) {
        prob *= tau(h, a, homeLambda, awayLambda, params.rho);
      }
      if (prob < 0) prob = 0;
      matrix[rowOffset + a] = prob;
      sum += prob;
    }
  }

  if (sum <= 0) {
    throw new Error("score matrix has no probability mass");
  }

  const cdf = new Float64Array(totalCells);
  let cumulative = 0;
  let homeProb = 0;
  let drawProb = 0;
  let awayProb = 0;
  let bestProb = -1;
  let bestHome = 0;
  let bestAway = 0;

  const invSum = 1 / sum;
  for (let h = 0; h < width; h++) {
    const rowOffset = h * width;
    for (let a = 0; a < width; a++) {
      const idx = rowOffset + a;
      const prob = matrix[idx] * invSum;
      matrix[idx] = prob;
      cumulative += prob;
      cdf[idx] = cumulative;

      if (h > a) homeProb += prob;
      else if (h === a) drawProb += prob;
      else awayProb += prob;

      if (prob > bestProb) {
        bestProb = prob;
        bestHome = h;
        bestAway = a;
      }
    }
  }
  cdf[totalCells - 1] = 1;

  return {
    homeLambda,
    awayLambda,
    width,
    matrix,
    cdf,
    probabilities: { home: homeProb, draw: drawProb, away: awayProb },
    mostLikely: [bestHome, bestAway, bestProb],
  };
}

export function buildConditionedCdf(
  prepared: PreparedScoreline,
  outcome: Outcome,
): Float64Array {
  const { width, matrix } = prepared;
  const totalCells = width * width;
  const conditioned = new Float64Array(totalCells);

  let sum = 0;
  for (let h = 0; h < width; h++) {
    const rowOffset = h * width;
    for (let a = 0; a < width; a++) {
      const keep =
        outcome === "H" ? h > a : outcome === "D" ? h === a : h < a;
      if (keep) {
        const prob = matrix[rowOffset + a];
        conditioned[rowOffset + a] = prob;
        sum += prob;
      }
    }
  }

  if (sum <= 0) {
    throw new Error("the requested outcome has no probability mass");
  }

  const cdf = new Float64Array(totalCells);
  let cumulative = 0;
  const invSum = 1 / sum;
  for (let i = 0; i < totalCells; i++) {
    cumulative += conditioned[i] * invSum;
    cdf[i] = cumulative;
  }
  cdf[totalCells - 1] = 1;
  return cdf;
}

/** Binary search on monotonically increasing CDF, returning the flat index. */
export function sampleFlatIndexFromCdf(cdf: Float64Array, draw: number): number {
  let low = 0;
  let high = cdf.length - 1;
  while (low < high) {
    const mid = (low + high) >>> 1;
    if (draw < cdf[mid]) {
      high = mid;
    } else {
      low = mid + 1;
    }
  }
  return low;
}

export function percentileFromHistogram(
  histogram: Uint32Array | number[],
  offset: number,
  length: number,
  quantile: number,
  nSims: number,
): number {
  const target = quantile * nSims;
  let cumulative = 0;
  for (let i = 0; i < length; i++) {
    cumulative += histogram[offset + i];
    if (cumulative >= target) {
      return i;
    }
  }
  return Math.max(0, length - 1);
}

export function roundTo(value: number, decimals: number): number {
  const factor = Math.pow(10, decimals);
  return Math.round(value * factor) / factor;
}

/** World Football Elo goal-margin multiplier (matches backend/app/domain/elo.py). */
export function goalMarginMultiplier(homeGoals: number, awayGoals: number): number {
  const margin = Math.abs(homeGoals - awayGoals);
  if (margin <= 1) return 1.0;
  if (margin === 2) return 1.5;
  return (11.0 + margin) / 8.0;
}

export function updateEloRatings(
  homeRating: number,
  awayRating: number,
  homeGoals: number,
  awayGoals: number,
  k = 20.0,
  homeAdvantage = 60.0,
  eloScale = 400.0,
): [number, number] {
  const expectedHome =
    1 / (1 + Math.pow(10, -((homeRating + homeAdvantage) - awayRating) / eloScale));
  const actualHome =
    homeGoals > awayGoals ? 1.0 : homeGoals < awayGoals ? 0.0 : 0.5;
  const change =
    k * goalMarginMultiplier(homeGoals, awayGoals) * (actualHome - expectedHome);
  return [homeRating + change, awayRating - change];
}
