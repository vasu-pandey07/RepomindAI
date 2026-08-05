"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { GitFork, Star, Database, CheckCircle2, AlertCircle, RefreshCw, Layers } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Repository, RepositoryIndexStatus } from "@/types";

export function RepositoryCard({ repository }: { repository: Repository }) {
  // Query indexing status
  const { data: indexStatus, isLoading: isStatusLoading, refetch } = useQuery<RepositoryIndexStatus>({
    queryKey: ["repository-status", repository.id],
    queryFn: async () => {
      const response = await api.get<RepositoryIndexStatus>(`/repositories/${repository.id}/index-status`);
      return response.data;
    },
  });

  // Mutation to trigger indexing
  const indexMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/repositories/${repository.id}/index`);
      return response.data;
    },
    onSuccess: () => {
      refetch();
    },
  });

  const isIndexed = indexStatus?.indexed;
  const isPending = indexMutation.isPending;

  return (
    <article
      className={`relative flex flex-col justify-between rounded-xl border bg-card p-6 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md glow-card group ${
        isIndexed
          ? "border-emerald-500/20 dark:border-emerald-500/10 shadow-emerald-500/[0.01]"
          : "border-border/60"
      }`}
    >
      {/* Visual top highlight for indexed repos */}
      {isIndexed && (
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500/40 via-emerald-500/10 to-transparent" />
      )}

      <div>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-base font-bold tracking-tight text-foreground group-hover:text-primary transition-colors">
              {repository.name}
            </h3>
            <p className="text-xs font-mono text-muted-foreground">{repository.full_name}</p>
          </div>
          {repository.language ? (
            <span className="rounded-full bg-secondary/80 px-2.5 py-0.5 text-xs font-semibold text-secondary-foreground border border-border/50">
              {repository.language}
            </span>
          ) : null}
        </div>

        <p className="mt-4 min-h-[3rem] text-sm text-muted-foreground/90 line-clamp-2 leading-relaxed">
          {repository.description || "No description provided."}
        </p>

        {/* Index Status Section */}
        <div className="mt-4 pt-4 border-t border-border/40 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {isStatusLoading ? (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <RefreshCw className="h-3 w-3 animate-spin" />
                <span>Checking index...</span>
              </div>
            ) : isIndexed ? (
              <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>Vector Indexed</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-xs font-medium text-amber-600 dark:text-amber-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>Not Indexed</span>
              </div>
            )}
          </div>

          {!isStatusLoading && isIndexed && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground font-mono bg-secondary/40 px-2 py-1 rounded">
              <span className="flex items-center gap-1">
                <Database className="h-3.5 w-3.5 text-muted-foreground/75" />
                {indexStatus.files} files
              </span>
              <span className="w-1 h-1 bg-border rounded-full" />
              <span className="flex items-center gap-1">
                <Layers className="h-3.5 w-3.5 text-muted-foreground/75" />
                {indexStatus.chunks} chunks
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between gap-4">
        {/* Repo Stats */}
        <div className="flex items-center gap-4 text-xs font-semibold text-muted-foreground/80">
          <span className="inline-flex items-center gap-1 hover:text-foreground transition-colors">
            <Star className="h-3.5 w-3.5 text-amber-500 fill-amber-500/20" />
            {repository.stars}
          </span>
          <span className="inline-flex items-center gap-1 hover:text-foreground transition-colors">
            <GitFork className="h-3.5 w-3.5" />
            {repository.forks}
          </span>
        </div>

        {/* Index Action Button */}
        <Button
          size="sm"
          onClick={() => indexMutation.mutate()}
          disabled={isPending || isStatusLoading}
          variant={isIndexed ? "outline" : "default"}
          className={`gap-1.5 px-4 h-9 font-medium shadow-sm transition-all duration-200 active:scale-95 ${
            isIndexed
              ? "border-border hover:bg-emerald-500/5 hover:text-emerald-600 dark:hover:text-emerald-400 hover:border-emerald-500/30"
              : "bg-primary text-primary-foreground hover:bg-primary/95"
          }`}
        >
          {isPending ? (
            <>
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              <span>Indexing...</span>
            </>
          ) : isIndexed ? (
            <>
              <RefreshCw className="h-3.5 w-3.5 opacity-80" />
              <span>Update Index</span>
            </>
          ) : (
            <>
              <Database className="h-3.5 w-3.5" />
              <span>Index Repository</span>
            </>
          )}
        </Button>
      </div>

      {/* Indexing status helper alert inside the card when indexing is active */}
      {isPending && (
        <div className="absolute inset-0 bg-background/80 dark:bg-background/90 backdrop-blur-[1px] flex flex-col items-center justify-center p-4 text-center z-10 animate-fade-in">
          <RefreshCw className="h-8 w-8 text-primary animate-spin mb-3" />
          <p className="text-sm font-semibold text-foreground">Indexing Repository</p>
          <p className="text-xs text-muted-foreground mt-1 max-w-[200px]">
            Cloning files, chunking code, and generating vector embeddings...
          </p>
        </div>
      )}
    </article>
  );
}
