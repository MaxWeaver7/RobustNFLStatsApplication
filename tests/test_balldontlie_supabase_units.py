import pytest

from src.database.supabase_client import SupabaseClient, SupabaseConfig
from src.ingestion.balldontlie_client import BallDontLieError, BallDontLieNFLClient, RateLimiter
from src.ingestion.balldontlie_ingestor import (
    ingest_stats_and_advanced,
    map_adv_passing,
    map_adv_receiving,
    map_adv_rushing,
    map_game,
    map_player,
    map_team,
)
from src.web import queries_supabase


def test_map_team_player_game_shapes():
    t = map_team(
        {
            "id": 18,
            "conference": "NFC",
            "division": "EAST",
            "location": "Philadelphia",
            "name": "Eagles",
            "full_name": "Philadelphia Eagles",
            "abbreviation": "PHI",
        }
    )
    assert t["id"] == 18
    assert t["abbreviation"] == "PHI"
    assert "updated_at" in t

    p = map_player(
        {
            "id": 33,
            "first_name": "Lamar",
            "last_name": "Jackson",
            "position": "Quarterback",
            "position_abbreviation": "QB",
            "team": {"id": 6, "abbreviation": "BAL"},
        }
    )
    assert p["id"] == 33
    assert p["team_id"] == 6
    assert p["position_abbreviation"] == "QB"
    assert "updated_at" in p

    g = map_game(
        {
            "id": 7001,
            "season": 2024,
            "week": 1,
            "date": "2024-09-06T00:20:00.000Z",
            "postseason": False,
            "status": "Final",
            "venue": "Somewhere",
            "home_team": {"id": 14, "abbreviation": "KC"},
            "visitor_team": {"id": 6, "abbreviation": "BAL"},
            "home_team_score": 27,
            "visitor_team_score": 20,
        }
    )
    assert g["id"] == 7001
    assert g["home_team_id"] == 14
    assert g["visitor_team_id"] == 6
    assert g["season"] == 2024
    assert "updated_at" in g


class StubResponse:
    def __init__(self, status_code, json_body):
        self.status_code = status_code
        self._json = json_body
        self.headers = {}
        self.text = str(json_body)

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._json


class StubSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def request(self, method, url, headers=None, params=None, timeout=None, data=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "params": params, "timeout": timeout, "data": data})
        if not self._responses:
            raise RuntimeError("no more stub responses")
        return self._responses.pop(0)


def test_balldontlie_paginate_next_cursor(monkeypatch):
    # Two pages then stop.
    sess = StubSession(
        [
            StubResponse(200, {"data": [{"id": 1}, {"id": 2}], "meta": {"next_cursor": 99, "per_page": 2}}),
            StubResponse(200, {"data": [{"id": 3}], "meta": {"next_cursor": None, "per_page": 2}}),
        ]
    )

    rl = RateLimiter(min_interval_seconds=0.0, _sleep=lambda s: None)
    c = BallDontLieNFLClient(api_key="k", session=sess, rate_limiter=rl, sleep_fn=lambda s: None, per_page=2)
    rows = list(c.paginate("/players"))
    assert [r["id"] for r in rows] == [1, 2, 3]
    assert len(sess.calls) == 2
    # First call includes per_page but no cursor; second includes cursor
    assert sess.calls[0]["params"]["per_page"] == 2
    assert "cursor" not in sess.calls[0]["params"]
    assert sess.calls[1]["params"]["cursor"] == 99


def test_balldontlie_advanced_params_match_docs_week_omitted_when_zero():
    # Verify we send params in the format the API actually accepts:
    # - season is required
    # - postseason is optional; send integer 1 when true, omit when false (defaults to regular season)
    # - week is optional; omit when week=0 (season totals)
    sess = StubSession([StubResponse(200, {"data": [], "meta": {"next_cursor": None, "per_page": 1}})])
    rl = RateLimiter(min_interval_seconds=0.0, _sleep=lambda s: None)
    c = BallDontLieNFLClient(api_key="k", session=sess, rate_limiter=rl, sleep_fn=lambda s: None, per_page=1)
    list(c.iter_advanced_rushing(season=2024, week=0, postseason=False))
    assert sess.calls[0]["params"]["season"] == 2024
    assert "postseason" not in sess.calls[0]["params"]
    assert "week" not in sess.calls[0]["params"]

    sess = StubSession([StubResponse(200, {"data": [], "meta": {"next_cursor": None, "per_page": 1}})])
    c = BallDontLieNFLClient(api_key="k", session=sess, rate_limiter=rl, sleep_fn=lambda s: None, per_page=1)
    list(c.iter_advanced_passing(season=2024, week=2, postseason=True))
    assert sess.calls[0]["params"]["season"] == 2024
    assert sess.calls[0]["params"]["postseason"] == 1
    assert sess.calls[0]["params"]["week"] == 2


def test_queries_supabase_recent_games_hydrates_team_abbr(monkeypatch):
    # We only test logic wiring by stubbing sb.select calls.
    class SB:
        def __init__(self):
            self.calls = []

        def select(self, table, *, select="*", filters=None, order=None, limit=None, offset=0):
            self.calls.append((table, select, filters, order, limit, offset))
            if table == "nfl_games":
                return [
                    {
                        "id": 7001,
                        "season": 2024,
                        "week": 1,
                        "date": "2024-09-06T00:20:00.000Z",
                        "status": "Final",
                        "venue": "X",
                        "home_team_id": 14,
                        "visitor_team_id": 6,
                        "home_team_score": 27,
                        "visitor_team_score": 20,
                    }
                ]
            if table == "nfl_teams":
                return [{"id": 14, "abbreviation": "KC"}, {"id": 6, "abbreviation": "BAL"}]
            raise AssertionError("unexpected table " + table)

    sb = SB()
    rows = queries_supabase.recent_games(sb, season=2024, week=1, team_abbr=None, limit=10)
    assert rows[0]["home_team"] == "KC"
    assert rows[0]["visitor_team"] == "BAL"


def test_map_adv_rushing_includes_goat_fields():
    row = map_adv_rushing(
        {
            "player": {"id": 466},
            "season": 2024,
            "week": 0,
            "postseason": False,
            "avg_time_to_los": 2.9,
            "expected_rush_yards": 618.9,
            "rush_attempts": 159,
            "rush_pct_over_expected": 0.42,
            "rush_touchdowns": 5,
            "rush_yards": 697,
            "rush_yards_over_expected": 59.0,
            "rush_yards_over_expected_per_att": 0.38,
            "efficiency": 4.16,
            "percent_attempts_gte_eight_defenders": 25.1,
            "avg_rush_yards": 4.38,
        }
    )
    assert row["player_id"] == 466
    assert row["rush_touchdowns"] == 5
    assert row["avg_time_to_los"] == 2.9
    assert row["rush_pct_over_expected"] == 0.42
    assert row["percent_attempts_gte_eight_defenders"] == 25.1


def test_map_adv_passing_includes_goat_fields():
    row = map_adv_passing(
        {
            "player": {"id": 63},
            "season": 2024,
            "week": 0,
            "postseason": False,
            "aggressiveness": 13.9,
            "attempts": 322,
            "avg_air_distance": 21.6,
            "avg_air_yards_differential": -2.1,
            "avg_air_yards_to_sticks": -0.87,
            "avg_completed_air_yards": 5.5,
            "avg_intended_air_yards": 7.7,
            "avg_time_to_throw": 2.78,
            "completion_percentage": 66.45,
            "completion_percentage_above_expectation": -1.85,
            "completions": 214,
            "expected_completion_percentage": 68.31,
            "games_played": 9,
            "interceptions": 7,
            "max_air_distance": 62.0,
            "max_completed_air_distance": 55.9,
            "pass_touchdowns": 9,
            "pass_yards": 2262,
            "passer_rating": 86.99,
        }
    )
    assert row["player_id"] == 63
    assert row["expected_completion_percentage"] == 68.31
    assert row["avg_air_distance"] == 21.6
    assert row["max_air_distance"] == 62.0
    assert row["games_played"] == 9


def test_map_adv_receiving_includes_goat_fields():
    row = map_adv_receiving(
        {
            "player": {"id": 651},
            "season": 2024,
            "week": 0,
            "postseason": False,
            "avg_cushion": 8.23,
            "avg_expected_yac": 4.38,
            "avg_intended_air_yards": 12.6,
            "avg_separation": 3.57,
            "avg_yac": 3.58,
            "avg_yac_above_expectation": -0.79,
            "catch_percentage": 65,
            "percent_share_of_intended_air_yards": 20.6,
            "rec_touchdowns": 0,
            "receptions": 26,
            "targets": 40,
            "yards": 372,
        }
    )
    assert row["player_id"] == 651
    assert row["avg_cushion"] == 8.23
    assert row["avg_separation"] == 3.57
    assert row["percent_share_of_intended_air_yards"] == 20.6
    assert row["rec_touchdowns"] == 0


def test_ingest_stats_and_advanced_loops_weeks_and_postseason():
    class SB:
        def __init__(self):
            self.upserts = []

        def upsert(self, table, rows, on_conflict=None):
            self.upserts.append((table, on_conflict, rows))
            return len(rows)

    class BDL:
        def __init__(self):
            self.calls = []

        def iter_advanced_receiving(self, *, season: int, week: int = 0, postseason: bool = False):
            self.calls.append(("recv", season, week, postseason))
            return iter(
                [
                    {
                        "player": {"id": 1},
                        "season": season,
                        "week": week,
                        "postseason": postseason,
                        "targets": 1,
                        "receptions": 1,
                        "yards": 10,
                    }
                ]
            )

        def iter_advanced_rushing(self, *, season: int, week: int = 0, postseason: bool = False):
            self.calls.append(("rush", season, week, postseason))
            return iter(
                [
                    {
                        "player": {"id": 2},
                        "season": season,
                        "week": week,
                        "postseason": postseason,
                        "rush_attempts": 1,
                        "rush_yards": 5,
                    }
                ]
            )

        def iter_advanced_passing(self, *, season: int, week: int = 0, postseason: bool = False):
            self.calls.append(("pass", season, week, postseason))
            return iter(
                [
                    {
                        "player": {"id": 3},
                        "season": season,
                        "week": week,
                        "postseason": postseason,
                        "attempts": 1,
                        "completions": 1,
                        "pass_yards": 7,
                    }
                ]
            )

        # Unused by this test
        def iter_player_season_stats(self, *, season: int, postseason: bool = False):
            return iter([])

        def iter_player_game_stats(self, *, seasons):
            return iter([])

    sb = SB()
    bdl = BDL()
    ingest_stats_and_advanced(
        seasons=[2024],
        supabase=sb,  # type: ignore[arg-type]
        bdl=bdl,  # type: ignore[arg-type]
        include_season_stats=False,
        include_game_stats=False,
        include_advanced=True,
        advanced_weeks=[0, 1],
        advanced_include_postseason=True,
        batch_size=50,
    )

    # We only fetch postseason totals (week=0). No "postseason week 1".
    # 1 season * ((2 regular weeks) + (1 postseason total week)) * 3 endpoints = 9 calls
    assert len(bdl.calls) == 9

    # We upsert 1 row per call in this stub, so 9 total rows written across 3 tables
    total_rows = sum(len(rows) for _, __, rows in sb.upserts)
    assert total_rows == 9

    # Keys should be normalized/coerced
    for table, on_conflict, rows in sb.upserts:
        assert on_conflict == "player_id,season,week,postseason"
        assert isinstance(rows[0]["player_id"], int)
        assert isinstance(rows[0]["season"], int)
        assert isinstance(rows[0]["week"], int)
        assert isinstance(rows[0]["postseason"], bool)


def test_ingest_stats_and_advanced_skips_invalid_rows():
    class SB:
        def __init__(self):
            self.upserts = []

        def upsert(self, table, rows, on_conflict=None):
            self.upserts.append((table, rows))
            return len(rows)

    class BDL:
        def iter_advanced_receiving(self, *, season: int, week: int = 0, postseason: bool = False):
            return iter(
                [
                    # Invalid: missing embedded player => player_id=None
                    {"season": season, "week": week, "postseason": postseason, "targets": 1},
                    # Valid
                    {"player": {"id": 10}, "season": season, "week": week, "postseason": postseason, "targets": 2},
                ]
            )

        def iter_advanced_rushing(self, *, season: int, week: int = 0, postseason: bool = False):
            return iter([])

        def iter_advanced_passing(self, *, season: int, week: int = 0, postseason: bool = False):
            return iter([])

        def iter_player_season_stats(self, *, season: int, postseason: bool = False):
            return iter([])

        def iter_player_game_stats(self, *, seasons):
            return iter([])

    sb = SB()
    bdl = BDL()
    ingest_stats_and_advanced(
        seasons=[2024],
        supabase=sb,  # type: ignore[arg-type]
        bdl=bdl,  # type: ignore[arg-type]
        include_season_stats=False,
        include_game_stats=False,
        include_advanced=True,
        advanced_weeks=[0],
        advanced_include_postseason=False,
        batch_size=50,
    )
    assert len(sb.upserts) == 1
    table, rows = sb.upserts[0]
    assert table == "nfl_advanced_receiving_stats"
    assert len(rows) == 1
    assert rows[0]["player_id"] == 10


def test_ingest_stats_and_advanced_aborts_on_too_many_invalid_rows():
    class SB:
        def upsert(self, table, rows, on_conflict=None):
            return len(rows)

    class BDL:
        def iter_advanced_receiving(self, *, season: int, week: int = 0, postseason: bool = False):
            # 30 invalid rows (missing player) -> should trip the abort threshold
            return iter([{"season": season, "week": week, "postseason": postseason, "targets": 1} for _ in range(30)])

        def iter_advanced_rushing(self, *, season: int, week: int = 0, postseason: bool = False):
            return iter([])

        def iter_advanced_passing(self, *, season: int, week: int = 0, postseason: bool = False):
            return iter([])

        def iter_player_season_stats(self, *, season: int, postseason: bool = False):
            return iter([])

        def iter_player_game_stats(self, *, seasons):
            return iter([])

    with pytest.raises(ValueError):
        ingest_stats_and_advanced(
            seasons=[2024],
            supabase=SB(),  # type: ignore[arg-type]
            bdl=BDL(),  # type: ignore[arg-type]
            include_season_stats=False,
            include_game_stats=False,
            include_advanced=True,
            advanced_weeks=[0],
            advanced_include_postseason=False,
            batch_size=100,
        )


def test_ingest_stats_and_advanced_skips_transient_bdl_errors_and_continues():
    class SB:
        def __init__(self):
            self.upserts = []

        def upsert(self, table, rows, on_conflict=None):
            self.upserts.append((table, rows))
            return len(rows)

    class BDL:
        def __init__(self):
            self.pass_calls = 0

        def iter_advanced_receiving(self, *, season: int, week: int = 0, postseason: bool = False):
            # Simulate transient 500 from BDL on receiving (raised during iteration, like the real client).
            def _gen():
                raise BallDontLieError(
                    "HTTP 500 after retries for GET https://api.balldontlie.io/nfl/v1/advanced_stats/receiving: {\"message\":\"Internal Server Error\"}"
                )
                yield {}  # pragma: no cover

            return _gen()

        def iter_advanced_rushing(self, *, season: int, week: int = 0, postseason: bool = False):
            return iter([{"player": {"id": 2}, "season": season, "week": week, "postseason": postseason, "rush_attempts": 1}])

        def iter_advanced_passing(self, *, season: int, week: int = 0, postseason: bool = False):
            self.pass_calls += 1
            return iter([{"player": {"id": 3}, "season": season, "week": week, "postseason": postseason, "attempts": 1}])

        def iter_player_season_stats(self, *, season: int, postseason: bool = False):
            return iter([])

        def iter_player_game_stats(self, *, seasons):
            return iter([])

    sb = SB()
    ingest_stats_and_advanced(
        seasons=[2024],
        supabase=sb,  # type: ignore[arg-type]
        bdl=BDL(),  # type: ignore[arg-type]
        include_season_stats=False,
        include_game_stats=False,
        include_advanced=True,
        advanced_weeks=[0],
        advanced_include_postseason=False,
        batch_size=50,
    )

    # Receiving upsert should be skipped, rushing and passing should still write.
    tables = [t for t, _ in sb.upserts]
    assert "nfl_advanced_receiving_stats" not in tables
    assert "nfl_advanced_rushing_stats" in tables
    assert "nfl_advanced_passing_stats" in tables


