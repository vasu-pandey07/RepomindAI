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

  // Forward request body for non-GET/HEAD methods. Read it as a string so the
  // same body can be safely re-sent across retry attempts.
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  // The backend may be briefly unreachable while it restarts (e.g. the
  // supervisor is bringing uvicorn back up after an OOM on the free tier, or a
  // cold start). Retry connection-level failures a few times before giving up
  // so a single restart window doesn't surface as a hard error to the user.
  const MAX_ATTEMPTS = 4;
  let lastError: unknown = null;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const backendResponse = await fetch(targetUrl, init);

      // Handle redirects — sanitize location and forward 307 response directly to browser
      const location = backendResponse.headers.get("location");
      if (location) {
        const cleanLocation = location
          .replace(/[\r\n\t]+/g, "")
          .replace(/%0A/gi, "")
          .replace(/%0D/gi, "")
          .trim();

        const redirectHeaders = new Headers();
        redirectHeaders.set("Location", cleanLocation);

        const setCookie = backendResponse.headers.get("set-cookie");
        if (setCookie) {
          redirectHeaders.set("set-cookie", setCookie);
        }

        return new Response(null, {
          status: backendResponse.status || 307,
          headers: redirectHeaders,
        });
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
      lastError = error;
      if (attempt < MAX_ATTEMPTS) {
        // Linear backoff: 0.75s, 1.5s, 2.25s
        await new Promise((resolve) => setTimeout(resolve, 750 * attempt));
        continue;
      }
    }
  }

  console.error(
    `[Proxy] Backend unreachable after ${MAX_ATTEMPTS} attempts for ${request.method} ${backendPath}:`,
    lastError
  );
  return new Response(
    JSON.stringify({
      detail:
        "Backend service is temporarily unavailable — it may be restarting. Please wait a few seconds and try again.",
    }),
    { status: 503, headers: { "content-type": "application/json" } }
  );
}
