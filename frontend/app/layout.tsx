import type { Metadata } from "next";
import { Archivo, Barlow_Condensed, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { Brand } from "@/components/Brand";
import { CompetitionSwitch } from "@/components/CompetitionSwitch";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";
import { ThemeToggle } from "@/components/ThemeToggle";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  display: "swap",
});

const barlow = Barlow_Condensed({
  variable: "--font-barlow",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "SimuLiga · LaLiga 2026/27",
  description:
    "Simulador visual de LaLiga: probabilidades de campeón, Top 4 y descenso, probabilidades 1X2 y escenarios interactivos.",
};

const themeScript = `(function(){try{var t=localStorage.getItem("simuliga-theme");var m=window.matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.dataset.theme=t||(m?"dark":"light");}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="es"
      className={`${archivo.variable} ${barlow.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <div className="shell">
          <header className="site-header">
            <div className="container">
              <Brand />
              <SiteNav />
              <CompetitionSwitch />
              <ThemeToggle />
            </div>
          </header>
          <main className="site-main">{children}</main>
          <SiteFooter />
        </div>
      </body>
    </html>
  );
}
