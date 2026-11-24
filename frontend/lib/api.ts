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
 * Con NEXT_PUBLIC_STATIC_DATA=1 la app no llama a la API: lee los JSON de
 * `public/data`, generados por `backend/scripts/export_frontend_snapshot.py`.
 * Es el modo que usa el despliegue estático en Cloudflare Pages.
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

function staticUnavailable(): Promise<never> {
  return Promise.reject(
    new ApiError(
      "Esta versión publicada muestra la última simulación: los escenarios necesitan el motor en marcha.",
      0,
    ),
  );
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
        detail = body.detail.map((item: { msg?: string }) => item.msg).join(", ");
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

export function getProjection(
  mode: Mode,
  sims: number,
  startMatchday?: number | null,
  signal?: AbortSignal,
): Promise<ProjectionPayload> {
  if (STATIC_DATA) {
    return staticPayload<ProjectionPayload>(`projection-${mode}.json`, signal);
  }
  const start =
    startMatchday != null ? `&start_matchday=${startMatchday}` : "";
  return request<ProjectionPayload>(
    `/api/projection?mode=${mode}&sims=${sims}&seed=42${start}`,
    undefined,
    signal,
  );
}

export function postScenario(
  payload: ScenarioRequest,
  signal?: AbortSignal,
): Promise<ProjectionPayload> {
  if (STATIC_DATA) return staticUnavailable();
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
  if (STATIC_DATA) return staticUnavailable();
  return request<JobCreated>(
    "/api/projection/full",
    { method: "POST", body: JSON.stringify(payload) },
    signal,
  );
}

export function getJob(jobId: string, signal?: AbortSignal): Promise<JobPayload> {
  if (STATIC_DATA) return staticUnavailable();
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
