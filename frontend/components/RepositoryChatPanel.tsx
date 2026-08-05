"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ChatMessage, ChatResponse, Repository } from "@/types";

async function fetchRepositories() {
  const response = await api.get<Repository[]>("/repositories");
  return response.data;
}

async function askRepositoryQuestion(payload: {
  repository_id: number;
  question: string;
  session_id?: number;
}) {
  const response = await api.post<ChatResponse>("/chat", payload);
  return response.data;
}

export function RepositoryChatPanel() {
  const [selectedRepositoryId, setSelectedRepositoryId] = useState<number | null>(null);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const repositoriesQuery = useQuery({
    queryKey: ["repositories"],
    queryFn: fetchRepositories,
  });

  const repositories = useMemo(() => repositoriesQuery.data ?? [], [repositoriesQuery.data]);

  useEffect(() => {
    if (selectedRepositoryId === null && repositories.length > 0) {
      setSelectedRepositoryId(repositories[0].id);
    }
  }, [repositories, selectedRepositoryId]);

  const chatMutation = useMutation({
    mutationFn: askRepositoryQuestion,
    onSuccess: (data) => {
      setSessionId(data.session_id);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: data.answer, sources: data.sources },
      ]);
    },
    onError: () => {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: "I could not answer from this repository right now. Check that it is indexed.",
          sources: [],
        },
      ]);
    },
  });

  const handleRepositoryChange = (value: string) => {
    setSelectedRepositoryId(Number(value));
    setSessionId(null);
    setMessages([]);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || selectedRepositoryId === null || chatMutation.isPending) {
      return;
    }

    setMessages((current) => [...current, { role: "user", content: trimmedQuestion }]);
    setQuestion("");
    chatMutation.mutate({
      repository_id: selectedRepositoryId,
      question: trimmedQuestion,
      session_id: sessionId ?? undefined,
    });
  };

  return (
    <section className="rounded-xl border border-border/50 bg-card text-card-foreground shadow-sm glow-card flex flex-col">
      <div className="border-b border-border/50 p-5 bg-card/40 backdrop-blur-sm">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="space-y-1">
            <h2 className="text-xl font-bold tracking-tight text-foreground">Repository Chat</h2>
            <p className="text-xs text-muted-foreground">
              Ask questions using only indexed repository context.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-muted-foreground">Active Repo:</label>
            <select
              className="h-9 rounded-lg border border-border/60 bg-background/50 px-3 py-1 text-xs font-medium text-foreground outline-none focus:ring-1 focus:ring-primary/40 transition-all cursor-pointer"
              value={selectedRepositoryId ?? ""}
              onChange={(event) => handleRepositoryChange(event.target.value)}
              disabled={repositoriesQuery.isLoading || repositories.length === 0}
            >
              {repositories.length === 0 ? (
                <option value="">No repositories</option>
              ) : (
                repositories.map((repository) => (
                  <option key={repository.id} value={repository.id}>
                    {repository.name}
                  </option>
                ))
              )}
            </select>
          </div>
        </div>
      </div>

      <div className="flex min-h-[28rem] flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border/60 p-8 text-center bg-muted/10">
              <h3 className="font-semibold text-sm text-foreground">Start with an indexed repository</h3>
              <p className="mt-2 text-xs text-muted-foreground">
                Try asking how authentication, routing, data models, or API calls work.
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={message.role === "user" ? "flex justify-end" : "flex justify-start"}
              >
                <div
                  className={
                    message.role === "user"
                      ? "max-w-[85%] rounded-lg bg-primary px-4 py-2.5 text-xs font-medium text-primary-foreground shadow-sm"
                      : "max-w-[85%] rounded-lg border border-border/50 bg-muted/40 px-4 py-2.5 text-xs text-foreground leading-relaxed shadow-sm"
                  }
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.sources && message.sources.length > 0 ? (
                    <div className="mt-2.5 border-t border-border/30 pt-2">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                        Sources
                      </p>
                      <ul className="mt-1 space-y-0.5 text-[10px] text-muted-foreground font-mono">
                        {message.sources.map((source) => (
                          <li key={source} className="hover:text-foreground transition-colors">{source}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            ))
          )}

          {chatMutation.isPending ? (
            <div className="flex justify-start">
              <div className="rounded-lg border border-border/50 bg-muted/30 px-4 py-2.5 text-xs text-muted-foreground flex items-center gap-2">
                <span className="h-1.5 w-1.5 bg-primary rounded-full animate-ping" />
                Thinking with repository context...
              </div>
            </div>
          ) : null}
        </div>

        <form onSubmit={handleSubmit} className="border-t border-border/50 p-4 bg-muted/10">
          <div className="flex gap-3">
            <input
              className="h-10 flex-1 rounded-lg border border-border/60 bg-background px-3 text-xs outline-none focus:ring-1 focus:ring-primary/40 transition-all text-foreground"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about this repository..."
              disabled={selectedRepositoryId === null || chatMutation.isPending}
            />
            <Button
              type="submit"
              disabled={selectedRepositoryId === null || chatMutation.isPending || !question.trim()}
              className="gap-1.5 h-10 shadow-sm"
            >
              <Send className="h-3.5 w-3.5" />
              Ask
            </Button>
          </div>
        </form>
      </div>
    </section>
  );
}
