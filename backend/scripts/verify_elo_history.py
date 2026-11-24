"""Verify the Elo history and the full 2025/26 replay.

Run from the backend directory with real data:

    python scripts/verify_elo_history.py

The script fails with exit code 1 when the previous season was not applied in
full, when a team could not be resolved, or when the history series is
incomplete.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.api.serializers import serialize_elo  # noqa: E402
from app.data.league import get_snapshot  # noqa: E402


def main() -> int:
    payload = serialize_elo(get_snapshot())
    verification = payload["verification"]
    if not verification.get("available"):
        print(
            "La verificación solo está disponible con datos reales "
            "(DATA_SOURCE=openfootball)."
        )
        return 1

    total = int(verification["matches_total"])
    applied = int(verification["matches_applied"])
    missing = int(verification["matches_missing"])
    unresolved = int(verification["matches_unresolved"])
    teams_total = int(verification["teams_total"])
    teams_resolved = int(verification["teams_resolved"])
    filled = int(verification["matches_filled_from_football_data"])
    without_score = int(verification["matches_without_score"])

    failures: list[str] = []
    if applied != total:
        failures.append(f"partidos aplicados {applied}/{total}")
    if missing:
        failures.append(f"{missing} partidos sin marcador")
    if unresolved:
        failures.append(f"{unresolved} partidos con equipos sin resolver")
    if teams_resolved != teams_total:
        failures.append(f"equipos resueltos {teams_resolved}/{teams_total}")

    history = payload["history"]
    seasons = history.get("seasons", [])
    if len(seasons) != 7:
        failures.append(f"el historial debería tener 7 temporadas, tiene {len(seasons)}")

    season_2025 = seasons.index("2025/26") if "2025/26" in seasons else 5
    series = {entry["team_id"]: entry["values"] for entry in history.get("series", [])}
    for team in payload["teams"]:
        values = series.get(team["id"])
        if values is None or len(values) != len(seasons):
            failures.append(f"historial incompleto para {team['name']}")
            continue
        if values[0] is not None and values[0] != 1500.0:
            failures.append(f"{team['name']} no arranca en 1500 ({values[0]})")

    if not any(
        values[season_2025] is not None
        for values in series.values()
        if len(values) == len(seasons)
    ):
        failures.append("ningún equipo tiene rating al inicio de 2025/26")

    timeline = payload.get("timeline", {})
    timeline_dates = timeline.get("dates", [])
    if len(timeline_dates) < 2:
        failures.append("la línea temporal tiene menos de 2 puntos")
    if timeline_dates != sorted(timeline_dates):
        failures.append("las fechas de la línea temporal no están ordenadas")
    for entry in timeline.get("series", []):
        if len(entry["values"]) != len(timeline_dates):
            failures.append(
                f"la serie temporal de {entry['team_id']} no coincide con las fechas"
            )

    print(f"Temporada anterior: {verification['previous_season']}")
    print(
        f"Partidos: {applied}/{total} aplicados · {filled} rellenados · "
        f"{without_score} sin marcador en OpenFootball · {missing} sin marcador final · "
        f"{unresolved} sin resolver"
    )
    print(f"Equipos: {teams_resolved}/{teams_total} resueltos")
    print(f"Fuentes: {', '.join(verification.get('sources', []))}")
    print(f"Baseline ascendidos 2025/26: {verification['promoted_baseline_2025']:.2f}")
    print(f"Baseline ascendidos 2026/27: {verification['promoted_baseline_2026']:.2f}")
    if timeline_dates:
        print(
            f"Línea temporal: {len(timeline_dates)} puntos · "
            f"{timeline_dates[0]} → {timeline_dates[-1]}"
        )
    print()
    print(f"{'Equipo':28} {'Final 2024/25':>14} {'Inicio 2026/27':>15} {'Delta 2025/26':>14}")
    print("-" * 76)

    baseline = verification.get("baseline", {})
    played = verification.get("played_previous_season", {})
    rows = []
    for team in payload["teams"]:
        base = baseline.get(team["id"])
        delta = None if base is None else team["start_elo"] - base
        rows.append((team, base, delta, played.get(team["id"], False)))
    rows.sort(key=lambda row: (row[2] is None, -(row[2] or 0.0)))

    for team, base, delta, played_previous in rows:
        base_label = "—" if base is None else f"{base:.2f}"
        delta_label = "—" if delta is None else f"{delta:+.2f}"
        status = "jugó 2025/26" if played_previous else "ascendido 2026/27"
        print(
            f"{team['name'][:28]:28} {base_label:>14} "
            f"{team['start_elo']:15.2f} {delta_label:>14}  {status}"
        )

    print()
    if failures:
        print("VERIFICACIÓN FALLIDA:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("VERIFICACIÓN OK: 2025/26 está incluido y el historial es completo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
