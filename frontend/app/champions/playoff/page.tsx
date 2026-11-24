import { PlayoffForecast } from "@/components/champions/PlayoffForecast";

export const metadata = {
  title: "Playoff · SimuChampions",
  description:
    "Previsión del playoff de la Champions League: emparejamientos 9-24, probabilidad de avanzar y rivales más probables.",
};

export default function ChampionsPlayoffPage() {
  return <PlayoffForecast />;
}
