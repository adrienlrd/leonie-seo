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
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface GeoLedgerEvent {
  id: number;
  created_at: string;
  event_type: string;
  resource_type: string;
  resource_id: string;
  resource_title: string;
  action_type: string;
  status: string;
  source: string;
  job_id: string | null;
  hypothesis: string | null;
  before_snapshot: Record<string, unknown>;
  after_snapshot: Record<string, unknown> | null;
  metrics_before: Record<string, unknown>;
  metrics_after: Record<string, unknown> | null;
  estimated_impact: Record<string, unknown>;
  observed_impact: Record<string, unknown> | null;
  notes: string | null;
}

interface GeoLedgerData {
  shop: string;
  available: boolean;
  total: number;
  limit: number;
  offset: number;
  summary: {
    total_events: number;
    by_status: Record<string, number>;
    estimated_revenue: number;
    observed_revenue: number;
    measurement_note: string;
  };
  events: GeoLedgerEvent[];
}

interface LoaderData {
  locale: Locale;
  data: GeoLedgerData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/ledger?limit=50`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as GeoLedgerData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function money(value: number): string {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(value);
}

function statusTone(status: string): "success" | "warning" | "info" | "critical" {
  if (status === "measured") return "success";
  if (status === "applied") return "info";
  if (status === "planned") return "warning";
  return "critical";
}

function EventCard({ event }: { event: GeoLedgerEvent }) {
  const estimatedRevenue = Number(event.estimated_impact.revenue_estimate ?? 0);
  const observedRevenue = event.observed_impact ? Number(event.observed_impact.revenue ?? 0) : null;
  const beforeReadiness = event.before_snapshot.readiness_score;
  const afterReadiness = event.after_snapshot?.readiness_score;

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{event.resource_title || event.resource_id}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{`${event.action_type} · ${event.created_at}`}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge tone={statusTone(event.status)}>{event.status}</Badge>
            <Badge tone="info">{event.event_type}</Badge>
          </InlineStack>
        </InlineStack>

        {event.hypothesis && (
          <Text as="p" variant="bodySm">{event.hypothesis}</Text>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
          {[
            { label: "Revenu estimé", value: money(estimatedRevenue) },
            { label: "Revenu observé", value: observedRevenue === null ? "En attente" : money(observedRevenue) },
            { label: "Readiness avant", value: beforeReadiness === undefined ? "n/a" : String(beforeReadiness) },
            { label: "Readiness après", value: afterReadiness === undefined ? "En attente" : String(afterReadiness) },
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

export default function GeoLedger() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoLedger")}
      subtitle={locale === "fr" ? "Historique des optimisations GEO et preuve d'impact" : "GEO optimization history and impact proof"}
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
                { label: "Événements", value: String(data.summary.total_events) },
                { label: "Estimé", value: money(data.summary.estimated_revenue) },
                { label: "Observé", value: money(data.summary.observed_revenue) },
                { label: "Planifiés", value: String(data.summary.by_status.planned ?? 0) },
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
              <Text as="p">{data.summary.measurement_note}</Text>
            </Banner>

            <BlockStack gap="300">
              {data.events.map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </BlockStack>

            {!data.events.length && (
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
