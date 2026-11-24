import { ChampionsDashboard } from "@/components/champions/ChampionsDashboard";

export const metadata = {
  title: "SimuChampions · Champions League",
  description:
    "Simulador de la fase de liga de la Champions League: probabilidades de top 8, playoff, eliminación y octavos.",
};

export default function ChampionsPage() {
  return <ChampionsDashboard />;
}
