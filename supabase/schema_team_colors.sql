-- Additive-only Supabase schema extension: team colors
--
-- Applies to: public.nfl_teams
-- Safe to re-run.

begin;

alter table if exists public.nfl_teams
  add column if not exists primary_color text;

alter table if exists public.nfl_teams
  add column if not exists secondary_color text;

commit;



