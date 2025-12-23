import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/Header";
import { PlayerCard } from "@/components/PlayerCard";
import { SeasonSummary } from "@/components/SeasonSummary";
import { AdvancedStatsTable } from "@/components/AdvancedStatsTable";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useFilterOptions, usePlayers } from "@/hooks/useApi";
import { Player, PlayerGameLog } from "@/types/player";
import { useSearchParams } from "react-router-dom";

const Index = () => {
  const { data: options } = useFilterOptions();
  const [searchParams] = useSearchParams();
  const DEFAULT_SEASON = 2025;
  const [selectedSeason, setSelectedSeason] = useState<number>(options?.seasons?.[0] || DEFAULT_SEASON);
  const [selectedPosition, setSelectedPosition] = useState<string>('');
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [includePostseason, setIncludePostseason] = useState<boolean>(false);
  const [search, setSearch] = useState<string>("");

  const { data: playersData, isLoading: playersLoading, refetch } = usePlayers(
    selectedSeason,
    selectedPosition || undefined,
    selectedTeam || undefined
  );

  async function fetchJson<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  const { data: playerDetail, isLoading: detailLoading } = useQuery({
    queryKey: ["player", selectedPlayer?.player_id, selectedSeason, includePostseason],
    queryFn: () => {
      const pid = selectedPlayer?.player_id || "";
      const qs = new URLSearchParams({ season: String(selectedSeason) });
      if (includePostseason) qs.set("include_postseason", "1");
      return fetchJson<{ player: Player; gameLogs: PlayerGameLog[] }>(`/api/player/${pid}?${qs.toString()}`);
    },
    enabled: !!selectedPlayer?.player_id && !!selectedSeason,
  });

  const players = useMemo(() => playersData?.players || [], [playersData]);
  const filteredPlayers = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return players;
    return players.filter((p) => p.player_name.toLowerCase().includes(q));
  }, [players, search]);

  const visiblePlayers = filteredPlayers;

  const requestedPlayerId = (searchParams.get("player_id") || "").trim();
  const requestedSeason = Number(searchParams.get("season") || "");

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

  // After players load, select the requested player if present.
  useEffect(() => {
    if (!requestedPlayerId) return;
    if (players.length === 0) return;
    if (selectedPlayer?.player_id === requestedPlayerId) return;
    const p = players.find((x) => x.player_id === requestedPlayerId);
    if (p) setSelectedPlayer(p);
  }, [players, requestedPlayerId, selectedPlayer?.player_id]);

  // Auto-select first player when list changes
  useEffect(() => {
    if (visiblePlayers.length > 0 && !selectedPlayer) {
      setSelectedPlayer(visiblePlayers[0]);
    }
  }, [visiblePlayers, selectedPlayer]);

  const handleRefresh = () => {
    refetch();
  };

  const currentPlayer = playerDetail?.player || selectedPlayer;
  const gameLogs = playerDetail?.gameLogs || [];

  return (
    <div className="min-h-screen bg-background">
      <Header onRefresh={handleRefresh} isRefreshing={playersLoading} />
      
      <main className="container mx-auto px-4 py-8">
        {/* Filters */}
        <div className="glass-card rounded-xl p-4 mb-6 opacity-0 animate-slide-up">
          <h3 className="font-medium text-foreground mb-3">Filters</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="text-sm text-muted-foreground mb-2 block">Season</label>
              <Select value={selectedSeason.toString()} onValueChange={(value: string) => setSelectedSeason(Number(value))}>
                <SelectTrigger>
                  <SelectValue placeholder="Select season" />
                </SelectTrigger>
                <SelectContent>
                  {options?.seasons.map(season => (
                    <SelectItem key={season} value={season.toString()}>{season}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm text-muted-foreground mb-2 block">Position</label>
              <Select value={selectedPosition || "ALL"} onValueChange={(val) => setSelectedPosition(val === "ALL" ? "" : val)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Positions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">All Positions</SelectItem>
                  <SelectItem value="WR">WR - Wide Receiver</SelectItem>
                  <SelectItem value="RB">RB - Running Back</SelectItem>
                  <SelectItem value="TE">TE - Tight End</SelectItem>
                  <SelectItem value="QB">QB - Quarterback</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm text-muted-foreground mb-2 block">Team</label>
              <Select value={selectedTeam || "ALL"} onValueChange={(val) => setSelectedTeam(val === "ALL" ? "" : val)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Teams" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">All Teams</SelectItem>
                  {options?.teams.map(team => (
                    <SelectItem key={team} value={team}>{team}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
              <p className="text-xs text-muted-foreground mt-2">
                Postseason shows as weeks 19–22 (WC/DIV/CONF/SB).
              </p>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-12 gap-8">
          {/* Player List Sidebar */}
          <div className="lg:col-span-4 space-y-4">
            <div className="opacity-0 animate-fade-in">
              <h2 className="text-lg font-semibold text-foreground mb-1">Players</h2>
              <p className="text-sm text-muted-foreground mb-4">
                {playersLoading ? 'Loading players...' : `${filteredPlayers.length} players found`}
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
              
              {!playersLoading && filteredPlayers.length === 0 && (
                <div className="glass-card rounded-xl p-8 text-center">
                  <p className="text-muted-foreground">No players found for the selected filters.</p>
                </div>
              )}
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-8 space-y-6">
            {currentPlayer ? (
              <>
                <SeasonSummary player={currentPlayer} />
                
                {gameLogs.length > 0 ? (
                  <AdvancedStatsTable gameLogs={gameLogs} position={currentPlayer.position || 'RB'} />
                ) : (
                  <div className="glass-card rounded-xl p-8 text-center opacity-0 animate-slide-up" style={{ animationDelay: '400ms' }}>
                    <p className="text-muted-foreground">
                      {detailLoading ? 'Loading game logs...' : 'No game logs available for this player and season.'}
                    </p>
                  </div>
                )}
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

