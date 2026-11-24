"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Brand() {
  const pathname = usePathname();
  const champions = pathname.startsWith("/champions");
  return (
    <Link
      href={champions ? "/champions" : "/"}
      className="brand"
      aria-label={champions ? "SimuChampions, inicio" : "SimuLiga, inicio"}
    >
      <span className="brand-mark" aria-hidden="true">
        S
      </span>
      <span className="brand-word">
        Simu<span>{champions ? "Champions" : "Liga"}</span>
      </span>
      <span className="brand-season">
        {champions ? "Champions 2026/27" : "LaLiga 2026/27"}
      </span>
    </Link>
  );
}
