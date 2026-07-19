/**
 * Server-side locale resolution: ?locale= param → persisted shop preference
 * (backend GET /language, 60s memory cache) → Shopify shop primaryLocale
 * (persisted on first read) → English.
 *
 * Routes call `resolveLocale(request, shop, accessToken, admin?)` instead of
 * the pure `getLocale(request)`; the admin GraphQL client is optional — when
 * absent the Shopify-locale step is skipped (the preference is usually
 * persisted by the first page that has one).
 */

import { callBackendForShop } from "./api.server";
import { isSupportedLocale, type Locale } from "./i18n";

interface CacheEntry {
  locale: Locale | null;
  configured: boolean;
  at: number;
}

const _CACHE = new Map<string, CacheEntry>();
const _TTL_MS = 60_000;

type AdminGraphql = {
  graphql: (query: string) => Promise<Response>;
};

async function fetchPreference(
  shop: string,
  accessToken: string | undefined,
): Promise<CacheEntry> {
  const cached = _CACHE.get(shop);
  if (cached && Date.now() - cached.at < _TTL_MS) return cached;
  let entry: CacheEntry = { locale: null, configured: false, at: Date.now() };
  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/language`, {
      accessToken,
      signal: AbortSignal.timeout(5_000),
    });
    if (resp.ok) {
      const data = (await resp.json()) as { language?: string; configured?: boolean };
      entry = {
        locale: isSupportedLocale(data.language) ? data.language : null,
        configured: Boolean(data.configured),
        at: Date.now(),
      };
    }
  } catch {
    // Backend unreachable — fall through to Shopify locale / English.
  }
  _CACHE.set(shop, entry);
  return entry;
}

async function shopifyPrimaryLocale(admin: AdminGraphql): Promise<Locale | null> {
  try {
    const resp = await admin.graphql(`#graphql
      query { shop { primaryDomain { id } } shopLocales(published: true) { locale primary } }
    `);
    const data = (await resp.json()) as {
      data?: { shopLocales?: Array<{ locale?: string; primary?: boolean }> };
    };
    const primary = (data.data?.shopLocales ?? []).find((l) => l.primary)?.locale ?? "";
    const short = primary.slice(0, 2).toLowerCase();
    return isSupportedLocale(short) ? short : "en";
  } catch {
    return null;
  }
}

async function persistPreference(
  shop: string,
  accessToken: string | undefined,
  locale: Locale,
): Promise<void> {
  try {
    await callBackendForShop(shop, `/api/shops/${shop}/language`, {
      accessToken,
      method: "PUT",
      body: JSON.stringify({ language: locale }),
      signal: AbortSignal.timeout(5_000),
    });
    _CACHE.set(shop, { locale, configured: true, at: Date.now() });
  } catch {
    // Non-fatal: resolution still returns the right locale for this request.
  }
}

/** Invalidate the cached preference (call after the merchant changes it). */
export function invalidateLocaleCache(shop: string): void {
  _CACHE.delete(shop);
}

export async function resolveLocale(
  request: Request,
  shop: string,
  accessToken: string | undefined,
  admin?: AdminGraphql,
): Promise<Locale> {
  // The persisted preference WINS over ?locale=. URLs carry stale locale
  // params (history, links rendered before a language switch), and letting
  // them override the setting made the app "snap back" to the old language
  // on every navigation. ?locale only matters before a preference exists.
  const pref = await fetchPreference(shop, accessToken);
  if (pref.configured && pref.locale) return pref.locale;

  const url = new URL(request.url);
  const requested = url.searchParams.get("locale");
  if (isSupportedLocale(requested)) {
    // No preference exists yet: persist this one. Returning without
    // persisting left the BACKEND on its English default while the UI
    // showed French — analyses and the business profile came out in
    // English despite a French interface.
    await persistPreference(shop, accessToken, requested);
    return requested;
  }

  if (admin) {
    const fromShopify = await shopifyPrimaryLocale(admin);
    if (fromShopify) {
      await persistPreference(shop, accessToken, fromShopify);
      return fromShopify;
    }
  }
  return pref.locale ?? "en";
}
