# SimuChampions — ELO de 5 temporadas

Fecha: 2026-10-24
Estado: diseño aprobado por el usuario
Ámbito: reconstrucción del ELO del módulo de Champions League

## 1. Objetivo

El ELO actual de Champions se construye con una sola temporada (2025/26) y los
partidos ya jugados de 2026/27. Eso produce ratings comprimidos y poco
representativos del nivel actual de cada club. El objetivo es reconstruir el ELO
con un replay de cinco temporadas de Champions League, dar más peso al presente
y validar objetivamente si el resultado se ajusta al nivel actual.

## 2. Alcance

### 2.1 Incluido

1. Replay de las temporadas 2021/22, 2022/23, 2023/24, 2024/25 y 2025/26.
2. Regresión del 20 % hacia 1500 al inicio de cada temporada.
3. Aplicación de la temporada activa 2026/27 sobre el rating resultante.
4. Normalización de nombres históricos de OpenFootball para no dividir un club
   en varios ids.
5. Verificación ampliada en la API y en la página de ELO.
6. Backtest temporal, correlación de rangos y sanity check del top 8.
7. Script de validación reproducible y actualización de la documentación.

### 2.2 Fuera de alcance

- Ligas domésticas o competiciones europeas distintas de la Champions.
- Lesiones, sanciones, alineaciones, mercado o coeficiente UEFA.
- Cambios en la simulación de LaLiga.
- Cambios en el formato o en la simulación de la fase de liga de Champions.

## 3. Datos

- Fuente: OpenFootball `champions-league/<temporada>/cl.txt`.
- Ventana de producción: 2021/22 a 2025/26.
- Partidos: 753 en total (125 + 125 + 125 + 189 + 189).
- La temporada 2026/27 se sigue cargando con la fuente actual (local o
  API-Football) y no forma parte del replay histórico.
- Cada temporada se cachea por separado. Si una temporada histórica no está
  disponible, se usa el histórico disponible, se marca `history_complete=false`
  y se informa en la UI. No se cae a modo demo por este motivo.
- El backtest usa además 2020/21 para poder evaluar una ventana móvil completa de
  cinco temporadas (2020/21–2024/25) contra 2025/26.

### 3.1 Configuración nueva

```dotenv
CHAMPIONS_HISTORY_SEASONS=5
CHAMPIONS_SEASON_REGRESSION=0.20
```

Valores por defecto en `ChampionsSettings`:

- `history_seasons: int = 5`
- `season_regression: float = 0.20`

La ventana se calcula hacia atrás desde `previous_season`. Con
`previous_season=2025`, las temporadas son 2021 a 2025.

## 4. Identidad de equipos

OpenFootball usa nombres históricos distintos para el mismo club. Ejemplos
detectados: `Bayern München`, `Aston Villa FC`, `Lille OSC`,
`Real Sociedad de Fútbol`, `Sevilla FC`, `SL Benfica`, `Racing Club de Lens`,
`ŠK Slovan Bratislava`, `GNK Dinamo Zagreb`, `RB Salzburg`.

Requisitos:

- Añadir alias para todos los nombres históricos que correspondan a clubes
  actuales del registro.
- Para clubes históricos que no están en el registro actual, usar un id
  canónico estable y agrupar sus variantes bajo ese id.
- `make_team` debe respetar el id canónico devuelto por `normalize_team_key`
  incluso cuando no exista un seed, en lugar de volver a derivar el id desde el
  nombre del proveedor.
- Añadir tests que cubran los alias actuales e históricos más importantes.

## 5. Cálculo del ELO

### 5.1 Semilla

- Si ClubElo está disponible al inicio de la ventana, se usa como semilla.
- En este entorno ClubElo no está disponible; todos los equipos parten de 1500.
- La verificación expone `seed_source` con el valor real.

### 5.2 Replay histórico

Se procesan las cinco temporadas en orden cronológico:

1. Al inicio de la primera temporada, todos los equipos parten de su semilla.
2. Al inicio de cada temporada posterior, se aplica:
   `nuevo = actual + alpha * (1500 - actual)`, con `alpha = season_regression`.
3. Se guarda el rating de inicio de la temporada.
4. Se procesan los partidos de la temporada en orden de fecha:
   - `K=20`.
   - `H=60` para partidos con localía; `H=0` para sede neutral.
   - Multiplicador por margen de goles ya existente en `update_ratings`.
   - Se usa el marcador a 90 minutos.
5. Se guarda el rating de final de temporada.
6. Se construye una serie temporal mensual con los ratings.

Los equipos que aparecen por primera vez en una temporada posterior permanecen
en 1500 hasta que juegan su primer partido. Los equipos que no participan en una
temporada conservan su rating y también reciben la regresión de esa frontera.

### 5.3 Temporada activa 2026/27

1. Se aplica la regresión de inicio de temporada a los ratings al final de
   2025/26.
2. Cada equipo actual toma su rating del replay.
3. Un equipo actual que no aparezca en el histórico usa ClubElo 2026 si está
   disponible; si no, la media de los ratings actuales conocidos.
4. Se aplican los partidos ya jugados de 2026/27 con las mismas reglas.
5. El rating final es el que se muestra en la tabla actual.
6. El rating de inicio de 2026/27 (post-regresión) es el que se muestra en la
   columna `Inicio` y se usa para calcular el delta de la temporada.

## 6. Calibración del modelo

- El replay histórico usa `K=20` y `H=60` para construir ratings, igual que
  antes.
- Davidson se recalibra sobre 2025/26 usando los ratings de inicio de esa
  temporada obtenidos del replay de cinco años.
- Se mantiene el esquema actual: jornadas 1–6 de la fase de liga para
  entrenamiento, resto de 2025/26 para validación y ajuste final con toda la
  temporada.
- `K`, `H` del replay y `nu` de Davidson se exponen en la API como hasta ahora.
- `calibrate_champions.py` y `verify_champions.py` usan la misma ventana de cinco
  temporadas y reportan el rango histórico aplicado.
- `champions_historical.json` mantiene `teams`, `final_ratings` y `season` (la
  última temporada histórica) para no romper el modo demo, y añade `seasons`,
  `season_start_ratings` y `season_end_ratings`.
- El modo demo sigue usando 2025/26 y no cambia de comportamiento.

## 7. API y verificación

`GET /api/champions/elo` y `GET /api/champions/season` deben seguir funcionando
con los mismos campos existentes. Se añaden a `verification`:

- `history_seasons`: número de temporadas usadas.
- `history_start`: etiqueta de la primera temporada.
- `history_end`: etiqueta de la última temporada histórica.
- `history_seasons_loaded`: lista de etiquetas cargadas.
- `history_complete`: booleano.
- `season_regression`: alpha aplicado.
- `history_matches_total`: partidos históricos totales.
- `history_matches_applied`: partidos históricos aplicados.
- `history_matches_without_score`: partidos históricos sin marcador.

`previous_season` se mantiene como 2025/26 y sigue siendo la temporada de
calibración. `matches_total` y `matches_applied` se mantienen para compatibilidad
con la UI actual, pero pasan a referirse al histórico completo. La UI mostrará
además los campos nuevos.

`elo_history` pasa a tener una entrada por temporada:

- `seasons`: 2021/22, 2022/23, 2023/24, 2024/25, 2025/26 y 2026/27.
- Cada serie contiene el rating de inicio de cada temporada.

`elo_timeline` cubre todo el replay histórico y la temporada activa.

## 8. UI

En `ChampionsElo`:

- Texto: “Rating reconstruido con el replay de las últimas 5 temporadas
  (2021/22–2025/26) y regresión del 20 % al inicio de cada temporada.”
- Chips: temporadas, partidos históricos aplicados, semilla y regresión.
- Panel de verificación: rango histórico, equipos resueltos, partidos sin
  marcador y estado de completitud.
- El gráfico de evolución muestra el rango 2021/22–2026/27.
- El estado de carga indica que se está recalculando el replay de cinco
  temporadas.

## 9. Validación

Se añade `backend/scripts/validate_champions_elo.py`. El script:

1. Carga 2020/21 a 2025/26 desde OpenFootball.
2. Construye el modelo de backtest con 2020/21–2024/25 y evalúa 2025/26.
3. Construye las siguientes referencias:
   - ELO de una temporada: 2024/25.
   - Ratings planos a 1500.
4. Usa los mismos parámetros de Davidson para las tres referencias, de modo que
   la comparación aísle el efecto de los ratings.
5. Calcula accuracy, log-loss y Brier sobre 2025/26.
6. Calcula la correlación de Spearman entre:
   - ratings de backtest y puntos/posición final de 2025/26;
   - ratings de producción y puntos actuales de 2026/27.
7. Calcula el solapamiento entre el top 8 de backtest y el top 8 final de
   2025/26.
8. Prueba `alpha` en 0, 0.1, 0.2 y 0.3, y `K` en 16, 20 y 24. Reporta la mejor
   combinación. La producción mantiene 0.20 salvo que el usuario apruebe otro
   valor.
9. Escribe un informe en `docs/champions-elo-5y-validation.md` con las tablas y
   una lectura de resultados.

### 9.1 Criterios de aceptación

- El log-loss del ELO de cinco años es menor que el de una temporada y que el de
  1500.
- Spearman con los puntos finales de 2025/26 es al menos 0.60.
- El top 8 de backtest comparte al menos 6 equipos con el top 8 final de 2025/26.
- El ranking de producción es plausible: los grandes europeos no quedan
  sistemáticamente por debajo de equipos con una sola buena temporada.
- Todos los tests existentes y nuevos pasan.

Si no se cumplen, el informe lo indica y se proponen ajustes concretos
(alpha, K o ventana). No se cambia el valor de producción sin aprobación.

## 10. Tests

Backend:

- Regresión de temporada: un rating 1600 con alpha 0.2 pasa a 1580.
- Cambio de temporada: la regresión se aplica exactamente una vez por frontera.
- Replay histórico: aplica todos los partidos con marcador y conserva la suma de
  ratings en partidos no neutrales.
- Nuevo equipo: empieza en 1500 y no se regresiona antes de jugar.
- Alias históricos: los nombres detectados resuelven al id esperado.
- Snapshot: `elo_history.seasons` contiene las seis etiquetas y cada serie tiene
  la misma longitud.
- Verificación: los campos nuevos están presentes y son coherentes.
- Backtest: con datos sintéticos, el ELO de cinco años produce métricas y no
  lanza errores.

Frontend:

- `npm run lint`.
- `npx tsc --noEmit`.
- `npm run build`.

## 11. Riesgos y limitaciones

- Solo Champions: un equipo fuerte en su liga pero con malos resultados europeos
  puede quedar infravalorado. El backtest dirá si el sesgo es aceptable.
- Los equipos que no jugaron la Champions en los últimos cinco años empiezan en
  1500 o en la media actual; su nivel doméstico no se captura.
- OpenFootball puede cambiar nombres o formato entre temporadas. Los alias y los
  tests de identidad reducen el riesgo.
- ClubElo no está disponible en este entorno; la semilla es 1500.
- La muestra de validación es una temporada; las métricas tienen ruido.
- El replay de 753 partidos es barato, pero la primera carga requiere descargar
  cinco ficheros. La caché y el TTL actual lo mitigan.

## 12. Archivos previstos

Backend:

- `app/champions/config.py`
- `app/champions/data/api_football.py`
- `app/champions/data/snapshot.py`
- `app/champions/names.py`
- `scripts/calibrate_champions.py`
- `scripts/verify_champions.py`
- `scripts/validate_champions_elo.py` (nuevo)
- `tests/test_champions_elo.py`
- `tests/test_champions_snapshot.py`
- `tests/test_champions_names.py` (nuevo)
- `tests/test_champions_api.py` (ajustes si cambian campos)

Frontend:

- `lib/champions-types.ts`
- `components/champions/ChampionsElo.tsx`

Documentación:

- `docs/champions.md`
- `docs/champions-calibration.md`
- `docs/champions-elo-5y-validation.md` (generado por el script)
