/**
 * Server-side API helpers for Next.js Server Components.
 *
 * Mirrors the client-side api.ts functions but:
 *  - reads the auth token from the `bdgo_token` cookie (set by auth.ts setAuth)
 *  - uses NEXT_PUBLIC_API_URL as the absolute backend URL
 *  - never references `window` — safe to import in Server Components
 */

import { cookies } from "next/headers";
import type { PaginatedCRM, DealTypeCount } from "./api";

const BACKEND =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8001";

async function serverGet<T>(
  path: string,
  params?: Record<string, string | number>,
): Promise<T> {
  const cookieStore = await cookies();
  const token = cookieStore.get("bdgo_token")?.value;

  const url = new URL(`${BACKEND}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v !== undefined && v !== null) {
        url.searchParams.set(k, String(v));
      }
    });
  }

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url.toString(), {
    headers,
    // Opt out of Next.js static cache — CRM data changes on every write.
    cache: "no-store",
  });

  if (!res.ok) throw new Error(`API server ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

// Typed helpers — one per CRM table

export const fetchCompaniesServer = (params: Record<string, string>) =>
  serverGet<PaginatedCRM>("/api/companies", params);

export const fetchAssetsServer = (params: Record<string, string>) =>
  serverGet<PaginatedCRM>("/api/assets", params);

export const fetchClinicalServer = (params: Record<string, string>) =>
  serverGet<PaginatedCRM>("/api/clinical", params);

export const fetchDealsServer = (params: Record<string, string>) =>
  serverGet<PaginatedCRM>("/api/deals", params);

export const fetchIPServer = (params: Record<string, string>) =>
  serverGet<PaginatedCRM>("/api/ip", params);

export const fetchBuyersServer = (params: Record<string, string>) =>
  serverGet<PaginatedCRM>("/api/buyers", params);

export const fetchDealsByTypeServer = () =>
  serverGet<DealTypeCount[]>("/api/stats/deals-by-type");
