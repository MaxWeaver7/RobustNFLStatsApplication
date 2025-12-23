-- Optional performance indexes for fast leaderboards + players list.
-- Run this once in Supabase SQL editor if your queries feel slow.

begin;

-- Weekly leaderboards (game stats)
create index if not exists idx_pgs_season_week_post_recv_tgt
  on public.nfl_player_game_stats (season, week, postseason, receiving_targets desc);

-- Faster when filtering by team
create index if not exists idx_pgs_season_week_post_team_recv_tgt
  on public.nfl_player_game_stats (season, week, postseason, team_id, receiving_targets desc);

create index if not exists idx_pgs_season_week_post_rush_yds
  on public.nfl_player_game_stats (season, week, postseason, rushing_yards desc);

create index if not exists idx_pgs_season_week_post_team_rush_yds
  on public.nfl_player_game_stats (season, week, postseason, team_id, rushing_yards desc);

create index if not exists idx_pgs_season_week_post_pass_yds
  on public.nfl_player_game_stats (season, week, postseason, passing_yards desc);

create index if not exists idx_pgs_season_week_post_team_pass_yds
  on public.nfl_player_game_stats (season, week, postseason, team_id, passing_yards desc);

-- Season leaderboards (season stats)
create index if not exists idx_pss_season_post_recv_yds
  on public.nfl_player_season_stats (season, postseason, receiving_yards desc);

create index if not exists idx_pss_season_post_team_recv_yds
  on public.nfl_player_season_stats (season, postseason, player_id, receiving_yards desc);

create index if not exists idx_pss_season_post_rush_yds
  on public.nfl_player_season_stats (season, postseason, rushing_yards desc);

create index if not exists idx_pss_season_post_team_rush_yds
  on public.nfl_player_season_stats (season, postseason, player_id, rushing_yards desc);

create index if not exists idx_pss_season_post_pass_yds
  on public.nfl_player_season_stats (season, postseason, passing_yards desc);

create index if not exists idx_pss_season_post_team_pass_yds
  on public.nfl_player_season_stats (season, postseason, player_id, passing_yards desc);

commit;


