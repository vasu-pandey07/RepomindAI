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
  async rewrites() {
    return [
      {
        source: "/repositories",
        destination: "http://127.0.0.1:8000/repositories",
      },
      {
        source: "/repositories/:path*",
        destination: "http://127.0.0.1:8000/repositories/:path*",
      },
      {
        source: "/chat",
        destination: "http://127.0.0.1:8000/chat",
      },
      {
        source: "/chat/:path*",
        destination: "http://127.0.0.1:8000/chat/:path*",
      },
      {
        source: "/agents",
        destination: "http://127.0.0.1:8000/agents",
      },
      {
        source: "/agents/:path*",
        destination: "http://127.0.0.1:8000/agents/:path*",
      },
      {
        source: "/health",
        destination: "http://127.0.0.1:8000/health",
      },
    ];
  },
  outputFileTracingRoot: resolve(__dirname),
};

export default nextConfig;
