"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function SiteFooter() {
  const pathname = usePathname();
  const champions = pathname.startsWith("/champions");
  return (
    <footer className="site-footer">
      <div className="container">
        <span>
          <strong>{champions ? "SimuChampions" : "SimuLiga"}</strong> ·{" "}
          {champions ? "Champions League 2026/27" : "LaLiga 2026/27"} ·
          Estimaciones, no certezas.
        </span>
        <span className="footer-long">
          {champions
            ? "Elo + ClubElo + Davidson · API-Football + OpenFootball"
            : "Elo propio + Davidson · OpenFootball + football-data.co.uk"}
        </span>
        <Link
          href={champions ? "/champions/metodologia" : "/metodologia"}
          className="link-arrow"
        >
          Cómo se calcula
        </Link>
      </div>
    </footer>
  );
}
