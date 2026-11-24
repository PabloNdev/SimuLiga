# Desplegar el frontend en Cloudflare Pages

SimuLiga se despliega en dos piezas:

| Pieza | Dónde | Qué hace |
| --- | --- | --- |
| `frontend/` | Cloudflare Pages | Sirve la interfaz estática (Next.js con `output: "export"`) |
| `backend/` | Un host con Python | FastAPI + NumPy/SciPy, con las simulaciones Monte Carlo |

Cloudflare Pages **solo sirve archivos estáticos**: no puede ejecutar el backend
ni el optimizador de imágenes de Next.js. La app ya funciona entera en el
cliente (no hay `fetch` en servidor, rutas API ni middleware), así que el export
estático es suficiente.

## 1. Publica primero el backend

La URL del backend debe ser pública y con HTTPS. En el `.env` del servidor añade
el dominio de Pages a los orígenes permitidos por CORS:

```bash
CORS_ALLOW_ORIGINS=http://localhost:3000,https://<proyecto>.pages.dev,https://tu-dominio.com
```

Sin ese paso el navegador bloquea las llamadas y la app muestra el aviso de
"no se pudo conectar con el motor de simulación". Opciones habituales para el
backend: Fly.io, Render, Railway, un VPS con Docker o cualquier host que admita
Python 3.12 y unas cuantas CPU para las simulaciones.

## 2. Crea el proyecto en Cloudflare Pages

En el panel de Cloudflare: **Workers & Pages → Create → Pages → Connect to Git**
y selecciona el repositorio. Configuración:

| Ajuste | Valor |
| --- | --- |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Build output directory | `out` |
| Environment variable | `STATIC_EXPORT=1` |
| Environment variable | `NEXT_PUBLIC_API_URL=https://tu-api.ejemplo.com` |
| Environment variable | `NODE_VERSION=22` |

`STATIC_EXPORT=1` es lo que activa el modo estático en
[`frontend/next.config.ts`](../frontend/next.config.ts): genera `out/`, marca las
imágenes como no optimizadas y desactiva `partialPrefetching` y
`cacheComponents`, porque la generación anticipada parcial (PPR) no existe en
modo export. Sin esa variable, el build local sigue comportándose como siempre.

`NEXT_PUBLIC_API_URL` se incrusta en el bundle **en tiempo de build**: si cambia
la URL del backend, hay que volver a desplegar. Añádela también en el entorno
de *Preview* si quieres que las ramas de prueba funcionen.

## 3. Comprueba el build en local

```powershell
cd frontend
$env:STATIC_EXPORT="1"; npm run build
```

```bash
cd frontend
STATIC_EXPORT=1 npm run build
```

El resultado queda en `frontend/out/` (ignorado por git). Para revisarlo:

```bash
npx serve out
```

Rutas generadas: `/`, `/elo`, `/escenario`, `/metodologia`, `/champions`,
`/champions/elo`, `/champions/metodologia`, `/champions/playoff` y `404.html`.
Cloudflare Pages resuelve `/elo` a `elo.html` automáticamente; no hace falta
`trailingSlash` ni `_redirects`.

## 4. Despliegue manual con Wrangler (opcional)

Si prefieres no conectar el repositorio:

```bash
cd frontend
STATIC_EXPORT=1 npm run build
npx wrangler pages deploy out --project-name simuliga
```

Wrangler pedirá iniciar sesión la primera vez. El *project name* define el
subdominio: `<project-name>.pages.dev`.

## 5. Dominio propio

En **Pages → tu proyecto → Custom domains** añade el dominio y crea el CNAME que
indique Cloudflare. Después actualiza `CORS_ALLOW_ORIGINS` en el backend para
incluir el dominio nuevo (el de `pages.dev` puede quedarse mientras lo uses).

## 6. Detalles del despliegue

- `frontend/public/_headers` añade caché inmutable de un año para
  `/_next/static/*`, cuyos nombres ya llevan hash.
- Las fuentes de `next/font/google` se descargan durante el build, así que el
  entorno de Pages necesita red (la tiene).
- Cada push a `main` reconstruye y publica; las ramas y pull requests generan
  despliegues de previsualización.
- No hay variables secretas en el frontend: todo lo que empieza por
  `NEXT_PUBLIC_` acaba en el JavaScript público. La `API_FOOTBALL_KEY` vive solo
  en el backend.

## 7. Limitaciones a tener en cuenta

- **Sin servidor en Pages**: nada de `app/api/*`, middleware, ISR ni SSR. Si en
  el futuro se añaden, habría que pasar a Workers con
  [`@opennextjs/cloudflare`](https://opennext.js.org/cloudflare) o mover esas
  rutas al backend.
- **Sin optimizador de imágenes**: los escudos se sirven tal cual
  (`images.unoptimized`).
- **CORS sin cookies**: el backend usa `allow_credentials=False`, así que el
  frontend y la API pueden vivir en dominios distintos sin configuración extra.
- **Coste de CPU**: cada proyección corre 10.000 simulaciones por defecto; el
  host del backend debe tener CPU suficiente o usar `/api/projection/full` para
  trabajos largos.

## Checklist

- [ ] Backend público con HTTPS y `CORS_ALLOW_ORIGINS` con el dominio de Pages.
- [ ] Proyecto de Pages con root `frontend`, build `npm run build`, salida `out`.
- [ ] Variables `STATIC_EXPORT=1`, `NEXT_PUBLIC_API_URL` y `NODE_VERSION`.
- [ ] Build local con `STATIC_EXPORT=1` sin errores.
- [ ] `/api/health` y `/api/ready` responden desde el navegador en el dominio de
      Pages (sin errores de CORS en la consola).
