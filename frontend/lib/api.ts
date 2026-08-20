"use client";

import axios from "axios";

import { getToken } from "@/lib/auth";

const getBaseUrl = () => {
  // In the browser, always use relative URLs — the Next.js API route proxies
  // will forward requests to the internal backend (works in both dev and prod)
  if (typeof window !== "undefined") {
    return "";
  }
  // Server-side (SSR): use internal backend URL
  return process.env.INTERNAL_BACKEND_URL || "http://127.0.0.1:8000";
};

export const api = axios.create({
  baseURL: getBaseUrl(),
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});
