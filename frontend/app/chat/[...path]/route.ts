export const dynamic = "force-dynamic";

import { proxyToBackend } from "@/lib/proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const subPath = path.join("/");
  return proxyToBackend(request, `/chat/${subPath}`);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const subPath = path.join("/");
  return proxyToBackend(request, `/chat/${subPath}`);
}
