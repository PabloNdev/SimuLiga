import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_SCENARIO,
  buildScenarioParams,
  modelParamDefaults,
  parseScenario,
} from "../lib/scenario.ts";

test("scenario model parameters default to 1X2 and calibrated backend values", () => {
  assert.equal(DEFAULT_SCENARIO.mode, "1x2");
  assert.equal(DEFAULT_SCENARIO.homeAdvantage, null);
  assert.equal(DEFAULT_SCENARIO.nu, null);
});

test("parseScenario leaves model parameters unset when the URL omits them", () => {
  const state = parseScenario(new URLSearchParams(""));
  assert.equal(state.mode, "1x2");
  assert.equal(state.homeAdvantage, null);
  assert.equal(state.nu, null);
});

test("parseScenario normalizes legacy mode=score links to 1x2 and reads model overrides", () => {
  const state = parseScenario(
    new URLSearchParams("mode=score&h=72&nu=1.1&rho=-0.02"),
  );
  assert.equal(state.mode, "1x2");
  assert.equal(state.homeAdvantage, 72);
  assert.equal(state.nu, 1.1);
  assert.equal("rho" in state, false);
});

test("buildScenarioParams omits mode, rho, and default model parameters", () => {
  const defaults = buildScenarioParams(DEFAULT_SCENARIO);
  assert.equal(defaults.has("mode"), false);
  assert.equal(defaults.has("h"), false);
  assert.equal(defaults.has("nu"), false);
  assert.equal(defaults.has("rho"), false);

  const overridden = buildScenarioParams({
    ...DEFAULT_SCENARIO,
    homeAdvantage: 70,
    nu: 1.1,
  });
  assert.equal(overridden.has("mode"), false);
  assert.equal(overridden.get("h"), "70.0");
  assert.equal(overridden.get("nu"), "1.100");
  assert.equal(overridden.has("rho"), false);
});

test("modelParamDefaults mirrors the calibrated season model", () => {
  const defaults = modelParamDefaults({
    davidson: { home_advantage: 83.26, nu: 0.8177, elo_scale: 400 },
    scoreline: {
      home_base: 1.45,
      away_base: 1.15,
      elo_slope: 0.0018,
      home_advantage: 83.26,
      rho: -0.05,
      max_goals: 10,
    },
  });
  assert.deepEqual(defaults, {
    homeAdvantage: 83.26,
    nu: 0.8177,
  });
});
