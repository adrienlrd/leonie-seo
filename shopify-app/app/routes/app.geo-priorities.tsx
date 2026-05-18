import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Card,
  InlineStack,
  Page,
  ProgressBar,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface PriorityRow {
  product_id: string;
  handle: string;
  title: string;
  action_type: string;
  action_label: string;
  priority_score: number;
  readiness_score: number;
  readiness_gap: number;
  effort: "low" | "medium" | "high";
  risk: "low" | "medium" | "high";
  confidence: "low" | "medium" | "high";
  inventory_status: string;
  price: number | null;
  impressions: number;
  clicks: number;
  position: number;
  clicks_gain_estimate: number;
  revenue_estimate: number;
  reason: string;
  estimated: boolean;
}

interface PriorityData {
  shop: string;
  available: boolean;
  total: number;
  assumptions: {
    conversion_rate: number;
    average_order_value: number;
    position_improvement: number;
  };
  summary: {
    avg_priority_score: number;
    total_revenue_estimate: number;
    high_confidence_actions: number;
    gsc_connected: boolean;
    estimated: boolean;
    note: string;
  };
  rows: PriorityRow[];
}

interface LoaderData {
  locale: Locale;
  data: PriorityData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/priorities?top=50`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as PriorityData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function money(value: number): string {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(value);
}

function scoreTone(score: number): "success" | "critical" | undefined {
  if (score >= 70) return "success";
  if (score >= 40) return undefined;
  return "critical";
}

function effortTone(effort: PriorityRow["effort"]): "success" | "warning" | "critical" {
  if (effort === "low") return "success";
  if (effort === "medium") return "warning";
  return "critical";
}

function confidenceTone(confidence: PriorityRow["confidence"]): "success" | "warning" | "info" {
  if (confidence === "high") return "success";
  if (confidence === "medium") return "warning";
  return "info";
}

function PriorityCard({ row }: { row: PriorityRow }) {
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{row.title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">/{row.handle}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge tone={scoreTone(row.priority_score)}>{`${row.priority_score} priorité`}</Badge>
            <Badge tone={effortTone(row.effort)}>{`Effort ${row.effort}`}</Badge>
            <Badge tone={confidenceTone(row.confidence)}>{`Confiance ${row.confidence}`}</Badge>
          </InlineStack>
        </InlineStack>

        <ProgressBar progress={Math.min(row.priority_score, 100)} size="small" tone={scoreTone(row.priority_score)} />

        <BlockStack gap="100">
          <Text as="p" variant="bodyMd" fontWeight="semibold">{row.action_label}</Text>
          <Text as="p" variant="bodySm" tone="subdued">{row.reason}</Text>
        </BlockStack>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
          {[
            { label: "Readiness", value: `${row.readiness_score} / 100` },
            { label: "Impressions", value: String(row.impressions) },
            { label: "Position", value: row.position ? String(row.position) : "n/a" },
            { label: "Clics gagnables", value: String(row.clicks_gain_estimate) },
            { label: "Revenu estimé", value: money(row.revenue_estimate) },
            { label: "Stock", value: row.inventory_status },
          ].map((item) => (
            <BlockStack key={item.label} gap="050">
              <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
              <Text as="p" variant="bodyMd" fontWeight="semibold">{item.value}</Text>
            </BlockStack>
          ))}
        </div>
      </BlockStack>
    </Card>
  );
}

export default function GeoPriorities() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoPriorities")}
      subtitle={locale === "fr" ? "Actions GEO classées par potentiel business estimé" : "GEO actions ranked by estimated business upside"}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/content-hub", locale) }}
    >
      <BlockStack gap="400">
        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {data && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
              {[
                { label: "Score priorité moyen", value: `${data.summary.avg_priority_score} / 100` },
                { label: "Potentiel estimé", value: money(data.summary.total_revenue_estimate) },
                { label: "Actions haute confiance", value: String(data.summary.high_confidence_actions) },
                { label: "GSC", value: data.summary.gsc_connected ? "Connecté" : "Fallback" },
              ].map((item) => (
                <Card key={item.label}>
                  <BlockStack gap="050">
                    <Text as="p" variant="headingLg">{item.value}</Text>
                    <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
                  </BlockStack>
                </Card>
              ))}
            </div>

            <Banner tone="info">
              <Text as="p">{data.summary.note}</Text>
            </Banner>

            <BlockStack gap="300">
              {data.rows.map((row) => (
                <PriorityCard key={row.product_id || row.handle} row={row} />
              ))}
            </BlockStack>

            {!data.rows.length && (
              <Banner tone="warning">
                <Text as="p">{t(locale, "noData")}</Text>
              </Banner>
            )}
          </>
        )}
      </BlockStack>
    </Page>
  );
}
