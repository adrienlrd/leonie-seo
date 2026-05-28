import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { BlockStack, Card, Page, Text } from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;

  let debug: unknown = null;
  let error: string | null = null;
  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/gsc/debug`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) {
      debug = await resp.json();
    } else {
      error = `HTTP ${resp.status}: ${await resp.text()}`;
    }
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  return json({ debug, error });
};

export default function GscDebug() {
  const { debug, error } = useLoaderData<typeof loader>();
  return (
    <Page title="GSC Debug">
      <Card>
        <BlockStack gap="300">
          {error && (
            <Text as="p" tone="critical">
              {error}
            </Text>
          )}
          <pre style={{ whiteSpace: "pre-wrap", fontSize: "12px" }}>
            {JSON.stringify(debug, null, 2)}
          </pre>
        </BlockStack>
      </Card>
    </Page>
  );
}
