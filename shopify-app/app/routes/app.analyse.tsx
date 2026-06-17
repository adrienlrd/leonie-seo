import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Box,
  Card,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface GscMetrics {
  clicks: number;
  impressions: number;
  position: number;
}

interface ProductEvent {
  event_id: number;
  action_type: string;
  applied_at: string;
  status: string;
  measurement_status: string;
  field: string;
  old_value: string;
  new_value: string;
  gsc_before: GscMetrics;
  gsc_after: GscMetrics | null;
}

interface ProductChange {
  field: string;
  old_value: string;
  new_value: string;
  applied_at: string;
}

interface ProductEntry {
  resource_id: string;
  resource_type: string;
  resource_title: string;
  resource_path: string;
  events: ProductEvent[];
  changes: ProductChange[];
  traffic_28d: GscMetrics;
  latest_applied_at: string;
  j28_date: string;
}

interface LoaderData {
  locale: Locale;
  products: ProductEntry[];
  summary: { total_products: number; total_events: number };
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let products: ProductEntry[] = [];
  let summary = { total_products: 0, total_events: 0 };

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/analysis-overview`,
      { accessToken: session.accessToken },
    );
    if (resp.ok) {
      const data = await resp.json();
      products = data.products ?? [];
      summary = data.summary ?? summary;
    }
  } catch {
    // fail-open
  }

  return json<LoaderData>({ locale, products, summary });
};

function fieldLabel(field: string): string {
  const labels: Record<string, string> = {
    "seo.title": "Meta title",
    "seo.description": "Meta description",
    descriptionHtml: "Description produit",
    "metafield.custom.json_ld": "Schema JSON-LD",
  };
  return labels[field] ?? field;
}

function statusTone(status: string): "success" | "info" | undefined {
  if (status === "measured") return "success";
  if (status === "applied") return "info";
  return undefined;
}

export default function AnalysePage() {
  const { locale, products, summary } = useLoaderData<typeof loader>() as LoaderData;

  return (
    <Page
      title={t(locale, "analyseTitle")}
      subtitle={t(locale, "analyseSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
      secondaryActions={[
        { content: t(locale, "measureNav"), url: localizedPath("/app/measure", locale) },
      ]}
    >
      <BlockStack gap="400">
        <Card>
          <InlineStack gap="600" wrap>
            <BlockStack gap="050">
              <Text as="span" variant="bodySm" tone="subdued">{t(locale, "analyseProductsOptimized")}</Text>
              <Text as="span" variant="headingLg">{summary.total_products}</Text>
            </BlockStack>
            <BlockStack gap="050">
              <Text as="span" variant="bodySm" tone="subdued">{t(locale, "analyseTotalActions")}</Text>
              <Text as="span" variant="headingLg">{summary.total_events}</Text>
            </BlockStack>
          </InlineStack>
        </Card>

        {products.length === 0 ? (
          <Card>
            <Text as="p" tone="subdued">{t(locale, "analyseEmpty")}</Text>
          </Card>
        ) : (
          products.map((product) => (
            <Card key={product.resource_id}>
              <BlockStack gap="300">
                <InlineStack gap="200" blockAlign="center" wrap>
                  <Text as="h2" variant="headingMd">{product.resource_title}</Text>
                  <Badge tone="info">{product.resource_type}</Badge>
                </InlineStack>

                <InlineStack gap="600" wrap>
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">{t(locale, "analyseAppliedAt")}</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">{product.latest_applied_at || "—"}</Text>
                  </BlockStack>
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">{t(locale, "analyseJ28Date")}</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">{product.j28_date || "—"}</Text>
                  </BlockStack>
                </InlineStack>

                <Box padding="300" background="bg-surface-secondary" borderRadius="200">
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingSm">{t(locale, "analyseTraffic28d")}</Text>
                    <InlineStack gap="600" wrap>
                      <BlockStack gap="050">
                        <Text as="span" variant="bodySm" tone="subdued">Impressions</Text>
                        <Text as="span" variant="headingMd">
                          {product.traffic_28d.impressions.toLocaleString("fr-FR")}
                        </Text>
                      </BlockStack>
                      <BlockStack gap="050">
                        <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureColClicks")}</Text>
                        <Text as="span" variant="headingMd">
                          {product.traffic_28d.clicks.toLocaleString("fr-FR")}
                        </Text>
                      </BlockStack>
                      <BlockStack gap="050">
                        <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureColPosition")}</Text>
                        <Text as="span" variant="headingMd">
                          {product.traffic_28d.position > 0 ? product.traffic_28d.position.toFixed(1) : "—"}
                        </Text>
                      </BlockStack>
                    </InlineStack>
                  </BlockStack>
                </Box>

                {product.events.length > 0 && (
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingSm">{t(locale, "analyseChanges")}</Text>
                    {product.events.map((event) => (
                      <Box key={event.event_id} padding="200" background="bg-surface-tertiary" borderRadius="100">
                        <BlockStack gap="100">
                          <InlineStack gap="200" blockAlign="center" wrap>
                            <Badge>{fieldLabel(event.field)}</Badge>
                            <Badge tone={statusTone(event.status)}>
                              {event.status === "measured" ? t(locale, "analyseMeasured") : t(locale, "analyseApplied")}
                            </Badge>
                            <Text as="span" variant="bodySm" tone="subdued">{event.applied_at}</Text>
                          </InlineStack>
                          {event.old_value ? (
                            <BlockStack gap="050">
                              <Text as="span" variant="bodySm" tone="subdued">{t(locale, "analyseBefore")}</Text>
                              <Text as="p" variant="bodySm">{event.old_value}</Text>
                            </BlockStack>
                          ) : null}
                          {event.new_value ? (
                            <BlockStack gap="050">
                              <Text as="span" variant="bodySm" tone="subdued">{t(locale, "analyseAfter")}</Text>
                              <Text as="p" variant="bodySm">{event.new_value}</Text>
                            </BlockStack>
                          ) : null}
                          {event.gsc_after ? (
                            <InlineStack gap="400" wrap>
                              <Text as="span" variant="bodySm">
                                Impressions: {event.gsc_before.impressions} → {event.gsc_after.impressions}
                                {event.gsc_after.impressions !== event.gsc_before.impressions && (
                                  <> ({event.gsc_after.impressions > event.gsc_before.impressions ? "+" : ""}
                                  {event.gsc_after.impressions - event.gsc_before.impressions})</>
                                )}
                              </Text>
                              <Text as="span" variant="bodySm">
                                Position: {event.gsc_before.position > 0 ? event.gsc_before.position.toFixed(1) : "—"} → {event.gsc_after.position > 0 ? event.gsc_after.position.toFixed(1) : "—"}
                              </Text>
                            </InlineStack>
                          ) : null}
                        </BlockStack>
                      </Box>
                    ))}
                  </BlockStack>
                )}
              </BlockStack>
            </Card>
          ))
        )}
      </BlockStack>
    </Page>
  );
}
