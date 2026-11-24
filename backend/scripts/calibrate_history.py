"""Reconstruct Elo from 2020/21 and calibrate Davidson.

Run from the backend directory:

    python scripts/calibrate_history.py

The script uses football-data.co.uk (free, no key) for the 2020/21–2024/25
seasons. It writes the historical ratings and the calibrated parameters to
``app/data/`` and prints a summary with temporal validation metrics.

The temporal split is:

- train: 2020/21–2023/24
- validate: 2024/25
- final fit: 2020/21–2024/25
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.data.football_data_csv import fetch_results  # noqa: E402
from app.data.history import HistoryMatch, compute_elo_history, evaluate_predictions  # noqa: E402
from app.data.names import normalize_name  # noqa: E402
from app.domain.davidson import fit_davidson, outcome_probabilities  # noqa: E402

SEASON_CODES = {
    2020: "2021",
    2021: "2122",
    2022: "2223",
    2023: "2324",
    2024: "2425",
}
TRAIN_SEASONS = (2020, 2021, 2022, 2023)
VALIDATION_SEASON = 2024
DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"


def load_matches() -> list[HistoryMatch]:
    settings = get_settings()
    matches: list[HistoryMatch] = []
    for season, code in SEASON_CODES.items():
        rows = fetch_results(code, settings.cache_dir, settings.cache_ttl_seconds)
        print(f"season {season}/{(season + 1) % 100:02d}: {len(rows)} matches")
        for row in rows:
            matches.append(
                HistoryMatch(
                    season=season,
                    date=row["date"],
                    home=normalize_name(row["home"]),
                    away=normalize_name(row["away"]),
                    home_goals=int(row["home_goals"]),
                    away_goals=int(row["away_goals"]),
                )
            )
    return matches


def season_tables(
    matches: list[HistoryMatch],
) -> tuple[dict[int, set[str]], dict[int, list[str]]]:
    """Participants and bottom three (relegated) per season.

    Relegation is inferred from points, then goal difference and goals scored.
    LaLiga's head-to-head tiebreak can only matter for teams level on points at
    the boundary; the historical cases used here are not affected.
    """
    by_season: dict[int, list[HistoryMatch]] = defaultdict(list)
    for match in matches:
        by_season[match.season].append(match)

    participants: dict[int, set[str]] = {}
    relegated: dict[int, list[str]] = {}
    for season, season_matches in sorted(by_season.items()):
        points: dict[str, int] = defaultdict(int)
        goals_for: dict[str, int] = defaultdict(int)
        goals_against: dict[str, int] = defaultdict(int)
        for match in season_matches:
            goals_for[match.home] += match.home_goals
            goals_against[match.home] += match.away_goals
            goals_for[match.away] += match.away_goals
            goals_against[match.away] += match.home_goals
            if match.home_goals > match.away_goals:
                points[match.home] += 3
            elif match.home_goals < match.away_goals:
                points[match.away] += 3
            else:
                points[match.home] += 1
                points[match.away] += 1

        teams = set(points)
        participants[season] = teams
        order = sorted(
            teams,
            key=lambda team: (
                -points[team],
                -(goals_for[team] - goals_against[team]),
                -goals_for[team],
                team,
            ),
        )
        relegated[season] = order[-3:]

    return participants, relegated


def main() -> None:
    matches = load_matches()
    if not matches:
        raise SystemExit("No finished matches were returned by football-data.co.uk")

    history = compute_elo_history(matches, collect_timeline=True)
    participants, relegated = season_tables(matches)

    train = [
        (delta, outcome)
        for delta, outcome, season in history.samples
        if season in TRAIN_SEASONS
    ]
    test = [
        (delta, outcome)
        for delta, outcome, season in history.samples
        if season == VALIDATION_SEASON
    ]
    if not train or not test:
        raise SystemExit("Not enough seasons to train and validate")

    train_deltas = [sample[0] for sample in train]
    train_outcomes = [sample[1] for sample in train]
    validation_params = fit_davidson(train_deltas, train_outcomes)
    test_probabilities = [
        outcome_probabilities(delta, validation_params).as_tuple() for delta, _ in test
    ]
    metrics = evaluate_predictions(
        test_probabilities, [outcome for _, outcome in test]
    )

    all_deltas = [sample[0] for sample in history.samples]
    all_outcomes = [sample[1] for sample in history.samples]
    final_params = fit_davidson(all_deltas, all_outcomes)

    final_2024 = {
        team: round(elo, 2)
        for team, elo in sorted(history.season_ends.get(VALIDATION_SEASON, {}).items())
    }
    relegated_2024 = relegated.get(VALIDATION_SEASON, [])
    promoted_baseline_2025 = (
        sum(final_2024[team] for team in relegated_2024 if team in final_2024)
        / max(1, sum(1 for team in relegated_2024 if team in final_2024))
        if relegated_2024
        else 1370.0
    )

    ratings_payload = {
        "start_2024": {
            team: round(elo, 2)
            for team, elo in sorted(
                history.season_starts.get(VALIDATION_SEASON, {}).items()
            )
        },
        "final_2024": final_2024,
        "season_starts": {
            str(season): {
                team: round(elo, 2)
                for team, elo in sorted(ratings.items())
            }
            for season, ratings in sorted(history.season_starts.items())
        },
        "season_ends": {
            str(season): {
                team: round(elo, 2)
                for team, elo in sorted(ratings.items())
            }
            for season, ratings in sorted(history.season_ends.items())
        },
        "season_teams": {
            str(season): sorted(teams)
            for season, teams in sorted(participants.items())
        },
        "relegated": {
            str(season): sorted(teams)
            for season, teams in sorted(relegated.items())
        },
        "timeline": history.timeline,
        "promoted_baselines": {"2025": round(promoted_baseline_2025, 2)},
        "meta": {
            "source": "football-data.co.uk",
            "seasons": sorted(SEASON_CODES),
            "train_seasons": list(TRAIN_SEASONS),
            "validation_season": VALIDATION_SEASON,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    calibrated = {
        "home_advantage": round(final_params.home_advantage, 4),
        "nu": round(final_params.nu, 4),
        "elo_scale": 400,
        "trained_on": list(TRAIN_SEASONS),
        "fit_on": sorted(SEASON_CODES),
        "validation": {
            "season": VALIDATION_SEASON,
            "home_advantage": round(validation_params.home_advantage, 4),
            "nu": round(validation_params.nu, 4),
            **{key: round(value, 6) for key, value in metrics.items()},
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "calibrated_params.json").write_text(
        json.dumps(calibrated, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (DATA_DIR / "historical_ratings.json").write_text(
        json.dumps(ratings_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(
        "seasons:",
        ", ".join(f"{season}/{(season + 1) % 100:02d}" for season in sorted(SEASON_CODES)),
    )
    print(
        "relegated 2024/25:",
        ", ".join(sorted(relegated_2024)),
        f"(baseline 2025/26 {promoted_baseline_2025:.2f})",
    )
    print(
        "calibrated:",
        f"H={final_params.home_advantage:.2f}",
        f"nu={final_params.nu:.4f}",
    )
    print(
        "validation 2024/25:",
        f"accuracy={metrics['accuracy']:.4f}",
        f"log_loss={metrics['log_loss']:.4f}",
        f"brier={metrics['brier']:.4f}",
        f"matches={metrics['matches']}",
    )
    print("written to", DATA_DIR)


if __name__ == "__main__":
    main()
