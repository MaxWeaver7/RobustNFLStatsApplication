from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from src.database.supabase_client import SupabaseClient


def player_photo_url(player_id: str) -> Optional[str]:
    # Deprecated signature (kept for compatibility). Use player_photo_url_from_name_team instead.
    return None


_NAME_RE = re.compile(r"[^a-z0-9 ]+")

_SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}

_TEAM_ABBR_ALIASES: dict[str, str] = {
    # ESPN-ish -> nflfastR-ish / dynastyprocess team codes in db_playerids.csv
    "KC": "KCC",
    "NE": "NEP",
    "NO": "NOS",
    "LV": "LVR",
    "SF": "SFO",
    "TB": "TBB",
    "GB": "GNB",
    "JAX": "JAC",
    "WSH": "WAS",
}


def _normalize_team_abbr(team: Optional[str]) -> str:
    t = (team or "").strip().upper()
    if not t:
        return ""
    return _TEAM_ABBR_ALIASES.get(t, t)


def _merge_name(name: str) -> str:
    s = _NAME_RE.sub("", (name or "").lower()).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _merge_name_candidates(name: str) -> list[str]:
    """
    Generate candidate merge_name values to improve matches for suffixes like Jr/Sr/III.
    """
    base = _merge_name(name)
    if not base:
        return []
    parts = base.split(" ")
    if not parts:
        return [base]

    out: list[str] = [base]

    # Strip a trailing suffix token if present.
    if parts and parts[-1] in _SUFFIX_TOKENS:
        no_suffix = " ".join(parts[:-1]).strip()
        if no_suffix and no_suffix != base:
            out.append(no_suffix)
            parts = no_suffix.split(" ")

    # If there are middle tokens (nicknames / middle names), also try first+last.
    if len(parts) >= 3:
        first_last = f"{parts[0]} {parts[-1]}".strip()
        if first_last and first_last not in out:
            out.append(first_last)

    # Deduplicate preserving order.
    seen = set()
    dedup: list[str] = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        dedup.append(x)
    return dedup


def player_photo_url_from_name_team(*, name: str, team: Optional[str]) -> Optional[str]:
    """
    Best-effort headshot URL based on player name + team.

    Uses dynastyprocess db_playerids.csv (already cached in hrb/data/db_playerids.csv).
    Prefers ESPN headshots, falls back to Sleeper.
    """
    maps = _photo_maps()
    if not maps:
        return None
    by_name_team, by_name, by_last_team, by_last = maps

    team_abbr = _normalize_team_abbr(team)
    for mn in _merge_name_candidates(name):
        ids = by_name_team.get((mn, team_abbr)) if team_abbr else None
        if ids is None:
            ids = by_name.get(mn)
        if ids is None:
            # Try last-name fallbacks
            last = mn.split(" ")[-1] if mn else ""
            if last:
                ids = by_last_team.get((last, team_abbr)) if team_abbr else None
                if ids is None:
                    ids = by_last.get(last)
        if ids is None:
            continue

        espn_id, sleeper_id = ids
        if espn_id:
            return f"https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"
        if sleeper_id:
            return f"https://sleepercdn.com/content/nfl/players/{sleeper_id}.jpg"
        return None
    return None


def _clean_id(v: Any) -> Optional[str]:
    s = str(v or "").strip()
    if not s or s.lower() == "nan" or s.lower() == "na":
        return None
    return s


PhotoMaps = tuple[
    dict[tuple[str, str], tuple[Optional[str], Optional[str]]],
    dict[str, tuple[Optional[str], Optional[str]]],
    dict[tuple[str, str], tuple[Optional[str], Optional[str]]],
    dict[str, tuple[Optional[str], Optional[str]]],
]


@lru_cache(maxsize=1)
def _photo_maps() -> Optional[PhotoMaps]:
    """
    Load and cache (process-wide) the dynastyprocess db_playerids.csv lookup maps.

    This is called for every player row rendered in the UI, so it must be fast.
    """
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "data" / "db_playerids.csv"
    if not path.exists():
        return None

    # Keep "best" row per key by highest db_season (mirrors the old pandas sort/newest-first behavior).
    by_name_team_s: dict[tuple[str, str], tuple[int, Optional[str], Optional[str]]] = {}
    by_name_s: dict[str, tuple[int, Optional[str], Optional[str]]] = {}
    by_last_team_s: dict[tuple[str, str], tuple[int, Optional[str], Optional[str]]] = {}
    by_last_s: dict[str, tuple[int, Optional[str], Optional[str]]] = {}

    def _season_num(raw: Any) -> int:
        try:
            return int(str(raw or "").strip())
        except Exception:
            return -1

    def _upsert_best(
        m: dict[Any, tuple[int, Optional[str], Optional[str]]],
        key: Any,
        season: int,
        espn: Optional[str],
        sleeper: Optional[str],
    ) -> None:
        cur = m.get(key)
        if cur is None or season > cur[0]:
            m[key] = (season, espn, sleeper)

    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mn = _merge_name(row.get("merge_name") or "")
                if not mn:
                    continue
                tn = str(row.get("team") or "").strip().upper()
                season = _season_num(row.get("db_season"))
                espn = _clean_id(row.get("espn_id"))
                sleeper = _clean_id(row.get("sleeper_id"))

                _upsert_best(by_name_team_s, (mn, tn), season, espn, sleeper)
                _upsert_best(by_name_s, mn, season, espn, sleeper)

                last = mn.split(" ")[-1] if mn else ""
                if last:
                    _upsert_best(by_last_team_s, (last, tn), season, espn, sleeper)
                    _upsert_best(by_last_s, last, season, espn, sleeper)
    except Exception:
        return None

    by_name_team = {k: (v[1], v[2]) for k, v in by_name_team_s.items()}
    by_name = {k: (v[1], v[2]) for k, v in by_name_s.items()}
    by_last_team = {k: (v[1], v[2]) for k, v in by_last_team_s.items()}
    by_last = {k: (v[1], v[2]) for k, v in by_last_s.items()}
    return by_name_team, by_name, by_last_team, by_last


def _uniq_sorted_int(vals: list[Any], *, desc: bool = False) -> list[int]:
    out: list[int] = []
    seen = set()
    for v in vals:
        try:
            i = int(v)
        except Exception:
            continue
        if i in seen:
            continue
        seen.add(i)
        out.append(i)
    return sorted(out, reverse=desc)


def _in_list(values: list[int]) -> str:
    inner = ",".join(str(int(v)) for v in values)
    return f"in.({inner})"

def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None or x == "":
            return None
        return int(x)
    except Exception:
        return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def _team_map(sb: SupabaseClient, team_ids: list[int]) -> dict[int, str]:
    team_map: dict[int, str] = {}
    if not team_ids:
        return team_map
    teams = sb.select("nfl_teams", select="id,abbreviation", filters={"id": _in_list(team_ids)}, limit=len(team_ids))
    for t in teams:
        try:
            team_map[int(t["id"])] = str(t.get("abbreviation") or "").upper()
        except Exception:
            continue
    return team_map


def options(sb: SupabaseClient) -> dict[str, Any]:
    games = sb.select("nfl_games", select="season,week", order="season.desc,week.asc", limit=5000)
    seasons = _uniq_sorted_int([g.get("season") for g in games], desc=True)
    weeks = _uniq_sorted_int([g.get("week") for g in games], desc=False)
    teams = sb.select("nfl_teams", select="abbreviation", order="abbreviation.asc", limit=1000)
    team_abbr = [t.get("abbreviation") for t in teams if isinstance(t.get("abbreviation"), str)]
    positions = ["QB", "RB", "WR", "TE"]
    return {"seasons": seasons, "weeks": weeks, "teams": team_abbr, "positions": positions}


def summary(sb: SupabaseClient) -> dict[str, Any]:
    games = sb.count("nfl_games")
    players = sb.count("nfl_players")
    teams = sb.count("nfl_teams")
    seasons_rows = sb.select("nfl_games", select="season", order="season.asc", limit=5000)
    seasons = _uniq_sorted_int([r.get("season") for r in seasons_rows], desc=False)
    # Mirror the existing JSON shape expected by the React UI (it doesn't depend on most fields).
    return {"seasons": seasons, "games": games, "players": players, "teams": teams}

def _has_any_stats(row: dict[str, Any]) -> bool:
    # Player recorded at least one meaningful offensive stat.
    # Important: some feeds may omit attempts/targets but still populate yards/TDs.
    for k in (
        # passing volume/production
        "passing_attempts",
        "passing_completions",
        "passing_yards",
        "passing_touchdowns",
        # rushing volume/production
        "rushing_attempts",
        "rushing_yards",
        "rushing_touchdowns",
        # receiving volume/production
        "receiving_targets",
        "receptions",
        "receiving_yards",
        "receiving_touchdowns",
    ):
        v = _safe_int(row.get(k))
        if v is not None and v > 0:
            return True
    return False


def _sanitize_search(q: Optional[str]) -> Optional[str]:
    """
    Create a safe token for PostgREST ilike filters.
    We intentionally strip anything that could break the query syntax (commas, parens, wildcards).
    """
    s = (q or "").strip()
    if not s:
        return None
    s = re.sub(r"[^a-zA-Z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) < 2:
        return None
    return s


def get_players_list(
    sb: SupabaseClient,
    *,
    season: Optional[int],
    position: Optional[str],
    team: Optional[str],
    q: Optional[str] = None,
    limit: int,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Players with Stats ONLY (INNER JOIN)
    Uses !inner to force INNER JOIN on stats table - only shows players who have
    season stats for the requested season. Includes rookies like Dart/Egbuka who HAVE stats,
    but excludes practice squad players with no stats.
    """
    if season is None:
        return []

    # Defensive/special teams positions to BLOCK
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}
    
    # Build filters for the INNER JOIN query
    player_filters: dict[str, Any] = {}
    
    # Filter by team if specified
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        if t:
            team_id = _safe_int(t[0].get("id"))
            if team_id:
                player_filters["team_id"] = f"eq.{team_id}"
    
    # Text search on name
    needle = _sanitize_search(q)
    if needle:
        player_filters["or"] = f"(first_name.ilike.*{needle}*,last_name.ilike.*{needle}*)"
    
    # CRITICAL: Filter stats by season (PostgREST foreign table filter syntax)
    player_filters["nfl_player_season_stats.season"] = f"eq.{int(season)}"
    player_filters["nfl_player_season_stats.postseason"] = "eq.false"
    
    # STRATEGY: Query from nfl_player_season_stats (ordered by passing_yards desc)
    # This ensures we get the TOP players, not just alphabetically first 1000
    safe_limit = max(int(limit or 0), 1)
    safe_offset = max(int(offset or 0), 0)
    
    # Build filters for the stats table
    stats_filters: dict[str, Any] = {
        "season": f"eq.{int(season)}",
        "postseason": "eq.false",
    }
    
    # Build embed filter for nfl_players (team + name search)
    embed_filters = []
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        if t:
            team_id = _safe_int(t[0].get("id"))
            if team_id:
                embed_filters.append(f"team_id.eq.{team_id}")
    if needle:
        embed_filters.append(f"or(first_name.ilike.*{needle}*,last_name.ilike.*{needle}*)")
    
    embed_filter_str = ",".join(embed_filters) if embed_filters else ""
    
    # Request many rows; Supabase will cap at ~1000
    req_limit = 5000
    req_offset = 0
    
    # Query from stats table, embed players, order by passing_yards (gets QBs first, which is fine)
    stats_rows = sb.select(
        "nfl_player_season_stats",
        select=(
            "player_id,games_played,"
            "passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions,"
            "qbr,qb_rating,"
            "rushing_attempts,rushing_yards,rushing_touchdowns,"
            "receptions,receiving_yards,receiving_touchdowns,receiving_targets,"
            f"nfl_players!inner({embed_filter_str if embed_filter_str else ''}id,first_name,last_name,position_abbreviation,team_id,nfl_teams(abbreviation))"
        ),
        filters=stats_filters,
        order="passing_yards.desc.nullslast",
        limit=req_limit,
        offset=req_offset,
    )
    
    # Restructure: convert stats-centric rows to player-centric
    players = []
    for stat_row in stats_rows:
        player_obj = stat_row.get("nfl_players")
        if not player_obj:
            continue
        # Merge stats into player object
        player_obj["nfl_player_season_stats"] = [stat_row]
        players.append(player_obj)
    
    
    # Process players with PYTHON-SIDE DEFENSIVE BLOCKING
    out: list[dict[str, Any]] = []
    pos_filter = (position or "").strip().upper()
    
    for p in players:
        pid = _safe_int(p.get("id"))
        if not pid:
            continue
        
        pos = (p.get("position_abbreviation") or "").strip().upper() or None

        # Extract stats from embedded table (INNER JOIN guarantees at least one row)
        stats_list = p.get("nfl_player_season_stats") or []
        stats = stats_list[0] if stats_list else {}

        games = _safe_int(stats.get("games_played")) or 0
        targets = _safe_int(stats.get("receiving_targets")) or 0
        rec = _safe_int(stats.get("receptions")) or 0
        rec_yards = _safe_int(stats.get("receiving_yards")) or 0
        rec_tds = _safe_int(stats.get("receiving_touchdowns")) or 0
        rush_att = _safe_int(stats.get("rushing_attempts")) or 0
        rush_yards = _safe_int(stats.get("rushing_yards")) or 0
        rush_tds = _safe_int(stats.get("rushing_touchdowns")) or 0
        pass_att = _safe_int(stats.get("passing_attempts")) or 0
        pass_cmp = _safe_int(stats.get("passing_completions")) or 0
        pass_yds = _safe_int(stats.get("passing_yards")) or 0
        pass_tds = _safe_int(stats.get("passing_touchdowns")) or 0
        pass_int = _safe_int(stats.get("passing_interceptions")) or 0
        qb_rating = _safe_float(stats.get("qb_rating"))
        qbr = _safe_float(stats.get("qbr"))

        # Position Filtering (Defense Blocker)
        # Special case: some feeds leave rookies as NULL/UNK/ROOKIE in nfl_players even though stats prove role.
        is_unknown_pos = (not pos) or (pos in {"UNK", "UNKNOWN", "NULL", "ROOKIE"})
        if pos in blocked_positions:
            continue  # Defensive/special teams

        if pos_filter:
            if not is_unknown_pos:
                if pos != pos_filter:
                    continue
            else:
                # Heuristic: allow unknown position if stats clearly match the requested role.
                if pos_filter == "QB":
                    if not (pass_att > 0 or pass_yds > 0 or pass_tds > 0):
                        continue
                elif pos_filter == "RB":
                    if not (rush_att > 0 or rush_yards > 0 or rush_tds > 0):
                        continue
                elif pos_filter in {"WR", "TE"}:
                    if not (targets > 0 or rec > 0 or rec_yards > 0 or rec_tds > 0):
                        continue
                else:
                    # Unknown filter value; be strict.
                    continue

        # Build player dict
        first = (p.get("first_name") or "").strip()
        last = (p.get("last_name") or "").strip()
        name = (first + " " + last).strip() or str(pid)
        
        team_obj = p.get("nfl_teams") or {}
        team_abbr = team_obj.get("abbreviation") or None
        
        avg_ypc = (float(rec_yards) / float(rec)) if rec else 0.0
        avg_ypr = (float(rush_yards) / float(rush_att)) if rush_att else 0.0
        photo = player_photo_url_from_name_team(name=name, team=team_abbr)
        
        out.append(
            {
                "player_id": str(pid),
                "player_name": name,
                "team": team_abbr,
                "position": pos or "UNK",
                "season": season,
                "games": games,
                "targets": targets,
                "receptions": rec,
                "receivingYards": rec_yards,
                "receivingTouchdowns": rec_tds,
                "avgYardsPerCatch": avg_ypc,
                "rushAttempts": rush_att,
                "rushingYards": rush_yards,
                "rushingTouchdowns": rush_tds,
                "avgYardsPerRush": avg_ypr,
                "passingAttempts": pass_att,
                "passingCompletions": pass_cmp,
                "passingYards": pass_yds,
                "passingTouchdowns": pass_tds,
                "passingInterceptions": pass_int,
                "qbRating": qb_rating,
                "qbr": qbr,
                "photoUrl": photo,
            }
        )
    
    # DON'T break early! We must process ALL fetched players before sorting/slicing
    # Otherwise players like "Stafford" (late alphabetically) get cut off
    
    if needle:
        # Keep name order for search results; slice to requested limit.
        return out[:safe_limit]

    # Sort by position-specific primary yards (QB: passing, RB: rushing, WR/TE: receiving)
    def sort_key(r: dict[str, Any]) -> int:
        pos = (r.get("position") or "").strip().upper()
        pass_yds = int(r.get("passingYards") or 0)
        rush_yds = int(r.get("rushingYards") or 0)
        rec_yds = int(r.get("receivingYards") or 0)
        
        if pos == "QB":
            return pass_yds
        elif pos in {"RB", "HB"}:
            return rush_yds
        elif pos in {"WR", "TE"}:
            return rec_yds
        else:
            # Unknown position: use total yards
            return pass_yds + rush_yds + rec_yds

    out.sort(key=sort_key, reverse=True)
    start = safe_offset
    end = safe_offset + safe_limit
    return out[start:end]


def get_player_game_logs(
    sb: SupabaseClient,
    player_id: str,
    season: int,
    *,
    include_postseason: bool = False,
) -> list[dict[str, Any]]:
    pid = _safe_int(player_id)
    if pid is None:
        return []

    # If include_postseason, return both; otherwise regular season only.
    filters: dict[str, Any] = {
        "player_id": f"eq.{pid}",
        "season": f"eq.{int(season)}",
    }
    if not include_postseason:
        filters["postseason"] = "eq.false"

    rows = sb.select(
        "nfl_player_game_stats",
        select=(
            "player_id,game_id,season,week,postseason,team_id,"
            "rushing_attempts,rushing_yards,rushing_touchdowns,"
            "receptions,receiving_yards,receiving_touchdowns,receiving_targets,"
            "passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions,"
            "qbr,qb_rating"
        ),
        filters=filters,
        order="week.asc",
        limit=400,
    )
    if not rows:
        return []

    game_ids = sorted({int(r["game_id"]) for r in rows if r.get("game_id") not in (None, "")})
    games = sb.select(
        "nfl_games",
        select="id,home_team_id,visitor_team_id,postseason",
        filters={"id": _in_list(game_ids)},
        limit=len(game_ids),
    )
    game_map: dict[int, dict[str, Any]] = {}
    team_ids = set()
    for g in games:
        gid = _safe_int(g.get("id"))
        if gid is None:
            continue
        game_map[gid] = g
        ht = _safe_int(g.get("home_team_id"))
        vt = _safe_int(g.get("visitor_team_id"))
        if ht is not None:
            team_ids.add(ht)
        if vt is not None:
            team_ids.add(vt)

    # Also include player's team_id values for mapping to abbreviation.
    for r in rows:
        tid = _safe_int(r.get("team_id"))
        if tid is not None:
            team_ids.add(tid)

    tmap = _team_map(sb, sorted(team_ids))

    out: list[dict[str, Any]] = []
    for r in rows:
        gid = _safe_int(r.get("game_id"))
        if gid is None:
            continue
        g = game_map.get(gid, {})
        ht = _safe_int(g.get("home_team_id"))
        vt = _safe_int(g.get("visitor_team_id"))
        tid = _safe_int(r.get("team_id"))

        team_abbr = tmap.get(tid) if tid is not None else None
        home_abbr = tmap.get(ht) if ht is not None else None
        away_abbr = tmap.get(vt) if vt is not None else None

        location = "home"
        opp = None
        if tid is not None and ht is not None and vt is not None:
            if tid == ht:
                location = "home"
                opp = away_abbr
            else:
                location = "away"
                opp = home_abbr

        out.append(
            {
                "season": _safe_int(r.get("season")) or season,
                "week": _safe_int(r.get("week")) or 0,
                "game_id": str(gid),
                "team": team_abbr,
                "opponent": opp,
                "home_team": home_abbr,
                "away_team": away_abbr,
                "location": location,
                "is_postseason": bool(r.get("postseason")),
                # Receiving
                "targets": _safe_int(r.get("receiving_targets")) or 0,
                "receptions": _safe_int(r.get("receptions")) or 0,
                "rec_yards": _safe_int(r.get("receiving_yards")) or 0,
                "rec_tds": _safe_int(r.get("receiving_touchdowns")) or 0,
                "air_yards": 0,
                "yac": 0,
                # no EPA yet
                # Rushing
                "rush_attempts": _safe_int(r.get("rushing_attempts")) or 0,
                "rush_yards": _safe_int(r.get("rushing_yards")) or 0,
                "rush_tds": _safe_int(r.get("rushing_touchdowns")) or 0,
                # Passing
                "passing_attempts": _safe_int(r.get("passing_attempts")) or 0,
                "passing_completions": _safe_int(r.get("passing_completions")) or 0,
                "passing_yards": _safe_int(r.get("passing_yards")) or 0,
                "passing_tds": _safe_int(r.get("passing_touchdowns")) or 0,
                "interceptions": _safe_int(r.get("passing_interceptions")) or 0,
                "qb_rating": _safe_float(r.get("qb_rating")),
                "qbr": _safe_float(r.get("qbr")),
            }
        )

    return out


def receiving_dashboard(
    sb: SupabaseClient,
    *,
    season: int,
    week: int,
    team: Optional[str],
    position: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    # Pull weekly player game stats, then hydrate player + team display fields.
    filters: dict[str, Any] = {
        "season": f"eq.{int(season)}",
        "week": f"eq.{int(week)}",
        "postseason": "eq.false",
        # only rows with real receiving involvement
        "or": "(receiving_yards.gt.0,receiving_targets.gt.0,receptions.gt.0,receiving_touchdowns.gt.0)",
    }
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        tid = _safe_int(t[0].get("id")) if t else None
        if tid is not None:
            filters["team_id"] = f"eq.{tid}"
    # Use PostgREST embedding to avoid extra round-trips for player/team hydration.
    stats = sb.select(
        "nfl_player_game_stats",
        select=(
            "player_id,team_id,season,week,receiving_targets,receptions,receiving_yards,receiving_touchdowns,"
            "nfl_players(first_name,last_name,position_abbreviation),"
            "nfl_teams(abbreviation)"
        ),
        filters=filters,
        order="receiving_yards.desc",
        limit=500,
    )

    pos_raw = (position or "").strip().upper()
    if pos_raw in {"", "ALL"}:
        allowed_positions = {"WR", "TE", "RB"}
    elif pos_raw == "HB":
        allowed_positions = {"RB"}
    else:
        allowed_positions = {pos_raw}

    # Defensive/special teams positions to exclude (unless user explicitly filters for them)
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}

    out = []
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        p = r.get("nfl_players") or {}
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        
        # Allow NULL/UNK/empty positions if they have receiving stats (already filtered by query)
        # But block defensive/special teams positions unless explicitly requested
        if pos and pos not in allowed_positions:
            # If user filtered for specific position, skip mismatches
            if pos_raw not in {"", "ALL"} or pos in blocked_positions:
                continue
        targets = _safe_int(r.get("receiving_targets")) or 0
        rec = _safe_int(r.get("receptions")) or 0
        rec_y = _safe_int(r.get("receiving_yards")) or 0
        rec_td = _safe_int(r.get("receiving_touchdowns")) or 0
        name = (str(p.get("first_name") or "").strip() + " " + str(p.get("last_name") or "").strip()).strip() or str(pid)
        t = r.get("nfl_teams") or {}
        team_abbr = (t.get("abbreviation") or None)
        out.append(
            {
                "season": season,
                "week": week,
                "team": team_abbr,
                "player_id": str(pid),
                "player_name": name,
                "position": pos,
                "targets": targets,
                "receptions": rec,
                "rec_yards": rec_y,
                "rec_tds": rec_td,
                "air_yards": 0,
                "yac": 0,
                "photoUrl": player_photo_url_from_name_team(name=name, team=team_abbr),
            }
        )
    
    # FORCE SORT by receiving yards descending to fix ordering issues
    out.sort(key=lambda x: (x.get('rec_yards') or 0), reverse=True)
    
    return out


def rushing_dashboard(
    sb: SupabaseClient,
    *,
    season: int,
    week: int,
    team: Optional[str],
    position: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {
        "season": f"eq.{int(season)}",
        "week": f"eq.{int(week)}",
        "postseason": "eq.false",
        "or": "(rushing_yards.gt.0,rushing_attempts.gt.0,rushing_touchdowns.gt.0)",
    }
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        tid = _safe_int(t[0].get("id")) if t else None
        if tid is not None:
            filters["team_id"] = f"eq.{tid}"
    stats = sb.select(
        "nfl_player_game_stats",
        select=(
            "player_id,team_id,season,week,rushing_attempts,rushing_yards,rushing_touchdowns,receptions,receiving_yards,"
            "nfl_players(first_name,last_name,position_abbreviation),"
            "nfl_teams(abbreviation)"
        ),
        filters=filters,
        order="rushing_yards.desc",
        limit=500,
    )

    pos_raw = (position or "").strip().upper()
    if pos_raw in {"", "ALL"}:
        allowed_positions = {"RB", "QB", "WR", "TE"}
    elif pos_raw == "HB":
        allowed_positions = {"RB"}
    else:
        allowed_positions = {pos_raw}

    # Defensive/special teams positions to exclude (unless user explicitly filters for them)
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}

    out = []
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        p = r.get("nfl_players") or {}
        name = (str(p.get("first_name") or "").strip() + " " + str(p.get("last_name") or "").strip()).strip() or str(pid)
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        
        # Allow NULL/UNK/empty positions if they have rushing stats (already filtered by query)
        # But block defensive/special teams positions unless explicitly requested
        if pos and pos not in allowed_positions:
            # If user filtered for specific position, skip mismatches
            if pos_raw not in {"", "ALL"} or pos in blocked_positions:
                continue
        t = r.get("nfl_teams") or {}
        team_abbr = (t.get("abbreviation") or None)
        rush_att = _safe_int(r.get("rushing_attempts")) or 0
        rush_y = _safe_int(r.get("rushing_yards")) or 0
        rec = _safe_int(r.get("receptions")) or 0
        rec_y = _safe_int(r.get("receiving_yards")) or 0
        out.append(
            {
                "season": season,
                "week": week,
                "team": team_abbr,
                "player_id": str(pid),
                "player_name": name,
                "position": pos,
                "rush_attempts": rush_att,
                "rush_yards": rush_y,
                "rush_tds": _safe_int(r.get("rushing_touchdowns")) or 0,
                "ypc": (float(rush_y) / float(rush_att)) if rush_att else 0.0,
                "receptions": rec,
                "rec_yards": rec_y,
                "ypr": (float(rec_y) / float(rec)) if rec else 0.0,
                "photoUrl": player_photo_url_from_name_team(name=name, team=team_abbr),
            }
        )
    
    # FORCE SORT by rushing yards descending to fix ordering issues
    out.sort(key=lambda x: (x.get('rush_yards') or 0), reverse=True)
    
    return out


def receiving_season(
    sb: SupabaseClient,
    *,
    season: int,
    team: Optional[str],
    q: Optional[str] = None,
    limit: int,
) -> list[dict[str, Any]]:
    # Use season stats; team is best-effort (current team).
    rows = get_players_list(sb, season=season, position=None, team=team, q=q, limit=8000)
    # compute team target share within returned team scope
    by_team: dict[str, int] = {}
    for r in rows:
        t = r.get("team") or ""
        by_team[t] = by_team.get(t, 0) + int(r.get("targets") or 0)
    # Defensive/special teams positions to exclude
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}
    
    out = []
    for r in rows:
        pos = (r.get("position") or "").upper()
        # Allow NULL/UNK/empty positions if they have receiving stats
        # Block defensive/special teams positions
        if pos and pos not in {"WR", "TE", "RB"}:
            if pos in blocked_positions:
                continue
        t = r.get("team") or ""
        denom = by_team.get(t, 0) or 0
        share = (float(r.get("targets") or 0) / float(denom)) if denom else None
        out.append(
            {
                "season": season,
                "team": r.get("team"),
                "player_id": r.get("player_id"),
                "player_name": r.get("player_name"),
                "position": r.get("position"),
                "targets": int(r.get("targets") or 0),
                "receptions": int(r.get("receptions") or 0),
                "rec_yards": int(r.get("receivingYards") or 0),
                "air_yards": 0,
                "rec_tds": int(r.get("receivingTouchdowns") or 0),
                "team_target_share": share,
                "photoUrl": player_photo_url_from_name_team(name=str(r.get("player_name") or ""), team=str(r.get("team") or "")),
            }
        )
    out.sort(key=lambda x: int(x.get("targets") or 0), reverse=True)
    return out[: min(max(limit, 1), 200)]


def rushing_season(
    sb: SupabaseClient,
    *,
    season: int,
    team: Optional[str],
    position: Optional[str],
    q: Optional[str] = None,
    limit: int,
) -> list[dict[str, Any]]:
    pos_raw = (position or "").strip().upper()
    pos_filter = None if pos_raw in {"", "ALL"} else ("RB" if pos_raw == "HB" else pos_raw)

    rows = get_players_list(sb, season=season, position=pos_filter, team=team, q=q, limit=8000)
    by_team: dict[str, int] = {}
    for r in rows:
        t = r.get("team") or ""
        by_team[t] = by_team.get(t, 0) + int(r.get("rushAttempts") or 0)
    out = []
    for r in rows:
        pos = (r.get("position") or "").upper()
        # Position filtering already applied above when requested. Default includes all positions.
        t = r.get("team") or ""
        denom = by_team.get(t, 0) or 0
        share = (float(r.get("rushAttempts") or 0) / float(denom)) if denom else None
        games = int(r.get("games") or 0) or 0
        rush_att = int(r.get("rushAttempts") or 0)
        rush_y = int(r.get("rushingYards") or 0)
        rec = int(r.get("receptions") or 0)
        rec_y = int(r.get("receivingYards") or 0)
        out.append(
            {
                "season": season,
                "team": r.get("team"),
                "player_id": r.get("player_id"),
                "player_name": r.get("player_name"),
                "position": r.get("position"),
                "games": games,
                "rush_attempts": rush_att,
                "rush_yards": rush_y,
                "rush_tds": int(r.get("rushingTouchdowns") or 0),
                "ypc": (float(rush_y) / float(rush_att)) if rush_att else 0.0,
                "ypg": (float(rush_y) / float(games)) if games else 0.0,
                "receptions": rec,
                "rpg": (float(rec) / float(games)) if games else 0.0,
                "rec_yards": rec_y,
                "rec_ypg": (float(rec_y) / float(games)) if games else 0.0,
                "team_rush_share": share,
                "photoUrl": player_photo_url_from_name_team(name=str(r.get("player_name") or ""), team=str(r.get("team") or "")),
            }
        )
    out.sort(key=lambda x: int(x.get("rush_yards") or 0), reverse=True)
    return out[: min(max(limit, 1), 200)]


def passing_dashboard(
    sb: SupabaseClient,
    *,
    season: int,
    week: int,
    team: Optional[str],
    position: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {
        "season": f"eq.{int(season)}",
        "week": f"eq.{int(week)}",
        "postseason": "eq.false",
        "or": "(passing_yards.gt.0,passing_attempts.gt.0,passing_touchdowns.gt.0)",
    }
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        tid = _safe_int(t[0].get("id")) if t else None
        if tid is not None:
            filters["team_id"] = f"eq.{tid}"
    stats = sb.select(
        "nfl_player_game_stats",
        select="player_id,team_id,season,week,passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions",
        filters=filters,
        limit=5000,
    )
    # DON'T slice yet - need to filter by position first

    pids = sorted({_safe_int(r.get("player_id")) for r in stats if _safe_int(r.get("player_id")) is not None})
    players = sb.select("nfl_players", select="id,first_name,last_name,position_abbreviation", filters={"id": _in_list(pids)}, limit=len(pids))
    pmap = {int(p["id"]): p for p in players if _safe_int(p.get("id")) is not None}

    team_ids = sorted({_safe_int(r.get("team_id")) for r in stats if _safe_int(r.get("team_id")) is not None})
    tmap = _team_map(sb, [t for t in team_ids if t is not None])

    pos_raw = (position or "").strip().upper()
    if pos_raw in {"", "ALL"}:
        allowed_positions = {"QB"}
    else:
        allowed_positions = {pos_raw}
    
    # Defensive/special teams positions to exclude (unless user explicitly filters for them)
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}
    
    out = []
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        p = pmap.get(pid, {})
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        
        # Allow NULL/UNK/empty positions if they have passing stats (already filtered by query)
        # But block defensive/special teams positions unless explicitly requested
        if pos and pos not in allowed_positions:
            # If user filtered for specific position, skip mismatches
            if pos_raw not in {"", "ALL"} or pos in blocked_positions:
                continue
        pass_att = _safe_int(r.get("passing_attempts")) or 0
        name = (str(p.get("first_name") or "").strip() + " " + str(p.get("last_name") or "").strip()).strip() or str(pid)
        tid = _safe_int(r.get("team_id"))
        out.append(
            {
                "season": season,
                "week": week,
                "team": tmap.get(tid) if tid is not None else None,
                "player_id": str(pid),
                "player_name": name,
                "position": pos,
                "passing_attempts": pass_att,
                "passing_completions": _safe_int(r.get("passing_completions")) or 0,
                "passing_yards": _safe_int(r.get("passing_yards")) or 0,
                "passing_tds": _safe_int(r.get("passing_touchdowns")) or 0,
                "interceptions": _safe_int(r.get("passing_interceptions")) or 0,
                "photoUrl": player_photo_url_from_name_team(name=name, team=tmap.get(tid) if tid is not None else None),
            }
        )
    
    # FORCE SORT by passing yards descending to fix ordering issues
    out.sort(key=lambda x: (x.get('passing_yards') or 0), reverse=True)
    
    return out[: min(max(limit, 1), 200)]


def passing_season(
    sb: SupabaseClient,
    *,
    season: int,
    team: Optional[str],
    position: Optional[str],
    q: Optional[str] = None,
    limit: int,
) -> list[dict[str, Any]]:
    # Keep this endpoint simple and robust: query the season-stats table directly and order by passing yards.
    # This avoids relying on broad player-list queries that may be subject to server-side max row caps.
    pos_raw = (position or "").strip().upper()
    pos_filter = None if pos_raw in {"", "ALL"} else pos_raw

    filters: dict[str, Any] = {
        "season": f"eq.{int(season)}",
        "postseason": "eq.false",
        "or": "(passing_yards.gt.0,passing_attempts.gt.0,passing_touchdowns.gt.0)",
    }

    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        tid = _safe_int(t[0].get("id")) if t else None
        if tid is not None:
            # PostgREST foreign-table filter syntax (season_stats -> nfl_players).
            filters["nfl_players.team_id"] = f"eq.{tid}"

    needle = _sanitize_search(q)
    if needle:
        filters["nfl_players.or"] = f"(first_name.ilike.*{needle}*,last_name.ilike.*{needle}*)"

    # Fetch a buffer to allow python-side position heuristics for unknown positions.
    req_limit = 1000
    rows = sb.select(
        "nfl_player_season_stats",
        select=(
            "player_id,passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions,"
            "nfl_players(first_name,last_name,position_abbreviation,team_id,nfl_teams(abbreviation))"
        ),
        filters=filters,
        order="passing_yards.desc.nullslast,passing_touchdowns.desc.nullslast",
        limit=req_limit,
    )

    out: list[dict[str, Any]] = []
    for r in rows:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue

        p = r.get("nfl_players") or {}
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        is_unknown_pos = (not pos) or (pos in {"UNK", "UNKNOWN", "NULL", "ROOKIE"})

        # If the user filtered for a position, enforce it, but allow unknown positions when stats prove the role.
        if pos_filter:
            if not is_unknown_pos and pos != pos_filter:
                continue
            if is_unknown_pos and pos_filter == "QB":
                # rows are already passing-only; still keep the check explicit.
                pass_yds = _safe_int(r.get("passing_yards")) or 0
                pass_att = _safe_int(r.get("passing_attempts")) or 0
                pass_tds = _safe_int(r.get("passing_touchdowns")) or 0
                if not (pass_yds > 0 or pass_att > 0 or pass_tds > 0):
                    continue

        team_obj = p.get("nfl_teams") or {}
        team_abbr = team_obj.get("abbreviation") or None
        name = (str(p.get("first_name") or "").strip() + " " + str(p.get("last_name") or "").strip()).strip() or str(pid)

        out.append(
            {
                "season": season,
                "team": team_abbr,
                "player_id": str(pid),
                "player_name": name,
                "position": pos or "UNK",
                "passing_attempts": _safe_int(r.get("passing_attempts")) or 0,
                "passing_completions": _safe_int(r.get("passing_completions")) or 0,
                "passing_yards": _safe_int(r.get("passing_yards")) or 0,
                "passing_tds": _safe_int(r.get("passing_touchdowns")) or 0,
                "interceptions": _safe_int(r.get("passing_interceptions")) or 0,
                "photoUrl": player_photo_url_from_name_team(name=name, team=team_abbr),
            }
        )

    out.sort(key=lambda x: int(x.get("passing_yards") or 0), reverse=True)
    return out[: min(max(limit, 1), 200)]


def total_yards_dashboard(
    sb: SupabaseClient,
    *,
    season: int,
    week: int,
    team: Optional[str],
    position: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    # Total yards = rushing + receiving.
    # Default behavior: show skill players (RB/WR/TE). `HB` is treated as `RB`.
    filters: dict[str, Any] = {"season": f"eq.{int(season)}", "week": f"eq.{int(week)}", "postseason": "eq.false"}
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        tid = _safe_int(t[0].get("id")) if t else None
        if tid is not None:
            filters["team_id"] = f"eq.{tid}"
    stats = sb.select(
        "nfl_player_game_stats",
        select="player_id,team_id,season,week,rushing_yards,rushing_touchdowns,receiving_yards,receiving_touchdowns,rushing_attempts,receptions,receiving_targets",
        filters=filters,
        limit=5000,
    )
    # DON'T slice yet - need to filter by position first

    pids = sorted({_safe_int(r.get("player_id")) for r in stats if _safe_int(r.get("player_id")) is not None})
    players = sb.select("nfl_players", select="id,first_name,last_name,position_abbreviation", filters={"id": _in_list(pids)}, limit=len(pids))
    pmap = {int(p["id"]): p for p in players if _safe_int(p.get("id")) is not None}
    team_ids = sorted({_safe_int(r.get("team_id")) for r in stats if _safe_int(r.get("team_id")) is not None})
    tmap = _team_map(sb, [t for t in team_ids if t is not None])

    pos_raw = (position or "").strip().upper()
    if pos_raw in {"", "ALL"}:
        allowed_positions = {"RB", "WR", "TE"}
    elif pos_raw == "HB":
        allowed_positions = {"RB"}
    else:
        allowed_positions = {pos_raw}
    
    # Defensive/special teams positions to exclude (unless user explicitly filters for them)
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}
    
    out = []
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        p = pmap.get(pid, {})
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        
        # Allow NULL/UNK/empty positions if they have yards (already filtered by query)
        # But block defensive/special teams positions unless explicitly requested
        if pos and pos not in allowed_positions:
            # If user filtered for specific position, skip mismatches
            if pos_raw not in {"", "ALL"} or pos in blocked_positions:
                continue
        name = (str(p.get("first_name") or "").strip() + " " + str(p.get("last_name") or "").strip()).strip() or str(pid)
        tid = _safe_int(r.get("team_id"))
        rush_y = _safe_int(r.get("rushing_yards")) or 0
        rec_y = _safe_int(r.get("receiving_yards")) or 0
        rush_td = _safe_int(r.get("rushing_touchdowns")) or 0
        rec_td = _safe_int(r.get("receiving_touchdowns")) or 0
        out.append(
            {
                "season": season,
                "week": week,
                "team": tmap.get(tid) if tid is not None else None,
                "player_id": str(pid),
                "player_name": name,
                "position": pos,
                "rush_yards": rush_y,
                "rec_yards": rec_y,
                "total_yards": rush_y + rec_y,
                "total_tds": rush_td + rec_td,
                "photoUrl": player_photo_url_from_name_team(name=name, team=tmap.get(tid) if tid is not None else None),
            }
        )
    out.sort(key=lambda x: int(x.get("total_yards") or 0), reverse=True)
    return out[: min(max(limit, 1), 200)]


def total_yards_season(
    sb: SupabaseClient,
    *,
    season: int,
    team: Optional[str],
    position: Optional[str],
    q: Optional[str] = None,
    limit: int,
) -> list[dict[str, Any]]:
    # Default behavior: show skill players (RB/WR/TE). `HB` is treated as `RB`.
    pos_raw = (position or "").strip().upper()
    if pos_raw in {"", "ALL"}:
        allowed_positions = {"RB", "WR", "TE"}
    elif pos_raw == "HB":
        allowed_positions = {"RB"}
    else:
        allowed_positions = {pos_raw}

    # Defensive/special teams positions to exclude (unless user explicitly filters for them)
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}

    rows = get_players_list(sb, season=season, position=None, team=team, q=q, limit=8000)
    out: list[dict[str, Any]] = []
    for r in rows:
        pos = (str(r.get("position") or "")).strip().upper()
        # Allow NULL/UNK/empty positions if they have yards
        # Block defensive/special teams positions unless explicitly requested
        if pos and pos not in allowed_positions:
            if pos_raw not in {"", "ALL"} or pos in blocked_positions:
                continue
        rush_y = int(r.get("rushingYards") or 0)
        rec_y = int(r.get("receivingYards") or 0)
        rush_td = int(r.get("rushingTouchdowns") or 0)
        rec_td = int(r.get("receivingTouchdowns") or 0)
        out.append(
            {
                "season": season,
                "team": r.get("team"),
                "player_id": r.get("player_id"),
                "player_name": r.get("player_name"),
                "position": r.get("position"),
                "rush_yards": rush_y,
                "rec_yards": rec_y,
                "total_yards": rush_y + rec_y,
                "total_tds": rush_td + rec_td,
                "photoUrl": player_photo_url_from_name_team(name=str(r.get("player_name") or ""), team=str(r.get("team") or "")),
            }
        )
    out.sort(key=lambda x: int(x.get("total_yards") or 0), reverse=True)
    return out[: min(max(limit, 1), 200)]


