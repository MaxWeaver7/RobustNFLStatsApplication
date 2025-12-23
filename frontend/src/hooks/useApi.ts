import { useQuery } from '@tanstack/react-query';
import { Player, FilterOptions, PlayerGameLog } from '@/types/player';

const API_BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}

export function useFilterOptions() {
  return useQuery({
    queryKey: ['options'],
    queryFn: () => fetchJson<FilterOptions>(`${API_BASE}/options`),
  });
}

export function usePlayers(season?: number, position?: string, team?: string) {
  const params = new URLSearchParams();
  if (season) params.set('season', season.toString());
  if (position) params.set('position', position);
  if (team) params.set('team', team);
  // User requested returning thousands (avoid artificial caps that hide players).
  params.set('limit', '12000');
  
  return useQuery({
    queryKey: ['players', season, position, team],
    queryFn: () => fetchJson<{ players: Player[] }>(`${API_BASE}/players?${params.toString()}`),
  });
}

export function usePlayerDetail(playerId: string, season: number) {
  return useQuery({
    queryKey: ['player', playerId, season],
    queryFn: () => fetchJson<{ player: Player; gameLogs: PlayerGameLog[] }>(`${API_BASE}/player/${playerId}?season=${season}`),
    enabled: !!playerId && !!season,
  });
}

export function useSummary() {
  return useQuery({
    queryKey: ['summary'],
    queryFn: () => fetchJson<any>(`${API_BASE}/summary`),
  });
}


