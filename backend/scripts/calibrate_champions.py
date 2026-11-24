"""Reconstruct Champions League Elo and calibrate Davidson.

Run from ``backend/``:

    python scripts/calibrate_champions.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.champions.config import get_champions_settings  # noqa: E402
from app.champions.data.api_football import (  # noqa: E402
    load_history_matches,
)
from app.champions.data.snapshot import (  # noqa: E402
    _clubelo_snapshot,
    build_history_payload,
    calibrate_params,
    calibration_score_samples,
    clubelo_priors_for_seasons,
    replay_history,
    resolve_teams,
    scoreline_params_to_dict,
    seed_history_ratings,
)
from app.domain.elo import (  # noqa: E402
    DEFAULT_HOME_ADVANTAGE,
    DEFAULT_K,
)
from app.domain.scoreline import fit_scoreline  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"


def main() -> None:
    settings = get_champions_settings()
    matches, labels, sources = load_history_matches(settings)
    if not matches or not labels:
        raise SystemExit("No Champions League matches were returned")

    history_start = int(labels[0].split("/")[0])
    clubelo = _clubelo_snapshot(
        settings, f"{history_start}-08-01"
    )
    teams = resolve_teams(matches)
    by_season: dict[str, list[dict]] = {}
    for raw in matches:
        by_season.setdefault(str(raw["season"]), []).append(raw)
    priors = clubelo_priors_for_seasons(settings, labels, teams)
    seeded_ratings, seed_source = seed_history_ratings(
        teams,
        by_season.get(labels[0], []),
        clubelo,
    )
    seeded = {
        team_id: team.with_elo(seeded_ratings[team_id])
        for team_id, team in teams.items()
    }
    season_groups = [
        (label, by_season.get(label, [])) for label in labels
    ]

    replay = replay_history(
        season_groups,
        seeded.values(),
        {"k": DEFAULT_K, "home_advantage": DEFAULT_HOME_ADVANTAGE},
        regression=float(settings.season_regression),
        season_priors=priors,
        prior_weight=float(settings.clubelo_prior_weight),
    )

    previous_label = labels[-1]
    previous_matches = by_season.get(previous_label, [])
    previous_teams = resolve_teams(previous_matches)
    historical = build_history_payload(
        replay,
        seed_source=seed_source,
        demo_team_ids=previous_teams.keys(),
    )

    calibration_start = replay.season_starts.get(previous_label, {})
    calibration_teams = [
        team.with_elo(calibration_start.get(team.id, team.elo))
        for team in previous_teams.values()
    ]
    calibrated = calibrate_params(previous_matches, calibration_teams)
    scoreline_samples = calibration_score_samples(
        previous_matches,
        calibration_teams,
        {"k": DEFAULT_K, "home_advantage": DEFAULT_HOME_ADVANTAGE},
    )
    scoreline = fit_scoreline(
        [sample[0] for sample in scoreline_samples],
        [sample[1] for sample in scoreline_samples],
        [sample[2] for sample in scoreline_samples],
        home_advantage=float(calibrated["home_advantage"]),
        max_goals=10,
    )
    calibrated["scoreline"] = scoreline_params_to_dict(scoreline)
    calibrated["scoreline_samples"] = len(scoreline_samples)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "champions_historical.json").write_text(
        json.dumps(historical, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (DATA_DIR / "champions_params.json").write_text(
        json.dumps(calibrated, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    demo = []
    for raw in previous_matches:
        if raw.get("phase") != "league":
            continue
        played = (
            int(raw.get("matchday") or 0)
            <= settings.fallback_rewind_matchday
        )
        demo.append(
            {
                "phase": "league",
                "matchday": int(raw.get("matchday") or 0),
                "leg": 0,
                "home": raw["home"],
                "away": raw["away"],
                "home_goals": raw.get("home_goals") if played else None,
                "away_goals": raw.get("away_goals") if played else None,
                "kickoff": raw.get("kickoff"),
                "neutral": False,
            }
        )
    (DATA_DIR / "champions_demo_matches.json").write_text(
        json.dumps(demo, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("sources:", sources)
    print("seasons:", labels)
    print("matches:", len(matches), "applied:", replay.applied)
    print("teams:", len(seeded), "seed_source:", seed_source)
    print(
        "clubelo prior:",
        settings.clubelo_prior_weight,
        "seasons:",
        sorted(priors),
    )
    print("regression:", settings.season_regression)
    print(
        "calibrated:",
        f"H={calibrated['home_advantage']:.2f}",
        f"nu={calibrated['nu']:.4f}",
    )
    print(
        "scoreline:",
        f"home_base={scoreline.home_base:.3f}",
        f"away_base={scoreline.away_base:.3f}",
        f"elo_slope={scoreline.elo_slope:.5f}",
        f"rho={scoreline.rho:.4f}",
        f"samples={len(scoreline_samples)}",
    )
    print("validation:", calibrated.get("validation"))
    print("written to", DATA_DIR)


if __name__ == "__main__":
    main()
