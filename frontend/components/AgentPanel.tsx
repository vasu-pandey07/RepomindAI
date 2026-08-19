"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  FileText,
  GitPullRequest,
  CheckSquare,
  Code,
  Copy,
  Check,
  Loader2,
  AlertTriangle,
  Play,
  CheckCircle2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Repository } from "@/types";

async function fetchRepositories() {
  const response = await api.get<Repository[]>("/repositories");
  return response.data;
}

export function AgentPanel() {
  const [selectedRepoId, setSelectedRepoId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<"docs" | "pr" | "tests">("docs");

  // State for PR Review inputs/outputs
  const [changedFiles, setChangedFiles] = useState("app/main.py");
  const [prResult, setPrResult] = useState<{ review: string; issues_found: number } | null>(null);

  // State for Test Gen inputs/outputs
  const [testFilePath, setTestFilePath] = useState("app/core/config.py");
  const [testsResult, setTestsResult] = useState<string | null>(null);

  // State for Doc Gen outputs
  const [docsResult, setDocsResult] = useState<string | null>(null);

  // General UI status
  const [copied, setCopied] = useState(false);

  const repositoriesQuery = useQuery({
    queryKey: ["repositories-agents"],
    queryFn: fetchRepositories,
  });

  const repositories = useMemo(() => repositoriesQuery.data ?? [], [repositoriesQuery.data]);

  useEffect(() => {
    if (selectedRepoId === null && repositories.length > 0) {
      setSelectedRepoId(repositories[0].id);
    }
  }, [repositories, selectedRepoId]);

  // Mutations
  const docMutation = useMutation({
    mutationFn: async (repoId: number) => {
      const response = await api.post<{ documentation: string }>(`/agents/documentation/${repoId}`);
      return response.data;
    },
    onSuccess: (data) => {
      setDocsResult(data.documentation);
    },
  });

  const prMutation = useMutation({
    mutationFn: async (payload: { repository_id: number; changed_files: string[] }) => {
      const response = await api.post<{ review: string; issues_found: number }>("/agents/pr-review", payload);
      return response.data;
    },
    onSuccess: (data) => {
      setPrResult(data);
    },
  });

  const testMutation = useMutation({
    mutationFn: async (payload: { repository_id: number; file_path: string }) => {
      const response = await api.post<{ tests: string }>("/agents/tests", payload);
      return response.data;
    },
    onSuccess: (data) => {
      setTestsResult(data.tests);
    },
  });

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDocGenerate = () => {
    if (selectedRepoId === null || docMutation.isPending) return;
    setDocsResult(null);
    docMutation.mutate(selectedRepoId);
  };

  const handlePrReview = () => {
    if (selectedRepoId === null || prMutation.isPending) return;
    setPrResult(null);
    const filesList = changedFiles
      .split(",")
      .map((f) => f.trim())
      .filter((f) => f.length > 0);
    if (filesList.length === 0) return;
    prMutation.mutate({
      repository_id: selectedRepoId,
      changed_files: filesList,
    });
  };

  const handleTestGenerate = () => {
    if (selectedRepoId === null || testMutation.isPending) return;
    setTestsResult(null);
    const path = testFilePath.trim();
    if (!path) return;
    testMutation.mutate({
      repository_id: selectedRepoId,
      file_path: path,
    });
  };

  return (
    <section className="relative overflow-hidden rounded-xl border border-border/50 bg-card shadow-sm glow-card flex flex-col">
      {/* Panel Header */}
      <div className="border-b border-border/50 p-5 bg-card/40 backdrop-blur-sm">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="space-y-1">
            <h2 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Code className="h-5 w-5 text-primary" />
              AI Code Agents
            </h2>
            <p className="text-xs text-muted-foreground">
              Run automated, repository-aware workflows for documentation, reviews, and tests.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-muted-foreground">Target Repo:</label>
            <select
              className="h-9 rounded-lg border border-border/60 bg-background/50 px-3 py-1 text-xs font-medium text-foreground outline-none focus:ring-1 focus:ring-primary/40 transition-all cursor-pointer"
              value={selectedRepoId ?? ""}
              onChange={(e) => {
                setSelectedRepoId(Number(e.target.value));
                setDocsResult(null);
                setPrResult(null);
                setTestsResult(null);
              }}
              disabled={repositoriesQuery.isLoading || repositories.length === 0}
            >
              {repositories.length === 0 ? (
                <option value="">No repositories synced</option>
              ) : (
                repositories.map((repo) => (
                  <option key={repo.id} value={repo.id}>
                    {repo.name}
                  </option>
                ))
              )}
            </select>
          </div>
        </div>
      </div>

      {/* Tabs Switcher */}
      <div className="flex border-b border-border/40 bg-muted/20 px-2 py-1 gap-1">
        <button
          onClick={() => setActiveTab("docs")}
          className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-md transition-all ${
            activeTab === "docs"
              ? "bg-background text-primary shadow-sm"
              : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
          }`}
        >
          <FileText className="h-3.5 w-3.5" />
          Documentation Agent
        </button>
        <button
          onClick={() => setActiveTab("pr")}
          className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-md transition-all ${
            activeTab === "pr"
              ? "bg-background text-primary shadow-sm"
              : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
          }`}
        >
          <GitPullRequest className="h-3.5 w-3.5" />
          PR Review Agent
        </button>
        <button
          onClick={() => setActiveTab("tests")}
          className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-md transition-all ${
            activeTab === "tests"
              ? "bg-background text-primary shadow-sm"
              : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
          }`}
        >
          <CheckSquare className="h-3.5 w-3.5" />
          Test Gen Agent
        </button>
      </div>

      {/* Active Tab Area */}
      <div className="flex-1 p-6 space-y-6">
        {selectedRepoId === null ? (
          <div className="rounded-lg border border-dashed border-border/60 p-8 text-center bg-muted/10">
            <AlertTriangle className="mx-auto h-8 w-8 text-yellow-500/80 mb-2 animate-bounce" />
            <h4 className="text-sm font-semibold">No Active Repository Selected</h4>
            <p className="text-xs text-muted-foreground mt-1">
              Please sync and select a repository from the header dropdown to proceed.
            </p>
          </div>
        ) : (
          <>
            {/* DOCUMENTATION AGENT TAB */}
            {activeTab === "docs" && (
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-primary/5 border border-primary/10 rounded-lg p-4">
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-foreground">Documentation Architect</h3>
                    <p className="text-xs text-muted-foreground">
                      Generates complete repository specifications: APIs, data models, folder schema, setup instructions.
                    </p>
                  </div>
                  <Button
                    onClick={handleDocGenerate}
                    disabled={docMutation.isPending}
                    size="sm"
                    className="gap-2 shrink-0 shadow-sm"
                  >
                    {docMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Play className="h-3.5 w-3.5 fill-current" />
                    )}
                    {docMutation.isPending ? "Generating..." : "Run Doc Agent"}
                  </Button>
                </div>

                {docMutation.isPending && (
                  <div className="flex flex-col items-center justify-center p-12 border border-dashed rounded-lg bg-card/50 space-y-3">
                    <Loader2 className="h-8 w-8 text-primary animate-spin" />
                    <div className="space-y-1 text-center">
                      <p className="text-xs font-semibold text-foreground">LangGraph Node Execution Active</p>
                      <p className="text-[10px] text-muted-foreground animate-pulse">
                        RetrieveContextNode → AnalyzeCodeNode → GenerateResponseNode
                      </p>
                    </div>
                  </div>
                )}

                {docMutation.isError && (
                  <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-xs text-red-600 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span>
                      {(docMutation.error as any)?.response?.data?.detail ||
                        "Agent execution failed. Please verify repository indices are fully populated."}
                    </span>
                  </div>
                )}

                {docsResult && (
                  <div className="space-y-2 animate-fadeIn">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                        Generated Documentation
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCopy(docsResult)}
                        className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                      >
                        {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                        {copied ? "Copied" : "Copy MD"}
                      </Button>
                    </div>
                    <div className="max-h-[30rem] overflow-y-auto border border-border/50 rounded-lg p-5 bg-muted/10 font-mono text-xs leading-relaxed whitespace-pre-wrap select-text selection:bg-primary/20">
                      {docsResult}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* PR REVIEW AGENT TAB */}
            {activeTab === "pr" && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                    Changed Files (Comma separated)
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      className="h-9 flex-1 rounded-lg border border-border/60 bg-background px-3 text-xs outline-none focus:ring-1 focus:ring-primary/40 transition-all font-mono"
                      value={changedFiles}
                      onChange={(e) => setChangedFiles(e.target.value)}
                      placeholder="e.g. auth.py, app/main.py"
                      disabled={prMutation.isPending}
                    />
                    <Button
                      onClick={handlePrReview}
                      disabled={prMutation.isPending || !changedFiles.trim()}
                      size="sm"
                      className="gap-2 shrink-0 shadow-sm"
                    >
                      {prMutation.isPending ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Play className="h-3.5 w-3.5 fill-current" />
                      )}
                      {prMutation.isPending ? "Reviewing..." : "Run PR Agent"}
                    </Button>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Reviews selected files for bugs, security holes, and code smells using LangGraph retrieval hooks.
                  </p>
                </div>

                {prMutation.isPending && (
                  <div className="flex flex-col items-center justify-center p-12 border border-dashed rounded-lg bg-card/50 space-y-3">
                    <Loader2 className="h-8 w-8 text-primary animate-spin" />
                    <div className="space-y-1 text-center">
                      <p className="text-xs font-semibold text-foreground">Evaluating changed files patterns...</p>
                      <p className="text-[10px] text-muted-foreground animate-pulse">
                        Scanning pgvector chunks to isolate diff regressions
                      </p>
                    </div>
                  </div>
                )}

                {prMutation.isError && (
                  <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-xs text-red-600 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span>
                      {(prMutation.error as any)?.response?.data?.detail ||
                        "Failed to complete review. Check the file paths match files in the index."}
                    </span>
                  </div>
                )}

                {prResult && (
                  <div className="space-y-3 animate-fadeIn">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                          Review Report
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            prResult.issues_found > 0
                              ? "bg-amber-500/10 text-amber-500"
                              : "bg-emerald-500/10 text-emerald-500"
                          }`}
                        >
                          {prResult.issues_found > 0 ? (
                            <>
                              <AlertTriangle className="h-3 w-3" />
                              {prResult.issues_found} potential issues
                            </>
                          ) : (
                            <>
                              <CheckCircle2 className="h-3 w-3" />
                              Clean review
                            </>
                          )}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCopy(prResult.review)}
                        className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                      >
                        {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                        {copied ? "Copied" : "Copy MD"}
                      </Button>
                    </div>
                    <div className="max-h-[30rem] overflow-y-auto border border-border/50 rounded-lg p-5 bg-muted/10 font-mono text-xs leading-relaxed whitespace-pre-wrap select-text selection:bg-primary/20">
                      {prResult.review}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TEST GENERATION AGENT TAB */}
            {activeTab === "tests" && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                    Target File Path
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      className="h-9 flex-1 rounded-lg border border-border/60 bg-background px-3 text-xs outline-none focus:ring-1 focus:ring-primary/40 transition-all font-mono"
                      value={testFilePath}
                      onChange={(e) => setTestFilePath(e.target.value)}
                      placeholder="e.g. app/core/config.py"
                      disabled={testMutation.isPending}
                    />
                    <Button
                      onClick={handleTestGenerate}
                      disabled={testMutation.isPending || !testFilePath.trim()}
                      size="sm"
                      className="gap-2 shrink-0 shadow-sm"
                    >
                      {testMutation.isPending ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Play className="h-3.5 w-3.5 fill-current" />
                      )}
                      {testMutation.isPending ? "Generating..." : "Run Test Agent"}
                    </Button>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Builds mock contexts, happy-path test cases, and edge-condition failures for the target file.
                  </p>
                </div>

                {testMutation.isPending && (
                  <div className="flex flex-col items-center justify-center p-12 border border-dashed rounded-lg bg-card/50 space-y-3">
                    <Loader2 className="h-8 w-8 text-primary animate-spin" />
                    <div className="space-y-1 text-center">
                      <p className="text-xs font-semibold text-foreground">Scaffolding test suites...</p>
                      <p className="text-[10px] text-muted-foreground animate-pulse">
                        Analyzing structures & designing failure cases
                      </p>
                    </div>
                  </div>
                )}

                {testMutation.isError && (
                  <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-xs text-red-600 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span>
                      {(testMutation.error as any)?.response?.data?.detail ||
                        "Failed to generate tests. Verify that the file path exists in the repository."}
                    </span>
                  </div>
                )}

                {testsResult && (
                  <div className="space-y-2 animate-fadeIn">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                        Generated Unit Tests
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCopy(testsResult)}
                        className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                      >
                        {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                        {copied ? "Copied" : "Copy Code"}
                      </Button>
                    </div>
                    <div className="max-h-[30rem] overflow-y-auto border border-border/50 rounded-lg p-5 bg-slate-900 dark:bg-black text-slate-100 font-mono text-xs leading-relaxed whitespace-pre-wrap select-text selection:bg-primary/30">
                      {testsResult}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
