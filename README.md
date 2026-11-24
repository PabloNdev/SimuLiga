# SimuLiga

Simulador Monte Carlo de LaLiga y de la Champions League. Proyecta la temporada
con miles de simulaciones y responde a la pregunta que ninguna tabla contesta:
**qué probabilidad tiene cada equipo de salir campeón, entrar en Champions,
jugar Europa o descender**.

El motor combina rating **ELO**, un modelo de resultados **Davidson** y una
distribución de marcadores **Dixon-Coles**; el frontend lo convierte en tablas,
gráficos y un laboratorio de escenarios donde puedes forzar resultados y mover
ratings para ver qué cambia.

## Funcionalidades

- **Proyección de temporada**: probabilidades de posición final, puntos, Top 4,
  Europa y descenso a partir de 10.000 simulaciones (hasta 200.000 en modo
  síncrono, más con trabajos en segundo plano).
- **Resultados exactos**: matriz de marcadores por partido y evolución de la
  probabilidad de cada resultado jornada a jornada.
- **ELO reconstruido**: cinco temporadas de histórico (2020/21–2024/25) más el
  replay completo de 2025/26, con vistas de evolución por temporada.
- **Escenarios**: fuerza un resultado, ajusta el ELO de un equipo o cambia los
  parámetros del modelo y vuelve a simular sin tocar el estado real.
- **SimuChampions**: formato 2026/27 con 36 equipos, fase de liga de 8 jornadas,
  clasificación directa 1-8, playoff 9-24 y eliminación 25-36, con cuadro de
  eliminatorias.
- **Validación**: backtest temporal del modelo contra resultados reales,
  visible en `/metodologia` y en la API.
- **Modo demo**: si no hay datos ni clave de API, la app funciona con un
  calendario generado y lo indica en la interfaz.

## Stack

| Capa | Tecnología |
| --- | --- |
| Backend | Python 3.12, FastAPI, NumPy, SciPy, httpx, pydantic-settings |
| Frontend | Next.js 16 (App Router), React 19, TypeScript |
| Datos | API-Football, OpenFootball, football-data.co.uk, snapshots de ClubElo |
| Tests | pytest (backend), `node --test` (frontend) |

## Estructura

```
.
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI: endpoints de LaLiga
│   │   ├── champions/     # Módulo SimuChampions (API, datos, dominio)
│   │   ├── data/          # Carga de datos, snapshots y JSON de calibración
│   │   └── domain/        # ELO, Davidson, Dixon-Coles, simulación y tablas
│   ├── scripts/           # Calibración, importación y verificación
│   └── tests/             # Suite de pytest (offline y determinista)
├── frontend/
│   ├── app/               # Rutas de la App Router
│   ├── components/        # Dashboard, tablas, gráficos y escenarios
│   ├── lib/               # Cliente de API, tipos y utilidades
│   ├── public/data/       # Snapshot publicado (JSON de la última simulación)
│   └── tests/             # Tests de Node
└── docs/                  # Metodología, calibración y validación
```

## Puesta en marcha

Requisitos: **Python 3.12+** y **Node 20+**.

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
copy .env.example .env   # en macOS/Linux: cp .env.example .env
uvicorn app.api.main:app --reload --port 8000
```

La API queda en `http://localhost:8000`, con documentación interactiva en
`/docs` y `/redoc`.

Sin clave de API-Football funciona igual: el `.env.example` deja
`DATA_SOURCE=openfootball`, que descarga calendarios y resultados públicos de
OpenFootball. Si tampoco hay red, la app cae en modo demo.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Abre `http://localhost:3000`. El frontend llama a `http://localhost:8000` por
defecto; para apuntar a otro backend crea `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

El backend permite CORS desde `localhost:3000`, `127.0.0.1:3000` y
`localhost:3001`.

### Rutas del frontend

| Ruta | Contenido |
| --- | --- |
| `/` | Dashboard de LaLiga: tabla, proyección, cuotas y calendario |
| `/elo` | Evolución histórica del ELO |
| `/escenario` | Laboratorio de escenarios (resultados forzados, ELO, parámetros) |
| `/metodologia` | Modelo, calibración y validación |
| `/champions` | SimuChampions: fase de liga y proyección |
| `/champions/playoff` | Cuadro y pronóstico del playoff |
| `/champions/elo` | ELO de los participantes de Champions |
| `/champions/metodologia` | Metodología y validación de SimuChampions |

## Despliegue

El frontend es 100% cliente y se publica como export estático:

```bash
cd frontend
STATIC_EXPORT=1 npm run build   # crea out/
```

En PowerShell: `$env:STATIC_EXPORT="1"; npm run build`.

Sin backend, la app lee los JSON de `frontend/public/data` (la última
simulación publicada) y desactiva el laboratorio de escenarios y la simulación
de 1M. Para refrescar esos datos, con el backend en local:

```bash
cd backend
python scripts/export_frontend_snapshot.py
```

Después, commit de `frontend/public/data` y push: Cloudflare Pages reconstruye
solo. Con `NEXT_PUBLIC_STATIC_DATA=0` y `NEXT_PUBLIC_API_URL=...` la app vuelve a
llamar a la API en vivo (y el backend debe permitir el dominio del sitio en
`CORS_ALLOW_ORIGINS`). Guía completa en
[`docs/deploy-cloudflare.md`](docs/deploy-cloudflare.md).

## Variables de entorno

Se leen de `backend/.env`. El archivo real **no se versiona**; parte de
`backend/.env.example`.

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `API_FOOTBALL_KEY` | vacío | Clave de API-Football (RapidAPI). Sin ella se usan fuentes públicas |
| `DATA_SOURCE` | `auto` | `auto`, `api-football`, `openfootball`, `local` o `demo` |
| `LEAGUE_ID` / `SEASON` | `140` / `2026` | Competición y temporada de LaLiga (el ejemplo trae `SEASON=2024`; ajústalo si usas API-Football) |
| `DEMO_PLAYED_MATCHDAYS` | `8` | Jornadas "jugadas" cuando se usa el modo demo |
| `REWIND_MATCHDAY` | `0` | Retrocede el estado de la temporada N jornadas |
| `CACHE_TTL_SECONDS` | `21600` | Vida de la caché de datos remotos |
| `SNAPSHOT_TTL_SECONDS` | `3600` | Vida del snapshot en memoria |
| `CLUBELO_ENABLED` | `true` | Usa ClubElo como prior de los ratings |
| `OPENFOOTBALL_SEASON` | `2026-27` | Temporada activa en OpenFootball |
| `PREVIOUS_OPENFOOTBALL_SEASON` | `2025-26` | Temporada usada para el replay de ELO |
| `CORS_ALLOW_ORIGINS` | localhost:3000/3001 | Orígenes permitidos, separados por comas |
| `CHAMPIONS_*` | — | Equivalentes para SimuChampions (`CHAMPIONS_DATA_SOURCE`, `CHAMPIONS_SEASON`, …) |

## API

Todos los endpoints devuelven JSON. Los de datos incluyen `source`,
`data_version` y, cuando aplica, `demo`.

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/health` | Estado del servicio |
| GET | `/api/ready` | Fuente de datos, versión y número de equipos/partidos |
| GET | `/api/season` | Equipos, calendario y modelo activo |
| GET | `/api/elo` | Ratings ELO y su evolución |
| GET | `/api/matches` | Partidos con probabilidades por resultado |
| GET | `/api/validation` | Métricas del backtest y reglas de desempate |
| GET | `/api/projection` | Proyección (`mode`, `sims`, `seed`, `start_matchday`) |
| POST | `/api/projection` | Escenario con resultados forzados o ELO modificado |
| POST | `/api/projection/full` | Igual que el anterior, como trabajo asíncrono (`202`) |
| GET | `/api/jobs/{job_id}` | Estado y progreso de un trabajo |

Champions League:

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/champions/season` | Equipos, calendario y formato |
| GET | `/api/champions/matches` | Partidos con probabilidades |
| GET | `/api/champions/elo` | ELO de los 36 equipos |
| GET | `/api/champions/validation` | Validación del modelo |
| GET | `/api/champions/projection` | Fase de liga, playoff y opciones de título |

`sims` admite hasta 200.000 simulaciones en LaLiga y 100.000 en Champions de
forma síncrona; por encima hay que usar `/api/projection/full` y consultar el
trabajo con `/api/jobs/{job_id}`.

## Modelo y datos

- **ELO**: reconstrucción desde 2020/21 partiendo de 1500, con regresión a la
  media entre temporadas y un prior basado en ClubElo para los equipos sin
  histórico reciente.
- **Davidson**: probabilidades de victoria/empate/derrota a partir de la
  diferencia de ELO, con ventaja de campo y parámetro `nu`.
- **Dixon-Coles**: distribución de marcadores exactos con correlación en
  resultados de pocos goles.
- **Datos**: se intentan en orden API-Football → OpenFootball →
  football-data.co.uk → snapshots locales de ClubElo → caché → demo.
- **Calibración**: los parámetros se ajustan con temporadas anteriores y se
  validan sobre una temporada completa no vista; los JSON resultantes viven en
  `backend/app/data/`.

Detalles y resultados de los experimentos en
[`docs/elo.md`](docs/elo.md), [`docs/champions.md`](docs/champions.md) y
[`docs/champions-calibration.md`](docs/champions-calibration.md).

## Tests

```bash
# Backend (offline: fuerza DATA_SOURCE=demo y sin claves)
cd backend && python -m pytest

# Frontend
cd frontend && npm test
cd frontend && npm run lint
```

## Scripts de backend

`backend/scripts/` contiene las herramientas de mantenimiento:

| Script | Uso |
| --- | --- |
| `calibrate_history.py` | Reconstruye el ELO histórico |
| `calibrate_champions.py` | Ajusta el modelo de SimuChampions |
| `validate_champions_elo.py` | Backtest de cinco temporadas |
| `verify_champions.py` / `verify_elo_history.py` | Comprobaciones de integridad |
| `import_clubelo_history.py` | Importa snapshots de ClubElo |
| `import_champions_2026_27.py` | Carga el calendario de la temporada activa |
| `export_frontend_snapshot.py` | Genera los JSON publicados del frontend |
| `analyze_elo_calibration.py` | Análisis de la calibración del ELO |

## Documentación

- [`docs/elo.md`](docs/elo.md) — cálculo y evolución del ELO.
- [`docs/elo-calibration-2026.md`](docs/elo-calibration-2026.md) — calibración de los ratings iniciales.
- [`docs/champions.md`](docs/champions.md) — formato y fuentes de SimuChampions.
- [`docs/champions-calibration.md`](docs/champions-calibration.md) — ajuste del modelo de Champions.
- [`docs/champions-elo-5y-validation.md`](docs/champions-elo-5y-validation.md) — backtest de cinco temporadas.
- [`docs/superpowers/`](docs/superpowers) — planes y especificaciones de diseño.
- [`docs/deploy-cloudflare.md`](docs/deploy-cloudflare.md) — despliegue en Cloudflare Pages y datos publicados.

## Licencia

Este repositorio no declara una licencia; el código queda bajo copyright de su
autor.
