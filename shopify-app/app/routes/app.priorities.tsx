import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Card,
  InlineGrid,
  InlineStack,
  Page,
  ProgressBar,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

type RiskStatus = "safe" | "review_required" | "protected";
type ConfidenceLevel = "low" | "medium" | "high";
type EffortLevel = "low" | "medium" | "high";

interface Evidence {
  source: string;
  metric: string;
  value: number | string;
}

interface Estimates {
  impact: string;
  confidence: ConfidenceLevel;
  effort: EffortLevel;
  risk: string;
  click_gain_estimate: number | null;
  revenue_estimate_eur: number | null;
  estimate_basis: string;
}

interface SuccessMetric {
  name: string;
  current_value: number;
  target_value: number;
  measurement_window_days: number;
  source: string;
}

interface RiskGuard {
  status: RiskStatus;
  reasons: string[];
  override_required: boolean;
}

interface NicheAlert {
  type: string;
  message: string;
}

interface ActionDossier {
  rank: number;
  action_id: string;
  product_handle: string;
  product_title: string;
  action_type: string;
  action_label: string;
  priority_score: number;
  why_now: string;
  evidence: Evidence[];
  estimates: Estimates;
  success_metric: SuccessMetric;
  risk_guard: RiskGuard;
  niche_alerts: NicheAlert[];
}

interface PrioritiesData {
  shop: string;
  generated_at: string;
  scope: string;
  actions: ActionDossier[];
  candidates_evaluated: number;
  sparse_signal: boolean;
  llm_used: boolean;
  fallback_reason: string | null;
  next_refresh_at: string;
  snapshot_age_days: number | null;
}

interface LoaderData {
  locale: Locale;
  data: PrioritiesData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs): Promise<ReturnType<typeof json>> => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  const url = new URL(request.url);
  const plan = url.searchParams.get("plan") ?? "free";

  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/priorities?scope=active&plan=${plan}`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json({ locale, data: null, error: `Backend error ${resp.status}` });
    }
    const data: PrioritiesData = await resp.json();
    return json({ locale, data, error: null });
  } catch (err) {
    return json({ locale, data: null, error: String(err) });
  }
};

function confidenceTone(c: ConfidenceLevel): "success" | "info" | "warning" {
  if (c === "high") return "success";
  if (c === "medium") return "info";
  return "warning";
}

function effortTone(e: EffortLevel): "success" | "warning" | "critical" {
  if (e === "low") return "success";
  if (e === "medium") return "warning";
  return "critical";
}

function riskTone(r: RiskStatus): "success" | "warning" | "critical" {
  if (r === "safe") return "success";
  if (r === "review_required") return "warning";
  return "critical";
}

function rankBadge(rank: number): string {
  if (rank === 1) return "#1";
  if (rank === 2) return "#2";
  return "#3";
}

export default function PrioritiesPage() {
  const { locale, data, error } = useLoaderData<LoaderData>();

  if (error || !data) {
    return (
      <Page
        title={t(locale, "priorities")}
        backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/audit-hub", locale) }}
      >
        <Banner tone="critical">
          <Text as="p">{error ?? t(locale, "prioritiesEmpty")}</Text>
        </Banner>
      </Page>
    );
  }

  return (
    <Page
      title={t(locale, "priorities")}
      subtitle={t(locale, "prioritiesSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/audit-hub", locale) }}
    >
      <BlockStack gap="400">
        {/* Meta bar */}
        <Card>
          <InlineStack gap="400" align="start" wrap>
            <Text as="p" variant="bodySm" tone="subdued">
              {data.candidates_evaluated} {t(locale, "candidatesEvaluated")}
            </Text>
            {data.llm_used && (
              <Badge tone="success">{t(locale, "llmUsed")}</Badge>
            )}
            {data.sparse_signal && (
              <Badge tone="warning">{t(locale, "sparseSignal")}</Badge>
            )}
          </InlineStack>
        </Card>

        {/* Sparse signal or empty state */}
        {data.actions.length === 0 ? (
          <Banner tone="info">
            <Text as="p">{t(locale, "prioritiesEmpty")}</Text>
          </Banner>
        ) : (
          <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="400">
            {data.actions.map((action) => (
              <Card key={action.action_id}>
                <BlockStack gap="300">
                  {/* Rank + title */}
                  <InlineStack gap="200" align="start">
                    <Badge tone="info">{rankBadge(action.rank)}</Badge>
                    <Text as="h3" variant="headingSm">{action.product_title}</Text>
                  </InlineStack>

                  {/* Action label */}
                  <Text as="p" variant="bodySm" fontWeight="semibold">{action.action_label}</Text>

                  {/* Priority score progress */}
                  <InlineStack gap="200" align="start">
                    <Text as="p" variant="bodySm" tone="subdued">
                      {t(locale, "priorityRank")}: {action.priority_score}/100
                    </Text>
                  </InlineStack>
                  <ProgressBar
                    progress={action.priority_score}
                    tone={action.priority_score >= 70 ? "success" : "highlight"}
                    size="small"
                  />

                  {/* Why now */}
                  <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border">
                    <Text as="p" variant="bodySm" tone="subdued">{t(locale, "whyNow")}</Text>
                    <Text as="p" variant="bodySm">{action.why_now}</Text>
                  </Box>

                  {/* Estimates badges */}
                  <InlineStack gap="200" wrap>
                    <Badge tone={confidenceTone(action.estimates.confidence)}>
                      {action.estimates.confidence}
                    </Badge>
                    <Badge tone={effortTone(action.estimates.effort)}>
                      {`${t(locale, "effortLabel")}: ${action.estimates.effort}`}
                    </Badge>
                    <Badge tone={riskTone(action.risk_guard.status)}>
                      {`${t(locale, "riskLabel")}: ${action.risk_guard.status}`}
                    </Badge>
                  </InlineStack>

                  {/* Risk guard override warning */}
                  {action.risk_guard.override_required && (
                    <Banner tone="warning">
                      <Text as="p" variant="bodySm">{t(locale, "overrideRequired")}</Text>
                    </Banner>
                  )}

                  {/* Success metric */}
                  <BlockStack gap="100">
                    <Text as="p" variant="bodySm" tone="subdued">{t(locale, "successMetric")}</Text>
                    <Text as="p" variant="bodySm">
                      {action.success_metric.name}: {action.success_metric.current_value}
                      {" → "}{action.success_metric.target_value}
                      {" ("}{action.success_metric.measurement_window_days}j{")"}
                    </Text>
                  </BlockStack>

                  {/* Niche alerts */}
                  {action.niche_alerts.length > 0 && (
                    <BlockStack gap="100">
                      {action.niche_alerts.map((alert, idx) => (
                        <Banner key={idx} tone="warning">
                          <Text as="p" variant="bodySm">{alert.message}</Text>
                        </Banner>
                      ))}
                    </BlockStack>
                  )}
                </BlockStack>
              </Card>
            ))}
          </InlineGrid>
        )}
      </BlockStack>
    </Page>
  );
}
