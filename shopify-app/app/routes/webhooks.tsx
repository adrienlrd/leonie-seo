import type { ActionFunctionArgs } from "@remix-run/node";
import { callBackend } from "../lib/api.server";

/**
 * Webhook relay — Shopify calls this endpoint for all subscribed topics.
 * We forward each webhook to the Python backend with its original HMAC headers
 * so the Python HMAC validator can re-verify the signature independently.
 *
 * Topics handled: app/uninstalled, customers/data_request,
 *                 customers/redact, shop/redact
 */
export const action = async ({ request }: ActionFunctionArgs) => {
  const topic = request.headers.get("x-shopify-topic") ?? "";
  const shop = request.headers.get("x-shopify-shop-domain") ?? "";
  const hmac = request.headers.get("x-shopify-hmac-sha256") ?? "";
  const rawBody = await request.text();

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
