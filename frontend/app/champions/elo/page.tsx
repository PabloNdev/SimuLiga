import { ChampionsElo } from "@/components/champions/ChampionsElo";

export const metadata = {
  title: "ELO · SimuChampions",
  description:
    "Rating ELO de los 36 equipos de la Champions League, evolución y verificación del replay de 2025/26.",
};

export default function ChampionsEloPage() {
  return <ChampionsElo />;
}
