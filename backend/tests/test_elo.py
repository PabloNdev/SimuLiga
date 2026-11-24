import pytest

from app.domain.elo import expected_score, update_ratings


def test_equal_ratings_have_even_expectation():
    assert expected_score(1500, 1500) == pytest.approx(0.5)


def test_400_point_gap_gives_ten_to_one_expectation():
    assert expected_score(1900, 1500) == pytest.approx(10 / 11, abs=1e-6)


def test_home_advantage_is_added_to_home_expectation():
    assert expected_score(1500, 1500, home_advantage=100) > 0.5


def test_home_win_increases_home_rating_and_preserves_total():
    home_after, away_after = update_ratings(1500, 1500, 2, 0)
    assert home_after > 1500
    assert away_after < 1500
    assert home_after + away_after == pytest.approx(3000)


def test_away_win_increases_away_rating():
    home_after, away_after = update_ratings(1700, 1500, 1, 3)
    assert away_after > 1500
    assert home_after < 1700


def test_bigger_win_moves_rating_more_than_narrow_win():
    narrow_home, _ = update_ratings(1500, 1500, 1, 0)
    big_home, _ = update_ratings(1500, 1500, 5, 0)
    assert big_home > narrow_home


def test_draw_between_equal_teams_keeps_ratings_without_home_advantage():
    home_after, away_after = update_ratings(1500, 1500, 1, 1, home_advantage=0)
    assert home_after == pytest.approx(1500)
    assert away_after == pytest.approx(1500)


def test_draw_after_home_advantage_punishes_home_side():
    home_after, away_after = update_ratings(1500, 1500, 1, 1, home_advantage=100)
    assert home_after < 1500
    assert away_after > 1500
