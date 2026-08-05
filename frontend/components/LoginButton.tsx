"use client";

import { Github } from "lucide-react";

import { Button } from "@/components/ui/button";

export function LoginButton() {
  const handleLogin = () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.location.href = `${apiUrl}/auth/github/login`;
  };

  return (
    <Button
      size="lg"
      onClick={handleLogin}
      className="gap-2 bg-slate-950 text-slate-50 hover:bg-slate-900 dark:bg-slate-50 dark:text-slate-950 dark:hover:bg-slate-100 transition-all duration-300 font-semibold px-6 py-5 rounded-xl shadow-md hover:shadow-xl hover:shadow-primary/10 active:scale-[0.98] transform"
    >
      <Github className="h-5 w-5 fill-current" />
      Connect GitHub Account
    </Button>
  );
}
