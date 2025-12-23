from __future__ import annotations

import re
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
    # Lazy import to avoid pandas dependency on cold paths if unused.
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return None

    from functools import lru_cache
    from pathlib import Path

    def _clean_id(v: Any) -> Optional[str]:
        s = str(v or "").strip()
        if not s or s.lower() == "nan" or s.lower() == "na":
            return None
        return s

    @lru_cache(maxsize=1)
    def _photo_maps() -> Optional[
        tuple[
            dict[tuple[str, str], tuple[Optional[str], Optional[str]]],
            dict[str, tuple[Optional[str], Optional[str]]],
            dict[tuple[str, str], tuple[Optional[str], Optional[str]]],
            dict[str, tuple[Optional[str], Optional[str]]],
        ]
    ]:
        repo_root = Path(__file__).resolve().parents[2]
        path = repo_root / "data" / "db_playerids.csv"
        if not path.exists():
            return None
        try:
            df = pd.read_csv(path, dtype=str)
        except Exception:
            return None
        if df is None or getattr(df, "empty", False):
            return None
        if "merge_name" not in df.columns:
            return None

        # Normalize and precompute best row per (name, team) and per name.
        if "team" not in df.columns:
            df["team"] = ""
        if "db_season" not in df.columns:
            df["db_season"] = ""
        if "espn_id" not in df.columns:
            df["espn_id"] = ""
        if "sleeper_id" not in df.columns:
            df["sleeper_id"] = ""

        tmp = df[["merge_name", "team", "db_season", "espn_id", "sleeper_id"]].copy()
        tmp["merge_name_norm"] = tmp["merge_name"].fillna("").map(_merge_name)
        tmp = tmp[tmp["merge_name_norm"] != ""]
        tmp["team_norm"] = tmp["team"].fillna("").astype(str).str.upper()
        try:
            tmp["_season"] = pd.to_numeric(tmp["db_season"], errors="coerce").fillna(-1)
        except Exception:
            tmp["_season"] = -1
        tmp = tmp.sort_values("_season", ascending=False)

        by_name_team: dict[tuple[str, str], tuple[Optional[str], Optional[str]]] = {}
        by_name: dict[str, tuple[Optional[str], Optional[str]]] = {}
        by_last_team: dict[tuple[str, str], tuple[Optional[str], Optional[str]]] = {}
        by_last: dict[str, tuple[Optional[str], Optional[str]]] = {}

        # First row encountered per key wins (we sorted newest season first).
        for r in tmp.itertuples(index=False):
            mn = getattr(r, "merge_name_norm")
            tn = getattr(r, "team_norm")
            espn = _clean_id(getattr(r, "espn_id"))
            sleeper = _clean_id(getattr(r, "sleeper_id"))
            if (mn, tn) not in by_name_team:
                by_name_team[(mn, tn)] = (espn, sleeper)
            if mn not in by_name:
                by_name[mn] = (espn, sleeper)
            # last-name fallbacks (helps nicknames like "Hollywood Brown" or "Josh Palmer")
            last = mn.split(" ")[-1] if mn else ""
            if last:
                if (last, tn) not in by_last_team:
                    by_last_team[(last, tn)] = (espn, sleeper)
                if last not in by_last:
                    by_last[last] = (espn, sleeper)

        return by_name_team, by_name, by_last_team, by_last

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


def get_players_list(
    sb: SupabaseClient,
    *,
    season: Optional[int],
    position: Optional[str],
    team: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    # Season stats drive both the displayed totals and the "only players with recorded stats" filter.
    if season is None:
        return []

    # Filter by team abbreviation (best-effort; uses current team on nfl_players).
    team_id: Optional[int] = None
    if team:
        t = sb.select("nfl_teams", select="id", filters={"abbreviation": f"eq.{team}"}, limit=1)
        if t:
            team_id = _safe_int(t[0].get("id"))

    pos_filter = (position or "").strip().upper()
    # Default: offense-only. (Prevents defensive players from ever showing up in the UI.)
    if not pos_filter:
        allowed_positions_default = {"QB", "RB", "WR", "TE"}
    else:
        allowed_positions_default = None
    # Important: PostgREST ordering puts NULLs first unless explicitly handled.
    # If we don't filter out NULL/zero stat rows up front, we can "use up" the limit
    # on empty rows and accidentally exclude real producers (e.g. Stafford).
    stats_filters: dict[str, Any] = {
        "season": f"eq.{int(season)}",
        "postseason": "eq.false",
        # keep only rows with any meaningful production
        "or": (
            "("
            "passing_yards.gt.0,"
            "passing_attempts.gt.0,"
            "passing_touchdowns.gt.0,"
            "rushing_yards.gt.0,"
            "rushing_attempts.gt.0,"
            "rushing_touchdowns.gt.0,"
            "receiving_yards.gt.0,"
            "receptions.gt.0,"
            "receiving_touchdowns.gt.0,"
            "receiving_targets.gt.0"
            ")"
        ),
    }

    stats_select = (
        "player_id,games_played,"
        "passing_attempts,passing_completions,passing_yards,passing_touchdowns,passing_interceptions,"
        "qbr,qb_rating,"
        "rushing_attempts,rushing_yards,rushing_touchdowns,"
        "receptions,receiving_yards,receiving_touchdowns,receiving_targets"
    )

    # Pull season stats and embed nfl_players + nfl_teams in a single query.
    # This avoids huge `id in (...)` URL filters that silently truncate/miss players at scale.
    req_limit = max(int(limit or 0), 1)
    # Safety cap (league size is ~11k players; 20k is plenty).
    req_limit = min(req_limit, 20000)

    stats_rows = sb.select(
        "nfl_player_season_stats",
        select=(
            stats_select
            + ","
            + "nfl_players(first_name,last_name,position_abbreviation,team_id,nfl_teams(abbreviation))"
        ),
        filters=stats_filters,
        # Any stable order is fine since we sort client-side. Avoid ordering by nullable stat cols.
        order="player_id.asc",
        limit=req_limit,
    )

    out: list[dict[str, Any]] = []
    for s in stats_rows:
        if not _has_any_stats(s):
            continue
        p = s.get("nfl_players") or {}
        pos = (p.get("position_abbreviation") or "").strip().upper()
        if allowed_positions_default is not None and pos not in allowed_positions_default:
            continue
        if pos_filter and pos != pos_filter:
            continue

        tid = _safe_int(p.get("team_id"))
        # Team filtering: we only have team_id for the player (current team), so match on that.
        if team_id is not None and tid != team_id:
            continue

        first = (p.get("first_name") or "").strip()
        last = (p.get("last_name") or "").strip()
        pid = _safe_int(s.get("player_id"))
        if pid is None:
            continue
        name = (first + " " + last).strip() or str(pid)
        t = p.get("nfl_teams") or {}
        team_abbr = (t.get("abbreviation") or None)

        games = _safe_int(s.get("games_played")) or 0
        targets = _safe_int(s.get("receiving_targets")) or 0
        rec = _safe_int(s.get("receptions")) or 0
        rec_yards = _safe_int(s.get("receiving_yards")) or 0
        rec_tds = _safe_int(s.get("receiving_touchdowns")) or 0
        rush_att = _safe_int(s.get("rushing_attempts")) or 0
        rush_yards = _safe_int(s.get("rushing_yards")) or 0
        rush_tds = _safe_int(s.get("rushing_touchdowns")) or 0
        pass_att = _safe_int(s.get("passing_attempts")) or 0
        pass_cmp = _safe_int(s.get("passing_completions")) or 0
        pass_yds = _safe_int(s.get("passing_yards")) or 0
        pass_tds = _safe_int(s.get("passing_touchdowns")) or 0
        pass_int = _safe_int(s.get("passing_interceptions")) or 0
        qb_rating = _safe_float(s.get("qb_rating"))
        qbr = _safe_float(s.get("qbr"))

        avg_ypc = (float(rec_yards) / float(rec)) if rec else 0.0
        avg_ypr = (float(rush_yards) / float(rush_att)) if rush_att else 0.0
        photo = player_photo_url_from_name_team(name=name, team=team_abbr)

        out.append(
            {
                "player_id": str(pid),
                "player_name": name,
                "team": team_abbr,
                "position": pos or None,
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

    # Sort: receivers by receiving yards, rushers/QBs by rushing yards (simple, UX-friendly).
    def sort_key(r: dict[str, Any]) -> int:
        pos = (r.get("position") or "").upper()
        if pos == "QB":
            return int(r.get("passingYards") or 0)
        if pos in {"WR", "TE"}:
            return int(r.get("receivingYards") or 0)
        return int(r.get("rushingYards") or 0)

    out.sort(key=sort_key, reverse=True)
    return out[: min(max(int(limit or 0), 1), len(out))]


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

    out = []
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        p = r.get("nfl_players") or {}
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        if (pos or "") not in allowed_positions:
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

    out = []
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        p = r.get("nfl_players") or {}
        name = (str(p.get("first_name") or "").strip() + " " + str(p.get("last_name") or "").strip()).strip() or str(pid)
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        if (pos or "") not in allowed_positions:
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
    return out


def receiving_season(
    sb: SupabaseClient,
    *,
    season: int,
    team: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    # Use season stats; team is best-effort (current team).
    rows = get_players_list(sb, season=season, position=None, team=team, limit=8000)
    # compute team target share within returned team scope
    by_team: dict[str, int] = {}
    for r in rows:
        t = r.get("team") or ""
        by_team[t] = by_team.get(t, 0) + int(r.get("targets") or 0)
    out = []
    for r in rows:
        pos = (r.get("position") or "").upper()
        if pos not in {"WR", "TE", "RB"}:
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
    limit: int,
) -> list[dict[str, Any]]:
    pos_raw = (position or "").strip().upper()
    pos_filter = None if pos_raw in {"", "ALL"} else ("RB" if pos_raw == "HB" else pos_raw)

    rows = get_players_list(sb, season=season, position=pos_filter, team=team, limit=8000)
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
    stats.sort(key=lambda r: _safe_int(r.get("passing_yards")) or 0, reverse=True)
    stats = stats[: min(max(limit, 1), 200)]

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
    out = []
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        p = pmap.get(pid, {})
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        if (pos or "") not in allowed_positions:
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
    return out[: min(max(limit, 1), 200)]


def passing_season(
    sb: SupabaseClient,
    *,
    season: int,
    team: Optional[str],
    position: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    # Passing is overwhelmingly QB; allow override.
    pos_filter = (position or "QB").strip().upper()
    rows = get_players_list(sb, season=season, position=pos_filter, team=team, limit=8000)
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "season": season,
                "team": r.get("team"),
                "player_id": r.get("player_id"),
                "player_name": r.get("player_name"),
                "position": r.get("position"),
                "passing_attempts": int(r.get("passingAttempts") or 0),
                "passing_completions": int(r.get("passingCompletions") or 0),
                "passing_yards": int(r.get("passingYards") or 0),
                "passing_tds": int(r.get("passingTouchdowns") or 0),
                "interceptions": int(r.get("passingInterceptions") or 0),
                "photoUrl": player_photo_url_from_name_team(name=str(r.get("player_name") or ""), team=str(r.get("team") or "")),
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
    stats.sort(key=lambda r: (_safe_int(r.get("rushing_yards")) or 0) + (_safe_int(r.get("receiving_yards")) or 0), reverse=True)
    stats = stats[: min(max(limit, 1), 200)]

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
    out = []
    for r in stats:
        pid = _safe_int(r.get("player_id"))
        if pid is None:
            continue
        p = pmap.get(pid, {})
        pos = (p.get("position_abbreviation") or "").strip().upper() or None
        if pos is None or pos.upper() not in allowed_positions:
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

    rows = get_players_list(sb, season=season, position=None, team=team, limit=8000)
    out: list[dict[str, Any]] = []
    for r in rows:
        pos = (str(r.get("position") or "")).strip().upper()
        if pos not in allowed_positions:
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


