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

interface RiskRow {
  product_id: string;
  handle: string;
  title: string;
  guard_status: "protected" | "review_required" | "safe";
  risk_score: number;
  confirmation_required: boolean;
  recommended_policy: string;
  reasons: string[];
  signals: {
    readiness_score: number;
    impressions: number;
    position: number;
    revenue_estimate: number;
    inventory_status: string;
    confidence: string;
  };
}

interface RiskData {
  shop: string;
  available: boolean;
  gsc_connected: boolean;
  total: number;
  summary: {
    protected: number;
    review_required: number;
    safe: number;
    confirmation_required: number;
    policy_note: string;
  };
  rows: RiskRow[];
}

interface LoaderData {
  locale: Locale;
  data: RiskData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/risk-guard?top=100`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as RiskData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function money(value: number): string {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(value);
}

function statusTone(status: RiskRow["guard_status"]): "critical" | "warning" | "success" {
  if (status === "protected") return "critical";
  if (status === "review_required") return "warning";
  return "success";
}

function statusLabel(status: RiskRow["guard_status"]): string {
  if (status === "protected") return "Protégée";
  if (status === "review_required") return "Revue requise";
  return "Standard";
}

function RiskCard({ row }: { row: RiskRow }) {
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{row.title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">/{row.handle}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge tone={statusTone(row.guard_status)}>{statusLabel(row.guard_status)}</Badge>
            <Badge tone={row.confirmation_required ? "critical" : "success"}>
              {row.confirmation_required ? "Confirmation forte" : "Revue standard"}
            </Badge>
            <Badge tone="info">{`${row.risk_score} risque`}</Badge>
          </InlineStack>
        </InlineStack>

        <Text as="p" variant="bodySm">{row.recommended_policy}</Text>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
          {[
            { label: "Readiness", value: `${row.signals.readiness_score} / 100` },
            { label: "Impressions", value: String(row.signals.impressions) },
            { label: "Position", value: row.signals.position ? String(row.signals.position) : "n/a" },
            { label: "Revenu estimé", value: money(row.signals.revenue_estimate) },
            { label: "Stock", value: row.signals.inventory_status },
          ].map((item) => (
            <BlockStack key={item.label} gap="050">
              <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
              <Text as="p" variant="bodyMd" fontWeight="semibold">{item.value}</Text>
            </BlockStack>
          ))}
        </div>

        <List type="bullet">
          {row.reasons.map((reason) => (
            <List.Item key={reason}>{reason}</List.Item>
          ))}
        </List>
      </BlockStack>
    </Card>
  );
}

export default function GeoRiskGuard() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoRiskGuard")}
      subtitle={locale === "fr" ? "Pages à protéger avant optimisation GEO" : "Pages to protect before GEO optimization"}
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
                { label: "Protégées", value: String(data.summary.protected) },
                { label: "Revue requise", value: String(data.summary.review_required) },
                { label: "Standard", value: String(data.summary.safe) },
                { label: "Confirmations", value: String(data.summary.confirmation_required) },
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
              <Text as="p">{data.summary.policy_note}</Text>
            </Banner>

            <BlockStack gap="300">
              {data.rows.map((row) => (
                <RiskCard key={row.product_id || row.handle} row={row} />
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
