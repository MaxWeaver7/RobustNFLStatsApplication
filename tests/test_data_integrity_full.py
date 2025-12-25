import sqlite3

import pytest

from src.database.schema import create_tables
from src.ingestion.nflfastr_ingestor import ingest_rosters
from src.metrics.calculator import compute_all_metrics
from src.web import queries
from src.validation.checks import (
    check_no_duplicate_plays,
    check_routes_ge_targets,
    check_season_totals_sum_correctly,
    check_targets_pfr_vs_pbp,
    check_yprr_bounds,
    run_all_checks,
)


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    create_tables(c)
    return c


def seed_minimal_game(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executemany("INSERT OR IGNORE INTO teams(team_abbr) VALUES (?)", [("KC",), ("BUF",)])
    cur.execute(
        """
        INSERT INTO games(game_id, season, week, home_team, away_team)
        VALUES ('G1', 2024, 1, 'KC', 'BUF')
        """
    )
    # player_id values intentionally resemble PFR-style IDs (often used in data-stat="player")
    cur.executemany(
        "INSERT INTO players(player_id, player_name, position, team_abbr) VALUES (?, ?, ?, ?)",
        [
            ("KelcTr00", "Travis Kelce", "TE", "KC"),
            ("RiceRa00", "Rashee Rice", "WR", "KC"),
        ],
    )

    # plays: Rice targeted 3 times, 2 catches for 25 yards and 12 YAC, 1 receiving TD.
    plays = [
        # target, complete, yards, yac, air, epa, cpoe, pass_td
        ("G1", 1, 2024, 1, "KC", "BUF", 1, 1, 10.0, 5.0, 8.0, 0.2, 1.0, 0, "RiceRa00"),
        ("G1", 2, 2024, 1, "KC", "BUF", 1, 1, 15.0, 7.0, 12.0, 0.3, 2.0, 1, "RiceRa00"),
        ("G1", 3, 2024, 1, "KC", "BUF", 1, 0, 0.0, 0.0, 6.0, -0.1, -1.0, 0, "RiceRa00"),
        # Kelce: 1 target, 1 catch
        ("G1", 4, 2024, 1, "KC", "BUF", 1, 1, 7.0, 2.0, 5.0, 0.1, 0.5, 0, "KelcTr00"),
    ]
    cur.executemany(
        """
        INSERT INTO plays(
            game_id, play_id, season, week, posteam, defteam,
            target, complete_pass, yards_gained, yards_after_catch, air_yards, epa, cpoe, pass_touchdown, receiver_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        plays,
    )

    # PFR receiving advanced provides routes (needed for YPRR and routes>=targets checks)
    cur.executemany(
        """
        INSERT INTO receiving_advanced(
            player_id, game_id, season, week, team_abbr, targets, receptions, rec_yards, routes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("RiceRa00", "G1", 2024, 1, "KC", 3, 2, 25.0, 12),
            ("KelcTr00", "G1", 2024, 1, "KC", 1, 1, 7.0, 20),
        ],
    )

    # Snap counts (optional, but should be handled)
    cur.executemany(
        """
        INSERT INTO player_game_stats(player_id, game_id, season, week, team_abbr, snaps_offense, snap_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("RiceRa00", "G1", 2024, 1, "KC", 55, 0.85),
            ("KelcTr00", "G1", 2024, 1, "KC", 60, 0.92),
        ],
    )
    conn.commit()


def test_compute_and_validate_happy_path(conn):
    seed_minimal_game(conn)
    compute_all_metrics(conn)

    # No validation issues for seeded data.
    assert run_all_checks(conn) == []

    # Receiving TDs surface in the dashboard queries.
    rows = queries.player_game_receiving(conn, season=2024, week=1, team="KC", limit=25)
    got = {r["player_id"]: r for r in rows}
    assert got["RiceRa00"]["rec_tds"] == 1
    assert got["KelcTr00"]["rec_tds"] == 0


def test_duplicate_play_ids_detected(conn):
    seed_minimal_game(conn)
    # The schema enforces uniqueness via PRIMARY KEY (game_id, play_id),
    # which is stronger than a post-hoc duplicate detector.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO plays(
                game_id, play_id, season, week, posteam, defteam, target, complete_pass, receiver_id
            ) VALUES ('G1', 1, 2024, 1, 'KC', 'BUF', 1, 1, 'RiceRa00')
            """
        )
        conn.commit()


def test_routes_ge_targets_for_wr_te(conn):
    seed_minimal_game(conn)
    compute_all_metrics(conn)
    assert check_routes_ge_targets(conn) == []


def test_yprr_bounds(conn):
    seed_minimal_game(conn)
    compute_all_metrics(conn)
    assert check_yprr_bounds(conn, lo=0.0, hi=30.0) == []


def test_pfr_targets_close_to_pbp(conn):
    seed_minimal_game(conn)
    compute_all_metrics(conn)
    assert check_targets_pfr_vs_pbp(conn, tolerance=2) == []


def test_season_totals_sum(conn):
    seed_minimal_game(conn)
    compute_all_metrics(conn)
    assert check_season_totals_sum_correctly(conn) == []


def seed_minimal_passing(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executemany("INSERT OR IGNORE INTO teams(team_abbr) VALUES (?)", [("KC",), ("BUF",)])
    cur.execute(
        """
        INSERT INTO games(game_id, season, week, home_team, away_team)
        VALUES ('G2', 2024, 2, 'KC', 'BUF')
        """
    )
    cur.executemany(
        "INSERT INTO players(player_id, player_name, position, team_abbr) VALUES (?, ?, ?, ?)",
        [
            ("MahomPa00", "Patrick Mahomes", "QB", "KC"),
        ],
    )
    plays = [
        # 5 attempts: 3 completions for 75 yards, 1 TD, 1 INT
        ("G2", 1, 2024, 2, "KC", "BUF", 1, 1, 20.0, 0, 0, 0.25, 5.0, "MahomPa00"),
        ("G2", 2, 2024, 2, "KC", "BUF", 1, 1, 30.0, 0, 1, 0.35, 8.0, "MahomPa00"),
        ("G2", 3, 2024, 2, "KC", "BUF", 1, 0, 0.0, 0, 0, -0.10, -2.0, "MahomPa00"),
        ("G2", 4, 2024, 2, "KC", "BUF", 1, 1, 25.0, 0, 0, 0.10, 3.0, "MahomPa00"),
        ("G2", 5, 2024, 2, "KC", "BUF", 1, 0, 0.0, 1, 0, -0.20, -5.0, "MahomPa00"),
    ]
    cur.executemany(
        """
        INSERT INTO plays(
            game_id, play_id, season, week, posteam, defteam,
            pass, complete_pass, yards_gained, interception, pass_touchdown, epa, cpoe, passer_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        plays,
    )
    conn.commit()


def test_passing_queries_game_and_season(conn):
    seed_minimal_passing(conn)
    rows = queries.player_game_passing(conn, season=2024, week=2, team="KC", limit=25)
    assert len(rows) == 1
    r = rows[0]
    assert r["attempts"] == 5
    assert r["completions"] == 3
    assert r["pass_yards"] == 75.0
    assert r["pass_tds"] == 1
    assert r["interceptions"] == 1

    rows2 = queries.season_passing(conn, season=2024, team="KC", limit=25)
    assert len(rows2) == 1
    r2 = rows2[0]
    assert r2["attempts"] == 5
    assert r2["pass_yards"] == 75.0
    assert r2["pass_tds"] == 1
    assert 0.99 < float(r2["team_pass_share"]) <= 1.0


def seed_minimal_expanded(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executemany("INSERT OR IGNORE INTO teams(team_abbr) VALUES (?)", [("KC",), ("BUF",)])
    cur.execute(
        """
        INSERT INTO games(game_id, season, week, gameday, home_team, away_team)
        VALUES ('G3', 2024, 3, '2024-09-22', 'KC', 'BUF')
        """
    )
    cur.executemany(
        "INSERT INTO players(player_id, player_name, position, team_abbr) VALUES (?, ?, ?, ?)",
        [
            ("RiceRa00", "Rashee Rice", "WR", "KC"),
        ],
    )

    # Column order for plays insert below:
    # (game_id, play_id, season, week, posteam, defteam,
    #  pass, complete_pass, yards_gained, yards_after_catch, air_yards, epa, cpoe,
    #  pass_touchdown, rush_touchdown, receiver_id, rusher_id, rush)
    plays = [
        # Receiving: 3 targets, 2 catches, 25 yards, 12 YAC, 1 TD.
        ("G3", 1, 2024, 3, "KC", "BUF", 1, 1, 10.0, 5.0, 8.0, 0.2, 0.0, 0, 0, "RiceRa00", None, 0),
        ("G3", 2, 2024, 3, "KC", "BUF", 1, 1, 15.0, 7.0, 12.0, 0.3, 0.0, 1, 0, "RiceRa00", None, 0),
        ("G3", 3, 2024, 3, "KC", "BUF", 1, 0, 0.0, 0.0, 6.0, -0.1, 0.0, 0, 0, "RiceRa00", None, 0),
        # Rushing: 2 attempts, 11 yards, 1 TD.
        ("G3", 4, 2024, 3, "KC", "BUF", 0, 0, 4.0, 0.0, 0.0, 0.05, 0.0, 0, 0, None, "RiceRa00", 1),
        ("G3", 5, 2024, 3, "KC", "BUF", 0, 0, 7.0, 0.0, 0.0, 0.10, 0.0, 0, 1, None, "RiceRa00", 1),
    ]
    cur.executemany(
        """
        INSERT INTO plays(
            game_id, play_id, season, week, posteam, defteam,
            pass, complete_pass, yards_gained, yards_after_catch, air_yards, epa, cpoe,
            pass_touchdown, rush_touchdown,
            receiver_id, rusher_id, rush
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        plays,
    )

    # PFR advanced tables (optional enrichment)
    cur.execute(
        """
        INSERT INTO receiving_advanced(
            player_id, game_id, season, week, team_abbr,
            targets, receptions, rec_yards, air_yards, ybc, yac, adot, drops, drop_pct, broken_tackles, routes
        ) VALUES (
            'RiceRa00', 'G3', 2024, 3, 'KC',
            3, 2, 25, 26, 13, 12, 8.7, 1, 20.0, 2, 18
        )
        """
    )
    cur.execute(
        """
        INSERT INTO rushing_advanced(
            player_id, game_id, season, week, team_abbr,
            attempts, rush_yards, ybc, yac, broken_tackles
        ) VALUES (
            'RiceRa00', 'G3', 2024, 3, 'KC',
            2, 11, 5, 6, 1
        )
        """
    )
    conn.commit()


def test_player_expanded_gamelog_prefers_pfr_when_available(conn):
    seed_minimal_expanded(conn)
    rows = queries.player_expanded_gamelog(conn, player_id="RiceRa00", season=2024, limit=10)
    assert len(rows) == 1
    r = rows[0]
    assert r["season"] == 2024
    assert r["week"] == 3
    assert r["targets"] == 3
    assert r["receptions"] == 2
    assert r["rec_yards"] == 25.0
    assert r["rec_tds"] == 1
    assert r["rush_attempts"] == 2
    assert r["rush_yards"] == 11.0
    assert r["rush_tds"] == 1
    # Advanced values come from PFR tables when present
    assert r["recv_yac"] == 12.0
    assert r["recv_ybc"] == 13.0
    assert r["recv_adot"] == 8.7
    assert r["rush_yac"] == 6.0


def test_player_expanded_gamelog_derives_yac_when_pfr_missing(conn):
    seed_minimal_expanded(conn)
    conn.execute("DELETE FROM receiving_advanced WHERE player_id='RiceRa00'")
    conn.execute("DELETE FROM rushing_advanced WHERE player_id='RiceRa00'")
    conn.commit()

    rows = queries.player_expanded_gamelog(conn, player_id="RiceRa00", season=2024, limit=10)
    assert len(rows) == 1
    r = rows[0]
    # Derived from pbp
    assert r["pbp_yac"] == 12.0
    # PFR columns are absent
    assert r["recv_yac"] is None
    assert r["rush_yac"] is None


def test_ingest_rosters_updates_positions_and_teams(conn, monkeypatch):
    import pandas as pd

    # Players exist but are missing (or have wrong) positions.
    conn.execute("INSERT OR IGNORE INTO teams(team_abbr) VALUES ('KC')")
    conn.executemany(
        "INSERT OR REPLACE INTO players(player_id, player_name, position, team_abbr) VALUES (?, ?, ?, ?)",
        [
            ("RiceRa00", "Rashee Rice", None, None),
            ("KelcTr00", "Travis Kelce", "WR", None),  # wrong on purpose
        ],
    )
    conn.commit()

    df = pd.DataFrame(
        [
            {"gsis_id": "RiceRa00", "position": "WR", "team": "KC", "season": 2024},
            {"gsis_id": "KelcTr00", "position": "TE", "team": "KC", "season": 2024},
        ]
    )

    class StubNflDataPy:
        @staticmethod
        def import_seasonal_rosters(seasons):
            return df

    monkeypatch.setitem(__import__("sys").modules, "nfl_data_py", StubNflDataPy)

    updated = ingest_rosters([2024], conn)
    assert updated >= 1

    rows = conn.execute(
        "SELECT player_id, position, team_abbr FROM players WHERE player_id IN ('RiceRa00','KelcTr00') ORDER BY player_id"
    ).fetchall()
    got = {r["player_id"]: (r["position"], r["team_abbr"]) for r in rows}
    assert got["RiceRa00"] == ("WR", "KC")
    assert got["KelcTr00"] == ("TE", "KC")


