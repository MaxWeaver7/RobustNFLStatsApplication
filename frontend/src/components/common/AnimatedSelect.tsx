import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface AnimatedSelectProps {
  label: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function AnimatedSelect({ label, options, value, onChange, className }: AnimatedSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    }
  }, [isOpen]);

  const handleSelect = (option: string) => {
    onChange(option);
    setIsOpen(false);
  };

  const displayValue = value || label;

  // Framer Motion Variants - "Turbo Mode"
  const containerVariants = {
    open: {
      clipPath: "inset(0% 0% 0% 0% round 10px)",
      transition: {
        type: "spring",
        bounce: 0,
        duration: 0.3,
        delayChildren: 0.1,
        staggerChildren: 0.01,
      },
    },
    closed: {
      clipPath: "inset(10% 50% 90% 50% round 10px)",
      transition: {
        type: "spring",
        bounce: 0,
        duration: 0.3,
      },
    },
  };

  const itemVariants = {
    open: {
      opacity: 1,
      y: 0,
      transition: { type: "spring", stiffness: 500, damping: 30 },
    },
    closed: {
      opacity: 0,
      y: 20,
      transition: { duration: 0.2 },
    },
  };

  return (
    <div ref={containerRef} className={cn("relative z-[50]", className)}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "w-full h-10 px-3 rounded-lg border border-border bg-card text-sm text-foreground",
          "hover:bg-secondary transition-colors flex items-center justify-between gap-2 relative",
          isOpen && "ring-2 ring-ring"
        )}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <span className="truncate">{displayValue}</span>
        <ChevronDown
          className={cn(
            "w-4 h-4 text-muted-foreground transition-transform duration-200",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {/* Animated Dropdown */}
      <AnimatePresence>
        {isOpen && (
          <motion.ul
            variants={containerVariants}
            initial="closed"
            animate="open"
            exit="closed"
            className="absolute top-full left-0 right-0 mt-2 bg-zinc-900 border border-zinc-700 shadow-xl rounded-lg overflow-hidden z-[9999] max-h-64 overflow-y-auto"
            role="listbox"
          >
            {options.map((option) => (
              <motion.li
                key={option}
                variants={itemVariants}
                onClick={() => handleSelect(option)}
                className={cn(
                  "px-4 py-2.5 text-sm cursor-pointer transition-colors",
                  option === value
                    ? "text-emerald-400 font-bold bg-zinc-800/50"
                    : "text-foreground hover:bg-zinc-800 hover:text-emerald-400"
                )}
                role="option"
                aria-selected={option === value}
              >
                {option}
              </motion.li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

