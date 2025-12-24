import { cn } from "@/lib/utils";

interface PlayerDossierSkeletonProps {
  position?: string;
  className?: string;
}

export function PlayerDossierSkeleton({ position, className }: PlayerDossierSkeletonProps) {
  // Determine grid columns based on position
  const isQB = (position || '').toUpperCase() === 'QB';
  const isReceiver = ['WR', 'TE'].includes((position || '').toUpperCase());
  
  // QB has 5 stat cards, others have 4
  const statCount = isQB ? 5 : 4;
  
  return (
    <div className={cn("space-y-4", className)}>
      {/* Header Section - Player Info */}
      <div className="flex items-center gap-4 opacity-0 animate-slide-up" style={{ animationDelay: '100ms' }}>
        {/* Avatar Skeleton */}
        <div className="w-20 h-20 rounded-2xl bg-muted/20 animate-pulse ring-2 ring-border" />
        
        <div className="flex-1 space-y-3">
          {/* Name Skeleton */}
          <div className="h-7 w-48 bg-muted/20 animate-pulse rounded-lg" />
          
          {/* Team/Position Line */}
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-muted/20 animate-pulse" />
            <div className="h-4 w-64 bg-muted/20 animate-pulse rounded" />
          </div>
          
          {/* Bio Chips */}
          <div className="flex flex-wrap gap-2">
            <div className="h-6 w-16 bg-muted/20 animate-pulse rounded-full" />
            <div className="h-6 w-20 bg-muted/20 animate-pulse rounded-full" />
            <div className="h-6 w-24 bg-muted/20 animate-pulse rounded-full" />
            <div className="h-6 w-20 bg-muted/20 animate-pulse rounded-full" />
          </div>
        </div>
      </div>

      {/* Stat Cards Grid */}
      <div className={cn(
        "grid gap-3",
        isQB ? "grid-cols-2 md:grid-cols-5" : "grid-cols-2 md:grid-cols-4"
      )}>
        {Array.from({ length: statCount }).map((_, idx) => (
          <div
            key={idx}
            className="glass-card rounded-xl p-4 opacity-0 animate-slide-up"
            style={{ animationDelay: `${150 + idx * 50}ms` }}
          >
            {/* Label */}
            <div className="h-3 w-20 bg-muted/20 animate-pulse rounded mb-2" />
            
            {/* Value */}
            <div className="h-8 w-16 bg-muted/20 animate-pulse rounded mb-2" />
            
            {/* Sub Value */}
            <div className="h-3 w-24 bg-muted/20 animate-pulse rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}

