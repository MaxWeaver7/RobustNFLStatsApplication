import { useMemo, useState, useEffect } from "react";
import { cn, formatStat } from "@/lib/utils";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { GoatAdvancedPayload, GoatAdvancedRow } from "@/types/player";

interface GoatAdvancedStatsProps {
  data?: GoatAdvancedPayload | null;
  className?: string;
}

type Kind = "receiving" | "rushing" | "passing";

// Tooltip definitions for advanced stats
const STAT_TOOLTIPS: Record<string, string> = {
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

export function GoatAdvancedStats({ data, className }: GoatAdvancedStatsProps) {
  // Determine which stat types have data
  const availableKinds = useMemo(() => {
    const kinds: Kind[] = [];
    if (data?.regular?.passing?.length) kinds.push("passing");
    if (data?.regular?.rushing?.length) kinds.push("rushing");
    if (data?.regular?.receiving?.length) kinds.push("receiving");
    return kinds;
  }, [data]);

  // Auto-select first available kind
  const [kind, setKind] = useState<Kind>(availableKinds[0] || "receiving");
  const [sortKey, setSortKey] = useState<string>("week");
  const [sortAsc, setSortAsc] = useState<boolean>(true);

  // Update kind if data changes and current kind has no data
  useEffect(() => {
    if (availableKinds.length > 0 && !availableKinds.includes(kind)) {
      setKind(availableKinds[0]);
    }
  }, [availableKinds, kind]);

  const { weekZeroRow, regularRows } = useMemo(() => {
    const r = data?.regular?.[kind] || [];
    const rawRows = Array.isArray(r) ? r : [];
    
    // Separate Week 0 (season total) from weekly data
    const weekZero = rawRows.find(row => row.week === 0) || null;
    const weekly = rawRows.filter(row => row.week !== 0);
    
    // Sort weekly rows
    if (!sortKey) return { weekZeroRow: weekZero, regularRows: weekly };
    
    const sorted = [...weekly].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      
      // Handle nulls
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      
      // Numeric comparison
      const aNum = Number(aVal);
      const bNum = Number(bVal);
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return sortAsc ? aNum - bNum : bNum - aNum;
      }
      
      // String comparison
      const aStr = String(aVal);
      const bStr = String(bVal);
      return sortAsc ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
    });
    
    return { weekZeroRow: weekZero, regularRows: sorted };
  }, [data, kind, sortKey, sortAsc]);

  const columns = useMemo(() => {
    if (kind === "receiving") {
      return [
        { k: "week", label: "WK", type: "int" as const },
        { k: "targets", label: "TGT", type: "int" as const },
        { k: "receptions", label: "REC", type: "int" as const },
        { k: "yards", label: "YDS", type: "int" as const },
        { k: "avg_intended_air_yards", label: "aIAY", type: "float" as const },
        { k: "avg_yac", label: "aYAC", type: "float" as const },
        { k: "avg_separation", label: "SEP", type: "float" as const },
        { k: "avg_cushion", label: "CUSH", type: "float" as const },
        { k: "catch_percentage", label: "CATCH%", type: "float" as const },
        { k: "rec_touchdowns", label: "TD", type: "int" as const },
      ];
    }
    if (kind === "rushing") {
      return [
        { k: "week", label: "WK", type: "int" as const },
        { k: "rush_attempts", label: "ATT", type: "int" as const },
        { k: "rush_yards", label: "YDS", type: "int" as const },
        { k: "rush_touchdowns", label: "TD", type: "int" as const },
        { k: "avg_time_to_los", label: "TTLOS", type: "float" as const },
        { k: "expected_rush_yards", label: "xRushY", type: "float" as const },
        { k: "rush_yards_over_expected", label: "RYOE", type: "float" as const },
        { k: "efficiency", label: "EFF", type: "float" as const },
        { k: "avg_rush_yards", label: "AVG", type: "float" as const },
      ];
    }
    return [
      { k: "week", label: "WK", type: "int" as const },
      { k: "attempts", label: "ATT", type: "int" as const },
      { k: "completions", label: "COMP", type: "int" as const },
      { k: "pass_yards", label: "YDS", type: "int" as const },
      { k: "pass_touchdowns", label: "TD", type: "int" as const },
      { k: "interceptions", label: "INT", type: "int" as const },
      { k: "passer_rating", label: "RATE", type: "float" as const },
      { k: "completion_percentage", label: "COMP%", type: "float" as const },
      { k: "avg_time_to_throw", label: "TTT", type: "float" as const },
      { k: "avg_intended_air_yards", label: "IAY", type: "float" as const },
      { k: "aggressiveness", label: "AGG", type: "float" as const },
    ];
  }, [kind]);

  const fmt = (colType: "int" | "float", v: any, colKey?: string) => {
    // Special handling for week column
    if (colKey === "week") {
      const weekNum = v ?? 0;
      if (weekNum === 0) return "TOTAL";
      return String(weekNum);
    }
    if (colType === "int") return formatStat(v ?? 0, { integer: true });
    // Percent-like columns should still be X.XX (we can add % sign later once we confirm units).
    return formatStat(v);
  };

  return (
    <div className={cn("glass-card rounded-xl overflow-hidden", className)}>
      <div className="p-4 border-b border-border flex items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold text-foreground">Advanced Metrics</h3>
          <p className="text-sm text-muted-foreground">Weekly + season totals</p>
        </div>
        <div className="flex items-center gap-2">
          {availableKinds.map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={cn(
                "h-9 px-3 rounded-lg border border-border text-sm transition-colors",
                k === kind ? "bg-secondary text-foreground" : "bg-transparent text-muted-foreground hover:bg-secondary"
              )}
              aria-pressed={k === kind}
            >
              {k[0].toUpperCase() + k.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              {columns.map((c) => {
                const tooltip = STAT_TOOLTIPS[c.k] || "";
                const isSorted = sortKey === c.k;
                const arrow = isSorted ? (sortAsc ? " ▲" : " ▼") : "";
                
                return (
                  <TableHead 
                    key={c.k} 
                    className="text-muted-foreground font-medium text-center select-none"
                    title={tooltip}
                  >
                    <button
                      type="button"
                      className={cn(
                        "inline-flex items-center gap-1 hover:text-foreground transition-colors",
                        isSorted && "text-foreground"
                      )}
                      onClick={() => {
                        if (sortKey === c.k) {
                          setSortAsc(!sortAsc);
                        } else {
                          setSortKey(c.k);
                          setSortAsc(false);
                        }
                      }}
                    >
                      <span>{c.label}</span>
                      {arrow && <span className="text-xs font-mono opacity-70">{arrow}</span>}
                    </button>
                  </TableHead>
                );
              })}
            </TableRow>
          </TableHeader>
          <TableBody>
            {regularRows.length === 0 && !weekZeroRow ? (
              <TableRow className="border-border">
                <TableCell colSpan={columns.length} className="text-muted-foreground text-center py-8">
                  No advanced metrics available for this player/season yet.
                </TableCell>
              </TableRow>
            ) : (
              <>
                {/* Week 0 (Season Total) Row - pinned to top with distinct styling */}
                {weekZeroRow && (
                  <TableRow className="border-border bg-muted/30">
                    {columns.map((c) => (
                      <TableCell key={c.k} className="text-center font-mono font-bold">
                        {fmt(c.type, weekZeroRow[c.k], c.k)}
                      </TableCell>
                    ))}
                  </TableRow>
                )}
                
                {/* Weekly Data Rows */}
                {regularRows.map((r: GoatAdvancedRow, idx: number) => (
                  <TableRow key={idx} className="data-row border-border">
                    {columns.map((c) => (
                      <TableCell key={c.k} className="text-center font-mono">
                        {fmt(c.type, r[c.k], c.k)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}


