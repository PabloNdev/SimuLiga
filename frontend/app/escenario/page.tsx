import { Suspense } from "react";
import { ScenarioLab } from "@/components/ScenarioLab";
import { LoadingState } from "@/components/States";

export default function ScenarioPage() {
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
