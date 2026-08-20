/**
 * Shared proxy utility for forwarding API requests from the Next.js frontend
 * to the internal FastAPI backend running at 127.0.0.1:8000 inside the Docker container.
 *
 * This replaces the next.config.ts `rewrites()` which do NOT work in
 * standalone builds (output: "standalone" + `node server.js`).
 */

const BACKEND_URL = process.env.INTERNAL_BACKEND_URL || "http://127.0.0.1:8000";

export async function proxyToBackend(
  request: Request,
  backendPath: string
): Promise<Response> {
  const url = new URL(request.url);
  const targetUrl = `${BACKEND_URL}${backendPath}${url.search}`;

  const headers = new Headers();
  // Forward essential headers
  const authHeader = request.headers.get("authorization");
  if (authHeader) {
    headers.set("authorization", authHeader);
  }
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  const cookie = request.headers.get("cookie");
  if (cookie) {
    headers.set("cookie", cookie);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  // Forward request body for non-GET/HEAD methods
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  try {
    const backendResponse = await fetch(targetUrl, init);

    // Handle redirects — rewrite backend URLs to frontend-relative URLs
    const location = backendResponse.headers.get("location");
    if (location) {
      return Response.redirect(location, backendResponse.status || 302);
    }

    // Stream the response back
    const responseHeaders = new Headers();
    const respContentType = backendResponse.headers.get("content-type");
    if (respContentType) {
      responseHeaders.set("content-type", respContentType);
    }
    const setCookie = backendResponse.headers.get("set-cookie");
    if (setCookie) {
      responseHeaders.set("set-cookie", setCookie);
    }

    const body = await backendResponse.text();
    return new Response(body, {
      status: backendResponse.status,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error(`[Proxy] Error forwarding ${request.method} ${backendPath}:`, error);
    return new Response(
      JSON.stringify({ detail: "Backend service unavailable" }),
      { status: 502, headers: { "content-type": "application/json" } }
    );
  }
}
