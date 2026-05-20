import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Card,
  DataTable,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

type ReadinessLevel = "excellent" | "bon" | "partiel" | "faible";

interface ComponentDetail {
  score: number;
  weight: number;
}

interface RecommendedAction {
  action: string;
  category: string;
  impact_estimate: "low" | "medium" | "high";
  effort_estimate: "low" | "medium" | "high";
}

interface NicheAlert {
  type: string;
  detail: string;
}

interface ReadinessProduct {
  id: string;
  handle: string;
  title: string;
  readiness_score: number;
  level: ReadinessLevel;
  components: Record<string, ComponentDetail>;
  recommended_actions: RecommendedAction[];
  niche_alerts: NicheAlert[];
}

interface CrawlHealth {
  available: boolean;
  critical?: number;
  high?: number;
  medium?: number;
  low?: number;
  info?: number;
}

interface ReadinessData {
  shop: string;
  global_score: number;
  global_level: ReadinessLevel;
  snapshot_age_days: number | null;
  snapshot_freshness_warning: boolean;
  total: number;
  summary: {
    avg_readiness_score: number;
    excellent_products: number;
    bon_products: number;
    partiel_products: number;
    faible_products: number;
  };
  niche_alerts: NicheAlert[];
  crawl_health: CrawlHealth;
  products: ReadinessProduct[];
  generated_at: string;
}

interface LoaderData {
  locale: Locale;
  data: ReadinessData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs): Promise<ReturnType<typeof json>> => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/audit/readiness`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json({ locale, data: null, error: `Backend error ${resp.status}` });
    }
    const data: ReadinessData = await resp.json();
    return json({ locale, data, error: null });
  } catch (err) {
    return json({ locale, data: null, error: String(err) });
  }
};

function levelTone(level: ReadinessLevel): "success" | "info" | "warning" | "critical" {
  if (level === "excellent") return "success";
  if (level === "bon") return "info";
  if (level === "partiel") return "warning";
  return "critical";
}

function levelLabel(level: ReadinessLevel, locale: Locale): string {
  const key = `level${level.charAt(0).toUpperCase()}${level.slice(1)}` as
    | "levelExcellent"
    | "levelBon"
    | "levelPartiel"
    | "levelFaible";
  return t(locale, key);
}

function impactLabel(impact: string, locale: Locale): string {
  if (impact === "high") return t(locale, "impactHigh");
  if (impact === "medium") return t(locale, "impactMedium");
  return t(locale, "impactLow");
}

function effortLabel(effort: string, locale: Locale): string {
  if (effort === "high") return t(locale, "effortHigh");
  if (effort === "medium") return t(locale, "effortMedium");
  return t(locale, "effortLow");
}

export default function AuditReadiness() {
  const { locale, data, error } = useLoaderData<LoaderData>();

  if (error || !data) {
    return (
      <Page
        title={t(locale, "auditReadiness")}
        backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/audit-hub", locale) }}
      >
        <Banner tone="critical">
          <Text as="p">{error ?? t(locale, "auditReadinessNoData")}</Text>
        </Banner>
      </Page>
    );
  }

  const productRows = data.products.slice(0, 50).map((p) => [
    p.title,
    p.handle,
    String(p.readiness_score),
    <Badge key={p.handle} tone={levelTone(p.level)}>{levelLabel(p.level, locale)}</Badge>,
  ]);

  return (
    <Page
      title={t(locale, "auditReadiness")}
      subtitle={t(locale, "auditReadinessSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/audit-hub", locale) }}
    >
      <BlockStack gap="400">
        {data.snapshot_freshness_warning && (
          <Banner tone="warning">
            <Text as="p">{t(locale, "snapshotStale")}</Text>
          </Banner>
        )}

        {/* Global score card */}
        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">{t(locale, "globalScore")}</Text>
            <InlineStack gap="300" align="start">
              <Text as="p" variant="heading2xl" fontWeight="bold">
                {data.global_score}
              </Text>
              <Badge tone={levelTone(data.global_level)}>
                {levelLabel(data.global_level, locale)}
              </Badge>
            </InlineStack>
            <InlineStack gap="400">
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "levelExcellent")}: {data.summary.excellent_products}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "levelBon")}: {data.summary.bon_products}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "levelPartiel")}: {data.summary.partiel_products}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "levelFaible")}: {data.summary.faible_products}
              </Text>
            </InlineStack>
          </BlockStack>
        </Card>

        {/* Crawl health */}
        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">{t(locale, "crawlHealth")}</Text>
            {data.crawl_health.available ? (
              <InlineStack gap="400">
                {(data.crawl_health.critical ?? 0) > 0 && (
                  <Badge tone="critical">{`Critical: ${data.crawl_health.critical}`}</Badge>
                )}
                {(data.crawl_health.high ?? 0) > 0 && (
                  <Badge tone="warning">{`High: ${data.crawl_health.high}`}</Badge>
                )}
                {(data.crawl_health.medium ?? 0) > 0 && (
                  <Badge tone="attention">{`Medium: ${data.crawl_health.medium}`}</Badge>
                )}
                {data.crawl_health.critical === 0 &&
                  data.crawl_health.high === 0 &&
                  data.crawl_health.medium === 0 && (
                    <Badge tone="success">OK</Badge>
                  )}
              </InlineStack>
            ) : (
              <Text as="p" tone="subdued">{t(locale, "crawlHealthUnavailable")}</Text>
            )}
          </BlockStack>
        </Card>

        {/* Niche alerts */}
        {data.niche_alerts.length > 0 && (
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">{t(locale, "nicheAlerts")}</Text>
              {data.niche_alerts.slice(0, 5).map((alert, idx) => (
                <Banner key={idx} tone="warning">
                  <Text as="p">{alert.detail}</Text>
                </Banner>
              ))}
            </BlockStack>
          </Card>
        )}

        {/* Top 3 recommended actions */}
        {data.products.length > 0 && (() => {
          const allActions: (RecommendedAction & { product_title: string })[] = [];
          for (const p of data.products) {
            for (const a of p.recommended_actions) {
              allActions.push({ ...a, product_title: p.title });
              if (allActions.length >= 3) break;
            }
            if (allActions.length >= 3) break;
          }
          return allActions.length > 0 ? (
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">{t(locale, "recommendedActions")}</Text>
                {allActions.map((action, idx) => (
                  <Box key={idx} padding="200" borderWidth="025" borderRadius="200" borderColor="border">
                    <BlockStack gap="100">
                      <Text as="p">{action.action}</Text>
                      <InlineStack gap="200">
                        <Badge>{action.product_title}</Badge>
                        <Badge tone={action.impact_estimate === "high" ? "success" : "attention"}>
                          {impactLabel(action.impact_estimate, locale)}
                        </Badge>
                        <Badge tone="info">{effortLabel(action.effort_estimate, locale)}</Badge>
                      </InlineStack>
                    </BlockStack>
                  </Box>
                ))}
              </BlockStack>
            </Card>
          ) : null;
        })()}

        {/* Product table */}
        {productRows.length > 0 && (
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {t(locale, "products")} ({data.total})
              </Text>
              <DataTable
                columnContentTypes={["text", "text", "numeric", "text"]}
                headings={[
                  t(locale, "title"),
                  "Handle",
                  t(locale, "globalScore"),
                  "Niveau",
                ]}
                rows={productRows}
              />
            </BlockStack>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
