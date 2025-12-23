import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Database, RefreshCw, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useTheme } from "@/context/theme";

interface HeaderProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function Header({ onRefresh, isRefreshing }: HeaderProps) {
  const { theme, toggleTheme } = useTheme();
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    if (!settingsOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSettingsOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [settingsOpen]);

  return (
    <header className="border-b border-border bg-card/50 backdrop-blur-xl sticky top-0 z-50">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
            <Database className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-foreground">Fantasy Analytics</h1>
            <p className="text-xs text-muted-foreground">Advanced NFL Metrics</p>
          </div>
          </div>

          <nav className="hidden md:flex items-center gap-2">
            <NavLink
              to="/"
              className={({ isActive }) =>
                cn(
                  "px-3 py-1.5 rounded-lg text-sm transition-colors",
                  isActive ? "bg-primary/10 text-foreground" : "text-muted-foreground hover:text-foreground"
                )
              }
            >
              Players
            </NavLink>
            <NavLink
              to="/leaderboards"
              className={({ isActive }) =>
                cn(
                  "px-3 py-1.5 rounded-lg text-sm transition-colors",
                  isActive ? "bg-primary/10 text-foreground" : "text-muted-foreground hover:text-foreground"
                )
              }
            >
              Leaderboards
            </NavLink>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <Button 
            variant="glow" 
            size="sm" 
            onClick={onRefresh}
            disabled={isRefreshing}
            className="gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            {isRefreshing ? 'Refreshing...' : 'Refresh Data'}
          </Button>
          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Settings"
              aria-expanded={settingsOpen}
              onClick={() => setSettingsOpen((v) => !v)}
            >
            <Settings className="w-5 h-5" />
            </Button>

            {settingsOpen ? (
              <>
                {/* click-outside backdrop */}
                <button
                  type="button"
                  className="fixed inset-0 z-40 cursor-default"
                  aria-label="Close settings"
                  onClick={() => setSettingsOpen(false)}
                />

                <div
                  className="absolute right-0 mt-2 w-64 rounded-xl border border-border bg-card shadow-lg p-3 z-50"
                  role="dialog"
                  aria-label="Settings"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-foreground">Theme</div>
                      <div className="text-xs text-muted-foreground truncate">Light / Dark</div>
                    </div>
                    <button
                      type="button"
                      className="h-9 px-3 rounded-lg border border-border bg-transparent text-sm text-foreground hover:bg-secondary transition-colors"
                      onClick={toggleTheme}
                    >
                      {theme === "light" ? "Switch to Dark" : "Switch to Light"}
                    </button>
                  </div>

                  <div className="mt-3 pt-3 border-t border-border">
                    <button
                      type="button"
                      className="w-full h-9 px-3 rounded-lg bg-secondary text-sm text-foreground hover:bg-secondary/80 transition-colors"
                      onClick={() => setSettingsOpen(false)}
                    >
                      Close
                    </button>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}

