"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const laligaLinks = [
  { href: "/", label: "Panel" },
  { href: "/escenario", label: "Escenarios" },
  { href: "/metodologia", label: "Método" },
  { href: "/elo", label: "ELO" },
];

const championsLinks = [
  { href: "/champions", label: "Panel" },
  { href: "/champions/playoff", label: "Playoff" },
  { href: "/champions/elo", label: "ELO" },
  { href: "/champions/metodologia", label: "Método" },
];

export function SiteNav() {
  const pathname = usePathname();
  const links = pathname.startsWith("/champions") ? championsLinks : laligaLinks;
  return (
    <nav className="site-nav" aria-label="Navegación principal">
      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          aria-current={pathname === link.href ? "page" : undefined}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
