import { useEffect, useState, useRef } from "react";

interface CountUpProps {
  end: number;
  duration?: number;
  className?: string;
}

export function CountUp({ end, duration = 1400, className }: CountUpProps) {
  const [count, setCount] = useState(0);
  const frameRef = useRef<number>();
  const startTimeRef = useRef<number>();

  useEffect(() => {
    // Reset when end value changes
    setCount(0);
    startTimeRef.current = undefined;

    const animate = (timestamp: number) => {
      if (!startTimeRef.current) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // Ease-out cubic function for smooth deceleration
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(eased * end);

      setCount(current);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        setCount(end); // Ensure we end at exact value
      }
    };

    frameRef.current = requestAnimationFrame(animate);

    return () => {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [end, duration]);

  // Format number with commas
  const formatted = count.toLocaleString('en-US');

  return <span className={className}>{formatted}</span>;
}

