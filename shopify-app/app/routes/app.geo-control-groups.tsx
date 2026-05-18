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

interface Baseline {
  readiness_score: number;
  impressions: number;
  position: number;
  price: number | null;
  inventory_quantity: number | null;
}

interface ControlCandidate {
  resource_id: string;
  resource_title: string;
  path: string;
  similarity_score: number;
  quality: string;
  match_reasons: string[];
  baseline: Baseline;
}

interface ControlGroup {
  event_id: number;
  snapshot_id: number | null;
  action_type: string;
  status: string;
  quality: string;
  warnings: string[];
  target: {
    resource_id: string;
    resource_title: string;
    path: string;
    baseline: Baseline;
  };
  controls: ControlCandidate[];
}

interface ControlGroupData {
  shop: string;
  available: boolean;
  summary: {
    events_considered: number;
    groups_built: number;
    groups_with_controls: number;
    causality_note: string;
  };
  groups: ControlGroup[];
}

interface LoaderData {
  locale: Locale;
  data: ControlGroupData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/control-groups?top_events=25&controls_per_event=3`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as ControlGroupData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function qualityTone(quality: string): "success" | "warning" | "critical" | "info" {
  if (quality === "strong") return "success";
  if (quality === "usable") return "info";
  if (quality === "missing") return "critical";
  return "warning";
}

function MetricGrid({ baseline }: { baseline: Baseline }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12 }}>
      {[
        { label: "Readiness", value: `${baseline.readiness_score}/100` },
        { label: "Impressions", value: String(baseline.impressions) },
        { label: "Position", value: String(baseline.position) },
        { label: "Prix", value: baseline.price === null ? "n/a" : `${baseline.price} €` },
      ].map((item) => (
        <BlockStack key={item.label} gap="050">
          <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
          <Text as="p" variant="bodyMd" fontWeight="semibold">{item.value}</Text>
        </BlockStack>
      ))}
    </div>
  );
}

function ControlGroupCard({ group }: { group: ControlGroup }) {
  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{group.target.resource_title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{`Event #${group.event_id} · ${group.action_type}`}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge tone={qualityTone(group.quality)}>{group.quality}</Badge>
            <Badge>{group.status}</Badge>
            {group.snapshot_id !== null && <Badge tone="info">{`Snapshot #${group.snapshot_id}`}</Badge>}
          </InlineStack>
        </InlineStack>

        <BlockStack gap="200">
          <Text as="p" variant="bodySm" tone="subdued">Page optimisée</Text>
          <MetricGrid baseline={group.target.baseline} />
        </BlockStack>

        {group.warnings.map((warning) => (
          <Banner key={warning} tone="warning">
            <Text as="p">{warning}</Text>
          </Banner>
        ))}

        <BlockStack gap="300">
          {group.controls.map((control) => (
            <div
              key={control.resource_id}
              style={{
                border: "1px solid var(--p-color-border)",
                borderRadius: 8,
                padding: 12,
              }}
            >
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center" wrap>
                  <BlockStack gap="050">
                    <Text as="h3" variant="headingSm">{control.resource_title}</Text>
                    <Text as="p" variant="bodySm" tone="subdued">{control.path}</Text>
                  </BlockStack>
                  <InlineStack gap="100" blockAlign="center">
                    <Badge tone={qualityTone(control.quality)}>{`${control.similarity_score}/100`}</Badge>
                    <Badge>{control.quality}</Badge>
                  </InlineStack>
                </InlineStack>
                <MetricGrid baseline={control.baseline} />
                <InlineStack gap="100" wrap>
                  {control.match_reasons.map((reason) => (
                    <Badge key={reason} tone="info">{reason}</Badge>
                  ))}
                </InlineStack>
              </BlockStack>
            </div>
          ))}
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

export default function GeoControlGroups() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoControlGroups")}
      subtitle={locale === "fr" ? "Pages témoins similaires pour mesurer l'impact GEO" : "Comparable control pages for GEO impact measurement"}
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
                { label: "Events analysés", value: String(data.summary.events_considered) },
                { label: "Groupes", value: String(data.summary.groups_built) },
                { label: "Avec témoins", value: String(data.summary.groups_with_controls) },
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
              <Text as="p">{data.summary.causality_note}</Text>
            </Banner>

            <BlockStack gap="300">
              {data.groups.map((group) => (
                <ControlGroupCard key={group.event_id} group={group} />
              ))}
            </BlockStack>

            {!data.groups.length && (
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
