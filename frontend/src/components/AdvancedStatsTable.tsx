import { useMemo, useState } from "react";
import { PlayerGameLog } from "@/types/player";
import { cn } from "@/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TeamLogo } from "./TeamLogo";

interface AdvancedStatsTableProps {
  gameLogs: PlayerGameLog[];
  position: string;
}

export function AdvancedStatsTable({ gameLogs, position }: AdvancedStatsTableProps) {
  const isReceiver = ['WR', 'TE'].includes(position);
  const isQB = (position || '').toUpperCase() === 'QB';
  const [sortKey, setSortKey] = useState<string>("week");
  const [asc, setAsc] = useState<boolean>(true);

  const getStatHighlight = (value: number, thresholds: { high: number; low: number }) => {
    if (value >= thresholds.high) return 'text-primary font-semibold';
    if (value <= thresholds.low) return 'text-destructive';
    return '';
  };

  const weekLabel = (g: PlayerGameLog) => {
    const isPost =
      g.is_postseason === true ||
      g.is_postseason === 1 ||
      (typeof g.is_postseason === "string" && g.is_postseason === "1") ||
      g.week >= 19;
    if (!isPost) return String(g.week);
    const map: Record<number, string> = { 19: "WC", 20: "DIV", 21: "CONF", 22: "SB" };
    const lbl = map[g.week] || `POST`;
    return `${lbl} (${g.week})`;
  };

  const getValue = (g: PlayerGameLog, key: string) => {
    if (key === "week") return g.week;
    if (key === "opponent") return (g.location === "away" ? `@ ${g.opponent}` : `vs ${g.opponent}`);
    if (key === "ypc") {
      const denom = isReceiver ? (g.receptions || 0) : (g.rush_attempts || 0);
      if (!denom) return 0;
      return isReceiver ? (g.rec_yards / denom) : (g.rush_yards / denom);
    }
    // @ts-expect-error - dynamic lookup for table sorting
    return g[key];
  };

  const sortedLogs = useMemo(() => {
    const rows = [...gameLogs];
    rows.sort((a, b) => {
      const av = getValue(a, sortKey);
      const bv = getValue(b, sortKey);
      const an = typeof av === "number" ? av : Number(av);
      const bn = typeof bv === "number" ? bv : Number(bv);
      const bothNum = Number.isFinite(an) && Number.isFinite(bn);
      if (bothNum) return asc ? an - bn : bn - an;
      const as = (av ?? "").toString();
      const bs = (bv ?? "").toString();
      return asc ? as.localeCompare(bs) : bs.localeCompare(as);
    });
    return rows;
  }, [gameLogs, sortKey, asc, isReceiver]);

  const SortHead = ({ k, label, className }: { k: string; label: string; className?: string }) => {
    const active = sortKey === k;
    const arrow = active ? (asc ? "▲" : "▼") : "";
    return (
      <TableHead
        className={cn("text-muted-foreground font-medium select-none", className, active && "text-foreground")}
      >
        <button
          type="button"
          className="inline-flex items-center gap-2 hover:text-foreground transition-colors"
          onClick={() => {
            if (sortKey === k) setAsc((v) => !v);
            else {
              setSortKey(k);
              setAsc(false);
            }
          }}
        >
          <span>{label}</span>
          <span className="text-xs font-mono opacity-70">{arrow}</span>
        </button>
      </TableHead>
    );
  };

  return (
    <div className="glass-card rounded-xl overflow-hidden opacity-0 animate-slide-up" style={{ animationDelay: '300ms' }}>
      <div className="p-4 border-b border-border">
        <h3 className="font-semibold text-foreground">
          Game-by-Game {isQB ? 'Passing' : (isReceiver ? 'Receiving' : 'Rushing')} Stats
        </h3>
        <p className="text-sm text-muted-foreground">
          Season {gameLogs[0]?.season || 'N/A'} • Click any column header to sort
        </p>
      </div>
      
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <SortHead k="week" label="Week" />
              <SortHead k="opponent" label="OPP" />
              {isQB ? (
                <>
                  <SortHead k="passing_attempts" label="ATT" className="text-center" />
                  <SortHead k="passing_completions" label="COMP" className="text-center" />
                  <SortHead k="passing_yards" label="P YDS" className="text-center" />
                  <SortHead k="passing_tds" label="P TD" className="text-center" />
                  <SortHead k="interceptions" label="INT" className="text-center" />
                  <SortHead k="rush_yards" label="RUSH YDS" className="text-center bg-primary/10" />
                  <SortHead k="rush_tds" label="RUSH TD" className="text-center bg-primary/10" />
                  <SortHead k="qb_rating" label="RATING" className="text-center bg-primary/5" />
                </>
              ) : isReceiver ? (
                <>
                  <SortHead k="targets" label="TGT" className="text-center" />
                  <SortHead k="receptions" label="REC" className="text-center" />
                  <SortHead k="rec_yards" label="YDS" className="text-center" />
                  <SortHead k="rec_tds" label="TD" className="text-center" />
                </>
              ) : (
                <>
                  <SortHead k="rush_attempts" label="ATT" className="text-center" />
                  <SortHead k="rush_yards" label="YDS" className="text-center" />
                  <SortHead k="rush_tds" label="TD" className="text-center" />
                  <SortHead k="ypc" label="YPC" className="text-center" />
                  <SortHead k="receptions" label="REC" className="text-center bg-primary/10" />
                  <SortHead k="rec_yards" label="REC YDS" className="text-center bg-primary/10" />
                </>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedLogs.map((game, idx) => {
              const opponent = game.location === 'away' ? `@ ${game.opponent}` : `vs ${game.opponent}`;
              const ypc = isReceiver 
                ? (game.receptions > 0 ? (game.rec_yards / game.receptions) : 0)
                : (game.rush_attempts > 0 ? (game.rush_yards / game.rush_attempts) : 0);

              return (
                <TableRow 
                  key={idx} 
                  className="data-row border-border"
                >
                  <TableCell className="font-mono text-sm">
                    {weekLabel(game)}
                  </TableCell>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-1.5">
                      <TeamLogo team={game.opponent} size="sm" />
                      <span>{opponent}</span>
                    </div>
                  </TableCell>
                  {isQB ? (
                    <>
                      <TableCell className="text-center font-mono">{game.passing_attempts ?? 0}</TableCell>
                      <TableCell className="text-center font-mono">{game.passing_completions ?? 0}</TableCell>
                      <TableCell className={cn("text-center font-mono font-semibold", getStatHighlight(game.passing_yards ?? 0, { high: 280, low: 180 }))}>
                        {game.passing_yards ?? 0}
                      </TableCell>
                      <TableCell className="text-center font-mono">{game.passing_tds ?? 0}</TableCell>
                      <TableCell className="text-center font-mono">{game.interceptions ?? 0}</TableCell>
                      <TableCell className="text-center font-mono bg-primary/5">{game.rush_yards ?? 0}</TableCell>
                      <TableCell className="text-center font-mono bg-primary/5">{game.rush_tds ?? 0}</TableCell>
                      <TableCell className="text-center font-mono bg-primary/[0.03]">
                        {typeof game.qb_rating === "number" ? game.qb_rating.toFixed(1) : "—"}
                      </TableCell>
                    </>
                  ) : isReceiver ? (
                    <>
                      <TableCell className="text-center font-mono">{game.targets}</TableCell>
                      <TableCell className="text-center font-mono">{game.receptions}</TableCell>
                      <TableCell className={cn("text-center font-mono font-semibold", getStatHighlight(game.rec_yards, { high: 80, low: 30 }))}>
                        {game.rec_yards}
                      </TableCell>
                      <TableCell className="text-center font-mono">{game.rec_tds}</TableCell>
                    </>
                  ) : (
                    <>
                      <TableCell className="text-center font-mono">{game.rush_attempts}</TableCell>
                      <TableCell className={cn("text-center font-mono font-semibold", getStatHighlight(game.rush_yards, { high: 80, low: 30 }))}>
                        {game.rush_yards}
                      </TableCell>
                      <TableCell className="text-center font-mono">{game.rush_tds}</TableCell>
                      <TableCell className={cn("text-center font-mono", getStatHighlight(ypc, { high: 5, low: 3 }))}>
                        {ypc.toFixed(1)}
                      </TableCell>
                      <TableCell className="text-center font-mono bg-primary/5">{game.receptions}</TableCell>
                      <TableCell className="text-center font-mono bg-primary/5">{game.rec_yards}</TableCell>
                    </>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

