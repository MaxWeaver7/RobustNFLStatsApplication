import { useMemo, useState, useEffect } from "react";
import { cn, formatStat } from "@/lib/utils";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { GoatAdvancedPayload, GoatAdvancedRow } from "@/types/player";
import {
  ADVANCED_STAT_TOOLTIPS,
  ADVANCED_RECEIVING_COLUMNS_WITH_WEEK,
  ADVANCED_RUSHING_COLUMNS_WITH_WEEK,
  ADVANCED_PASSING_COLUMNS_WITH_WEEK,
} from "@/config/advanced-stats-config";

interface GoatAdvancedStatsProps {
  data?: GoatAdvancedPayload | null;
  className?: string;
}

type Kind = "receiving" | "rushing" | "passing";

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
      return ADVANCED_RECEIVING_COLUMNS_WITH_WEEK;
    }
    if (kind === "rushing") {
      return ADVANCED_RUSHING_COLUMNS_WITH_WEEK;
    }
    return ADVANCED_PASSING_COLUMNS_WITH_WEEK;
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
                const tooltip = ADVANCED_STAT_TOOLTIPS[c.k] || "";
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


