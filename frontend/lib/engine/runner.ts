import type { ChampionsProjectionPayload } from "@/lib/champions-types";
import type { SimulationProgress } from "@/lib/sim-config";
import type { ProjectionPayload } from "@/lib/types";
import {
  finalizeChampionsProjection,
  mergeChampionsChunks,
  simulateChampions,
  type ChampionsChunkOutput,
  type ChampionsSimConfig,
} from "./champions";
import {
  finalizeLaLigaProjection,
  mergeLaLigaChunks,
  simulateLaLiga,
  type LaLigaChunkOutput,
  type LaLigaSimConfig,
} from "./laliga";
import { deriveWorkerSeed } from "./math";
import type { WorkerRequest, WorkerResponse } from "./worker";

export interface RunOptions {
  signal?: AbortSignal;
  onProgress?: (progress: SimulationProgress) => void;
}

const MULTI_WORKER_THRESHOLD = 15_000;
let nextRequestId = 1;

function createAbortError(): DOMException {
  return new DOMException("Simulación cancelada", "AbortError");
}

function chooseWorkerCount(nSims: number): number {
  if (nSims < MULTI_WORKER_THRESHOLD) return 1;
  const cores =
    typeof navigator !== "undefined" &&
    typeof navigator.hardwareConcurrency === "number" &&
    navigator.hardwareConcurrency > 0
      ? navigator.hardwareConcurrency
      : 2;
  // Leave at least one thread free for smooth UI & mobile thermals; cap at 6.
  const maxWorkers = Math.max(1, Math.min(6, cores - 1));
  return Math.min(maxWorkers, Math.max(1, Math.floor(nSims / 5_000)));
}

function splitWork(total: number, parts: number): number[] {
  const base = Math.floor(total / parts);
  const remainder = total % parts;
  const sizes: number[] = [];
  for (let i = 0; i < parts; i++) {
    sizes.push(base + (i < remainder ? 1 : 0));
  }
  return sizes.filter((s) => s > 0);
}

function createWorker(): Worker {
  return new Worker(new URL("./worker.ts", import.meta.url), {
    type: "module",
  });
}

function runInWorkers<TChunk>(
  kind: "laliga" | "champions",
  config: LaLigaSimConfig | ChampionsSimConfig,
  totalSims: number,
  seed: number | null,
  options?: RunOptions,
): Promise<TChunk[]> {
  if (options?.signal?.aborted) {
    return Promise.reject(createAbortError());
  }

  const workerCount = chooseWorkerCount(totalSims);
  const chunkSizes = splitWork(totalSims, workerCount);
  const progressInterval = Math.max(
    500,
    Math.min(5_000, Math.floor(totalSims / 40)),
  );
  const started = performance.now();

  return new Promise<TChunk[]>((resolve, reject) => {
    const workers: Worker[] = [];
    const results: (TChunk | undefined)[] = new Array(chunkSizes.length);
    const completedByWorker = new Array<number>(chunkSizes.length).fill(0);
    let finishedCount = 0;
    let settled = false;
    let lastProgressReport = 0;

    const cleanup = () => {
      for (const worker of workers) {
        try {
          worker.terminate();
        } catch {
          // Ignore termination errors.
        }
      }
      if (options?.signal) {
        options.signal.removeEventListener("abort", handleAbort);
      }
    };

    const fail = (error: unknown) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };

    const handleAbort = () => {
      fail(createAbortError());
    };

    if (options?.signal) {
      options.signal.addEventListener("abort", handleAbort, { once: true });
    }

    const emitProgress = (force = false) => {
      if (!options?.onProgress || settled) return;
      const now = performance.now();
      if (!force && now - lastProgressReport < 60) return;
      lastProgressReport = now;
      let done = 0;
      for (let i = 0; i < completedByWorker.length; i++) {
        done += completedByWorker[i];
      }
      options.onProgress({
        completed: Math.min(totalSims, done),
        total: totalSims,
        progress: totalSims > 0 ? Math.min(1, done / totalSims) : 1,
        elapsedSeconds: (now - started) / 1000,
      });
    };

    try {
      for (let idx = 0; idx < chunkSizes.length; idx++) {
        const worker = createWorker();
        workers.push(worker);
        const reqId = nextRequestId++;
        const chunkSeed =
          chunkSizes.length === 1 ? seed : deriveWorkerSeed(seed, idx);

        worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
          const msg = event.data;
          if (!msg || msg.id !== reqId || settled) return;
          if (msg.type === "progress") {
            completedByWorker[idx] = msg.completed;
            emitProgress(false);
          } else if (msg.type === "done") {
            completedByWorker[idx] = chunkSizes[idx];
            results[idx] = msg.chunk as unknown as TChunk;
            finishedCount += 1;
            emitProgress(finishedCount === chunkSizes.length);
            if (finishedCount === chunkSizes.length) {
              settled = true;
              cleanup();
              resolve(results as TChunk[]);
            }
          } else if (msg.type === "error") {
            fail(new Error(msg.message));
          }
        };

        worker.onerror = (event: ErrorEvent) => {
          fail(
            new Error(
              event.message || "El trabajador de simulación falló inesperadamente.",
            ),
          );
        };

        const payload: WorkerRequest =
          kind === "laliga"
            ? {
                id: reqId,
                kind: "laliga",
                config: config as LaLigaSimConfig,
                chunkSims: chunkSizes[idx],
                chunkSeed,
                progressInterval,
              }
            : {
                id: reqId,
                kind: "champions",
                config: config as ChampionsSimConfig,
                chunkSims: chunkSizes[idx],
                chunkSeed,
                progressInterval,
              };
        worker.postMessage(payload);
      }
    } catch (caught) {
      fail(caught);
    }
  });
}

export async function runLaLigaInBrowser(
  config: LaLigaSimConfig,
  options?: RunOptions,
): Promise<ProjectionPayload> {
  if (options?.signal?.aborted) {
    throw createAbortError();
  }
  const started = performance.now();

  if (typeof Worker === "undefined") {
    return simulateLaLiga(config, (completed, total) => {
      options?.onProgress?.({
        completed,
        total,
        progress: total > 0 ? completed / total : 1,
        elapsedSeconds: (performance.now() - started) / 1000,
      });
    });
  }

  const chunks = await runInWorkers<LaLigaChunkOutput>(
    "laliga",
    config,
    config.nSims,
    config.seed,
    options,
  );
  const merged = chunks.length === 1 ? chunks[0] : mergeLaLigaChunks(chunks);
  const elapsedSeconds = (performance.now() - started) / 1000;
  return finalizeLaLigaProjection(config, merged, elapsedSeconds);
}

export async function runChampionsInBrowser(
  config: ChampionsSimConfig,
  options?: RunOptions,
): Promise<ChampionsProjectionPayload> {
  if (options?.signal?.aborted) {
    throw createAbortError();
  }
  const started = performance.now();

  if (typeof Worker === "undefined") {
    return simulateChampions(config, (completed, total) => {
      options?.onProgress?.({
        completed,
        total,
        progress: total > 0 ? completed / total : 1,
        elapsedSeconds: (performance.now() - started) / 1000,
      });
    });
  }

  const chunks = await runInWorkers<ChampionsChunkOutput>(
    "champions",
    config,
    config.nSims,
    config.seed,
    options,
  );
  const merged = chunks.length === 1 ? chunks[0] : mergeChampionsChunks(chunks);
  const elapsedSeconds = (performance.now() - started) / 1000;
  return finalizeChampionsProjection(config, merged, elapsedSeconds);
}
