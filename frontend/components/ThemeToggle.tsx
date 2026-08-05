"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="w-9 h-9 rounded-full bg-secondary/50 animate-pulse flex items-center justify-center" />
    );
  }

  const isDark = theme === "dark";

  return (
    <Button
      variant="ghost"
      size="sm"
      className="w-9 h-9 px-0 rounded-full hover:bg-secondary/80 text-foreground transition-all duration-200"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label="Toggle theme"
    >
      {isDark ? (
        <Sun className="h-[1.15rem] w-[1.15rem] text-amber-400 hover:text-amber-300 transition-all animate-in fade-in zoom-in duration-300" />
      ) : (
        <Moon className="h-[1.15rem] w-[1.15rem] text-slate-700 hover:text-slate-900 transition-all animate-in fade-in zoom-in duration-300" />
      )}
    </Button>
  );
}
