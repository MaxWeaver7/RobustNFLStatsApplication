from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path


logger = logging.getLogger(__name__)


def ingest_coordinators(conn: sqlite3.Connection, *, csv_path: str) -> int:
    """
    Load a small coordinators CSV into the `coordinators` table.

    Expected columns:
      - team_abbr
      - season
      - offensive_coordinator
      - defensive_coordinator
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Coordinators CSV not found: {path}")

    rows: list[tuple[str, int, str | None, str | None]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            team = (r.get("team_abbr") or "").strip().upper()
            season_raw = (r.get("season") or "").strip()
            if not team or not season_raw.isdigit():
                continue
            oc = (r.get("offensive_coordinator") or "").strip() or None
            dc = (r.get("defensive_coordinator") or "").strip() or None
            rows.append((team, int(season_raw), oc, dc))

    if not rows:
        return 0

    cur = conn.cursor()
    cur.executemany("INSERT OR IGNORE INTO teams(team_abbr) VALUES (?)", [(t,) for t, _, __, ___ in rows])
    cur.executemany(
        """
        INSERT OR REPLACE INTO coordinators(team_abbr, season, offensive_coordinator, defensive_coordinator)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    logger.info("Ingested coordinators rows=%d from %s", len(rows), path)
    return len(rows)



