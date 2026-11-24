# Spike: ClubElo como semilla/prior del ELO de Champions

Experimento throwaway. No modifica el ELO de producción.

## Backtest 2020/21–2024/25 → 2025/26

| Modelo | Accuracy | Log-loss | Brier | Spearman | Top-8 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CL-only 5 temporadas | 0.5079 | 0.9869 | 0.5852 | 0.5643 | 5/8 |
| ClubElo 2025-08-01 | 0.5979 | 0.9711 | 0.5688 | 0.7028 | 5/8 |
| Blend CL 0.75 + ClubElo | 0.5926 | 0.9697 | 0.5710 | 0.6331 | 5/8 |
| Blend CL 0.50 + ClubElo | 0.5873 | 0.9621 | 0.5651 | 0.6693 | 5/8 |
| Blend CL 0.25 + ClubElo | 0.6085 | 0.9630 | 0.5651 | 0.6907 | 5/8 |
| Replay 5y seed ClubElo 2020 | 0.5714 | 0.9764 | 0.5772 | 0.6069 | 5/8 |
| Replay 5y prior ClubElo w=1.00 | 0.5926 | 0.9811 | 0.5745 | 0.7497 | 5/8 |
| Replay 5y prior ClubElo w=0.75 | 0.6032 | 0.9773 | 0.5738 | 0.7384 | 5/8 |
| Replay 5y prior ClubElo w=0.50 | 0.5873 | 0.9741 | 0.5734 | 0.7329 | 5/8 |
| Replay 5y prior ClubElo w=0.25 | 0.5873 | 0.9718 | 0.5732 | 0.6755 | 5/8 |

## 2026/27 pre-temporada (vs puntos actuales)

| Modelo | Spearman | Top-8 |
| --- | ---: | ---: |
| CL-only | 0.5705 | 3/8 |
| ClubElo 2026-08-01 | 0.5209 | 3/8 |
| Prior ClubElo w=0.50 | 0.5424 | 4/8 |
| Prior ClubElo w=1.00 | 0.5767 | 4/8 |

## Mejores

- Log-loss: Blend CL 0.50 + ClubElo (0.9621).
- Spearman: Replay 5y prior ClubElo w=1.00 (0.7497).
- Top-8: CL-only 5 temporadas (5/8).

## Lectura

- ClubElo se toma de snapshots históricos del dataset abierto de xgabora (2000–2026).
- El backtest usa ClubElo al 2025-08-01 para predecir 2025/26; no hay fuga del holdout.
- Las variantes 'prior ClubElo' mezclan el rating del replay con el snapshot de ClubElo al inicio de cada temporada.
- La sección 2026/27 usa ratings pre-temporada (sin partidos 2026/27) contra los puntos actuales; la muestra es pequeña y ruidosa.
- No se incluye el modelo que rejuega 2025/26 y evalúa sobre esos mismos partidos porque sería in-sample.
