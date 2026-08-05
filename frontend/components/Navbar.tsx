"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BrainCircuit, LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { clearToken, getToken } from "@/lib/auth";

export function Navbar() {
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    setIsLoggedIn(Boolean(getToken()));
  }, []);

  const handleLogout = () => {
    clearToken();
    setIsLoggedIn(false);
    router.push("/");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 group">
          <div className="p-1.5 rounded-lg bg-primary/10 text-primary group-hover:scale-105 transition-transform">
            <BrainCircuit className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
            RepoMind <span className="text-primary">AI</span>
          </span>
        </Link>

        <div className="flex items-center gap-4">
          <ThemeToggle />
          {isLoggedIn ? (
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="gap-2 border-border/80 bg-background/50 hover:bg-secondary text-sm font-medium"
            >
              <LogOut className="h-4 w-4" />
              <span>Logout</span>
            </Button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
