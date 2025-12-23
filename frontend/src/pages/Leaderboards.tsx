import { useEffect, useMemo, useState } from "react";
import { Header } from "@/components/Header";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useFilterOptions } from "@/hooks/useApi";
import { TeamLogo } from "@/components/TeamLogo";
import { useNavigate } from "react-router-dom";

type Mode = "weekly" | "season";
type Category = "receiving" | "rushing" | "passing" | "total_yards";

type Row = Record<string, any>;

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export default function Leaderboards() {
  const { data: options } = useFilterOptions();
  const navigate = useNavigate();

  const DEFAULT_SEASON = 2025;
  const [mode, setMode] = useState<Mode>("weekly");
  const [category, setCategory] = useState<Category>("receiving");
  const [season, setSeason] = useState<number>(options?.seasons?.[0] || DEFAULT_SEASON);
  const [week, setWeek] = useState<number>(options?.weeks?.[0] || 1);
  const [team, setTeam] = useState<string>("");
  const [position, setPosition] = useState<string>("ALL");
  const [search, setSearch] = useState<string>("");
  const [sortKey, setSortKey] = useState<string>("rank");
  const [asc, setAsc] = useState<boolean>(false);

  // When options load (async), prefer the latest season unless user already chose something valid.
  useEffect(() => {
    const seasons = options?.seasons || [];
    if (seasons.length === 0) return;
    if (!seasons.includes(season)) setSeason(seasons[0]);
  }, [options?.seasons, season]);

  const endpoint = useMemo(() => {
    const base = new URLSearchParams();
    base.set("season", String(season));
    if (team) base.set("team", team);
    if (position && position !== "ALL") base.set("position", position);
    base.set("limit", "50");
    if (mode === "weekly") base.set("week", String(week));

    if (category === "receiving") {
      return mode === "weekly"
        ? `/api/receiving_dashboard?${base.toString()}`
        : `/api/receiving_season?${base.toString()}`;
    }
    if (category === "rushing") {
      return mode === "weekly"
        ? `/api/rushing_dashboard?${base.toString()}`
        : `/api/rushing_season?${base.toString()}`;
    }
    if (category === "passing") {
      return mode === "weekly"
        ? `/api/passing_dashboard?${base.toString()}`
        : `/api/passing_season?${base.toString()}`;
    }
    // total_yards
    return mode === "weekly"
      ? `/api/total_yards_dashboard?${base.toString()}`
      : `/api/total_yards_season?${base.toString()}`;
  }, [mode, category, season, week, team, position]);

  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // lightweight fetch-on-change (keeps this page isolated from react-query setup)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    fetchJson<{ rows: Row[] }>(endpoint)
      .then((data) => {
        if (cancelled) return;
        setRows(data.rows || []);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(String(e?.message || e));
        setRows([]);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [endpoint]);

  const displayRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    let out = rows;
    if (q) {
      out = out.filter((r) => String(r.player_name || "").toLowerCase().includes(q));
    }
    const getVal = (r: Row, k: string): any => {
      if (k === "rank") return 0;
      return r[k];
    };
    const sorted = [...out].sort((a, b) => {
      const av = getVal(a, sortKey);
      const bv = getVal(b, sortKey);
      const an = typeof av === "number" ? av : Number(av);
      const bn = typeof bv === "number" ? bv : Number(bv);
      const bothNum = Number.isFinite(an) && Number.isFinite(bn);
      if (bothNum) return asc ? an - bn : bn - an;
      const as = (av ?? "").toString();
      const bs = (bv ?? "").toString();
      return asc ? as.localeCompare(bs) : bs.localeCompare(as);
    });
    return sorted;
  }, [rows, search, sortKey, asc]);

  const SortHead = ({ k, label, className }: { k: string; label: string; className?: string }) => {
    const active = sortKey === k;
    const arrow = active ? (asc ? "▲" : "▼") : "";
    return (
      <TableHead className={className}>
        <button
          type="button"
          className="w-full inline-flex items-center justify-center gap-2 text-muted-foreground font-medium hover:text-foreground transition-colors"
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

  const title =
    mode === "weekly"
      ? `Weekly Leaders • Week ${week} • ${season}`
      : `Season Leaders • ${season}`;

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container mx-auto px-4 py-8 space-y-6">
        <div className="glass-card rounded-xl p-5">
          <div className="flex items-start justify-between gap-4 flex-col md:flex-row">
            <div>
              <h2 className="text-xl font-semibold text-foreground">{title}</h2>
              <p className="text-sm text-muted-foreground">
                Leaderboards powered by your FantasyAppTest database (plays + derived metrics).
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3 w-full md:w-auto">
              <Select value={mode} onValueChange={(v) => setMode(v as Mode)}>
                <SelectTrigger><SelectValue placeholder="Mode" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="season">Season</SelectItem>
                </SelectContent>
              </Select>

              <Select value={category} onValueChange={(v) => setCategory(v as Category)}>
                <SelectTrigger><SelectValue placeholder="Category" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="receiving">Receiving</SelectItem>
                  <SelectItem value="rushing">Rushing</SelectItem>
                  <SelectItem value="passing">Passing</SelectItem>
                  <SelectItem value="total_yards">Total Yards</SelectItem>
                </SelectContent>
              </Select>

              <Select value={String(season)} onValueChange={(v) => setSeason(Number(v))}>
                <SelectTrigger><SelectValue placeholder="Season" /></SelectTrigger>
                <SelectContent>
                  {options?.seasons?.map((s) => (
                    <SelectItem key={s} value={String(s)}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {mode === "weekly" ? (
                <Select value={String(week)} onValueChange={(v) => setWeek(Number(v))}>
                  <SelectTrigger><SelectValue placeholder="Week" /></SelectTrigger>
                  <SelectContent>
                    {options?.weeks?.map((w) => (
                      <SelectItem key={w} value={String(w)}>Week {w}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <div className="hidden lg:block" />
              )}

              <Select value={team || "ALL"} onValueChange={(v) => setTeam(v === "ALL" ? "" : v)}>
                <SelectTrigger><SelectValue placeholder="Team" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">All Teams</SelectItem>
                  {options?.teams?.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={position} onValueChange={(v) => setPosition(v)}>
                <SelectTrigger><SelectValue placeholder="Position" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">All Positions</SelectItem>
                  <SelectItem value="QB">QB</SelectItem>
                  <SelectItem value="RB">RB</SelectItem>
                  <SelectItem value="HB">HB</SelectItem>
                  <SelectItem value="WR">WR</SelectItem>
                  <SelectItem value="TE">TE</SelectItem>
                </SelectContent>
              </Select>

              <div className="lg:min-w-[240px]">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search player…"
                  className="w-full h-10 px-3 rounded-lg border border-border bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="glass-card rounded-xl overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              {loading ? "Loading..." : `${rows.length} rows`}
              {err ? ` • Error: ${err}` : ""}
            </div>
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground font-medium">Player</TableHead>
                  <TableHead className="text-muted-foreground font-medium">Team</TableHead>
                  {category === "receiving" ? (
                    <>
                      <SortHead k="targets" label="TGT" className="text-center" />
                      <SortHead k="receptions" label="REC" className="text-center" />
                      <SortHead k="rec_yards" label="YDS" className="text-center" />
                      <SortHead k="rec_tds" label="TD" className="text-center" />
                    </>
                  ) : category === "rushing" ? (
                    <>
                      <SortHead k="rush_attempts" label="ATT" className="text-center" />
                      <SortHead k="rush_yards" label="YDS" className="text-center" />
                      <SortHead k="ypc" label="YPC" className="text-center" />
                      {mode === "weekly" ? null : <SortHead k="ypg" label="YPG" className="text-center" />}
                      <SortHead k="receptions" label="REC" className="text-center" />
                      {mode === "weekly" ? null : <SortHead k="rpg" label="RPG" className="text-center" />}
                      <SortHead k="rec_yards" label="REC YDS" className="text-center" />
                      {mode === "weekly" ? null : <SortHead k="rec_ypg" label="REC YPG" className="text-center" />}
                      <SortHead k="rush_tds" label="TD" className="text-center" />
                    </>
                  ) : category === "passing" ? (
                    <>
                      <SortHead k="passing_completions" label="CMP" className="text-center" />
                      <SortHead k="passing_attempts" label="ATT" className="text-center" />
                      <SortHead k="passing_yards" label="YDS" className="text-center" />
                      <SortHead k="passing_tds" label="TD" className="text-center" />
                      <SortHead k="interceptions" label="INT" className="text-center" />
                    </>
                  ) : (
                    <>
                      <SortHead k="rush_yards" label="RUSH" className="text-center" />
                      <SortHead k="rec_yards" label="REC" className="text-center" />
                      <SortHead k="total_yards" label="TOTAL" className="text-center" />
                      <SortHead k="total_tds" label="TD" className="text-center" />
                    </>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayRows.map((r, i) => (
                  <TableRow
                    key={i}
                    className="data-row border-border cursor-pointer"
                    onClick={() => {
                      const pid = String(r.player_id || "").trim();
                      if (!pid) return;
                      const qs = new URLSearchParams({ season: String(season), player_id: pid });
                      navigate(`/?${qs.toString()}`);
                    }}
                  >
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full overflow-hidden bg-secondary ring-1 ring-border shrink-0">
                          {r.photoUrl ? (
                            <img src={r.photoUrl} className="w-full h-full object-cover" loading="lazy" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-muted-foreground text-xs font-bold">
                              {(r.player_name || r.player_id || "?")
                                .toString()
                                .split(" ")
                                .filter(Boolean)
                                .slice(0, 2)
                                .map((n: string) => n[0])
                                .join("")}
                            </div>
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="truncate">{r.player_name || r.player_id}</div>
                          <div className="text-xs text-muted-foreground">{r.position || ""}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      <div className="flex items-center gap-1.5">
                        <TeamLogo team={r.team} size="sm" />
                        <span>{r.team}</span>
                      </div>
                    </TableCell>

                    {category === "receiving" ? (
                      <>
                        <TableCell className="text-center font-mono">{r.targets ?? 0}</TableCell>
                        <TableCell className="text-center font-mono">{r.receptions ?? 0}</TableCell>
                        <TableCell className="text-center font-mono font-semibold">{r.rec_yards ?? 0}</TableCell>
                        <TableCell className="text-center font-mono">{r.rec_tds ?? 0}</TableCell>
                      </>
                    ) : category === "rushing" ? (
                      <>
                        <TableCell className="text-center font-mono">{r.rush_attempts ?? 0}</TableCell>
                        <TableCell className="text-center font-mono font-semibold">{r.rush_yards ?? 0}</TableCell>
                        <TableCell className="text-center font-mono">{typeof r.ypc === "number" ? r.ypc.toFixed(1) : "0.0"}</TableCell>
                        {mode === "weekly" ? null : (
                          <TableCell className="text-center font-mono">{typeof r.ypg === "number" ? r.ypg.toFixed(1) : "0.0"}</TableCell>
                        )}
                        <TableCell className="text-center font-mono">{r.receptions ?? 0}</TableCell>
                        {mode === "weekly" ? null : (
                          <TableCell className="text-center font-mono">{typeof r.rpg === "number" ? r.rpg.toFixed(1) : "0.0"}</TableCell>
                        )}
                        <TableCell className="text-center font-mono">{r.rec_yards ?? 0}</TableCell>
                        {mode === "weekly" ? null : (
                          <TableCell className="text-center font-mono">{typeof r.rec_ypg === "number" ? r.rec_ypg.toFixed(1) : "0.0"}</TableCell>
                        )}
                        <TableCell className="text-center font-mono">{r.rush_tds ?? 0}</TableCell>
                      </>
                    ) : category === "passing" ? (
                      <>
                        <TableCell className="text-center font-mono">{r.passing_completions ?? 0}</TableCell>
                        <TableCell className="text-center font-mono">{r.passing_attempts ?? 0}</TableCell>
                        <TableCell className="text-center font-mono font-semibold">{r.passing_yards ?? 0}</TableCell>
                        <TableCell className="text-center font-mono">{r.passing_tds ?? 0}</TableCell>
                        <TableCell className="text-center font-mono">{r.interceptions ?? 0}</TableCell>
                      </>
                    ) : (
                      <>
                        <TableCell className="text-center font-mono">{r.rush_yards ?? 0}</TableCell>
                        <TableCell className="text-center font-mono">{r.rec_yards ?? 0}</TableCell>
                        <TableCell className="text-center font-mono font-semibold">{r.total_yards ?? 0}</TableCell>
                        <TableCell className="text-center font-mono">{r.total_tds ?? 0}</TableCell>
                      </>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </main>
    </div>
  );
}


