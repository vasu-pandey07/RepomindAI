import { LoginButton } from "@/components/LoginButton";
import { Navbar } from "@/components/Navbar";
import { ShieldCheck, GitPullRequest, Code, Database } from "lucide-react";

export default function HomePage() {
  const steps = [
    {
      icon: <ShieldCheck className="h-6 w-6 text-primary" />,
      title: "Secure Auth",
      description: "Sign in with GitHub OAuth. Only read-access tokens are used to fetch public/private repos.",
    },
    {
      icon: <GitPullRequest className="h-6 w-6 text-primary" />,
      title: "Repository Sync",
      description: "List all your repositories instantly. Sync metadata, stars, language details with one click.",
    },
    {
      icon: <Code className="h-6 w-6 text-primary" />,
      title: "Gemini Embedding Indexing",
      description: "Extract source files, split into overlap chunks using LangChain character splitters, and embed via Gemini text-embedding-004.",
    },
    {
      icon: <Database className="h-6 w-6 text-primary" />,
      title: "pgvector Storage",
      description: "Vectors are stored in PostgreSQL pgvector. Retrieve relevant code context semantically in milliseconds.",
    },
  ];

  return (
    <main className="min-h-screen bg-background text-foreground transition-colors duration-200">
      <Navbar />

      {/* Hero section */}
      <section className="relative mx-auto flex max-w-5xl flex-col items-center justify-center px-4 pt-20 pb-16 text-center lg:pt-32">
        {/* Decorative background glow */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[300px] bg-primary/10 rounded-full blur-[100px] pointer-events-none glow-primary" />

        <span className="relative z-10 inline-flex items-center gap-1.5 mb-5 rounded-full border border-primary/25 bg-primary/5 px-4 py-1 text-xs font-semibold tracking-wide text-primary">
          <span className="w-1.5 h-1.5 bg-primary rounded-full animate-ping" />
          GitHub-Powered Code Intelligence
        </span>

        <h1 className="relative z-10 max-w-4xl text-4xl font-extrabold tracking-tight sm:text-6xl bg-gradient-to-b from-foreground to-foreground/80 bg-clip-text text-transparent leading-none">
          Build a Vector Foundation For Your Code
        </h1>

        <p className="relative z-10 mt-6 max-w-2xl text-base sm:text-lg leading-relaxed text-muted-foreground">
          RepoMind AI connects your GitHub repositories, processes source code through intelligent chunking,
          and populates a high-performance vector store with Gemini embeddings.
        </p>

        <div className="relative z-10 mt-10 flex flex-col items-center gap-4">
          <LoginButton />
          <p className="text-xs text-muted-foreground">Requires active GitHub authorization</p>
        </div>
      </section>

      {/* Pipeline steps section */}
      <section className="border-t border-border/40 bg-secondary/15 py-20 dark:bg-slate-950/20">
        <div className="mx-auto max-w-5xl px-4">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">How RepoMind AI Works</h2>
            <p className="text-sm sm:text-base text-muted-foreground mt-2">
              A highly engineered pipeline to transform raw git repositories into semantic code vectors.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, idx) => (
              <div
                key={idx}
                className="relative bg-card border border-border/50 rounded-xl p-5 hover:border-primary/30 transition-all duration-300 shadow-sm flex flex-col items-start gap-4 glow-card group"
              >
                {/* Step indicator */}
                <span className="absolute top-4 right-4 text-3xl font-extrabold text-muted-foreground/10 group-hover:text-primary/10 transition-colors">
                  0{idx + 1}
                </span>

                <div className="p-2.5 rounded-lg bg-primary/10 border border-primary/20 shrink-0">
                  {step.icon}
                </div>

                <div className="space-y-1">
                  <h3 className="text-sm font-bold text-foreground tracking-tight">{step.title}</h3>
                  <p className="text-xs leading-relaxed text-muted-foreground">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Technical details badge block */}
      <section className="py-16">
        <div className="mx-auto max-w-4xl px-4 text-center">
          <div className="inline-flex flex-wrap items-center justify-center gap-x-8 gap-y-4 text-xs font-semibold text-muted-foreground/80 font-mono">
            <span>FastAPI Backend</span>
            <span className="w-1.5 h-1.5 bg-border rounded-full" />
            <span>Next.js Frontend</span>
            <span className="w-1.5 h-1.5 bg-border rounded-full" />
            <span>PostgreSQL & pgvector</span>
            <span className="w-1.5 h-1.5 bg-border rounded-full" />
            <span>Google Gemini SDK</span>
          </div>
        </div>
      </section>
    </main>
  );
}
