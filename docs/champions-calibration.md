# Calibración de SimuChampions

Informe del replay de ELO de cinco temporadas y del ajuste de Davidson para la
Champions League. Se reproduce con:

```powershell
cd backend
python scripts/calibrate_champions.py
python scripts/verify_champions.py
python scripts/validate_champions_elo.py
```

## 1. Replay de ELO

- Ventana: 2021/22–2025/26, cinco temporadas de Champions.
- Fuente: OpenFootball.
- Partidos: 753, todos con marcador aplicado.
- Equipos históricos: 72.
- Replay cronológico con `K=20`, `H=60` y multiplicador por margen de goles.
- Regresión al inicio de cada temporada: 20 % hacia 1500,
  `nuevo = actual + 0.20 * (1500 - actual)`.
- Prior ClubElo: snapshots al inicio de cada temporada desde
  `app/data/clubelo_snapshots.json`, mezclados con peso 0.75:
  `rating = 0.25 * replay + 0.75 * ClubElo`.
- La semilla es ClubElo (`seed_source = "clubelo"`). Si no hay dato para un
  equipo, se usa 1500 o la media de los ratings conocidos.
- La temporada 2026/27 arranca desde el rating post-regresión, aplica el prior
  ClubElo de `2026-08-01` y después los partidos ya jugados.
- La final se trata como campo neutral y se usa el marcador a 90 minutos.

## 2. Calibración de Davidson

- Temporada de calibración: 2025/26.
- Ratings de partida: inicio de 2025/26 del replay con prior ClubElo.
- Entrenamiento: jornadas 1–6 de la fase de liga.
- Validación: jornadas 7–8, playoff y eliminatorias.
- Ajuste final: toda la temporada.

| Parámetro | Valor |
| --- | ---: |
| `H` final (ventaja de casa) | 34,4070 |
| `nu` final (empates) | 0,5152 |
| Escala ELO | 400 |
| Partidos de validación | 81 |
| Accuracy de validación | 0,6049 |
| Log-loss de validación | 0,9775 |
| Brier de validación | 0,5762 |
| `H` de entrenamiento | 23,0265 |
| `nu` de entrenamiento | 0,5673 |

La diferencia entre el `H` de entrenamiento y el final indica sensibilidad a la
muestra. El ajuste final se conserva para producción.

## 2b. Calibración del marcador exacto

El marcador exacto usa un modelo Dixon-Coles con goles esperados derivados del
ELO. Sus parámetros se ajustan por máxima verosimilitud sobre los marcadores
reales:

- Temporada base: 2025/26 (188 partidos; se excluyen los neutrales).
- `home_advantage` queda fijado al valor calibrado de Davidson para no duplicar
  fuentes.
- En producción se añaden los partidos ya jugados de 2026/27, siempre con los
  ratings previos a cada partido. Si hay menos de 30 muestras se conservan los
  parámetros guardados.

| Parámetro | Valor |
| --- | ---: |
| `home_base` | 1,815 |
| `away_base` | 1,477 |
| `elo_slope` | 0,00146 |
| `rho` | -0,0603 |
| `home_advantage` | 34,41 |

En el backtest de las jornadas 1–3 de 2026/27, el ajuste baja el log-loss del
marcador de 3,515 a 3,322 y el log-loss 1X2 de 0,851 a 0,837. Los goles
esperados medios pasan de 2,84 a 3,49 por partido (4,09 reales).

## 3. Validación

El backtest completo, las correlaciones y la búsqueda de alpha/K están en
[`docs/champions-elo-5y-validation.md`](champions-elo-5y-validation.md).

Backtest limpio: 2020/21–2024/25 → 2025/26, 189 partidos de validación.
Cada modelo usa Davidson ajustado solo con 2024/25.

| Modelo | Accuracy | Log-loss | Brier | Spearman | Top-8 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5 temporadas CL-only | 0,5079 | 0,9869 | 0,5852 | 0,5643 | 5/8 |
| 5 temporadas + prior ClubElo 75 % | **0,5979** | **0,9708** | **0,5714** | **0,7211** | 5/8 |
| 1 temporada | 0,5608 | 1,0042 | 0,5990 | 0,4035 | 5/8 |
| 1500 plano | 0,4974 | 1,0404 | 0,6296 | 0,0000 | 0/8 |

- El prior ClubElo mejora log-loss, Brier, accuracy y Spearman.
- Spearman con los puntos de 2025/26: **0,7211** (objetivo ≥ 0,60).
- Solapamiento del top 8: **5/8** (objetivo ≥ 6/8). Sigue corto: el top 8 real
  de 2025/26 incluye sorpresas como Tottenham, Chelsea y Sporting.
- Spearman con los puntos actuales de 2026/27: **0,6914**, calculado sobre el
  snapshot de producción con 54 partidos jugados. Es una comprobación
  in-sample, no una predicción fuera de muestra.
- El grid alpha/K de CL-only se conserva como referencia metodológica, pero el
  modelo de producción es el de prior ClubElo w=0,75.

## 4. Limitaciones

- Solo Champions en el replay: el prior ClubElo aporta la señal doméstica.
- El prior cubre 53 de los 72 equipos históricos; el resto usa 1500 o la media.
- La muestra de validación es una temporada.
- El top 8 sigue por debajo del objetivo; el ranking global sí mejora.
- El experimento de añadir resultados domésticos al replay mejoró calibración
  pero empeoró ranking, así que se descartó.
- La correlación de 2026/27 incluye partidos ya aplicados al rating de
  producción y no sustituye al backtest fuera de muestra.
