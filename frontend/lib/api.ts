import {
  buildEloByMatchday,
  matchItemsToEngineInput,
  modelParamsFromSeason,
  type LaLigaMatchInput,
} from "@/lib/engine/laliga";
import { runLaLigaInBrowser } from "@/lib/engine/runner";
import {
  clampSimSize,
  LALIGA_MAX_SIMS,
  type SimulationProgress,
} from "@/lib/sim-config";
import type {
  EloPayload,
  JobCreated,
  JobPayload,
  MatchesPayload,
  Mode,
  ProjectionPayload,
  ScenarioRequest,
  SeasonPayload,
  ValidationPayload,
} from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Con NEXT_PUBLIC_STATIC_DATA=1 la app lee los datos base de `public/data`
 * (generados por `backend/scripts/export_frontend_snapshot.py`) y ejecuta las
 * simulaciones Monte Carlo en el navegador mediante Web Workers.
 */
export const STATIC_DATA = process.env.NEXT_PUBLIC_STATIC_DATA === "1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function staticPayload<T>(
  file: string,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/data/${file}`, { signal, cache: "force-cache" });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(
      "No se pudieron cargar los datos publicados. Recarga la página.",
      0,
    );
  }
  if (!response.ok) {
    throw new ApiError(
      `Faltan los datos publicados (${file}). Regenera la instantánea desde el backend.`,
      response.status,
    );
  }
  return (await response.json()) as T;
}

interface LaLigaBrowserContext {
  season: SeasonPayload;
  matches: LaLigaMatchInput[];
  eloByMatchday: Record<number, Record<string, number>>;
}

let laligaContextPromise: Promise<LaLigaBrowserContext> | null = null;
const projectionCache = new Map<string, ProjectionPayload>();
const MAX_CACHE_ENTRIES = 12;

function getLaLigaBrowserContext(
  signal?: AbortSignal,
): Promise<LaLigaBrowserContext> {
  if (!laligaContextPromise) {
    laligaContextPromise = Promise.all([
      staticPayload<SeasonPayload>("season.json"),
      staticPayload<MatchesPayload>("matches-score.json"),
      staticPayload<EloPayload>("elo.json").catch(() => null),
    ])
      .then(([season, matchesPayload, eloPayload]) => {
        const matches = matchItemsToEngineInput(matchesPayload.matches);
        const eloByMatchday = buildEloByMatchday(season, matches, eloPayload);
        return { season, matches, eloByMatchday };
      })
      .catch((error) => {
        laligaContextPromise = null;
        throw error;
      });
  }
  if (!signal) return laligaContextPromise;
  if (signal.aborted) {
    return Promise.reject(new DOMException("Abortado", "AbortError"));
  }
  return new Promise<LaLigaBrowserContext>((resolve, reject) => {
    const onAbort = () => reject(new DOMException("Abortado", "AbortError"));
    signal.addEventListener("abort", onAbort, { once: true });
    laligaContextPromise!.then(
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

function cacheProjection(key: string, payload: ProjectionPayload): void {
  if (projectionCache.size >= MAX_CACHE_ENTRIES) {
    const oldest = projectionCache.keys().next().value;
    if (oldest !== undefined) projectionCache.delete(oldest);
  }
  projectionCache.set(key, payload);
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
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(
      "No se pudo conectar con el motor de simulación. Comprueba que el backend esté en marcha.",
      0,
    );
  }

  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body?.detail)) {
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

export function getSeason(signal?: AbortSignal): Promise<SeasonPayload> {
  if (STATIC_DATA) return staticPayload<SeasonPayload>("season.json", signal);
  return request<SeasonPayload>("/api/season", undefined, signal);
}

export async function getProjection(
  mode: Mode,
  sims: number,
  startMatchday?: number | null,
  signal?: AbortSignal,
  onProgress?: (progress: SimulationProgress) => void,
  seed = 42,
): Promise<ProjectionPayload> {
  if (STATIC_DATA) {
    const safeSims = clampSimSize(sims, LALIGA_MAX_SIMS);
    const context = await getLaLigaBrowserContext(signal);
    const effectiveStart =
      startMatchday != null ? startMatchday : context.season.current_matchday;
    const cacheKey = `${context.season.data_version}|${mode}|${safeSims}|${effectiveStart}|${seed}`;
    const cached = projectionCache.get(cacheKey);
    if (cached) {
      onProgress?.({
        completed: safeSims,
        total: safeSims,
        progress: 1,
        elapsedSeconds: 0,
      });
      return cached;
    }

    const { davidson, scoreline } = modelParamsFromSeason(context.season.model);
    const payload = await runLaLigaInBrowser(
      {
        teams: context.season.teams,
        matches: context.matches,
        mode,
        nSims: safeSims,
        seed,
        davidson,
        scoreline,
        startMatchday: effectiveStart,
        eloByMatchday: context.eloByMatchday,
        dataVersion: context.season.data_version,
        source: context.season.source,
      },
      { signal, onProgress },
    );
    cacheProjection(cacheKey, payload);
    return payload;
  }

  const start =
    startMatchday != null ? `&start_matchday=${startMatchday}` : "";
  return request<ProjectionPayload>(
    `/api/projection?mode=${mode}&sims=${sims}&seed=${seed}${start}`,
    undefined,
    signal,
  );
}

export async function postScenario(
  payload: ScenarioRequest,
  signal?: AbortSignal,
  onProgress?: (progress: SimulationProgress) => void,
): Promise<ProjectionPayload> {
  if (STATIC_DATA) {
    const safeSims = clampSimSize(payload.sims, LALIGA_MAX_SIMS);
    const context = await getLaLigaBrowserContext(signal);
    const { davidson, scoreline } = modelParamsFromSeason(
      context.season.model,
      {
        home_advantage: payload.home_advantage,
        nu: payload.nu,
        rho: payload.rho,
      },
    );
    return runLaLigaInBrowser(
      {
        teams: context.season.teams,
        matches: context.matches,
        mode: payload.mode,
        nSims: safeSims,
        seed: payload.seed ?? 42,
        davidson,
        scoreline,
        eloDelta: payload.elo_delta,
        forcedResults: payload.forced_results,
        forcedScores: payload.forced_scores,
        startMatchday:
          payload.start_matchday !== undefined
            ? payload.start_matchday
            : context.season.current_matchday,
        eloByMatchday: context.eloByMatchday,
        dataVersion: context.season.data_version,
        source: context.season.source,
      },
      { signal, onProgress },
    );
  }
  return request<ProjectionPayload>(
    "/api/projection",
    { method: "POST", body: JSON.stringify(payload) },
    signal,
  );
}

export function postFullProjection(
  payload: ScenarioRequest,
  signal?: AbortSignal,
): Promise<JobCreated> {
  return request<JobCreated>(
    "/api/projection/full",
    { method: "POST", body: JSON.stringify(payload) },
    signal,
  );
}

export function getJob(jobId: string, signal?: AbortSignal): Promise<JobPayload> {
  return request<JobPayload>(`/api/jobs/${jobId}`, undefined, signal);
}

export function getMatches(
  mode: Mode,
  signal?: AbortSignal,
): Promise<MatchesPayload> {
  if (STATIC_DATA) {
    return staticPayload<MatchesPayload>(`matches-${mode}.json`, signal);
  }
  return request<MatchesPayload>(`/api/matches?mode=${mode}`, undefined, signal);
}

export function getValidation(signal?: AbortSignal): Promise<ValidationPayload> {
  if (STATIC_DATA) {
    return staticPayload<ValidationPayload>("validation.json", signal);
  }
  return request<ValidationPayload>("/api/validation", undefined, signal);
}

export function getElo(signal?: AbortSignal): Promise<EloPayload> {
  if (STATIC_DATA) return staticPayload<EloPayload>("elo.json", signal);
  return request<EloPayload>("/api/elo", undefined, signal);
}
