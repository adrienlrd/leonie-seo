// Shopify session token retrieval.
//
// In production (embedded inside Shopify Admin), `window.shopify` is
// injected by App Bridge and exposes `shopify.idToken()` returning a
// short-lived JWT we attach to every API call as a Bearer token.
//
// In local dev (no App Bridge), this returns null and the backend
// must run with LEONIE_REQUIRE_SESSION_TOKEN=false.

export async function getSessionToken() {
  if (typeof window === 'undefined') return null
  if (window.shopify && typeof window.shopify.idToken === 'function') {
    try {
      return await window.shopify.idToken()
    } catch {
      return null
    }
  }
  return null
}
