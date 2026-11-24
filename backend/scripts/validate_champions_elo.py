"""Validate the five-season Champions Elo against a holdout season."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.champions.config import get_champions_settings  # noqa: E402
from app.champions.data.api_football import (  # noqa: E402
    load_history_matches,
    load_source_matches,
)
from app.champions.data.snapshot import (  # noqa: E402
    _clubelo_snapshot,
    build_snapshot_from_matches,
    calibrate_params,
    clubelo_priors_for_seasons,
    replay_history,
    resolve_teams,
    seed_history_ratings,
)
from app.champions.data.validation import (  # noqa: E402
    evaluate_ratings,
    points_by_team,
    ratings_for_window,
    replay_for_window,
    season_groups,
    spearman_correlation,
    top_overlap,
)
from app.domain.davidson import DavidsonParams  # noqa: E402

OUTPUT = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "champions-elo-5y-validation.md"
)
SPEARMAN_TARGET = 0.60
TOP_OVERLAP_TARGET = 6


def points_from_snapshot(snapshot) -> dict[str, float]:
    points: dict[str, float] = {}
    for match in snapshot.matches:
        if match.phase != "league" or not match.is_played:
            continue
        if match.home_goals is None or match.away_goals is None:
            continue
        points.setdefault(match.home_id, 0.0)
        points.setdefault(match.away_id, 0.0)
        if match.home_goals > match.away_goals:
            points[match.home_id] += 3
        elif match.home_goals < match.away_goals:
            points[match.away_id] += 3
        else:
            points[match.home_id] += 1
            points[match.away_id] += 1
    return points


def training_params(train_matches: list[dict], train_labels: list[str]):
    replay = replay_for_window(
        train_matches, train_labels, regression=0.2, k=20
    )
    calibration_label = train_labels[-1]
    calibration_matches = [
        raw
        for raw in train_matches
        if raw["season"] == calibration_label
    ]
    calibration_start = replay.season_starts.get(calibration_label)
    if not calibration_matches or calibration_start is None:
        raise SystemExit(
            f"No calibration data for {calibration_label}"
        )
    calibration_teams = [
        team.with_elo(calibration_start.get(team.id, team.elo))
        for team in resolve_teams(calibration_matches).values()
    ]
    try:
        calibrated = calibrate_params(
            calibration_matches, calibration_teams
        )
    except Exception as error:  # noqa: BLE001 - reported to the operator
        raise SystemExit(
            f"Could not calibrate Davidson on "
            f"{calibration_label}: {error}"
        ) from error
    params = DavidsonParams(
        home_advantage=float(calibrated["home_advantage"]),
        nu=float(calibrated["nu"]),
    )
    return replay.ratings, params


def clubelo_replay_for_window(settings, matches: list[dict], labels: list[str]):
    teams = resolve_teams(matches)
    first_raw = _clubelo_snapshot(
        settings, f"{labels[0][:4]}-08-01"
    )
    seeded_ratings, _ = seed_history_ratings(
        teams, [], first_raw
    )
    seeded = [
        team.with_elo(seeded_ratings[team_id])
        for team_id, team in teams.items()
    ]
    priors = clubelo_priors_for_seasons(settings, labels, teams)
    return replay_history(
        season_groups(matches, labels),
        seeded,
        {"k": 20, "home_advantage": 60},
        regression=0.20,
        season_priors=priors,
        prior_weight=float(settings.clubelo_prior_weight),
    )


def training_params_clubelo(
    settings, matches: list[dict], labels: list[str]
):
    replay = clubelo_replay_for_window(settings, matches, labels)
    calibration_label = labels[-1]
    calibration_matches = [
        raw
        for raw in matches
        if raw["season"] == calibration_label
    ]
    calibration_start = replay.season_starts.get(calibration_label)
    if not calibration_matches or calibration_start is None:
        raise SystemExit(
            f"No ClubElo calibration data for {calibration_label}"
        )
    calibration_teams = [
        team.with_elo(calibration_start.get(team.id, team.elo))
        for team in resolve_teams(calibration_matches).values()
    ]
    calibrated = calibrate_params(
        calibration_matches, calibration_teams
    )
    params = DavidsonParams(
        home_advantage=float(calibrated["home_advantage"]),
        nu=float(calibrated["nu"]),
    )
    return replay.ratings, params


def main() -> None:
    settings = get_champions_settings()
    matches, labels, _ = load_history_matches(
        settings, seasons=list(range(2020, 2026))
    )
    if len(labels) < 6:
        raise SystemExit(f"Expected 6 seasons, got {labels}")

    train_labels = labels[:5]
    test_label = labels[5]
    train_matches = [
        raw for raw in matches if raw["season"] in train_labels
    ]
    test_matches = [
        raw for raw in matches if raw["season"] == test_label
    ]
    league_test = [
        raw for raw in test_matches if raw.get("phase") == "league"
    ]
    if not train_matches:
        raise SystemExit("No training matches available")
    if not test_matches:
        raise SystemExit(f"No holdout matches available for {test_label}")

    ratings_5, params = training_params(train_matches, train_labels)
    ratings_clubelo, params_clubelo = training_params_clubelo(
        settings, train_matches, train_labels
    )

    ratings_1 = ratings_for_window(
        [
            raw
            for raw in matches
            if raw["season"] == train_labels[-1]
        ],
        [train_labels[-1]],
        regression=0.0,
        k=20,
    )
    ratings_flat: dict[str, float] = {}

    metrics_5 = evaluate_ratings(test_matches, ratings_5, params)
    metrics_clubelo = evaluate_ratings(
        test_matches, ratings_clubelo, params_clubelo
    )
    metrics_1 = evaluate_ratings(test_matches, ratings_1, params)
    metrics_flat = evaluate_ratings(test_matches, ratings_flat, params)

    if not league_test:
        raise SystemExit(
            f"No league matches available for {test_label} points"
        )
    test_points = points_by_team(league_test)
    if not test_points:
        raise SystemExit(
            f"Empty points table for {test_label}"
        )
    spearman_5 = spearman_correlation(ratings_5, test_points)
    overlap_5 = top_overlap(ratings_5, test_points)
    spearman_clubelo = spearman_correlation(
        ratings_clubelo, test_points
    )
    overlap_clubelo = top_overlap(ratings_clubelo, test_points)

    prod_matches, prod_labels, _ = load_history_matches(settings)
    if not prod_matches or not prod_labels:
        raise SystemExit("No production history available")
    current_matches, _ = load_source_matches(settings, settings.season)
    if not current_matches:
        raise SystemExit(
            f"No current-season matches available for {settings.season}"
        )
    current_label = (
        f"{settings.season}/{(settings.season + 1) % 100:02d}"
    )
    snapshot = build_snapshot_from_matches(
        prod_matches,
        current_matches,
        settings,
        source="validation",
        history_labels=prod_labels,
        current_label=current_label,
    )
    prod_ratings = {
        team.id: team.elo for team in snapshot.teams
    }
    current_points = points_from_snapshot(snapshot)
    if not current_points:
        raise SystemExit(
            f"Empty points table for current season {current_label}"
        )
    spearman_current = spearman_correlation(
        prod_ratings, current_points
    )
    current_played = sum(
        1
        for match in snapshot.matches
        if match.phase == "league" and match.is_played
    )

    grid = []
    for alpha in (0.0, 0.1, 0.2, 0.3):
        for k in (16, 20, 24):
            ratings = ratings_for_window(
                train_matches,
                train_labels,
                regression=alpha,
                k=k,
            )
            grid.append(
                (
                    alpha,
                    k,
                    evaluate_ratings(test_matches, ratings, params),
                    spearman_correlation(ratings, test_points),
                    top_overlap(ratings, test_points),
                )
            )

    best_log_loss = min(
        grid, key=lambda row: (row[2].log_loss, row[0], row[1])
    )
    best_brier = min(
        grid, key=lambda row: (row[2].brier, row[0], row[1])
    )
    best_spearman = max(
        grid, key=lambda row: (row[3], -row[0], -row[1])
    )
    best_overlap = max(
        grid, key=lambda row: (row[4], -row[0], -row[1])
    )
    grid_passing = [
        (alpha, k, spearman, overlap)
        for alpha, k, _, spearman, overlap in grid
        if spearman >= SPEARMAN_TARGET
        and overlap >= TOP_OVERLAP_TARGET
    ]
    log_loss_ok = (
        metrics_clubelo.log_loss < metrics_1.log_loss
        and metrics_clubelo.log_loss < metrics_flat.log_loss
    )
    spearman_ok = spearman_clubelo >= SPEARMAN_TARGET
    overlap_ok = overlap_clubelo >= TOP_OVERLAP_TARGET

    lines = [
        "# Validación del ELO de 5 temporadas",
        "",
        f"Backtest: {train_labels[0]}–{train_labels[-1]} "
        f"→ {test_label}",
        "",
        f"Calibración Davidson ajustada solo con "
        f"{train_labels[-1]} del training. CL-only: "
        f"H={params.home_advantage:.4f}, nu={params.nu:.4f}. "
        f"Prior ClubElo: H={params_clubelo.home_advantage:.4f}, "
        f"nu={params_clubelo.nu:.4f}.",
        "",
        "## Comparación de ratings",
        "",
        "| Modelo | Partidos | Accuracy | Log-loss | Brier |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| 5 temporadas | {metrics_5.matches} | "
        f"{metrics_5.accuracy:.4f} | {metrics_5.log_loss:.4f} | "
        f"{metrics_5.brier:.4f} |",
        f"| 5 temporadas + prior ClubElo "
        f"{settings.clubelo_prior_weight:.0%} | "
        f"{metrics_clubelo.matches} | "
        f"{metrics_clubelo.accuracy:.4f} | "
        f"{metrics_clubelo.log_loss:.4f} | "
        f"{metrics_clubelo.brier:.4f} |",
        f"| 1 temporada | {metrics_1.matches} | "
        f"{metrics_1.accuracy:.4f} | {metrics_1.log_loss:.4f} | "
        f"{metrics_1.brier:.4f} |",
        f"| 1500 plano | {metrics_flat.matches} | "
        f"{metrics_flat.accuracy:.4f} | "
        f"{metrics_flat.log_loss:.4f} | "
        f"{metrics_flat.brier:.4f} |",
        "",
        "## Correlación y top 8",
        "",
        f"- Spearman con puntos de {test_label} (CL-only): "
        f"{spearman_5:.4f}",
        f"- Solapamiento top 8 (CL-only): {overlap_5}/8",
        f"- Spearman con puntos de {test_label} (prior ClubElo): "
        f"{spearman_clubelo:.4f}",
        f"- Solapamiento top 8 (prior ClubElo): "
        f"{overlap_clubelo}/8",
        f"- Spearman con puntos actuales de {current_label} "
        f"(snapshot de producción, {current_played} partidos de liga "
        f"jugados): {spearman_current:.4f}",
        "",
        "## Búsqueda de alpha y K",
        "",
        "| alpha | K | Accuracy | Log-loss | Brier | Spearman | Top-8 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for alpha, k, metrics, spearman, overlap in grid:
        lines.append(
            f"| {alpha:.1f} | {k} | {metrics.accuracy:.4f} | "
            f"{metrics.log_loss:.4f} | {metrics.brier:.4f} | "
            f"{spearman:.4f} | {overlap}/8 |"
        )

    lines.extend(
        [
            "",
            f"Configuraciones del grid que cumplen Spearman >= "
            f"{SPEARMAN_TARGET:.2f} y top 8 >= "
            f"{TOP_OVERLAP_TARGET}/8: "
            f"{len(grid_passing)} de {len(grid)}.",
        ]
    )
    if grid_passing:
        for alpha, k, spearman, overlap in grid_passing:
            lines.append(
                f"- alpha={alpha:.1f}, K={k}: Spearman="
                f"{spearman:.4f}, top 8={overlap}/8."
            )
    else:
        lines.append(
            "- Ninguna configuración del grid cumple ambos criterios "
            "de ranking."
        )

    lines.extend(
        [
            "",
            "## Mejores combinaciones",
            "",
            "| Criterio | alpha | K | Log-loss | Brier | Spearman | Top-8 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            f"| Mejor log-loss | {best_log_loss[0]:.1f} | "
            f"{best_log_loss[1]} | {best_log_loss[2].log_loss:.4f} | "
            f"{best_log_loss[2].brier:.4f} | {best_log_loss[3]:.4f} | "
            f"{best_log_loss[4]}/8 |",
            f"| Mejor Brier | {best_brier[0]:.1f} | "
            f"{best_brier[1]} | {best_brier[2].log_loss:.4f} | "
            f"{best_brier[2].brier:.4f} | {best_brier[3]:.4f} | "
            f"{best_brier[4]}/8 |",
            f"| Mejor Spearman | {best_spearman[0]:.1f} | "
            f"{best_spearman[1]} | "
            f"{best_spearman[2].log_loss:.4f} | "
            f"{best_spearman[2].brier:.4f} | "
            f"{best_spearman[3]:.4f} | {best_spearman[4]}/8 |",
            f"| Mejor top 8 | {best_overlap[0]:.1f} | "
            f"{best_overlap[1]} | {best_overlap[2].log_loss:.4f} | "
            f"{best_overlap[2].brier:.4f} | {best_overlap[3]:.4f} | "
            f"{best_overlap[4]}/8 |",
            "",
            "## Recomendaciones",
            "",
            f"- El modelo de producción usa prior ClubElo "
            f"w={settings.clubelo_prior_weight:.2f} sobre el replay "
            "de cinco temporadas.",
            "- El grid alpha/K de CL-only se mantiene como referencia "
            "metodológica; no es el modelo de producción.",
            f"- Criterios del modelo de producción: log-loss "
            f"{'OK' if log_loss_ok else 'NO'} ("
            f"{metrics_clubelo.log_loss:.4f}), Spearman "
            f"{'OK' if spearman_ok else 'NO'} "
            f"({spearman_clubelo:.4f}), top 8 "
            f"{'OK' if overlap_ok else 'NO'} "
            f"({overlap_clubelo}/8).",
            "- Si el top 8 sigue corto, el siguiente paso es añadir "
            "otra señal de nivel actual (coeficiente UEFA, valor de "
            "plantilla o forma reciente) o aceptar la limitación.",
            "- Mantener el análisis doméstico como experimento "
            "descartado: mejora calibración pero empeora ranking.",
            "",
            "## Criterios",
            "",
            f"- Log-loss del modelo de producción (prior ClubElo) "
            f"menor que 1 temporada y que 1500: "
            f"{'sí' if log_loss_ok else 'no'} "
            f"({metrics_clubelo.log_loss:.4f} vs "
            f"{metrics_1.log_loss:.4f} vs "
            f"{metrics_flat.log_loss:.4f}).",
            f"- Spearman del modelo de producción (prior ClubElo) "
            f"con puntos de {test_label} >= "
            f"{SPEARMAN_TARGET:.2f}: "
            f"{'sí' if spearman_ok else 'no'} "
            f"({spearman_clubelo:.4f}).",
            f"- Top 8 compartido del modelo de producción >= "
            f"{TOP_OVERLAP_TARGET}/8: "
            f"{'sí' if overlap_ok else 'no'} "
            f"({overlap_clubelo}/8).",
            "- Ranking de producción plausible: comprobado contra el "
            f"snapshot de producción de {current_label}.",
        ]
    )

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("written to", OUTPUT)


if __name__ == "__main__":
    main()
