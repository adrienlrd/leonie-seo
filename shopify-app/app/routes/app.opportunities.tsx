import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useSearchParams } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Card,
  InlineStack,
  Page,
  ProgressBar,
  Tabs,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

type Tier = "high" | "medium" | "low";

interface Signal {
  type: string;
  weight: number;
  value: number;
  evidence: Record<string, unknown>;
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

interface Opportunity {
  product_id: string;
  handle: string;
  title: string;
  opportunity_score: number;
  tier: Tier;
  primary_reason: string;
  signals: Signal[];
  matched_queries: string[];
  matched_intents: string[];
  recommended_actions: RecommendedAction[];
  niche_alerts: NicheAlert[];
  confidence: "low" | "medium" | "high";
}

interface OpportunitySummary {
  by_tier: { high: number; medium: number; low: number };
  by_intent: Record<string, number>;
  average_score: number;
}

interface OpportunitiesData {
  shop: string;
  total_products_scanned: number;
  opportunities: Opportunity[];
  summary: OpportunitySummary;
  snapshot_age_days: number | null;
  generated_at: string;
}

interface LoaderData {
  locale: Locale;
  data: OpportunitiesData | null;
  error: string | null;
  intent: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs): Promise<ReturnType<typeof json>> => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  const url = new URL(request.url);
  const intent = url.searchParams.get("intent");
  const intentParam = intent ? `&intent=${encodeURIComponent(intent)}` : "";

  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/opportunities?scope=active&top=20${intentParam}`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json({ locale, data: null, error: `Backend error ${resp.status}`, intent });
    }
    const data: OpportunitiesData = await resp.json();
    return json({ locale, data, error: null, intent });
  } catch (err) {
    return json({ locale, data: null, error: String(err), intent });
  }
};

function tierTone(tier: Tier): "success" | "warning" | "info" {
  if (tier === "high") return "success";
  if (tier === "medium") return "warning";
  return "info";
}

function tierLabel(tier: Tier, locale: Locale): string {
  if (tier === "high") return t(locale, "tierHigh");
  if (tier === "medium") return t(locale, "tierMedium");
  return t(locale, "tierLow");
}

function impactLabel(impact: string, locale: Locale): string {
  if (impact === "high") return t(locale, "impactHigh");
  if (impact === "medium") return t(locale, "impactMedium");
  return t(locale, "impactLow");
}

function confidenceTone(confidence: string): "success" | "info" | "warning" {
  if (confidence === "high") return "success";
  if (confidence === "medium") return "info";
  return "warning";
}

export default function OpportunitiesPage() {
  const { locale, data, error } = useLoaderData<LoaderData>();
  const [, setSearchParams] = useSearchParams();

  if (error || !data) {
    return (
      <Page
        title={t(locale, "opportunities")}
        backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/audit-hub", locale) }}
      >
        <Banner tone="critical">
          <Text as="p">{error ?? t(locale, "opportunitiesEmpty")}</Text>
        </Banner>
      </Page>
    );
  }

  const intentKeys = Object.keys(data.summary.by_intent);
  const tabSelected = (intent: string | null) => {
    const idx = intent ? intentKeys.indexOf(intent) + 1 : 0;
    return idx < 0 ? 0 : idx;
  };

  const tabs = [
    { id: "all", content: locale === "fr" ? "Tous" : "All", panelID: "all-panel" },
    ...intentKeys.map((k) => ({
      id: k,
      content: k.charAt(0).toUpperCase() + k.slice(1),
      panelID: `${k}-panel`,
    })),
  ];

  const { locale: _l, data: _d, error: _e, intent } = useLoaderData<LoaderData>();
  const selected = tabSelected(intent);

  const handleTabChange = (selectedTabIndex: number) => {
    if (selectedTabIndex === 0) {
      setSearchParams({});
    } else {
      setSearchParams({ intent: intentKeys[selectedTabIndex - 1] });
    }
  };

  return (
    <Page
      title={t(locale, "opportunities")}
      subtitle={t(locale, "opportunitiesSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/audit-hub", locale) }}
    >
      <BlockStack gap="400">
        {/* Summary bar */}
        <Card>
          <BlockStack gap="200">
            <InlineStack gap="400" align="start">
              <Text as="p" variant="bodySm" tone="subdued">
                {data.total_products_scanned} {t(locale, "opportunitiesTotal")}
              </Text>
              <Badge tone="success">{`${t(locale, "tierHigh")}: ${data.summary.by_tier.high}`}</Badge>
              <Badge tone="warning">{`${t(locale, "tierMedium")}: ${data.summary.by_tier.medium}`}</Badge>
              <Badge tone="info">{`${t(locale, "tierLow")}: ${data.summary.by_tier.low}`}</Badge>
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "opportunityScore")}: {data.summary.average_score}
              </Text>
            </InlineStack>
          </BlockStack>
        </Card>

        {/* Intent filter tabs */}
        {tabs.length > 1 && (
          <Tabs tabs={tabs} selected={selected} onSelect={handleTabChange} />
        )}

        {/* Opportunity list */}
        {data.opportunities.length === 0 ? (
          <Banner tone="info">
            <Text as="p">{t(locale, "opportunitiesEmpty")}</Text>
          </Banner>
        ) : (
          <BlockStack gap="300">
            {data.opportunities.map((opp) => (
              <Card key={opp.handle}>
                <BlockStack gap="200">
                  <InlineStack gap="300" align="start">
                    <Text as="h3" variant="headingSm">{opp.title}</Text>
                    <Badge tone={tierTone(opp.tier)}>{tierLabel(opp.tier, locale)}</Badge>
                    <Badge tone={confidenceTone(opp.confidence)}>{opp.confidence}</Badge>
                  </InlineStack>

                  {/* Score progress bar */}
                  <InlineStack gap="200" align="start">
                    <Text as="p" variant="bodySm" tone="subdued">
                      {t(locale, "opportunityScore")}: {opp.opportunity_score}/100
                    </Text>
                  </InlineStack>
                  <ProgressBar
                    progress={opp.opportunity_score}
                    tone={opp.tier === "high" ? "success" : opp.tier === "medium" ? "highlight" : "primary"}
                    size="small"
                  />

                  {/* Primary reason */}
                  <Text as="p" variant="bodySm">{opp.primary_reason}</Text>

                  {/* Niche alerts */}
                  {opp.niche_alerts.length > 0 && (
                    <BlockStack gap="100">
                      {opp.niche_alerts.map((alert, idx) => (
                        <Banner key={idx} tone="warning">
                          <Text as="p" variant="bodySm">{alert.detail}</Text>
                        </Banner>
                      ))}
                    </BlockStack>
                  )}

                  {/* Matched intents */}
                  {opp.matched_intents.length > 0 && (
                    <InlineStack gap="200">
                      <Text as="p" variant="bodySm" tone="subdued">{t(locale, "matchedIntents")}:</Text>
                      {opp.matched_intents.map((intent) => (
                        <Badge key={intent} tone="info">{intent}</Badge>
                      ))}
                    </InlineStack>
                  )}

                  {/* Matched queries */}
                  {opp.matched_queries.length > 0 && (
                    <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border">
                      <Text as="p" variant="bodySm" tone="subdued">{t(locale, "matchedQueries")}:</Text>
                      <Text as="p" variant="bodySm">{opp.matched_queries.slice(0, 3).join(" · ")}</Text>
                    </Box>
                  )}

                  {/* Recommended actions */}
                  {opp.recommended_actions.length > 0 && (
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySm" fontWeight="semibold">{t(locale, "recommendedActions")}:</Text>
                      {opp.recommended_actions.map((action, idx) => (
                        <InlineStack key={idx} gap="200" align="start">
                          <Text as="p" variant="bodySm">{action.action}</Text>
                          <Badge tone={action.impact_estimate === "high" ? "success" : "attention"}>
                            {impactLabel(action.impact_estimate, locale)}
                          </Badge>
                        </InlineStack>
                      ))}
                    </BlockStack>
                  )}
                </BlockStack>
              </Card>
            ))}
          </BlockStack>
        )}
      </BlockStack>
    </Page>
  );
}
