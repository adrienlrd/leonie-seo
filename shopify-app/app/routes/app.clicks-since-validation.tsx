import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";

// Resource route polled by the Analyse page to keep the per-product click
// counters live without re-running the heavy analysis-overview loader.
export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/clicks-since-validation`,
      { accessToken: session.accessToken },
    );
    if (resp.ok) {
      return json(await resp.json());
    }
  } catch {
    // fail-open
  }
  return json({ ga4_ready: false, resources: {} });
};
