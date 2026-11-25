/// <reference lib="webworker" />

import {
  runChampionsChunk,
  type ChampionsChunkOutput,
  type ChampionsSimConfig,
} from "./champions";
import {
  runLaLigaChunk,
  type LaLigaChunkOutput,
  type LaLigaSimConfig,
} from "./laliga";

export type WorkerRequest =
  | {
      id: number;
      kind: "laliga";
      config: LaLigaSimConfig;
      chunkSims: number;
      chunkSeed: number | null;
      progressInterval: number;
    }
  | {
      id: number;
      kind: "champions";
      config: ChampionsSimConfig;
      chunkSims: number;
      chunkSeed: number | null;
      progressInterval: number;
    };

export type WorkerResponse =
  | {
      id: number;
      type: "progress";
      completed: number;
      total: number;
    }
  | {
      id: number;
      type: "done";
      kind: "laliga";
      chunk: LaLigaChunkOutput;
    }
  | {
      id: number;
      type: "done";
      kind: "champions";
      chunk: ChampionsChunkOutput;
    }
  | {
      id: number;
      type: "error";
      message: string;
    };

const ctx: DedicatedWorkerGlobalScope =
  self as unknown as DedicatedWorkerGlobalScope;

ctx.onmessage = (event: MessageEvent<WorkerRequest>) => {
  const msg = event.data;
  try {
    if (msg.kind === "laliga") {
      const chunk = runLaLigaChunk(
        msg.config,
        msg.chunkSims,
        msg.chunkSeed,
        (completed, total) => {
          ctx.postMessage({
            id: msg.id,
            type: "progress",
            completed,
            total,
          } satisfies WorkerResponse);
        },
        msg.progressInterval,
      );
      ctx.postMessage(
        { id: msg.id, type: "done", kind: "laliga", chunk } satisfies WorkerResponse,
        [
          chunk.positionHistogram.buffer,
          chunk.pointsHistogram.buffer,
          chunk.pointsSum.buffer,
          chunk.pointsSquaredSum.buffer,
        ],
      );
    } else {
      const chunk = runChampionsChunk(
        msg.config,
        msg.chunkSims,
        msg.chunkSeed,
        (completed, total) => {
          ctx.postMessage({
            id: msg.id,
            type: "progress",
            completed,
            total,
          } satisfies WorkerResponse);
        },
        msg.progressInterval,
      );
      ctx.postMessage(
        {
          id: msg.id,
          type: "done",
          kind: "champions",
          chunk,
        } satisfies WorkerResponse,
        [
          chunk.positionHistogram.buffer,
          chunk.pointsHistogram.buffer,
          chunk.pointsSum.buffer,
          chunk.pointsSquaredSum.buffer,
          chunk.advanceCounts.buffer,
          chunk.opponentCounts.buffer,
          chunk.pairCounts.buffer,
          chunk.slotCounts.buffer,
        ],
      );
    }
  } catch (caught) {
    ctx.postMessage({
      id: msg.id,
      type: "error",
      message:
        caught instanceof Error ? caught.message : "Error en la simulación",
    } satisfies WorkerResponse);
  }
};
