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
import { Sparkline } from "../components/Sparkline";

interface SeriesPoint {
  date: string;
  value: number;
}

interface ProgressCurveData {
  window_days: number;
  series: Record<string, SeriesPoint[]>;
  flags: {
    low_volume: boolean;
    incomplete_tracking: boolean;
    out_of_stock_pages: number;
    price_changed_pages: number;
  };
  totals: {
    snapshots_in_window: number;
    events_in_window: number;
    total_impressions: number;
  };
}

interface RetentionMilestone {
  label: string;
  days: number;
  due_date: string;
  status: "completed" | "active" | "upcoming";
  events_reached: number;
  total_events: number;
  message_fr: string;
  message_en: string;
}

interface RetentionData {
  has_active_events: boolean;
  active_event_count: number;
  elapsed_days?: number;
  milestones: RetentionMilestone[];
  next_milestone: { label: string; due_date: string; days_remaining: number } | null;
  retention_message_fr: string;
  retention_message_en: string;
}

interface ImpactReportGsc {
  impressions_before: number | null;
  impressions_after: number | null;
  impressions_delta: number | null;
  clicks_before: number | null;
  clicks_after: number | null;
  clicks_delta: number | null;
  position_before: number | null;
  position_after: number | null;
}

interface ImpactReportEntry {
  event_id: number;
  resource_title: string;
  action_type: string;
  applied_at: string;
  verdict: string;
  verdict_summary: string;
  next_recommendation: string;
  confidence: { score: number; label: string };
  gsc?: ImpactReportGsc;
}

interface ImpactReportData {
  reports: ImpactReportEntry[];
  summary: { total: number; by_verdict: Record<string, number> };
}

interface ConfidenceData {
  summary: { avg_score: number; by_label: Record<string, number> };
}

interface ControlGroupCandidate {
  resource_title: string;
  similarity_score: number;
  quality: string;
}

interface ControlGroup {
  event_id: number;
  action_type: string;
  target: { resource_title: string };
  controls: ControlGroupCandidate[];
}

interface ControlGroupsData {
  summary: { events_considered: number; groups_built: number; groups_with_controls: number };
  groups: ControlGroup[];
}

interface NextBestAction {
  source_resource_title: string;
  action_type: string;
  priority: "high" | "medium" | "low";
  rationale: string;
  suggested_resources: Array<{ resource_title: string; similarity_reason: string }>;
}

interface NextBestActionsData {
  actions: NextBestAction[];
  summary: { total_actions: number; high_priority: number };
}

interface LoaderData {
  locale: Locale;
  progress: ProgressCurveData | null;
  retention: RetentionData | null;
  impactReport: ImpactReportData | null;
  confidence: ConfidenceData | null;
  controlGroups: ControlGroupsData | null;
  nextActions: NextBestActionsData | null;
}

async function fetchJson<T>(promise: Promise<Response>): Promise<T | null> {
  try {
    const resp = await promise;
    if (!resp.ok) return null;
    return (await resp.json()) as T;
  } catch {
    return null;
  }
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const be = (path: string) =>
    callBackendForShop(shop, path, { accessToken: session.accessToken });

  const [progress, retention, impactReport, confidence, controlGroups, nextActions] =
    await Promise.all([
      fetchJson<ProgressCurveData>(be(`/api/shops/${shop}/geo/progress-curve?days=90`)),
      fetchJson<RetentionData>(be(`/api/shops/${shop}/geo/retention-milestones`)),
      fetchJson<ImpactReportData>(be(`/api/shops/${shop}/geo/impact-report`)),
      fetchJson<ConfidenceData>(be(`/api/shops/${shop}/geo/confidence-scores`)),
      fetchJson<ControlGroupsData>(be(`/api/shops/${shop}/geo/control-groups`)),
      fetchJson<NextBestActionsData>(be(`/api/shops/${shop}/geo/next-best-actions`)),
    ]);

  return json<LoaderData>({
    locale,
    progress,
    retention,
    impactReport,
    confidence,
    controlGroups,
    nextActions,
  });
};

const VERDICT_KEYS: Record<string, string> = {
  positif_probable: "measureVerdictPositifProbable",
  neutre: "measureVerdictNeutre",
  inconclusif: "measureVerdictInconclusif",
  négatif_possible: "measureVerdictNegatifPossible",
};

const RECOMMENDATION_KEYS: Record<string, string> = {
  répliquer: "measureRecommendationRepliquer",
  ajuster: "measureRecommendationAjuster",
  rollback: "measureRecommendationRollback",
  attendre: "measureRecommendationAttendre",
};

const CONFIDENCE_LABEL_KEYS: Record<string, string> = {
  données_insuffisantes: "measureConfidenceLabelDonneesInsuffisantes",
  signal_faible: "measureConfidenceLabelSignalFaible",
  impact_probable: "measureConfidenceLabelImpactProbable",
  impact_fort: "measureConfidenceLabelImpactFort",
};

const MILESTONE_STATUS_KEYS: Record<string, string> = {
  completed: "measureMilestoneStatusCompleted",
  active: "measureMilestoneStatusActive",
  upcoming: "measureMilestoneStatusUpcoming",
};

const PRIORITY_KEYS: Record<string, string> = {
  high: "measurePriorityHigh",
  medium: "measurePriorityMedium",
  low: "measurePriorityLow",
};

function localize(locale: Locale, map: Record<string, string>, value: string): string {
  const key = map[value];
  return key ? t(locale, key) : value;
}

function verdictTone(verdict: string): "success" | "info" | "critical" | undefined {
  if (verdict === "positif_probable") return "success";
  if (verdict === "négatif_possible") return "critical";
  if (verdict === "neutre") return "info";
  return undefined;
}

function milestoneTone(status: string): "success" | "info" | undefined {
  if (status === "completed") return "success";
  if (status === "active") return "info";
  return undefined;
}

function priorityTone(priority: string): "critical" | "warning" | "info" {
  if (priority === "high") return "critical";
  if (priority === "medium") return "warning";
  return "info";
}

const SERIES_CONFIG: Array<{ key: string; labelKey: string; format: (value: number) => string }> = [
  { key: "geo_score", labelKey: "measureSeriesGeoScore", format: (v) => String(Math.round(v)) },
  { key: "seo_score", labelKey: "measureSeriesSeoScore", format: (v) => String(Math.round(v)) },
  { key: "clicks", labelKey: "measureSeriesClicks", format: (v) => Math.round(v).toLocaleString("fr-FR") },
  { key: "impressions", labelKey: "measureSeriesImpressions", format: (v) => Math.round(v).toLocaleString("fr-FR") },
  { key: "sessions", labelKey: "measureSeriesSessions", format: (v) => Math.round(v).toLocaleString("fr-FR") },
];

export default function MeasurePage() {
  const { locale, progress, retention, impactReport, confidence, controlGroups, nextActions } =
    useLoaderData<typeof loader>() as LoaderData;

  const visibleSeries = progress
    ? SERIES_CONFIG.filter((config) => (progress.series[config.key]?.length ?? 0) > 0)
    : [];

  return (
    <Page
      title={t(locale, "measureTitle")}
      subtitle={t(locale, "measureSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        {progress?.flags.incomplete_tracking && (
          <Banner
            tone="info"
            title={t(locale, "measureIncompleteTrackingBanner")}
            action={{ content: t(locale, "measureConnectGoogle"), url: localizedPath("/app/onboarding", locale) }}
          />
        )}

        {progress && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">{t(locale, "measureTotalsTitle")}</Text>
              <InlineStack gap="600" wrap>
                <BlockStack gap="050">
                  <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureTotalsSnapshots")}</Text>
                  <Text as="span" variant="headingLg">{progress.totals.snapshots_in_window}</Text>
                </BlockStack>
                <BlockStack gap="050">
                  <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureTotalsEvents")}</Text>
                  <Text as="span" variant="headingLg">{progress.totals.events_in_window}</Text>
                </BlockStack>
                <BlockStack gap="050">
                  <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureTotalsImpressions")}</Text>
                  <Text as="span" variant="headingLg">{progress.totals.total_impressions.toLocaleString("fr-FR")}</Text>
                </BlockStack>
              </InlineStack>
              {progress.flags.low_volume && (
                <Banner tone="info">
                  <Text as="p">{t(locale, "measureLowVolumeBanner")}</Text>
                </Banner>
              )}
            </BlockStack>
          </Card>
        )}

        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">{t(locale, "measureTrendsTitle")}</Text>
            {visibleSeries.length > 0 ? (
              <InlineStack gap="600" wrap>
                {visibleSeries.map((config) => (
                  <Sparkline
                    key={config.key}
                    data={progress!.series[config.key]}
                    label={t(locale, config.labelKey)}
                    formatValue={config.format}
                  />
                ))}
              </InlineStack>
            ) : (
              <Text as="p" tone="subdued">{t(locale, "measureTrendsEmpty")}</Text>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">{t(locale, "measureRetentionTitle")}</Text>
            {retention?.has_active_events ? (
              <BlockStack gap="300">
                {retention.elapsed_days !== undefined && (
                  <Text as="p" tone="subdued">
                    {retention.elapsed_days} {t(locale, "measureRetentionElapsed")}
                  </Text>
                )}
                <InlineStack gap="400" wrap>
                  {retention.milestones.map((milestone) => (
                    <Box key={milestone.label} padding="300" background="bg-surface-secondary" borderRadius="200">
                      <BlockStack gap="100">
                        <InlineStack gap="200" blockAlign="center">
                          <Text as="span" variant="headingMd">{milestone.label}</Text>
                          <Badge tone={milestoneTone(milestone.status)}>
                            {localize(locale, MILESTONE_STATUS_KEYS, milestone.status)}
                          </Badge>
                        </InlineStack>
                        <Text as="p" variant="bodySm" tone="subdued">{milestone.due_date}</Text>
                        <Text as="p" variant="bodySm">
                          {milestone.events_reached}/{milestone.total_events} {t(locale, "measureMilestoneEvents")}
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {locale === "fr" ? milestone.message_fr : milestone.message_en}
                        </Text>
                      </BlockStack>
                    </Box>
                  ))}
                </InlineStack>
                {retention.next_milestone && (
                  <Text as="p" variant="bodySm">
                    {t(locale, "measureNextMilestone")}: {retention.next_milestone.label} — {retention.next_milestone.due_date}
                  </Text>
                )}
                <Text as="p" variant="bodySm" tone="subdued">
                  {locale === "fr" ? retention.retention_message_fr : retention.retention_message_en}
                </Text>
              </BlockStack>
            ) : (
              <Text as="p" tone="subdued">{t(locale, "measureRetentionEmpty")}</Text>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">{t(locale, "measureImpactReportTitle")}</Text>
            {impactReport && impactReport.reports.length > 0 ? (
              <BlockStack gap="300">
                {impactReport.reports.map((report) => (
                  <Box key={report.event_id} padding="300" background="bg-surface-secondary" borderRadius="200">
                    <BlockStack gap="200">
                      <InlineStack gap="200" blockAlign="center" wrap>
                        <Text as="span" fontWeight="semibold">{report.resource_title}</Text>
                        <Badge>{report.action_type}</Badge>
                        <Badge tone={verdictTone(report.verdict)}>
                          {localize(locale, VERDICT_KEYS, report.verdict)}
                        </Badge>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {(report.applied_at || "").slice(0, 10) || "—"}
                        </Text>
                      </InlineStack>
                      {report.verdict_summary ? (
                        <Text as="p" variant="bodyMd">{report.verdict_summary}</Text>
                      ) : null}
                      {report.gsc && report.gsc.impressions_after != null ? (
                        <InlineStack gap="400" wrap>
                          <BlockStack gap="050">
                            <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureColImpressions")}</Text>
                            <Text as="span" variant="bodySm">
                              {report.gsc.impressions_before ?? "—"} → {report.gsc.impressions_after ?? "—"}
                              {report.gsc.impressions_delta != null && (
                                <> ({report.gsc.impressions_delta > 0 ? "+" : ""}{report.gsc.impressions_delta})</>
                              )}
                            </Text>
                          </BlockStack>
                          <BlockStack gap="050">
                            <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureColClicks")}</Text>
                            <Text as="span" variant="bodySm">
                              {report.gsc.clicks_before ?? "—"} → {report.gsc.clicks_after ?? "—"}
                              {report.gsc.clicks_delta != null && (
                                <> ({report.gsc.clicks_delta > 0 ? "+" : ""}{report.gsc.clicks_delta})</>
                              )}
                            </Text>
                          </BlockStack>
                          <BlockStack gap="050">
                            <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureColPosition")}</Text>
                            <Text as="span" variant="bodySm">
                              {report.gsc.position_before != null ? report.gsc.position_before.toFixed(1) : "—"} → {report.gsc.position_after != null ? report.gsc.position_after.toFixed(1) : "—"}
                            </Text>
                          </BlockStack>
                        </InlineStack>
                      ) : null}
                      <InlineStack gap="200" blockAlign="center">
                        <Text as="span" variant="bodySm" tone="subdued">
                          {t(locale, "measureColConfidence")}: {report.confidence.score} — {localize(locale, CONFIDENCE_LABEL_KEYS, report.confidence.label)}
                        </Text>
                        <Text as="span" variant="bodySm">
                          → {localize(locale, RECOMMENDATION_KEYS, report.next_recommendation)}
                        </Text>
                      </InlineStack>
                    </BlockStack>
                  </Box>
                ))}
              </BlockStack>
            ) : (
              <Text as="p" tone="subdued">{t(locale, "measureImpactReportEmpty")}</Text>
            )}
          </BlockStack>
        </Card>

        {confidence && impactReport && impactReport.reports.length > 0 && (
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">{t(locale, "measureConfidenceTitle")}</Text>
              <InlineStack gap="400" blockAlign="center" wrap>
                <BlockStack gap="050">
                  <Text as="span" variant="bodySm" tone="subdued">{t(locale, "measureConfidenceAvg")}</Text>
                  <Text as="span" variant="headingLg">{confidence.summary.avg_score}</Text>
                </BlockStack>
                <InlineStack gap="200" wrap>
                  {Object.entries(confidence.summary.by_label)
                    .filter(([, count]) => count > 0)
                    .map(([label, count]) => (
                      <Badge key={label}>{`${localize(locale, CONFIDENCE_LABEL_KEYS, label)}: ${count}`}</Badge>
                    ))}
                </InlineStack>
              </InlineStack>
            </BlockStack>
          </Card>
        )}

        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">{t(locale, "measureControlGroupsTitle")}</Text>
            {controlGroups && controlGroups.groups.length > 0 ? (
              <DataTable
                columnContentTypes={["text", "text", "text", "text"]}
                headings={[
                  t(locale, "measureColTarget"),
                  t(locale, "measureColAction"),
                  t(locale, "measureColBestControl"),
                  t(locale, "measureColSimilarity"),
                ]}
                rows={controlGroups.groups.map((group) => {
                  const best = group.controls[0];
                  return [
                    group.target.resource_title,
                    group.action_type,
                    best ? best.resource_title : "—",
                    best ? `${best.similarity_score}% (${best.quality})` : "—",
                  ];
                })}
              />
            ) : (
              <Text as="p" tone="subdued">{t(locale, "measureControlGroupsEmpty")}</Text>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <Text as="h2" variant="headingMd">{t(locale, "measureNextActionsTitle")}</Text>
              {nextActions && nextActions.summary.high_priority > 0 && (
                <Badge tone="critical">{String(nextActions.summary.high_priority)}</Badge>
              )}
            </InlineStack>
            {nextActions && nextActions.actions.length > 0 ? (
              <BlockStack gap="300">
                {nextActions.actions.map((action, index) => (
                  <Box key={index} padding="300" background="bg-surface-secondary" borderRadius="200">
                    <BlockStack gap="100">
                      <InlineStack gap="200" blockAlign="center" wrap>
                        <Badge tone={priorityTone(action.priority)}>
                          {localize(locale, PRIORITY_KEYS, action.priority)}
                        </Badge>
                        <Text as="span" fontWeight="semibold">{action.source_resource_title}</Text>
                        <Badge>{localize(locale, RECOMMENDATION_KEYS, action.action_type)}</Badge>
                      </InlineStack>
                      <Text as="p" variant="bodySm" tone="subdued">{action.rationale}</Text>
                      {action.suggested_resources.length > 0 && (
                        <Text as="p" variant="bodySm">
                          {t(locale, "measureSuggestedFor")}: {action.suggested_resources.map((r) => r.resource_title).join(", ")}
                        </Text>
                      )}
                    </BlockStack>
                  </Box>
                ))}
              </BlockStack>
            ) : (
              <Text as="p" tone="subdued">{t(locale, "measureNextActionsEmpty")}</Text>
            )}
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
