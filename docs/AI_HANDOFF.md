# AI Handoff: NFLAdvancedStats (Supabase + React)

This doc is a **handoff/context pack** for another AI (or human) so it can work effectively without repeating past mistakes.

## What this app is
- **Frontend**: React + Vite (Tailwind) in `frontend/`
- **Backend**: Python `http.server` in `src/web/server.py`
- **DB**: Supabase Postgres (primary) with a legacy SQLite fallback

## How to run (dev)
- Backend:
  - `python3 -m src.web.server --db ../data/nfl_data.db --host 127.0.0.1 --port 8000`
  - Uses Supabase when `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are present.
- Frontend:
  - `npm install`
  - `npm run dev -- --host 127.0.0.1 --port 5173`

## Critical API endpoints
Backend routes live in `src/web/server.py` and use `src/web/queries_supabase.py` when Supabase is configured.

- `GET /api/options`
- `GET /api/players?season=&position=&team=&limit=`
- `GET /api/player/:id?season=&include_postseason=`
- `GET /api/receiving_dashboard?season=&week=&team=&position=&limit=`
- `GET /api/rushing_dashboard?season=&week=&team=&position=&limit=`
- `GET /api/passing_dashboard?season=&week=&team=&position=&limit=`
- Season leaderboards:
  - `/api/receiving_season`
  - `/api/rushing_season`
  - `/api/passing_season`
  - `/api/total_yards_season`

## The big gotcha we hit (and fixed)
### PostgREST + NULL ordering can silently “hide” real players
Supabase’s PostgREST ordering can return **NULL-heavy rows first** depending on `order=` and column nullability.
If you apply a **limit before filtering**, you can accidentally exclude real producers (e.g., QBs like Stafford).

**Fix pattern used in this repo**:
- Filter at the DB level using PostgREST `or=(...)` so only “real stat” rows are returned.
- Avoid ordering by nullable stat columns unless you’re sure they’re non-null for the cohort.

See `get_players_list()` in `src/web/queries_supabase.py`.

## Headshots (player images)
Backend generates headshot URLs using `data/db_playerids.csv` (dynastyprocess mapping).
- Function: `player_photo_url_from_name_team()` in `src/web/queries_supabase.py`
- Handles:
  - `Jr/Sr/III` suffixes
  - nickname/short-name fallbacks (last-name + team)
  - team abbreviation normalization (ESPN-style ↔ mapping file codes)

Tests: `tests/test_player_photos.py`

## Team logos
Frontend component: `frontend/src/components/TeamLogo.tsx`
- Supports both nflfastR-style and ESPN-style abbreviations (e.g. `KC` + `KCC`).

## Performance standards / approach
The performance bottleneck is usually **DB sorting + network** and **rendering huge lists**.

Current approach:
- Keep leaderboards `limit` small (e.g. 50) but ensure DB-side filters don’t return NULL rows.
- For Players list: either paginate/virtualize, or use server-side search.

Optional DB indexes:
- `supabase/add_perf_indexes.sql` adds composite indexes for the common filter + sort patterns.

## Testing
- `pytest -q`
- For regressions, run:
  - `pytest tests/test_supabase_stats_queries.py -q`
  - `pytest tests/test_player_photos.py -q`

## “If you change X, test Y”
- If you touch `/api/players` logic: test `curl /api/players?...` and confirm Stafford/QBs are present.
- If you touch weekly leaderboards: confirm targets/yards are non-zero for Week 1.
- Always restart the backend; it does **not** hot-reload.


