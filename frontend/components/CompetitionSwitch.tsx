"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function CompetitionSwitch() {
  const pathname = usePathname();
  const champions = pathname.startsWith("/champions");
  return (
    <div className="competition-switch" role="group" aria-label="Competición">
      <Link
        href="/"
        className={champions ? "" : "is-on"}
        aria-current={champions ? undefined : "page"}
      >
        LaLiga
      </Link>
      <Link
        href="/champions"
        className={champions ? "is-on" : ""}
        aria-current={champions ? "page" : undefined}
      >
        Champions
      </Link>
    </div>
  );
}
