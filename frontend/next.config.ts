import type { NextConfig } from "next";

// Cloudflare Pages sirve solo estáticos. Con STATIC_EXPORT=1 el build genera
// `out/` (export estático) y desactiva las funciones que requieren servidor
// (PPR y Cache Components fallan en modo export). En local no se define y el
// comportamiento de desarrollo sigue igual.
const staticExport = process.env.STATIC_EXPORT === "1";

const nextConfig: NextConfig = {
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
