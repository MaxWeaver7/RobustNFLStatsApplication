## NFLAdvancedStats — Supabase + BALLDONTLIE NFL (with React UI)

This repo contains:
- A **React UI** served by the Python server at `http://127.0.0.1:8003/`
- A **Supabase (Postgres) schema + ingestion pipeline** that loads NFL data from the **BALLDONTLIE NFL API**
- A legacy local **SQLite + nflfastR** ingestion path (optional fallback)

### Setup

Create a virtualenv, install deps, and set environment variables:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp config/env.example .env  # optional (if your env supports dotfiles)
```

### Supabase + BALLDONTLIE (recommended)

1) **Create tables in Supabase**

Open Supabase Dashboard → SQL Editor, and run:
- `supabase/schema_core.sql`
- `supabase/schema_stats.sql`

Optional (recommended for speed if Players/Leaderboards feel slow):
- `supabase/add_perf_indexes.sql`

If you ran an older schema that created a strict unique index on games, run once:
- `supabase/drop_uq_nfl_games_season_week_teams.sql`

### AI handoff / project context
- `docs/AI_HANDOFF.md`

2) **Set env vars** in `.env`:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (server-side only)
- `BALLDONTLIE_API_KEY`

3) **Ingest**:

```bash
python3 main.py
```

Optional:
- `BDL_INCLUDE_ADVANCED=1` to attempt GOAT advanced endpoints (may be unstable at times).
- `BDL_ADVANCED_ONLY=1` to run advanced-only (skips core + season/game stats).

### Run the web app

If you have already built the frontend to `dist/`, run:

```bash
python3 -m src.web.server --host 127.0.0.1 --port 8003
```

To rebuild the frontend:

```bash
npm install
npm run build
```

### Legacy (SQLite + nflfastR)
If Supabase vars are not set, `main.py` falls back to ingesting nflfastR → SQLite.

```bash
python3 main.py
```

### Tests

```bash
pytest
```

### Notes

- The PFR scraper is **best-effort** and will **never fabricate data**. If `games.pfr_boxscore_url` is empty, scraping is skipped.


