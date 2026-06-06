import type { ActionFunctionArgs } from "@remix-run/node";
import { createHmac, timingSafeEqual } from "node:crypto";
import { callBackend, callBackendForShop } from "../lib/api.server";

/**
 * Verify the Shopify webhook HMAC over the raw request body.
 *
 * Shopify requires that an app returns 401 when a mandatory compliance webhook
 * arrives with an invalid HMAC header, and authenticity must be checked on every
 * webhook. We verify here at the edge (timing-safe) before any processing, and
 * forward the unmodified raw body so the Python backend can re-verify too.
 */
function isValidWebhookHmac(rawBody: string, hmacHeader: string): boolean {
  const secret = process.env.SHOPIFY_API_SECRET;
  if (!secret || !hmacHeader) {
    return false;
  }
  const digest = createHmac("sha256", secret).update(rawBody, "utf8").digest("base64");
  const expected = Buffer.from(digest);
  const received = Buffer.from(hmacHeader);
  if (expected.length !== received.length) {
    return false;
  }
  return timingSafeEqual(expected, received);
}

/**
 * Catalogue topics that should trigger an llms.txt / llms-full.txt regeneration.
 * The backend debounces (5 min) and only republishes content that is already
 * public, so a redundant trigger is cheap and safe.
 */
const CATALOG_TOPICS = new Set([
  "products/create",
  "products/update",
  "products/delete",
  "collections/update",
  "collections/delete",
]);

/**
 * Webhook relay — Shopify calls this endpoint for all subscribed topics.
 *
 * - Catalogue topics (products/*, collections/*) → POST the llms-txt webhook-tick
 *   so the backend can debounce-regenerate the published files.
 * - All other topics (app/uninstalled, compliance) are forwarded to the Python
 *   backend with their original HMAC headers so Python re-verifies the signature.
 *
 * The HMAC is verified first: an invalid signature returns 401 (required by
 * Shopify for mandatory compliance webhooks). Valid deliveries always return 200
 * so Shopify does not retry/duplicate them.
 */
export const action = async ({ request }: ActionFunctionArgs) => {
  const topic = request.headers.get("x-shopify-topic") ?? "";
  const shop = request.headers.get("x-shopify-shop-domain") ?? "";
  const hmac = request.headers.get("x-shopify-hmac-sha256") ?? "";
  const rawBody = await request.text();

  if (!isValidWebhookHmac(rawBody, hmac)) {
    console.error(`[webhooks] invalid HMAC for topic=${topic} shop=${shop}`);
    return new Response("Unauthorized", { status: 401 });
  }

  if (CATALOG_TOPICS.has(topic) && shop) {
    try {
      await callBackendForShop(
        shop,
        `/api/shops/${shop}/llms-txt/webhook-tick`,
        { method: "POST", body: JSON.stringify({ shop }) },
      );
    } catch (err) {
      console.error(`[webhooks] llms-txt tick failed for shop=${shop}:`, err);
    }
    return new Response(null, { status: 200 });
  }

  // Map Shopify topic format (customers/data_request) to Python path segment
  const path = `/shopify/webhooks/${topic}`;

  try {
    await callBackend(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Hmac-Sha256": hmac,
        "X-Shopify-Shop-Domain": shop,
        "X-Shopify-Topic": topic,
      },
      body: rawBody,
    });
  } catch (err) {
    // Log but always return 200 to Shopify — they will retry on non-2xx.
    // Returning 200 here prevents duplicate webhook deliveries.
    console.error(`[webhooks] relay failed for topic=${topic} shop=${shop}:`, err);
  }

  return new Response(null, { status: 200 });
};
