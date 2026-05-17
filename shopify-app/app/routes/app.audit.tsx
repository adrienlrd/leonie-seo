import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { useState } from "react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Page,
  Text,
  Tooltip,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Issue {
  resource_type: string;
  resource_id: string;
  resource_title: string;
  issue_type: string;
  severity: string;
  current_value: string | null;
  detail: string;
}

interface SEOScore {
  total: number;
  components: Record<string, number>;
  issue_count: Record<string, number>;
}

interface CrawlIssue {
  url: string;
  issue_type: string;
  severity: string;
  detail: string;
}

interface CrawlStatus {
  available: boolean;
  issues: CrawlIssue[];
}

interface IceRow {
  ice_score: number;
  impact: number;
  confidence: number;
  effort: number;
  resource_type: string;
  resource_title: string;
  issue_type: string;
  severity: string;
  impressions: number;
  position: number | null;
  url: string | null;
  detail: string;
}

interface LoaderData {
  locale: Locale;
  shop: string;
  issues: Issue[];
  score: SEOScore | null;
  ice: IceRow[];
  error: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
};

const SEVERITY_TONE: Record<
  string,
  "critical" | "warning" | "attention" | "info" | "new"
> = {
  critical: "critical",
  high: "warning",
  medium: "attention",
  low: "info",
  info: "new",
};

const ISSUE_TYPE_LABELS: Record<string, string> = {
  missing_meta_title: "Title manquant",
  too_short_meta_title: "Title trop court",
  too_long_meta_title: "Title trop long",
  duplicate_meta_title: "Title dupliqué",
  missing_meta_description: "Description manquante",
  too_short_meta_description: "Description trop courte",
  too_long_meta_description: "Description trop longue",
  duplicate_meta_description: "Description dupliquée",
  missing_alt_text: "Alt text manquant",
  too_long_alt_text: "Alt text trop long",
  shopify_duplicate_url: "URL dupliquée Shopify",
  page_404: "Page 404",
  redirect_chain: "Chaîne de redirection",
  temporary_redirect_302: "Redirection 302 temporaire",
  duplicate_title: "Titre dupliqué (crawl)",
  duplicate_meta_description_crawl: "Description dupliquée (crawl)",
  missing_canonical: "Canonical manquant",
  non_self_canonical: "Canonical non-self",
};

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  product: "Produit",
  collection: "Collection",
  image: "Image",
  page: "Page",
  redirect: "Redirect",
};

function normalizeCrawlIssue(ci: CrawlIssue): Issue {
  return {
    resource_type: ci.issue_type.includes("redirect") ? "redirect" : "page",
    resource_id: ci.url,
    resource_title: ci.url,
    issue_type: ci.issue_type,
    severity: ci.severity,
    current_value: null,
    detail: ci.detail,
  };
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let issues: Issue[] = [];
  let score: SEOScore | null = null;
  let error: string | null = null;

  let ice: IceRow[] = [];

  try {
    const [issuesResp, scoreResp, crawlResp, iceResp] = await Promise.all([
      callBackendForShop(shop, `/api/shops/${shop}/audit/issues`, {
        accessToken: session.accessToken,
      }),
      callBackendForShop(shop, `/api/shops/${shop}/audit/score`, {
        accessToken: session.accessToken,
      }),
      callBackendForShop(shop, `/api/shops/${shop}/crawl/status`, {
        accessToken: session.accessToken,
      }),
      callBackendForShop(shop, `/api/shops/${shop}/audit/ice?top=10`, {
        accessToken: session.accessToken,
      }),
    ]);

    if (issuesResp.ok) {
      issues = (await issuesResp.json()) as Issue[];
    } else if (issuesResp.status === 404) {
      error = "Aucune donnée de crawl. Lancez un audit SEO depuis l'Onboarding.";
    }

    if (scoreResp.ok) score = (await scoreResp.json()) as SEOScore;

    if (crawlResp.ok) {
      const crawl = (await crawlResp.json()) as CrawlStatus;
      if (crawl.available) {
        const crawlIssues = crawl.issues.map(normalizeCrawlIssue);
        issues = [...issues, ...crawlIssues];
      }
    }

    if (iceResp.ok) ice = (await iceResp.json()) as IceRow[];
  } catch {
    error = t(locale, "backendOffline");
  }

  issues.sort(
    (a, b) =>
      (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9)
  );

  return json<LoaderData>({ locale, shop, issues, score, ice, error });
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;
const RESOURCE_TYPES = ["product", "collection", "image", "page", "redirect"] as const;

export default function Audit() {
  const { locale, issues, score, ice, error } = useLoaderData<typeof loader>();
  const [activeSeverity, setActiveSeverity] = useState<string | null>(null);
  const [activeResourceType, setActiveResourceType] = useState<string | null>(null);

  const filtered = issues.filter((i) => {
    if (activeSeverity && i.severity !== activeSeverity) return false;
    if (activeResourceType && i.resource_type !== activeResourceType) return false;
    return true;
  });

  const countBySeverity = issues.reduce<Record<string, number>>((acc, i) => {
    acc[i.severity] = (acc[i.severity] ?? 0) + 1;
    return acc;
  }, {});

  const countByResourceType = issues.reduce<Record<string, number>>((acc, i) => {
    acc[i.resource_type] = (acc[i.resource_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Page
      title={t(locale, "audit")}
      backAction={{
        content: t(locale, "backDashboard"),
        url: localizedPath("/app", locale),
      }}
    >
      <BlockStack gap="400">

        {/* Score summary */}
        {score && (
          <Card>
            <BlockStack gap="300">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">Score SEO global</Text>
                <Text as="span" variant="headingXl" fontWeight="bold">
                  {`${Math.round(score.total)}/100`}
                </Text>
              </InlineStack>
              <InlineGrid columns={["oneHalf", "oneHalf"]} gap="300">
                {Object.entries(score.components).map(([key, val]) => (
                  <InlineStack key={key} align="space-between">
                    <Text as="span" tone="subdued">{key}</Text>
                    <Text as="span" fontWeight="semibold">{`${Math.round(val)}/100`}</Text>
                  </InlineStack>
                ))}
              </InlineGrid>
              <InlineStack gap="200">
                {SEVERITIES.map((sev) =>
                  countBySeverity[sev] ? (
                    <Badge key={sev} tone={SEVERITY_TONE[sev]}>
                      {`${countBySeverity[sev]} ${sev}`}
                    </Badge>
                  ) : null
                )}
              </InlineStack>
            </BlockStack>
          </Card>
        )}

        {/* ICE priority matrix */}
        {ice.length > 0 && (
          <Card>
            <BlockStack gap="300">
              <InlineStack gap="200" blockAlign="center">
                <Text as="h2" variant="headingMd">Priorités ICE (top 10)</Text>
                <Tooltip
                  content={
                    locale === "fr"
                      ? "ICE = Impact × Confiance ÷ Effort. Plus le score est élevé, plus la correction est rentable. I, C, E sont notés de 1 à 10."
                      : "ICE = Impact × Confidence ÷ Effort. The higher the score, the more cost-effective the fix. I, C, E are scored 1–10."
                  }
                >
                  <Badge tone="info">?</Badge>
                </Tooltip>
              </InlineStack>
              <BlockStack gap="200">
                {ice.map((row, idx) => (
                  <BlockStack key={`ice-${idx}`} gap="100">
                    <InlineStack align="space-between" wrap>
                      <InlineStack gap="200" wrap>
                        <Badge tone={SEVERITY_TONE[row.severity] ?? "new"}>
                          {row.severity}
                        </Badge>
                        <Text as="span" fontWeight="semibold">
                          {ISSUE_TYPE_LABELS[row.issue_type] ?? row.issue_type}
                        </Text>
                        <Text as="span" tone="subdued">
                          {row.resource_title.length > 50
                            ? `${row.resource_title.slice(0, 50)}…`
                            : row.resource_title}
                        </Text>
                      </InlineStack>
                      <InlineStack gap="300">
                        <Text as="span" tone="subdued" variant="bodySm">
                          {`ICE ${Math.round(row.ice_score)}`}
                        </Text>
                        <Text as="span" tone="subdued" variant="bodySm">
                          {`I${row.impact} C${row.confidence} E${row.effort}`}
                        </Text>
                        {row.impressions > 0 && (
                          <Text as="span" tone="subdued" variant="bodySm">
                            {`${row.impressions} imp.`}
                          </Text>
                        )}
                      </InlineStack>
                    </InlineStack>
                    <Text as="p" tone="subdued" variant="bodySm">
                      {row.detail}
                    </Text>
                    {idx < ice.length - 1 && (
                      <div style={{ borderTop: "1px solid var(--p-color-border)", marginTop: 4 }} />
                    )}
                  </BlockStack>
                ))}
              </BlockStack>
            </BlockStack>
          </Card>
        )}

        {/* Error / empty state */}
        {error && (
          <Card>
            <Text as="p" tone="subdued">{error}</Text>
          </Card>
        )}

        {/* Issues list */}
        {!error && (
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">
                  {`Issues (${filtered.length}${filtered.length !== issues.length ? ` / ${issues.length}` : ""})`}
                </Text>
              </InlineStack>

              {/* Severity filters */}
              <BlockStack gap="200">
                <Text as="p" variant="bodySm" tone="subdued">Sévérité</Text>
                <InlineStack gap="200" wrap>
                  <Button
                    size="slim"
                    pressed={activeSeverity === null}
                    onClick={() => setActiveSeverity(null)}
                  >
                    {`Toutes (${issues.length})`}
                  </Button>
                  {SEVERITIES.map((sev) =>
                    countBySeverity[sev] ? (
                      <Button
                        key={sev}
                        size="slim"
                        pressed={activeSeverity === sev}
                        onClick={() =>
                          setActiveSeverity(activeSeverity === sev ? null : sev)
                        }
                        tone={sev === "critical" ? "critical" : undefined}
                      >
                        {`${sev} (${countBySeverity[sev]})`}
                      </Button>
                    ) : null
                  )}
                </InlineStack>
              </BlockStack>

              {/* Resource type filters */}
              <BlockStack gap="200">
                <Text as="p" variant="bodySm" tone="subdued">Type de ressource</Text>
                <InlineStack gap="200" wrap>
                  <Button
                    size="slim"
                    pressed={activeResourceType === null}
                    onClick={() => setActiveResourceType(null)}
                  >
                    Tous
                  </Button>
                  {RESOURCE_TYPES.map((rt) =>
                    countByResourceType[rt] ? (
                      <Button
                        key={rt}
                        size="slim"
                        pressed={activeResourceType === rt}
                        onClick={() =>
                          setActiveResourceType(
                            activeResourceType === rt ? null : rt
                          )
                        }
                      >
                        {`${RESOURCE_TYPE_LABELS[rt] ?? rt} (${countByResourceType[rt]})`}
                      </Button>
                    ) : null
                  )}
                </InlineStack>
              </BlockStack>

              {/* Issues */}
              {filtered.length === 0 ? (
                <Text as="p" tone="subdued">
                  {issues.length === 0
                    ? "Aucune issue détectée. Lancez un audit SEO depuis l'Onboarding."
                    : "Aucune issue correspondant aux filtres actifs."}
                </Text>
              ) : (
                <BlockStack gap="300">
                  {filtered.slice(0, 200).map((issue, idx) => (
                    <BlockStack
                      key={`${issue.resource_id}-${issue.issue_type}-${idx}`}
                      gap="100"
                    >
                      <InlineStack gap="200" align="start" wrap>
                        <Badge tone={SEVERITY_TONE[issue.severity] ?? "new"}>
                          {issue.severity}
                        </Badge>
                        <Badge>
                          {RESOURCE_TYPE_LABELS[issue.resource_type] ?? issue.resource_type}
                        </Badge>
                        <Text as="span" fontWeight="semibold">
                          {ISSUE_TYPE_LABELS[issue.issue_type] ?? issue.issue_type}
                        </Text>
                        <Text as="span" tone="subdued">
                          {issue.resource_title.length > 60
                            ? `${issue.resource_title.slice(0, 60)}…`
                            : issue.resource_title}
                        </Text>
                      </InlineStack>
                      <Text as="p" tone="subdued" variant="bodySm">
                        {issue.detail}
                      </Text>
                      {filtered.length > 1 && idx < filtered.slice(0, 200).length - 1 && (
                        <div style={{ borderTop: "1px solid var(--p-color-border)", marginTop: 4 }} />
                      )}
                    </BlockStack>
                  ))}
                  {filtered.length > 200 && (
                    <Text as="p" tone="subdued">
                      {filtered.length - 200} issues supplémentaires — affinez les filtres pour les voir.
                    </Text>
                  )}
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
