/**
 * HTTP client for the Python backend (Léonie SEO engine).
 *
 * Two functions:
 * - callBackend()        — unauthenticated call (health checks, public endpoints)
 * - callBackendForShop() — authenticated internal call (adds X-Leonie-Shop +
 *                          X-Internal-Secret so Python can resolve the shop context)
 */

const PYTHON_BACKEND_URL =
  process.env.PYTHON_BACKEND_URL || "http://localhost:8000";

const INTERNAL_API_SECRET = process.env.INTERNAL_API_SECRET || "";

export async function callBackend(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const url = `${PYTHON_BACKEND_URL}${path}`;
  const headers = new Headers(options.headers as HeadersInit | undefined);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(url, { ...options, headers });
}

/**
 * Authenticated call on behalf of a specific shop.
 * Injects X-Leonie-Shop and X-Internal-Secret so the Python backend
 * can resolve the shop context without a Shopify session token.
 */
export async function callBackendForShop(
  shop: string,
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(options.headers as HeadersInit | undefined);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("X-Leonie-Shop", shop);
  if (INTERNAL_API_SECRET) {
    headers.set("X-Internal-Secret", INTERNAL_API_SECRET);
  }
  return callBackend(path, { ...options, headers });
}

export async function callBackendJsonForShop<T = unknown>(
  shop: string,
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const resp = await callBackendForShop(shop, path, options);
  if (!resp.ok) {
    throw new Error(`Backend error ${resp.status} on ${path}`);
  }
  return resp.json() as Promise<T>;
}
