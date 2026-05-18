import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Form, useActionData, useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  InlineStack,
  Page,
  Select,
  Text,
  TextField,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface SnapshotRow {
  id: number;
  created_at: string;
  resource_type: "product" | "collection";
  resource_id: string;
  resource_title: string;
  action_type: string;
  readiness_score: number;
  seo_score: number;
  content_hash: string;
  metrics: {
    gsc?: {
      clicks: number;
      impressions: number;
      position: number;
    };
  };
}

interface SnapshotData {
  shop: string;
  available: boolean;
  total: number;
  snapshots: SnapshotRow[];
}

interface LoaderData {
  locale: Locale;
  data: SnapshotData | null;
  error: string | null;
}

interface ActionData {
  ok: boolean;
  message: string;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/optimization-snapshots?limit=25`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as SnapshotData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const form = await request.formData();
  const payload = {
    resource_type: String(form.get("resource_type") || "product"),
    resource_id: String(form.get("resource_id") || ""),
    action_type: String(form.get("action_type") || "add_answer_blocks"),
    hypothesis: String(form.get("hypothesis") || ""),
    notes: String(form.get("notes") || ""),
  };

  if (!payload.resource_id.trim()) {
    return json<ActionData>({ ok: false, message: "Resource ID is required." });
  }

  const resp = await callBackendForShop(
    shop,
    `/api/shops/${shop}/geo/optimization-snapshots`,
    {
      accessToken: session.accessToken,
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
    },
  );
  if (!resp.ok) {
    return json<ActionData>({ ok: false, message: await resp.text() });
  }
  const data = (await resp.json()) as { snapshot_id: number };
  return json<ActionData>({ ok: true, message: `Snapshot #${data.snapshot_id} créé.` });
};

function SnapshotCard({ snapshot }: { snapshot: SnapshotRow }) {
  const gsc = snapshot.metrics.gsc;
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{snapshot.resource_title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{snapshot.resource_id}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge tone="info">{snapshot.resource_type}</Badge>
            <Badge tone="attention">{snapshot.action_type}</Badge>
            <Badge>{snapshot.content_hash}</Badge>
          </InlineStack>
        </InlineStack>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
          {[
            { label: "Readiness", value: `${snapshot.readiness_score}/100` },
            { label: "SEO", value: `${snapshot.seo_score}/100` },
            { label: "Impressions", value: String(gsc?.impressions ?? 0) },
            { label: "Position", value: String(gsc?.position ?? 0) },
          ].map((item) => (
            <BlockStack key={item.label} gap="050">
              <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
              <Text as="p" variant="bodyMd" fontWeight="semibold">{item.value}</Text>
            </BlockStack>
          ))}
        </div>
        <Text as="p" variant="bodySm" tone="subdued">{snapshot.created_at}</Text>
      </BlockStack>
    </Card>
  );
}

export default function GeoSnapshots() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();

  return (
    <Page
      title={t(locale, "geoSnapshots")}
      subtitle={locale === "fr" ? "Snapshots avant optimisation pour validation d'impact" : "Before-optimization snapshots for impact validation"}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/content-hub", locale) }}
    >
      <BlockStack gap="400">
        <Card>
          <Form method="post">
            <BlockStack gap="300">
              <Select
                label="Type de ressource"
                name="resource_type"
                options={[
                  { label: "Product", value: "product" },
                  { label: "Collection", value: "collection" },
                ]}
              />
              <TextField label="Resource ID Shopify" name="resource_id" autoComplete="off" />
              <Select
                label="Action type"
                name="action_type"
                options={[
                  { label: "Add answer blocks", value: "add_answer_blocks" },
                  { label: "Enrich product facts", value: "enrich_product_facts" },
                  { label: "Improve schema", value: "improve_schema" },
                  { label: "Create collection or guide", value: "create_collection_or_guide" },
                ]}
              />
              <TextField label="Hypothesis" name="hypothesis" autoComplete="off" />
              <TextField label="Notes" name="notes" autoComplete="off" />
              <InlineStack align="end">
                <Button submit variant="primary">Créer snapshot</Button>
              </InlineStack>
            </BlockStack>
          </Form>
        </Card>

        {actionData && (
          <Banner tone={actionData.ok ? "success" : "warning"}>
            <Text as="p">{actionData.message}</Text>
          </Banner>
        )}

        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {data && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
              <Card>
                <BlockStack gap="050">
                  <Text as="p" variant="headingLg">{String(data.total)}</Text>
                  <Text as="p" variant="bodySm" tone="subdued">Snapshots</Text>
                </BlockStack>
              </Card>
            </div>
            <BlockStack gap="300">
              {data.snapshots.map((snapshot) => (
                <SnapshotCard key={snapshot.id} snapshot={snapshot} />
              ))}
            </BlockStack>
            {!data.snapshots.length && (
              <Banner tone="info">
                <Text as="p">{t(locale, "noData")}</Text>
              </Banner>
            )}
          </>
        )}
      </BlockStack>
    </Page>
  );
}
