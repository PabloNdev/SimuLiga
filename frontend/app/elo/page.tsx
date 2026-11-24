import { EloSheet } from "@/components/EloSheet";

export const metadata = {
  title: "ELO · SimuLiga",
  description:
    "Rating Elo de cada equipo de LaLiga, su evolución desde 1500 y la verificación del cálculo de 2025/26.",
};

export default function EloPage() {
  return <EloSheet />;
}
