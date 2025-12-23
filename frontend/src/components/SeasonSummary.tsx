import { Player } from "@/types/player";
import { StatCard } from "./StatCard";
import { cn, getStatTrend } from "@/lib/utils";
import { TeamLogo } from "./TeamLogo";
import { useState } from "react";

interface SeasonSummaryProps {
  player: Player;
}

export function SeasonSummary({ player }: SeasonSummaryProps) {
  const stats = player.seasonTotals || player;
  const isReceiver = ['WR', 'TE'].includes(player.position || '');
  const isQB = (player.position || '').toUpperCase() === 'QB';
  const photoUrl = player.photoUrl;
  const [imgError, setImgError] = useState(false);
  const showImage = !!photoUrl && !imgError;
  
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 opacity-0 animate-slide-up" style={{ animationDelay: '100ms' }}>
        <div className="w-20 h-20 rounded-2xl bg-secondary overflow-hidden ring-2 ring-border">
          {showImage ? (
            <img
              src={photoUrl}
              alt={player.player_name}
              className="w-full h-full object-cover"
              loading="lazy"
              onError={(e) => {
                setImgError(true);
              }}
            />
          ) : null}
          <div className={cn(
            "w-full h-full flex items-center justify-center text-muted-foreground text-2xl font-bold",
            showImage && "hidden"
          )}>
            {player.player_name.split(' ').map(n => n[0]).join('')}
          </div>
        </div>
        <div>
          <h2 className="text-2xl font-bold text-foreground">{player.player_name}</h2>
          <div className="flex items-center gap-2 text-muted-foreground">
            <TeamLogo team={player.team} size="md" />
            <p>{player.team} • {player.position} • {stats.season || player.season} Season</p>
          </div>
        </div>
      </div>

      {isQB ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <StatCard 
            label="Pass Yards" 
            value={stats.passingYards || 0} 
            subValue={`${stats.games || 0} games`}
            trend={getStatTrend('passing yards', stats.passingYards || 0)}
            delay={150}
          />
          <StatCard 
            label="Pass TDs" 
            value={stats.passingTouchdowns || 0} 
            subValue="Passing"
            trend={getStatTrend('touchdown', stats.passingTouchdowns || 0)}
            delay={200}
          />
          <StatCard 
            label="Rush Yards" 
            value={stats.rushingYards || 0} 
            subValue={`${Number(stats.avgYardsPerRush || 0).toFixed(1)} avg`}
            trend={getStatTrend('rushingYards', stats.rushingYards || 0)}
            delay={250}
          />
          <StatCard 
            label="Rush TDs" 
            value={stats.rushingTouchdowns || 0} 
            subValue="Rushing"
            trend={getStatTrend('touchdown', stats.rushingTouchdowns || 0)}
            delay={300}
          />
          <StatCard 
            label="INT" 
            value={stats.passingInterceptions || 0} 
            subValue={`${typeof stats.qbRating === "number" ? stats.qbRating.toFixed(1) : "—"} rating`}
            delay={350}
          />
        </div>
      ) : isReceiver ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard 
            label="Receptions" 
            value={stats.receptions || 0} 
            subValue={`${stats.games || 0} games`}
            delay={150}
          />
          <StatCard 
            label="Rec Yards" 
            value={stats.receivingYards || 0} 
            subValue={`${Number(stats.avgYardsPerCatch || 0).toFixed(1)} avg`}
            trend={getStatTrend('receivingYards', stats.receivingYards || 0)}
            delay={200}
          />
          <StatCard 
            label="Targets" 
            value={stats.targets || 0} 
            subValue={`${((stats.targets || 0) / (stats.games || 1)).toFixed(1)} per game`}
            delay={250}
          />
          <StatCard 
            label="Rec TDs" 
            value={stats.receivingTouchdowns || 0} 
            subValue="Touchdowns"
            trend={getStatTrend('touchdown', stats.receivingTouchdowns || 0)}
            delay={300}
          />
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard 
            label="Rush Attempts" 
            value={stats.rushAttempts || 0} 
            subValue={`${stats.games || 0} games`}
            delay={150}
          />
          <StatCard 
            label="Rush Yards" 
            value={stats.rushingYards || 0} 
            subValue={`${Number(stats.avgYardsPerRush || 0).toFixed(1)} avg`}
            trend={getStatTrend('rushingYards', stats.rushingYards || 0)}
            delay={200}
          />
          <StatCard 
            label="Rush TDs" 
            value={stats.rushingTouchdowns || 0} 
            subValue="Touchdowns"
            trend={getStatTrend('touchdown', stats.rushingTouchdowns || 0)}
            delay={250}
          />
          <StatCard 
            label="Receptions" 
            value={stats.receptions || 0} 
            subValue={`${stats.receivingYards || 0} rec yards`}
            delay={300}
          />
        </div>
      )}
    </div>
  );
}

