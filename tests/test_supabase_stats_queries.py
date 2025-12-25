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
            # get_players_list now queries nfl_player_season_stats with embedded nfl_players
            (
                "nfl_player_season_stats",
                "player_id,games_played,passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions,qbr,qb_rating,rushing_attempts,rushing_yards,rushing_touchdowns,receptions,receiving_yards,receiving_touchdowns,receiving_targets,nfl_players!inner(id,first_name,last_name,position_abbreviation,team_id,nfl_teams(abbreviation))",
                (
                    ("postseason", "eq.false"),
                    ("season", "eq.2024"),
                ),
                "passing_yards.desc.nullslast",
                5000,
                0,
            ): [
                # has season stats -> included
                {
                    "player_id": 2,
                    "games_played": 16,
                    "receiving_targets": 100,
                    "receptions": 80,
                    "receiving_yards": 900,
                    "receiving_touchdowns": 6,
                    "rushing_attempts": 0,
                    "rushing_yards": 0,
                    "rushing_touchdowns": 0,
                    "passing_attempts": 0,
                    "passing_completions": 0,
                    "passing_yards": 0,
                    "passing_touchdowns": 0,
                    "passing_interceptions": 0,
                    "qbr": None,
                    "qb_rating": None,
                    "nfl_players": {
                        "id": 2,
                        "first_name": "A",
                        "last_name": "B",
                        "position_abbreviation": "WR",
                        "team_id": 10,
                        "nfl_teams": {"abbreviation": "ATL"},
                    },
                },
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


def test_players_list_can_filter_by_name_on_embedded_players_relation():
    sb = SBStub(
        {
            (
                "nfl_player_season_stats",
                "player_id,games_played,passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions,qbr,qb_rating,rushing_attempts,rushing_yards,rushing_touchdowns,receptions,receiving_yards,receiving_touchdowns,receiving_targets,nfl_players!inner(or(first_name.ilike.*jo*,last_name.ilike.*jo*)id,first_name,last_name,position_abbreviation,team_id,nfl_teams(abbreviation))",
                (
                    ("postseason", "eq.false"),
                    ("season", "eq.2024"),
                ),
                "passing_yards.desc.nullslast",
                1400,
                0,
            ): [
                {
                    "player_id": 10,
                    "games_played": 16,
                    "passing_yards": 4000,
                    "passing_attempts": 600,
                    "passing_completions": 400,
                    "passing_touchdowns": 30,
                    "passing_interceptions": 10,
                    "rushing_attempts": 0,
                    "rushing_yards": 0,
                    "rushing_touchdowns": 0,
                    "receiving_targets": 0,
                    "receptions": 0,
                    "receiving_yards": 0,
                    "receiving_touchdowns": 0,
                    "qbr": None,
                    "qb_rating": None,
                    "nfl_players": {
                        "id": 10,
                        "first_name": "Joe",
                        "last_name": "Tester",
                        "position_abbreviation": "QB",
                        "team_id": 10,
                        "nfl_teams": {"abbreviation": "ATL"},
                    },
                },
            ],
        }
    )
    rows = queries_supabase.get_players_list(sb, season=2024, position=None, team=None, q="jo", limit=50, offset=25)
    assert len(rows) == 1
    assert rows[0]["player_id"] == "10"


def test_passing_season_supports_q_name_filter():
    sb = SBStub(
        {
            (
                "nfl_player_season_stats",
                "player_id,passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions,nfl_players(first_name,last_name,position_abbreviation,team_id,nfl_teams(abbreviation))",
                (
                    ("nfl_players.or", "(first_name.ilike.*jo*,last_name.ilike.*jo*)"),
                    ("or", "(passing_yards.gt.0,passing_attempts.gt.0,passing_touchdowns.gt.0)"),
                    ("postseason", "eq.false"),
                    ("season", "eq.2024"),
                ),
                "passing_yards.desc.nullslast,passing_touchdowns.desc.nullslast",
                1000,
                0,
            ): [
                {
                    "player_id": 10,
                    "passing_attempts": 600,
                    "passing_completions": 400,
                    "passing_yards": 4000,
                    "passing_touchdowns": 30,
                    "passing_interceptions": 10,
                    "nfl_players": {
                        "first_name": "Joe",
                        "last_name": "Tester",
                        "position_abbreviation": "QB",
                        "team_id": 10,
                        "nfl_teams": {"abbreviation": "ATL"},
                    },
                }
            ],
        }
    )

    rows = queries_supabase.passing_season(sb, season=2024, team=None, position=None, q="jo", limit=25)
    assert len(rows) == 1
    assert rows[0]["player_name"] == "Joe Tester"


def test_get_players_list_qb_filter_includes_unknown_pos_when_stats_show_qb():
    sb = SBStub(
        {
            (
                "nfl_player_season_stats",
                "player_id,games_played,passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions,qbr,qb_rating,rushing_attempts,rushing_yards,rushing_touchdowns,receptions,receiving_yards,receiving_touchdowns,receiving_targets,nfl_players!inner(id,first_name,last_name,position_abbreviation,team_id,nfl_teams(abbreviation))",
                (
                    ("postseason", "eq.false"),
                    ("season", "eq.2024"),
                ),
                "passing_yards.desc.nullslast",
                5000,
                0,
            ): [
                {
                    "player_id": 99,
                    "games_played": 10,
                    "passing_attempts": 320,
                    "passing_completions": 200,
                    "passing_yards": 2276,
                    "passing_touchdowns": 14,
                    "passing_interceptions": 6,
                    "rushing_attempts": 30,
                    "rushing_yards": 120,
                    "rushing_touchdowns": 1,
                    "receiving_targets": 0,
                    "receptions": 0,
                    "receiving_yards": 0,
                    "receiving_touchdowns": 0,
                    "qbr": None,
                    "qb_rating": None,
                    "nfl_players": {
                        "id": 99,
                        "first_name": "Drake",
                        "last_name": "Maye",
                        "position_abbreviation": None,  # unknown in nfl_players
                        "team_id": 1,
                        "nfl_teams": {"abbreviation": "NE"},
                    },
                }
            ],
        }
    )

    rows = queries_supabase.get_players_list(sb, season=2024, position="QB", team=None, limit=100, offset=0)
    assert len(rows) == 1
    assert rows[0]["player_name"] == "Drake Maye"
    assert rows[0]["passingYards"] == 2276


