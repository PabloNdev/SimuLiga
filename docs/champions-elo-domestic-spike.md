# Spike: resultados domésticos en el ELO de Champions

Experimento throwaway. No modifica el ELO de producción.

## Cobertura

- Ligas: E0, SP1, D1, I1, F1, N1, P1, B1, T1, G1, SC0.
- Temporadas: 2020/21–2026/27.
- Clubes históricos de Champions con datos domésticos: 59/89.
- Clubes actuales 2026/27 con datos domésticos: 29/36.
- Partidos domésticos cargados: 21971.

## Backtest 2020/21–2024/25 → 2025/26

| Modelo | Accuracy | Log-loss | Brier | Spearman | Top-8 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CL-only 5 temporadas | 0.5079 | 0.9869 | 0.5852 | 0.5643 | 5/8 |
| CL-only 1 temporada | 0.5608 | 1.0042 | 0.5990 | 0.4035 | 5/8 |
| 1500 plano | 0.4974 | 1.0404 | 0.6296 | 0.0000 | 0/8 |
| Domésticos w=0.00 | 0.5079 | 0.9869 | 0.5852 | 0.5643 | 5/8 |
| Domésticos w=0.01 | 0.5238 | 0.9858 | 0.5842 | 0.5305 | 5/8 |
| Domésticos w=0.02 | 0.5291 | 0.9848 | 0.5834 | 0.5362 | 5/8 |
| Domésticos w=0.05 | 0.5608 | 0.9825 | 0.5816 | 0.5414 | 5/8 |
| Domésticos w=0.10 | 0.5714 | 0.9805 | 0.5799 | 0.5184 | 5/8 |
| Domésticos w=0.20 | 0.5767 | 0.9800 | 0.5797 | 0.5127 | 5/8 |
| Domésticos w=0.30 | 0.5661 | 0.9819 | 0.5814 | 0.5129 | 4/8 |
| Domésticos w=0.50 | 0.5661 | 0.9886 | 0.5870 | 0.4621 | 4/8 |
| Domésticos w=1.00 | 0.5344 | 1.0093 | 0.6037 | 0.3915 | 4/8 |
| Domésticos solo | 0.4921 | 1.0362 | 0.6254 | 0.1214 | 2/8 |
| Domésticos solo nuevos | 0.4921 | 1.0234 | 0.6137 | 0.3954 | 3/8 |
| Blend CL+dom beta=0.02 | 0.5238 | 0.9860 | 0.5845 | 0.5305 | 5/8 |
| Blend CL+dom beta=0.05 | 0.5291 | 0.9848 | 0.5835 | 0.5044 | 5/8 |
| Blend CL+dom beta=0.10 | 0.5238 | 0.9831 | 0.5822 | 0.5014 | 5/8 |
| Blend CL+dom beta=0.20 | 0.5450 | 0.9807 | 0.5804 | 0.5188 | 5/8 |

## Producción 2026/27 (in-sample)

- Spearman CL-only: 0.8070.
- Spearman mixed (histórico + CL actual): 0.6994.
- Spearman mixed + domésticos actuales: 0.6682.

## Mejores

- Log-loss: Domésticos w=0.20 (0.9800).
- Spearman: CL-only 5 temporadas (0.5643).
- Top-8: CL-only 5 temporadas (5/8).
- Mejor variante doméstica por Spearman: Domésticos w=0.00 (0.5643).
- Mejor variante doméstica por top-8: Domésticos w=0.00 (5/8).

## Conclusión

Ninguna variante doméstica mejora el ranking (Spearman/top-8) respecto al ELO CL-only; solo mejora la calibración. No se recomienda producir esta vía tal cual.

## Lectura

- Comparar cada peso con `CL-only 5 temporadas`.
- Un peso es interesante solo si mejora log-loss/Brier sin empeorar de forma clara Spearman/top-8.
- Cobertura incompleta: LASK, Sabah, Bodø/Glimt, Viking, Shakhtar y Slovan Bratislava no tienen datos domésticos en esta fuente; Slavia Praha se unifica ahora con su id histórico.
