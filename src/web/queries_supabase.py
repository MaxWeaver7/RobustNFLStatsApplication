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
    Get players list by aggregating from WEEKLY game stats using 3 separate focused queries.
    Uses the same efficient pattern as the season leaderboards (passing_season, rushing_season, receiving_season).
    This ensures ALL players appear, including rookies like Drake Maye & Bo Nix.
    """
    if season is None:
        return []
    
    # Base filters
    base_filters = {
        "season": f"eq.{int(season)}",
        "postseason": "eq.false",
    }
    
    # Team filter
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        if t:
            tid = _safe_int(t[0].get("id"))
            if tid:
                base_filters["team_id"] = f"eq.{tid}"
    
    # Fetch passing stats (like passing_season does)
    passing_filters = {**base_filters, "or": "(passing_yards.gt.0,passing_attempts.gt.0,passing_touchdowns.gt.0)"}
    passing_stats = sb.select(
        "nfl_player_game_stats",
        select="player_id,team_id,passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions",
        filters=passing_filters,
        limit=12000,
    )
    
    # Fetch rushing stats (like rushing_season does)
    rushing_filters = {**base_filters, "or": "(rushing_yards.gt.0,rushing_attempts.gt.0,rushing_touchdowns.gt.0)"}
    rushing_stats = sb.select(
        "nfl_player_game_stats",
        select="player_id,team_id,rushing_attempts,rushing_yards,rushing_touchdowns",
        filters=rushing_filters,
        limit=12000,
    )
    
    # Fetch receiving stats (like receiving_season does)
    receiving_filters = {**base_filters, "or": "(receiving_yards.gt.0,receptions.gt.0,receiving_targets.gt.0)"}
    receiving_stats = sb.select(
        "nfl_player_game_stats",
        select="player_id,team_id,receiving_targets,receptions,receiving_yards,receiving_touchdowns",
        filters=receiving_filters,
        limit=12000,
    )
    
    # Aggregate by player_id across all 3 stat types
    player_totals: dict[int, dict[str, Any]] = {}
    
    # Aggregate passing stats
    for r in passing_stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        if pid not in player_totals:
            player_totals[pid] = {
                "team_id": _safe_int(r.get("team_id")),
                "passing_attempts": 0,
                "passing_completions": 0,
                "passing_yards": 0,
                "passing_tds": 0,
                "passing_ints": 0,
                "rushing_attempts": 0,
                "rushing_yards": 0,
                "rushing_tds": 0,
                "targets": 0,
                "receptions": 0,
                "rec_yards": 0,
                "rec_tds": 0,
            }
        player_totals[pid]["passing_attempts"] += _safe_int(r.get("passing_attempts")) or 0
        player_totals[pid]["passing_completions"] += _safe_int(r.get("passing_completions")) or 0
        player_totals[pid]["passing_yards"] += _safe_int(r.get("passing_yards")) or 0
        player_totals[pid]["passing_tds"] += _safe_int(r.get("passing_touchdowns")) or 0
        player_totals[pid]["passing_ints"] += _safe_int(r.get("passing_interceptions")) or 0
    
    # Aggregate rushing stats
    for r in rushing_stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        if pid not in player_totals:
            player_totals[pid] = {
                "team_id": _safe_int(r.get("team_id")),
                "passing_attempts": 0,
                "passing_completions": 0,
                "passing_yards": 0,
                "passing_tds": 0,
                "passing_ints": 0,
                "rushing_attempts": 0,
                "rushing_yards": 0,
                "rushing_tds": 0,
                "targets": 0,
                "receptions": 0,
                "rec_yards": 0,
                "rec_tds": 0,
            }
        player_totals[pid]["rushing_attempts"] += _safe_int(r.get("rushing_attempts")) or 0
        player_totals[pid]["rushing_yards"] += _safe_int(r.get("rushing_yards")) or 0
        player_totals[pid]["rushing_tds"] += _safe_int(r.get("rushing_touchdowns")) or 0
    
    # Aggregate receiving stats
    for r in receiving_stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        if pid not in player_totals:
            player_totals[pid] = {
                "team_id": _safe_int(r.get("team_id")),
                "passing_attempts": 0,
                "passing_completions": 0,
                "passing_yards": 0,
                "passing_tds": 0,
                "passing_ints": 0,
                "rushing_attempts": 0,
                "rushing_yards": 0,
                "rushing_tds": 0,
                "targets": 0,
                "receptions": 0,
                "rec_yards": 0,
                "rec_tds": 0,
            }
        player_totals[pid]["targets"] += _safe_int(r.get("receiving_targets")) or 0
        player_totals[pid]["receptions"] += _safe_int(r.get("receptions")) or 0
        player_totals[pid]["rec_yards"] += _safe_int(r.get("receiving_yards")) or 0
        player_totals[pid]["rec_tds"] += _safe_int(r.get("receiving_touchdowns")) or 0
    
    # Fetch player names and positions
    pids = sorted(player_totals.keys())
    if not pids:
        return []
    
    players = sb.select("nfl_players", select="id,first_name,last_name,position_abbreviation,team_id", filters={"id": _in_list(pids)}, limit=len(pids))
    pmap = {int(p["id"]): p for p in players if _safe_int(p.get("id")) is not None}
    
    # Fetch team abbreviations
    team_ids = sorted({pt["team_id"] for pt in player_totals.values() if pt["team_id"] is not None})
    tmap = _team_map(sb, [t for t in team_ids if t is not None])
    
    # Position filtering
    pos_filter = (position or "").strip().upper()
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}
    
    # Name search filter
    needle = _sanitize_search(q)
    
    # Build output
    out = []
    for pid, totals in player_totals.items():
        p = pmap.get(pid, {})
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        
        # Position filtering
        if pos and pos in blocked_positions:
            continue
        if pos_filter and pos and pos != pos_filter:
            continue
        
        # Name search filtering
        first = (p.get("first_name") or "").strip()
        last = (p.get("last_name") or "").strip()
        name = (first + " " + last).strip() or str(pid)
        if needle:
            if needle.lower() not in name.lower():
                continue
        
        tid = totals["team_id"]
        team_abbr = tmap.get(tid) if tid is not None else None
        
        # Calculate derived stats
        rec = totals["receptions"]
        rec_yards = totals["rec_yards"]
        rush_att = totals["rushing_attempts"]
        rush_yards = totals["rushing_yards"]
        avg_ypc = (float(rec_yards) / float(rec)) if rec else 0.0
        avg_ypr = (float(rush_yards) / float(rush_att)) if rush_att else 0.0
        
        # Calculate games played (estimate based on max category with activity)
        games = 0
        if totals["passing_attempts"] > 0:
            games = max(games, 1)  # Simple estimation - not perfect but close enough
        if totals["rushing_attempts"] > 0:
            games = max(games, 1)
        if totals["receptions"] > 0:
            games = max(games, 1)
        
        out.append(
            {
                "player_id": str(pid),
                "player_name": name,
                "team": team_abbr,
                "position": pos or "UNK",
                "season": season,
                "games": games,  # Approximation
                "targets": totals["targets"],
                "receptions": rec,
                "receivingYards": rec_yards,
                "receivingTouchdowns": totals["rec_tds"],
                "avgYardsPerCatch": avg_ypc,
                "rushAttempts": rush_att,
                "rushingYards": rush_yards,
                "rushingTouchdowns": totals["rushing_tds"],
                "avgYardsPerRush": avg_ypr,
                "passingAttempts": totals["passing_attempts"],
                "passingCompletions": totals["passing_completions"],
                "passingYards": totals["passing_yards"],
                "passingTouchdowns": totals["passing_tds"],
                "passingInterceptions": totals["passing_ints"],
                "qbRating": None,  # Not calculated from weekly aggregation
                "qbr": None,  # Not calculated from weekly aggregation
                "photoUrl": player_photo_url_from_name_team(name=name, team=team_abbr),
            }
        )
    
    # Position-aware sorting: QBs by passing yards, everyone else by total production
    def sort_key(r: dict[str, Any]) -> int:
        pos = (r.get("position") or "").strip().upper()
        if pos == "QB":
            return int(r.get("passingYards") or 0)
        else:
            return (
                int(r.get("passingYards") or 0) +
                int(r.get("rushingYards") or 0) +
                int(r.get("receivingYards") or 0)
            )
    
    out.sort(key=sort_key, reverse=True)
    
    # Apply offset and limit
    start = max(int(offset or 0), 0)
    end = start + max(int(limit or 250), 1)
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
    limit: int,
) -> list[dict[str, Any]]:
    """
    Aggregate receiving stats from weekly game logs for the season.
    This ensures we include ALL players with receiving stats, including rookies.
    """
    # Build filters for weekly stats
    filters: dict[str, Any] = {
        "season": f"eq.{int(season)}",
        "postseason": "eq.false",
        "or": "(receiving_yards.gt.0,receptions.gt.0,receiving_targets.gt.0)",
    }
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        tid = _safe_int(t[0].get("id")) if t else None
        if tid is not None:
            filters["team_id"] = f"eq.{tid}"
    
    # Fetch ALL weekly receiving stats for the season
    stats = sb.select(
        "nfl_player_game_stats",
        select="player_id,team_id,receiving_targets,receptions,receiving_yards,receiving_touchdowns",
        filters=filters,
        limit=12000,
    )
    
    # Aggregate by player_id
    player_totals: dict[int, dict[str, int]] = {}
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        if pid not in player_totals:
            player_totals[pid] = {
                "team_id": _safe_int(r.get("team_id")),
                "targets": 0,
                "receptions": 0,
                "rec_yards": 0,
                "rec_tds": 0,
            }
        player_totals[pid]["targets"] += _safe_int(r.get("receiving_targets")) or 0
        player_totals[pid]["receptions"] += _safe_int(r.get("receptions")) or 0
        player_totals[pid]["rec_yards"] += _safe_int(r.get("receiving_yards")) or 0
        player_totals[pid]["rec_tds"] += _safe_int(r.get("receiving_touchdowns")) or 0
    
    # Fetch player names and positions
    pids = sorted(player_totals.keys())
    players = sb.select("nfl_players", select="id,first_name,last_name,position_abbreviation", filters={"id": _in_list(pids)}, limit=len(pids))
    pmap = {int(p["id"]): p for p in players if _safe_int(p.get("id")) is not None}
    
    # Fetch team abbreviations
    team_ids = sorted({pt["team_id"] for pt in player_totals.values() if pt["team_id"] is not None})
    tmap = _team_map(sb, [t for t in team_ids if t is not None])
    
    # Compute team target shares
    by_team: dict[str, int] = {}
    for pid, totals in player_totals.items():
        tid = totals["team_id"]
        team_abbr = tmap.get(tid) if tid is not None else ""
        by_team[team_abbr] = by_team.get(team_abbr, 0) + totals["targets"]
    
    # Position filtering
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}
    
    # Build output
    out = []
    for pid, totals in player_totals.items():
        p = pmap.get(pid, {})
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        
        # Allow NULL/UNK/empty positions if they have receiving stats
        # Block defensive/special teams positions
        if pos and pos not in {"WR", "TE", "RB"}:
            if pos in blocked_positions:
                continue
        
        name = (str(p.get("first_name") or "").strip() + " " + str(p.get("last_name") or "").strip()).strip() or str(pid)
        tid = totals["team_id"]
        team_abbr = tmap.get(tid) if tid is not None else ""
        denom = by_team.get(team_abbr, 0) or 0
        share = (float(totals["targets"]) / float(denom)) if denom else None
        
        out.append(
            {
                "season": season,
                "team": team_abbr or None,
                "player_id": str(pid),
                "player_name": name,
                "position": pos or "UNK",
                "targets": totals["targets"],
                "receptions": totals["receptions"],
                "rec_yards": totals["rec_yards"],
                "air_yards": 0,
                "rec_tds": totals["rec_tds"],
                "team_target_share": share,
                "photoUrl": player_photo_url_from_name_team(name=name, team=team_abbr or None),
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
    limit: int,
) -> list[dict[str, Any]]:
    """
    Aggregate rushing stats from weekly game logs for the season.
    This ensures we include ALL players with rushing stats, including rookies.
    """
    # Build filters for weekly stats
    filters: dict[str, Any] = {
        "season": f"eq.{int(season)}",
        "postseason": "eq.false",
        "or": "(rushing_yards.gt.0,rushing_attempts.gt.0,rushing_touchdowns.gt.0)",
    }
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        tid = _safe_int(t[0].get("id")) if t else None
        if tid is not None:
            filters["team_id"] = f"eq.{tid}"
    
    # Fetch ALL weekly rushing stats for the season
    stats = sb.select(
        "nfl_player_game_stats",
        select="player_id,team_id,rushing_attempts,rushing_yards,rushing_touchdowns,receptions,receiving_yards",
        filters=filters,
        limit=12000,
    )
    
    # Aggregate by player_id and count games
    player_totals: dict[int, dict[str, int]] = {}
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        if pid not in player_totals:
            player_totals[pid] = {
                "team_id": _safe_int(r.get("team_id")),
                "games": 0,
                "rush_attempts": 0,
                "rush_yards": 0,
                "rush_tds": 0,
                "receptions": 0,
                "rec_yards": 0,
            }
        player_totals[pid]["games"] += 1  # Count games played
        player_totals[pid]["rush_attempts"] += _safe_int(r.get("rushing_attempts")) or 0
        player_totals[pid]["rush_yards"] += _safe_int(r.get("rushing_yards")) or 0
        player_totals[pid]["rush_tds"] += _safe_int(r.get("rushing_touchdowns")) or 0
        player_totals[pid]["receptions"] += _safe_int(r.get("receptions")) or 0
        player_totals[pid]["rec_yards"] += _safe_int(r.get("receiving_yards")) or 0
    
    # Fetch player names and positions
    pids = sorted(player_totals.keys())
    players = sb.select("nfl_players", select="id,first_name,last_name,position_abbreviation", filters={"id": _in_list(pids)}, limit=len(pids))
    pmap = {int(p["id"]): p for p in players if _safe_int(p.get("id")) is not None}
    
    # Fetch team abbreviations
    team_ids = sorted({pt["team_id"] for pt in player_totals.values() if pt["team_id"] is not None})
    tmap = _team_map(sb, [t for t in team_ids if t is not None])
    
    # Compute team rush shares
    by_team: dict[str, int] = {}
    for pid, totals in player_totals.items():
        tid = totals["team_id"]
        team_abbr = tmap.get(tid) if tid is not None else ""
        by_team[team_abbr] = by_team.get(team_abbr, 0) + totals["rush_attempts"]
    
    # Position filtering
    pos_raw = (position or "").strip().upper()
    pos_filter = None if pos_raw in {"", "ALL"} else ("RB" if pos_raw == "HB" else pos_raw)
    
    # Build output
    out = []
    for pid, totals in player_totals.items():
        p = pmap.get(pid, {})
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        
        # Position filtering
        if pos_filter and pos and pos != pos_filter:
            continue
        
        name = (str(p.get("first_name") or "").strip() + " " + str(p.get("last_name") or "").strip()).strip() or str(pid)
        tid = totals["team_id"]
        team_abbr = tmap.get(tid) if tid is not None else ""
        denom = by_team.get(team_abbr, 0) or 0
        share = (float(totals["rush_attempts"]) / float(denom)) if denom else None
        
        games = totals["games"]
        rush_att = totals["rush_attempts"]
        rush_y = totals["rush_yards"]
        rec = totals["receptions"]
        rec_y = totals["rec_yards"]
        
        out.append(
            {
                "season": season,
                "team": team_abbr or None,
                "player_id": str(pid),
                "player_name": name,
                "position": pos or "UNK",
                "games": games,
                "rush_attempts": rush_att,
                "rush_yards": rush_y,
                "rush_tds": totals["rush_tds"],
                "ypc": (float(rush_y) / float(rush_att)) if rush_att else 0.0,
                "ypg": (float(rush_y) / float(games)) if games else 0.0,
                "receptions": rec,
                "rpg": (float(rec) / float(games)) if games else 0.0,
                "rec_yards": rec_y,
                "rec_ypg": (float(rec_y) / float(games)) if games else 0.0,
                "team_rush_share": share,
                "photoUrl": player_photo_url_from_name_team(name=name, team=team_abbr or None),
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
    limit: int,
) -> list[dict[str, Any]]:
    """
    Aggregate passing stats from weekly game logs for the season.
    This ensures we include ALL players with passing stats, including rookies.
    """
    # Build filters for weekly stats
    filters: dict[str, Any] = {
        "season": f"eq.{int(season)}",
        "postseason": "eq.false",
        "or": "(passing_yards.gt.0,passing_attempts.gt.0,passing_touchdowns.gt.0)",
    }
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        tid = _safe_int(t[0].get("id")) if t else None
        if tid is not None:
            filters["team_id"] = f"eq.{tid}"
    
    # Fetch ALL weekly passing stats for the season (increased limit for full season)
    stats = sb.select(
        "nfl_player_game_stats",
        select="player_id,team_id,passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions",
        filters=filters,
        limit=12000,  # Increased to ensure we get all players
    )
    
    # Aggregate by player_id
    player_totals: dict[int, dict[str, int]] = {}
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        if pid not in player_totals:
            player_totals[pid] = {
                "team_id": _safe_int(r.get("team_id")),
                "passing_attempts": 0,
                "passing_completions": 0,
                "passing_yards": 0,
                "passing_tds": 0,
                "interceptions": 0,
            }
        player_totals[pid]["passing_attempts"] += _safe_int(r.get("passing_attempts")) or 0
        player_totals[pid]["passing_completions"] += _safe_int(r.get("passing_completions")) or 0
        player_totals[pid]["passing_yards"] += _safe_int(r.get("passing_yards")) or 0
        player_totals[pid]["passing_tds"] += _safe_int(r.get("passing_touchdowns")) or 0
        player_totals[pid]["interceptions"] += _safe_int(r.get("passing_interceptions")) or 0
    
    # Fetch player names and positions
    pids = sorted(player_totals.keys())
    players = sb.select("nfl_players", select="id,first_name,last_name,position_abbreviation", filters={"id": _in_list(pids)}, limit=len(pids))
    pmap = {int(p["id"]): p for p in players if _safe_int(p.get("id")) is not None}
    
    # Fetch team abbreviations
    team_ids = sorted({pt["team_id"] for pt in player_totals.values() if pt["team_id"] is not None})
    tmap = _team_map(sb, [t for t in team_ids if t is not None])
    
    # Position filtering
    pos_raw = (position or "QB").strip().upper()
    if pos_raw in {"", "ALL"}:
        allowed_positions = {"QB"}
    else:
        allowed_positions = {pos_raw}
    blocked_positions = {"DB", "CB", "S", "SS", "FS", "LB", "ILB", "OLB", "DL", "DE", "DT", "NT", "OL", "OT", "OG", "C", "K", "P", "LS"}
    
    # Build output
    out = []
    for pid, totals in player_totals.items():
        p = pmap.get(pid, {})
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        
        # Allow NULL/UNK/empty positions if they have passing stats
        # But block defensive/special teams positions unless explicitly requested
        if pos and pos not in allowed_positions:
            if pos_raw not in {"", "ALL"} or pos in blocked_positions:
                continue
        
        name = (str(p.get("first_name") or "").strip() + " " + str(p.get("last_name") or "").strip()).strip() or str(pid)
        tid = totals["team_id"]
        out.append(
            {
                "season": season,
                "team": tmap.get(tid) if tid is not None else None,
                "player_id": str(pid),
                "player_name": name,
                "position": pos or "UNK",
                "passing_attempts": totals["passing_attempts"],
                "passing_completions": totals["passing_completions"],
                "passing_yards": totals["passing_yards"],
                "passing_tds": totals["passing_tds"],
                "interceptions": totals["interceptions"],
                "photoUrl": player_photo_url_from_name_team(name=name, team=tmap.get(tid) if tid is not None else None),
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

    rows = get_players_list(sb, season=season, position=None, team=team, limit=8000)
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


