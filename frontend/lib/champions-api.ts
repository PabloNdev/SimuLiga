import { ApiError } from "@/lib/api";
import type {
  ChampionsEloPayload,
  ChampionsMatchesPayload,
  ChampionsProjectionPayload,
  ChampionsSeasonPayload,
  ChampionsValidationPayload,
} from "@/lib/champions-types";
import type { Mode } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
        detail = body.detail.map((item: { msg?: string }) => item.msg).join(", ");
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
  return request<ChampionsSeasonPayload>("/api/champions/season", undefined, signal);
}

export function getChampionsProjection(
  sims = 10_000,
  mode: Mode = "score",
  signal?: AbortSignal,
): Promise<ChampionsProjectionPayload> {
  return request<ChampionsProjectionPayload>(
    `/api/champions/projection?mode=${mode}&sims=${sims}&seed=42`,
    undefined,
    signal,
  );
}

export function getChampionsMatches(
  mode: Mode = "score",
  signal?: AbortSignal,
): Promise<ChampionsMatchesPayload> {
  return request<ChampionsMatchesPayload>(
    `/api/champions/matches?mode=${mode}`,
    undefined,
    signal,
  );
}

export function getChampionsElo(
  signal?: AbortSignal,
): Promise<ChampionsEloPayload> {
  return request<ChampionsEloPayload>("/api/champions/elo", undefined, signal);
}

export function getChampionsValidation(
  signal?: AbortSignal,
): Promise<ChampionsValidationPayload> {
  return request<ChampionsValidationPayload>(
    "/api/champions/validation",
    undefined,
    signal,
  );
}
