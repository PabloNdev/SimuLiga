import { ApiError, STATIC_DATA, staticPayload } from "@/lib/api";
import {
  championsMatchItemsToInput,
  type ChampionsMatchInput,
} from "@/lib/engine/champions";
import { runChampionsInBrowser } from "@/lib/engine/runner";
import {
  CHAMPIONS_MAX_SIMS_BROWSER,
  clampSimSize,
  DEFAULT_SIMS,
  type SimulationProgress,
} from "@/lib/sim-config";
import type {
  ChampionsEloPayload,
  ChampionsMatchesPayload,
  ChampionsProjectionPayload,
  ChampionsSeasonPayload,
  ChampionsValidationPayload,
} from "@/lib/champions-types";
import type { Mode } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ChampionsBrowserContext {
  season: ChampionsSeasonPayload;
  matches: ChampionsMatchInput[];
}

let championsContextPromise: Promise<ChampionsBrowserContext> | null = null;
const championsProjectionCache = new Map<string, ChampionsProjectionPayload>();
const MAX_CACHE_ENTRIES = 12;

function getChampionsBrowserContext(
  signal?: AbortSignal,
): Promise<ChampionsBrowserContext> {
  if (!championsContextPromise) {
    championsContextPromise = Promise.all([
      staticPayload<ChampionsSeasonPayload>("champions-season.json"),
      staticPayload<ChampionsMatchesPayload>("champions-matches-1x2.json"),
    ])
      .then(([season, matchesPayload]) => ({
        season,
        matches: championsMatchItemsToInput(matchesPayload.matches),
      }))
      .catch((error) => {
        championsContextPromise = null;
        throw error;
      });
  }
  if (!signal) return championsContextPromise;
  if (signal.aborted) {
    return Promise.reject(new DOMException("Abortado", "AbortError"));
  }
  return new Promise<ChampionsBrowserContext>((resolve, reject) => {
    const onAbort = () => reject(new DOMException("Abortado", "AbortError"));
    signal.addEventListener("abort", onAbort, { once: true });
    championsContextPromise!.then(
      (ctx) => {
        signal.removeEventListener("abort", onAbort);
        resolve(ctx);
      },
      (err) => {
        signal.removeEventListener("abort", onAbort);
        reject(err);
      },
    );
  });
}

function cacheChampionsProjection(
  key: string,
  payload: ChampionsProjectionPayload,
): void {
  if (championsProjectionCache.size >= MAX_CACHE_ENTRIES) {
    const oldest = championsProjectionCache.keys().next().value;
    if (oldest !== undefined) championsProjectionCache.delete(oldest);
  }
  championsProjectionCache.set(key, payload);
}

async function request<T>(
  path: string,
  init?: RequestInit,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      signal,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      "No se pudo conectar con el motor de SimuChampions. Comprueba que el backend está en marcha.",
      0,
    );
  }

  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) {
        detail = body.detail
          .map((item: { msg?: string }) => item.msg)
          .join(", ");
      }
    } catch {
      // Keep the generic status message.
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export function getChampionsSeason(
  signal?: AbortSignal,
): Promise<ChampionsSeasonPayload> {
  if (STATIC_DATA) {
    return staticPayload<ChampionsSeasonPayload>("champions-season.json", signal);
  }
  return request<ChampionsSeasonPayload>("/api/champions/season", undefined, signal);
}

export async function getChampionsProjection(
  sims = DEFAULT_SIMS,
  mode: Mode = "1x2",
  signal?: AbortSignal,
  onProgress?: (progress: SimulationProgress) => void,
  seed = 42,
): Promise<ChampionsProjectionPayload> {
  if (STATIC_DATA) {
    const safeSims = clampSimSize(sims, CHAMPIONS_MAX_SIMS_BROWSER);
    const context = await getChampionsBrowserContext(signal);
    const cacheKey = `${context.season.data_version}|${mode}|${safeSims}|${seed}`;
    const cached = championsProjectionCache.get(cacheKey);
    if (cached) {
      onProgress?.({
        completed: safeSims,
        total: safeSims,
        progress: 1,
        elapsedSeconds: 0,
      });
      return cached;
    }

    const payload = await runChampionsInBrowser(
      {
        teams: context.season.teams,
        matches: context.matches,
        baseStandings: context.season.standings,
        mode,
        nSims: safeSims,
        seed,
        davidson: context.season.model.davidson,
        scoreline: context.season.model.scoreline,
        dataVersion: context.season.data_version,
        source: context.season.source,
        demo: context.season.demo,
        fallback: context.season.fallback,
        dataNote: context.season.data_note,
      },
      { signal, onProgress },
    );
    cacheChampionsProjection(cacheKey, payload);
    return payload;
  }

  return request<ChampionsProjectionPayload>(
    `/api/champions/projection?mode=${mode}&sims=${sims}&seed=${seed}`,
    undefined,
    signal,
  );
}

export function getChampionsMatches(
  mode: Mode = "1x2",
  signal?: AbortSignal,
): Promise<ChampionsMatchesPayload> {
  if (STATIC_DATA) {
    return staticPayload<ChampionsMatchesPayload>(
      `champions-matches-${mode}.json`,
      signal,
    );
  }
  return request<ChampionsMatchesPayload>(
    `/api/champions/matches?mode=${mode}`,
    undefined,
    signal,
  );
}

export function getChampionsElo(
  signal?: AbortSignal,
): Promise<ChampionsEloPayload> {
  if (STATIC_DATA) {
    return staticPayload<ChampionsEloPayload>("champions-elo.json", signal);
  }
  return request<ChampionsEloPayload>("/api/champions/elo", undefined, signal);
}

export function getChampionsValidation(
  signal?: AbortSignal,
): Promise<ChampionsValidationPayload> {
  if (STATIC_DATA) {
    return staticPayload<ChampionsValidationPayload>(
      "champions-validation.json",
      signal,
    );
  }
  return request<ChampionsValidationPayload>(
    "/api/champions/validation",
    undefined,
    signal,
  );
}
