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

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
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
  return request<SeasonPayload>("/api/season", undefined, signal);
}

export function getProjection(
  mode: Mode,
  sims: number,
  startMatchday?: number | null,
  signal?: AbortSignal,
): Promise<ProjectionPayload> {
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
  return request<MatchesPayload>(`/api/matches?mode=${mode}`, undefined, signal);
}

export function getValidation(signal?: AbortSignal): Promise<ValidationPayload> {
  return request<ValidationPayload>("/api/validation", undefined, signal);
}

export function getElo(signal?: AbortSignal): Promise<EloPayload> {
  return request<EloPayload>("/api/elo", undefined, signal);
}
