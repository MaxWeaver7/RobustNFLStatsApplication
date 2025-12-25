from __future__ import annotations

import logging
import sqlite3
from typing import Any, Optional

import requests


logger = logging.getLogger(__name__)


def fetch_sleeper_week_stats(
    *,
    season: int,
    week: int,
    session: Optional[requests.Session] = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """
    Fetch Sleeper NFL weekly stats.

    Sleeper endpoint returns a JSON object keyed by Sleeper player_id.
    """
    sess = session or requests.Session()
    url = f"https://api.sleeper.app/v1/stats/nfl/{season}/{week}"
    resp = sess.get(url, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected Sleeper response shape: {type(data)}")
    return data


def ingest_sleeper_fantasy_stats(
    conn: sqlite3.Connection,
    *,
    season: int,
    weeks: list[int],
    session: Optional[requests.Session] = None,
) -> int:
    """
    Best-effort ingestion into `fantasy_stats`.

    This is intentionally optional/off-by-default: it depends on a third-party API.
    Returns: rows written.
    """
    sess = session or requests.Session()
    cur = conn.cursor()
    rows_to_write: list[tuple[str, int, int, Optional[float], Optional[float], Optional[float]]] = []

    for week in weeks:
        try:
            data = fetch_sleeper_week_stats(season=season, week=week, session=sess)
        except Exception as e:
            logger.warning("Sleeper stats fetch failed season=%s week=%s err=%s", season, week, e)
            continue

        for player_id, stats in data.items():
            if not isinstance(player_id, str) or not player_id.strip():
                continue
            if not isinstance(stats, dict):
                continue

            def f(key: str) -> Optional[float]:
                v = stats.get(key)
                if v is None:
                    return None
                try:
                    return float(v)
                except Exception:
                    return None

            rows_to_write.append(
                (
                    player_id,
                    int(season),
                    int(week),
                    f("pts_ppr"),
                    f("pts_half_ppr"),
                    f("pts_std"),
                )
            )

    if not rows_to_write:
        return 0

    cur.executemany(
        """
        INSERT OR REPLACE INTO fantasy_stats(
            player_id, season, week,
            fantasy_points_ppr, fantasy_points_half_ppr, fantasy_points_standard
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows_to_write,
    )
    conn.commit()
    return len(rows_to_write)



