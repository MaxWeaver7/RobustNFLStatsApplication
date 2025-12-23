import { useState } from "react";
import { Player } from "@/types/player";
import { cn } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import { TeamLogo } from "./TeamLogo";

interface PlayerCardProps {
  player: Player;
  isSelected?: boolean;
  onClick?: () => void;
  delay?: number;
}

export function PlayerCard({ player, isSelected, onClick, delay = 0 }: PlayerCardProps) {
  const isReceiver = ['WR', 'TE'].includes(player.position || '');
  const isQB = (player.position || '').toUpperCase() === 'QB';
  const seasonTotals = player.seasonTotals || player;
  const primaryStat = isQB
    ? (seasonTotals.passingYards || 0)
    : isReceiver
      ? (seasonTotals.receivingYards || 0)
      : (seasonTotals.rushingYards || 0);
  const primaryLabel = isQB ? 'PASS YDS' : (isReceiver ? 'REC YDS' : 'RUSH YDS');
  const photoUrl = player.photoUrl;
  const [imgError, setImgError] = useState(false);
  const showImage = !!photoUrl && !imgError;
  
  return (
    <div
      onClick={onClick}
      className={cn(
        "glass-card rounded-xl p-4 cursor-pointer transition-all duration-300 opacity-0 animate-slide-up group",
        isSelected && "ring-2 ring-primary glow-primary",
        !isSelected && "hover:ring-1 hover:ring-border/50"
      )}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-center gap-4">
        <div className="relative">
          <div className="w-14 h-14 rounded-full bg-secondary overflow-hidden ring-2 ring-border">
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
              "w-full h-full flex items-center justify-center text-muted-foreground text-lg font-bold",
              showImage && "hidden"
            )}>
              {player.player_name.split(' ').map(n => n[0]).join('')}
            </div>
          </div>
          <div className="absolute -bottom-1 -right-1 bg-secondary text-xs font-bold px-1.5 py-0.5 rounded-md border border-border">
            {player.position}
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-foreground truncate">{player.player_name}</h3>
          <div className="flex items-center gap-1.5">
            <TeamLogo team={player.team} size="sm" />
            <p className="text-sm text-muted-foreground">{player.team}</p>
          </div>
        </div>

        <div className="text-right mr-2">
          <p className="text-xl font-bold font-mono text-primary">
            {primaryStat}
          </p>
          <p className="text-xs text-muted-foreground">{primaryLabel}</p>
        </div>

        <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
      </div>

      {isQB ? (
        <div className="grid grid-cols-4 gap-2 mt-4 pt-4 border-t border-border">
          <div className="text-center">
            <p className="text-lg font-mono font-semibold text-primary">{seasonTotals.passingYards || 0}</p>
            <p className="text-xs text-muted-foreground">PASS YDS</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-mono font-semibold">{seasonTotals.passingTouchdowns || 0}</p>
            <p className="text-xs text-muted-foreground">PASS TD</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-mono font-semibold">{seasonTotals.rushingYards || 0}</p>
            <p className="text-xs text-muted-foreground">RUSH YDS</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-mono font-semibold">{seasonTotals.rushingTouchdowns || 0}</p>
            <p className="text-xs text-muted-foreground">RUSH TD</p>
          </div>
        </div>
      ) : isReceiver ? (
        <div className="grid grid-cols-4 gap-2 mt-4 pt-4 border-t border-border">
          <div className="text-center">
            <p className="text-lg font-mono font-semibold">{seasonTotals.targets || 0}</p>
            <p className="text-xs text-muted-foreground">TGT</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-mono font-semibold">{seasonTotals.receptions || 0}</p>
            <p className="text-xs text-muted-foreground">REC</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-mono font-semibold text-primary">{seasonTotals.receivingYards || 0}</p>
            <p className="text-xs text-muted-foreground">YDS</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-mono font-semibold">{seasonTotals.receivingTouchdowns || 0}</p>
            <p className="text-xs text-muted-foreground">TD</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-2 mt-4 pt-4 border-t border-border">
          <div className="text-center">
            <p className="text-lg font-mono font-semibold">{seasonTotals.rushAttempts || 0}</p>
            <p className="text-xs text-muted-foreground">ATT</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-mono font-semibold text-primary">{Number(seasonTotals.avgYardsPerRush || 0).toFixed(1)}</p>
            <p className="text-xs text-muted-foreground">YPC</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-mono font-semibold">{seasonTotals.rushingTouchdowns || 0}</p>
            <p className="text-xs text-muted-foreground">TD</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-mono font-semibold">{seasonTotals.receptions || 0}</p>
            <p className="text-xs text-muted-foreground">REC</p>
          </div>
        </div>
      )}
    </div>
  );
}

