-- Run this ONCE in Supabase SQL Editor if you previously applied an older schema_core.sql
-- that created the unique index uq_nfl_games_season_week_teams.
--
-- This index can block ingestion because the upstream API may emit duplicates (different IDs)
-- for the same season/week matchup.

drop index if exists public.uq_nfl_games_season_week_teams;


