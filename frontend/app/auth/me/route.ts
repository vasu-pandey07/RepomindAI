export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const backendUrl = process.env.INTERNAL_BACKEND_URL || "http://127.0.0.1:8000";
    const authHeader = request.headers.get("authorization");
    const res = await fetch(`${backendUrl}/auth/me`, {
      headers: {
        ...(authHeader ? { authorization: authHeader } : {}),
      },
    });

    const data = await res.text();
    return new Response(data, {
      status: res.status,
      headers: { "content-type": "application/json" },
    });
  } catch (error) {
    return new Response(`Error: ${error}`, { status: 500 });
  }
}
