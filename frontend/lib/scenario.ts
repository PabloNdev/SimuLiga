import type { Mode, ModelInfo, Outcome } from "@/lib/types";

export interface ScenarioState {
  mode: Mode;
  elo: Record<string, number>;
  forced: Record<string, Outcome>;
  homeAdvantage: number | null;
  nu: number | null;
  rho: number | null;
  sims: number;
  startMatchday: number;
}

export const DEFAULT_SCENARIO: ScenarioState = {
  mode: "score",
  elo: {},
  forced: {},
  homeAdvantage: null,
  nu: null,
  rho: null,
  sims: 10_000,
  startMatchday: 10,
};

export interface ScenarioModelDefaults {
  homeAdvantage: number;
  nu: number;
  rho: number;
}

export function modelParamDefaults(model: ModelInfo): ScenarioModelDefaults {
  return {
    homeAdvantage: model.davidson.home_advantage,
    nu: model.davidson.nu,
    rho: model.scoreline.rho,
  };
}

export function parseScenario(params: URLSearchParams): ScenarioState {
  const mode = params.get("mode") === "1x2" ? "1x2" : "score";
  const elo: Record<string, number> = {};
  const forced: Record<string, Outcome> = {};

  for (const entry of params.get("elo")?.split(",") ?? []) {
    const separator = entry.indexOf(":");
    if (separator < 1) continue;
    const team = entry.slice(0, separator);
    const value = Number(entry.slice(separator + 1));
    if (Number.isFinite(value) && value !== 0) {
      elo[team] = Math.max(-300, Math.min(300, value));
    }
  }

  for (const entry of params.get("forced")?.split(",") ?? []) {
    const separator = entry.indexOf(":");
    if (separator < 1) continue;
    const match = entry.slice(0, separator);
    const outcome = entry.slice(separator + 1);
    if (outcome === "H" || outcome === "D" || outcome === "A") {
      forced[match] = outcome;
    }
  }

  const numberOrDefault = (key: string, fallback: number) => {
    const raw = params.get(key);
    const value = raw === null ? Number.NaN : Number(raw);
    return Number.isFinite(value) ? value : fallback;
  };

  const numberOrNull = (key: string) => {
    const raw = params.get(key);
    if (raw === null) return null;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  };

  return {
    mode,
    elo,
    forced,
    homeAdvantage: numberOrNull("h"),
    nu: numberOrNull("nu"),
    rho: numberOrNull("rho"),
    sims: numberOrDefault("sims", DEFAULT_SCENARIO.sims),
    startMatchday: Math.max(
      1,
      Math.min(38, Math.round(numberOrDefault("start", DEFAULT_SCENARIO.startMatchday))),
    ),
  };
}

export function buildScenarioParams(state: ScenarioState): URLSearchParams {
  const params = new URLSearchParams();
  params.set("mode", state.mode);

  const elo = Object.entries(state.elo)
    .filter(([, value]) => Math.abs(value) >= 1)
    .map(([team, value]) => `${team}:${Math.round(value)}`)
    .join(",");
  if (elo) params.set("elo", elo);

  const forced = Object.entries(state.forced)
    .map(([match, outcome]) => `${match}:${outcome}`)
    .join(",");
  if (forced) params.set("forced", forced);

  if (state.homeAdvantage !== null) {
    params.set("h", state.homeAdvantage.toFixed(1));
  }
  if (state.nu !== null) {
    params.set("nu", state.nu.toFixed(3));
  }
  if (state.rho !== null) {
    params.set("rho", state.rho.toFixed(3));
  }
  if (state.sims !== DEFAULT_SCENARIO.sims) {
    params.set("sims", String(state.sims));
  }
  params.set("start", String(state.startMatchday));
  return params;
}
