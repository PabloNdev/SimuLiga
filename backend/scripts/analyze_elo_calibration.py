"""Statistical calibration analysis of the start-of-season Elo ratings.

The script evaluates the ratings frozen at the start of 2026/27 against the
matches already played in that season. It reports proper scoring rules,
reliability bins, a spread-shrinkage fit and a walk-forward comparison.

Run from the backend directory with real data:

    python scripts/analyze_elo_calibration.py
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import chi2, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.data.league import get_snapshot  # noqa: E402
from app.domain.elo import DEFAULT_HOME_ADVANTAGE, DEFAULT_K, update_ratings  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
OUTCOME_INDEX = {"H": 0, "D": 1, "A": 2}
CLASS_NAMES = ("Local", "Empate", "Visitante")
BOOTSTRAP = 800
H_NU_BOOTSTRAP = 300
SEED = 20262027


@dataclass(frozen=True)
class Calibration:
    home_advantage: float
    nu: float
    elo_scale: float = 400.0


@dataclass
class MatchRow:
    matchday: int
    home_id: str
    away_id: str
    home_goals: int
    away_goals: int
    outcome: int
    kickoff: str


@dataclass
class Sample:
    rows: list[MatchRow]
    start_ratings: dict[str, float]


def load_calibration() -> Calibration:
    path = DATA_DIR / "calibrated_params.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Calibration(
            home_advantage=float(payload.get("home_advantage", 60.0)),
            nu=float(payload.get("nu", 0.9)),
            elo_scale=float(payload.get("elo_scale", 400)),
        )
    return Calibration(home_advantage=60.0, nu=0.9)


def load_sample() -> Sample:
    snapshot = get_snapshot()
    if snapshot.demo:
        raise SystemExit(
            "El análisis necesita datos reales (DATA_SOURCE=openfootball), no la demo."
        )
    start_ratings = snapshot.elo_by_matchday.get(1, {})
    if not start_ratings:
        raise SystemExit("El snapshot no contiene los ratings de inicio de temporada.")

    rows: list[MatchRow] = []
    for match in snapshot.matches:
        if not match.is_played or not match.has_score:
            continue
        if match.home_id not in start_ratings or match.away_id not in start_ratings:
            continue
        assert match.home_goals is not None and match.away_goals is not None
        if match.home_goals > match.away_goals:
            outcome = 0
        elif match.home_goals < match.away_goals:
            outcome = 2
        else:
            outcome = 1
        rows.append(
            MatchRow(
                matchday=match.matchday,
                home_id=match.home_id,
                away_id=match.away_id,
                home_goals=match.home_goals,
                away_goals=match.away_goals,
                outcome=outcome,
                kickoff=match.kickoff or "",
            )
        )
    rows.sort(key=lambda row: (row.matchday, row.kickoff, row.home_id, row.away_id))
    if not rows:
        raise SystemExit("No hay partidos jugados de 2026/27 para evaluar.")
    return Sample(rows=rows, start_ratings=start_ratings)


def davidson_probabilities(
    delta: float, home_advantage: float, nu: float, scale: float = 400.0
) -> tuple[float, float, float]:
    strength = 10.0 ** ((delta + home_advantage) / scale)
    root = math.sqrt(strength)
    denominator = strength + 1.0 + nu * root
    return (
        strength / denominator,
        nu * root / denominator,
        1.0 / denominator,
    )


def predict_prior(
    sample: Sample, calibration: Calibration, alpha: float = 1.0
) -> np.ndarray:
    probabilities = np.empty((len(sample.rows), 3), dtype=float)
    for index, row in enumerate(sample.rows):
        delta = sample.start_ratings[row.home_id] - sample.start_ratings[row.away_id]
        probabilities[index] = davidson_probabilities(
            alpha * delta,
            calibration.home_advantage,
            calibration.nu,
            calibration.elo_scale,
        )
    return probabilities


def predict_equal_teams(
    sample: Sample, home_advantage: float, nu: float
) -> np.ndarray:
    probability = davidson_probabilities(0.0, home_advantage, nu)
    return np.tile(np.array(probability, dtype=float), (len(sample.rows), 1))


def predict_walk_forward(sample: Sample, calibration: Calibration) -> np.ndarray:
    ratings = dict(sample.start_ratings)
    probabilities = np.empty((len(sample.rows), 3), dtype=float)
    for index, row in enumerate(sample.rows):
        probabilities[index] = davidson_probabilities(
            ratings[row.home_id] - ratings[row.away_id],
            calibration.home_advantage,
            calibration.nu,
            calibration.elo_scale,
        )
        home_after, away_after = update_ratings(
            ratings[row.home_id],
            ratings[row.away_id],
            row.home_goals,
            row.away_goals,
            k=DEFAULT_K,
            home_advantage=DEFAULT_HOME_ADVANTAGE,
        )
        ratings[row.home_id] = home_after
        ratings[row.away_id] = away_after
    return probabilities


def evaluate(probabilities: np.ndarray, outcomes: np.ndarray) -> dict[str, float]:
    rows = np.arange(len(outcomes))
    chosen = np.clip(probabilities[rows, outcomes], 1e-12, 1.0)
    one_hot = np.zeros_like(probabilities)
    one_hot[rows, outcomes] = 1.0
    return {
        "matches": int(len(outcomes)),
        "accuracy": float(np.mean(np.argmax(probabilities, axis=1) == outcomes)),
        "log_loss": float(-np.mean(np.log(chosen))),
        "brier": float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))),
        "brier_home": float(np.mean((probabilities[:, 0] - one_hot[:, 0]) ** 2)),
        "brier_draw": float(np.mean((probabilities[:, 1] - one_hot[:, 1]) ** 2)),
        "brier_away": float(np.mean((probabilities[:, 2] - one_hot[:, 2]) ** 2)),
    }


def reliability_table(
    probabilities: np.ndarray, outcomes: np.ndarray, class_index: int
) -> tuple[list[dict[str, float | int]], float]:
    predicted = probabilities[:, class_index]
    observed = (outcomes == class_index).astype(float)
    edges = np.linspace(0.0, 1.0, 11)
    rows: list[dict[str, float | int]] = []
    ece = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        if upper == 1.0:
            mask = (predicted >= lower) & (predicted <= upper)
        else:
            mask = (predicted >= lower) & (predicted < upper)
        count = int(mask.sum())
        if count == 0:
            continue
        mean_predicted = float(predicted[mask].mean())
        observed_rate = float(observed[mask].mean())
        ece += (count / len(predicted)) * abs(mean_predicted - observed_rate)
        rows.append(
            {
                "bin": f"{lower:.1f}-{upper:.1f}",
                "count": count,
                "predicted": mean_predicted,
                "observed": observed_rate,
                "gap": observed_rate - mean_predicted,
            }
        )
    return rows, ece


def negative_log_likelihood(
    alpha: float,
    sample: Sample,
    calibration: Calibration,
    outcomes: np.ndarray,
) -> float:
    probabilities = predict_prior(sample, calibration, alpha)
    rows = np.arange(len(outcomes))
    chosen = np.clip(probabilities[rows, outcomes], 1e-12, 1.0)
    return float(-np.mean(np.log(chosen)))


def fit_alpha(
    sample: Sample, calibration: Calibration, outcomes: np.ndarray
) -> float:
    result = minimize_scalar(
        negative_log_likelihood,
        bounds=(0.2, 4.0),
        method="bounded",
        args=(sample, calibration, outcomes),
    )
    return float(result.x)


def profile_alpha_interval(
    sample: Sample, calibration: Calibration, outcomes: np.ndarray
) -> tuple[float, float, float]:
    grid = np.linspace(0.2, 4.0, 381)
    losses = np.array(
        [
            negative_log_likelihood(alpha, sample, calibration, outcomes)
            for alpha in grid
        ]
    )
    best = float(losses.min())
    threshold = chi2.ppf(0.95, 1) / (2.0 * len(outcomes))
    inside = grid[losses - best <= threshold]
    return float(inside.min()), float(inside.max()), float(grid[int(np.argmin(losses))])


def fit_home_nu(
    sample: Sample,
    calibration: Calibration,
    outcomes: np.ndarray,
    alpha: float = 1.0,
    starts: tuple[tuple[float, float], ...] | None = None,
) -> tuple[float, float, float]:
    def objective(theta: np.ndarray) -> float:
        home_advantage, nu = float(theta[0]), float(theta[1])
        if nu <= 0:
            return 1e12
        probabilities = np.empty((len(sample.rows), 3), dtype=float)
        for index, row in enumerate(sample.rows):
            delta = (
                sample.start_ratings[row.home_id] - sample.start_ratings[row.away_id]
            )
            probabilities[index] = davidson_probabilities(
                alpha * delta, home_advantage, nu, calibration.elo_scale
            )
        chosen = np.clip(
            probabilities[np.arange(len(outcomes)), outcomes], 1e-12, 1.0
        )
        return float(-np.mean(np.log(chosen)))

    best_result = None
    candidate_starts = starts or (
        (calibration.home_advantage, calibration.nu),
        (60.0, 0.9),
        (120.0, 1.2),
        (0.0, 0.5),
    )
    for start in candidate_starts:
        result = minimize(
            objective,
            x0=np.array(start),
            method="L-BFGS-B",
            bounds=[(-200.0, 400.0), (1e-3, 5.0)],
        )
        if best_result is None or result.fun < best_result.fun:
            best_result = result
    assert best_result is not None
    return float(best_result.x[0]), float(best_result.x[1]), float(best_result.fun)


def bootstrap_ci(
    sample: Sample,
    calibration: Calibration,
    outcomes: np.ndarray,
    statistic,
    *,
    iterations: int = BOOTSTRAP,
    seed: int = SEED,
) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(iterations):
        indices = rng.integers(0, len(sample.rows), size=len(sample.rows))
        resampled = Sample(
            rows=[sample.rows[index] for index in indices],
            start_ratings=sample.start_ratings,
        )
        values.append(statistic(resampled, calibration, outcomes[indices]))
    return (
        float(np.mean(values)),
        float(np.percentile(values, 2.5)),
        float(np.percentile(values, 97.5)),
    )


def paired_log_loss_difference(
    first: np.ndarray,
    second: np.ndarray,
    outcomes: np.ndarray,
    *,
    iterations: int = BOOTSTRAP,
    seed: int = SEED,
) -> tuple[float, float, float]:
    rows = np.arange(len(outcomes))
    first_loss = -np.log(np.clip(first[rows, outcomes], 1e-12, 1.0))
    second_loss = -np.log(np.clip(second[rows, outcomes], 1e-12, 1.0))
    difference = first_loss - second_loss
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(iterations):
        indices = rng.integers(0, len(outcomes), size=len(outcomes))
        means.append(float(difference[indices].mean()))
    return (
        float(difference.mean()),
        float(np.percentile(means, 2.5)),
        float(np.percentile(means, 97.5)),
    )


def team_points(sample: Sample) -> dict[str, int]:
    points = {team_id: 0 for team_id in sample.start_ratings}
    for row in sample.rows:
        if row.outcome == 0:
            points[row.home_id] += 3
        elif row.outcome == 2:
            points[row.away_id] += 3
        else:
            points[row.home_id] += 1
            points[row.away_id] += 1
    return points


def main() -> int:
    sample = load_sample()
    calibration = load_calibration()
    outcomes = np.array([row.outcome for row in sample.rows], dtype=int)

    prior = predict_prior(sample, calibration)
    walk_forward = predict_walk_forward(sample, calibration)
    equal_teams = predict_equal_teams(sample, calibration.home_advantage, calibration.nu)

    prior_metrics = evaluate(prior, outcomes)
    walk_metrics = evaluate(walk_forward, outcomes)
    equal_metrics = evaluate(equal_teams, outcomes)

    alpha_hat = fit_alpha(sample, calibration, outcomes)
    nll_alpha_one = negative_log_likelihood(1.0, sample, calibration, outcomes)
    nll_alpha_hat = negative_log_likelihood(alpha_hat, sample, calibration, outcomes)
    lr_statistic = 2.0 * len(outcomes) * (nll_alpha_one - nll_alpha_hat)
    alpha_p_value = float(1.0 - chi2.cdf(max(lr_statistic, 0.0), df=1))

    alpha_mean, alpha_low, alpha_high = bootstrap_ci(
        sample, calibration, outcomes, lambda s, c, o: fit_alpha(s, c, o)
    )
    profile_low, profile_high, profile_best = profile_alpha_interval(
        sample, calibration, outcomes
    )

    home_hat, nu_hat, nll_home_nu = fit_home_nu(sample, calibration, outcomes)
    home_mean, home_low, home_high = bootstrap_ci(
        sample,
        calibration,
        outcomes,
        lambda s, c, o: fit_home_nu(
            s, c, o, starts=((c.home_advantage, c.nu),)
        )[0],
        iterations=H_NU_BOOTSTRAP,
    )
    nu_mean, nu_low, nu_high = bootstrap_ci(
        sample,
        calibration,
        outcomes,
        lambda s, c, o: fit_home_nu(
            s, c, o, starts=((c.home_advantage, c.nu),)
        )[1],
        iterations=H_NU_BOOTSTRAP,
    )
    nll_training_params = negative_log_likelihood(1.0, sample, calibration, outcomes)
    joint_lr = 2.0 * len(outcomes) * (nll_training_params - nll_home_nu)
    joint_p_value = float(1.0 - chi2.cdf(max(joint_lr, 0.0), df=2))

    accuracy_mean, accuracy_low, accuracy_high = bootstrap_ci(
        sample,
        calibration,
        outcomes,
        lambda s, c, o: evaluate(predict_prior(s, c), o)["accuracy"],
    )
    log_loss_mean, log_loss_low, log_loss_high = bootstrap_ci(
        sample,
        calibration,
        outcomes,
        lambda s, c, o: evaluate(predict_prior(s, c), o)["log_loss"],
    )
    brier_mean, brier_low, brier_high = bootstrap_ci(
        sample,
        calibration,
        outcomes,
        lambda s, c, o: evaluate(predict_prior(s, c), o)["brier"],
    )

    diff_mean, diff_low, diff_high = paired_log_loss_difference(
        prior, walk_forward, outcomes
    )
    equal_diff_mean, equal_diff_low, equal_diff_high = paired_log_loss_difference(
        prior, equal_teams, outcomes
    )

    reliability = {
        index: reliability_table(prior, outcomes, index) for index in range(3)
    }

    points = team_points(sample)
    team_ids = list(sample.start_ratings)
    ratings = np.array([sample.start_ratings[team_id] for team_id in team_ids])
    points_per_match = np.array(
        [
            points[team_id]
            / max(1, sum(1 for row in sample.rows if team_id in (row.home_id, row.away_id)))
            for team_id in team_ids
        ]
    )
    spearman = float(spearmanr(ratings, points_per_match).statistic)
    slope = float(np.polyfit(ratings, points_per_match, 1)[0])

    print("=" * 78)
    print("CALIBRACIÓN DE LOS ELO DE INICIO DE 2026/27")
    print("=" * 78)
    print(f"Partidos jugados evaluados: {len(sample.rows)}")
    print(
        "Resultados observados: "
        f"local {int(np.sum(outcomes == 0))} · empate {int(np.sum(outcomes == 1))} · "
        f"visitante {int(np.sum(outcomes == 2))}"
    )
    print(
        f"Equipos: {len(team_ids)} · jornadas: {min(r.matchday for r in sample.rows)}–"
        f"{max(r.matchday for r in sample.rows)}"
    )
    print(
        f"Ratings de inicio: media {ratings.mean():.1f} · desviación {ratings.std():.1f} "
        f"· rango {ratings.min():.1f}–{ratings.max():.1f}"
    )
    print(
        f"Calibración Davidson congelada: H={calibration.home_advantage:.2f} · "
        f"nu={calibration.nu:.4f} · escala={calibration.elo_scale:.0f}"
    )
    print()

    print("Métricas (con los ELO de inicio, sin actualizar):")
    print(
        f"  accuracy {prior_metrics['accuracy']:.4f} "
        f"[{accuracy_low:.4f}, {accuracy_high:.4f}]"
    )
    print(
        f"  log-loss {prior_metrics['log_loss']:.4f} "
        f"[{log_loss_low:.4f}, {log_loss_high:.4f}]"
    )
    print(
        f"  Brier    {prior_metrics['brier']:.4f} "
        f"[{brier_low:.4f}, {brier_high:.4f}]"
    )
    print(
        f"  Brier por clase: local {prior_metrics['brier_home']:.4f} · "
        f"empate {prior_metrics['brier_draw']:.4f} · "
        f"visitante {prior_metrics['brier_away']:.4f}"
    )
    print()

    print("Comparación:")
    print(
        f"  baseline sin ELO (equipos iguales): accuracy {equal_metrics['accuracy']:.4f} "
        f"· log-loss {equal_metrics['log_loss']:.4f} · Brier {equal_metrics['brier']:.4f}"
    )
    print(
        f"  walk-forward (ELO actualizado):     accuracy {walk_metrics['accuracy']:.4f} "
        f"· log-loss {walk_metrics['log_loss']:.4f} · Brier {walk_metrics['brier']:.4f}"
    )
    print(
        f"  Δ log-loss prior − walk-forward: {diff_mean:+.4f} "
        f"[{diff_low:+.4f}, {diff_high:+.4f}] (positivo = el prior es peor)"
    )
    print(
        f"  Δ log-loss prior − sin ELO:     {equal_diff_mean:+.4f} "
        f"[{equal_diff_low:+.4f}, {equal_diff_high:+.4f}] (negativo = el prior es mejor)"
    )
    print()

    observed_rates = np.bincount(outcomes, minlength=3) / len(outcomes)
    mean_predicted = prior.mean(axis=0)
    print("Media predicha vs frecuencia observada:")
    for index, name in enumerate(CLASS_NAMES):
        print(
            f"  {name:10} pred {mean_predicted[index]:.4f} · "
            f"obs {observed_rates[index]:.4f} · "
            f"gap {observed_rates[index] - mean_predicted[index]:+.4f}"
        )
    print()

    print("Por tramo de jornadas (log-loss / accuracy):")
    for label, low, high in (("J1–J3", 1, 3), ("J4–J6", 4, 6), ("J7–J9", 7, 9)):
        indices = [
            index
            for index, row in enumerate(sample.rows)
            if low <= row.matchday <= high
        ]
        if not indices:
            continue
        prior_slice = evaluate(prior[indices], outcomes[indices])
        walk_slice = evaluate(walk_forward[indices], outcomes[indices])
        print(
            f"  {label}: n={len(indices):2} · prior {prior_slice['log_loss']:.4f} / "
            f"walk {walk_slice['log_loss']:.4f} · acc "
            f"{prior_slice['accuracy']:.3f} / {walk_slice['accuracy']:.3f}"
        )
    print()

    print("Fiabilidad por clase (predicción media vs frecuencia observada):")
    for index, name in enumerate(CLASS_NAMES):
        rows, ece = reliability[index]
        print(f"  {name}: ECE {ece:.4f}")
        for row in rows:
            print(
                f"    {row['bin']:>7}  n={row['count']:>2}  "
                f"pred={row['predicted']:.3f}  obs={row['observed']:.3f}  "
                f"gap={row['gap']:+.3f}"
            )
    print()

    print("Ajuste de dispersión (alpha sobre la diferencia de ELO):")
    print(
        f"  alpha_hat = {alpha_hat:.4f} · bootstrap [{alpha_low:.4f}, "
        f"{alpha_high:.4f}] · perfil [{profile_low:.4f}, {profile_high:.4f}]"
    )
    print(f"  escala implícita = {calibration.elo_scale / alpha_hat:.1f}")
    print(
        f"  H0 alpha=1: LR={lr_statistic:.3f} · p={alpha_p_value:.4f} "
        f"({'se rechaza' if alpha_p_value < 0.05 else 'no se rechaza'})"
    )
    if alpha_hat < 1:
        print("  Interpretación: los ELO de inicio están sobredispuestos (demasiado separados).")
    elif alpha_hat > 1:
        print("  Interpretación: los ELO de inicio están subdispuestos (demasiado juntos).")
    else:
        print("  Interpretación: la dispersión es adecuada.")
    print()

    print("Recalibración de H y nu sobre 2026/27 (alpha=1):")
    print(f"  H_hat  = {home_hat:.2f} [{home_low:.2f}, {home_high:.2f}] (entrenamiento {calibration.home_advantage:.2f})")
    print(f"  nu_hat = {nu_hat:.4f} [{nu_low:.4f}, {nu_high:.4f}] (entrenamiento {calibration.nu:.4f})")
    print(
        f"  H0 H=entrenamiento y nu=entrenamiento: LR={joint_lr:.3f} · "
        f"p={joint_p_value:.4f} "
        f"({'se rechaza' if joint_p_value < 0.05 else 'no se rechaza'})"
    )
    print()

    print("Validez predictiva de los ratings (9 jornadas):")
    print(f"  Spearman(rating inicio, puntos/partido) = {spearman:.4f}")
    print(f"  pendiente puntos/partido por 100 puntos ELO = {slope * 100:.4f}")
    print()

    snapshot = get_snapshot()
    baseline = snapshot.elo_verification.get("baseline", {})
    moved = [
        sample.start_ratings[team_id] - baseline[team_id]
        for team_id in sample.start_ratings
        if baseline.get(team_id) is not None
    ]
    if moved:
        moved_array = np.array(moved)
        print("Profundidad histórica y sensibilidad:")
        print("  Reconstrucción ELO: 2020/21–2024/25 (5 temporadas) + replay 2025/26.")
        if (DATA_DIR / "calibrated_params.json").exists():
            payload = json.loads(
                (DATA_DIR / "calibrated_params.json").read_text(encoding="utf-8")
            )
            trained = payload.get("trained_on", [2022, 2023, 2024])
            print(f"  Ajuste de Davidson: temporadas {trained}.")
        print(
            f"  Movimiento absoluto medio por 2025/26: {np.mean(np.abs(moved_array)):.1f} "
            f"puntos · máximo {np.max(np.abs(moved_array)):.1f} · "
            f"desviación {moved_array.std():.1f}"
        )
        print(
            f"  Desviación de los ratings de inicio: {ratings.std():.1f} puntos; "
            f"el movimiento de una sola temporada es del mismo orden."
        )
        print()

    print("Lectura:")
    if profile_low <= 1.0 <= profile_high:
        print("  - El factor de dispersión no se distingue de 1 con esta muestra:")
        print("    no hay evidencia fuerte de sobre/subconfianza en los ELO de inicio.")
    elif profile_high < 1.0:
        print("  - alpha < 1: los ratings están demasiado separados (sobredispersión).")
        print("    Conviene encoger las diferencias hacia la media o alargar el histórico.")
    elif profile_low > 1.0:
        print("  - alpha > 1: los ratings están demasiado juntos (subdispersión).")
        print("    Conviene aumentar la dispersión o revisar la escala de calibración.")
    if profile_low <= 0.2001 or profile_high >= 3.999:
        print("    Aviso: el intervalo de perfil toca el límite de búsqueda; alpha está")
        print("    poco identificado con 88 partidos.")
    if alpha_p_value >= 0.05:
        print(
            f"  - El test de razón de verosimilitud no rechaza alpha=1 "
            f"(p={alpha_p_value:.3f}); la evidencia es débil."
        )
    if joint_p_value < 0.05:
        print("  - H y nu calibrados con 2020/21–2023/24 no describen bien 2026/27.")
        print("    La muestra es corta; revisar con más jornadas antes de recalibrar.")
    else:
        print("  - H y nu de 2020/21–2023/24 siguen siendo compatibles con 2026/27.")
    if equal_diff_high < 0.0:
        print("  - Los ELO de inicio baten claramente al modelo sin ELO.")
    elif equal_diff_low > 0.0:
        print("  - Los ELO de inicio no baten al modelo sin ELO en esta muestra.")
    else:
        print("  - La mejora frente al modelo sin ELO es positiva pero no concluyente.")
    print(
        f"  - Fiabilidad media: ECE local {reliability[0][1]:.3f}, "
        f"empate {reliability[1][1]:.3f}, visitante {reliability[2][1]:.3f}."
    )
    if observed_rates[1] - mean_predicted[1] > 0.02:
        print("    El empate se predice por debajo de su frecuencia observada.")
    elif mean_predicted[1] - observed_rates[1] > 0.02:
        print("    El empate se predice por encima de su frecuencia observada.")
    print(
        f"  - Muestra: {len(sample.rows)} partidos y {len(team_ids)} equipos "
        "(9 jornadas). Los intervalos son anchos; revisar al completar la temporada."
    )
    print(
        "  - La calibración de H/nu usó 4 temporadas de entrenamiento "
        "(2020/21–2023/24, 1.520 partidos) y validación en 2024/25; "
        "los ratings añaden el replay de 2025/26."
    )
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
