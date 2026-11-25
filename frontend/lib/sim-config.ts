/**
 * Shared simulation size defaults and presets for SimuLiga & SimuChampions.
 *
 * The default (5.000) is tuned for mobile visitors: fast (< 300 ms on phones),
 * low battery/memory footprint, and ~0.7 pp standard error on 50% odds.
 */

export const DEFAULT_SIMS = 5_000;
export const MIN_SIMS = 100;
export const LALIGA_MAX_SIMS = 1_000_000;
export const CHAMPIONS_MAX_SIMS_BROWSER = 250_000;
export const CHAMPIONS_MAX_SIMS_API = 100_000;
export const LALIGA_SYNC_API_LIMIT = 200_000;

export interface SimSizePreset {
  value: number;
  label: string;
  hint: string;
}

export const LALIGA_SIM_PRESETS: readonly SimSizePreset[] = [
  { value: 2_000, label: "2.000", hint: "ultra rápido" },
  { value: 5_000, label: "5.000", hint: "móvil · defecto" },
  { value: 10_000, label: "10.000", hint: "estándar" },
  { value: 25_000, label: "25.000", hint: "preciso" },
  { value: 50_000, label: "50.000", hint: "alta precisión" },
  { value: 100_000, label: "100.000", hint: "escritorio" },
  { value: 250_000, label: "250.000", hint: "intensivo" },
  { value: 1_000_000, label: "1.000.000", hint: "máxima precisión" },
] as const;

export const CHAMPIONS_SIM_PRESETS: readonly SimSizePreset[] = [
  { value: 2_000, label: "2.000", hint: "ultra rápido" },
  { value: 5_000, label: "5.000", hint: "móvil · defecto" },
  { value: 10_000, label: "10.000", hint: "estándar" },
  { value: 25_000, label: "25.000", hint: "preciso" },
  { value: 50_000, label: "50.000", hint: "alta precisión" },
  { value: 100_000, label: "100.000", hint: "escritorio" },
  { value: 250_000, label: "250.000", hint: "máxima precisión" },
] as const;

export function clampSimSize(value: number, maxSims: number): number {
  if (!Number.isFinite(value)) return DEFAULT_SIMS;
  return Math.max(MIN_SIMS, Math.min(maxSims, Math.round(value)));
}

export function formatSimCount(sims: number): string {
  if (sims >= 1_000_000 && sims % 1_000_000 === 0) {
    return `${sims / 1_000_000}M`;
  }
  if (sims >= 1_000 && sims % 1_000 === 0) {
    return `${sims / 1_000}k`;
  }
  return sims.toLocaleString("es-ES");
}

export interface SimulationProgress {
  completed: number;
  total: number;
  progress: number;
  elapsedSeconds: number;
}
