import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/Header";
import { PlayerCard } from "@/components/PlayerCard";
import { SeasonSummary } from "@/components/SeasonSummary";
import { PlayerDossierSkeleton } from "@/components/skeletons/PlayerDossierSkeleton";
import { AdvancedStatsTable } from "@/components/AdvancedStatsTable";
import { GoatAdvancedStats } from "@/components/GoatAdvancedStats";
import { AnimatedSelect } from "@/components/common/AnimatedSelect";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useFilterOptions, usePlayers } from "@/hooks/useApi";
import { Player, PlayerGameLog } from "@/types/player";
import { useSearchParams } from "react-router-dom";

const Index = () => {
  const { data: options } = useFilterOptions();
  const [searchParams] = useSearchParams();
  const DEFAULT_SEASON = 2025;
  const requestedPlayerId = (searchParams.get("player_id") || "").trim();
  const requestedSeason = Number(searchParams.get("season") || "");
  const initialSeason =
    Number.isFinite(requestedSeason) && requestedSeason > 0 ? requestedSeason : (options?.seasons?.[0] || DEFAULT_SEASON);

  const [selectedSeason, setSelectedSeason] = useState<number>(initialSeason);
  const [selectedPosition, setSelectedPosition] = useState<string>('');
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [includePostseason, setIncludePostseason] = useState<boolean>(false);
  const [search, setSearch] = useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [offset, setOffset] = useState<number>(0);
  const [allPlayers, setAllPlayers] = useState<Player[]>([]);
  const PAGE_SIZE = 250;
  const serverSearch = debouncedSearch.trim().length >= 2 ? debouncedSearch.trim() : "";
  const isServerSearchActive = serverSearch.length >= 2;

  // Debounce search so we don't hammer /api/players while typing.
  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search), 250);
    return () => window.clearTimeout(t);
  }, [search]);

  // Reset paging when filters/search change.
  useEffect(() => {
    setOffset(0);
    setAllPlayers([]);
    setSelectedPlayer(null);
  }, [selectedSeason, selectedPosition, selectedTeam, serverSearch]);

  const { data: playersData, isLoading: playersLoading, isFetching: playersFetching } = usePlayers(
    selectedSeason,
    selectedPosition || undefined,
    selectedTeam || undefined,
    serverSearch || undefined,
    offset,
    PAGE_SIZE
  );

  async function fetchJson<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  // Allow deep-linking to a player even if they are not in the currently loaded list page.
  const activePlayerId = (selectedPlayer?.player_id || requestedPlayerId || "").trim();

  const { data: playerDetail, isLoading: detailLoading } = useQuery({
    queryKey: ["player", activePlayerId, selectedSeason, includePostseason],
    queryFn: () => {
      const pid = activePlayerId;
      const qs = new URLSearchParams({ season: String(selectedSeason) });
      if (includePostseason) qs.set("include_postseason", "1");
      return fetchJson<{ player: Player; gameLogs: PlayerGameLog[]; goatAdvanced?: any }>(`/api/player/${pid}?${qs.toString()}`);
    },
    enabled: !!activePlayerId && !!selectedSeason,
  });

  // Merge pages (server returns stable objects; de-dupe by player_id just in case).
  useEffect(() => {
    const page = playersData?.players || [];
    if (offset === 0) {
      setAllPlayers(page);
      return;
    }
    if (page.length === 0) return;
    setAllPlayers((prev) => {
      const seen = new Set(prev.map((p) => p.player_id));
      const next = [...prev];
      for (const p of page) {
        if (!seen.has(p.player_id)) {
          seen.add(p.player_id);
          next.push(p);
        }
      }
      return next;
    });
  }, [playersData?.players, offset]);

  const visiblePlayers = useMemo(() => {
    // When we’re server-searching, the backend already narrowed the list; still apply local filter for niceness.
    const base = allPlayers;
    const q = search.trim().toLowerCase();
    if (!q) return base;
    return base.filter((p) => p.player_name.toLowerCase().includes(q));
  }, [allPlayers, search]);

  // If coming from Leaderboards, honor ?season= and ?player_id=.
  useEffect(() => {
    if (!Number.isFinite(requestedSeason) || requestedSeason <= 0) return;
    if (requestedSeason !== selectedSeason) setSelectedSeason(requestedSeason);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestedSeason]);

  // When options load (async), prefer the latest season unless user already chose something valid.
  useEffect(() => {
    const seasons = options?.seasons || [];
    if (seasons.length === 0) return;
    if (!seasons.includes(selectedSeason)) {
      setSelectedSeason(seasons[0]);
    }
  }, [options?.seasons, selectedSeason]);

  // When deep-linking, once the detail loads, sync selection state so the UI highlights the player.
  useEffect(() => {
    if (!requestedPlayerId) return;
    const p = playerDetail?.player;
    if (!p) return;
    if (selectedPlayer?.player_id === p.player_id) return;
    setSelectedPlayer(p);
  }, [requestedPlayerId, playerDetail?.player, selectedPlayer?.player_id]);

  // Auto-select first player when list changes (but not if deep-linking to a specific player)
  useEffect(() => {
    if (requestedPlayerId) return; // Don't auto-select if URL has a specific player
    if (visiblePlayers.length > 0 && !selectedPlayer) {
      setSelectedPlayer(visiblePlayers[0]);
    }
  }, [visiblePlayers, selectedPlayer, requestedPlayerId]);

  const currentPlayer = playerDetail?.player || selectedPlayer;
  const gameLogs = playerDetail?.gameLogs || [];
  const goatAdvanced = (playerDetail as any)?.goatAdvanced || null;
  const accent = (currentPlayer as any)?.teamColors?.primary || "";

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container mx-auto px-4 py-8">
        {/* Filters */}
        <div className="glass-card rounded-xl p-4 mb-6 opacity-0 animate-slide-up relative z-[100]">
          <h3 className="font-medium text-foreground mb-3">Filters</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="text-sm text-muted-foreground mb-2 block">Season</label>
              <AnimatedSelect
                label="Select season"
                options={(options?.seasons || []).map(s => s.toString())}
                value={selectedSeason.toString()}
                onChange={(value) => setSelectedSeason(Number(value))}
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground mb-2 block">Position</label>
              <AnimatedSelect
                label="All Positions"
                options={["All Positions", "QB - Quarterback", "RB - Running Back", "WR - Wide Receiver", "TE - Tight End"]}
                value={selectedPosition ? `${selectedPosition} - ${selectedPosition === 'QB' ? 'Quarterback' : selectedPosition === 'RB' ? 'Running Back' : selectedPosition === 'WR' ? 'Wide Receiver' : 'Tight End'}` : "All Positions"}
                onChange={(val) => {
                  if (val === "All Positions") {
                    setSelectedPosition("");
                  } else {
                    const pos = val.split(" - ")[0];
                    setSelectedPosition(pos);
                  }
                }}
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground mb-2 block">Team</label>
              <AnimatedSelect
                label="All Teams"
                options={["All Teams", ...(options?.teams || [])]}
                value={selectedTeam || "All Teams"}
                onChange={(val) => setSelectedTeam(val === "All Teams" ? "" : val)}
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground mb-2 block">Season Type</label>
              <button
                type="button"
                className="w-full h-10 px-3 rounded-lg border border-border bg-transparent text-sm text-foreground hover:bg-secondary transition-colors flex items-center justify-between"
                onClick={() => setIncludePostseason((v) => !v)}
                aria-pressed={includePostseason}
                title="Toggle postseason games (weeks 19-22)"
              >
                <span>{includePostseason ? "Regular + Postseason" : "Regular Season Only"}</span>
                <span className={`text-xs font-mono ${includePostseason ? "text-primary" : "text-muted-foreground"}`}>
                  {includePostseason ? "ON" : "OFF"}
                </span>
              </button>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-12 gap-8 relative z-0">
          {/* Player List Sidebar */}
          <div className="lg:col-span-4 space-y-4">
            <div className="opacity-0 animate-fade-in">
              <h2 className="text-lg font-semibold text-foreground mb-1">Players</h2>
              <p className="text-sm text-muted-foreground mb-4">
                {playersLoading ? 'Loading players...' : ''}
                {!playersLoading && playersFetching ? "Updating…" : ""}
              </p>
              <div className="mt-3">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search players…"
                  className="w-full h-10 px-3 rounded-lg border border-border bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
            
            <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto pr-2">
              {visiblePlayers.map((player, idx) => (
                <PlayerCard
                  key={player.player_id}
                  player={player}
                  isSelected={selectedPlayer?.player_id === player.player_id}
                  onClick={() => setSelectedPlayer(player)}
                  // Avoid huge perceived slowness from staggered animations on large lists.
                  delay={idx < 16 ? 60 + idx * 20 : 0}
                />
              ))}
              
              {!playersLoading && visiblePlayers.length === 0 && (
                <div className="glass-card rounded-xl p-8 text-center">
                  <p className="text-muted-foreground">No players found for the selected filters.</p>
                </div>
              )}
            </div>

            {/* Paging (only when not searching) */}
            {!playersLoading && !isServerSearchActive && (playersData?.hasMore ?? false) ? (
              <button
                type="button"
                className="w-full h-10 px-3 rounded-lg border border-border bg-transparent text-sm text-foreground hover:bg-secondary transition-colors"
                onClick={() => setOffset(playersData?.nextOffset ?? offset + PAGE_SIZE)}
              >
                Load more
              </button>
            ) : null}
          </div>

          {/* Main Content */}
          <div className="lg:col-span-8 space-y-6">
            {currentPlayer ? (
              <>
                <div
                  id="player-dossier"
                  className="glass-card rounded-xl p-5 opacity-0 animate-slide-up"
                  style={{
                    animationDelay: "150ms",
                    borderLeftWidth: "3px",
                    borderLeftStyle: "solid",
                    borderLeftColor: accent || "transparent",
                  }}
                >
                  {detailLoading ? (
                    <PlayerDossierSkeleton position={currentPlayer.position || undefined} />
                  ) : (
                    <SeasonSummary player={{ ...currentPlayer, gameLogs }} />
                  )}

                  {/* Accordion Reveal */}
                  <DossierReveal
                    loading={detailLoading}
                    gameLogs={gameLogs}
                    position={currentPlayer.position || "RB"}
                    goatAdvanced={goatAdvanced}
                    accent={accent}
                  />
                </div>
              </>
            ) : (
              <div className="glass-card rounded-xl p-12 text-center opacity-0 animate-fade-in">
                <p className="text-muted-foreground">Select a player to view detailed metrics</p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-12 py-6">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>Data sourced from nflfastR • Built for Fantasy Analytics</p>
        </div>
      </footer>
    </div>
  );
};

export default Index;

function DossierReveal({
  loading,
  gameLogs,
  position,
  goatAdvanced,
  accent,
}: {
  loading: boolean;
  gameLogs: PlayerGameLog[];
  position: string;
  goatAdvanced: any;
  accent: string;
}) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"gamelog" | "advanced">("gamelog");

  return (
    <div className="mt-5">
      <button
        type="button"
        className="w-full h-11 px-4 rounded-lg border border-border bg-transparent text-sm text-foreground hover:bg-secondary transition-colors flex items-center justify-between"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="font-medium">View Analysis</span>
        <span className="text-muted-foreground">{open ? "▴" : "▾"}</span>
      </button>

      <div
        className="overflow-hidden transition-[max-height,opacity] duration-300 ease-out"
        style={{
          maxHeight: open ? 2000 : 0,
          opacity: open ? 1 : 0,
        }}
        aria-hidden={!open}
      >
        <div className="pt-5">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setTab("gamelog")}
              className="h-9 px-3 rounded-lg border border-border text-sm transition-colors"
              style={{
                borderColor: tab === "gamelog" && accent ? accent : undefined,
              }}
            >
              Game Log
            </button>
            <button
              type="button"
              onClick={() => setTab("advanced")}
              className="h-9 px-3 rounded-lg border border-border text-sm transition-colors"
              style={{
                borderColor: tab === "advanced" && accent ? accent : undefined,
              }}
            >
              Advanced Stats
            </button>
          </div>

          <div className="mt-4">
            {tab === "gamelog" ? (
              gameLogs.length > 0 ? (
                <AdvancedStatsTable gameLogs={gameLogs} position={position} />
              ) : (
                <div className="rounded-xl border border-border p-6 text-center">
                  <p className="text-muted-foreground">
                    {loading ? "Loading game logs..." : "No game logs available for this player and season."}
                  </p>
                </div>
              )
            ) : (
              <GoatAdvancedStats data={goatAdvanced} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

