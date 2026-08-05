"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Mail, User as UserIcon, Calendar, Github, AlertTriangle } from "lucide-react";

import { Navbar } from "@/components/Navbar";
import { RepositoryList } from "@/components/RepositoryList";
import { RepositoryChatPanel } from "@/components/RepositoryChatPanel";
import { AgentPanel } from "@/components/AgentPanel";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { User } from "@/types";

async function fetchCurrentUser() {
  const response = await api.get<User>("/auth/me");
  return response.data;
}

export default function DashboardPage() {
  const router = useRouter();
  const [token, setTokenValue] = useState<string | null>(null);
  const [checkedAuth, setCheckedAuth] = useState(false);
  const [activeTab, setActiveTab] = useState<"repos" | "chat" | "agents">("repos");

  useEffect(() => {
    const storedToken = getToken();
    setTokenValue(storedToken);
    setCheckedAuth(true);

    if (!storedToken) {
      router.replace("/");
    }
  }, [router]);

  const userQuery = useQuery({
    queryKey: ["current-user"],
    queryFn: fetchCurrentUser,
    enabled: Boolean(token),
  });

  if (!checkedAuth || !token) {
    return null;
  }

  return (
    <main className="min-h-screen bg-background text-foreground transition-colors duration-200">
      <Navbar />

      <div className="mx-auto max-w-6xl space-y-8 px-4 py-8">
        {/* Profile Card Section */}
        <section className="relative overflow-hidden rounded-xl border border-border/50 bg-card p-6 shadow-sm glow-card">
          {/* Subtle decoration background */}
          <div className="absolute -right-16 -top-16 w-36 h-36 bg-primary/5 rounded-full blur-xl pointer-events-none" />

          {userQuery.isLoading ? (
            <div className="flex items-center gap-4 animate-pulse">
              <div className="h-16 w-16 bg-muted rounded-full" />
              <div className="space-y-2">
                <div className="h-4 w-28 bg-muted rounded" />
                <div className="h-6 w-44 bg-muted rounded" />
              </div>
            </div>
          ) : userQuery.isError ? (
            <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-xs font-semibold text-red-600 dark:text-red-400 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              <span>Could not load account details. Please sign out and log back in.</span>
            </div>
          ) : userQuery.data ? (
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                {userQuery.data.avatar_url ? (
                  <div className="relative h-16 w-16 shrink-0 rounded-full border-2 border-primary/20 hover:border-primary/40 transition-colors overflow-hidden">
                    <Image
                      src={userQuery.data.avatar_url}
                      alt={`${userQuery.data.username} avatar`}
                      fill
                      sizes="64px"
                      className="object-cover"
                    />
                  </div>
                ) : (
                  <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-2 border-primary/20 bg-secondary/80 text-primary">
                    <UserIcon className="h-8 w-8" />
                  </div>
                )}
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h1 className="text-2xl font-bold tracking-tight text-foreground">
                      {userQuery.data.username}
                    </h1>
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold tracking-wider uppercase bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                      <Github className="h-2.5 w-2.5" />
                      Developer
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                    {userQuery.data.email ? (
                      <span className="flex items-center gap-1">
                        <Mail className="h-3.5 w-3.5" />
                        {userQuery.data.email}
                      </span>
                    ) : null}
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5" />
                      Joined {new Date(userQuery.data.created_at).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric'
                      })}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </section>

        {/* Dashboard Tab Selector */}
        <div className="flex border-b border-border/60 gap-4">
          <button
            onClick={() => setActiveTab("repos")}
            className={`pb-3 text-sm font-semibold relative transition-colors ${
              activeTab === "repos" ? "text-primary" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Repositories
            {activeTab === "repos" && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />
            )}
          </button>
          <button
            onClick={() => setActiveTab("chat")}
            className={`pb-3 text-sm font-semibold relative transition-colors ${
              activeTab === "chat" ? "text-primary" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            RAG Chat
            {activeTab === "chat" && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />
            )}
          </button>
          <button
            onClick={() => setActiveTab("agents")}
            className={`pb-3 text-sm font-semibold relative transition-colors ${
              activeTab === "agents" ? "text-primary" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            AI Code Agents
            {activeTab === "agents" && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />
            )}
          </button>
        </div>

        {/* Tab Contents */}
        <div className="space-y-6">
          {activeTab === "repos" && <RepositoryList />}
          {activeTab === "chat" && <RepositoryChatPanel />}
          {activeTab === "agents" && <AgentPanel />}
        </div>
      </div>
    </main>

  );
}
