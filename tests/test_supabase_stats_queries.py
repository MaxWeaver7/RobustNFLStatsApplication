import pytest

from src.web import queries_supabase


class SBStub:
    def __init__(self, data):
        self.data = data

    def select(self, table, *, select="*", filters=None, order=None, limit=None, offset=0):
        key = (table, select, tuple(sorted((filters or {}).items())), order, limit, offset)
        if key in self.data:
            return self.data[key]
        # Looser matching: ignore select/order/limit for convenience
        for (t, _sel, f, _o, _l, _off), val in self.data.items():
            if t == table and f == tuple(sorted((filters or {}).items())):
                return val
        return []


def test_players_list_filters_to_players_with_stats():
    sb = SBStub(
        {
            # get_players_list now uses a single embedded select from nfl_player_season_stats
            (
                "nfl_player_season_stats",
                "*",
                (
                    ("or", "(passing_yards.gt.0,passing_attempts.gt.0,passing_touchdowns.gt.0,rushing_yards.gt.0,rushing_attempts.gt.0,rushing_touchdowns.gt.0,receiving_yards.gt.0,receptions.gt.0,receiving_touchdowns.gt.0,receiving_targets.gt.0)"),
                    ("postseason", "eq.false"),
                    ("season", "eq.2024"),
                ),
                None,
                None,
                0,
            ): [
                # no stats -> filtered out
                {"player_id": 1, "games_played": 17, "receiving_targets": 0, "receptions": 0, "rushing_attempts": 0, "nfl_players": {"first_name": "X", "last_name": "Y", "position_abbreviation": "WR", "team_id": 10, "nfl_teams": {"abbreviation": "ATL"}}},
                # has stats -> included
                {"player_id": 2, "games_played": 16, "receiving_targets": 100, "receptions": 80, "receiving_yards": 900, "receiving_touchdowns": 6, "nfl_players": {"first_name": "A", "last_name": "B", "position_abbreviation": "WR", "team_id": 10, "nfl_teams": {"abbreviation": "ATL"}}},
            ],
        }
    )
    rows = queries_supabase.get_players_list(sb, season=2024, position=None, team=None, limit=100)
    assert len(rows) == 1
    assert rows[0]["player_id"] == "2"
    assert rows[0]["targets"] == 100
    assert rows[0]["receptions"] == 80


def test_player_game_logs_shape():
    sb = SBStub(
        {
            ("nfl_player_game_stats", "*", (("player_id", "eq.2"), ("postseason", "eq.false"), ("season", "eq.2024")), "week.asc", None, 0): [
                {"player_id": 2, "game_id": 7001, "season": 2024, "week": 1, "postseason": False, "team_id": 10, "receiving_targets": 8, "receptions": 6, "receiving_yards": 75, "receiving_touchdowns": 1, "rushing_attempts": 0, "rushing_yards": 0, "rushing_touchdowns": 0},
            ],
            ("nfl_games", "*", (("id", "in.(7001)"),), None, None, 0): [
                {"id": 7001, "home_team_id": 10, "visitor_team_id": 11, "postseason": False},
            ],
            ("nfl_teams", "*", (("id", "in.(10,11)"),), None, None, 0): [{"id": 10, "abbreviation": "ATL"}, {"id": 11, "abbreviation": "NYJ"}],
        }
    )
    logs = queries_supabase.get_player_game_logs(sb, player_id="2", season=2024, include_postseason=False)
    assert len(logs) == 1
    g = logs[0]
    assert g["week"] == 1
    assert g["targets"] == 8
    assert g["rec_yards"] == 75
    assert g["rec_tds"] == 1
    assert g["home_team"] == "ATL"
    assert g["away_team"] == "NYJ"


