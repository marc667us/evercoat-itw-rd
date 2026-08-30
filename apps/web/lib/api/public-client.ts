/**
 * The public surface's own client. No token, no organization, no session.
 *
 * 🔴 WHY THIS IS NOT `client.ts` WITH THE HEADERS MADE OPTIONAL.
 *
 * `client.ts` states its own contract in its header: it ALWAYS sends
 * `Authorization: Bearer <token>` and `X-Organization-Id`, and "a request
 * built here without both is a request that cannot succeed, so the types make
 * it impossible to build one."
 *
 * That is deliberate and correct, and relaxing it to serve the landing page
 * would put an authentication-bypass seam into the one module whose entire
 * purpose is that an unauthenticated request cannot be CONSTRUCTED. The API
 * side refuses the same shortcut for the same reason: `/api/public/*` is a
 * separate router on a separate database connection, not `permit_anonymous`
 * bolted onto `/api/competitors`.
 *
 * So the public surface gets its own small client. It shares the base URL and
 * nothing else.
 *
 * 🔴 IT NEVER FALLS BACK TO THE DEMONSTRATION DATASET.
 *
 * `LiveOnlyPage` and `DemoBanner` exist because a screen of invented figures
 * is indistinguishable from a working one at a glance. That risk is worse
 * here, not better: this page is public, and the marketplace makes claims
 * about REAL manufacturers. Rendering `lib/demo/dataset` when the API is
 * unreachable would publish invented competitor products to anonymous
 * visitors as though they were the live global catalogue.
 *
 * An unreachable API yields an empty marketplace and a notice saying so.
 *
 * ⚠️ MONEY ARRIVES AS A STRING. The API sends `price_amount` as a string
 * because FastAPI encodes `Decimal` as a float and loses scale — the defect
 * that broke the material edit form twice on 2026-08-29. Keep it a string all
 * the way to the formatter; do not `Number()` it to "tidy" the type.
 */

import { API_BASE_URL, isApiConfigured } from "./config";

export class PublicApiUnconfiguredError extends Error {
  constructor() {
    super("no API address was compiled into this build");
    this.name = "PublicApiUnconfiguredError";
  }
}

export class PublicApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "PublicApiError";
  }
}

async function publicRequest<T>(path: string, init?: RequestInit): Promise<T> {
  // `API_BASE_URL` is `string | null` and `isApiConfigured` is the boolean
  // derived from it. Both are checked so the narrowing is real rather than
  // assumed: the static export genuinely has no API address, and that is a
  // normal state of the live deployment, not a fault.
  if (!isApiConfigured || API_BASE_URL === null) throw new PublicApiUnconfiguredError();

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    // A network failure and a refusal are different answers and must not
    // collapse into one, or "the marketplace is empty" and "you are offline"
    // become the same message.
    throw new PublicApiError("the catalogue could not be reached", null);
  }

  if (!response.ok) {
    throw new PublicApiError(
      response.status === 503
        ? "the public catalogue is not configured on this deployment"
        : `the catalogue answered ${response.status}`,
      response.status,
    );
  }
  return (await response.json()) as T;
}

/** Provenance, as the API projects it. Never widened here. */
export type ContentOrigin = "synthetic" | "source_derived" | "verified";

export interface PublicProduct {
  id: string;
  manufacturer_id: string;
  manufacturer_name: string;
  product_name: string;
  product_code: string | null;
  category: string | null;
  chemistry: string | null;
  region: string | null;
  description: string | null;
  /** A STRING. See the header. */
  price_amount: string | null;
  price_currency: string | null;
  price_as_of: string | null;
  price_source_url: string | null;
  content_origin: ContentOrigin;
  is_demonstration_data: boolean;
  source_url: string | null;
}

export interface PublicProductDocument {
  id: string;
  document_kind: "datasheet" | "label" | "literature" | "sds";
  title: string;
  url: string;
  content_origin: ContentOrigin;
  is_demonstration_data: boolean;
}

export interface PublicNewsItem {
  id: string;
  headline: string;
  summary: string | null;
  summary_is_ai_generated: boolean;
  source_url: string;
  published_at: string | null;
  region: string | null;
  country: string | null;
  manufacturer_id: string | null;
  product_id: string | null;
  category_slug: string;
  category_label: string;
  source_name: string;
  source_type: string | null;
  source_tier: number;
  content_origin: ContentOrigin;
  is_demonstration_data: boolean;
}

export interface PublicNewsCategory {
  id: string;
  slug: string;
  label: string;
  sort_order: number;
}

export interface PublicManufacturer {
  id: string;
  name: string;
  country: string | null;
  website_url: string | null;
  content_origin: ContentOrigin;
  is_demonstration_data: boolean;
}

export interface PublicProductDetail extends PublicProduct {
  documents: PublicProductDocument[];
  news: PublicNewsItem[];
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
}

export function fetchPublicProducts(params: {
  q?: string;
  category?: string;
  manufacturer_id?: string;
  limit?: number;
  offset?: number;
}): Promise<{ products: PublicProduct[]; total: number }> {
  return publicRequest(`/api/public/products${query(params)}`);
}

export function fetchPublicProduct(id: string): Promise<PublicProductDetail> {
  return publicRequest(`/api/public/products/${id}`);
}

export function fetchPublicNews(params: {
  category?: string;
  manufacturer_id?: string;
  region?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: PublicNewsItem[] }> {
  return publicRequest(`/api/public/news${query(params)}`);
}

export function fetchPublicNewsCategories(): Promise<{ categories: PublicNewsCategory[] }> {
  return publicRequest("/api/public/news/categories");
}

export function fetchPublicManufacturers(): Promise<{ manufacturers: PublicManufacturer[] }> {
  return publicRequest("/api/public/manufacturers");
}

export function submitAccessRequest(payload: {
  full_name: string;
  work_email: string;
  company: string;
  reason?: string;
}): Promise<{ status: string; message: string }> {
  return publicRequest("/api/public/access-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Money, formatted from the string the API sent.
 *
 * ⚠️ ISO CODE, NEVER A SYMBOL — SolarPro's rule, adopted rather than
 * reinvented. "$" is ambiguous across at least a dozen currencies, and a
 * marketplace spanning regions is exactly where that ambiguity costs money.
 */
export function formatPrice(amount: string | null, currency: string | null): string | null {
  if (amount === null || currency === null) return null;
  const value = Number(amount);
  if (!Number.isFinite(value)) return null;
  return `${currency} ${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
