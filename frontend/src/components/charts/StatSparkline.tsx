import { useId } from "react";
import { AreaChart, Area, ResponsiveContainer, Tooltip, ReferenceLine } from "recharts";

interface StatSparklineProps {
  data: number[];
  average?: number;
  unit?: string;
  className?: string;
}

export function StatSparkline({ data, average, unit = 'Yds', className }: StatSparklineProps) {
  // Need at least 2 data points for a chart
  if (!data || data.length < 2) return null;

  // Transform data for Recharts (week starts at the first game shown)
  const chartData = data.map((value, index) => ({ 
    value, 
    week: index + 1,
  }));

  // Determine color based on trend (last vs first)
  const firstValue = data[0];
  const lastValue = data[data.length - 1];
  const isPositive = lastValue > firstValue;
  const isFlat = lastValue === firstValue;

  const strokeColor = isPositive ? '#10b981' : isFlat ? '#9ca3af' : '#f43f5e';
  const reactId = useId();
  // `useId()` can contain ":"; sanitize to keep the SVG id/url reference robust.
  const gradientId = `gradient-${reactId}-${isPositive ? "positive" : isFlat ? "flat" : "negative"}`.replace(/:/g, "");

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;
    
    const { value, week } = payload[0].payload;
    
    return (
      <div className="bg-black text-white text-xs rounded px-2 py-1 shadow-lg border border-border/20">
        <div className="font-mono font-bold">{value} {unit}</div>
        <div className="text-muted-foreground text-[10px]">Game {week}</div>
      </div>
    );
  };

  // Custom dot for the last point
  const CustomDot = (props: any) => {
    const { cx, cy, index } = props;
    // Only render dot on the last point
    if (index !== data.length - 1) return null;
    
    return (
      <circle 
        cx={cx} 
        cy={cy} 
        r={4} 
        fill={strokeColor} 
        stroke="white" 
        strokeWidth={2}
      />
    );
  };

  return (
    <div className={className} style={{ width: '100%', height: 50 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={strokeColor} stopOpacity={0.4} />
              <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          
          {/* Optional average reference line */}
          {average !== undefined && (
            <ReferenceLine 
              y={average} 
              stroke="#6b7280" 
              strokeDasharray="3 3" 
              strokeWidth={1}
              strokeOpacity={0.3}
            />
          )}
          
          <Tooltip content={<CustomTooltip />} cursor={false} />
          
          <Area 
            type="monotone" 
            dataKey="value" 
            stroke={strokeColor}
            strokeWidth={2.5}
            fill={`url(#${gradientId})`}
            dot={<CustomDot />}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

