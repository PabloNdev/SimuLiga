# Validación del ELO de 5 temporadas

Backtest: 2020/21–2024/25 → 2025/26

Calibración Davidson ajustada solo con 2024/25 del training. CL-only: H=9.5533, nu=0.3335. Prior ClubElo: H=22.4081, nu=0.3670.

## Comparación de ratings

| Modelo | Partidos | Accuracy | Log-loss | Brier |
| --- | ---: | ---: | ---: | ---: |
| 5 temporadas | 189 | 0.5079 | 0.9869 | 0.5852 |
| 5 temporadas + prior ClubElo 75% | 189 | 0.5979 | 0.9708 | 0.5714 |
| 1 temporada | 189 | 0.5608 | 1.0042 | 0.5990 |
| 1500 plano | 189 | 0.4974 | 1.0404 | 0.6296 |

## Correlación y top 8

- Spearman con puntos de 2025/26 (CL-only): 0.5643
- Solapamiento top 8 (CL-only): 5/8
- Spearman con puntos de 2025/26 (prior ClubElo): 0.7211
- Solapamiento top 8 (prior ClubElo): 5/8
- Spearman con puntos actuales de 2026/27 (snapshot de producción, 54 partidos de liga jugados): 0.6914

## Búsqueda de alpha y K

| alpha | K | Accuracy | Log-loss | Brier | Spearman | Top-8 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | 16 | 0.5185 | 0.9866 | 0.5851 | 0.5468 | 5/8 |
| 0.0 | 20 | 0.5026 | 0.9833 | 0.5828 | 0.5525 | 5/8 |
| 0.0 | 24 | 0.5026 | 0.9814 | 0.5817 | 0.5426 | 5/8 |
| 0.1 | 16 | 0.5185 | 0.9889 | 0.5867 | 0.5429 | 5/8 |
| 0.1 | 20 | 0.5026 | 0.9846 | 0.5835 | 0.5429 | 5/8 |
| 0.1 | 24 | 0.5026 | 0.9818 | 0.5816 | 0.5426 | 5/8 |
| 0.2 | 16 | 0.5185 | 0.9917 | 0.5888 | 0.5553 | 5/8 |
| 0.2 | 20 | 0.5079 | 0.9869 | 0.5852 | 0.5643 | 5/8 |
| 0.2 | 24 | 0.5026 | 0.9834 | 0.5826 | 0.5413 | 4/8 |
| 0.3 | 16 | 0.5291 | 0.9947 | 0.5912 | 0.5349 | 4/8 |
| 0.3 | 20 | 0.5132 | 0.9895 | 0.5871 | 0.5344 | 4/8 |
| 0.3 | 24 | 0.5079 | 0.9856 | 0.5842 | 0.5297 | 4/8 |

Configuraciones del grid que cumplen Spearman >= 0.60 y top 8 >= 6/8: 0 de 12.
- Ninguna configuración del grid cumple ambos criterios de ranking.

## Mejores combinaciones

| Criterio | alpha | K | Log-loss | Brier | Spearman | Top-8 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Mejor log-loss | 0.0 | 24 | 0.9814 | 0.5817 | 0.5426 | 5/8 |
| Mejor Brier | 0.1 | 24 | 0.9818 | 0.5816 | 0.5426 | 5/8 |
| Mejor Spearman | 0.2 | 20 | 0.9869 | 0.5852 | 0.5643 | 5/8 |
| Mejor top 8 | 0.0 | 16 | 0.9866 | 0.5851 | 0.5468 | 5/8 |

## Recomendaciones

- El modelo de producción usa prior ClubElo w=0.75 sobre el replay de cinco temporadas.
- El grid alpha/K de CL-only se mantiene como referencia metodológica; no es el modelo de producción.
- Criterios del modelo de producción: log-loss OK (0.9708), Spearman OK (0.7211), top 8 NO (5/8).
- Si el top 8 sigue corto, el siguiente paso es añadir otra señal de nivel actual (coeficiente UEFA, valor de plantilla o forma reciente) o aceptar la limitación.
- Mantener el análisis doméstico como experimento descartado: mejora calibración pero empeora ranking.

## Criterios

- Log-loss del modelo de producción (prior ClubElo) menor que 1 temporada y que 1500: sí (0.9708 vs 1.0042 vs 1.0404).
- Spearman del modelo de producción (prior ClubElo) con puntos de 2025/26 >= 0.60: sí (0.7211).
- Top 8 compartido del modelo de producción >= 6/8: no (5/8).
- Ranking de producción plausible: comprobado contra el snapshot de producción de 2026/27.
