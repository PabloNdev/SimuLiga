"use client";

import { useEffect, useState } from "react";
import { getValidation } from "@/lib/api";
import type { ValidationPayload } from "@/lib/types";
import { formatProbability } from "@/lib/format";
import { InfoTip } from "@/components/InfoTip";

export function ValidationPanel() {
  const [data, setData] = useState<ValidationPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getValidation(controller.signal)
      .then((payload) => {
        setData(payload);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught.message : "Error inesperado");
        setLoading(false);
      });
    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <section className="panel">
        <div className="panel-body">
          <div className="skeleton skeleton-line short" />
          <div className="skeleton skeleton-line" />
          <div className="skeleton skeleton-line" />
        </div>
      </section>
    );
  }

  const metrics = data?.metrics;
  if (error || !metrics) {
    return (
      <section className="panel">
        <div className="panel-body">
          <span className="kicker">Validación</span>
          <p className="lead">
            {error ?? data?.message ?? "Todavía no hay métricas de validación."}
          </p>
        </div>
      </section>
    );
  }

  const trainedOn = data?.calibration?.trained_on?.join(", ") ?? "2022–2023";
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Validación del modelo</h2>
          <span className="panel-note">
            Entrenado con {trainedOn} y probado en {metrics.season} ·{" "}
            {metrics.matches} partidos.
          </span>
        </div>
        <span className="chip chip-accent">Datos reales</span>
      </div>
      <div className="panel-body">
        <div className="summary-grid">
          <div className="summary-card">
            <span>
              Accuracy <InfoTip text="Porcentaje de partidos en los que el resultado más probable coincide con el real." />
            </span>
            <strong>{formatProbability(metrics.accuracy)}</strong>
            <small>aciertos del favorito</small>
          </div>
          <div className="summary-card">
            <span>
              Log-loss <InfoTip text="Penaliza las probabilidades mal calibradas. Más bajo es mejor; la referencia aleatoria ronda 1,10." />
            </span>
            <strong>{metrics.log_loss.toFixed(3)}</strong>
            <small>más bajo, mejor</small>
          </div>
          <div className="summary-card">
            <span>
              Brier <InfoTip text="Error cuadrático medio de las tres probabilidades. Más bajo es mejor." />
            </span>
            <strong>{metrics.brier.toFixed(3)}</strong>
            <small>error probabilístico</small>
          </div>
        </div>
        <p className="control-hint" style={{ marginTop: 14, marginBottom: 0 }}>
          El modelo estima <code>H = {metrics.home_advantage.toFixed(1)}</code> y{" "}
          <code>ν = {metrics.nu.toFixed(2)}</code> con máxima verosimilitud. La
          accuracy premia acertar el signo; log-loss y Brier premian además que
          las probabilidades sean honestas.
        </p>
      </div>
    </section>
  );
}
