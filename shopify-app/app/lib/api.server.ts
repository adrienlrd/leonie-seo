/**
 * HTTP client for the Python backend (Léonie SEO engine).
 * All calls go through this module so the base URL is configured in one place.
 */

const PYTHON_BACKEND_URL =
  process.env.PYTHON_BACKEND_URL || "http://localhost:8000";

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

export async function callBackendJson<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const resp = await callBackend(path, options);
  if (!resp.ok) {
    throw new Error(`Backend error ${resp.status} on ${path}`);
  }
  return resp.json() as Promise<T>;
}
