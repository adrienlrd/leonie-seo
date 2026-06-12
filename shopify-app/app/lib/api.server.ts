/**
 * HTTP client for the Python backend (Giulio Geo engine).
 *
 * Two functions:
 * - callBackend()        — unauthenticated call (health checks, public endpoints)
 * - callBackendForShop() — authenticated internal call (adds X-Leonie-Shop,
 *                          X-Internal-Secret, and optionally the Shopify
 *                          session access token so Python can resolve context)
 */

// Render's private-network `fromService` (property: hostport) returns "host:port"
// without a scheme — the internal network is plain HTTP, so default to that.
function normalizeBackendUrl(value: string): string {
  return /^https?:\/\//.test(value) ? value : `http://${value}`;
}

const PYTHON_BACKEND_URL = normalizeBackendUrl(
  process.env.PYTHON_BACKEND_URL || "http://localhost:8000"
);

const INTERNAL_API_SECRET = process.env.INTERNAL_API_SECRET || "";

type BackendRequestInit = RequestInit & {
  accessToken?: string;
};

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
  options: BackendRequestInit = {}
): Promise<Response> {
  const { accessToken, ...requestOptions } = options;
  const headers = new Headers(options.headers as HeadersInit | undefined);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("X-Leonie-Shop", shop);
  if (INTERNAL_API_SECRET) {
    headers.set("X-Internal-Secret", INTERNAL_API_SECRET);
  }
  if (accessToken) {
    headers.set("X-Shopify-Access-Token", accessToken);
  }
  return callBackend(path, { ...requestOptions, headers });
}

/**
 * Multipart file upload to the backend on behalf of a specific shop.
 * Does NOT set Content-Type so fetch handles the multipart boundary automatically.
 */
export async function callBackendMultipartForShop(
  shop: string,
  path: string,
  formData: FormData,
  accessToken?: string,
): Promise<Response> {
  const url = `${PYTHON_BACKEND_URL}${path}`;
  const headers = new Headers();
  headers.set("X-Leonie-Shop", shop);
  if (INTERNAL_API_SECRET) headers.set("X-Internal-Secret", INTERNAL_API_SECRET);
  if (accessToken) headers.set("X-Shopify-Access-Token", accessToken);
  return fetch(url, { method: "POST", headers, body: formData });
}

export async function callBackendJsonForShop<T = unknown>(
  shop: string,
  path: string,
  options: BackendRequestInit = {}
): Promise<T> {
  const resp = await callBackendForShop(shop, path, options);
  if (!resp.ok) {
    throw new Error(`Backend error ${resp.status} on ${path}`);
  }
  return resp.json() as Promise<T>;
}
