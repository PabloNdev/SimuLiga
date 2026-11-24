# Calibración de los ELO de inicio de 2026/27

Análisis estadístico de los ratings congelados al inicio de la temporada
2026/27, evaluados contra los partidos reales ya disputados. Tras ampliar la
reconstrucción histórica a **2020/21–2024/25** (cinco temporadas), el objetivo
es responder:

1. ¿Están bien calibrados los ELO de inicio?
2. ¿Mejora la calibración al pasar de tres a cinco temporadas?

El análisis es reproducible con:

```powershell
cd backend
python scripts/analyze_elo_calibration.py
```

## 1. Resumen ejecutivo

- **No hay evidencia fuerte de mala calibración.** El factor de dispersión
  estimado es `alpha = 1,657`, pero su intervalo de perfil al 95% es
  `[0,95; 2,49]`, que incluye 1. El test de razón de verosimilitud no rechaza
  `alpha = 1` (`p = 0,070`).
- **Los ELO de inicio aportan información.** Frente a un modelo sin ELO,
  mejoran el log-loss de `1,078` a `0,952`; la diferencia pareada es `−0,126`
  `[−0,196; −0,061]`.
- **La calibración de H y nu con 2020/21–2023/24 sigue siendo compatible con
  2026/27.** El ajuste sobre 2026/27 da `H = 84,58` y `nu = 0,893`, valores
  dentro de intervalos amplios que contienen los de entrenamiento
  (`H = 83,26`, `nu = 0,818`); el test conjunto no rechaza (`p = 0,934`).
- **Cinco temporadas mejoran ligeramente el prior.** Log-loss `0,956 → 0,952`,
  Brier `0,565 → 0,563`, ECE local `0,138 → 0,112`, ECE empate `0,061 → 0,043`.
  El empate pasa de subpredictirse 3,3 pp a 1,7 pp.
- **La muestra de evaluación sigue siendo corta.** 88 partidos y 9 jornadas.
  Los intervalos son anchos; las conclusiones deben revisarse al completar la
  temporada.
- **Cinco temporadas bastan para el nivel de liga, no para afinar cada equipo.**
  El movimiento medio de un rating tras una sola temporada (2025/26) es de
  `36,1` puntos (máximo `145,6`), comparable a la desviación entre equipos
  (`109,9`). La incertidumbre individual sigue siendo relevante, sobre todo en
  ascendidos.

## 2. Datos y método

### 2.1 Muestra

- **Partidos evaluados:** 88 partidos jugados de 2026/27 (jornadas 1–9).
- **Resultados:** 38 victorias locales, 25 empates, 25 victorias visitantes.
- **Equipos:** 20.
- **Ratings evaluados:** `elo_by_matchday[1]`, el rating congelado al inicio de
  2026/27, antes de aplicar ningún resultado de la temporada actual.
- **Resultados reales:** los del snapshot 2026/27 de OpenFootball +
  football-data.co.uk.

### 2.2 Modelo

Para cada partido se calculan las probabilidades 1X2 con el modelo Davidson y
los parámetros calibrados con 2020/21–2023/24 y ajustados finalmente sobre
2020/21–2024/25:

```text
fuerza = 10^((delta_elo + H) / 400)
P(local)     = fuerza / (fuerza + 1 + nu·sqrt(fuerza))
P(empate)    = nu·sqrt(fuerza) / (fuerza + 1 + nu·sqrt(fuerza))
P(visitante) = 1 / (fuerza + 1 + nu·sqrt(fuerza))

H  = 83,2599
nu = 0,8177
```

`delta_elo` es la diferencia de los ratings de inicio. No se actualizan los
ratings: se mide el prior de pretemporada.

### 2.3 Comparaciones

1. **Prior congelado:** los ratings de inicio para los 88 partidos.
2. **Walk-forward:** se actualiza el ELO después de cada partido con la fórmula
   habitual (`K = 20`, `H = 60`) y se predice el siguiente. Es el comportamiento
   real de la app.
3. **Sin ELO:** todos los equipos iguales (`delta_elo = 0`), con la misma `H` y
   `nu`. Mide si los ratings aportan algo más que la ventaja de casa.

### 2.4 Métricas

- **Accuracy:** acierto de la clase más probable.
- **Log-loss:** pérdida logarítmica media; menor es mejor.
- **Brier multiclase:** media de la suma de errores cuadráticos por partido;
  menor es mejor.
- **ECE:** error de calibración esperado por clase, en bins de 0,1.
- **Intervalos:** bootstrap de 800 remuestreos para métricas y `alpha`; 300 para
  `H` y `nu`.
- **Dispersión:** se ajusta un factor `alpha` que multiplica la diferencia de
  ELO. `alpha = 1` significa que la dispersión actual es la adecuada;
  `alpha < 1` indica ratings demasiado separados; `alpha > 1`, demasiado juntos.
  El intervalo principal es el de perfil de verosimilitud.

## 3. Resultados

### 3.1 Métricas globales

| Modelo | Accuracy | Log-loss | Brier |
| --- | ---: | ---: | ---: |
| ELO de inicio (prior) | 0,4773 | 0,9520 | 0,5629 |
| Walk-forward (ELO actualizado) | 0,5000 | 0,9525 | 0,5632 |
| Sin ELO (equipos iguales) | 0,4318 | 1,0780 | 0,6523 |

Intervalos bootstrap del prior:

- Accuracy: `[0,375; 0,580]`
- Log-loss: `[0,868; 1,032]`
- Brier: `[0,504; 0,620]`

Brier por clase: local `0,2035`, empate `0,1969`, visitante `0,1625`.

Diferencias pareadas de log-loss:

- Prior − walk-forward: `−0,0005` `[−0,0120; +0,0109]`. Actualizar el ELO
  durante las primeras 9 jornadas no mejora de forma apreciable.
- Prior − sin ELO: `−0,1260` `[−0,1964; −0,0609]`. Los ratings sí aportan.

### 3.2 Predicción media vs observación

| Clase | Predicción media | Frecuencia observada | Diferencia |
| --- | ---: | ---: | ---: |
| Local | 0,4410 | 0,4318 | −0,0092 |
| Empate | 0,2667 | 0,2841 | +0,0174 |
| Visitante | 0,2924 | 0,2841 | −0,0083 |

La media está más cerca que con la calibración de tres temporadas. El empate se
predice 1,7 puntos porcentuales por debajo de lo observado; la victoria local,
0,9 puntos por encima.

### 3.3 Fiabilidad por bins

**Victoria local** (ECE `0,1116`):

| Bin | n | Predicho | Observado | Gap |
| --- | ---: | ---: | ---: | ---: |
| 0,1–0,2 | 6 | 0,138 | 0,000 | −0,138 |
| 0,2–0,3 | 11 | 0,259 | 0,273 | +0,014 |
| 0,3–0,4 | 13 | 0,351 | 0,385 | +0,033 |
| 0,4–0,5 | 28 | 0,446 | 0,286 | −0,160 |
| 0,5–0,6 | 17 | 0,532 | 0,647 | +0,116 |
| 0,6–0,7 | 6 | 0,645 | 0,667 | +0,022 |
| 0,7–0,8 | 7 | 0,740 | 1,000 | +0,260 |

**Empate** (ECE `0,0426`):

| Bin | n | Predicho | Observado | Gap |
| --- | ---: | ---: | ---: | ---: |
| 0,1–0,2 | 6 | 0,185 | 0,000 | −0,185 |
| 0,2–0,3 | 82 | 0,273 | 0,305 | +0,032 |

**Victoria visitante** (ECE `0,0710`):

| Bin | n | Predicho | Observado | Gap |
| --- | ---: | ---: | ---: | ---: |
| 0,0–0,1 | 7 | 0,072 | 0,000 | −0,072 |
| 0,1–0,2 | 13 | 0,156 | 0,077 | −0,079 |
| 0,2–0,3 | 35 | 0,251 | 0,229 | −0,023 |
| 0,3–0,4 | 14 | 0,341 | 0,286 | −0,056 |
| 0,4–0,5 | 12 | 0,447 | 0,417 | −0,031 |
| 0,5–0,6 | 3 | 0,556 | 1,000 | +0,444 |
| 0,6–0,7 | 4 | 0,643 | 1,000 | +0,357 |

Los bins altos de visitante tienen muy pocos casos (3–4), por lo que sus gaps
no son concluyentes. El bin 0,4–0,5 de local (28 partidos, 28,6% de victorias
locales) sigue siendo el que más pesa en el ECE local.

### 3.4 Dispersión de los ratings

| Parámetro | Estimación | Intervalo bootstrap | Intervalo de perfil |
| --- | ---: | ---: | ---: |
| `alpha` | 1,6572 | `[1,018; 2,583]` | `[0,950; 2,490]` |
| Escala implícita (`400/alpha`) | 241,4 | — | — |

- `H0: alpha = 1`: LR `3,274`, `p = 0,070`. No se rechaza al 5%.
- El perfil incluye 1, así que **no hay evidencia sólida de sobre/subdispersión**.
- El punto estimado sugiere que los ratings podrían estar algo **juntos**
  (`alpha > 1`), no demasiado separados. Si se confirmara, la escala efectiva
  sería ~241 en lugar de 400. Pero el intervalo es amplio.

### 3.5 Recalibración de H y nu

| Parámetro | 2026/27 | IC bootstrap 95% | Entrenamiento 2020/21–2023/24 |
| --- | ---: | ---: | ---: |
| `H` | 84,58 | `[3,75; 174,94]` | 83,26 |
| `nu` | 0,8933 | `[0,529; 1,381]` | 0,8177 |

- Test conjunto `H = 83,26` y `nu = 0,8177`: LR `0,136`, `p = 0,934`. No se
  rechaza.
- El `nu` puntual es más alto (más empates), coherente con la subpredicción de
  empates, pero el intervalo contiene el valor de entrenamiento.
- La `H` es prácticamente idéntica; el intervalo es muy ancho porque 88
  partidos no identifican bien la ventaja de casa y el empate a la vez.

### 3.6 Validez predictiva y sensibilidad

- **Spearman** entre rating de inicio y puntos por partido tras 9 jornadas:
  `0,5991`.
- **Pendiente:** `+0,464` puntos por partido por cada 100 puntos de ELO.
- **Movimiento 2025/26:** media absoluta `36,1` puntos; máximo `145,6`;
  desviación `50,9`.
- **Desviación de los ratings de inicio:** `109,9` puntos.

Lectura: los ratings ordenan razonablemente a los equipos y la pendiente es
positiva, pero la incertidumbre de un rating individual es del mismo orden que
el movimiento de una sola temporada. Un equipo puede moverse 36–51 puntos por
una temporada normal; la separación entre equipos es de ~110 puntos. Eso limita
la precisión individual, no tanto la calibración global.

### 3.7 Por tramos de jornadas

| Tramo | n | Log-loss prior | Log-loss walk-forward | Accuracy prior | Accuracy walk-forward |
| --- | ---: | ---: | ---: | ---: | ---: |
| J1–J3 | 30 | 0,9321 | 0,9329 | 0,500 | 0,500 |
| J4–J6 | 29 | 0,9887 | 0,9899 | 0,448 | 0,483 |
| J7–J9 | 29 | 0,9358 | 0,9353 | 0,483 | 0,517 |

No se aprecia degradación clara del prior con las jornadas; el tramo J4–J6 es
el peor para ambos modelos, pero las diferencias están dentro del ruido.

## 4. Comparación con la calibración de tres temporadas

| Métrica | 3 temporadas (2022–2024) | 5 temporadas (2020–2024) |
| --- | ---: | ---: |
| `H` final | 85,70 | 83,26 |
| `nu` final | 0,7541 | 0,8177 |
| Validación 2024/25: accuracy | 0,5395 | 0,5421 |
| Validación 2024/25: log-loss | 0,9802 | 0,9771 |
| Validación 2024/25: Brier | 0,5823 | 0,5802 |
| Prior 2026/27: log-loss | 0,9560 | 0,9520 |
| Prior 2026/27: Brier | 0,5651 | 0,5629 |
| ECE local | 0,1377 | 0,1116 |
| ECE empate | 0,0606 | 0,0426 |
| ECE visitante | 0,0744 | 0,0710 |
| `alpha` | 1,6535 | 1,6572 |
| Perfil de `alpha` | [0,94; 2,49] | [0,95; 2,49] |
| Spearman | 0,5635 | 0,5991 |
| Baseline ascenso 2025/26 | 1369,72 | 1377,05 |
| Baseline ascenso 2026/27 | 1427,69 | 1437,93 |

La ampliación mejora ligeramente la validación y la fiabilidad del empate, y
mantiene las conclusiones: no hay evidencia de mala calibración, pero la
muestra de 2026/27 sigue siendo corta.

## 5. Interpretación

### ¿Están bien calibrados los ELO de inicio?

**Sí, de forma razonable para ser un prior de pretemporada.** La evidencia:

- No se rechaza `alpha = 1` ni la `H`/`nu` de entrenamiento.
- Las probabilidades medias están cerca de las frecuencias observadas.
- Los ratings baten claramente al modelo sin ELO.
- El walk-forward no mejora al prior en 9 jornadas.
- La ampliación a cinco temporadas mejora ligeramente las métricas.

**Pero no están perfectamente calibrados.** Hay señales que merecen seguimiento:

- El empate se subpredice ~1,7 pp (antes 3,3 pp).
- El ECE de la victoria local sigue siendo alto (0,112), aunque dominado por
  bins con pocos casos y por el bin 0,4–0,5.
- El punto estimado de `alpha` (1,66) sugiere que los ratings podrían estar
  demasiado juntos; el intervalo es amplio y no concluyente.

### ¿Bastan cinco temporadas?

**Para el nivel de liga, sí; para afinar cada equipo, sigue siendo justo.**

- La calibración de `H`/`nu` usa 1.520 partidos de entrenamiento (4 temporadas)
  y 380 de validación (2024/25). Los parámetros de 2020–2023 siguen siendo
  compatibles con 2026/27.
- Los ratings individuales acumulan ~190 partidos por equipo en 5 temporadas
  (más los de 2025/26). Es suficiente para una fuerza media, pero no para
  distinguir con precisión a equipos separados por 20–30 puntos.
- El movimiento de una sola temporada (`36,1` puntos de media, `145,6` máximo)
  es del orden de la desviación entre equipos (`109,9`). Los ratings de
  ascendidos y de equipos con poca historia son los más frágiles.
- Cinco temporadas es una base más estable que tres; alargar a 7–10 años o
  aplicar shrinkage bayesiano ayudaría a estabilizar los ratings individuales.

## 6. Recomendaciones

1. **Mantener `H = 83,26` y `nu = 0,8177`** por ahora. No hay evidencia
   suficiente para recalibrar con 88 partidos.
2. **No aplicar todavía un factor de shrinkage/expansión** a los ratings. El
   punto estimado sugiere expandir ligeramente (`alpha > 1`), pero el intervalo
   incluye 1 y el test no rechaza. Revisar cuando haya 20–25 jornadas o al
   final de la temporada.
3. **Vigilar el empate.** La subpredicción se redujo a 1,7 pp; si persiste, un
   `nu` algo mayor (~0,85–0,90) mejoraría la calibración de las tablas.
4. **Reforzar la estabilidad individual.** Para equipos con poca historia
   (ascendidos, recién llegados), considerar un prior más fuerte hacia la media
   de la liga o una ventana histórica más larga.
5. **Repetir el análisis al final de la temporada.** Con 380 partidos, el
   intervalo de `alpha` se reducirá mucho y permitirá decidir con más base si
   la escala de 400 y la dispersión actual son las correctas.
6. **Mantener el walk-forward.** No mejora en 9 jornadas, pero tampoco empeora;
   a medida que avance la temporada capturará forma y cambios.

## 7. Limitaciones

- **Muestra pequeña y parcial:** 88 partidos de las primeras 9 jornadas, con
  aplazados. No es una muestra aleatoria de toda la temporada.
- **Evaluación del prior:** el prior congelado se usa para todos los partidos,
  incluso los de la jornada 9. Es una prueba dura del prior; el walk-forward es
  el comportamiento real de la app. Ambos dan resultados casi idénticos.
- **Datos históricos:** 2020/21–2024/25 provienen de football-data.co.uk. La
  temporada 2025/26 depende de OpenFootball y del relleno con
  football-data.co.uk; los 15 partidos rellenados están incluidos.
- **Parámetros:** la `H` de Davidson (83,26) no es la misma que la `H` de
  actualización del ELO (60). El análisis usa la primera porque es la que genera
  las probabilidades 1X2.
- **Intervalos:** los bootstrap no corrigen la dependencia entre partidos de un
  mismo equipo; los intervalos son una guía, no una inferencia exacta.
- **Lesiones, fichajes y contexto:** no están en el modelo. Una parte del error
  de calibración puede deberse a cambios de plantilla no observados.

## 8. Reproducción

```powershell
cd backend
python scripts/calibrate_history.py
python scripts/analyze_elo_calibration.py
```

El primer script regenera `historical_ratings.json` y `calibrated_params.json`
con las cinco temporadas. El segundo imprime todas las tablas anteriores.
Requiere `DATA_SOURCE=openfootball` para el snapshot de 2026/27.

## 9. Archivos

| Archivo | Uso |
| --- | --- |
| `backend/scripts/calibrate_history.py` | Reconstrucción 2020/21–2024/25 y calibración temporal |
| `backend/scripts/analyze_elo_calibration.py` | Análisis completo y reproducible |
| `backend/app/data/calibrated_params.json` | `H`, `nu` y temporadas de entrenamiento |
| `backend/app/data/historical_ratings.json` | Ratings históricos, participantes y descensos |
| `backend/app/data/league.py` | Snapshot y `elo_by_matchday[1]` |
| `docs/elo.md` | Documentación del cálculo y del gráfico |
