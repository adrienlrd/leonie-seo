import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useFetcher } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  Collapsible,
  DataTable,
  InlineStack,
  Page,
  ProgressBar,
  Spinner,
  Text,
} from "@shopify/polaris";
import { useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SeoKeyword {
  query: string;
  intent_type: string;
  demand_score: number;
  competition_score: number;
  product_fit_score: number;
  reason: string;
}

interface GeoQuestion {
  question: string;
  answer_angle: string;
  content_block_type: string;
  confidence: string;
}

interface ContentTestPack {
  current_meta_title: string;
  proposed_meta_title: string;
  current_meta_description: string;
  proposed_meta_description: string;
  current_product_title: string;
  proposed_product_title: string;
  current_product_description_summary: string;
  proposed_product_description: string;
  proposed_faq: { q: string; a: string }[];
  proposed_geo_answer_block: string;
  proposed_blog_title: string;
  proposed_blog_outline: string[];
  proposed_blog_intro: string;
  facts_used: string[];
  facts_missing: string[];
  confidence: string;
}

interface ProductResult {
  product_id: string;
  product_title: string;
  product_handle: string;
  product_url: string;
  product_summary: string;
  target_customer: string;
  buying_intents: string[];
  seo_keywords: SeoKeyword[];
  geo_questions: GeoQuestion[];
  content_test_pack: ContentTestPack;
  recommended_content_actions: string[];
  confidence: string;
  opportunity_score: number;
  sources_used: string[];
}

interface AnalysisResults {
  shop: string;
  analyzed_at: string;
  active_product_count: number;
  analyzed_product_count: number;
  total_opportunity_count: number;
  sources_used: string[];
  products: ProductResult[];
}

interface LoaderData {
  locale: Locale;
  shop: string;
}

// ── Remix loader / action ─────────────────────────────────────────────────────

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  return json({ locale: getLocale(request), shop: session.shop });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const formData = await request.formData();
  const intent = formData.get("intent") as string;

  if (intent !== "run") {
    return json({ results: null, error: "Unknown intent" });
  }

  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/run?max_products=3`,
      {
        accessToken: session.accessToken,
        method: "POST",
        signal: AbortSignal.timeout(180_000),
      },
    );
    if (!resp.ok) {
      const err = await resp.text();
      return json({ results: null, error: `Erreur backend ${resp.status}: ${err}` });
    }
    const results: AnalysisResults = await resp.json();
    return json({ results, error: null });
  } catch (err) {
    return json({ results: null, error: String(err) });
  }
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreTone(score: number): "success" | "warning" | "critical" {
  if (score >= 65) return "success";
  if (score >= 35) return "warning";
  return "critical";
}

function confidenceTone(c: string): "success" | "warning" | "critical" | "info" {
  if (c === "high") return "success";
  if (c === "medium") return "warning";
  if (c === "low") return "critical";
  return "info";
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SummaryCard({
  results,
  locale,
}: {
  results: AnalysisResults;
  locale: Locale;
}) {
  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack gap="400" wrap>
          <Text as="p" variant="bodySm" tone="subdued">
            {t(locale, "marketAnalysisLastRun")} : {formatDate(results.analyzed_at)}
          </Text>
          <Text as="p" variant="bodySm">
            <strong>{results.analyzed_product_count}</strong>{" "}
            {t(locale, "marketAnalysisProductCount")}
          </Text>
          <Text as="p" variant="bodySm">
            <strong>{results.total_opportunity_count}</strong>{" "}
            {t(locale, "marketAnalysisOpportunityCount")}
          </Text>
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

function ProductCard({
  product,
  locale,
}: {
  product: ProductResult;
  locale: Locale;
}) {
  const [openSection, setOpenSection] = useState<string | null>(null);

  const toggle = (section: string) =>
    setOpenSection((prev) => (prev === section ? null : section));

  const pack = product.content_test_pack;

  return (
    <Card>
      <BlockStack gap="300">
        {/* Header */}
        <InlineStack gap="200" align="space-between" wrap>
          <BlockStack gap="100">
            <Text as="h3" variant="headingSm">
              {product.product_title}
            </Text>
            <Text as="p" variant="bodySm" tone="subdued">
              /{product.product_handle}
            </Text>
          </BlockStack>
          <InlineStack gap="200">
            <Badge tone={scoreTone(product.opportunity_score)}>
              Score {product.opportunity_score}/100
            </Badge>
            <Badge tone={confidenceTone(product.confidence)}>
              {product.confidence}
            </Badge>
          </InlineStack>
        </InlineStack>

        {/* Summary */}
        {product.product_summary && (
          <Text as="p" variant="bodySm">
            {product.product_summary}
          </Text>
        )}

        {product.target_customer && (
          <Text as="p" variant="bodySm" tone="subdued">
            {locale === "fr" ? "Client cible" : "Target customer"} :{" "}
            {product.target_customer}
          </Text>
        )}

        {/* SEO Keywords */}
        {product.seo_keywords.length > 0 && (
          <Box>
            <Button
              variant="plain"
              onClick={() => toggle("keywords")}
            >
              {t(locale, "marketAnalysisSeoKeywords")} ({product.seo_keywords.length})
            </Button>
            <Collapsible id={`kw-${product.product_id}`} open={openSection === "keywords"}>
              <Box paddingBlockStart="200">
                <DataTable
                  columnContentTypes={["text", "text", "numeric", "numeric", "numeric"]}
                  headings={[
                    t(locale, "query"),
                    "Intent",
                    locale === "fr" ? "Demande" : "Demand",
                    locale === "fr" ? "Concurrence" : "Competition",
                    locale === "fr" ? "Fit" : "Fit",
                  ]}
                  rows={product.seo_keywords.map((k) => [
                    k.query,
                    k.intent_type,
                    k.demand_score,
                    k.competition_score,
                    k.product_fit_score,
                  ])}
                />
              </Box>
            </Collapsible>
          </Box>
        )}

        {/* GEO Questions */}
        {product.geo_questions.length > 0 && (
          <Box>
            <Button
              variant="plain"
              onClick={() => toggle("geo")}
            >
              {t(locale, "marketAnalysisGeoQuestions")} ({product.geo_questions.length})
            </Button>
            <Collapsible id={`geo-${product.product_id}`} open={openSection === "geo"}>
              <Box paddingBlockStart="200">
                <DataTable
                  columnContentTypes={["text", "text", "text"]}
                  headings={[
                    locale === "fr" ? "Question" : "Question",
                    locale === "fr" ? "Angle de réponse" : "Answer angle",
                    locale === "fr" ? "Type de bloc" : "Block type",
                  ]}
                  rows={product.geo_questions.map((q) => [
                    q.question,
                    q.answer_angle,
                    q.content_block_type,
                  ])}
                />
              </Box>
            </Collapsible>
          </Box>
        )}

        {/* Content proposals */}
        {(pack.proposed_meta_title ||
          pack.proposed_meta_description ||
          pack.proposed_product_description ||
          pack.proposed_faq.length > 0 ||
          pack.proposed_blog_title) && (
          <Box>
            <Button
              variant="plain"
              onClick={() => toggle("proposals")}
            >
              {t(locale, "marketAnalysisProposals")}
            </Button>
            <Collapsible id={`prop-${product.product_id}`} open={openSection === "proposals"}>
              <Box paddingBlockStart="200">
                <BlockStack gap="300">
                  {pack.proposed_meta_title && (
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySmBold">
                        Meta title
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {locale === "fr" ? "Actuel" : "Current"} : {pack.current_meta_title}
                      </Text>
                      <Box
                        padding="200"
                        borderWidth="025"
                        borderRadius="200"
                        borderColor="border"
                        background="bg-surface-secondary"
                      >
                        <Text as="p" variant="bodySm">{pack.proposed_meta_title}</Text>
                      </Box>
                    </BlockStack>
                  )}

                  {pack.proposed_meta_description && (
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySmBold">
                        Meta description
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {locale === "fr" ? "Actuelle" : "Current"} :{" "}
                        {pack.current_meta_description || (locale === "fr" ? "absente" : "missing")}
                      </Text>
                      <Box
                        padding="200"
                        borderWidth="025"
                        borderRadius="200"
                        borderColor="border"
                        background="bg-surface-secondary"
                      >
                        <Text as="p" variant="bodySm">{pack.proposed_meta_description}</Text>
                      </Box>
                    </BlockStack>
                  )}

                  {pack.proposed_product_description && (
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySmBold">
                        {t(locale, "contentTypeProductDescription")}
                      </Text>
                      <Box
                        padding="200"
                        borderWidth="025"
                        borderRadius="200"
                        borderColor="border"
                        background="bg-surface-secondary"
                      >
                        <Text as="p" variant="bodySm">{pack.proposed_product_description}</Text>
                      </Box>
                    </BlockStack>
                  )}

                  {pack.proposed_faq.length > 0 && (
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySmBold">FAQ</Text>
                      {pack.proposed_faq.map((item, i) => (
                        <Box key={i} padding="200" borderWidth="025" borderRadius="200" borderColor="border">
                          <BlockStack gap="100">
                            <Text as="p" variant="bodySmBold">{item.q}</Text>
                            <Text as="p" variant="bodySm">{item.a}</Text>
                          </BlockStack>
                        </Box>
                      ))}
                    </BlockStack>
                  )}

                  {pack.proposed_geo_answer_block && (
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySmBold">
                        {locale === "fr" ? "Bloc réponse GEO" : "GEO answer block"}
                      </Text>
                      <Box
                        padding="200"
                        borderWidth="025"
                        borderRadius="200"
                        borderColor="border"
                        background="bg-surface-secondary"
                      >
                        <Text as="p" variant="bodySm">{pack.proposed_geo_answer_block}</Text>
                      </Box>
                    </BlockStack>
                  )}

                  {pack.proposed_blog_title && (
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySmBold">
                        {locale === "fr" ? "Idée d'article de blog" : "Blog article idea"}
                      </Text>
                      <Text as="p" variant="bodySm">
                        <strong>{pack.proposed_blog_title}</strong>
                      </Text>
                      {pack.proposed_blog_intro && (
                        <Text as="p" variant="bodySm" tone="subdued">
                          {pack.proposed_blog_intro}
                        </Text>
                      )}
                      {pack.proposed_blog_outline.length > 0 && (
                        <BlockStack gap="050">
                          {pack.proposed_blog_outline.map((line, i) => (
                            <Text key={i} as="p" variant="bodySm" tone="subdued">
                              • {line}
                            </Text>
                          ))}
                        </BlockStack>
                      )}
                    </BlockStack>
                  )}
                </BlockStack>
              </Box>
            </Collapsible>
          </Box>
        )}

        {/* Facts missing */}
        {pack.facts_missing.length > 0 && (
          <Box>
            <Button variant="plain" onClick={() => toggle("facts")}>
              {t(locale, "marketAnalysisFactsMissing")} ({pack.facts_missing.length})
            </Button>
            <Collapsible id={`facts-${product.product_id}`} open={openSection === "facts"}>
              <Box paddingBlockStart="100">
                <BlockStack gap="050">
                  {pack.facts_missing.map((f, i) => (
                    <Text key={i} as="p" variant="bodySm" tone="subdued">
                      • {f}
                    </Text>
                  ))}
                </BlockStack>
              </Box>
            </Collapsible>
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}

// ── Page component ────────────────────────────────────────────────────────────

export default function MarketAnalysisPage() {
  const { locale } = useLoaderData<LoaderData>();
  const fetcher = useFetcher<{ results: AnalysisResults | null; error: string | null }>();

  const isLoading = fetcher.state !== "idle";
  const results = fetcher.data?.results ?? null;
  const error = fetcher.data?.error ?? null;

  const handleAnalyse = () => {
    const fd = new FormData();
    fd.set("intent", "run");
    fetcher.submit(fd, { method: "post", replace: true });
  };

  return (
    <Page
      title={t(locale, "marketAnalysis")}
      subtitle={t(locale, "marketAnalysisSubtitle")}
      backAction={{
        content: t(locale, "hubInsights"),
        url: localizedPath("/app/insights", locale),
      }}
    >
      <BlockStack gap="400">
        {/* Read-only banner */}
        <Banner tone="info">
          <Text as="p">{t(locale, "marketAnalysisReadOnly")}</Text>
        </Banner>

        {/* Launch card */}
        <Card>
          <BlockStack gap="300">
            <Text as="p">
              {t(locale, "marketAnalysisEmpty")}
            </Text>
            {isLoading ? (
              <InlineStack gap="200" align="start">
                <Spinner size="small" />
                <Text as="p" tone="subdued">
                  {t(locale, "marketAnalysisRunning")}
                </Text>
              </InlineStack>
            ) : (
              <Button
                variant="primary"
                onClick={handleAnalyse}
                disabled={isLoading}
              >
                {t(locale, "marketAnalysisRun")}
              </Button>
            )}
          </BlockStack>
        </Card>

        {/* Error */}
        {error && (
          <Banner tone="critical">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {/* Summary */}
        {results && <SummaryCard results={results} locale={locale} />}

        {/* Product results */}
        {results?.products?.map((product) => (
          <ProductCard key={product.product_id} product={product} locale={locale} />
        ))}
      </BlockStack>
    </Page>
  );
}
