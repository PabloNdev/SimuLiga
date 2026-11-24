import Link from "next/link";
import { Suspense } from "react";
import { ScenarioLab } from "@/components/ScenarioLab";
import { LoadingState } from "@/components/States";

const STATIC_DATA = process.env.NEXT_PUBLIC_STATIC_DATA === "1";

export default function ScenarioPage() {
  if (STATIC_DATA) {
    return (
      <div className="container">
        <div className="page-head">
          <div>
            <span className="kicker">Laboratorio de escenarios</span>
            <h1 className="page-title">Los escenarios necesitan el motor.</h1>
            <p className="page-sub">
              Esta versión publicada es estática: muestra la última simulación
              guardada, sin backend detrás.
            </p>
          </div>
        </div>
        <div className="notice" style={{ marginBottom: 18 }}>
          <strong>Modo publicado.</strong>
          <span>
            Para mover el Elo de un equipo, forzar resultados o lanzar un millón
            de temporadas hace falta el motor de simulación en marcha. Mientras
            tanto, el panel y la tabla muestran los datos de la última
            simulación publicada.
          </span>
        </div>
        <Link href="/" className="btn btn-primary">
          Volver al panel
        </Link>
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="container">
          <LoadingState
            title="Preparando el laboratorio"
            note="Leyendo el escenario y cargando la temporada."
          />
        </div>
      }
    >
      <ScenarioLab />
    </Suspense>
  );
}
