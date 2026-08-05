import type { Metadata } from "next";
import { ReactNode } from "react";

import { Providers } from "@/app/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "RepoMind AI",
  description: "GitHub-powered code intelligence foundation.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
