"use client";

import { useState, type FormEvent } from "react";
import {
  clampSimSize,
  MIN_SIMS,
  type SimSizePreset,
  type SimulationProgress,
} from "@/lib/sim-config";

const CUSTOM_OPTION = "__custom__";

export interface SimSizeControlProps {
  value: number;
  presets: readonly SimSizePreset[];
  maxSims: number;
  onChange: (nextSims: number) => void;
  disabled?: boolean;
  variant?: "toolbar" | "panel";
  id?: string;
}

export function SimSizeControl({
  value,
  presets,
  maxSims,
  onChange,
  disabled = false,
  variant = "toolbar",
  id = "sim-size",
}: SimSizeControlProps) {
  const availablePresets = presets.filter((preset) => preset.value <= maxSims);
  const isPreset = availablePresets.some((preset) => preset.value === value);
  const [customOpen, setCustomOpen] = useState(!isPreset);
  const [draft, setDraft] = useState(() => String(value));

  const showCustomInput = customOpen || !isPreset;
  const selectValue = showCustomInput ? CUSTOM_OPTION : String(value);

  function handleSelectChange(raw: string) {
    if (raw === CUSTOM_OPTION) {
      setCustomOpen(true);
      setDraft(String(value));
      return;
    }
    const parsed = Number(raw);
    if (Number.isFinite(parsed)) {
      setCustomOpen(false);
      setDraft(String(parsed));
      onChange(clampSimSize(parsed, maxSims));
    }
  }

  function applyCustom(event: FormEvent) {
    event.preventDefault();
    const cleaned = draft.replace(/[.\s,_]/g, "");
    const parsed = Number(cleaned);
    if (!Number.isFinite(parsed)) return;
    const clamped = clampSimSize(parsed, maxSims);
    setDraft(String(clamped));
    if (availablePresets.some((preset) => preset.value === clamped)) {
      setCustomOpen(false);
    }
    onChange(clamped);
  }

  const selectClass =
    variant === "panel" ? "control-select" : "matchday-select";

  return (
    <div
      className={
        variant === "panel" ? "sim-size-panel" : "sim-size-toolbar"
      }
    >
      <select
        id={id}
        className={selectClass}
        value={selectValue}
        disabled={disabled}
        onChange={(event) => handleSelectChange(event.target.value)}
        aria-label="Tamaño de la simulación"
        title={`Número de temporadas simuladas (entre ${MIN_SIMS.toLocaleString("es-ES")} y ${maxSims.toLocaleString("es-ES")}).`}
      >
        {availablePresets.map((preset) => (
          <option key={preset.value} value={preset.value}>
            {preset.label} · {preset.hint}
          </option>
        ))}
        <option value={CUSTOM_OPTION}>
          Personalizado{!isPreset ? ` (${value.toLocaleString("es-ES")})` : "…"}
        </option>
      </select>

      {showCustomInput ? (
        <form className="sim-custom-form" onSubmit={applyCustom}>
          <input
            type="number"
            inputMode="numeric"
            className="sim-custom-input"
            min={MIN_SIMS}
            max={maxSims}
            step={100}
            value={draft}
            disabled={disabled}
            onChange={(event) => setDraft(event.target.value)}
            aria-label="Número personalizado de simulaciones"
            placeholder={String(value)}
          />
          <button
            type="submit"
            className="btn sim-custom-apply"
            disabled={disabled}
          >
            Aplicar
          </button>
        </form>
      ) : null}
    </div>
  );
}

export interface SimulationProgressNoticeProps {
  title?: string;
  message: string;
  progress: SimulationProgress | null;
  running: boolean;
  onCancel?: () => void;
}

export function SimulationProgressNotice({
  title,
  message,
  progress,
  running,
  onCancel,
}: SimulationProgressNoticeProps) {
  return (
    <div
      className="notice"
      style={{ marginBottom: 18 }}
      role="status"
      aria-live="polite"
    >
      <strong>{title ?? (running ? "Simulando." : "Simulación.")}</strong>
      <span>{message}</span>
      {running && onCancel ? (
        <button
          type="button"
          className="btn btn-danger sim-cancel-btn"
          onClick={onCancel}
        >
          Cancelar
        </button>
      ) : null}
      {running && progress ? (
        <div style={{ flexBasis: "100%", display: "grid", gap: 6 }}>
          <div className="bar" style={{ height: 8 }}>
            <div
              className="bar-fill accent"
              style={{ width: `${Math.max(2, progress.progress * 100)}%` }}
            />
          </div>
          <span className="muted" style={{ fontSize: 11 }}>
            {Math.round(progress.progress * 100)}% ·{" "}
            {progress.completed.toLocaleString("es-ES")} /{" "}
            {progress.total.toLocaleString("es-ES")}
            {progress.progress > 0.04 && progress.elapsedSeconds > 0.2
              ? ` · quedan ~${Math.max(
                  1,
                  Math.round(
                    progress.elapsedSeconds / progress.progress -
                      progress.elapsedSeconds,
                  ),
                )} s`
              : ""}
          </span>
        </div>
      ) : null}
    </div>
  );
}
