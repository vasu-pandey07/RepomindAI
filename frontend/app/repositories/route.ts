export const dynamic = "force-dynamic";

import { proxyToBackend } from "@/lib/proxy";

export async function GET(request: Request) {
  return proxyToBackend(request, "/repositories");
}

export async function POST(request: Request) {
  return proxyToBackend(request, "/repositories");
}
