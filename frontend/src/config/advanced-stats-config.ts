// Shared configuration for advanced stats display
// Used by both GoatAdvancedStats (player dossier) and Leaderboards (season leaderboard)

export type ColumnType = "int" | "float";

export interface AdvancedColumn {
  k: string;
  label: string;
  type: ColumnType;
}

// Tooltip definitions for all advanced stats
export const ADVANCED_STAT_TOOLTIPS: Record<string, string> = {
  // Receiving
  targets: "Total times the player was targeted by a pass",
  receptions: "Total number of passes caught",
  yards: "Total receiving yards gained",
  avg_intended_air_yards: "Average distance the ball traveled in the air on targets",
  avg_yac: "Average yards gained after the catch",
  avg_expected_yac: "Expected yards after catch based on catch location and defense",
  avg_yac_above_expectation: "Difference between actual and expected yards after catch",
  avg_cushion: "Average distance the nearest defender was at time of catch",
  avg_separation: "Average distance from the nearest defender when ball arrived",
  catch_percentage: "Percentage of targets that resulted in receptions",
  percent_share_of_intended_air_yards: "Player's share of team's total intended air yards",
  rec_touchdowns: "Total receiving touchdowns",
  
  // Rushing
  rush_attempts: "Total number of rushing attempts",
  rush_yards: "Total rushing yards gained",
  rush_touchdowns: "Total rushing touchdowns",
  avg_time_to_los: "Average time (seconds) from snap to crossing line of scrimmage",
  expected_rush_yards: "Expected rushing yards based on blockers and defenders",
  rush_yards_over_expected: "Rushing yards gained above expectation",
  rush_yards_over_expected_per_att: "Average yards over expected per rushing attempt",
  rush_pct_over_expected: "Percentage of rushes that exceeded expected yards",
  efficiency: "Overall rushing efficiency rating",
  percent_attempts_gte_eight_defenders: "Percentage of rushes against 8+ defenders in box",
  avg_rush_yards: "Average yards per rushing attempt",
  
  // Passing
  attempts: "Total passing attempts",
  completions: "Total completed passes",
  pass_yards: "Total passing yards",
  pass_touchdowns: "Total passing touchdowns",
  interceptions: "Total interceptions thrown",
  passer_rating: "Traditional NFL passer rating",
  completion_percentage: "Percentage of passes completed",
  completion_percentage_above_expectation: "Completion % above expected based on throw difficulty",
  expected_completion_percentage: "Expected completion % based on throw characteristics",
  avg_time_to_throw: "Average time (seconds) from snap to throw",
  avg_intended_air_yards: "Average distance ball traveled in air on pass attempts",
  avg_completed_air_yards: "Average air yards on completed passes",
  avg_air_distance: "Average distance ball traveled in air (all attempts)",
  avg_air_yards_differential: "Difference between intended and completed air yards",
  avg_air_yards_to_sticks: "Average air yards relative to first down marker",
  max_air_distance: "Longest air yards on any attempt",
  max_completed_air_distance: "Longest completed pass (air yards)",
  aggressiveness: "Percentage of throws into tight coverage",
  games_played: "Number of games played"
};

// Column definitions for receiving stats (for player dossier - includes week)
export const ADVANCED_RECEIVING_COLUMNS_WITH_WEEK: AdvancedColumn[] = [
  { k: "week", label: "WK", type: "int" },
  { k: "targets", label: "TGT", type: "int" },
  { k: "receptions", label: "REC", type: "int" },
  { k: "yards", label: "YDS", type: "int" },
  { k: "avg_intended_air_yards", label: "aIAY", type: "float" },
  { k: "avg_yac", label: "aYAC", type: "float" },
  { k: "avg_separation", label: "SEP", type: "float" },
  { k: "avg_cushion", label: "CUSH", type: "float" },
  { k: "catch_percentage", label: "CATCH%", type: "float" },
  { k: "rec_touchdowns", label: "TD", type: "int" },
];

// Column definitions for rushing stats (for player dossier - includes week)
export const ADVANCED_RUSHING_COLUMNS_WITH_WEEK: AdvancedColumn[] = [
  { k: "week", label: "WK", type: "int" },
  { k: "rush_attempts", label: "ATT", type: "int" },
  { k: "rush_yards", label: "YDS", type: "int" },
  { k: "rush_touchdowns", label: "TD", type: "int" },
  { k: "avg_time_to_los", label: "TTLOS", type: "float" },
  { k: "expected_rush_yards", label: "xRushY", type: "float" },
  { k: "rush_yards_over_expected", label: "RYOE", type: "float" },
  { k: "efficiency", label: "EFF", type: "float" },
  { k: "avg_rush_yards", label: "AVG", type: "float" },
];

// Column definitions for passing stats (for player dossier - includes week)
export const ADVANCED_PASSING_COLUMNS_WITH_WEEK: AdvancedColumn[] = [
  { k: "week", label: "WK", type: "int" },
  { k: "attempts", label: "ATT", type: "int" },
  { k: "completions", label: "COMP", type: "int" },
  { k: "pass_yards", label: "YDS", type: "int" },
  { k: "pass_touchdowns", label: "TD", type: "int" },
  { k: "interceptions", label: "INT", type: "int" },
  { k: "passer_rating", label: "RATE", type: "float" },
  { k: "completion_percentage", label: "COMP%", type: "float" },
  { k: "avg_time_to_throw", label: "TTT", type: "float" },
  { k: "avg_intended_air_yards", label: "IAY", type: "float" },
  { k: "aggressiveness", label: "AGG", type: "float" },
];

// Column definitions for leaderboards (season totals - no week column)
export const ADVANCED_RECEIVING_COLUMNS: AdvancedColumn[] = [
  { k: "targets", label: "TGT", type: "int" },
  { k: "receptions", label: "REC", type: "int" },
  { k: "yards", label: "YDS", type: "int" },
  { k: "rec_touchdowns", label: "TD", type: "int" },
  { k: "avg_intended_air_yards", label: "aIAY", type: "float" },
  { k: "avg_yac", label: "aYAC", type: "float" },
  { k: "avg_yac_above_expectation", label: "YAC+", type: "float" },
  { k: "avg_separation", label: "SEP", type: "float" },
  { k: "avg_cushion", label: "CUSH", type: "float" },
  { k: "catch_percentage", label: "CATCH%", type: "float" },
];

export const ADVANCED_RUSHING_COLUMNS: AdvancedColumn[] = [
  { k: "rush_attempts", label: "ATT", type: "int" },
  { k: "rush_yards", label: "YDS", type: "int" },
  { k: "rush_touchdowns", label: "TD", type: "int" },
  { k: "avg_rush_yards", label: "YPC", type: "float" },
  { k: "rush_yards_over_expected", label: "RYOE", type: "float" },
  { k: "rush_yards_over_expected_per_att", label: "RYOE/A", type: "float" },
  { k: "efficiency", label: "EFF", type: "float" },
  { k: "avg_time_to_los", label: "TTLOS", type: "float" },
  { k: "expected_rush_yards", label: "xRushY", type: "float" },
];

export const ADVANCED_PASSING_COLUMNS: AdvancedColumn[] = [
  { k: "attempts", label: "ATT", type: "int" },
  { k: "completions", label: "COMP", type: "int" },
  { k: "pass_yards", label: "YDS", type: "int" },
  { k: "pass_touchdowns", label: "TD", type: "int" },
  { k: "interceptions", label: "INT", type: "int" },
  { k: "passer_rating", label: "RATE", type: "float" },
  { k: "completion_percentage", label: "COMP%", type: "float" },
  { k: "completion_percentage_above_expectation", label: "CPOE", type: "float" },
  { k: "avg_air_distance", label: "AIR", type: "float" },
  { k: "avg_intended_air_yards", label: "IAY", type: "float" },
  { k: "avg_time_to_throw", label: "TTT", type: "float" },
  { k: "aggressiveness", label: "AGG", type: "float" },
];

