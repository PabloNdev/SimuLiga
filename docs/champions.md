# SimuChampions

SimuChampions es el módulo de Champions League dentro de SimuLiga. Comparte la
matemática de SimuLiga (ELO, Davidson y Dixon-Coles) y añade el formato propio
de la competición: 36 equipos, fase de liga de 8 jornadas, puestos 1-8 a octavos,
9-24 a playoff y 25-36 eliminados.

## Formato

- 36 equipos, 144 partidos de fase de liga, 8 por equipo.
- Tabla única sin ida/vuelta.
- Puestos 1-8: clasificación directa a octavos.
- Puestos 9-24: playoff a dos partidos.
- Puestos 25-36: eliminados.
- Playoff: `9 vs 24`, `10 vs 23`, …, `16 vs 17`. La vuelta se juega en casa del
  mejor clasificado. Sin goles fuera de casa; prórroga y penaltis si hace falta.

## Fuentes de datos

Orden de uso:

1. API-Football (`league=2`) para 2025/26 y 2026/27.
2. OpenFootball `champions-league/<temporada>/cl.txt`.
3. Snapshots de ClubElo (`app/data/clubelo_snapshots.json`) para el prior.
4. Caché local del último snapshot válido.
5. Modo demo con calendario generado.

El replay de cinco temporadas reconstruye el ELO y 2025/26 calibra Davidson.
La 2026/27 es la vista activa. Si 2026/27 no está disponible, la app muestra
2025/26 con las primeras jornadas reales y el resto simulado, y lo indica en
`data_note`.

## ELO

- Ventana: cinco temporadas de Champions, de 2021/22 a 2025/26.
- Fuente: OpenFootball. Total: 753 partidos.
- Prior: snapshots de ClubElo al inicio de cada temporada, desde
  `backend/app/data/clubelo_snapshots.json`. El snapshot se genera a partir del
  dataset abierto `xgabora/Club-Football-Match-Data` (EloRatings.csv).
- Al inicio de cada temporada se aplica una regresión del 20 % hacia 1500:
  `nuevo = actual + 0.20 * (1500 - actual)`.
- Después se mezcla con el rating de ClubElo de esa temporada con peso 0.75:
  `rating = 0.25 * replay + 0.75 * ClubElo`.
- Replay cronológico con `K=20`, `H=60` y multiplicador por margen de goles.
- La temporada 2026/27 arranca desde el rating post-regresión y aplica el
  prior ClubElo de `2026-08-01` antes de jugar sus partidos.
- Los equipos nuevos usan el prior ClubElo 2026; si no hay dato, la media de
  los ratings actuales conocidos.
- La final se trata como campo neutral. Se usa el marcador a 90 minutos.
- Los ratings de LaLiga no se tocan.

## Modelo

- Davidson convierte la diferencia de ELO en probabilidades 1X2.
- Dixon-Coles genera marcadores exactos y goles para los desempates.
- `H` y `nu` se calibran con la Champions 2025/26: jornadas 1-6 para
  entrenamiento, 7-8 + eliminatorias para validación, y ajuste final con toda la
  temporada.
- Si el ajuste falla, se usan los parámetros de LaLiga como respaldo.

## Simulación

- Monte Carlo de la fase de liga; por defecto 10.000 simulaciones.
- El ELO permanece fijo durante la simulación, igual que en SimuLiga.
- Desempates: puntos, diferencia de goles, goles a favor, goles fuera,
  victorias, victorias fuera y sorteo determinista.
- Playoff simulado a dos partidos con prórroga y penaltis.
- Salidas: top 8, playoff, eliminación, octavos, puntos esperados, distribución
  de posiciones, rivales probables y cuadro 9-24.

## API

- `GET /api/champions/season`
- `GET /api/champions/projection?mode=score|1x2&sims=10000&seed=42`
- `GET /api/champions/matches?mode=score|1x2`
- `GET /api/champions/elo`
- `GET /api/champions/validation`

## Configuración

```dotenv
CHAMPIONS_LEAGUE_ID=2
CHAMPIONS_SEASON=2026
CHAMPIONS_PREVIOUS_SEASON=2025
CHAMPIONS_DATA_SOURCE=auto
CHAMPIONS_CLUBELO_DATE_2025=2025-08-01
CHAMPIONS_CLUBELO_DATE_2026=2026-08-01
CHAMPIONS_CACHE_TTL_SECONDS=21600
CHAMPIONS_SNAPSHOT_TTL_SECONDS=3600
CHAMPIONS_FALLBACK_REWIND_MATCHDAY=4
CHAMPIONS_CLUBELO_ENABLED=true
CHAMPIONS_HISTORY_SEASONS=5
CHAMPIONS_SEASON_REGRESSION=0.20
CHAMPIONS_CLUBELO_PRIOR_WEIGHT=0.75
```

`CHAMPIONS_API_FOOTBALL_KEY` es opcional; si no existe, se reutiliza
`API_FOOTBALL_KEY`.

## Scripts

```powershell
cd backend
python scripts/import_clubelo_history.py
python scripts/calibrate_champions.py
python scripts/verify_champions.py
python scripts/validate_champions_elo.py
```

`import_clubelo_history.py` regenera `app/data/clubelo_snapshots.json` desde
el dataset abierto de ClubElo.

`calibrate_champions.py` genera `app/data/champions_historical.json`,
`app/data/champions_params.json` y `app/data/champions_demo_matches.json`.

`validate_champions_elo.py` ejecuta el backtest de cinco temporadas contra una
temporada de holdout, compara configuraciones de alpha/K y regenera
`docs/champions-elo-5y-validation.md`.

## Limitaciones

- API-Football puede no cubrir 2025/26 o 2026/27 según el plan contratado.
- ClubElo puede no estar disponible; en ese caso la semilla es 1500.
- No se modelan lesiones, sanciones, alineaciones, mercado ni coeficiente UEFA.
- La disciplina y el coeficiente se sustituyen por un sorteo determinista.
- El ELO no se actualiza dentro de la simulación.
- La final se trata como neutral.
