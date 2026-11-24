import math

import pytest

from app.data.history import HistoryMatch, compute_elo_history, evaluate_predictions


def test_compute_elo_history_updates_ratings_and_carries_seasons():
    matches = [
        HistoryMatch(2022, "2022-08-10", "A", "B", 2, 0),
        HistoryMatch(2022, "2022-08-17", "B", "C", 1, 1),
        HistoryMatch(2023, "2023-08-10", "A", "C", 0, 1),
    ]
    history = compute_elo_history(matches)
    assert len(history.samples) == 3
    assert history.samples[0][0] == pytest.approx(0.0)
    assert history.samples[0][1] == "H"
    assert history.season_starts[2023]["A"] > 1500
    assert history.season_starts[2023]["B"] < 1500
    assert history.season_ends[2023]["C"] > history.season_starts[2023]["C"]


def test_evaluate_predictions_returns_accuracy_log_loss_and_brier():
    probabilities = [(0.7, 0.2, 0.1), (0.2, 0.3, 0.5)]
    outcomes = ["H", "A"]
    metrics = evaluate_predictions(probabilities, outcomes)
    assert metrics["accuracy"] == pytest.approx(1.0)
    assert metrics["log_loss"] == pytest.approx(
        -(math.log(0.7) + math.log(0.5)) / 2
    )
    assert metrics["brier"] == pytest.approx(
        ((0.3**2 + 0.2**2 + 0.1**2) + (0.2**2 + 0.3**2 + 0.5**2)) / 2
    )
