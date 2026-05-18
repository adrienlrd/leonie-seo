import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Card,
  InlineStack,
  List,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface WeeklyAction {
  product_id: string;
  handle: string;
  title: string;
  action_label: string;
  priority_score: number;
  readiness_score: number;
  effort: "low" | "medium" | "high";
  risk: "low" | "medium" | "high";
  confidence: "low" | "medium" | "high";
  impressions: number;
  clicks_gain_estimate: number;
  revenue_estimate: number;
  weekly_message: string;
  next_steps: string[];
}

interface WeeklyData {
  shop: string;
  available: boolean;
  total_candidates: number;
  assumptions: {
    conversion_rate: number;
    average_order_value: number;
    position_improvement: number;
  };
  summary: {
    weekly_actions: number;
    estimated_revenue: number;
    estimated_clicks: number;
    high_confidence_actions: number;
    note: string;
  };
  actions: WeeklyAction[];
}

interface LoaderData {
  locale: Locale;
  data: WeeklyData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/weekly-actions?limit=3`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as WeeklyData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function money(value: number): string {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(value);
}

function effortTone(effort: WeeklyAction["effort"]): "success" | "warning" | "critical" {
  if (effort === "low") return "success";
  if (effort === "medium") return "warning";
  return "critical";
}

function confidenceTone(confidence: WeeklyAction["confidence"]): "success" | "warning" | "info" {
  if (confidence === "high") return "success";
  if (confidence === "medium") return "warning";
  return "info";
}

function ActionCard({ action, index }: { action: WeeklyAction; index: number }) {
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="p" variant="bodySm" tone="subdued">{`Action ${index + 1}`}</Text>
            <Text as="h2" variant="headingMd">{action.action_label}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{`${action.title} · /${action.handle}`}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge tone={action.priority_score >= 70 ? "success" : action.priority_score >= 40 ? "warning" : "critical"}>
              {`${action.priority_score} priorité`}
            </Badge>
            <Badge tone={effortTone(action.effort)}>{`Effort ${action.effort}`}</Badge>
            <Badge tone={confidenceTone(action.confidence)}>{`Confiance ${action.confidence}`}</Badge>
          </InlineStack>
        </InlineStack>

        <Text as="p" variant="bodyMd">{action.weekly_message}</Text>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
          {[
            { label: "Readiness", value: `${action.readiness_score} / 100` },
            { label: "Impressions", value: String(action.impressions) },
            { label: "Clics estimés", value: String(action.clicks_gain_estimate) },
            { label: "Gain estimé", value: money(action.revenue_estimate) },
          ].map((item) => (
            <BlockStack key={item.label} gap="050">
              <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
              <Text as="p" variant="bodyMd" fontWeight="semibold">{item.value}</Text>
            </BlockStack>
          ))}
        </div>

        <BlockStack gap="100">
          <Text as="h3" variant="headingSm">Étapes proposées</Text>
          <List type="bullet">
            {action.next_steps.map((step) => (
              <List.Item key={step}>{step}</List.Item>
            ))}
          </List>
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

export default function GeoWeekly() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoWeekly")}
      subtitle={locale === "fr" ? "Les 3 actions GEO à traiter cette semaine" : "The 3 GEO actions to handle this week"}
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
                { label: "Actions semaine", value: String(data.summary.weekly_actions) },
                { label: "Gain estimé", value: money(data.summary.estimated_revenue) },
                { label: "Clics estimés", value: String(data.summary.estimated_clicks) },
                { label: "Haute confiance", value: String(data.summary.high_confidence_actions) },
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
              {data.actions.map((action, index) => (
                <ActionCard key={action.product_id || action.handle} action={action} index={index} />
              ))}
            </BlockStack>

            {!data.actions.length && (
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
