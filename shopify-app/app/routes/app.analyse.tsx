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

interface ProductEntry {
  resource_id: string;
  resource_type: string;
  resource_title: string;
  actions: ProductAction[];
  traffic_28d: GscMetrics | null;
}

interface ApplicationDate {
  date: string;
  j28_date: string;
  window_status: "complete" | "waiting" | "insufficient";
  window_message_fr: string;
  window_message_en: string;
  days_remaining: number;
  products: ProductEntry[];
  total_actions: number;
}

interface LoaderData {
  locale: Locale;
  applicationDates: ApplicationDate[];
  summary: { total_dates: number; total_products: number; total_actions: number };
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let applicationDates: ApplicationDate[] = [];
  let summary = { total_dates: 0, total_products: 0, total_actions: 0 };

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/analysis-overview`,
      { accessToken: session.accessToken },
    );
    if (resp.ok) {
      const data = await resp.json();
      applicationDates = data.application_dates ?? [];
      summary = data.summary ?? summary;
    }
  } catch {
    // fail-open
  }

  return json<LoaderData>({ locale, applicationDates, summary });
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
  if (status === "complete") {
    return locale === "fr" ? "28 j ✓" : "28 d ✓";
  }
  if (status === "waiting") {
    return locale === "fr" ? `J-${daysRemaining}` : `D-${daysRemaining}`;
  }
  return locale === "fr" ? "< 28 j" : "< 28 d";
}

export default function AnalysePage() {
  const { locale, applicationDates, summary } = useLoaderData<typeof loader>() as LoaderData;

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
              <Text as="span" variant="bodySm" tone="subdued">{t(locale, "analyseTotalDates")}</Text>
              <Text as="span" variant="headingLg">{summary.total_dates}</Text>
            </BlockStack>
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

        {applicationDates.length === 0 ? (
          <Card>
            <Text as="p" tone="subdued">{t(locale, "analyseEmpty")}</Text>
          </Card>
        ) : (
          applicationDates.map((appDate) => (
            <Card key={appDate.date}>
              <BlockStack gap="300">
                {/* Date header + window status */}
                <InlineStack gap="200" blockAlign="center" wrap>
                  <Text as="h2" variant="headingMd">
                    {t(locale, "analyseAppliedAt")} {appDate.date}
                  </Text>
                  <Badge tone={windowTone(appDate.window_status)}>
                    {windowBadgeLabel(appDate.window_status, appDate.days_remaining, locale)}
                  </Badge>
                  <Text as="span" variant="bodySm" tone="subdued">
                    {appDate.total_actions} {t(locale, "analyseActionsCount")}
                  </Text>
                </InlineStack>

                {/* Window status message */}
                {appDate.window_status === "waiting" && (
                  <Banner tone="warning">
                    <BlockStack gap="200">
                      <Text as="p">
                        {locale === "fr" ? appDate.window_message_fr : appDate.window_message_en}
                      </Text>
                      <ProgressBar
                        progress={Math.round(((28 - appDate.days_remaining) / 28) * 100)}
                        tone="highlight"
                        size="small"
                      />
                    </BlockStack>
                  </Banner>
                )}

                {appDate.window_status === "insufficient" && (
                  <Banner tone="critical">
                    <Text as="p">
                      {locale === "fr" ? appDate.window_message_fr : appDate.window_message_en}
                    </Text>
                  </Banner>
                )}

                {appDate.window_status === "complete" && (
                  <Text as="p" variant="bodySm" tone="subdued">
                    {t(locale, "analyseJ28Date")}: {appDate.j28_date}
                  </Text>
                )}

                {/* Products in this date */}
                {appDate.products.map((product) => (
                  <Box key={product.resource_id} padding="300" background="bg-surface-secondary" borderRadius="200">
                    <BlockStack gap="200">
                      <InlineStack gap="200" blockAlign="center">
                        <Text as="h3" variant="headingSm">{product.resource_title}</Text>
                        <Badge tone="info">{product.resource_type}</Badge>
                      </InlineStack>

                      {/* GSC traffic at J+28 — only shown when window is complete */}
                      {appDate.window_status === "complete" && product.traffic_28d && (
                        <Box padding="200" background="bg-surface-tertiary" borderRadius="100">
                          <InlineStack gap="600" wrap>
                            <BlockStack gap="050">
                              <Text as="span" variant="bodySm" tone="subdued">Impressions</Text>
                              <Text as="span" variant="headingSm">
                                {product.traffic_28d.impressions.toLocaleString("fr-FR")}
                              </Text>
                            </BlockStack>
                            <BlockStack gap="050">
                              <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureColClicks")}</Text>
                              <Text as="span" variant="headingSm">
                                {product.traffic_28d.clicks.toLocaleString("fr-FR")}
                              </Text>
                            </BlockStack>
                            <BlockStack gap="050">
                              <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureColPosition")}</Text>
                              <Text as="span" variant="headingSm">
                                {product.traffic_28d.position > 0 ? product.traffic_28d.position.toFixed(1) : "—"}
                              </Text>
                            </BlockStack>
                          </InlineStack>
                        </Box>
                      )}

                      {/* Actions applied */}
                      {product.actions.map((action) => (
                        <Box key={action.event_id} padding="200" borderRadius="100">
                          <BlockStack gap="100">
                            <InlineStack gap="200" blockAlign="center" wrap>
                              <Badge>{fieldLabel(action.field)}</Badge>
                            </InlineStack>
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
                            {appDate.window_status === "complete" && action.gsc_after ? (
                              <InlineStack gap="400" wrap>
                                <Text as="span" variant="bodySm">
                                  Imp: {action.gsc_before.impressions} → {action.gsc_after.impressions}
                                  {action.gsc_after.impressions !== action.gsc_before.impressions && (
                                    <> ({action.gsc_after.impressions > action.gsc_before.impressions ? "+" : ""}
                                    {action.gsc_after.impressions - action.gsc_before.impressions})</>
                                  )}
                                </Text>
                                <Text as="span" variant="bodySm">
                                  Pos: {action.gsc_before.position > 0 ? action.gsc_before.position.toFixed(1) : "—"} → {action.gsc_after?.position > 0 ? action.gsc_after.position.toFixed(1) : "—"}
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
