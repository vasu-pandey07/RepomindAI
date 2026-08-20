import type { NextConfig } from "next";
import { resolve } from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "avatars.githubusercontent.com",
      },
    ],
  },
  // NOTE: rewrites() do NOT work in standalone builds (node server.js).
  // All API proxying is handled by Next.js API route handlers in:
  //   app/repositories/route.ts, app/chat/route.ts, app/agents/route.ts, etc.
  outputFileTracingRoot: resolve(__dirname),
};

export default nextConfig;

