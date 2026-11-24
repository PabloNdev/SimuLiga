import type { NextConfig } from "next";

// El sitio se publica como export estático en Cloudflare Workers (assets).
// `next build` lo activa solo; con STATIC_EXPORT=0 se puede desactivar y con
// STATIC_EXPORT=1 forzarlo también en otros entornos. En `next dev` no se
// aplica, así que el desarrollo sigue igual.
const staticExport =
  process.env.STATIC_EXPORT === "1" ||
  (process.env.STATIC_EXPORT !== "0" && process.env.NODE_ENV === "production");

// El export estático sirve por defecto los JSON publicados de public/data para
// funcionar sin backend. Con NEXT_PUBLIC_STATIC_DATA=0 vuelve a llamar a la API
// de NEXT_PUBLIC_API_URL.
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
