# Desplegar en Cloudflare (Workers)

El proyecto de Cloudflare conectado al repositorio es un **Worker con assets
estáticos**: `next build` genera `out/` y `wrangler deploy` lo publica tal cual.
No hay servidor de Next en producción.

| Pieza | Dónde | Qué hace |
| --- | --- | --- |
| `frontend/` | Worker `simuliga` | Sirve la interfaz estática desde `out/` |
| `backend/` | Opcional, otro host | FastAPI con las simulaciones; solo si se activan datos en vivo |

Los datos que muestra el sitio salen de `frontend/public/data`: una foto de la
última simulación. Así funciona sin backend.

## Configuración del Worker

En **Workers y Pages → simuliga → Configuración → Compilaciones**:

| Ajuste | Valor |
| --- | --- |
| Repositorio | `PabloNdev/SimuLiga` |
| Rama de producción | `main` |
| Comando de compilación | `npm run build` |
| Implementar comando | `npx wrangler deploy` |
| Directorio raíz | `frontend` |

No hacen falta variables de entorno: `next build` activa solo el export estático
(ver `frontend/next.config.ts`). El entorno de compilación detecta Node 22 por su
cuenta; si quisieras fijarlo, añade `NODE_VERSION=22`.

[`frontend/wrangler.jsonc`](../frontend/wrangler.jsonc) define el Worker:

```jsonc
{
  "name": "simuliga",
  "compatibility_date": "2026-11-24",
  "assets": {
    "directory": "./out",
    "not_found_handling": "404-page"
  }
}
```

Cloudflare sirve `/champions` desde `champions.html` y devuelve `404.html` para
rutas inexistentes.

## Publicar y comprobar

Cada `push` a `main` dispara una compilación. Para probar en local:

```bash
cd frontend
npm run build
npx wrangler dev
```

Queda en `http://localhost:8787` sirviendo `out/` como lo hará Cloudflare.

La primera vez hay que habilitar una URL en **Dominios**: activa
`simuliga.pablondev.workers.dev` o añade un dominio propio. Sin eso el Worker se
despliega pero no responde en ninguna dirección.

## Regenerar los datos publicados

Los JSON de `frontend/public/data` salen de la API real. Con el backend en local
(necesita acceso a OpenFootball / football-data.co.uk, o `DATA_SOURCE=demo`):

```bash
cd backend
python scripts/export_frontend_snapshot.py
git add frontend/public/data
git commit -m "data: refresh published snapshot"
git push
```

El script llama a FastAPI en proceso, usa 10.000 simulaciones y la jornada
actual, y escribe 15 archivos (~1 MB): un `manifest.json` con fecha, jornada,
simulaciones y origen, más temporada, ELO, validación, partidos y proyección de
LaLiga y Champions en los dos modos (`score` y `1x2`).

Comprueba que en `manifest.json` aparezca `"demo": false` antes de publicar.
Opciones: `--sims 50000` para más precisión y `--out` para otra carpeta.

No hay refresco automático: los datos cambian cuando ejecutas el script y haces
push.

## Pasar a datos en vivo (cuando exista API)

1. Publica el backend y añade el dominio del Worker a `CORS_ALLOW_ORIGINS`.
2. En el Worker, añade `NEXT_PUBLIC_API_URL=https://tu-api.ejemplo.com` y
   `NEXT_PUBLIC_STATIC_DATA=0` como variables de compilación.
3. Reintenta el despliegue (**Implementaciones → Reintentar compilación**): las
   variables `NEXT_PUBLIC_*` se incrustan en el build.

Con eso se reactivan el laboratorio de escenarios y la simulación de 1M.

## Detalles y límites

- `frontend/public/_headers` no lo aplica Workers: si hacen falta cabeceras
  personalizadas, se declaran en `wrangler.jsonc` (`assets.headers`).
- Sin servidor: nada de `app/api/*`, middleware, ISR ni SSR. Si algún día hacen
  falta, habría que usar `@opennextjs/cloudflare`.
- Sin optimizador de imágenes (`images.unoptimized`).
- Los datos son una foto fija hasta que se regenera el snapshot.
- El export ocupa ~4 MB y 214 archivos; muy por debajo de los límites del plan
  gratuito.

## Checklist

- [ ] Root `frontend`, build `npm run build`, deploy `npx wrangler deploy`.
- [ ] `frontend/wrangler.jsonc` con `assets.directory: "./out"`.
- [ ] `frontend/public/data/manifest.json` con `demo: false` y fecha reciente.
- [ ] `npm run build` local genera `out/` con `out/data/`.
- [ ] URL habilitada en **Dominios** (`workers.dev` o dominio propio).
- [ ] El panel, `/elo`, `/champions` y `/champions/playoff` enseñan datos;
      `/escenario` explica que necesita el motor.
