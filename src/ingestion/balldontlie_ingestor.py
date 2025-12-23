from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from src.database.supabase_client import SupabaseClient
from src.ingestion.balldontlie_client import BallDontLieNFLClient


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoreIngestSummary:
    teams_upserted: int
    players_upserted: int
    games_upserted: int


@dataclass(frozen=True)
class StatsIngestSummary:
    season_stats_upserted: int
    game_stats_upserted: int
    adv_receiving_upserted: int
    adv_rushing_upserted: int
    adv_passing_upserted: int


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chunked(items: Iterable[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    buf: list[dict[str, Any]] = []
    for it in items:
        buf.append(it)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def map_team(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": t.get("id"),
        "conference": t.get("conference"),
        "division": t.get("division"),
        "location": t.get("location"),
        "name": t.get("name"),
        "full_name": t.get("full_name"),
        "abbreviation": t.get("abbreviation"),
        "updated_at": _now_iso(),
    }


def map_player(p: dict[str, Any]) -> dict[str, Any]:
    team = p.get("team") if isinstance(p.get("team"), dict) else None
    team_id = team.get("id") if isinstance(team, dict) else None
    return {
        "id": p.get("id"),
        "first_name": p.get("first_name"),
        "last_name": p.get("last_name"),
        "position": p.get("position"),
        "position_abbreviation": p.get("position_abbreviation"),
        "height": p.get("height"),
        "weight": p.get("weight"),
        "jersey_number": p.get("jersey_number"),
        "college": p.get("college"),
        "experience": p.get("experience"),
        "age": p.get("age"),
        "team_id": team_id,
        "updated_at": _now_iso(),
    }


def map_game(g: dict[str, Any]) -> dict[str, Any]:
    home = g.get("home_team") if isinstance(g.get("home_team"), dict) else None
    visitor = g.get("visitor_team") if isinstance(g.get("visitor_team"), dict) else None
    return {
        "id": g.get("id"),
        "season": g.get("season"),
        "week": g.get("week"),
        "date": g.get("date"),
        "postseason": g.get("postseason"),
        "status": g.get("status"),
        "venue": g.get("venue"),
        "summary": g.get("summary"),
        "home_team_id": home.get("id") if isinstance(home, dict) else None,
        "visitor_team_id": visitor.get("id") if isinstance(visitor, dict) else None,
        "home_team_score": g.get("home_team_score"),
        "home_team_q1": g.get("home_team_q1"),
        "home_team_q2": g.get("home_team_q2"),
        "home_team_q3": g.get("home_team_q3"),
        "home_team_q4": g.get("home_team_q4"),
        "home_team_ot": g.get("home_team_ot"),
        "visitor_team_score": g.get("visitor_team_score"),
        "visitor_team_q1": g.get("visitor_team_q1"),
        "visitor_team_q2": g.get("visitor_team_q2"),
        "visitor_team_q3": g.get("visitor_team_q3"),
        "visitor_team_q4": g.get("visitor_team_q4"),
        "visitor_team_ot": g.get("visitor_team_ot"),
        "updated_at": _now_iso(),
    }


def map_player_season_stats(s: dict[str, Any]) -> dict[str, Any]:
    p = s.get("player") if isinstance(s.get("player"), dict) else None
    pid = p.get("id") if isinstance(p, dict) else None
    return {
        "player_id": pid,
        "season": s.get("season"),
        "postseason": s.get("postseason", False),
        "games_played": s.get("games_played"),
        "passing_completions": s.get("passing_completions"),
        "passing_attempts": s.get("passing_attempts"),
        "passing_yards": s.get("passing_yards"),
        "passing_touchdowns": s.get("passing_touchdowns"),
        "passing_interceptions": s.get("passing_interceptions"),
        "qbr": s.get("qbr"),
        "qb_rating": s.get("qb_rating"),
        "rushing_attempts": s.get("rushing_attempts"),
        "rushing_yards": s.get("rushing_yards"),
        "rushing_touchdowns": s.get("rushing_touchdowns"),
        "receptions": s.get("receptions"),
        "receiving_yards": s.get("receiving_yards"),
        "receiving_touchdowns": s.get("receiving_touchdowns"),
        "receiving_targets": s.get("receiving_targets"),
        "updated_at": _now_iso(),
    }


def map_player_game_stats(s: dict[str, Any]) -> dict[str, Any]:
    p = s.get("player") if isinstance(s.get("player"), dict) else None
    pid = p.get("id") if isinstance(p, dict) else None
    t = s.get("team") if isinstance(s.get("team"), dict) else None
    tid = t.get("id") if isinstance(t, dict) else None
    g = s.get("game") if isinstance(s.get("game"), dict) else None
    gid = g.get("id") if isinstance(g, dict) else None
    return {
        "player_id": pid,
        "game_id": gid,
        "season": g.get("season") if isinstance(g, dict) else None,
        "week": g.get("week") if isinstance(g, dict) else None,
        "postseason": g.get("postseason", False) if isinstance(g, dict) else False,
        "team_id": tid,
        "passing_completions": s.get("passing_completions"),
        "passing_attempts": s.get("passing_attempts"),
        "passing_yards": s.get("passing_yards"),
        "passing_touchdowns": s.get("passing_touchdowns"),
        "passing_interceptions": s.get("passing_interceptions"),
        "qbr": s.get("qbr"),
        "qb_rating": s.get("qb_rating"),
        "rushing_attempts": s.get("rushing_attempts"),
        "rushing_yards": s.get("rushing_yards"),
        "rushing_touchdowns": s.get("rushing_touchdowns"),
        "receptions": s.get("receptions"),
        "receiving_yards": s.get("receiving_yards"),
        "receiving_touchdowns": s.get("receiving_touchdowns"),
        "receiving_targets": s.get("receiving_targets"),
        "updated_at": _now_iso(),
    }


def map_adv_receiving(s: dict[str, Any]) -> dict[str, Any]:
    p = s.get("player") if isinstance(s.get("player"), dict) else None
    pid = p.get("id") if isinstance(p, dict) else None
    return {
        "player_id": pid,
        "season": s.get("season"),
        "week": s.get("week"),
        "postseason": s.get("postseason", False),
        "receptions": s.get("receptions"),
        "targets": s.get("targets"),
        "yards": s.get("yards"),
        "avg_intended_air_yards": s.get("avg_intended_air_yards"),
        "avg_yac": s.get("avg_yac"),
        "avg_expected_yac": s.get("avg_expected_yac"),
        "avg_yac_above_expectation": s.get("avg_yac_above_expectation"),
        "catch_percentage": s.get("catch_percentage"),
        "updated_at": _now_iso(),
    }


def map_adv_rushing(s: dict[str, Any]) -> dict[str, Any]:
    p = s.get("player") if isinstance(s.get("player"), dict) else None
    pid = p.get("id") if isinstance(p, dict) else None
    return {
        "player_id": pid,
        "season": s.get("season"),
        "week": s.get("week"),
        "postseason": s.get("postseason", False),
        "rush_attempts": s.get("rush_attempts"),
        "rush_yards": s.get("rush_yards"),
        "efficiency": s.get("efficiency"),
        "avg_rush_yards": s.get("avg_rush_yards"),
        "expected_rush_yards": s.get("expected_rush_yards"),
        "rush_yards_over_expected": s.get("rush_yards_over_expected"),
        "rush_yards_over_expected_per_att": s.get("rush_yards_over_expected_per_att"),
        "updated_at": _now_iso(),
    }


def map_adv_passing(s: dict[str, Any]) -> dict[str, Any]:
    p = s.get("player") if isinstance(s.get("player"), dict) else None
    pid = p.get("id") if isinstance(p, dict) else None
    return {
        "player_id": pid,
        "season": s.get("season"),
        "week": s.get("week"),
        "postseason": s.get("postseason", False),
        "attempts": s.get("attempts"),
        "completions": s.get("completions"),
        "pass_yards": s.get("pass_yards"),
        "pass_touchdowns": s.get("pass_touchdowns"),
        "interceptions": s.get("interceptions"),
        "passer_rating": s.get("passer_rating"),
        "completion_percentage": s.get("completion_percentage"),
        "completion_percentage_above_expectation": s.get("completion_percentage_above_expectation"),
        "avg_time_to_throw": s.get("avg_time_to_throw"),
        "avg_intended_air_yards": s.get("avg_intended_air_yards"),
        "avg_completed_air_yards": s.get("avg_completed_air_yards"),
        "aggressiveness": s.get("aggressiveness"),
        "updated_at": _now_iso(),
    }


def ingest_core(
    *,
    seasons: list[int],
    supabase: SupabaseClient,
    bdl: BallDontLieNFLClient,
    batch_size: int = 500,
) -> CoreIngestSummary:
    # 1) Teams
    teams_raw = bdl.list_teams()
    teams_rows = [map_team(t) for t in teams_raw]
    teams_upserted = supabase.upsert("nfl_teams", teams_rows, on_conflict="id") if teams_rows else 0
    logger.info("Upserted nfl_teams=%d", teams_upserted)

    # 2) Players (cursor pagination)
    players_upserted = 0
    for chunk in _chunked((map_player(p) for p in bdl.iter_players()), batch_size):
        players_upserted += supabase.upsert("nfl_players", chunk, on_conflict="id")
        if players_upserted % (batch_size * 10) == 0:
            logger.info("Upserted nfl_players=%d", players_upserted)
    logger.info("Upserted nfl_players=%d", players_upserted)

    # 3) Games (for seasons)
    games_upserted = 0
    for chunk in _chunked((map_game(g) for g in bdl.iter_games(seasons=seasons)), batch_size):
        games_upserted += supabase.upsert("nfl_games", chunk, on_conflict="id")
        if games_upserted % (batch_size * 10) == 0:
            logger.info("Upserted nfl_games=%d", games_upserted)
    logger.info("Upserted nfl_games=%d", games_upserted)

    return CoreIngestSummary(
        teams_upserted=teams_upserted,
        players_upserted=players_upserted,
        games_upserted=games_upserted,
    )


def ingest_stats_and_advanced(
    *,
    seasons: list[int],
    supabase: SupabaseClient,
    bdl: BallDontLieNFLClient,
    batch_size: int = 500,
    include_season_stats: bool = True,
    include_game_stats: bool = True,
    include_advanced: bool = True,
) -> StatsIngestSummary:
    season_stats_upserted = 0
    # Season stats
    if include_season_stats:
        for season in seasons:
            for chunk in _chunked(
                (map_player_season_stats(s) for s in bdl.iter_player_season_stats(season=season, postseason=False)),
                batch_size,
            ):
                season_stats_upserted += supabase.upsert(
                    "nfl_player_season_stats", chunk, on_conflict="player_id,season,postseason"
                )
    logger.info("Upserted nfl_player_season_stats=%d", season_stats_upserted)

    # Per-game player stats
    game_stats_upserted = 0
    if include_game_stats:
        for chunk in _chunked((map_player_game_stats(s) for s in bdl.iter_player_game_stats(seasons=seasons)), batch_size):
            game_stats_upserted += supabase.upsert("nfl_player_game_stats", chunk, on_conflict="player_id,game_id")
            if game_stats_upserted % (batch_size * 10) == 0:
                logger.info("Upserted nfl_player_game_stats=%d", game_stats_upserted)
    logger.info("Upserted nfl_player_game_stats=%d", game_stats_upserted)

    # Advanced stats (week 0 = full season)
    adv_receiving_upserted = 0
    adv_rushing_upserted = 0
    adv_passing_upserted = 0
    if include_advanced:
        for season in seasons:
            for chunk in _chunked((map_adv_receiving(s) for s in bdl.iter_advanced_receiving(season=season, week=0, postseason=False)), batch_size):
                adv_receiving_upserted += supabase.upsert("nfl_advanced_receiving_stats", chunk, on_conflict="player_id,season,week,postseason")
            for chunk in _chunked((map_adv_rushing(s) for s in bdl.iter_advanced_rushing(season=season, week=0, postseason=False)), batch_size):
                adv_rushing_upserted += supabase.upsert("nfl_advanced_rushing_stats", chunk, on_conflict="player_id,season,week,postseason")
            for chunk in _chunked((map_adv_passing(s) for s in bdl.iter_advanced_passing(season=season, week=0, postseason=False)), batch_size):
                adv_passing_upserted += supabase.upsert("nfl_advanced_passing_stats", chunk, on_conflict="player_id,season,week,postseason")
    logger.info(
        "Upserted advanced stats: receiving=%d rushing=%d passing=%d",
        adv_receiving_upserted,
        adv_rushing_upserted,
        adv_passing_upserted,
    )

    return StatsIngestSummary(
        season_stats_upserted=season_stats_upserted,
        game_stats_upserted=game_stats_upserted,
        adv_receiving_upserted=adv_receiving_upserted,
        adv_rushing_upserted=adv_rushing_upserted,
        adv_passing_upserted=adv_passing_upserted,
    )


