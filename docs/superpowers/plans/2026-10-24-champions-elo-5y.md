# ELO de 5 temporadas para SimuChampions — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruir el ELO de Champions con un replay de cinco temporadas (2021/22–2025/26), regresión del 20 % al inicio de cada temporada, y validar con un backtest si los ratings resultantes reflejan el nivel actual.

**Architecture:** Se añade una ventana histórica configurable al cargador de OpenFootball, un replay multi-temporada con regresión, y un payload histórico compatible con el modo demo. La temporada 2026/27 se aplica después sobre el rating post-regresión. La validación se separa en un módulo reutilizable y un script que genera un informe.

**Tech Stack:** Python 3.12, FastAPI, pytest, scipy, Next.js 16, TypeScript.

**Spec:** `docs/superpowers/specs/2026-10-24-champions-elo-5y-design.md`

## Global Constraints

- No modificar el comportamiento ni los datos de LaLiga.
- No añadir dependencias nuevas: `scipy` y `pytest` ya están disponibles.
- Mantener los campos actuales de la API; los nuevos campos son aditivos.
- `K=20`, `H=60`, `alpha=0.20` por defecto.
- Todos los archivos nuevos en UTF-8 sin BOM.
- Los tests backend deben seguir siendo offline: `CHAMPIONS_DATA_SOURCE=demo` y `CHAMPIONS_CLUBELO_ENABLED=false`.
- Comandos backend desde `backend/`: `python -m pytest`.
- Comandos frontend desde `frontend/`: `npm run lint`, `npx tsc --noEmit`, `npm run build`.
- Este repositorio no tiene git; los pasos de commit se sustituyen por ejecutar los tests y revisar los archivos modificados.

---

## Estructura de archivos

- `backend/app/champions/config.py`: configuración de la ventana y regresión.
- `backend/app/champions/names.py`: alias históricos y ids canónicos.
- `backend/app/champions/data/snapshot.py`: `make_team`, replay multi-temporada, payload y snapshot.
- `backend/app/champions/data/api_football.py`: carga de las cinco temporadas.
- `backend/app/champions/data/validation.py` (nuevo): helpers de backtest.
- `backend/scripts/calibrate_champions.py`: regenera histórico y parámetros.
- `backend/scripts/verify_champions.py`: verificación del snapshot.
- `backend/scripts/validate_champions_elo.py` (nuevo): backtest y correlaciones.
- `backend/tests/test_champions_names.py` (nuevo).
- `backend/tests/test_champions_elo.py`, `test_champions_snapshot.py`, `test_champions_validation.py` (nuevo).
- `frontend/lib/champions-types.ts`, `frontend/components/champions/ChampionsElo.tsx`.
- `docs/champions.md`, `docs/champions-calibration.md`, `docs/champions-elo-5y-validation.md`.

---

### Task 1: Configuración y alias históricos

**Files:**
- Modify: `backend/app/champions/config.py`
- Modify: `backend/app/champions/names.py`
- Modify: `backend/app/champions/data/snapshot.py`
- Test: `backend/tests/test_champions_names.py`

**Interfaces:**
- Consumes: `normalize_name`, `slugify`, `TeamSeed`.
- Produces: `ChampionsSettings.history_seasons`, `ChampionsSettings.season_regression`, `HISTORICAL_ALIASES`, `make_team` con ids canónicos para clubes sin seed.

- [ ] **Step 1: Escribir el test que falla**

Crea `backend/tests/test_champions_names.py`:

```python
from app.champions.data.snapshot import make_team
from app.champions.names import normalize_team_key


def test_historical_current_aliases_resolve_to_seed_ids():
    assert normalize_team_key("Bayern München") == "bayern-munich"
    assert normalize_team_key("Aston Villa FC") == "aston-villa"
    assert normalize_team_key("Lille OSC") == "lille"
    assert normalize_team_key("Real Sociedad de Fútbol") == "real-sociedad"
    assert normalize_team_key("Sevilla FC") == "sevilla"
    assert normalize_team_key("SL Benfica") == "benfica"
    assert normalize_team_key("Racing Club de Lens") == "lens"
    assert normalize_team_key("ŠK Slovan Bratislava") == "slovan-bratislava"


def test_historical_non_seed_aliases_are_stable():
    assert normalize_team_key("AC Milan") == "ac-milan"
    assert normalize_team_key("Milan") == "ac-milan"
    assert normalize_team_key("GNK Dinamo Zagreb") == "dinamo-zagreb"
    assert normalize_team_key("Dinamo Zagreb") == "dinamo-zagreb"
    assert normalize_team_key("RB Salzburg") == "rb-salzburg"
    assert normalize_team_key("FC Red Bull Salzburg") == "rb-salzburg"


def test_make_team_uses_canonical_key_for_non_seed_alias():
    assert make_team("Milan").id == "ac-milan"
    assert make_team("AC Milan").id == "ac-milan"
```

- [ ] **Step 2: Ejecutar el test y comprobar que falla**

Run: `python -m pytest tests/test_champions_names.py -v`
Expected: FAIL con `AttributeError` o `AssertionError` porque los alias todavía no existen.

- [ ] **Step 3: Añadir configuración**

En `backend/app/champions/config.py`, dentro de `ChampionsSettings`, añade:

```python
    history_seasons: int = 5
    season_regression: float = 0.20
```

- [ ] **Step 4: Añadir alias históricos**

En `backend/app/champions/names.py`, después del bloque `TEAM_ALIASES.update({...})`, añade:

```python
HISTORICAL_ALIASES: dict[str, str] = {
    "Bayern München": "bayern-munich",
    "Bayern Munchen": "bayern-munich",
    "Aston Villa FC": "aston-villa",
    "SL Benfica": "benfica",
    "Feyenoord Rotterdam": "feyenoord",
    "Racing Club de Lens": "lens",
    "Lille OSC": "lille",
    "Manchester United FC": "manchester-united",
    "Olympique Marseille": "marseille",
    "Real Sociedad de Fútbol": "real-sociedad",
    "Real Sociedad de Futbol": "real-sociedad",
    "Sevilla FC": "sevilla",
    "FK Shakhtar Donetsk": "shakhtar",
    "ŠK Slovan Bratislava": "slovan-bratislava",
    "SK Slovan Bratislava": "slovan-bratislava",
    "AC Milan": "ac-milan",
    "Milan": "ac-milan",
    "AC Sparta Praha": "sparta-prague",
    "Sparta Praha": "sparta-prague",
    "GNK Dinamo Zagreb": "dinamo-zagreb",
    "Dinamo Zagreb": "dinamo-zagreb",
    "RB Salzburg": "rb-salzburg",
    "FC Red Bull Salzburg": "rb-salzburg",
    "Dinamo Kiev": "dynamo-kyiv",
    "Dynamo Kyiv": "dynamo-kyiv",
    "FC Sheriff": "sheriff",
    "Sheriff Tiraspol": "sheriff",
    "BSC Young Boys": "young-boys",
    "Young Boys": "young-boys",
    "Beşiktaş": "besiktas",
    "Besiktas": "besiktas",
    "Bologna FC 1909": "bologna",
    "Bologna": "bologna",
    "Celtic FC": "celtic",
    "Celtic": "celtic",
    "Girona FC": "girona",
    "Girona": "girona",
    "Maccabi Haifa": "maccabi-haifa",
    "Malmö FF": "malmo",
    "Malmo FF": "malmo",
    "Rangers FC": "rangers",
    "Rangers": "rangers",
    "Royal Antwerp FC": "antwerp",
    "Antwerp": "antwerp",
    "SK Sturm Graz": "sturm-graz",
    "Sturm Graz": "sturm-graz",
    "SS Lazio": "lazio",
    "Lazio": "lazio",
    "Sporting Clube de Braga": "braga",
    "Braga": "braga",
    "Stade Brestois 29": "brest",
    "Brest": "brest",
    "VfL Wolfsburg": "wolfsburg",
    "Wolfsburg": "wolfsburg",
    "Viktoria Plzeň": "plzen",
    "Viktoria Plzen": "plzen",
    "Zenit St. Petersburg": "zenit",
    "Zenit": "zenit",
    "1. FC Union Berlin": "union-berlin",
    "Union Berlin": "union-berlin",
}

TEAM_ALIASES.update(
    {normalize_name(alias): team_id for alias, team_id in HISTORICAL_ALIASES.items()}
)
```

- [ ] **Step 5: Hacer que `make_team` respete el id canónico sin seed**

En `backend/app/champions/data/snapshot.py`, sustituye `make_team` por:

```python
def make_team(
    name: str,
    *,
    country: str = "",
    elo: float = DEFAULT_START_RATING,
) -> ChampionsTeam:
    key = normalize_team_key(name)
    if key is not None:
        seed = team_seed(key)
        if seed is not None:
            return ChampionsTeam(
                id=seed.id,
                name=seed.name,
                short_name=seed.short_name,
                color=seed.color,
                country=seed.country,
                elo=elo,
            )
        _, short_name, color = fallback_identity(name)
        return ChampionsTeam(
            id=key,
            name=name,
            short_name=short_name,
            color=color,
            country=country or "—",
            elo=elo,
        )
    team_id, short_name, color = fallback_identity(name)
    return ChampionsTeam(
        id=team_id,
        name=name,
        short_name=short_name,
        color=color,
        country=country or "—",
        elo=elo,
    )
```

- [ ] **Step 6: Ejecutar los tests**

Run: `python -m pytest tests/test_champions_names.py tests/test_champions_snapshot.py -v`
Expected: PASS.

---

### Task 2: Cargador de cinco temporadas

**Files:**
- Modify: `backend/app/champions/data/api_football.py`
- Test: `backend/tests/test_champions_history.py`

**Interfaces:**
- Consumes: `fetch_openfootball_matches`, `load_source_matches`, `season_label`.
- Produces: `history_seasons(settings, count=None) -> list[int]`, `load_history_matches(settings, seasons=None) -> tuple[list[dict], list[str], list[str]]`.

- [ ] **Step 1: Escribir el test que falla**

Crea `backend/tests/test_champions_history.py`:

```python
from app.champions.config import ChampionsSettings
from app.champions.data import api_football


def test_history_seasons_uses_previous_season_and_count():
    settings = ChampionsSettings(previous_season=2025, history_seasons=5)
    assert api_football.history_seasons(settings) == [2021, 2022, 2023, 2024, 2025]


def test_load_history_matches_annotates_and_skips_missing(monkeypatch):
    settings = ChampionsSettings(previous_season=2025, history_seasons=2)

    def fake_fetch(settings, season):
        if season == 2024:
            raise RuntimeError("missing")
        return [
            {
                "phase": "league",
                "matchday": 1,
                "home": "Real Madrid",
                "away": "Barcelona",
                "home_goals": 2,
                "away_goals": 1,
                "kickoff": "2025-09-01",
                "neutral": False,
            }
        ]

    monkeypatch.setattr(api_football, "fetch_openfootball_matches", fake_fetch)
    monkeypatch.setattr(
        api_football,
        "load_source_matches",
        lambda settings, season: (_ for _ in ()).throw(RuntimeError("missing")),
    )

    matches, labels, sources = api_football.load_history_matches(settings)
    assert labels == ["2025/26"]
    assert sources == ["openfootball"]
    assert len(matches) == 1
    assert matches[0]["season"] == "2025/26"
    assert matches[0]["season_start"] == 2025
    assert matches[0]["sequence"] == 0
```

- [ ] **Step 2: Ejecutar el test y comprobar que falla**

Run: `python -m pytest tests/test_champions_history.py -v`
Expected: FAIL porque `history_seasons` y `load_history_matches` no existen.

- [ ] **Step 3: Implementar el cargador**

Al final de `backend/app/champions/data/api_football.py`, añade:

```python
def history_seasons(
    settings: ChampionsSettings, count: int | None = None
) -> list[int]:
    total = max(1, count if count is not None else settings.history_seasons)
    return list(
        range(settings.previous_season - total + 1, settings.previous_season + 1)
    )


def load_history_matches(
    settings: ChampionsSettings,
    seasons: list[int] | None = None,
) -> tuple[list[dict], list[str], list[str]]:
    season_years = seasons if seasons is not None else history_seasons(settings)
    matches: list[dict] = []
    labels: list[str] = []
    sources: list[str] = []

    for season in season_years:
        label = season_label(season)
        try:
            season_matches = fetch_openfootball_matches(settings, season)
            source = "openfootball"
        except Exception:
            try:
                season_matches, source = load_source_matches(settings, season)
            except Exception:
                continue

        if not season_matches:
            continue

        for index, raw in enumerate(season_matches):
            raw["season"] = label
            raw["season_start"] = season
            raw["sequence"] = index

        matches.extend(season_matches)
        labels.append(label)
        sources.append(source)

    return matches, labels, sources
```

- [ ] **Step 4: Ejecutar los tests**

Run: `python -m pytest tests/test_champions_history.py -v`
Expected: PASS.

---

### Task 3: Replay histórico con regresión

**Files:**
- Modify: `backend/app/champions/data/snapshot.py`
- Test: `backend/tests/test_champions_elo.py`

**Interfaces:**
- Consumes: `update_ratings`, `make_team`, `_side_country`.
- Produces: `HistoryReplayResult`, `replay_history(seasons, teams, params, *, regression=0.0)`.

- [ ] **Step 1: Escribir los tests que fallan**

Añade a `backend/tests/test_champions_elo.py`:

```python
from app.champions.data.snapshot import replay_history


def test_replay_history_applies_regression_at_season_boundary():
    teams = [team("a", 1500.0), team("b", 1500.0)]
    seasons = [
        (
            "2021/22",
            [
                {
                    "home": "a",
                    "away": "b",
                    "home_goals": 2,
                    "away_goals": 0,
                    "neutral": False,
                    "kickoff": "2021-09-01",
                    "sequence": 0,
                }
            ],
        ),
        ("2022/23", []),
    ]
    result = replay_history(
        seasons, teams, {"k": 20, "home_advantage": 60}, regression=0.2
    )
    end_a = result.season_ends["2021/22"]["a"]
    start_a = result.season_starts["2022/23"]["a"]
    assert start_a == pytest.approx(1500.0 + 0.8 * (end_a - 1500.0))


def test_replay_history_new_team_starts_at_1500():
    teams = [team("a", 1500.0), team("b", 1500.0), team("c", 1500.0)]
    seasons = [
        (
            "2021/22",
            [
                {
                    "home": "a",
                    "away": "b",
                    "home_goals": 1,
                    "away_goals": 0,
                    "neutral": False,
                    "kickoff": "2021-09-01",
                    "sequence": 0,
                }
            ],
        ),
        (
            "2022/23",
            [
                {
                    "home": "c",
                    "away": "a",
                    "home_goals": 1,
                    "away_goals": 0,
                    "neutral": False,
                    "kickoff": "2022-09-01",
                    "sequence": 0,
                }
            ],
        ),
    ]
    result = replay_history(
        seasons, teams, {"k": 20, "home_advantage": 60}, regression=0.2
    )
    assert result.season_starts["2022/23"]["c"] == pytest.approx(1500.0)


def test_replay_history_preserves_total_without_regression():
    teams = [team("a", 1600.0), team("b", 1500.0)]
    seasons = [
        (
            "2021/22",
            [
                {
                    "home": "a",
                    "away": "b",
                    "home_goals": 2,
                    "away_goals": 0,
                    "neutral": False,
                    "kickoff": "2021-09-01",
                    "sequence": 0,
                }
            ],
        )
    ]
    result = replay_history(
        seasons, teams, {"k": 20, "home_advantage": 60}, regression=0.0
    )
    assert result.ratings["a"] + result.ratings["b"] == pytest.approx(3100.0)
```

- [ ] **Step 2: Ejecutar los tests y comprobar que fallan**

Run: `python -m pytest tests/test_champions_elo.py -v`
Expected: FAIL porque `replay_history` no existe.

- [ ] **Step 3: Implementar `HistoryReplayResult` y `replay_history`**

En `backend/app/champions/data/snapshot.py`, después de `ReplayResult`, añade:

```python
@dataclass
class HistoryReplayResult:
    ratings: dict[str, float]
    start_ratings: dict[str, float]
    season_starts: dict[str, dict[str, float]]
    season_ends: dict[str, dict[str, float]]
    applied: int = 0
    without_score: int = 0
    timeline: list[dict] = field(default_factory=list)
    seasons: list[str] = field(default_factory=list)
    regression: float = 0.0
```

Después de `replay_matches`, añade:

```python
def _timeline_point(
    date: str, season: str, ratings: dict[str, float]
) -> dict:
    return {
        "date": date,
        "season": season,
        "ratings": {
            team_id: round(value, 2) for team_id, value in ratings.items()
        },
    }


def replay_history(
    seasons: list[tuple[str, list[dict]]],
    teams: Iterable[ChampionsTeam],
    params: dict,
    *,
    regression: float = 0.0,
) -> HistoryReplayResult:
    team_list = list(teams)
    start_ratings = {team.id: float(team.elo) for team in team_list}
    ratings = dict(start_ratings)
    k = float(params.get("k", DEFAULT_K))
    home_advantage = float(params.get("home_advantage", DEFAULT_HOME_ADVANTAGE))
    result = HistoryReplayResult(
        ratings=ratings,
        start_ratings=start_ratings,
        season_starts={},
        season_ends={},
        regression=regression,
    )

    for index, (label, raw_matches) in enumerate(seasons):
        if index > 0 and regression:
            ratings = {
                team_id: value + regression * (DEFAULT_START_RATING - value)
                for team_id, value in ratings.items()
            }

        result.seasons.append(label)
        result.season_starts[label] = dict(ratings)
        ordered = sorted(
            raw_matches,
            key=lambda raw: (
                raw.get("kickoff") or "",
                int(raw.get("sequence") or 0),
            ),
        )
        if not ordered:
            result.season_ends[label] = dict(ratings)
            continue

        first_date = (ordered[0].get("kickoff") or "")[:10]
        last_date = first_date
        current_month = first_date[:7]
        result.timeline.append(_timeline_point(first_date, label, ratings))

        for raw in ordered:
            home_id = make_team(
                raw["home"], country=_side_country(raw, "home")
            ).id
            away_id = make_team(
                raw["away"], country=_side_country(raw, "away")
            ).id
            if home_id not in ratings or away_id not in ratings:
                continue
            if raw.get("home_goals") is None or raw.get("away_goals") is None:
                result.without_score += 1
                continue

            date = (raw.get("kickoff") or "")[:10]
            if date[:7] != current_month:
                result.timeline.append(_timeline_point(last_date, label, ratings))
                current_month = date[:7]

            advantage = 0.0 if raw.get("neutral") else home_advantage
            home_after, away_after = update_ratings(
                ratings[home_id],
                ratings[away_id],
                int(raw["home_goals"]),
                int(raw["away_goals"]),
                k=k,
                home_advantage=advantage,
            )
            ratings[home_id] = home_after
            ratings[away_id] = away_after
            result.applied += 1
            last_date = date or last_date

        result.season_ends[label] = dict(ratings)
        result.timeline.append(_timeline_point(last_date, label, ratings))

    result.ratings = ratings
    return result
```

- [ ] **Step 4: Ejecutar los tests**

Run: `python -m pytest tests/test_champions_elo.py -v`
Expected: PASS.

---

### Task 4: Payload histórico y snapshot de cinco temporadas

**Files:**
- Modify: `backend/app/champions/data/snapshot.py`
- Test: `backend/tests/test_champions_snapshot.py`

**Interfaces:**
- Consumes: `HistoryReplayResult`, `replay_history`, `calibrate_params`, `_seed_previous_ratings`.
- Produces: `build_history_payload(replay, *, seed_source, demo_team_ids) -> dict`, `build_snapshot_from_matches(history_matches, current_matches, settings, *, source, history_labels, current_label, history_sources=None)`.

- [ ] **Step 1: Escribir el test que falla**

Añade a `backend/tests/test_champions_snapshot.py`:

```python
from app.champions.config import ChampionsSettings
from app.champions.data.snapshot import build_snapshot_from_matches


def raw_match(season, kickoff, home, away, home_goals, away_goals, matchday=1):
    return {
        "season": season,
        "season_start": int(season.split("/")[0]),
        "sequence": 0,
        "phase": "league",
        "matchday": matchday,
        "leg": 0,
        "home": home,
        "away": away,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "kickoff": kickoff,
        "neutral": False,
    }


def test_snapshot_uses_history_seasons_and_verification():
    settings = ChampionsSettings(
        data_source="demo",
        clubelo_enabled=False,
        history_seasons=2,
        season_regression=0.2,
        previous_season=2025,
        season=2026,
    )
    history = [
        raw_match("2024/25", "2024-09-01", "Real Madrid", "Barcelona", 2, 1),
        raw_match("2024/25", "2024-09-02", "Barcelona", "Real Madrid", 1, 1),
        raw_match("2025/26", "2025-09-01", "Real Madrid", "Barcelona", 1, 0),
        raw_match("2025/26", "2025-09-02", "Barcelona", "Real Madrid", 2, 2),
    ]
    current = [
        raw_match("2026/27", "2026-09-01", "Real Madrid", "Barcelona", 1, 1),
        raw_match(
            "2026/27", "2026-09-02", "Barcelona", "Real Madrid", None, None
        ),
    ]
    snapshot = build_snapshot_from_matches(
        history,
        current,
        settings,
        source="test",
        history_labels=["2024/25", "2025/26"],
        current_label="2026/27",
        history_sources=["test"],
    )
    assert snapshot.elo_history["seasons"] == [
        "2024/25",
        "2025/26",
        "2026/27",
    ]
    assert len(snapshot.elo_history["series"]) == 2
    assert all(
        len(series["values"]) == 3 for series in snapshot.elo_history["series"]
    )
    assert snapshot.elo_verification["history_seasons"] == 2
    assert snapshot.elo_verification["history_complete"] is True
    assert snapshot.elo_verification["season_regression"] == 0.2
    assert snapshot.elo_verification["history_matches_applied"] == 4
```

- [ ] **Step 2: Ejecutar el test y comprobar que falla**

Run: `python -m pytest tests/test_champions_snapshot.py::test_snapshot_uses_history_seasons_and_verification -v`
Expected: FAIL porque la firma actual no acepta `history_labels` ni existe el payload nuevo.

- [ ] **Step 3: Implementar `build_history_payload`**

En `backend/app/champions/data/snapshot.py`, sustituye `build_historical_payload` por:

```python
def build_history_payload(
    replay: HistoryReplayResult,
    *,
    seed_source: str,
    demo_team_ids: Iterable[str],
) -> dict:
    return {
        "season": replay.seasons[-1] if replay.seasons else "",
        "seasons": list(replay.seasons),
        "start_ratings": {
            team_id: round(value, 2)
            for team_id, value in replay.start_ratings.items()
        },
        "final_ratings": {
            team_id: round(value, 2)
            for team_id, value in replay.ratings.items()
        },
        "season_start_ratings": {
            label: {
                team_id: round(value, 2)
                for team_id, value in values.items()
            }
            for label, values in replay.season_starts.items()
        },
        "season_end_ratings": {
            label: {
                team_id: round(value, 2)
                for team_id, value in values.items()
            }
            for label, values in replay.season_ends.items()
        },
        "teams": sorted(demo_team_ids),
        "timeline": replay.timeline,
        "matches_total": replay.applied + replay.without_score,
        "matches_applied": replay.applied,
        "matches_without_score": replay.without_score,
        "seed_source": seed_source,
        "season_regression": replay.regression,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: Reescribir `build_snapshot_from_matches`**

Sustituye la función completa por:

```python
def build_snapshot_from_matches(
    history_matches: list[dict],
    current_matches: list[dict],
    settings: ChampionsSettings,
    *,
    source: str,
    history_labels: list[str],
    current_label: str,
    history_sources: list[str] | None = None,
) -> ChampionsSnapshot:
    if not history_labels:
        raise ValueError("history_labels must not be empty")

    history_start = int(history_labels[0].split("/")[0])
    clubelo_history = _clubelo_snapshot(
        settings, f"{history_start}-08-01"
    )
    history_teams = resolve_teams(history_matches)
    seeded_ratings, seed_source = _seed_previous_ratings(
        history_teams, clubelo_history
    )
    history_teams = {
        team_id: team.with_elo(seeded_ratings[team_id])
        for team_id, team in history_teams.items()
    }

    by_season: dict[str, list[dict]] = {}
    for raw in history_matches:
        by_season.setdefault(
            str(raw.get("season") or history_labels[-1]), []
        ).append(raw)
    season_groups = [
        (label, by_season.get(label, [])) for label in history_labels
    ]

    base_params = {"k": DEFAULT_K, "home_advantage": DEFAULT_HOME_ADVANTAGE}
    replay = replay_history(
        season_groups,
        history_teams.values(),
        base_params,
        regression=float(settings.season_regression),
    )

    previous_label = history_labels[-1]
    previous_matches = by_season.get(previous_label, [])
    previous_teams = resolve_teams(previous_matches)

    calibration_start = replay.season_starts.get(previous_label, {})
    calibration_teams = [
        team.with_elo(calibration_start.get(team.id, team.elo))
        for team in previous_teams.values()
    ]
    try:
        calibrated = calibrate_params(previous_matches, calibration_teams)
    except Exception:  # noqa: BLE001 - parameters are optional
        calibrated = load_params()

    fallback = not current_matches
    if fallback:
        start_ratings = {
            team_id: calibration_start.get(team_id, team.elo)
            for team_id, team in previous_teams.items()
        }
        active_teams = {
            team_id: team.with_elo(start_ratings[team_id])
            for team_id, team in previous_teams.items()
        }
        raw_active = [
            match
            for match in previous_matches
            if match.get("phase") == "league"
        ]
        active_label = previous_label
        max_matchday = settings.fallback_rewind_matchday
        model_params = calibrated
        current_source = source
    else:
        clubelo_current = _clubelo_snapshot(
            settings, settings.clubelo_date_2026
        )
        active_teams = resolve_teams(current_matches)
        regressed = {
            team_id: value
            + float(settings.season_regression)
            * (DEFAULT_START_RATING - value)
            for team_id, value in replay.ratings.items()
        }
        by_id = _clubelo_by_id(clubelo_current)
        ratings: dict[str, float] = {}
        unresolved: list[str] = []
        for team_id in active_teams:
            if team_id in regressed:
                ratings[team_id] = regressed[team_id]
            elif team_id in by_id:
                ratings[team_id] = by_id[team_id]
            else:
                unresolved.append(team_id)
        if unresolved:
            known = [
                ratings[team_id]
                for team_id in active_teams
                if team_id in ratings
            ]
            baseline = (
                sum(known) / len(known) if known else DEFAULT_START_RATING
            )
            for team_id in unresolved:
                ratings[team_id] = baseline
        active_teams = {
            team_id: team.with_elo(ratings[team_id])
            for team_id, team in active_teams.items()
        }
        start_ratings = dict(ratings)
        raw_active = current_matches
        active_label = current_label
        max_matchday = None
        model_params = calibrated
        current_source = source

    active_matches = with_match_ids(raw_active, active_teams)
    if fallback:
        active_matches = [
            match
            if match.matchday <= settings.fallback_rewind_matchday
            else match.as_pending()
            for match in active_matches
        ]

    current_ratings, elo_by_matchday = _apply_matchdays(
        active_matches,
        start_ratings,
        model_params,
        max_matchday=max_matchday,
    )
    updated_teams = [
        team.with_elo(round(current_ratings.get(team.id, team.elo), 2))
        for team in active_teams.values()
    ]

    if fallback:
        seasons = list(history_labels)
        history_values = {
            team.id: [
                round(
                    replay.season_starts.get(label, {}).get(
                        team.id, team.elo
                    ),
                    2,
                )
                for label in history_labels
            ]
            for team in updated_teams
        }
    else:
        seasons = [*history_labels, current_label]
        history_values = {
            team.id: [
                *[
                    round(
                        replay.season_starts.get(label, {}).get(
                            team.id, team.elo
                        ),
                        2,
                    )
                    for label in history_labels
                ],
                round(start_ratings.get(team.id, team.elo), 2),
            ]
            for team in updated_teams
        }

    timeline_current = _timeline_points(
        active_matches, elo_by_matchday, active_label
    )
    timeline = sorted(
        [*replay.timeline, *timeline_current],
        key=lambda point: (
            point.get("date") or "",
            point.get("season") or "",
        ),
    )
    timeline_series = {
        team.id: [
            point.get("ratings", {}).get(team.id) for point in timeline
        ]
        for team in updated_teams
    }

    played_current = sum(
        1 for match in active_matches if match.is_played
    )
    total_current = len(active_matches)
    if fallback:
        note = (
            f"{current_label} no disponible todavía; mostrando "
            f"{previous_label} con las "
            f"{settings.fallback_rewind_matchday} primeras jornadas "
            "reales y el resto simulado"
        )
    else:
        note = (
            f"Datos reales {active_label} · {played_current}/"
            f"{total_current} partidos jugados"
        )

    verification = {
        "available": bool(history_matches),
        "previous_season": previous_label,
        "history_seasons": len(history_labels),
        "history_start": history_labels[0],
        "history_end": history_labels[-1],
        "history_seasons_loaded": list(history_labels),
        "history_complete": len(history_labels)
        == int(settings.history_seasons),
        "season_regression": float(settings.season_regression),
        "history_matches_total": replay.applied + replay.without_score,
        "history_matches_applied": replay.applied,
        "history_matches_without_score": replay.without_score,
        "matches_total": replay.applied + replay.without_score,
        "matches_applied": replay.applied,
        "matches_without_score": replay.without_score,
        "teams_total": len(history_teams),
        "teams_resolved": len(history_teams),
        "seed_source": seed_source,
        "sources": sorted({*(history_sources or []), source}),
        "fallback": fallback,
        "fallback_season": previous_label if fallback else None,
        "current_matches_total": total_current,
        "current_matches_played": played_current,
        "params": calibrated,
    }

    model = {
        "davidson": {
            "home_advantage": round(
                float(calibrated.get("home_advantage", 60.0)), 2
            ),
            "nu": round(float(calibrated.get("nu", 0.9)), 4),
            "elo_scale": 400.0,
        },
        "scoreline": {
            "home_base": 1.45,
            "away_base": 1.15,
            "elo_slope": 0.0018,
            "home_advantage": round(
                float(calibrated.get("home_advantage", 60.0)), 2
            ),
            "rho": -0.05,
            "max_goals": 10,
        },
    }

    return ChampionsSnapshot(
        competition="Champions League",
        season=active_label,
        source=current_source,
        updated_at=datetime.now(timezone.utc).isoformat(),
        teams=sorted(updated_teams, key=lambda team: (-team.elo, team.name)),
        matches=active_matches,
        data_version=_version(updated_teams, active_matches, current_source),
        demo=False,
        data_note=note,
        elo_by_matchday=elo_by_matchday,
        elo_history={
            "seasons": seasons,
            "series": [
                {"team_id": team_id, "values": values}
                for team_id, values in history_values.items()
            ],
            "origin": 1500.0,
        },
        elo_verification=verification,
        elo_timeline={
            "dates": [point.get("date") or "" for point in timeline],
            "series": [
                {"team_id": team_id, "values": values}
                for team_id, values in timeline_series.items()
            ],
        },
        model=model,
        target_season=current_label,
        fallback=fallback,
    )
```

- [ ] **Step 5: Actualizar `_load_snapshot`**

Sustituye `_load_snapshot` por:

```python
def _load_snapshot(settings: ChampionsSettings) -> ChampionsSnapshot:
    source = settings.data_source.lower()
    if source == "demo":
        return build_demo_snapshot(settings)

    current_label = _season_label(settings.season)
    try:
        history_matches, history_labels, history_sources = (
            load_history_matches(settings)
        )
        if not history_matches:
            raise DataSourceError("no history matches")
        try:
            current_matches, current_source = load_source_matches(
                settings, settings.season
            )
        except Exception:  # noqa: BLE001 - fallback season is valid
            current_matches = []
            current_source = (
                history_sources[-1] if history_sources else "openfootball"
            )
        return build_snapshot_from_matches(
            history_matches,
            current_matches,
            settings,
            source=current_source,
            history_labels=history_labels,
            current_label=current_label,
            history_sources=history_sources,
        )
    except Exception as error:  # noqa: BLE001 - demo keeps app usable
        snapshot = build_demo_snapshot(settings)
        return ChampionsSnapshot(
            **{
                **snapshot.__dict__,
                "data_note": f"Modo demo ({type(error).__name__}: {error})",
            }
        )
```

Añade el import al inicio de `snapshot.py`:

```python
from app.champions.data.api_football import (
    DataSourceError,
    load_history_matches,
    load_source_matches,
)
```

- [ ] **Step 6: Ejecutar los tests**

Run: `python -m pytest tests/test_champions_snapshot.py tests/test_champions_elo.py -v`
Expected: PASS.

---

### Task 5: Calibración y datos regenerados

**Files:**
- Modify: `backend/scripts/calibrate_champions.py`
- Modify: `backend/scripts/verify_champions.py`

**Interfaces:**
- Consumes: `load_history_matches`, `replay_history`, `build_history_payload`, `calibrate_params`.
- Produces: `champions_historical.json` de cinco temporadas, `champions_params.json` recalibrado, `champions_demo_matches.json` de 2025/26.

- [ ] **Step 1: Reescribir `calibrate_champions.py`**

Sustituye el contenido por:

```python
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
    _seed_previous_ratings,
    build_history_payload,
    calibrate_params,
    replay_history,
    resolve_teams,
)
from app.domain.elo import (  # noqa: E402
    DEFAULT_HOME_ADVANTAGE,
    DEFAULT_K,
)

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
    seeded_ratings, seed_source = _seed_previous_ratings(teams, clubelo)
    seeded = {
        team_id: team.with_elo(seeded_ratings[team_id])
        for team_id, team in teams.items()
    }

    by_season: dict[str, list[dict]] = {}
    for raw in matches:
        by_season.setdefault(str(raw["season"]), []).append(raw)
    season_groups = [
        (label, by_season.get(label, [])) for label in labels
    ]

    replay = replay_history(
        season_groups,
        seeded.values(),
        {"k": DEFAULT_K, "home_advantage": DEFAULT_HOME_ADVANTAGE},
        regression=float(settings.season_regression),
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
    print("regression:", settings.season_regression)
    print(
        "calibrated:",
        f"H={calibrated['home_advantage']:.2f}",
        f"nu={calibrated['nu']:.4f}",
    )
    print("validation:", calibrated.get("validation"))
    print("written to", DATA_DIR)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Actualizar `verify_champions.py`**

Añade después de `print("seed source:", ...)`:

```python
    print(
        "history:",
        verification.get("history_start"),
        "-",
        verification.get("history_end"),
        "seasons:",
        verification.get("history_seasons_loaded"),
    )
    print(
        "history applied:",
        verification.get("history_matches_applied"),
        "/",
        verification.get("history_matches_total"),
        "regression:",
        verification.get("season_regression"),
    )
```

- [ ] **Step 3: Ejecutar la calibración**

Run desde `backend/`: `python scripts/calibrate_champions.py`
Expected: descarga/cachea las cinco temporadas, imprime `seasons: ['2021/22', ..., '2025/26']` y escribe los tres JSON.

- [ ] **Step 4: Ejecutar la verificación**

Run desde `backend/`: `python scripts/verify_champions.py`
Expected: 36 equipos, 144 partidos de liga, 8 jornadas y el histórico de cinco temporadas.

- [ ] **Step 5: Ejecutar los tests backend**

Run: `python -m pytest`
Expected: PASS.

---

### Task 6: Backtest y correlaciones

**Files:**
- Create: `backend/app/champions/data/validation.py`
- Create: `backend/scripts/validate_champions_elo.py`
- Test: `backend/tests/test_champions_validation.py`

**Interfaces:**
- Consumes: `replay_history`, `make_team`, `_side_country`, `probabilities_from_ratings`, `evaluate_predictions`.
- Produces: `RatingEvaluation`, `ratings_for_window`, `evaluate_ratings`, `points_by_team`, `spearman_correlation`, `top_overlap`.

- [ ] **Step 1: Escribir los tests que fallan**

Crea `backend/tests/test_champions_validation.py`:

```python
import pytest

from app.champions.data.validation import (
    evaluate_ratings,
    points_by_team,
    spearman_correlation,
    top_overlap,
)
from app.domain.davidson import DavidsonParams


def raw_match(home, away, home_goals, away_goals):
    return {
        "home": home,
        "away": away,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "phase": "league",
        "kickoff": "2025-09-01",
        "sequence": 0,
        "neutral": False,
    }


def test_points_by_team_counts_results():
    points = points_by_team(
        [
            raw_match("Real Madrid", "Barcelona", 2, 1),
            raw_match("Barcelona", "Real Madrid", 1, 1),
        ]
    )
    assert points["real-madrid"] == 4
    assert points["barcelona"] == 1


def test_evaluate_ratings_returns_metrics():
    metrics = evaluate_ratings(
        [raw_match("Real Madrid", "Barcelona", 2, 1)],
        {"real-madrid": 1700.0, "barcelona": 1500.0},
        DavidsonParams(home_advantage=17.3, nu=0.45),
    )
    assert metrics.matches == 1
    assert 0.0 <= metrics.accuracy <= 1.0
    assert metrics.log_loss > 0.0


def test_top_overlap_and_spearman():
    ratings = {"a": 1700.0, "b": 1600.0, "c": 1500.0}
    points = {"a": 9.0, "b": 6.0, "c": 3.0}
    assert top_overlap(ratings, points, size=2) == 2
    assert spearman_correlation(ratings, points) == pytest.approx(1.0)
```

- [ ] **Step 2: Ejecutar los tests y comprobar que fallan**

Run: `python -m pytest tests/test_champions_validation.py -v`
Expected: FAIL porque el módulo no existe.

- [ ] **Step 3: Implementar `validation.py`**

Crea `backend/app/champions/data/validation.py`:

```python
"""Backtest helpers for the five-season Champions Elo."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from scipy.stats import spearmanr

from app.champions.data.snapshot import (
    _side_country,
    make_team,
    replay_history,
    resolve_teams,
)
from app.champions.models import ChampionsTeam
from app.data.history import evaluate_predictions
from app.domain.davidson import DavidsonParams, probabilities_from_ratings
from app.domain.elo import DEFAULT_HOME_ADVANTAGE


@dataclass(frozen=True)
class RatingEvaluation:
    matches: int
    accuracy: float
    log_loss: float
    brier: float


def season_groups(
    matches: Iterable[dict], labels: list[str]
) -> list[tuple[str, list[dict]]]:
    by_season: dict[str, list[dict]] = {}
    for raw in matches:
        by_season.setdefault(str(raw.get("season") or ""), []).append(raw)
    return [(label, by_season.get(label, [])) for label in labels]


def ratings_for_window(
    matches: list[dict],
    labels: list[str],
    *,
    regression: float,
    k: float,
) -> dict[str, float]:
    teams = resolve_teams(matches)
    seeded = {
        team_id: team.with_elo(1500.0)
        for team_id, team in teams.items()
    }
    replay = replay_history(
        season_groups(matches, labels),
        seeded.values(),
        {"k": k, "home_advantage": DEFAULT_HOME_ADVANTAGE},
        regression=regression,
    )
    return replay.ratings


def evaluate_ratings(
    matches: Iterable[dict],
    ratings: dict[str, float],
    params: DavidsonParams,
) -> RatingEvaluation:
    probabilities: list[tuple[float, float, float]] = []
    outcomes: list[str] = []
    for raw in sorted(
        matches,
        key=lambda item: (
            item.get("kickoff") or "",
            item.get("sequence") or 0,
        ),
    ):
        if raw.get("home_goals") is None or raw.get("away_goals") is None:
            continue
        home_id = make_team(
            raw["home"], country=_side_country(raw, "home")
        ).id
        away_id = make_team(
            raw["away"], country=_side_country(raw, "away")
        ).id
        home_elo = ratings.get(home_id, 1500.0)
        away_elo = ratings.get(away_id, 1500.0)
        probability = probabilities_from_ratings(
            home_elo, away_elo, params
        )
        probabilities.append(probability.as_tuple())
        home_goals = int(raw["home_goals"])
        away_goals = int(raw["away_goals"])
        outcomes.append(
            "H"
            if home_goals > away_goals
            else "A"
            if home_goals < away_goals
            else "D"
        )
    metrics = evaluate_predictions(probabilities, outcomes)
    return RatingEvaluation(**metrics)


def points_by_team(matches: Iterable[dict]) -> dict[str, float]:
    points: dict[str, float] = {}
    for raw in matches:
        if raw.get("phase") != "league":
            continue
        if raw.get("home_goals") is None or raw.get("away_goals") is None:
            continue
        home_id = make_team(
            raw["home"], country=_side_country(raw, "home")
        ).id
        away_id = make_team(
            raw["away"], country=_side_country(raw, "away")
        ).id
        points.setdefault(home_id, 0.0)
        points.setdefault(away_id, 0.0)
        home_goals = int(raw["home_goals"])
        away_goals = int(raw["away_goals"])
        if home_goals > away_goals:
            points[home_id] += 3
        elif home_goals < away_goals:
            points[away_id] += 3
        else:
            points[home_id] += 1
            points[away_id] += 1
    return points


def spearman_correlation(
    ratings: dict[str, float], points: dict[str, float]
) -> float:
    common = sorted(set(ratings) & set(points))
    if len(common) < 2:
        return 0.0
    result = spearmanr(
        [ratings[team_id] for team_id in common],
        [points[team_id] for team_id in common],
    )
    value = float(result.statistic)
    return 0.0 if math.isnan(value) else value


def top_overlap(
    ratings: dict[str, float], points: dict[str, float], size: int = 8
) -> int:
    top_ratings = set(
        sorted(
            ratings, key=lambda team_id: ratings[team_id], reverse=True
        )[:size]
    )
    top_points = set(
        sorted(
            points, key=lambda team_id: points[team_id], reverse=True
        )[:size]
    )
    return len(top_ratings & top_points)
```

- [ ] **Step 4: Ejecutar los tests**

Run: `python -m pytest tests/test_champions_validation.py -v`
Expected: PASS.

- [ ] **Step 5: Implementar el script de validación**

Crea `backend/scripts/validate_champions_elo.py`:

```python
"""Validate the five-season Champions Elo against a holdout season."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.champions.config import get_champions_settings  # noqa: E402
from app.champions.data.api_football import (  # noqa: E402
    load_history_matches,
    load_source_matches,
)
from app.champions.data.snapshot import load_params  # noqa: E402
from app.champions.data.validation import (  # noqa: E402
    evaluate_ratings,
    points_by_team,
    ratings_for_window,
    spearman_correlation,
    top_overlap,
)
from app.domain.davidson import DavidsonParams  # noqa: E402

OUTPUT = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "champions-elo-5y-validation.md"
)


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

    params_data = load_params()
    params = DavidsonParams(
        home_advantage=float(params_data["home_advantage"]),
        nu=float(params_data["nu"]),
    )

    ratings_5 = ratings_for_window(
        train_matches, train_labels, regression=0.2, k=20
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
    metrics_1 = evaluate_ratings(test_matches, ratings_1, params)
    metrics_flat = evaluate_ratings(test_matches, ratings_flat, params)

    test_points = points_by_team(league_test)
    spearman_5 = spearman_correlation(ratings_5, test_points)
    overlap_5 = top_overlap(ratings_5, test_points)

    prod_matches, prod_labels, _ = load_history_matches(settings)
    prod_ratings = ratings_for_window(
        prod_matches, prod_labels, regression=0.2, k=20
    )
    current_matches, _ = load_source_matches(settings, settings.season)
    current_points = points_by_team(current_matches)
    spearman_current = spearman_correlation(
        prod_ratings, current_points
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
                (alpha, k, evaluate_ratings(test_matches, ratings, params))
            )

    lines = [
        "# Validación del ELO de 5 temporadas",
        "",
        f"Backtest: {train_labels[0]}–{train_labels[-1]} "
        f"→ {test_label}",
        "",
        "## Comparación de ratings",
        "",
        "| Modelo | Partidos | Accuracy | Log-loss | Brier |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| 5 temporadas | {metrics_5.matches} | "
        f"{metrics_5.accuracy:.4f} | {metrics_5.log_loss:.4f} | "
        f"{metrics_5.brier:.4f} |",
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
        f"- Spearman con puntos de {test_label}: {spearman_5:.4f}",
        f"- Solapamiento top 8: {overlap_5}/8",
        f"- Spearman con puntos actuales de 2026/27: "
        f"{spearman_current:.4f}",
        "",
        "## Búsqueda de alpha y K",
        "",
        "| alpha | K | Accuracy | Log-loss | Brier |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for alpha, k, metrics in grid:
        lines.append(
            f"| {alpha:.1f} | {k} | {metrics.accuracy:.4f} | "
            f"{metrics.log_loss:.4f} | {metrics.brier:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Criterios",
            "",
            "- Log-loss de 5 temporadas menor que 1 temporada y que 1500.",
            "- Spearman con puntos de 2025/26 >= 0.60.",
            "- Top 8 compartido >= 6/8.",
            "- Ranking de producción plausible.",
        ]
    )

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("written to", OUTPUT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Ejecutar la validación**

Run desde `backend/`: `python scripts/validate_champions_elo.py`
Expected: imprime las tablas y escribe `docs/champions-elo-5y-validation.md`.

- [ ] **Step 7: Ejecutar los tests**

Run: `python -m pytest tests/test_champions_validation.py -v`
Expected: PASS.

---

### Task 7: Frontend

**Files:**
- Modify: `frontend/lib/champions-types.ts`
- Modify: `frontend/components/champions/ChampionsElo.tsx`

**Interfaces:**
- Consumes: `ChampionsEloPayload.verification`.
- Produces: UI con temporadas, partidos históricos, regresión y estado de completitud.

- [ ] **Step 1: Ampliar el tipo de verificación**

En `frontend/lib/champions-types.ts`, dentro de `verification`, añade:

```ts
    history_seasons?: number;
    history_start?: string;
    history_end?: string;
    history_seasons_loaded?: string[];
    history_complete?: boolean;
    season_regression?: number;
    history_matches_total?: number;
    history_matches_applied?: number;
    history_matches_without_score?: number;
```

- [ ] **Step 2: Actualizar `ChampionsElo.tsx`**

Sustituye el bloque de carga y la cabecera por:

```tsx
  if (!elo) {
    return (
      <div className="container">
        <LoadingState
          title="Cargando ELO"
          note="Recalculando ratings y replay de 5 temporadas."
        />
      </div>
    );
  }

  const verification = elo.verification;
  const validation = verification.params?.validation;
  const historySeasons =
    verification.history_seasons_loaded?.length ??
    verification.history_seasons ??
    0;
  const regression = Math.round(
    (verification.season_regression ?? 0.2) * 100,
  );
```

Sustituye el subtítulo y los chips de cabecera por:

```tsx
          <p className="page-sub">
            Rating reconstruido con el replay de las últimas 5 temporadas
            (2021/22–2025/26) y regresión del {regression} % al inicio de cada
            temporada. Los partidos de 2026/27 ya jugados se aplican después.
          </p>
        </div>
        <div className="status-row">
          <span className="chip">
            Fuente <strong>{elo.source}</strong>
          </span>
          <span className="chip">
            Replay{" "}
            <strong>
              {verification.history_matches_applied ??
                verification.matches_applied ??
                0}
            </strong>
            /
            {verification.history_matches_total ??
              verification.matches_total ??
              0}
          </span>
          <span className="chip">
            Temporadas <strong>{historySeasons}</strong>
          </span>
          <span className="chip">
            Semilla <strong>{verification.seed_source ?? "—"}</strong>
          </span>
          <span className="chip">
            Regresión <strong>{regression}%</strong>
          </span>
        </div>
```

Sustituye la nota y el chip del panel de verificación por:

```tsx
            <span className="panel-note">
              Histórico: {verification.history_start ?? "—"}–
              {verification.history_end ?? "—"} · equipos{" "}
              {verification.teams_resolved ?? 0}/
              {verification.teams_total ?? 0}
            </span>
          </div>
          <span
            className={`chip ${
              verification.history_complete ? "chip-good" : "chip-danger"
            }`}
          >
            {verification.history_complete
              ? "histórico completo"
              : "histórico parcial"}
          </span>
```

- [ ] **Step 3: Ejecutar lint y typecheck**

Run desde `frontend/`: `npm run lint`
Expected: sin errores.

Run desde `frontend/`: `npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 4: Ejecutar build**

Run desde `frontend/`: `npm run build`
Expected: build correcto.

- [ ] **Step 5: Verificar la UI**

Abrir `http://localhost:3000/champions/elo` y comprobar que aparecen:
- “5 temporadas” y el rango 2021/22–2025/26.
- Partidos históricos aplicados.
- Regresión 20 %.
- Gráfico con varios años.

---

### Task 8: Documentación y verificación final

**Files:**
- Modify: `docs/champions.md`
- Modify: `docs/champions-calibration.md`
- Generated: `docs/champions-elo-5y-validation.md`

**Interfaces:**
- Consumes: resultados de Task 5 y Task 6.
- Produces: documentación coherente y verificación final.

- [ ] **Step 1: Reescribir la sección ELO de `docs/champions.md`**

Sustituye la sección `## ELO` por:

```markdown
## ELO

- Ventana: cinco temporadas de Champions, de 2021/22 a 2025/26.
- Fuente: OpenFootball. Total: 753 partidos.
- Semilla: ClubElo al inicio de la ventana si está disponible; si no, 1500.
- Replay cronológico con `K=20`, `H=60` y multiplicador por margen de goles.
- Al inicio de cada temporada se aplica una regresión del 20 % hacia 1500:
  `nuevo = actual + 0.20 * (1500 - actual)`.
- La temporada 2026/27 arranca desde el rating post-regresión y aplica los
  partidos ya jugados.
- Los equipos nuevos usan ClubElo 2026 si está disponible; si no, la media de
  los ratings actuales conocidos.
- La final se trata como campo neutral. Se usa el marcador a 90 minutos.
- Los ratings de LaLiga no se tocan.
```

- [ ] **Step 2: Reescribir `docs/champions-calibration.md`**

Sustituye el contenido por un informe con:

```markdown
# Calibración de SimuChampions

## Replay de ELO

- Ventana: 2021/22–2025/26.
- Partidos: 753.
- Regresión por temporada: 20 %.
- Semilla: la indicada por `seed_source`.

## Calibración de Davidson

- Temporada de calibración: 2025/26.
- Ratings de partida: inicio de 2025/26 del replay de cinco temporadas.
- Entrenamiento: jornadas 1–6 de la fase de liga.
- Validación: resto de 2025/26.
- Ajuste final: toda la temporada.

## Validación

Ver `docs/champions-elo-5y-validation.md` para el backtest, las correlaciones
y la búsqueda de alpha/K.

## Limitaciones

- Solo Champions: no se captura la forma doméstica.
- Los equipos sin Champions reciente parten de 1500 o de la media actual.
- La muestra de validación es una temporada.
```

- [ ] **Step 3: Revisar la codificación de los docs**

Comprobar que `docs/champions.md` y `docs/champions-calibration.md` no contienen
`Ã`, `Â`, `â€` ni `�`. Si aparece alguno, reescribir el archivo completo en UTF-8.

- [ ] **Step 4: Ejecutar todos los tests backend**

Run desde `backend/`: `python -m pytest`
Expected: PASS.

- [ ] **Step 5: Ejecutar todas las comprobaciones frontend**

Run desde `frontend/`: `npm run lint`
Expected: PASS.

Run desde `frontend/`: `npx tsc --noEmit`
Expected: PASS.

Run desde `frontend/`: `npm run build`
Expected: PASS.

- [ ] **Step 6: Verificar los endpoints**

Con el backend en marcha:

```powershell
Invoke-RestMethod http://localhost:8000/api/champions/elo |
  Select-Object -ExpandProperty verification
```

Expected: aparecen `history_seasons`, `history_start`, `history_end`,
`history_complete`, `season_regression` y los partidos históricos.

- [ ] **Step 7: Reportar resultados**

Resumir en la respuesta final:
- métricas del backtest (5 temporadas vs 1 temporada vs 1500);
- Spearman con 2025/26 y 2026/27;
- solapamiento del top 8;
- conclusión sobre si el ELO se ajusta al nivel actual y, si no, qué ajuste se
  propone.

---

## Autorrevisión del plan

- Cobertura del spec: configuración, datos, alias, replay, regresión, temporada
  actual, calibración, payload, API, UI, validación, tests y docs.
- Sin placeholders: los pasos incluyen código y comandos concretos.
- Consistencia de tipos: `HistoryReplayResult`, `history_labels`,
  `season_starts`, `season_ends`, `build_history_payload` y
  `build_snapshot_from_matches` se usan con las mismas firmas en todas las
  tareas.
