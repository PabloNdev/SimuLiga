import type { NextConfig } from "next";

// Cloudflare Pages sirve solo estáticos. Con STATIC_EXPORT=1 el build genera
// `out/` (export estático) y desactiva las funciones que requieren servidor
// (PPR y Cache Components fallan en modo export). En local no se define y el
// comportamiento de desarrollo sigue igual.
const staticExport = process.env.STATIC_EXPORT === "1";

// El export estático da por defecto datos publicados (JSON en public/data), para
// que el sitio funcione sin backend. Con NEXT_PUBLIC_STATIC_DATA=0 se vuelve a
// llamar a la API de NEXT_PUBLIC_API_URL.
const staticData =
  process.env.NEXT_PUBLIC_STATIC_DATA === "1" ||
  (staticExport && process.env.NEXT_PUBLIC_STATIC_DATA !== "0");

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_STATIC_DATA: staticData ? "1" : "0",
  },
  ...(staticExport
    ? {
        output: "export" as const,
        images: { unoptimized: true },
      }
    : {}),
  cacheComponents: !staticExport,
  partialPrefetching: !staticExport,
};

export default nextConfig;
