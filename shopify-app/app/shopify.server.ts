import "@shopify/shopify-app-remix/adapters/node";
import path from "node:path";
import {
  AppDistribution,
  DeliveryMethod,
  LATEST_API_VERSION,
  shopifyApp,
} from "@shopify/shopify-app-remix/server";
import { SQLiteSessionStorage } from "@shopify/shopify-app-session-storage-sqlite";
import { PostgreSQLSessionStorage } from "@shopify/shopify-app-session-storage-postgresql";
import { RedisSessionStorage } from "@shopify/shopify-app-session-storage-redis";
import { callBackendForShop } from "./lib/api.server";

// Session storage priority: Redis > Postgres > SQLite.
// Redis avoids a Postgres round-trip on every authenticate.admin() call (every
// embedded app navigation), which matters once many merchants are active.
// Cast silences a TypeScript peer-dep skew (shopify-api v11 vs v12); runtime-compatible.
function requireSslMode(databaseUrl: string): string {
  const url = new URL(databaseUrl);
  if (!url.searchParams.has("sslmode")) {
    url.searchParams.set("sslmode", "require");
  }
  return url.toString();
}

const databaseUrl = process.env.DATABASE_URL
  ? requireSslMode(process.env.DATABASE_URL)
  : undefined;

const sessionStorage = process.env.REDIS_URL
  ? (new RedisSessionStorage(new URL(process.env.REDIS_URL)) as unknown)
  : databaseUrl
    ? (new PostgreSQLSessionStorage(databaseUrl) as unknown)
    : (new SQLiteSessionStorage(
        path.resolve(process.cwd(), "../data/shopify-sessions.db")
      ) as unknown);
const appUrl = process.env.SHOPIFY_APP_URL || "";
const skipWebhookRegistration = (() => {
  try {
    const hostname = new URL(appUrl).hostname;
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  } catch {
    return false;
  }
})();

if (process.env.REDIS_URL) {
  console.info("[shopify.server] REDIS_URL set — using Redis session storage");
} else if (!process.env.DATABASE_URL) {
  console.info(
    "[shopify.server] DATABASE_URL not set — using SQLite session storage at data/shopify-sessions.db"
  );
}

const shopify = shopifyApp({
  apiKey: process.env.SHOPIFY_CLIENT_ID ?? process.env.SHOPIFY_API_KEY,
  apiSecretKey: process.env.SHOPIFY_CLIENT_SECRET ?? process.env.SHOPIFY_API_SECRET ?? "",
  apiVersion: LATEST_API_VERSION,
  scopes: process.env.SCOPES?.split(","),
  appUrl,
  authPathPrefix: "/auth",
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  sessionStorage: sessionStorage as any,
  distribution: AppDistribution.AppStore,
  webhooks: {
    APP_UNINSTALLED: {
      deliveryMethod: DeliveryMethod.Http,
      callbackUrl: "/webhooks",
    },
    CUSTOMERS_DATA_REQUEST: {
      deliveryMethod: DeliveryMethod.Http,
      callbackUrl: "/webhooks",
    },
    CUSTOMERS_REDACT: {
      deliveryMethod: DeliveryMethod.Http,
      callbackUrl: "/webhooks",
    },
    SHOP_REDACT: {
      deliveryMethod: DeliveryMethod.Http,
      callbackUrl: "/webhooks",
    },
  },
  hooks: {
    afterAuth: async ({ session }) => {
      if (skipWebhookRegistration) {
        console.info(
          "[shopify.server] Skipping webhook registration for localhost development."
        );
      } else {
        await shopify.registerWebhooks({ session });
      }
      // Sync the freshly issued offline token to the Python backend so its admin
      // writes — and webhook-triggered jobs that read shop_tokens directly —
      // always use a valid token. Without this the backend relies on a stale
      // token and every Shopify write 401s.
      try {
        await callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/internal/token`,
          {
            method: "POST",
            body: JSON.stringify({
              access_token: session.accessToken ?? "",
              scope: session.scope ?? "",
            }),
          },
        );
      } catch (err) {
        console.error("[shopify.server] token sync to backend failed:", err);
      }
    },
  },
  future: {
    unstable_newEmbeddedAuthStrategy: true,
  },
});

export default shopify;
export const apiVersion = LATEST_API_VERSION;
export const addDocumentResponseHeaders = shopify.addDocumentResponseHeaders;
export const authenticate = shopify.authenticate;
export const unauthenticated = shopify.unauthenticated;
export const login = shopify.login;
export const registerWebhooks = shopify.registerWebhooks;
