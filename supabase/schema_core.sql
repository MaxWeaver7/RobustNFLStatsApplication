-- Supabase Postgres schema for BALLDONTLIE NFL API (Phase 1: core entities)
--
-- Apply this in Supabase:
--   Supabase Dashboard -> SQL Editor -> New query -> paste/run this file.
--
-- Notes:
-- - We keep this minimal and ingestion-friendly.
-- - RLS is left OFF by default for simplicity because the app uses server-side service-role access.

begin;

create table if not exists public.nfl_teams (
  id bigint primary key,
  conference text,
  division text,
  location text,
  name text,
  full_name text,
  abbreviation text not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.nfl_players (
  id bigint primary key,
  first_name text,
  last_name text,
  position text,
  position_abbreviation text,
  height text,
  weight text,
  jersey_number text,
  college text,
  experience text,
  age integer,
  team_id bigint references public.nfl_teams(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_nfl_players_team_id on public.nfl_players(team_id);
create index if not exists idx_nfl_players_last_name on public.nfl_players(last_name);

create table if not exists public.nfl_games (
  id bigint primary key,
  season integer not null,
  week integer not null,
  date timestamptz,
  postseason boolean not null default false,
  status text,
  venue text,
  summary text,

  home_team_id bigint references public.nfl_teams(id) on delete set null,
  visitor_team_id bigint references public.nfl_teams(id) on delete set null,

  home_team_score integer,
  home_team_q1 integer,
  home_team_q2 integer,
  home_team_q3 integer,
  home_team_q4 integer,
  home_team_ot integer,

  visitor_team_score integer,
  visitor_team_q1 integer,
  visitor_team_q2 integer,
  visitor_team_q3 integer,
  visitor_team_q4 integer,
  visitor_team_ot integer,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Prevent obvious duplicates even if upstream IDs change (belt-and-suspenders).
--
-- NOTE: We intentionally do NOT enforce a uniqueness constraint on (season, week, home_team_id, visitor_team_id).
-- Some upstream providers can emit duplicate rows with different IDs for the same matchup/week (e.g. corrections).
-- We treat `id` as the canonical identifier and allow duplicates by matchup/week if the upstream chooses.

create index if not exists idx_nfl_games_season_week on public.nfl_games(season, week);
create index if not exists idx_nfl_games_home_team_id on public.nfl_games(home_team_id);
create index if not exists idx_nfl_games_visitor_team_id on public.nfl_games(visitor_team_id);
create index if not exists idx_nfl_games_date on public.nfl_games(date);

commit;


