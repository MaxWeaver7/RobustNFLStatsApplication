# Performance + Scalability Notes (Supabase + React)

This doc explains **why the app was slow**, what was changed to make it fast, and the **patterns to reuse** when integrating future **advanced stats** tables (`nfl_advanced_passing_stats`, `nfl_advanced_receiving_stats`, `nfl_advanced_rushing_stats`).

## Symptoms
- Initial page load is OK, but the **Players list takes a long time to appear**.
- Typing into search appears to “work instantly” and then shows a **loading flash**.

## Root causes (what was actually slow)
### 1) Pulling/rendering too many players
Fetching thousands of players and rendering huge lists is expensive for:
- Network payload size
- JSON parsing
- React render cost

**Fix**: page the Players list and optionally do **server-side search**.

### 2) Headshot URL mapping was recomputed per request
`player_photo_url_from_name_team()` uses `data/db_playerids.csv` to map player name/team → ESPN/Sleeper IDs.

If the mapping CSV is loaded/parsing work happens **per request**, `/api/players` becomes slow even if Supabase is fast.

**Fix**: load/parse `db_playerids.csv` once per process (module-level cache).

## What we changed (high-level)
### Backend
- `/api/players` supports:
  - **DB-side “has stats” filtering** (no LIMIT-before-filter bug)
  - **server-side name search** via `q=`
  - **pagination** via `offset=` + `limit=`
- Headshot lookup maps are cached process-wide (so `/api/players` doesn’t stall doing file work).

### Frontend
- Players list is fetched in **pages** (default 250).
- Search only triggers server-side filtering at **2+ characters**.
- Uses React Query `keepPreviousData` to avoid “flash to loading/empty” UX.

## Supabase index guidance
Run:
- `supabase/add_perf_indexes.sql`

If the Players endpoint is still slow, consider adding a **partial index** for “has any stat” rows in `nfl_player_season_stats`, because the `or=(...gt.0...)` filter can otherwise scan more rows than needed.

## Advanced stats integration plan (how to extend safely)
The repo already defines tables in `supabase/schema_stats.sql`:
- `nfl_advanced_receiving_stats`
- `nfl_advanced_rushing_stats`
- `nfl_advanced_passing_stats`

### Pattern to follow (do this, don’t break the UI)
1. **Keep existing JSON shape stable**
   - Add new fields under a new object key (e.g. `advanced`), or create new endpoints.
2. **Filter at the DB level**
   - Always filter out null/zero rows in PostgREST (avoid limit-before-filter).
3. **Join/Embed, don’t N+1**
   - Prefer a single PostgREST call with embedding when possible, or a small number of calls with `id in (...)`.
4. **Never “LIMIT to make it fast” without validating required fields**
   - If limiting, apply it *after* DB-side filters that enforce “real stat rows”.

### Suggested endpoints
- `GET /api/advanced_receiving?season=&week=&team=&position=&limit=`
- `GET /api/advanced_rushing?...`
- `GET /api/advanced_passing?...`

Each endpoint should:
- Query the corresponding `nfl_advanced_*` table
- Apply `season/week/postseason` filters
- Apply DB-side `or=(...)` for meaningful rows
- Embed `nfl_players(...)` + `nfl_teams(abbreviation)` for display fields

### Suggested indexes for advanced tables
The schema already includes:
- `(season, week, postseason)` btree indexes

If you add “top N” leaderboards ordered by a metric, add composite indexes that match your filters + sort:
- `(season, week, postseason, yards desc)` for receiving
- `(season, week, postseason, rush_yards desc)` for rushing
- `(season, week, postseason, pass_yards desc)` for passing



