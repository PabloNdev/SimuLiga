import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  championsMatchItemsToInput,
  finalizeChampionsProjection,
  mergeChampionsChunks,
  runChampionsChunk,
  simulateChampions,
} from "../lib/engine/champions.ts";
import {
  buildEloByMatchday,
  finalizeLaLigaProjection,
  matchItemsToEngineInput,
  mergeLaLigaChunks,
  modelParamsFromSeason,
  runLaLigaChunk,
  simulateLaLiga,
} from "../lib/engine/laliga.ts";
import {
  davidsonProbabilities,
  deriveWorkerSeed,
  expectedGoals,
  prepareScoreline,
} from "../lib/engine/math.ts";
import {
  CHAMPIONS_MAX_SIMS_BROWSER,
  clampSimSize,
  DEFAULT_SIMS,
  LALIGA_MAX_SIMS,
  MIN_SIMS,
} from "../lib/sim-config.ts";

const dataDir = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "public",
  "data",
);

async function readJson(name) {
  return JSON.parse(await readFile(path.join(dataDir, name), "utf8"));
}

test("mobile-first default simulation size and clamping rules", () => {
  assert.equal(DEFAULT_SIMS, 5_000);
  assert.equal(clampSimSize(10, LALIGA_MAX_SIMS), MIN_SIMS);
  assert.equal(clampSimSize(5_000_000, LALIGA_MAX_SIMS), LALIGA_MAX_SIMS);
  assert.equal(
    clampSimSize(500_000, CHAMPIONS_MAX_SIMS_BROWSER),
    CHAMPIONS_MAX_SIMS_BROWSER,
  );
  assert.equal(clampSimSize(Number.NaN, LALIGA_MAX_SIMS), DEFAULT_SIMS);
  assert.equal(clampSimSize(12345.6, LALIGA_MAX_SIMS), 12346);
});

test("Davidson and Dixon-Coles probabilities sum to 1 and match expected monotonicity", () => {
  const dav = davidsonProbabilities(1850, 1550, {
    home_advantage: 83.26,
    nu: 0.8177,
    elo_scale: 400,
  });
  assert.ok(Math.abs(dav.home + dav.draw + dav.away - 1) < 1e-12);
  assert.ok(dav.home > dav.draw && dav.home > dav.away);

  const scoreParams = {
    home_base: 1.45,
    away_base: 1.15,
    elo_slope: 0.0018,
    home_advantage: 83.26,
    rho: -0.05,
    max_goals: 10,
  };
  const [lh, la] = expectedGoals(1850, 1550, scoreParams);
  const prepared = prepareScoreline(lh, la, scoreParams);
  assert.ok(
    Math.abs(
      prepared.probabilities.home +
        prepared.probabilities.draw +
        prepared.probabilities.away -
        1,
    ) < 1e-12,
  );
  assert.equal(prepared.cdf[prepared.cdf.length - 1], 1);
});

test("buildEloByMatchday reconstructs current Elo ratings closely to backend elo.json", async () => {
  const [season, matchesPayload, eloPayload] = await Promise.all([
    readJson("season.json"),
    readJson("matches-score.json"),
    readJson("elo.json"),
  ]);
  const matches = matchItemsToEngineInput(matchesPayload.matches);
  const byMd = buildEloByMatchday(season, matches, eloPayload);

  const latestKey = Math.max(...Object.keys(byMd).map(Number));
  const latest = byMd[latestKey];

  for (const team of season.teams) {
    const diff = Math.abs(latest[team.id] - team.elo);
    assert.ok(
      diff < 1.0,
      `Expected reconstructed Elo for ${team.id} (${latest[team.id]}) to match ${team.elo}`,
    );
  }
});

test("LaLiga browser engine matches Python snapshot statistically (score and 1x2)", async () => {
  const [season, matchesPayload, eloPayload, refScore, ref1x2] =
    await Promise.all([
      readJson("season.json"),
      readJson("matches-score.json"),
      readJson("elo.json"),
      readJson("projection-score.json"),
      readJson("projection-1x2.json"),
    ]);

  const matches = matchItemsToEngineInput(matchesPayload.matches);
  const eloByMatchday = buildEloByMatchday(season, matches, eloPayload);
  const { davidson, scoreline } = modelParamsFromSeason(season.model);

  for (const [mode, ref] of [
    ["score", refScore],
    ["1x2", ref1x2],
  ]) {
    const result = simulateLaLiga({
      teams: season.teams,
      matches,
      mode,
      nSims: 5_000,
      seed: 42,
      davidson,
      scoreline,
      startMatchday: season.current_matchday,
      eloByMatchday,
      dataVersion: season.data_version,
      source: season.source,
    });

    assert.equal(result.n_sims, 5_000);
    assert.equal(result.mode, mode);
    assert.equal(result.teams.length, season.teams.length);

    const refById = new Map(ref.teams.map((t) => [t.team.id, t]));
    const champSum = result.teams.reduce(
      (acc, t) => acc + t.champion_probability,
      0,
    );
    assert.ok(Math.abs(champSum - 1) < 1e-6);

    for (const proj of result.teams) {
      const expected = refById.get(proj.team.id);
      assert.ok(expected, `missing team ${proj.team.id}`);
      assert.ok(
        Math.abs(proj.expected_points - expected.expected_points) < 1.2,
        `${mode} expected_points mismatch for ${proj.team.id}: ${proj.expected_points} vs ${expected.expected_points}`,
      );
      assert.ok(
        Math.abs(proj.champion_probability - expected.champion_probability) <
          0.035,
        `${mode} champion_probability mismatch for ${proj.team.id}: ${proj.champion_probability} vs ${expected.champion_probability}`,
      );
    }
  }
});

test("LaLiga scenario overrides (Elo delta & forced results) shift probabilities cleanly and chunks merge", async () => {
  const [season, matchesPayload, eloPayload] = await Promise.all([
    readJson("season.json"),
    readJson("matches-score.json"),
    readJson("elo.json"),
  ]);
  const matches = matchItemsToEngineInput(matchesPayload.matches);
  const eloByMatchday = buildEloByMatchday(season, matches, eloPayload);
  const { davidson, scoreline } = modelParamsFromSeason(season.model);

  const baseConfig = {
    teams: season.teams,
    matches,
    mode: "score",
    nSims: 2_000,
    seed: 42,
    davidson,
    scoreline,
    startMatchday: season.current_matchday,
    eloByMatchday,
    dataVersion: season.data_version,
    source: season.source,
  };

  const base = simulateLaLiga(baseConfig);
  const boosted = simulateLaLiga({
    ...baseConfig,
    eloDelta: { "real-madrid": 150 },
  });

  const baseRma = base.teams.find((t) => t.team.id === "real-madrid");
  const boostedRma = boosted.teams.find((t) => t.team.id === "real-madrid");
  assert.ok(boostedRma.champion_probability > baseRma.champion_probability);

  // Chunk merging check
  const c1 = runLaLigaChunk(baseConfig, 1_000, deriveWorkerSeed(42, 0));
  const c2 = runLaLigaChunk(baseConfig, 1_000, deriveWorkerSeed(42, 1));
  const merged = finalizeLaLigaProjection(
    baseConfig,
    mergeLaLigaChunks([c1, c2]),
    0.1,
  );
  assert.equal(merged.n_sims, 2_000);
  const champSum = merged.teams.reduce(
    (acc, t) => acc + t.champion_probability,
    0,
  );
  assert.ok(Math.abs(champSum - 1) < 1e-6);
});

test("Champions browser engine matches Python snapshot statistically (score and 1x2) and merges chunks", async () => {
  const [season, matchesPayload, refScore, ref1x2] = await Promise.all([
    readJson("champions-season.json"),
    readJson("champions-matches-score.json"),
    readJson("champions-projection-score.json"),
    readJson("champions-projection-1x2.json"),
  ]);

  const matches = championsMatchItemsToInput(matchesPayload.matches);

  for (const [mode, ref] of [
    ["score", refScore],
    ["1x2", ref1x2],
  ]) {
    const config = {
      teams: season.teams,
      matches,
      baseStandings: season.standings,
      mode,
      nSims: 5_000,
      seed: 42,
      davidson: season.model.davidson,
      scoreline: season.model.scoreline,
      dataVersion: season.data_version,
      source: season.source,
      demo: season.demo,
      fallback: season.fallback,
      dataNote: season.data_note,
    };

    const result = simulateChampions(config);
    assert.equal(result.n_sims, 5_000);
    assert.equal(result.teams.length, 36);
    assert.equal(result.playoff.bracket.length, 8);
    assert.ok(result.playoff.matchups.length > 0);

    const top8Sum = result.teams.reduce((acc, t) => acc + t.top8_probability, 0);
    const playoffWinSum = result.teams.reduce(
      (acc, t) => acc + t.playoff_win_probability,
      0,
    );
    assert.ok(Math.abs(top8Sum - 8) < 1e-6);
    assert.ok(Math.abs(playoffWinSum - 8) < 1e-6);

    const refById = new Map(ref.teams.map((t) => [t.team.id, t]));
    for (const proj of result.teams) {
      const expected = refById.get(proj.team.id);
      assert.ok(expected, `missing champions team ${proj.team.id}`);
      assert.ok(
        Math.abs(proj.expected_points - expected.expected_points) < 0.6,
        `UCL ${mode} expected_points mismatch for ${proj.team.id}: ${proj.expected_points} vs ${expected.expected_points}`,
      );
      assert.ok(
        Math.abs(proj.round_of_16_probability - expected.round_of_16_probability) <
          0.045,
        `UCL ${mode} round_of_16 mismatch for ${proj.team.id}: ${proj.round_of_16_probability} vs ${expected.round_of_16_probability}`,
      );
    }

    if (mode === "score") {
      const c1 = runChampionsChunk(config, 1_000, deriveWorkerSeed(42, 0));
      const c2 = runChampionsChunk(config, 1_000, deriveWorkerSeed(42, 1));
      const merged = finalizeChampionsProjection(
        config,
        mergeChampionsChunks([c1, c2]),
        0.1,
      );
      assert.equal(merged.n_sims, 2_000);
      assert.equal(merged.playoff.bracket.length, 8);
    }
  }
});
