# SimuChampions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Champions League module to SimuLiga with real 2025/26 calibration, 2026/27 league-phase projections and playoff forecasts.

**Architecture:** Keep the existing Elo, Davidson and Dixon-Coles math shared. Add an isolated `app/champions` package for the UCL format, data pipeline, standings, simulation and API. Add separate `/champions` routes and components in the frontend, leaving LaLiga untouched.

**Tech Stack:** Python 3.12, FastAPI, numpy, scipy, httpx, pytest, Next.js 16, React 19, TypeScript.

**Spec:** `docs/superpowers/specs/2026-10-23-simuchampions-design.md`

## Global Constraints

- Do not change LaLiga endpoints, data files, calculations or UI behavior.
- Do not add new Python or npm dependencies.
- Python tests run from `backend/` with `python -m pytest tests -q`.
- Frontend checks run from `frontend/` with `npm run lint` and `npm run build`.
- The workspace is not a git repository. Skip commit steps; use the test checkpoints as review gates.
- API-Football free plans may not cover 2025/26 or 2026/27. The pipeline must fall back to OpenFootball `cl.txt`, then cached/last valid data, then a clearly labelled demo.
- ClubElo may be unreachable. The pipeline must fall back to 1500 seeds and record `seed_source`.
- All user-facing copy is Spanish. Code identifiers are English.
- Reuse `app.domain.elo`, `app.domain.davidson`, `app.domain.scoreline`, `app.data.clubelo` and `app.data.names`.

---

## Task 1: Champions foundations and OpenFootball parser

**Files:**
- Create: `backend/app/champions/__init__.py`
- Create: `backend/app/champions/config.py`
- Create: `backend/app/champions/models.py`
- Create: `backend/app/champions/names.py`
- Create: `backend/app/champions/data/__init__.py`
- Create: `backend/app/champions/data/openfootball.py`
- Create: `backend/tests/fixtures/champions_cl_2025_26.txt`
- Test: `backend/tests/test_champions_openfootball.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ChampionsSettings` with `league_id`, `season`, `previous_season`, `data_source`, `clubelo_date_2025`, `clubelo_date_2026`, `cache_dir`, `cache_ttl_seconds`, `snapshot_ttl_seconds`.
  - `ChampionsTeam`, `ChampionsMatch`, `ChampionsSnapshot` dataclasses.
  - `normalize_team_key(name)`, `clean_provider_name(name)`, `TEAM_SEEDS`, `TEAM_ALIASES`, `team_key_map()`.
  - `parse_openfootball_cl(text) -> list[dict]`.

- [ ] **Step 1: Create the fixture**

Download the real 2025/26 file and save it offline:

```powershell
New-Item -ItemType Directory -Force -Path backend\tests\fixtures | Out-Null
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/openfootball/champions-league/master/2025-26/cl.txt' -OutFile backend\tests\fixtures\champions_cl_2025_26.txt
```

- [ ] **Step 2: Write the failing test**

```python
from pathlib import Path

from app.champions.data.openfootball import parse_openfootball_cl

FIXTURE = Path(__file__).parent / "fixtures" / "champions_cl_2025_26.txt"


def test_openfootball_parses_all_2025_26_matches():
    matches = parse_openfootball_cl(FIXTURE.read_text(encoding="utf-8"))
    assert len(matches) == 189
    league = [match for match in matches if match["phase"] == "league"]
    assert len(league) == 144
    assert {match["matchday"] for match in league} == set(range(1, 9))
    assert len({match["home"] for match in matches}) == 36
    assert all(match["home_goals"] is not None for match in matches)
    final = [match for match in matches if match["phase"] == "final"][0]
    assert final["neutral"] is True
    assert final["home"] == "Paris Saint-Germain FC"
    assert final["away"] == "Arsenal FC"
    assert (final["home_goals"], final["away_goals"]) == (1, 1)


def test_openfootball_parses_extra_time_and_penalties_as_90_minutes():
    text = """
= UEFA Champions League 2025/26

? Finals, Final
  Sat May 30
    18:00  Paris Saint-Germain FC (FRA) v Arsenal FC (ENG)  4-3 pen. 1-1 a.e.t. (1-1, 0-1)
"""
    matches = parse_openfootball_cl(text)
    assert (matches[0]["home_goals"], matches[0]["away_goals"]) == (1, 1)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `python -m pytest tests/test_champions_openfootball.py -v`
Expected: FAIL because the module does not exist.

- [ ] **Step 4: Implement the parser**

`openfootball.py` must:

- Split lines and track the current section from lines starting with `?`.
- Track dates from lines like `Tue Sep 16 2025` and `Wed Sep 17`.
- Parse match lines with `team1 v team2 score`.
- Strip `(ENG)`-style country suffixes from names.
- Map sections:
  - `League, Matchday N` → `phase="league"`, `matchday=N`.
  - `Playoffs, Matchday N` → `phase="playoff"`, `matchday=N`, `leg=N`.
  - `Finals, Round of 16` → `phase="r16"`, `leg` inferred from the appearance order (first 8 matches leg 1, next 8 leg 2).
  - `Finals, Quarterfinals` → `phase="qf"`.
  - `Finals, Semifinals` → `phase="sf"`.
  - `Finals, Final` → `phase="final"`, `neutral=True`.
- Extract the 90-minute score:
  - plain `2-1` → `(2, 1)`;
  - `3-2 a.e.t. (3-0, 1-0)` → use the first parenthesised score `(3, 0)`;
  - `4-3 pen. 1-1 a.e.t. (1-1, 0-1)` → use the first parenthesised score `(1, 1)`;
  - if no parenthesised score exists, use the main score.
- Return dicts with `phase`, `matchday`, `leg`, `home`, `away`, `home_goals`, `away_goals`, `kickoff`, `neutral`.

Use a regex equivalent to:

```python
MATCH_RE = re.compile(
    r"^\s*(?:(?P<time>\d{1,2}:\d{2})\s+)?"
    r"(?P<home>.+?)\s+v\s+(?P<away>.+?)\s+"
    r"(?P<score>\d+-\d+)(?P<extra>.*)$"
)
```

Parse the parenthesised 90-minute score from `extra` when present:

```python
PAREN_SCORE_RE = re.compile(r"\((\d+)-(\d+)")
```

- [ ] **Step 5: Add config and models**

`config.py`:

```python
class ChampionsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHAMPIONS_", env_file=".env", extra="ignore")
    league_id: int = 2
    season: int = 2026
    previous_season: int = 2025
    data_source: str = "auto"
    clubelo_date_2025: str = "2025-08-01"
    clubelo_date_2026: str = "2026-08-01"
    cache_dir: str = ".cache"
    cache_ttl_seconds: int = 21_600
    snapshot_ttl_seconds: int = 3_600
    api_football_key: str = ""
    fallback_rewind_matchday: int = 4
```

`models.py`:

```python
Phase = Literal["league", "playoff", "r16", "qf", "sf", "final"]

@dataclass(frozen=True)
class ChampionsTeam:
    id: str
    name: str
    short_name: str
    color: str
    country: str
    elo: float
    pot: int | None = None
    coefficient: float | None = None
    def with_elo(self, elo: float) -> "ChampionsTeam": ...

@dataclass(frozen=True)
class ChampionsMatch:
    id: str
    phase: Phase
    matchday: int
    leg: int
    home_id: str
    away_id: str
    home_goals: int | None = None
    away_goals: int | None = None
    kickoff: str | None = None
    neutral: bool = False
    @property
    def has_score(self) -> bool: ...
    @property
    def is_played(self) -> bool: ...
    @property
    def result(self) -> Outcome | None: ...

@dataclass(frozen=True)
class ChampionsSnapshot:
    competition: str
    season: str
    source: str
    updated_at: str
    teams: list[ChampionsTeam]
    matches: list[ChampionsMatch]
    data_version: str
    demo: bool
    data_note: str | None
    elo_by_matchday: dict[int, dict[str, float]]
    elo_history: dict
    elo_verification: dict
    elo_timeline: dict
    model: dict
```

`names.py` must define the 36 2025/26 teams with canonical id, name, short name, color, country, and aliases for API-Football, OpenFootball and ClubElo. At minimum cover the teams present in the fixture. Fallback teams use `slugify` and a rotating palette.

- [ ] **Step 6: Run tests and fix**

Run: `python -m pytest tests/test_champions_openfootball.py -v`
Expected: PASS.

---

## Task 2: API-Football adapter and source selection

**Files:**
- Create: `backend/app/champions/data/api_football.py`
- Test: `backend/tests/test_champions_api_football.py`

**Interfaces:**
- Consumes: `ChampionsSettings`, parser helpers from `openfootball.py`.
- Produces:
  - `fetch_api_matches(settings, season) -> list[dict]`
  - `parse_api_fixtures(payload, season) -> list[dict]`
  - `load_source_matches(settings, season) -> tuple[list[dict], str]`

- [ ] **Step 1: Write failing tests with a small fixture payload**

```python
from app.champions.data.api_football import parse_api_fixtures

PAYLOAD = {"response": [
    {
        "fixture": {"id": 1, "date": "2025-09-16T16:45:00+00:00", "status": {"short": "FT"}},
        "league": {"round": "League Stage - 1"},
        "teams": {"home": {"name": "Athletic Club"}, "away": {"name": "Arsenal"}},
        "goals": {"home": 0, "away": 2},
        "score": {"fulltime": {"home": 0, "away": 2}},
    },
    {
        "fixture": {"id": 2, "date": "2026-05-30T16:00:00+00:00", "status": {"short": "PEN"}},
        "league": {"round": "Final"},
        "teams": {"home": {"name": "Paris Saint-Germain"}, "away": {"name": "Arsenal"}},
        "goals": {"home": 4, "away": 3},
        "score": {
            "fulltime": {"home": 1, "away": 1},
            "extratime": {"home": 1, "away": 1},
            "penalty": {"home": 4, "away": 3},
        },
    },
]}


def test_api_parser_uses_90_minute_score_and_neutral_final():
    matches = parse_api_fixtures(PAYLOAD, 2025)
    assert matches[0]["phase"] == "league"
    assert matches[0]["matchday"] == 1
    assert matches[0]["home_goals"] == 0
    assert matches[1]["phase"] == "final"
    assert matches[1]["neutral"] is True
    assert (matches[1]["home_goals"], matches[1]["away_goals"]) == (1, 1)
```

- [ ] **Step 2: Run it and see it fail**

Run: `python -m pytest tests/test_champions_api_football.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

- Paginate up to 20 pages, like `app.data.api_football`.
- Cache to `.cache/champions_api_{season}.json`.
- Use `x-apisports-key`.
- If `ChampionsSettings.api_football_key` is empty, read `Settings().api_football_key`.
- Normalize rounds:
  - `League Stage - N` → `league`, `N`;
  - `Knockout Round Playoffs` → `playoff`;
  - `Round of 16` → `r16`;
  - `Quarter-finals` → `qf`;
  - `Semi-finals` → `sf`;
  - `Final` → `final`.
- Exclude qualification rounds.
- Use `score.fulltime` for 90 minutes when present; otherwise `goals`.
- `neutral=True` only for `final`.
- `load_source_matches` order:
  - `auto`: API-Football, then OpenFootball, then raise `DataSourceError`.
  - `api-football`: API only.
  - `openfootball`: OpenFootball only.
  - `demo`: return `[]`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_champions_api_football.py -v`
Expected: PASS.

---

## Task 3: ELO replay, historical payload and calibration

**Files:**
- Create: `backend/app/champions/data/snapshot.py`
- Create: `backend/app/data/champions_historical.json` (generated)
- Create: `backend/app/data/champions_params.json` (generated)
- Test: `backend/tests/test_champions_elo.py`

**Interfaces:**
- Consumes: parsed match dicts, `ChampionsTeam`, `update_ratings`, `fit_davidson`.
- Produces:
  - `replay_matches(matches, teams, params) -> ReplayResult`
  - `build_historical_payload(matches, teams, params) -> dict`
  - `calibrate_params(matches, teams, params) -> dict`
  - `load_historical_payload() -> dict`
  - `load_params() -> dict`

- [ ] **Step 1: Write failing tests**

```python
from app.champions.data.snapshot import replay_matches
from app.champions.models import ChampionsTeam


def team(team_id, elo):
    return ChampionsTeam(team_id, team_id, team_id[:3].upper(), "#000000", "ESP", elo)


def test_replay_updates_both_sides_and_preserves_total():
    teams = [team("a", 1600.0), team("b", 1500.0)]
    matches = [{"home_id": "a", "away_id": "b", "home_goals": 2, "away_goals": 0, "neutral": False}]
    result = replay_matches(matches, teams, {"k": 20, "home_advantage": 60})
    assert result.ratings["a"] > 1600
    assert result.ratings["b"] < 1500
    assert result.ratings["a"] + result.ratings["b"] == 3100.0


def test_calibration_uses_pre_match_deltas():
    from app.champions.data.snapshot import calibration_samples
    teams = [team("a", 1600.0), team("b", 1500.0)]
    matches = [{"home_id": "a", "away_id": "b", "home_goals": 1, "away_goals": 0, "neutral": False, "phase": "league", "matchday": 1}]
    samples = calibration_samples(matches, teams, {"k": 20, "home_advantage": 60})
    assert samples[0][0] == 160.0
    assert samples[0][1] == "H"
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/test_champions_elo.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement replay**

- Sort by `kickoff`, then `id`.
- Before each match, record `delta = home_elo + (0 if neutral else H) - away_elo`.
- Apply `update_ratings` with `k=20`, `home_advantage=0 if neutral else 60`.
- Store `ratings`, `start_ratings`, `timeline` (one point per month), `applied`, `without_score`.
- Use only matches with both scores. Matches without a score are counted and skipped.

- [ ] **Step 4: Implement calibration**

- `calibration_samples` returns `(delta, outcome, phase, matchday)`.
- Split: `matchday <= 6` for training, the rest for validation.
- `fit_davidson` on training deltas/outcomes, evaluate validation.
- Final fit on all samples.
- Payload:

```json
{
  "home_advantage": 60.0,
  "nu": 0.9,
  "elo_scale": 400,
  "validation": {"matches": 0, "accuracy": 0.0, "log_loss": 0.0, "brier": 0.0},
  "generated_at": "..."
}
```

- [ ] **Step 5: Implement historical payload**

```json
{
  "season": "2025/26",
  "start_ratings": {"team": 1500.0},
  "final_ratings": {"team": 1550.0},
  "teams": ["team"],
  "timeline": [{"date": "2025-09-16", "ratings": {"team": 1500.0}}],
  "matches_total": 189,
  "matches_applied": 189,
  "seed_source": "clubelo" | "fallback_1500"
}
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_champions_elo.py -v`
Expected: PASS.

---

## Task 4: UCL standings and tiebreakers

**Files:**
- Create: `backend/app/champions/domain/__init__.py`
- Create: `backend/app/champions/domain/standings.py`
- Test: `backend/tests/test_champions_standings.py`

**Interfaces:**
- Consumes: `ChampionsMatch`.
- Produces:
  - `TeamRecord` with `played`, `won`, `drawn`, `lost`, `points`, `goals_for`, `goals_against`, `away_goals`, `wins`, `away_wins`.
  - `build_records(team_ids, matches) -> dict[str, TeamRecord]`
  - `rank_teams(team_ids, matches, *, random_keys=None) -> list[str]`

- [ ] **Step 1: Write failing tests**

```python
from app.champions.domain.standings import build_records, rank_teams


def test_points_then_goal_difference_then_goals():
    teams = ["a", "b", "c"]
    matches = []
    records = build_records(teams, matches)
    assert records["a"].points == 0
    assert rank_teams(teams, matches, random_keys={"a": 0.1, "b": 0.2, "c": 0.3}) == ["a", "b", "c"]


def test_away_goals_break_goal_difference_tie():
    from app.champions.models import ChampionsMatch

    def match(match_id, home, away, hg, ag):
        return ChampionsMatch(match_id, "league", 1, 0, home, away, hg, ag)

    matches = [
        match("m1", "c", "a", 0, 1),   # a: 3 pts, +1 GD, 1 GF, 1 away goal
        match("m2", "b", "c", 1, 0),   # b: 3 pts, +1 GD, 1 GF, 0 away goals
    ]
    assert rank_teams(["a", "b", "c"], matches) == ["a", "b", "c"]
```

- [ ] **Step 2: Run and see failure**

Run: `python -m pytest tests/test_champions_standings.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Ordering key (descending):

```python
(
    points,
    goal_difference,
    goals_for,
    away_goals,
    wins,
    away_wins,
    random_key,
)
```

`random_keys` is a `dict[str, float]`; missing values default to `0.0`. The final tiebreak must be deterministic for a given simulation.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_champions_standings.py -v`
Expected: PASS.

---

## Task 5: Playoff model

**Files:**
- Create: `backend/app/champions/domain/playoff.py`
- Test: `backend/tests/test_champions_playoff.py`

**Interfaces:**
- Consumes: `ChampionsTeam`, `ScorelineParams`, `prepare_scoreline`, `sample_prepared_scores`.
- Produces:
  - `PAIRINGS = [(9, 24), (10, 23), ...]`
  - `pair_slots(positions: dict[str, int]) -> list[tuple[str, str]]`
  - `simulate_tie(home_team, away_team, first_leg_home_id, params, rng) -> bool`
  - `simulate_playoff(positions_by_sim, teams, params, rng) -> dict`

- [ ] **Step 1: Write failing tests**

```python
from app.champions.domain.playoff import pair_slots


def test_pairings_are_deterministic():
    positions = {f"t{i}": i for i in range(1, 37)}
    pairs = pair_slots(positions)
    assert pairs[0] == ("t9", "t24")
    assert pairs[1] == ("t10", "t23")
    assert pairs[-1] == ("t16", "t17")
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/test_champions_playoff.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

- First leg at the worse-ranked team; second leg at the better-ranked team.
- Sample two 90-minute scorelines.
- Aggregate; if tied:
  - sample extra time with `home_lambda / 3` and `away_lambda / 3`;
  - if still tied, penalty winner via `rng.random() < 0.5`.
- Return the winning team id.
- `simulate_playoff` accumulates:
  - `advance_counts[team_id]`;
  - `opponent_counts[team_id][opponent_id]`;
  - `slot_counts[slot][team_id]`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_champions_playoff.py -v`
Expected: PASS.

---

## Task 6: League-phase Monte Carlo

**Files:**
- Create: `backend/app/champions/domain/simulation.py`
- Test: `backend/tests/test_champions_simulation.py`

**Interfaces:**
- Consumes: `ChampionsTeam`, `ChampionsMatch`, `prepare_scoreline`, `sample_prepared_scores`, `rank_teams`, `simulate_playoff`.
- Produces:
  - `ChampionsSimulationRequest`
  - `ChampionsSimulationResult`
  - `simulate_champions(request) -> ChampionsSimulationResult`

- [ ] **Step 1: Write failing tests**

```python
from app.champions.domain.simulation import ChampionsSimulationRequest, simulate_champions
from app.champions.models import ChampionsMatch, ChampionsTeam


def make_teams(count=36):
    return [ChampionsTeam(f"t{i}", f"Team {i}", f"T{i}", "#000000", "ESP", 1500.0 + i) for i in range(count)]


def make_matches(teams):
    matches = []
    for first in range(len(teams)):
        for second in range(first + 1, len(teams)):
            matches.append(
                ChampionsMatch(
                    f"m{first}-{second}",
                    "league",
                    1,
                    0,
                    teams[first].id,
                    teams[second].id,
                )
            )
    return matches


def test_probabilities_sum_to_one():
    teams = make_teams(8)
    request = ChampionsSimulationRequest(
        teams=teams, matches=make_matches(teams), n_sims=200, seed=1
    )
    result = simulate_champions(request)
    total = sum(
        team.top8_probability + team.playoff_probability + team.eliminated_probability
        for team in result.teams
    )
    assert total == pytest.approx(8.0, abs=1e-9)


def test_same_seed_is_deterministic():
    teams = make_teams(8)
    matches = make_matches(teams)
    first = simulate_champions(
        ChampionsSimulationRequest(teams=teams, matches=matches, n_sims=100, seed=7)
    )
    second = simulate_champions(
        ChampionsSimulationRequest(teams=teams, matches=matches, n_sims=100, seed=7)
    )
    assert [team.expected_points for team in first.teams] == [
        team.expected_points for team in second.teams
    ]
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/test_champions_simulation.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

- Accept 36 teams (tests may use 8 with a reduced top/playoff cut; compute cuts from team count: top 8 or `max(1, n//4)`, playoff to `n//2`, eliminated below).
- Base table from played matches.
- Pending matches sampled in chunks of 5,000.
- Fixed ELO for all pending matches.
- For each simulation:
  - build points, goals for/against, away goals, wins, away wins;
  - rank with `rank_teams` and random keys;
  - increment position histogram;
  - for positions 9-24, call `simulate_playoff` on the same simulation.
- Outputs:
  - `expected_points`, `points_std`, `median_points`, `p10_points`, `p90_points`;
  - `expected_position`, `most_likely_position`;
  - `position_probabilities` (length = team count);
  - `top8_probability`, `playoff_probability`, `eliminated_probability`;
  - `playoff_win_probability`, `round_of_16_probability`;
  - `opponent_probabilities: dict[str, float]`;
  - `match_predictions`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_champions_simulation.py -v`
Expected: PASS.

---

## Task 7: Snapshot builder, cache and demo fallback

**Files:**
- Modify: `backend/app/champions/data/snapshot.py`
- Test: `backend/tests/test_champions_snapshot.py`

**Interfaces:**
- Consumes: source loaders, replay, calibration, simulation models.
- Produces:
  - `get_champions_snapshot(force=False, settings=None) -> ChampionsSnapshot`
  - `build_demo_snapshot(settings=None) -> ChampionsSnapshot`
  - `build_snapshot_from_matches(previous_matches, current_matches, settings, ...) -> ChampionsSnapshot`
  - `_version(...)`

- [ ] **Step 1: Write failing test**

```python
from app.champions.data.snapshot import build_demo_snapshot


def test_demo_snapshot_has_36_teams_and_8_matchdays():
    snapshot = build_demo_snapshot()
    assert snapshot.demo is True
    assert len(snapshot.teams) == 36
    assert {match.matchday for match in snapshot.matches if match.phase == "league"} == set(range(1, 9))
    assert sum(1 for match in snapshot.matches if match.is_played) > 0
```

- [ ] **Step 2: Run and see failure**

Run: `python -m pytest tests/test_champions_snapshot.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement snapshot building**

1. Load previous-season matches (2025/26) via `load_source_matches`.
2. Resolve teams with `names.py`.
3. Seed ratings:
   - ClubElo if available;
   - else 1500 and `seed_source="fallback_1500"`.
4. Replay previous season, produce historical payload.
5. Load current-season matches:
   - if unavailable, use previous-season league-phase matches with `fallback_rewind_matchday` results kept and the rest pending;
   - set `data_note` explaining the fallback.
6. Build current ratings:
   - teams that played previous season: final replay rating;
   - new teams: ClubElo 2026 or 1500.
7. Apply current-season played league matches to get `elo_by_matchday`.
8. Build timeline and verification.
9. Load `champions_params.json`, else LaLiga `calibrated_params.json`, else defaults.
10. Cache in module-level `_SNAPSHOT` with TTL.

- [ ] **Step 4: Implement demo**

- Prefer the generated `champions_historical.json`.
- Use the 2025/26 league-phase fixtures as the demo schedule; mark the first `fallback_rewind_matchday` matchdays as played with their real scores.
- If no historical payload exists, use `TEAM_SEEDS` with ELO 1500 and a generated 8-round schedule.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_champions_snapshot.py -v`
Expected: PASS.

---

## Task 8: Serializers and API routes

**Files:**
- Create: `backend/app/champions/api/__init__.py`
- Create: `backend/app/champions/api/serializers.py`
- Create: `backend/app/champions/api/routes.py`
- Modify: `backend/app/api/main.py`
- Test: `backend/tests/test_champions_api.py`

**Interfaces:**
- Consumes: snapshot and simulation result.
- Produces: endpoints under `/api/champions`.

- [ ] **Step 1: Write failing API tests**

```python
from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)


def test_champions_season_endpoint():
    response = client.get("/api/champions/season")
    assert response.status_code == 200
    payload = response.json()
    assert payload["competition"] == "Champions League"
    assert len(payload["teams"]) >= 8
    assert len(payload["standings"]) == len(payload["teams"])


def test_champions_projection_endpoint():
    response = client.get("/api/champions/projection", params={"sims": 200, "seed": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["n_sims"] == 200
    assert all("top8_probability" in team for team in payload["teams"])
    assert "playoff" in payload
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/test_champions_api.py -v`
Expected: 404s.

- [ ] **Step 3: Implement serializers**

Payload shapes:

`/season`:
```json
{
  "competition": "Champions League",
  "season": "2026/27",
  "phase": "league",
  "source": "...",
  "demo": false,
  "data_note": null,
  "updated_at": "...",
  "data_version": "...",
  "current_matchday": 3,
  "total_matchdays": 8,
  "played_matches": 54,
  "pending_matches": 90,
  "teams": [{"id": "...", "name": "...", "short_name": "...", "color": "...", "country": "ESP", "elo": 1800.0, "pot": 1}],
  "standings": [{"position": 1, "team": {...}, "played": 3, "won": 3, "drawn": 0, "lost": 0, "goals_for": 6, "goals_against": 1, "goal_difference": 5, "points": 9, "away_goals": 3, "wins": 3, "away_wins": 1}],
  "model": {...},
  "tiebreak_rules": [...],
  "qualification_zones": {"direct": [1, 8], "playoff": [9, 24], "eliminated": [25, 36]}
}
```

`/projection` includes `teams`, `match_predictions`, `playoff` with `bracket`, `advance_probabilities`, `opponent_probabilities`, `base_standings`.

`/elo` includes `teams`, `history`, `verification`, `timeline`, `params`.

`/validation` includes `metrics`, `model`, `data`.

- [ ] **Step 4: Register router**

In `app/api/main.py`:

```python
from app.champions.api.routes import router as champions_router

app.include_router(champions_router)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_champions_api.py -v`
Expected: PASS.

---

## Task 9: Calibration and verification scripts

**Files:**
- Create: `backend/scripts/calibrate_champions.py`
- Create: `backend/scripts/verify_champions.py`
- Create: `docs/champions.md`
- Create: `docs/champions-calibration.md`

**Interfaces:**
- Consumes: source loaders, replay, calibration.
- Produces: `app/data/champions_historical.json`, `app/data/champions_params.json`, console verification.

- [ ] **Step 1: Implement `calibrate_champions.py`**

- Load 2025/26 from OpenFootball/API-Football.
- Resolve teams.
- Fetch ClubElo for `2025-08-01`; if empty, use 1500 and print a warning.
- Replay, calibrate, write JSON.
- Print counts and parameters.

- [ ] **Step 2: Implement `verify_champions.py`**

- Load snapshot.
- Assert 36 teams and 144 league matches.
- Print applied/total matches, seed source, current ratings and calibration metrics.

- [ ] **Step 3: Run the scripts**

```powershell
cd backend
python scripts/calibrate_champions.py
python scripts/verify_champions.py
```

Expected: both exit 0 and write the JSON files.

- [ ] **Step 4: Write docs**

`docs/champions.md`: format, sources, ELO, simulation, tiebreaks, API.
`docs/champions-calibration.md`: seed source actually used, matches, params, validation metrics and limitations.

---

## Task 10: Frontend types, API client, navigation and layout

**Files:**
- Create: `frontend/lib/champions-types.ts`
- Create: `frontend/lib/champions-api.ts`
- Create: `frontend/components/CompetitionSwitch.tsx`
- Modify: `frontend/components/SiteNav.tsx`
- Modify: `frontend/app/layout.tsx`
- Test: `npm run lint`

**Interfaces:**
- Produces types matching the API and functions:
  - `getChampionsSeason(signal?)`
  - `getChampionsProjection(sims, mode, signal?)`
  - `getChampionsMatches(mode, signal?)`
  - `getChampionsElo(signal?)`
  - `getChampionsValidation(signal?)`

- [ ] **Step 1: Add types**

Include `ChampionsTeam`, `ChampionsStanding`, `ChampionsProjectionTeam`, `ChampionsPlayoff`, `ChampionsSeasonPayload`, `ChampionsProjectionPayload`, `ChampionsMatchesPayload`, `ChampionsEloPayload`, `ChampionsValidationPayload`.

- [ ] **Step 2: Add API client**

Use the existing `request` pattern from `frontend/lib/api.ts` or copy the minimal fetch logic with `ApiError`.

- [ ] **Step 3: Add competition switch and nav**

- `CompetitionSwitch` uses `usePathname` and renders `LaLiga | Champions` links.
- `SiteNav` shows Champions links when `pathname.startsWith("/champions")`, otherwise LaLiga links.
- `layout.tsx` adds the switch in the header and changes the brand season text on Champions routes. Use a small client `Brand` component if needed.

- [ ] **Step 4: Run lint**

Run: `npm run lint`
Expected: PASS.

---

## Task 11: Champions dashboard components

**Files:**
- Create: `frontend/app/champions/page.tsx`
- Create: `frontend/components/champions/ChampionsDashboard.tsx`
- Create: `frontend/components/champions/LeaguePhaseTable.tsx`
- Create: `frontend/components/champions/ProjectionTable.tsx`
- Create: `frontend/components/champions/PositionHeatmap.tsx`
- Create: `frontend/components/champions/ChampionsMatches.tsx`
- Test: `npm run lint`, `npm run build`

**Interfaces:**
- Consumes: `champions-api.ts`, `champions-types.ts`, `TeamBadge`, `ProbabilityBar`, `RangeBar`, `InfoTip`, `States`.
- Produces: `/champions` page.

- [ ] **Step 1: Build `ChampionsDashboard`**

- Fetch season, projection and matches in parallel.
- Show loading skeletons and error retry.
- Header: season, current matchday, played/total, source, demo notice.
- Summary cards: favorite by `round_of_16_probability`, top 8, playoff, eliminated.
- Render tables and heatmap.
- Add a notice when `demo` is true or `data_note` is present.

- [ ] **Step 2: Build `LeaguePhaseTable`**

Columns: position, team, P, W, D, L, GF, GA, GD, Pts. Zone classes:
- `zone-direct` for 1-8;
- `zone-playoff` for 9-24;
- `zone-out` for 25-36.

- [ ] **Step 3: Build `ProjectionTable`**

Columns: team, expected points, range bar, top 8, playoff, eliminated, round of 16, opponent. Use `ProbabilityBar`.

- [ ] **Step 4: Build `PositionHeatmap`**

Adapt the existing heatmap markup to 36 columns. Use `position_probabilities` and `most_likely_position`.

- [ ] **Step 5: Build `ChampionsMatches`**

Matchday selector; played matches show score; pending show 1X2 probabilities and most likely score.

- [ ] **Step 6: Run lint and build**

Run: `npm run lint`, `npm run build`
Expected: PASS.

---

## Task 12: Playoff, ELO and methodology pages

**Files:**
- Create: `frontend/app/champions/playoff/page.tsx`
- Create: `frontend/app/champions/elo/page.tsx`
- Create: `frontend/app/champions/metodologia/page.tsx`
- Create: `frontend/components/champions/PlayoffForecast.tsx`
- Create: `frontend/components/champions/ChampionsElo.tsx`
- Create: `frontend/components/champions/ChampionsMethodology.tsx`
- Modify: `frontend/app/globals.css`
- Test: `npm run lint`, `npm run build`

**Interfaces:**
- Consumes: API payloads and existing visual primitives.
- Produces: the remaining Champions pages.

- [ ] **Step 1: Playoff page**

- Bracket 9-24 with the most likely team per slot.
- Advancement probabilities table.
- Opponent probability matrix or top-3 opponents per team.
- Explanation of two legs, extra time and penalties.

- [ ] **Step 2: ELO page**

- Rating table: position, team, current ELO, start ELO, delta, played.
- Timeline chart.
- Verification panel: matches applied/total, teams resolved, seed source, sources.
- Model parameters.

- [ ] **Step 3: Methodology page**

- Static content matching the spec sections 4-7.
- Include formulas and the UCL tiebreak list.
- Mention fallbacks, ClubElo, 90-minute scores and limitations.

- [ ] **Step 4: CSS**

Add `.champions-*` classes in `globals.css`:
- zone backgrounds;
- 36-column heatmap horizontal scroll;
- bracket grid;
- summary cards;
- responsive rules for mobile.

Use existing tokens (`--panel`, `--border`, `--accent`, etc.) and do not modify LaLiga classes.

- [ ] **Step 5: Run lint and build**

Run: `npm run lint`, `npm run build`
Expected: PASS.

---

## Task 13: End-to-end verification

**Files:**
- No new files.
- Test: full backend and frontend suites.

- [ ] **Step 1: Backend tests**

```powershell
cd backend
python -m pytest tests -q
```

Expected: all tests pass, including LaLiga tests.

- [ ] **Step 2: Scripts**

```powershell
python scripts/verify_champions.py
```

Expected: exit 0, 36 teams, 144 league matches, calibration metrics printed.

- [ ] **Step 3: Frontend checks**

```powershell
cd frontend
npm run lint
npm run build
```

Expected: both pass.

- [ ] **Step 4: Browser check**

Start backend and frontend, then open:
- `/champions`
- `/champions/playoff`
- `/champions/elo`
- `/champions/metodologia`

Verify:
- no console errors;
- table zones are visible;
- demo/fallback notice is visible when applicable;
- mobile layout scrolls horizontally instead of breaking.

- [ ] **Step 5: Final report**

Record:
- tests and commands run;
- data source actually used;
- whether ClubElo and 2026/27 data were available;
- any limitation discovered during implementation.
