# Cálculo y evolución del ELO

Esta nota documenta cómo SimuLiga atribuye el rating ELO a cada equipo, cómo se
verifica la temporada 2025/26 y qué muestra el gráfico de evolución de la hoja
`/elo`.

## 1. Resumen

- El ELO es una escala relativa de fuerza. No es una probabilidad.
- La reconstrucción histórica arranca en **1500** para todos los equipos en
  **2020/21** y cubre cinco temporadas (2020/21–2024/25).
- La temporada **2025/26 se reaplica completa**: 380 partidos, incluidos los de
  Girona, Mallorca y Oviedo, que ya no están en LaLiga 2026/27.
- Los equipos que no jugaron la temporada anterior entran con la **media de los
  tres descendidos**, no con un rating antiguo ni con 1500.
- El gráfico de `/elo` muestra el rating al inicio de cada temporada, desde
  **2020/21 hasta 2026/27** (siete puntos).

## 2. Fuentes de datos

| Dato | Fuente | Uso |
| --- | --- | --- |
| Resultados 2020/21–2024/25 | football-data.co.uk (`2021`, `2122`, `2223`, `2324`, `2425`) | Reconstrucción histórica y calibración de Davidson |
| Calendario y resultados 2025/26 | OpenFootball | Replay de la temporada anterior |
| Resultados 2025/26 sin marcador | football-data.co.uk (`2526`) | Relleno de los 15 encuentros incompletos |
| Calendario y resultados 2026/27 | OpenFootball + football-data.co.uk (`2627`) | Snapshot actual |
| Ratings históricos | `app/data/historical_ratings.json` | Semillas, participantes y descensos |

API-Football sigue disponible como fuente alternativa para el snapshot actual,
pero el plan gratuito no cubre 2020/21; por eso el histórico se construye con
football-data.co.uk.

Variables relevantes en `.env`:

```dotenv
DATA_SOURCE=openfootball
OPENFOOTBALL_SEASON=2026-27
PREVIOUS_OPENFOOTBALL_SEASON=2025-26
FOOTBALL_DATA_SEASON=2627
PREVIOUS_FOOTBALL_DATA_SEASON=2526
```

## 3. Fórmulas

### 3.1 Expectativa de victoria

```text
E_local = 1 / (1 + 10^(-((Elo_local + 60) - Elo_visitante) / 400))
```

- `60` es la ventaja de casa usada al **actualizar** ratings.
- `400` es la escala: 400 puntos de diferencia equivalen a una expectativa de
  10 a 1.

### 3.2 Actualización

```text
ΔElo = 20 · multiplicador_margen · (resultado − E_local)

resultado = 1 victoria · 0,5 empate · 0 derrota
```

Multiplicador por margen de goles:

```text
margen 0–1 → ×1,0
margen 2   → ×1,5
margen ≥3  → ×(11 + margen) / 8
```

Los puntos que gana un equipo los pierde el rival: el total se conserva.

> La actualización ELO usa `H = 60`. El modelo Davidson calibrado usa otro
> valor (`H = 83,26`) para convertir la diferencia de ELO en probabilidades
> 1X2. Son dos parámetros distintos y no deben confundirse.

## 4. Pipeline completo

### 4.1 Reconstrucción 2020/21–2024/25

1. Todos los equipos parten de **1500** en 2020/21.
2. Se aplican los 380 partidos de cada temporada con la fórmula anterior.
3. El resultado se guarda en `historical_ratings.json`:
   - `season_starts["2021"]`: rating al inicio de 2021/22 (final de 2020/21).
   - `season_starts["2022"]`: rating al inicio de 2022/23.
   - `season_starts["2023"]`: rating al inicio de 2023/24.
   - `season_starts["2024"]`: rating al inicio de 2024/25.
   - `final_2024`: rating al final de 2024/25.
   - `season_teams["2020"]`…`["2024"]`: participantes de cada temporada.
   - `relegated["2020"]`…`["2024"]`: tres últimos de cada temporada.
4. Este bloque histórico está congelado. Los equipos que entran por primera vez
   en una temporada usan 1500; los que vuelven tras un descenso conservan su
   rating anterior.

La calibración temporal de Davidson usa:

- **Entrenamiento:** 2020/21–2023/24 (1.520 partidos).
- **Validación:** 2024/25 (380 partidos).
- **Ajuste final:** 2020/21–2024/25 (1.900 partidos).

### 4.2 Replay de 2025/26

El código anterior descartaba cualquier partido en el que uno de los equipos no
estuviera en LaLiga 2026/27. Eso dejaba fuera a Girona, Mallorca y Oviedo y
aplicaba solo **263 de los 365 partidos con marcador**. La corrección:

1. Resuelve los 20 equipos de 2025/26, aunque no estén en 2026/27.
2. Siembra con `final_2024` a los equipos que jugaron 2024/25.
3. Si un equipo **no jugó 2024/25** (ascendido), usa la media de los tres
   descendidos de 2024/25, aunque conserve un rating antiguo:
   - Valladolid: 1272,59
   - Las Palmas: 1394,69
   - Leganés: 1463,88
   - Media: **1377,05**
4. Aplica los 380 partidos en orden de fecha.
5. Rellena los 15 encuentros sin marcador en OpenFootball con
   football-data.co.uk (`2526`).
6. El resultado es el rating de inicio de 2026/27 (`elo_by_matchday[1]`).

Con la corrección, la verificación del snapshot devuelve:

```text
Temporada anterior: 2025/26
Partidos: 380/380 aplicados · 15 rellenados · 0 sin marcador · 0 sin resolver
Equipos: 20/20 resueltos
Baseline ascendidos 2025/26: 1377.05
Baseline ascendidos 2026/27: 1437.93 (se recalcula en cada snapshot)
```

### 4.3 Ascendidos de 2026/27

Los tres equipos que no jugaron 2025/26 pero sí están en 2026/27 son Málaga,
Deportivo y Racing. Su rating de entrada es la media de los ratings finales de
los tres equipos que descendieron tras 2025/26: Girona, Mallorca y Oviedo.

En la ejecución actual esa media es **1437,93**. Es un valor dinámico: si cambian
los resultados o la composición de la liga, cambia el baseline.

### 4.4 Temporada 2026/27

1. Se parte del rating de inicio de 2026/27.
2. Se aplican las jornadas ya disputadas (resultados reales).
3. El rating resultante es el que usan Davidson y Dixon-Coles para proyectar los
   partidos pendientes.

## 5. Corrección de alias históricos

Además del filtro de equipos, había un segundo problema: algunos equipos
actuales no se emparejaban con su clave histórica por diferencias de nombre.

- `Atlético de Madrid` no coincidía con `ath madrid`.
- `Celta de Vigo` no coincidía con `celta`.
- `Athletic Club` no coincidía con `ath bilbao`.

La resolución ahora reutiliza los alias de proveedor y busca la clave histórica
por id canónico. También se apoya en `season_teams["2024"]` para saber si un
equipo jugó 2024/25 y evitar sembrar con ratings antiguos de equipos que
estuvieron fuera de LaLiga.

## 6. Gráfico de evolución

La hoja `/elo` incluye un gráfico de pequeños múltiplos: una mini-línea por
equipo.

- Eje X: inicio de cada temporada (`2020/21`, `2021/22`, `2022/23`, `2023/24`,
  `2024/25`, `2025/26`, `2026/27`).
- Eje Y: escala compartida para todos los equipos, con una línea de referencia
  en 1500.
- El tramo grueso es la temporada 2025/26, que va del inicio de 2025/26 al inicio
  de 2026/27.
- Una línea plana significa que el equipo no jugó esa temporada y conservó su
  rating.
- Una línea que empieza más tarde indica la temporada de entrada del equipo.
- El pie muestra el primer rating y la variación total hasta 2026/27.

La tabla de verificación que acompaña al gráfico muestra, por equipo:

- `Final 2024/25`: rating antes de aplicar 2025/26.
- `Inicio 2026/27`: rating después de aplicar 2025/26.
- `Δ 2025/26`: diferencia entre ambos. Mide el efecto de la temporada anterior.
- `2025/26`: si el equipo jugó esa temporada o es un ascendido de 2026/27.

## 7. API

`GET /api/elo` devuelve, además de la tabla actual:

```json
{
  "history": {
    "seasons": [
      "2020/21", "2021/22", "2022/23", "2023/24",
      "2024/25", "2025/26", "2026/27"
    ],
    "origin": 1500,
    "series": [
      {
        "team_id": "real-madrid",
        "values": [1500.0, 1676.79, 1731.68, 1700.36, 1803.51, 1788.3, 1778.42]
      }
    ]
  },
  "verification": {
    "available": true,
    "previous_season": "2025/26",
    "matches_total": 380,
    "matches_applied": 380,
    "matches_without_score": 15,
    "matches_filled_from_football_data": 15,
    "matches_missing": 0,
    "matches_unresolved": 0,
    "teams_total": 20,
    "teams_resolved": 20,
    "sources": ["OpenFootball", "football-data.co.uk"],
    "baseline_label": "Final 2024/25",
    "baseline": {"real-madrid": 1788.3},
    "played_previous_season": {"real-madrid": true, "malaga": false},
    "promoted_baseline_2025": 1377.05,
    "promoted_baseline_2026": 1437.93
  }
}
```

En modo demostración, `history.series` está vacío y
`verification.available` es `false`.

## 8. Verificación reproducible

Desde `backend/`:

```powershell
python scripts/verify_elo_history.py
```

El script:

1. Carga el snapshot real.
2. Comprueba que se aplicaron todos los partidos de 2025/26.
3. Comprueba que no quedan equipos sin resolver.
4. Comprueba que el histórico tiene siete temporadas y que los equipos
   fundacionales arrancan en 1500.
5. Imprime la tabla `Equipo · Final 2024/25 · Inicio 2026/27 · Δ 2025/26`.

Para ejecutar los tests:

```powershell
python -m pytest tests -q
```

### 8.1 Calibración de los ELO de inicio

El análisis de calibración de los ratings de inicio de 2026/27 se documenta en
[`docs/elo-calibration-2026.md`](elo-calibration-2026.md) y se reproduce con:

```powershell
python scripts/analyze_elo_calibration.py
```

Resumen de la ejecución con 88 partidos (jornadas 1–9):

- Log-loss `0,952` frente a `1,078` del modelo sin ELO.
- `alpha = 1,657`, intervalo de perfil `[0,95; 2,49]`: no se rechaza la
  dispersión actual.
- `H` y `nu` de 2020/21–2023/24 siguen siendo compatibles con 2026/27.
- El empate se subpredice ~1,7 puntos porcentuales; la muestra es corta.

## 9. Limitaciones

- El bloque 2020/21–2024/25 está congelado. Los equipos que entran por primera
  vez en esas temporadas usan 1500; la regla de la media de descendidos se
  aplica desde 2025/26.
- El baseline de 2026/27 es dinámico y depende de los ratings finales de los
  descendidos de 2025/26.
- Los 15 partidos sin marcador en OpenFootball se rellenan con
  football-data.co.uk. Si esa fuente falla, la API lo indica en
  `matches_missing` y `matches_applied` baja de 380.
- El ELO no incorpora lesiones, sanciones, mercado de fichajes ni contexto.
- Un rating alto no es una garantía: es una fuerza media condicionada a los
  datos y al modelo.

## 10. Mapa de archivos

| Archivo | Responsabilidad |
| --- | --- |
| `backend/app/domain/elo.py` | Fórmula, constantes y baseline de respaldo |
| `backend/app/data/real_league.py` | Replay de 2025/26, resolución de equipos, historial y verificación |
| `backend/app/data/league.py` | `LeagueSnapshot` con `elo_history` y `elo_verification` |
| `backend/app/api/serializers.py` | `serialize_elo` y payload de `/api/elo` |
| `backend/app/data/historical_ratings.json` | Ratings históricos, participantes y descensos |
| `backend/scripts/calibrate_history.py` | Regenera `historical_ratings.json` y `calibrated_params.json` |
| `backend/scripts/verify_elo_history.py` | Verificación reproducible del replay y del gráfico |
| `backend/scripts/analyze_elo_calibration.py` | Análisis estadístico de calibración de 2026/27 |
| `docs/elo-calibration-2026.md` | Informe de calibración con resultados e interpretación |
| `frontend/components/EloSheet.tsx` | Página `/elo` |
| `frontend/components/EloHistory.tsx` | Gráfico de evolución y tabla de verificación |
| `frontend/lib/types.ts` | Tipos de `history` y `verification` |

## 11. Regenerar el histórico

Solo es necesario si se quiere rehacer la reconstrucción 2020/21–2024/25:

```powershell
python scripts/calibrate_history.py
```

Usa football-data.co.uk (sin clave ni cuota de API-Football). Sobrescribe
`app/data/historical_ratings.json` y `app/data/calibrated_params.json`. Si se
cambia la convención de entrada de los ascendidos, hay que volver a validar el
modelo Davidson.
