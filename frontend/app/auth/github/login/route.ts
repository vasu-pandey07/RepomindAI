import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const backendUrl = process.env.INTERNAL_BACKEND_URL || "http://127.0.0.1:8000";
    const res = await fetch(`${backendUrl}/auth/github/login`, {
      redirect: "manual",
      headers: {
        cookie: request.headers.get("cookie") || "",
      },
    });

    const location = res.headers.get("location");
    if (location) {
      const response = NextResponse.redirect(location);
      const setCookie = res.headers.get("set-cookie");
      if (setCookie) {
        response.headers.set("set-cookie", setCookie);
      }
      return response;
    }

    const text = await res.text();
    return new Response(text, { status: res.status });
  } catch (error) {
    return new Response(`Auth error: ${error}`, { status: 500 });
  }
}
