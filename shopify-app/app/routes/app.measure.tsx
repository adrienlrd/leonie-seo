import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Badge, BlockStack, Card, DataTable, InlineGrid, InlineStack, Page, Text } from "@shopify/polaris";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, t, type Locale } from "../lib/i18n";
import { authenticate } from "../shopify.server";

interface LoaderData {
  locale: Locale;
  progress: any | null;
  ledger: any | null;
  milestones: any | null;
  impact: any | null;
  confidence: any | null;
  controls: any | null;
  nextBestActions: any | null;
}

async function fetchOk<T>(promise: Promise<Response>): Promise<T | null> {
  try {
    const resp = await promise;
    if (!resp.ok) return null;
    return (await resp.json()) as T;
  } catch (_error) {
    return null;
  }
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const be = (path: string) => callBackendForShop(shop, path, { accessToken: session.accessToken });
  const [progress, ledger, milestones, impact, confidence, controls, nextBestActions] = await Promise.all([
    fetchOk(be(`/api/shops/${shop}/geo/progress-curve`)),
    fetchOk(be(`/api/shops/${shop}/geo/ledger`)),
    fetchOk(be(`/api/shops/${shop}/geo/retention-milestones`)),
    fetchOk(be(`/api/shops/${shop}/geo/impact-report`)),
    fetchOk(be(`/api/shops/${shop}/geo/confidence-scores`)),
    fetchOk(be(`/api/shops/${shop}/geo/control-groups`)),
    fetchOk(be(`/api/shops/${shop}/geo/next-best-actions`)),
  ]);
  return json<LoaderData>({ locale, progress, ledger, milestones, impact, confidence, controls, nextBestActions });
};

function numberValue(value: unknown): string {
  if (typeof value === "number") return Intl.NumberFormat("fr-FR").format(value);
  return "—";
}

function latestSeriesPoint(progress: any | null): any | null {
  const series = progress?.series ?? progress?.points ?? progress?.daily ?? [];
  return Array.isArray(series) && series.length > 0 ? series[series.length - 1] : null;
}

export default function MeasurePage() {
  const { locale, progress, ledger, milestones, impact, confidence, controls, nextBestActions } = useLoaderData<typeof loader>();
  const latest = latestSeriesPoint(progress);
  const events = Array.isArray(ledger?.events) ? ledger.events.slice(0, 8) : [];
  const reports = Array.isArray(impact?.reports) ? impact.reports.slice(0, 6) : [];
  const scores = Array.isArray(confidence?.scores) ? confidence.scores.slice(0, 6) : [];
  const actions = Array.isArray(nextBestActions?.actions) ? nextBestActions.actions.slice(0, 5) : [];
  const controlRows = Array.isArray(controls?.comparisons) ? controls.comparisons.slice(0, 5) : [];

  return (
    <Page title={t(locale, "measureTitle")} subtitle={t(locale, "measureSubtitle")}>
      <BlockStack gap="400">
        <InlineGrid columns={{ xs: 1, md: 3 }} gap="300">
          <Card><BlockStack gap="100"><Text as="p" tone="subdued">{t(locale, "measureClicks")}</Text><Text as="p" variant="headingLg">{numberValue(latest?.clicks ?? progress?.summary?.clicks)}</Text></BlockStack></Card>
          <Card><BlockStack gap="100"><Text as="p" tone="subdued">{t(locale, "measureImpressions")}</Text><Text as="p" variant="headingLg">{numberValue(latest?.impressions ?? progress?.summary?.impressions)}</Text></BlockStack></Card>
          <Card><BlockStack gap="100"><Text as="p" tone="subdued">{t(locale, "measureSessions")}</Text><Text as="p" variant="headingLg">{numberValue(latest?.sessions ?? progress?.summary?.sessions)}</Text></BlockStack></Card>
        </InlineGrid>

        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">{t(locale, "measureTimeline")}</Text>
            {events.length ? <DataTable columnContentTypes={["text", "text", "text", "text"]} headings={[t(locale, "status"), t(locale, "product"), t(locale, "action"), "Date"]} rows={events.map((event: any) => [event.status ?? "—", event.resource_id ?? event.product_id ?? "—", event.field ?? event.action_type ?? "—", event.applied_at ?? event.created_at ?? "—"])} /> : <Text as="p" tone="subdued">{t(locale, "noData")}</Text>}
          </BlockStack>
        </Card>

        <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
          <Card><BlockStack gap="300"><Text as="h2" variant="headingMd">{t(locale, "measureMilestones")}</Text>{Array.isArray(milestones?.milestones) && milestones.milestones.length ? milestones.milestones.slice(0, 6).map((m: any, i: number) => <InlineStack key={i} align="space-between"><Text as="span">{m.label ?? m.window ?? m.event_id ?? "—"}</Text><Badge tone={m.verdict === "positive" ? "success" : m.verdict === "negative" ? "critical" : "info"}>{m.verdict ?? m.status ?? "pending"}</Badge></InlineStack>) : <Text as="p" tone="subdued">{t(locale, "noData")}</Text>}</BlockStack></Card>
          <Card><BlockStack gap="300"><Text as="h2" variant="headingMd">{t(locale, "measureConfidence")}</Text>{scores.length ? scores.map((score: any, i: number) => <InlineStack key={i} align="space-between"><Text as="span">{score.event_id ?? score.resource_id ?? `#${i + 1}`}</Text><Badge tone="info">{`${numberValue(score.confidence ?? score.score)}%`}</Badge></InlineStack>) : <Text as="p" tone="subdued">{t(locale, "noData")}</Text>}</BlockStack></Card>
        </InlineGrid>

        <Card><BlockStack gap="300"><Text as="h2" variant="headingMd">{t(locale, "measureImpact")}</Text>{reports.length ? <DataTable columnContentTypes={["text", "text", "text"]} headings={[t(locale, "product"), t(locale, "status"), t(locale, "measureConfidence")]} rows={reports.map((report: any) => [report.resource_id ?? report.product_id ?? "—", report.verdict ?? report.status ?? "—", numberValue(report.confidence)])} /> : <Text as="p" tone="subdued">{t(locale, "noData")}</Text>}</BlockStack></Card>
        <Card><BlockStack gap="300"><Text as="h2" variant="headingMd">{t(locale, "measureControls")}</Text>{controlRows.length ? <DataTable columnContentTypes={["text", "numeric", "numeric"]} headings={[t(locale, "product"), t(locale, "measureModified"), t(locale, "measureControl")]} rows={controlRows.map((row: any) => [row.resource_id ?? row.event_id ?? "—", numberValue(row.modified_clicks ?? row.modified_delta), numberValue(row.control_clicks ?? row.control_delta)])} /> : <Text as="p" tone="subdued">{t(locale, "noData")}</Text>}</BlockStack></Card>
        <Card><BlockStack gap="300"><Text as="h2" variant="headingMd">{t(locale, "measureNextActions")}</Text>{actions.length ? actions.map((action: any, i: number) => <BlockStack key={i} gap="050"><Text as="h3" variant="headingSm">{action.title ?? action.action ?? action.resource_id ?? `#${i + 1}`}</Text><Text as="p" tone="subdued">{action.reason ?? action.summary ?? action.field ?? "—"}</Text></BlockStack>) : <Text as="p" tone="subdued">{t(locale, "noData")}</Text>}</BlockStack></Card>
      </BlockStack>
    </Page>
  );
}
