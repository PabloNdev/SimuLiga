# SimuChampions â€” DiseÃ±o

Fecha: 2026-10-23
Estado: aprobado por el usuario
Ãmbito: mÃ³dulo de Champions League dentro del repositorio SimuLiga

## 1. Objetivo

AÃ±adir SimuChampions como una competiciÃ³n mÃ¡s dentro de SimuLiga. El motor
comparte la base matemÃ¡tica de SimuLiga (ELO, Davidson y Dixon-Coles), pero el
formato, los datos y la simulaciÃ³n son propios de la Champions League:

- 36 equipos en una Ãºnica fase de liga.
- 8 partidos por equipo (144 partidos).
- ClasificaciÃ³n directa a octavos para los puestos 1-8.
- Playoff para los puestos 9-24.
- EliminaciÃ³n para los puestos 25-36.

La vista activa es la temporada 2026/27. La temporada 2025/26 se usa para
reconstruir el ELO, calibrar el modelo y validar las mÃ©tricas.

## 2. Alcance

### 2.1 Incluido en v1

1. Fase de liga completa de 2026/27 con partidos reales jugados y pendientes.
2. Tabla Ãºnica de 36 equipos con zonas de clasificaciÃ³n.
3. Probabilidades por equipo de:
   - terminar entre los puestos 1-8;
   - terminar entre los puestos 9-24 y jugar el playoff;
   - terminar entre los puestos 25-36 y quedar eliminado;
   - alcanzar los octavos de final (top 8 o ganar el playoff).
4. DistribuciÃ³n de posiciones por equipo y puntos esperados.
5. PrevisiÃ³n del playoff:
   - probabilidad de ganar la eliminatoria;
   - rivales mÃ¡s probables;
   - cuadro con el equipo mÃ¡s probable en cada puesto 9-24.
6. Predicciones 1X2 y marcador mÃ¡s probable de los partidos pendientes.
7. PÃ¡gina de ELO con rating actual, evoluciÃ³n desde el inicio de 2025/26 y
   verificaciÃ³n del replay.
8. PÃ¡gina de metodologÃ­a con fuentes, fÃ³rmulas, desempates y limitaciones.
9. Selector de competiciÃ³n LaLiga / Champions en la cabecera.

### 2.2 Fuera de v1

- Simular octavos, cuartos, semifinales y final.
- Laboratorio de escenarios con resultados forzados o ajustes de ELO.
- HistÃ³rico visual de varias temporadas de Champions.
- Lesiones, sanciones, alineaciones, mercado o coeficiente UEFA como variable
  predictiva.
- Cambios en el comportamiento o en los datos de las rutas de LaLiga.

## 3. Arquitectura

### 3.1 Principios

- Se reutiliza la matemÃ¡tica ya validada: `app.domain.elo`,
  `app.domain.davidson`, `app.domain.scoreline`.
- El formato Champions se implementa en un paquete aislado: `app.champions`.
- No se duplica el motor completo de LaLiga ni se refactoriza en una abstracciÃ³n
  genÃ©rica de competiciones.
- El frontend aÃ±ade rutas y componentes propios bajo `/champions`; las pÃ¡ginas
  de LaLiga no cambian.

### 3.2 Backend

```text
backend/app/champions/
  __init__.py
  config.py
  models.py
  names.py
  data/
    __init__.py
    api_football.py
    openfootball.py
    snapshot.py
  domain/
    __init__.py
    standings.py
    simulation.py
    playoff.py
  api/
    __init__.py
    routes.py
    serializers.py
```

Responsabilidades:

| Archivo | Responsabilidad |
| --- | --- |
| `config.py` | `ChampionsSettings` con prefijo `CHAMPIONS_`, TTL y fechas de ClubElo. |
| `models.py` | `ChampionsTeam`, `ChampionsMatch`, `Phase`, `ChampionsSnapshot`. |
| `names.py` | NormalizaciÃ³n y alias de API-Football, OpenFootball y ClubElo. |
| `data/api_football.py` | Descarga de fixtures `league=2`, parseo de rondas, ida/vuelta y marcador a 90 minutos. |
| `data/openfootball.py` | Parser del formato `cl.txt`. |
| `data/snapshot.py` | ConstrucciÃ³n del snapshot, replay ELO, cachÃ©, parÃ¡metros y verificaciÃ³n. |
| `domain/standings.py` | Registros y ordenaciÃ³n con desempates UCL. |
| `domain/simulation.py` | Monte Carlo de la fase de liga. |
| `domain/playoff.py` | Emparejamientos 9-24, eliminatorias a dos partidos, prÃ³rroga y penaltis. |
| `api/routes.py` | Router `/api/champions`. |
| `api/serializers.py` | Payloads JSON. |

Se reutilizan sin cambios:

- `app.domain.elo.update_ratings`
- `app.domain.davidson`
- `app.domain.scoreline`
- `app.data.clubelo.fetch_clubelo_ratings`
- `app.data.names.normalize_name` y `slugify`
- `app.api.main` solo para registrar el router.

### 3.3 Frontend

```text
frontend/app/champions/page.tsx
frontend/app/champions/playoff/page.tsx
frontend/app/champions/elo/page.tsx
frontend/app/champions/metodologia/page.tsx

frontend/components/champions/
  ChampionsDashboard.tsx
  LeaguePhaseTable.tsx
  ProjectionTable.tsx
  PositionHeatmap.tsx
  PlayoffForecast.tsx
  ChampionsMatches.tsx
  ChampionsElo.tsx
  ChampionsMethodology.tsx

frontend/components/CompetitionSwitch.tsx
frontend/lib/champions-api.ts
frontend/lib/champions-types.ts
```

Se reutilizan `TeamBadge`, `ProbabilityBar`, `RangeBar`, `Heatmap`, `InfoTip`,
`States` y los tokens visuales existentes de `globals.css`. Los estilos nuevos
usan el prefijo `.champions-` para no afectar a LaLiga.

### 3.4 NavegaciÃ³n

- La cabecera muestra un selector `LaLiga | Champions`.
- En rutas que empiezan por `/champions`, la marca pasa a SimuChampions y la
  navegaciÃ³n muestra Panel, Playoff, ELO y MÃ©todo.
- En el resto de rutas se mantiene la navegaciÃ³n actual de SimuLiga.
- El selector no duplica estado global: se deriva de `usePathname()`.

## 4. Datos

### 4.1 Fuentes

Orden de preferencia:

1. API-Football, `league=2`, `season=2025` y `season=2026`.
2. OpenFootball `champions-league/<temporada>/cl.txt`.
3. CachÃ© local del Ãºltimo snapshot vÃ¡lido.
4. Modo demo: usa los 36 participantes de 2025/26, sus ratings finales y un
   calendario sintÃ©tico de 8 jornadas generado de forma determinista (cada
   equipo 4 partidos en casa y 4 fuera, sin repetir rival). Se etiqueta como
   demo en la API y en la UI.

ConfiguraciÃ³n:

```dotenv
CHAMPIONS_LEAGUE_ID=2
CHAMPIONS_SEASON=2026
CHAMPIONS_PREVIOUS_SEASON=2025
CHAMPIONS_DATA_SOURCE=auto
CHAMPIONS_CLUBELO_DATE_2025=2025-08-01
CHAMPIONS_CLUBELO_DATE_2026=2026-08-01
CHAMPIONS_CACHE_TTL_SECONDS=21600
CHAMPIONS_SNAPSHOT_TTL_SECONDS=3600
```

Valores de `CHAMPIONS_DATA_SOURCE`: `auto`, `api-football`, `openfootball` o
`demo`. En `auto` se prueba API-Football, despuÃ©s OpenFootball, despuÃ©s cachÃ© y
finalmente demo.

La clave se toma de `CHAMPIONS_API_FOOTBALL_KEY`; si estÃ¡ vacÃ­a, se reutiliza
`API_FOOTBALL_KEY` de la configuraciÃ³n existente. Nunca se registra en logs ni
se devuelve en la API.

### 4.2 NormalizaciÃ³n de equipos

- Cada equipo tiene un `id` canÃ³nico en kebab-case, nombre, nombre corto,
  color, paÃ­s y ELO.
- `names.py` mantiene alias por proveedor:
  - API-Football: nombres completos.
  - OpenFootball: nombres con sufijo de paÃ­s, por ejemplo `Arsenal FC (ENG)`.
  - ClubElo: nombres cortos, por ejemplo `Arsenal`.
- El paÃ­s se extrae del sufijo `(XXX)` en OpenFootball o del campo de
  API-Football cuando estÃ© disponible.
- Si un equipo no se resuelve, se crea con `slugify`, color de respaldo y ELO
  pendiente de asignar.

### 4.3 Parseo de rondas

API-Football devuelve etiquetas como:

- `League Stage - 1` â€¦ `League Stage - 8`
- `Knockout Round Playoffs`
- `Round of 16`
- `Quarter-finals`
- `Semi-finals`
- `Final`

Se normalizan a:

```text
league:<1-8>
playoff:<leg>
r16:<leg>
qf:<leg>
sf:<leg>
final
```

Se excluyen las rondas de clasificaciÃ³n (`Qualification Round`, `Play-offs` de
acceso). La ida y la vuelta se infieren del texto de la ronda o del orden de
fechas dentro de la eliminatoria.

### 4.4 Marcador a 90 minutos

- El ELO y el modelo de marcador usan el resultado a 90 minutos.
- API-Football: se usa `score.fulltime`; si no existe, se usa `goals`.
- OpenFootball: se usa el marcador principal; el parcial entre parÃ©ntesis no
  sustituye al resultado final.
- En partidos con prÃ³rroga o penaltis, el replay ELO usa el marcador a 90
  minutos si estÃ¡ disponible. Si solo existe el marcador final, se usa ese y se
  anota la limitaciÃ³n.
- La final se trata como sede neutral: `home_advantage = 0` al actualizar ELO.

## 5. ELO

### 5.1 Siembra

- Snapshot de ClubElo al `2025-08-01` para el replay de 2025/26.
- Cada equipo participante de 2025/26 recibe su ELO de ClubElo.
- Los equipos no encontrados reciben 1500 y se cuentan en la verificaciÃ³n.
- No se usa `historical_ratings.json` de LaLiga.

### 5.2 Replay 2025/26

1. Ordenar todos los partidos por fecha y hora.
2. Aplicar `update_ratings` con `K=20`, `H=60` y multiplicador por margen.
3. La final usa `H=0`.
4. Guardar:
   - rating inicial por equipo;
   - rating final por equipo;
   - timeline mensual con ratings;
   - partidos aplicados, aplazados y sin marcador;
   - equipos resueltos y no resueltos.

El replay incluye fase de liga, playoff, octavos, cuartos, semifinales y final.
No incluye rondas de clasificaciÃ³n.

### 5.3 Ratings de 2026/27

- Equipo que jugÃ³ 2025/26: parte del rating final del replay.
- Equipo nuevo en 2026/27: parte del ClubElo al `2026-08-01`.
- Equipo nuevo sin ClubElo: media de los ratings de los equipos nuevos
  resueltos; si no hay ninguno, 1500.
- DespuÃ©s se aplican los partidos de 2026/27 ya jugados, por jornada.
- El rating resultante es el que usa la simulaciÃ³n.

### 5.4 VerificaciÃ³n

El snapshot expone:

- temporada anterior y partidos totales/aplicados;
- partidos sin marcador, rellenados o no resueltos;
- equipos totales/resueltos;
- fuentes usadas;
- baseline de equipos nuevos;
- ratings inicial y final por equipo.

## 6. CalibraciÃ³n de Davidson

- Se usan los partidos de 2025/26 con el ELO previo a cada partido
  (walk-forward) para obtener `delta_elo`.
- Split temporal:
  - entrenamiento: jornadas 1-6 de la fase de liga;
  - validaciÃ³n: jornadas 7-8 + playoff + eliminatorias;
  - ajuste final: todos los partidos de 2025/26.
- Se ajustan `H` y `nu` con `fit_davidson`.
- Se guardan mÃ©tricas de validaciÃ³n: accuracy, log-loss, Brier y error de
  calibraciÃ³n por resultado.
- Si la muestra es insuficiente o el ajuste falla, se usan los parÃ¡metros de
  `calibrated_params.json` de LaLiga como respaldo.
- Los parÃ¡metros se guardan en `app/data/champions_params.json` y no modifican
  los de LaLiga.

## 7. SimulaciÃ³n

### 7.1 Fase de liga

- Entrada: 36 equipos, partidos jugados y pendientes, ratings actuales,
  parÃ¡metros Davidson y Dixon-Coles.
- Los partidos jugados son base fija.
- Cada simulaciÃ³n muestrea los partidos pendientes:
  - modo `score`: marcador exacto con Dixon-Coles;
  - modo `1x2`: resultado con Davidson.
- El ELO permanece fijo durante la simulaciÃ³n.
- Se construye la tabla de 36 con los desempates UCL.

Desempates, en orden:

1. Puntos.
2. Diferencia de goles.
3. Goles a favor.
4. Goles como visitante.
5. Victorias.
6. Victorias como visitante.
7. Sorteo determinista con la semilla de la simulaciÃ³n.

No se modelan puntos de disciplina ni coeficiente UEFA; el sorteo cubre el
Ãºltimo criterio. Esto se documenta en la metodologÃ­a.

### 7.2 Salidas por equipo

- Puntos esperados, desviaciÃ³n tÃ­pica, mediana, p10 y p90.
- PosiciÃ³n esperada y posiciÃ³n mÃ¡s probable.
- DistribuciÃ³n de probabilidad de las 36 posiciones.
- Probabilidad de top 8.
- Probabilidad de playoff (9-24).
- Probabilidad de eliminaciÃ³n (25-36).
- Probabilidad de ganar el playoff.
- Probabilidad de octavos: `P(top 8) + P(playoff) * P(ganar playoff | playoff)`.
- Probabilidad de cada rival en el playoff.

### 7.3 Playoff

- Emparejamientos deterministas:
  - 9 vs 24
  - 10 vs 23
  - 11 vs 22
  - 12 vs 21
  - 13 vs 20
  - 14 vs 19
  - 15 vs 18
  - 16 vs 17
- El equipo mejor clasificado juega la vuelta en casa.
- Cada eliminatoria se simula a dos partidos con el modelo de marcador.
- Si el agregado queda empatado:
  - prÃ³rroga de 30 minutos con lambdas escaladas por `1/3`;
  - si persiste el empate, penaltis 50/50.
- No se aplica la regla del gol fuera de casa.
- Se agrega, por equipo, la distribuciÃ³n de rivales y la probabilidad de
  avanzar.
- El cuadro muestra, para cada puesto 9-24, el equipo mÃ¡s probable y su
  probabilidad.

### 7.4 Rendimiento

- 10.000 simulaciones por defecto.
- MÃ¡ximo sÃ­ncrono: 100.000.
- Procesamiento vectorizado por lotes de 5.000, siguiendo el patrÃ³n de
  `app/domain/simulation.py`.
- Semilla por defecto 42; misma semilla implica mismo resultado.

## 8. API

Prefijo: `/api/champions`.

### 8.1 `GET /api/champions/season`

Devuelve competiciÃ³n, temporada, fuente, `demo`, `data_note`, `updated_at`,
`data_version`, jornada actual, partidos jugados/pendientes, equipos, tabla,
modelo, reglas de desempate y zonas de clasificaciÃ³n.

### 8.2 `GET /api/champions/projection`

ParÃ¡metros:

- `mode`: `score` (por defecto) o `1x2`.
- `sims`: 1-100000, por defecto 10000.
- `seed`: por defecto 42.

Devuelve proyecciones por equipo, predicciones de partidos pendientes, playoff
y standings base.

### 8.3 `GET /api/champions/matches`

ParÃ¡metros:

- `mode`: `score` o `1x2`.

Devuelve todos los partidos con estado, marcador real, probabilidades y
marcador mÃ¡s probable.

### 8.4 `GET /api/champions/elo`

Devuelve ratings actuales, inicio de temporada, delta, partidos jugados,
histÃ³rico, timeline y verificaciÃ³n.

### 8.5 `GET /api/champions/validation`

Devuelve mÃ©tricas de calibraciÃ³n, modelo, fuentes y conteos de datos.

### 8.6 Errores

- Si no hay datos reales, la API responde con el snapshot demo y
  `demo: true`.
- Si la peticiÃ³n es invÃ¡lida, `422` con detalle.
- Si el motor falla, `500` con mensaje controlado; nunca se expone la clave.

## 9. Frontend

### 9.1 Panel `/champions`

Orden de bloques:

1. Cabecera de competiciÃ³n: temporada, jornada, fuente y estado de datos.
2. Resumen de favoritos: probabilidad de top 8 y de octavos.
3. Tabla de 36 equipos con zonas 1-8, 9-24 y 25-36.
4. Tabla de proyecciones con puntos esperados y probabilidades.
5. Mapa de calor de posiciones.
6. PrevisiÃ³n de playoff.
7. Partidos por jornada.

### 9.2 Playoff `/champions/playoff`

- Cuadro 9-24 con el equipo mÃ¡s probable en cada puesto.
- Probabilidad de avanzar por equipo.
- Rivales mÃ¡s probables por equipo.
- ExplicaciÃ³n de ida/vuelta, prÃ³rroga y penaltis.

### 9.3 ELO `/champions/elo`

- Tabla ordenada por rating con inicio, delta y partidos.
- GrÃ¡fico de evoluciÃ³n desde el inicio de 2025/26.
- Panel de verificaciÃ³n del replay.
- ParÃ¡metros ELO y Davidson.

### 9.4 MÃ©todo `/champions/metodologia`

- Formato de la competiciÃ³n.
- Fuentes de datos y orden de fallback.
- Siembra ClubElo, replay y regla de equipos nuevos.
- Davidson y Dixon-Coles.
- Desempates UCL.
- SimulaciÃ³n de playoff.
- Limitaciones.

### 9.5 Estados de UI

- Carga con esqueletos.
- Error de conexiÃ³n con reintento.
- Aviso visible si `demo` es verdadero.
- Aviso si hay partidos aplazados o sin marcador.
- Responsive: tabla con scroll horizontal en mÃ³vil; tarjetas apiladas.

## 10. Testing

### 10.1 Backend

- Parser OpenFootball: `cl.txt` de 2025/26 devuelve 189 partidos, 144 de fase
  de liga, 36 equipos y marcadores correctos.
- Parser API-Football: rondas, ida/vuelta, final neutral y marcador a 90
  minutos.
- Desempates: puntos, diferencia, goles, goles fuera, victorias, victorias
  fuera y sorteo.
- Playoff: emparejamientos, agregado, prÃ³rroga y penaltis.
- SimulaciÃ³n:
  - probabilidades suman 1;
  - top 8 + playoff + eliminado = 1;
  - octavos = top 8 + playoff ganado;
  - misma semilla, mismo resultado;
  - partidos jugados se respetan.
- ELO: siembra ClubElo, replay, equipos nuevos y verificaciÃ³n.
- API: endpoints, esquemas y modo demo.

Comando:

```powershell
cd backend
python -m pytest tests -q
```

### 10.2 Frontend

```powershell
cd frontend
npm run lint
npm run build
```

ComprobaciÃ³n manual de `/champions`, `/champions/playoff`,
`/champions/elo` y `/champions/metodologia` en escritorio y mÃ³vil.

## 11. Criterios de aceptaciÃ³n

1. La app muestra la tabla real de 36 equipos con los partidos de 2026/27 ya
   jugados y los pendientes.
2. El ELO de cada equipo se reconstruye desde ClubElo y el replay de 2025/26;
   la verificaciÃ³n indica partidos y equipos resueltos.
3. La proyecciÃ³n devuelve probabilidades de top 8, playoff, eliminaciÃ³n y
   octavos que suman de forma coherente.
4. El playoff muestra emparejamientos 9-24, probabilidad de avance y rivales
   mÃ¡s probables.
5. La UI distingue claramente datos reales de modo demo.
6. Las rutas y tests de LaLiga siguen funcionando.
7. `pytest`, `npm run lint` y `npm run build` pasan.

## 12. Riesgos y mitigaciones

| Riesgo | MitigaciÃ³n |
| --- | --- |
| API-Football sin cuota o sin clave | Fallback OpenFootball, cachÃ© y demo etiquetado. |
| OpenFootball no publica 2026/27 | API-Football como principal; cachÃ© editable; aviso en UI. |
| Nombres de equipos inconsistentes | Mapa de alias por proveedor y tests de resoluciÃ³n. |
| Muestra corta para calibrar Davidson | Split temporal, mÃ©tricas y fallback a parÃ¡metros de LaLiga. |
| ELO fijo durante la simulaciÃ³n | Documentado como limitaciÃ³n; misma convenciÃ³n que SimuLiga. |
| RegresiÃ³n en LaLiga | Paquete aislado, router separado y tests existentes. |

## 13. Mapa de archivos previsto

| Archivo | Cambio |
| --- | --- |
| `backend/app/champions/**` | Nuevo paquete. |
| `backend/app/api/main.py` | Registrar router de Champions. |
| `backend/app/data/champions_historical.json` | Nuevo, generado por script. |
| `backend/app/data/champions_params.json` | Nuevo, generado por script. |
| `backend/scripts/calibrate_champions.py` | Nuevo. |
| `backend/scripts/verify_champions.py` | Nuevo. |
| `backend/tests/test_champions_*.py` | Nuevos. |
| `frontend/app/champions/**` | Nuevas rutas. |
| `frontend/components/champions/**` | Nuevos componentes. |
| `frontend/components/CompetitionSwitch.tsx` | Nuevo. |
| `frontend/components/SiteNav.tsx` | NavegaciÃ³n segÃºn competiciÃ³n. |
| `frontend/app/layout.tsx` | Marca y selector segÃºn ruta. |
| `frontend/lib/champions-api.ts` | Nuevo. |
| `frontend/lib/champions-types.ts` | Nuevo. |
| `frontend/app/globals.css` | Estilos `.champions-*`. |
| `docs/champions.md` | DocumentaciÃ³n funcional. |
| `docs/champions-calibration.md` | Informe de calibraciÃ³n. |

