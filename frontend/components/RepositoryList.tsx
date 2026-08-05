"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Search, Filter, Database, AlertTriangle } from "lucide-react";
import { useState } from "react";

import { RepositoryCard } from "@/components/RepositoryCard";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Repository } from "@/types";

async function fetchRepositories() {
  const response = await api.get<Repository[]>("/repositories");
  return response.data;
}

async function syncRepositories() {
  const response = await api.post<Repository[]>("/repositories/sync");
  return response.data;
}

export function RepositoryList() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLanguage, setSelectedLanguage] = useState("all");

  const repositoriesQuery = useQuery({
    queryKey: ["repositories"],
    queryFn: fetchRepositories,
  });

  const syncMutation = useMutation({
    mutationFn: syncRepositories,
    onSuccess: (repositories) => {
      queryClient.setQueryData(["repositories"], repositories);
    },
  });

  if (repositoriesQuery.isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="h-12 w-48 bg-muted animate-pulse rounded-lg" />
          <div className="h-10 w-36 bg-muted animate-pulse rounded-lg" />
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          {[1, 2, 4].map((i) => (
            <div key={i} className="h-44 border border-border/60 bg-card rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (repositoriesQuery.isError) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 flex gap-3 text-red-600 dark:text-red-400 items-start max-w-2xl mx-auto shadow-sm">
        <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
        <div>
          <h4 className="font-bold text-sm">Authentication or network issue</h4>
          <p className="text-xs text-red-600/80 dark:text-red-400/80 mt-1">
            Unable to load repositories. Please try signing out and signing back in with GitHub.
          </p>
        </div>
      </div>
    );
  }

  const repositories = repositoriesQuery.data ?? [];

  // Get unique list of languages
  const languages = Array.from(
    new Set(repositories.map((repo) => repo.language).filter(Boolean))
  ) as string[];

  // Filter repositories
  const filteredRepositories = repositories.filter((repo) => {
    const matchesSearch =
      repo.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      repo.full_name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesLanguage = selectedLanguage === "all" || repo.language === selectedLanguage;
    return matchesSearch && matchesLanguage;
  });

  return (
    <section className="space-y-6">
      {/* Header section with Stats & Sync Action */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center bg-card border border-border/50 p-6 rounded-xl shadow-sm">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">GitHub Repositories</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {repositories.length} {repositories.length === 1 ? "repository" : "repositories"} synced with RepoMind.
          </p>
        </div>
        <Button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="gap-2 bg-primary hover:bg-primary/95 text-primary-foreground font-medium shadow-sm transition-transform active:scale-[0.98]"
        >
          <RefreshCw className={syncMutation.isPending ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
          {syncMutation.isPending ? "Syncing Repos..." : "Sync from GitHub"}
        </Button>
      </div>

      {syncMutation.isError ? (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-xs font-semibold text-red-600 dark:text-red-400 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          <span>Sync failed. Please check your GitHub token or try again later.</span>
        </div>
      ) : null}

      {/* Filter and Search controls */}
      {repositories.length > 0 && (
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/75" />
            <input
              type="text"
              placeholder="Search synced repositories..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-card hover:bg-card/80 focus:bg-card border border-border/80 focus:border-primary/80 focus:ring-1 focus:ring-primary/80 rounded-xl pl-9 pr-4 py-2.5 text-sm text-foreground placeholder-muted-foreground/70 outline-none transition-all"
            />
          </div>

          <div className="relative w-full sm:w-48 flex items-center">
            <Filter className="absolute left-3 h-4 w-4 text-muted-foreground/75 pointer-events-none" />
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              className="w-full bg-card hover:bg-card/80 border border-border/80 focus:border-primary/80 focus:ring-1 focus:ring-primary/80 rounded-xl pl-9 pr-8 py-2.5 text-sm text-foreground outline-none appearance-none transition-all cursor-pointer"
            >
              <option value="all">All Languages</option>
              {languages.map((lang) => (
                <option key={lang} value={lang}>
                  {lang}
                </option>
              ))}
            </select>
            <div className="absolute right-3 pointer-events-none text-muted-foreground/75 text-xs">▼</div>
          </div>
        </div>
      )}

      {/* Repositories Display Grid */}
      {repositories.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/80 bg-card/50 p-12 text-center flex flex-col items-center max-w-xl mx-auto">
          <Database className="h-10 w-10 text-muted-foreground/60 mb-4" />
          <h3 className="text-lg font-bold text-foreground">No repositories found</h3>
          <p className="mt-2 text-sm text-muted-foreground max-w-sm leading-relaxed">
            Connect and sync your repositories from GitHub to get started with code intelligence.
          </p>
          <Button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="mt-6 gap-2"
          >
            <RefreshCw className={syncMutation.isPending ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Sync Repositories
          </Button>
        </div>
      ) : filteredRepositories.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-12 text-center max-w-md mx-auto">
          <p className="text-sm text-muted-foreground">No repositories match your search filters.</p>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {filteredRepositories.map((repository) => (
            <RepositoryCard key={repository.id} repository={repository} />
          ))}
        </div>
      )}
    </section>
  );
}
