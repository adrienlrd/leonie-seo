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

interface TimelineWindow {
  key: string;
  label: string;
  days_after_apply: number;
  due_at: string;
  status: string;
  purpose: string;
  message: string;
}

interface ValidationTimeline {
  event_id: number;
  snapshot_id: number | null;
  resource_title: string;
  action_type: string;
  status: string;
  measurement_status: string | null;
  applied_at: string;
  baseline: {
    score_before: number | null;
    impressions: number;
  };
  windows: TimelineWindow[];
}

interface TimelineData {
  shop: string;
  available: boolean;
  summary: {
    events_considered: number;
    timelines_built: number;
    status_counts: Record<string, number>;
    next_due_at: string | null;
    time_note: string;
    min_impressions: number;
  };
  timelines: ValidationTimeline[];
}

interface LoaderData {
  locale: Locale;
  data: TimelineData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/validation-timeline`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as TimelineData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function statusTone(status: string): "success" | "warning" | "critical" | "info" {
  if (status === "ready") return "success";
  if (status === "measuring") return "info";
  if (status === "inconclusive") return "critical";
  return "warning";
}

function TimelineCard({ timeline }: { timeline: ValidationTimeline }) {
  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{timeline.resource_title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{`Event #${timeline.event_id} · ${timeline.action_type}`}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge>{timeline.status}</Badge>
            {timeline.snapshot_id !== null && <Badge tone="info">{`Snapshot #${timeline.snapshot_id}`}</Badge>}
            {timeline.measurement_status && <Badge tone="attention">{timeline.measurement_status}</Badge>}
          </InlineStack>
        </InlineStack>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
          {[
            { label: "Applied", value: timeline.applied_at },
            { label: "Score avant", value: timeline.baseline.score_before === null ? "n/a" : `${timeline.baseline.score_before}/100` },
            { label: "Impressions base", value: String(timeline.baseline.impressions) },
          ].map((item) => (
            <BlockStack key={item.label} gap="050">
              <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
              <Text as="p" variant="bodyMd" fontWeight="semibold">{item.value}</Text>
            </BlockStack>
          ))}
        </div>

        <BlockStack gap="200">
          {timeline.windows.map((window) => (
            <div
              key={window.key}
              style={{
                border: "1px solid var(--p-color-border)",
                borderRadius: 8,
                padding: 12,
              }}
            >
              <InlineStack align="space-between" blockAlign="start" wrap>
                <BlockStack gap="050">
                  <Text as="h3" variant="headingSm">{`${window.label} · ${window.due_at}`}</Text>
                  <Text as="p" variant="bodySm" tone="subdued">{window.purpose}</Text>
                  <Text as="p" variant="bodySm">{window.message}</Text>
                </BlockStack>
                <Badge tone={statusTone(window.status)}>{window.status}</Badge>
              </InlineStack>
            </div>
          ))}
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

export default function GeoValidationTimeline() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoValidationTimeline")}
      subtitle={locale === "fr" ? "Fenêtres J+7/J+30/J+60/J+90 pour valider l'impact" : "J+7/J+30/J+60/J+90 windows for impact validation"}
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
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
              {[
                { label: "Timelines", value: String(data.summary.timelines_built) },
                { label: "Ready", value: String(data.summary.status_counts.ready ?? 0) },
                { label: "Measuring", value: String(data.summary.status_counts.measuring ?? 0) },
                { label: "Pending", value: String(data.summary.status_counts.pending ?? 0) },
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
              <Text as="p">{data.summary.time_note}</Text>
            </Banner>

            <BlockStack gap="300">
              {data.timelines.map((timeline) => (
                <TimelineCard key={timeline.event_id} timeline={timeline} />
              ))}
            </BlockStack>

            {!data.timelines.length && (
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
