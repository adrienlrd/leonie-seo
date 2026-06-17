import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Card,
  InlineStack,
  Page,
  ProgressBar,
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

interface ProductAction {
  event_id: number;
  action_type: string;
  field: string;
  old_value: string;
  new_value: string;
  gsc_before: GscMetrics;
  gsc_after: GscMetrics | null;
}

interface ValidationDate {
  date: string;
  j28_date: string;
  window_status: "complete" | "waiting" | "insufficient";
  window_message_fr: string;
  window_message_en: string;
  days_remaining: number;
  actions: ProductAction[];
  traffic_28d: GscMetrics | null;
}

interface ProductEntry {
  resource_id: string;
  resource_type: string;
  resource_title: string;
  latest_applied_at: string;
  validation_dates: ValidationDate[];
  total_actions: number;
}

interface LoaderData {
  locale: Locale;
  products: ProductEntry[];
  summary: { total_products: number; total_actions: number };
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let products: ProductEntry[] = [];
  let summary = { total_products: 0, total_actions: 0 };

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

function windowTone(status: string): "success" | "warning" | "critical" {
  if (status === "complete") return "success";
  if (status === "waiting") return "warning";
  return "critical";
}

function windowBadgeLabel(status: string, daysRemaining: number, locale: Locale): string {
  if (status === "complete") return locale === "fr" ? "28 j ✓" : "28 d ✓";
  if (status === "waiting") return locale === "fr" ? `J-${daysRemaining}` : `D-${daysRemaining}`;
  return locale === "fr" ? "< 28 j" : "< 28 d";
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
              <Text as="span" variant="headingLg">{summary.total_actions}</Text>
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
              <BlockStack gap="400">
                {/* Product header */}
                <InlineStack gap="200" blockAlign="center" wrap>
                  <Text as="h2" variant="headingMd">{product.resource_title}</Text>
                  <Badge tone="info">{product.resource_type}</Badge>
                  <Text as="span" variant="bodySm" tone="subdued">
                    {product.total_actions} {t(locale, "analyseActionsCount")}
                  </Text>
                </InlineStack>

                {/* Validation dates for this product */}
                {product.validation_dates.map((vd) => (
                  <Box key={vd.date} padding="300" background="bg-surface-secondary" borderRadius="200">
                    <BlockStack gap="200">
                      {/* Date header + window badge */}
                      <InlineStack gap="200" blockAlign="center" wrap>
                        <Text as="h3" variant="headingSm">
                          {t(locale, "analyseAppliedAt")} {vd.date}
                        </Text>
                        <Badge tone={windowTone(vd.window_status)}>
                          {windowBadgeLabel(vd.window_status, vd.days_remaining, locale)}
                        </Badge>
                      </InlineStack>

                      {/* Window status */}
                      {vd.window_status === "waiting" && (
                        <Banner tone="warning">
                          <BlockStack gap="200">
                            <Text as="p">
                              {locale === "fr" ? vd.window_message_fr : vd.window_message_en}
                            </Text>
                            <ProgressBar
                              progress={Math.round(((28 - vd.days_remaining) / 28) * 100)}
                              tone="highlight"
                              size="small"
                            />
                          </BlockStack>
                        </Banner>
                      )}

                      {vd.window_status === "insufficient" && (
                        <Banner tone="critical">
                          <Text as="p">
                            {locale === "fr" ? vd.window_message_fr : vd.window_message_en}
                          </Text>
                        </Banner>
                      )}

                      {/* GSC traffic at J+28 — only when window complete */}
                      {vd.window_status === "complete" && vd.traffic_28d && (
                        <>
                          <Text as="span" variant="bodySm" tone="subdued">
                            {t(locale, "analyseJ28Date")}: {vd.j28_date}
                          </Text>
                          <InlineStack gap="600" wrap>
                            <BlockStack gap="050">
                              <Text as="span" variant="bodySm" tone="subdued">Impressions</Text>
                              <Text as="span" variant="headingSm">
                                {vd.traffic_28d.impressions.toLocaleString("fr-FR")}
                              </Text>
                            </BlockStack>
                            <BlockStack gap="050">
                              <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureColClicks")}</Text>
                              <Text as="span" variant="headingSm">
                                {vd.traffic_28d.clicks.toLocaleString("fr-FR")}
                              </Text>
                            </BlockStack>
                            <BlockStack gap="050">
                              <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureColPosition")}</Text>
                              <Text as="span" variant="headingSm">
                                {vd.traffic_28d.position > 0 ? vd.traffic_28d.position.toFixed(1) : "—"}
                              </Text>
                            </BlockStack>
                          </InlineStack>
                        </>
                      )}

                      {/* Actions for this date */}
                      {vd.actions.map((action) => (
                        <Box key={action.event_id} padding="200" background="bg-surface-tertiary" borderRadius="100">
                          <BlockStack gap="100">
                            <Badge>{fieldLabel(action.field)}</Badge>
                            {action.old_value ? (
                              <InlineStack gap="200">
                                <Text as="span" variant="bodySm" tone="subdued">{t(locale, "analyseBefore")}</Text>
                                <Text as="span" variant="bodySm">{action.old_value}</Text>
                              </InlineStack>
                            ) : null}
                            {action.new_value ? (
                              <InlineStack gap="200">
                                <Text as="span" variant="bodySm" tone="subdued">{t(locale, "analyseAfter")}</Text>
                                <Text as="span" variant="bodySm">{action.new_value}</Text>
                              </InlineStack>
                            ) : null}
                            {vd.window_status === "complete" && action.gsc_after ? (
                              <InlineStack gap="400" wrap>
                                <Text as="span" variant="bodySm">
                                  Imp: {action.gsc_before.impressions} → {action.gsc_after.impressions}
                                  {action.gsc_after.impressions !== action.gsc_before.impressions && (
                                    <> ({action.gsc_after.impressions > action.gsc_before.impressions ? "+" : ""}
                                    {action.gsc_after.impressions - action.gsc_before.impressions})</>
                                  )}
                                </Text>
                                <Text as="span" variant="bodySm">
                                  Pos: {action.gsc_before.position > 0 ? action.gsc_before.position.toFixed(1) : "—"} → {action.gsc_after.position > 0 ? action.gsc_after.position.toFixed(1) : "—"}
                                </Text>
                              </InlineStack>
                            ) : null}
                          </BlockStack>
                        </Box>
                      ))}
                    </BlockStack>
                  </Box>
                ))}
              </BlockStack>
            </Card>
          ))
        )}
      </BlockStack>
    </Page>
  );
}
