# Desplegar el frontend en Cloudflare Pages

El sitio se publica como **export estático** (Next.js `output: "export"`). Hay
dos formas de darle datos:

| Modo | Datos | Qué necesita |
| --- | --- | --- |
| **Publicado (por defecto)** | JSON de la última simulación, en `frontend/public/data` | Nada: solo el build |
| Con API | Respuestas en vivo de FastAPI | Un backend público y `NEXT_PUBLIC_API_URL` |

En el modo publicado el sitio enseña la última simulación generada, sin errores
de conexión. El laboratorio de escenarios y la simulación de 1M quedan
desactivados, porque necesitan el motor de simulación.

## 1. Crea el proyecto en Cloudflare Pages

En el panel: **Workers & Pages → Create → Pages → Connect to Git**, elige el
repositorio y configura:

| Ajuste | Valor |
| --- | --- |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Build output directory | `out` |
| Environment variable | `STATIC_EXPORT=1` |
| Environment variable | `NODE_VERSION=22` |

El preset **Next.js (Static HTML Export)** ya rellena build y salida; si aparece
otro, elige **None** y escríbelo a mano. Lo que nunca puede faltar es el root
directory `frontend`.

`STATIC_EXPORT=1` activa el modo estático en
[`frontend/next.config.ts`](../frontend/next.config.ts): genera `out/`, marca las
imágenes como no optimizadas y desactiva `partialPrefetching` y
`cacheComponents` (PPR no existe en modo export). Además, en un export estático
la app lee por defecto los JSON publicados en lugar de llamar a la API.

Cada `push` a `main` reconstruye y publica el sitio.

## 2. Regenera los datos publicados

Los JSON de `frontend/public/data` salen de la API real. Se regeneran con el
backend en local (necesita acceso a OpenFootball / football-data.co.uk o
`DATA_SOURCE=demo`):

```bash
cd backend
python scripts/export_frontend_snapshot.py
```

El script llama a la app FastAPI en proceso (no hace falta levantar el
servidor), usa 10.000 simulaciones y la jornada actual, y escribe:

| Archivo | Contenido |
| --- | --- |
| `manifest.json` | Fecha de generación, jornada, simulaciones y origen de los datos |
| `season.json`, `elo.json`, `validation.json` | Temporada, ratings y backtest de LaLiga |
| `matches-*.json`, `projection-*.json` | Partidos y proyección en modo `score` y `1x2` |
| `champions-*.json` | Los mismos datos para SimuChampions, con sus dos modos |

Opciones: `--sims 50000` para más precisión (el archivo crece) y `--out` para
otra carpeta de destino.

Revisa `manifest.json` (que `demo` sea `false`), haz commit de los JSON y push:

```bash
git add frontend/public/data
git commit -m "data: refresh published snapshot"
git push
```

Pages reconstruye solo y el sitio pasa a mostrar los datos nuevos. No hay un
refresh automático: si la jornada avanza, hay que volver a ejecutar el script.

## 3. Pasar a datos en vivo (cuando tengas API)

Cuando publiques el backend en Fly.io, Render, Railway o un VPS:

1. En el `.env` del backend añade el dominio del sitio a `CORS_ALLOW_ORIGINS`
   (separados por comas, con `https://` y sin barra final).
2. En Pages añade `NEXT_PUBLIC_API_URL=https://tu-api.ejemplo.com` y
   `NEXT_PUBLIC_STATIC_DATA=0`.
3. Vuelve a desplegar (**Deployments → Retry deployment**): las variables
   `NEXT_PUBLIC_*` se incrustan en el build.

Con `NEXT_PUBLIC_STATIC_DATA=0` se reactivan el laboratorio de escenarios y la
simulación de 1M.

## 4. Comprueba el build en local

```powershell
cd frontend
$env:STATIC_EXPORT="1"; npm run build
```

```bash
cd frontend
STATIC_EXPORT=1 npm run build
```

Queda en `frontend/out/` (ignorado por git) con los JSON en `out/data/`. Para
servirlo hace falta un servidor que resuelva URLs limpias:

```bash
npx wrangler pages dev out
```

Rutas generadas: `/`, `/elo`, `/escenario` (aviso de modo publicado),
`/metodologia`, `/champions`, `/champions/elo`, `/champions/metodologia`,
`/champions/playoff` y `404.html`.

## 5. Despliegue manual (opcional)

Sin conectar el repositorio:

```bash
cd frontend
STATIC_EXPORT=1 npm run build
npx wrangler pages deploy out --project-name simuliga
```

Wrangler pide iniciar sesión la primera vez. El *project name* define el
subdominio `<project-name>.pages.dev`.

## 6. Dominio propio

En **Pages → tu proyecto → Custom domains** añade el dominio y crea el CNAME que
indique Cloudflare. Si más adelante usas la API, incluye también ese dominio en
`CORS_ALLOW_ORIGINS`.

## 7. Detalles y límites

- `frontend/public/_headers` añade caché inmutable de un año para
  `/_next/static/*`.
- Las fuentes de `next/font/google` se descargan durante el build.
- Sin servidor en Pages: nada de `app/api/*`, middleware, ISR ni SSR. Si algún
  día hacen falta, habría que pasar a Workers con
  [`@opennextjs/cloudflare`](https://opennext.js.org/cloudflare).
- Sin optimizador de imágenes: los escudos se sirven tal cual.
- Los datos publicados son una foto fija: cambian cuando ejecutas el script y
  haces push, no con los resultados del día.
- El snapshot actual ocupa ~1 MB y 15 archivos, muy por debajo de los límites
  del plan gratuito.

## Checklist

- [ ] Proyecto de Pages con root `frontend`, build `npm run build`, salida `out`.
- [ ] Variables `STATIC_EXPORT=1` y `NODE_VERSION=22`.
- [ ] `frontend/public/data/manifest.json` con `demo: false` y fecha reciente.
- [ ] Build local con `STATIC_EXPORT=1` sin errores.
- [ ] El panel, `/elo`, `/champions` y `/champions/playoff` enseñan datos; `/escenario`
      explica que necesita el motor.
- [ ] (Opcional) `NEXT_PUBLIC_STATIC_DATA=0` + `NEXT_PUBLIC_API_URL` cuando exista
      backend, y su dominio en `CORS_ALLOW_ORIGINS`.
