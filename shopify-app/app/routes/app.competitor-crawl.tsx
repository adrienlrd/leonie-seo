import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  Divider,
  EmptyState,
  InlineGrid,
  InlineStack,
  Page,
  Select,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, type Locale } from "../lib/i18n";
import type {
  CompetitorCrawlGap,
  CompetitorCrawlInsights,
  CompetitorCrawlTopUrl,
  ProductResult,
} from "../lib/marketAnalysisShared";
import React, { useMemo, useState } from "react";

interface MarketAnalysisLatest {
  status?: string;
  analyzed_product_count?: number;
  sources_used?: string[];
  products?: ProductResult[];
}

interface LoaderData {
  shop: string;
  locale: Locale;
  job: MarketAnalysisLatest | null;
  error: string | null;
}

interface CompetitorPageRow {
  product: ProductResult;
  insights: CompetitorCrawlInsights;
  page: CompetitorCrawlTopUrl;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/latest`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({
        shop: session.shop,
        locale,
        job: null,
        error: `HTTP ${resp.status}`,
      });
    }
    return json<LoaderData>({
      shop: session.shop,
      locale,
      job: (await resp.json()) as MarketAnalysisLatest,
      error: null,
    });
  } catch (err) {
    return json<LoaderData>({
      shop: session.shop,
      locale,
      job: null,
      error: err instanceof Error ? err.message : "Network error",
    });
  }
};

function asNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function asList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

function yesNo(value: unknown, locale: Locale): string {
  return value ? (locale === "fr" ? "Oui" : "Yes") : (locale === "fr" ? "Non" : "No");
}

function yesNoBadge(value: unknown, locale: Locale) {
  return <Badge tone={value ? "success" : "critical"}>{yesNo(value, locale)}</Badge>;
}

function pageTypeLabel(type: string | undefined, locale: Locale): string {
  const labels: Record<string, [string, string]> = {
    product: ["Produit", "Product"],
    collection: ["Collection", "Collection"],
    blog: ["Blog", "Blog"],
    faq: ["FAQ", "FAQ"],
    guide: ["Guide", "Guide"],
    unknown: ["Non classée", "Unclassified"],
  };
  const label = labels[type || "unknown"] ?? labels.unknown;
  return label[locale === "fr" ? 0 : 1];
}

function intentLabel(intent: string | undefined, locale: Locale): string {
  const labels: Record<string, [string, string]> = {
    informational: ["Informationnelle", "Informational"],
    commercial: ["Commerciale", "Commercial"],
    transactional: ["Transactionnelle", "Transactional"],
    navigational: ["Navigationnelle", "Navigational"],
    unknown: ["Non classée", "Unclassified"],
  };
  const key = intent || "unknown";
  return (labels[key] ?? labels.unknown)[locale === "fr" ? 0 : 1];
}

function metricLabel(label: string, value: string | number | React.ReactNode) {
  return (
    <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border">
      <BlockStack gap="050">
        <Text as="p" variant="bodySm" tone="subdued">
          {label}
        </Text>
        {typeof value === "string" || typeof value === "number" ? (
          <Text as="p" fontWeight="semibold">
            {value}
          </Text>
        ) : (
          value
        )}
      </BlockStack>
    </Box>
  );
}

function textOrDash(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

function collectRows(products: ProductResult[]): CompetitorPageRow[] {
  const rows: CompetitorPageRow[] = [];
  for (const product of products) {
    const insights = product.competitor_crawl_insights;
    if (!insights?.enabled || !Array.isArray(insights.top_urls)) continue;
    for (const page of insights.top_urls) {
      rows.push({ product, insights, page });
    }
  }
  return rows.sort((a, b) => asNumber(a.page.rank) - asNumber(b.page.rank));
}

function pageCounts(rows: CompetitorPageRow[]): Record<string, number> {
  return rows.reduce<Record<string, number>>((acc, row) => {
    const type = row.page.page_type || "unknown";
    acc[type] = (acc[type] ?? 0) + 1;
    return acc;
  }, {});
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <Text as="h2" variant="headingSm">
      {children}
    </Text>
  );
}

function RateText({ value }: { value: unknown }) {
  const num = asNumber(value);
  return <Text as="p" fontWeight="semibold">{Math.round(num * 100)}%</Text>;
}

function DominantPatterns({
  rows,
  locale,
}: {
  rows: CompetitorPageRow[];
  locale: Locale;
}) {
  const productInsights = new Map<string, CompetitorCrawlInsights>();
  for (const row of rows) {
    productInsights.set(row.product.product_id, row.insights);
  }
  const insights = [...productInsights.values()];
  const avg = (key: string) => {
    if (!insights.length) return 0;
    return insights.reduce((sum, item) => sum + asNumber(item.dominant_patterns?.[key]), 0) / insights.length;
  };
  const medianWords = insights.length
    ? Math.round(
        insights.reduce((sum, item) => sum + asNumber(item.dominant_patterns?.median_word_count), 0) /
          insights.length,
      )
    : 0;

  return (
    <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
      {metricLabel("FAQ visible", <RateText value={avg("has_faq_block_rate")} />)}
      {metricLabel("Product schema", <RateText value={avg("has_product_schema_rate")} />)}
      {metricLabel("Breadcrumb schema", <RateText value={avg("has_breadcrumb_schema_rate")} />)}
      {metricLabel(locale === "fr" ? "Contenu médian" : "Median content", `${medianWords} mots`)}
    </InlineGrid>
  );
}

function GapBadges({ gaps }: { gaps: CompetitorCrawlGap[] }) {
  if (!gaps.length) return <Text as="p" tone="subdued">—</Text>;
  return (
    <InlineStack gap="100" wrap>
      {gaps.map((gap) => (
        <Badge key={`${gap.gap}-${gap.action_type}`} tone="attention">
          {`${gap.gap} +${gap.priority_boost}`}
        </Badge>
      ))}
    </InlineStack>
  );
}

function ListBlock({ items, empty = "—" }: { items: string[]; empty?: string }) {
  if (!items.length) return <Text as="p" tone="subdued">{empty}</Text>;
  return (
    <BlockStack gap="050">
      {items.map((item, index) => (
        <Text as="p" variant="bodySm" key={`${item}-${index}`}>
          {item}
        </Text>
      ))}
    </BlockStack>
  );
}

function CompetitorPageCard({
  row,
  locale,
}: {
  row: CompetitorPageRow;
  locale: Locale;
}) {
  const { product, insights, page } = row;
  const seo = page.seo ?? {};
  const structure = page.structure ?? {};
  const geo = page.geo_aeo ?? {};
  const schema = page.schema ?? {};
  const links = page.links ?? {};
  const images = page.images ?? {};
  const trust = page.trust ?? {};
  const depth = page.product_depth ?? {};
  const serp = page.serp ?? {};
  const fallback = page.feature_summary ?? {};
  const h2 = asList(structure.h2_texts);
  const h3 = asList(structure.h3_texts);
  const paa = asList(serp.paa_questions);
  const schemaTypes = asList(schema.schema_types);
  const linkExamples = links.internal_link_examples ?? [];
  const altExamples = asList(images.image_alt_examples);

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="start" gap="300" wrap>
          <BlockStack gap="150">
            <InlineStack gap="150" wrap>
              <Badge tone="success">{`Rank ${page.rank}`}</Badge>
              <Badge tone="info">{pageTypeLabel(page.page_type, locale)}</Badge>
              <Badge>{intentLabel(page.keyword_intent_type, locale)}</Badge>
              <Badge tone="attention">{`+${insights.priority_boost_total}`}</Badge>
            </InlineStack>
            <Text as="h2" variant="headingMd">
              {product.product_title}
            </Text>
            <Text as="p" tone="subdued">
              {page.keyword} · {page.domain}
            </Text>
          </BlockStack>
          <Button url={page.final_url || page.url} target="_blank" variant="secondary" size="slim">
            {locale === "fr" ? "Ouvrir l'URL" : "Open URL"}
          </Button>
        </InlineStack>

        <Text as="p" variant="bodySm" tone="subdued">
          {page.final_url || page.url}
        </Text>

        <Divider />

        <BlockStack gap="300">
          <SectionHeading>SERP</SectionHeading>
          <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
            {metricLabel("Mot-clé associé", page.keyword)}
            {metricLabel("Position SERP", `#${page.rank}`)}
            {metricLabel("Type d'intention", intentLabel(page.keyword_intent_type, locale))}
            {metricLabel("Featured snippet", yesNoBadge(serp.featured_snippet_present, locale))}
          </InlineGrid>
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="150">
              <Text as="p" variant="bodySm" tone="subdued">PAA / questions SERP</Text>
              <ListBlock items={paa} />
            </BlockStack>
          </Box>
        </BlockStack>

        <BlockStack gap="300">
          <SectionHeading>SEO</SectionHeading>
          <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">Title SEO</Text>
                <Text as="p">{textOrDash(seo.title || page.title)}</Text>
                <InlineStack gap="100" wrap>
                  <Badge>{`${asNumber(seo.title_length)} caractères`}</Badge>
                  <Badge tone={seo.title_keyword_present ? "success" : "attention"}>
                    {`Mot-clé ${yesNo(seo.title_keyword_present, locale)}`}
                  </Badge>
                  <Badge tone={seo.title_promise_detected ? "success" : "info"}>
                    {`Promesse ${yesNo(seo.title_promise_detected, locale)}`}
                  </Badge>
                </InlineStack>
              </BlockStack>
            </Box>
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">Meta description</Text>
                <Text as="p">{textOrDash(seo.meta_description)}</Text>
                <InlineStack gap="100" wrap>
                  <Badge>{`${asNumber(seo.meta_description_length)} caractères`}</Badge>
                  <Badge tone={seo.meta_has_commercial_angle ? "success" : "info"}>
                    {`Angle commercial ${yesNo(seo.meta_has_commercial_angle, locale)}`}
                  </Badge>
                  <Badge tone={seo.meta_has_cta ? "success" : "info"}>
                    {`CTA ${yesNo(seo.meta_has_cta, locale)}`}
                  </Badge>
                </InlineStack>
              </BlockStack>
            </Box>
          </InlineGrid>
        </BlockStack>

        <BlockStack gap="300">
          <SectionHeading>Structure Hn et contenu</SectionHeading>
          <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
            {metricLabel("H1", `${asNumber(structure.h1_count)} · ${textOrDash(structure.h1_text)}`)}
            {metricLabel("H2", asNumber(structure.h2_count))}
            {metricLabel("H3", asNumber(structure.h3_count))}
            {metricLabel("Longueur du contenu", `${asNumber(structure.word_count || fallback.word_count)} mots`)}
            {metricLabel("Paragraphes", asNumber(structure.paragraph_count))}
            {metricLabel("Listes à puces", yesNoBadge(structure.has_bullet_lists, locale))}
            {metricLabel("Tableau comparatif", yesNoBadge(structure.has_comparison_table, locale))}
            {metricLabel("Specs produit", yesNoBadge(structure.has_product_specs_table, locale))}
          </InlineGrid>
          <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">H2 utilisés</Text>
                <ListBlock items={h2} />
              </BlockStack>
            </Box>
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">H3 utilisés</Text>
                <ListBlock items={h3} />
              </BlockStack>
            </Box>
          </InlineGrid>
        </BlockStack>

        <BlockStack gap="300">
          <SectionHeading>GEO / AEO / Schema</SectionHeading>
          <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
            {metricLabel("FAQ visible", `${yesNo(geo.has_faq_block, locale)} · ${asNumber(geo.faq_question_count)} questions`)}
            {metricLabel("Blocs réponse courte", `${yesNo(geo.has_short_answer_block, locale)} · ${asNumber(geo.short_answer_block_count)}`)}
            {metricLabel("Answerability", `${asNumber(geo.answerability_score)}/100`)}
            {metricLabel("AI readability", `${asNumber(geo.ai_readability_score)}/100`)}
            {metricLabel("JSON-LD", `${asNumber(schema.jsonld_count)} blocs`)}
            {metricLabel("Product / Offer", `${yesNo(schema.has_product_schema, locale)} / ${yesNo(schema.has_offer_schema, locale)}`)}
            {metricLabel("Breadcrumb / FAQPage", `${yesNo(schema.has_breadcrumb_schema, locale)} / ${yesNo(schema.has_faq_schema, locale)}`)}
            {metricLabel("Article / Organization", `${yesNo(schema.has_article_schema, locale)} / ${yesNo(schema.has_organization_schema, locale)}`)}
          </InlineGrid>
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="150">
              <Text as="p" variant="bodySm" tone="subdued">Types Schema détectés</Text>
              <InlineStack gap="100" wrap>
                {schemaTypes.length ? schemaTypes.map((item) => <Badge key={item}>{item}</Badge>) : <Text as="p" tone="subdued">—</Text>}
              </InlineStack>
            </BlockStack>
          </Box>
        </BlockStack>

        <BlockStack gap="300">
          <SectionHeading>Maillage, images et confiance</SectionHeading>
          <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
            {metricLabel("Liens internes", asNumber(links.internal_link_count || fallback.internal_link_count))}
            {metricLabel("Liens externes", asNumber(links.external_link_count))}
            {metricLabel("Images", asNumber(images.image_count))}
            {metricLabel("Alt text descriptifs", `${asNumber(images.descriptive_image_alt_count)}/${asNumber(images.image_alt_count)}`)}
            {metricLabel("Alt text manquants", asNumber(images.images_missing_alt_count))}
            {metricLabel("Breadcrumb", yesNoBadge(structure.has_breadcrumb_block || schema.has_breadcrumb_schema, locale))}
            {metricLabel("Preuves de confiance", yesNoBadge(trust.has_trust_proof || trust.has_reviews_or_social_proof, locale))}
            {metricLabel("Avantages / inconvénients", yesNoBadge(structure.has_pros_cons, locale))}
          </InlineGrid>
          <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">Ancres internes</Text>
                {linkExamples.length ? (
                  <BlockStack gap="100">
                    {linkExamples.map((link, index) => (
                      <InlineStack key={`${link.href}-${index}`} gap="100" wrap>
                        <Badge>{link.target_type}</Badge>
                        <Text as="p" variant="bodySm">{textOrDash(link.anchor)}</Text>
                      </InlineStack>
                    ))}
                  </BlockStack>
                ) : (
                  <Text as="p" tone="subdued">—</Text>
                )}
              </BlockStack>
            </Box>
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">Alt text exemples</Text>
                <ListBlock items={altExamples} />
              </BlockStack>
            </Box>
          </InlineGrid>
        </BlockStack>

        <BlockStack gap="300">
          <SectionHeading>Profondeur produit et gaps marchand</SectionHeading>
          <InlineStack gap="100" wrap>
            <Badge tone={depth.materials ? "success" : "info"}>{`Matériaux ${yesNo(depth.materials, locale)}`}</Badge>
            <Badge tone={depth.dimensions ? "success" : "info"}>{`Dimensions ${yesNo(depth.dimensions, locale)}`}</Badge>
            <Badge tone={depth.usage ? "success" : "info"}>{`Usage ${yesNo(depth.usage, locale)}`}</Badge>
            <Badge tone={depth.compatibility ? "success" : "info"}>{`Compatibilité ${yesNo(depth.compatibility, locale)}`}</Badge>
            <Badge tone={depth.care ? "success" : "info"}>{`Entretien ${yesNo(depth.care, locale)}`}</Badge>
          </InlineStack>
          <GapBadges gaps={insights.merchant_gaps ?? []} />
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

export default function CompetitorCrawlPage() {
  const { locale, job, error } = useLoaderData<typeof loader>() as LoaderData;
  const [productId, setProductId] = useState("all");
  const [pageType, setPageType] = useState("all");

  const allRows = useMemo(() => collectRows(job?.products ?? []), [job?.products]);
  const counts = pageCounts(allRows);
  const productOptions = [
    { label: locale === "fr" ? "Tous les produits" : "All products", value: "all" },
    ...Array.from(new Map(allRows.map((row) => [row.product.product_id, row.product.product_title])).entries())
      .map(([value, label]) => ({ label, value })),
  ];
  const typeOptions = [
    { label: locale === "fr" ? "Tous les types de pages" : "All page types", value: "all" },
    ...["product", "collection", "blog", "faq", "guide", "unknown"]
      .filter((type) => counts[type])
      .map((type) => ({ label: pageTypeLabel(type, locale), value: type })),
  ];
  const rows = allRows.filter((row) => {
    if (productId !== "all" && row.product.product_id !== productId) return false;
    if (pageType !== "all" && (row.page.page_type || "unknown") !== pageType) return false;
    return true;
  });
  const uniqueProducts = new Set(allRows.map((row) => row.product.product_id)).size;
  const avgBoost = uniqueProducts
    ? Math.round(
        Array.from(new Map(allRows.map((row) => [row.product.product_id, row.insights.priority_boost_total])).values())
          .reduce((sum, value) => sum + asNumber(value), 0) / uniqueProducts,
      )
    : 0;

  return (
    <Page
      title={locale === "fr" ? "Analyse concurrentielle SERP" : "SERP competitor analysis"}
      subtitle={
        locale === "fr"
          ? "URLs qui rankent, structures crawlées, patterns SEO/GEO et gaps face à la boutique."
          : "Ranking URLs, crawled structures, SEO/GEO patterns and merchant gaps."
      }
      backAction={{ content: locale === "fr" ? "Accueil" : "Dashboard", url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        {error && (
          <Banner tone="critical">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {!error && allRows.length === 0 && (
          <EmptyState
            heading={locale === "fr" ? "Aucun crawl concurrentiel exploitable" : "No competitor crawl data yet"}
            action={{
              content: locale === "fr" ? "Lancer une analyse marché" : "Run market analysis",
              url: localizedPath("/app/market-analysis", locale),
            }}
            image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
          >
            <Text as="p">
              {locale === "fr"
                ? "Activez COMPETITOR_CRAWL_ENABLED sur l'API, relancez une analyse marché, puis revenez ici."
                : "Enable COMPETITOR_CRAWL_ENABLED on the API, rerun market analysis, then come back here."}
            </Text>
          </EmptyState>
        )}

        {allRows.length > 0 && (
          <>
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between" blockAlign="center" wrap>
                  <BlockStack gap="100">
                    <Text as="h2" variant="headingMd">
                      {locale === "fr" ? "Vue concurrentielle crawlée" : "Crawled competitor view"}
                    </Text>
                    <Text as="p" tone="subdued">
                      {job?.sources_used?.includes("competitor_crawl")
                        ? "competitor_crawl actif dans la dernière analyse"
                        : "Données issues des insights présents dans la dernière analyse"}
                    </Text>
                  </BlockStack>
                  <Button url={localizedPath("/app/market-analysis", locale)} variant="secondary">
                    {locale === "fr" ? "Voir l'analyse marché" : "Open market analysis"}
                  </Button>
                </InlineStack>
                <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
                  {metricLabel("URLs rankantes", allRows.length)}
                  {metricLabel("Produits couverts", uniqueProducts)}
                  {metricLabel("Boost moyen", `+${avgBoost}`)}
                  {metricLabel("Pages produit / collection / blog / FAQ", `${counts.product ?? 0} / ${counts.collection ?? 0} / ${counts.blog ?? 0} / ${counts.faq ?? 0}`)}
                </InlineGrid>
                <DominantPatterns rows={allRows} locale={locale} />
                <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
                  <Select label="Produit" options={productOptions} value={productId} onChange={setProductId} />
                  <Select label="Type de page" options={typeOptions} value={pageType} onChange={setPageType} />
                </InlineGrid>
              </BlockStack>
            </Card>

            {rows.length === 0 ? (
              <Banner tone="info">
                <Text as="p">
                  {locale === "fr" ? "Aucune URL ne correspond aux filtres." : "No URL matches the filters."}
                </Text>
              </Banner>
            ) : (
              <BlockStack gap="400">
                {rows.map((row) => (
                  <CompetitorPageCard
                    key={`${row.product.product_id}-${row.page.url}-${row.page.keyword}`}
                    row={row}
                    locale={locale}
                  />
                ))}
              </BlockStack>
            )}
          </>
        )}
      </BlockStack>
    </Page>
  );
}
