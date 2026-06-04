import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  Collapsible,
  Divider,
  EmptyState,
  InlineGrid,
  InlineStack,
  Page,
  ProgressBar,
  Select,
  Spinner,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, type Locale } from "../lib/i18n";
import type {
  CompetitorCrawlGap,
  CompetitorSerpDomain,
  CompetitorSerpResult,
  CompetitorSerpUrl,
} from "../lib/marketAnalysisShared";
import React, { useEffect, useRef, useState } from "react";

interface LoaderData {
  shop: string;
  locale: Locale;
  result: CompetitorSerpResult | null;
  error: string | null;
}

type ActionResult =
  | { job_id: string; status: string }
  | { status: string; completed_at?: string; total_urls_crawled?: number; keywords_used?: number; competitor_count?: number; error?: string }
  | { result: CompetitorSerpResult };

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/competitor-serp/latest`,
      { accessToken: session.accessToken },
    );
    if (resp.status === 404) {
      return json<LoaderData>({ shop: session.shop, locale, result: null, error: null });
    }
    if (!resp.ok) {
      return json<LoaderData>({ shop: session.shop, locale, result: null, error: `HTTP ${resp.status}` });
    }
    return json<LoaderData>({ shop: session.shop, locale, result: await resp.json(), error: null });
  } catch (err) {
    return json<LoaderData>({ shop: session.shop, locale, result: null, error: err instanceof Error ? err.message : "Network error" });
  }
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const formData = await request.formData();
  const intent = formData.get("intent");

  if (intent === "start_job") {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/competitor-serp/jobs`,
      { method: "POST", accessToken: session.accessToken },
    );
    return json(await resp.json());
  }

  if (intent === "poll") {
    const jobId = String(formData.get("jobId") ?? "");
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/competitor-serp/jobs/${jobId}`,
      { accessToken: session.accessToken },
    );
    const job = await resp.json();
    if (job.status === "completed") {
      const latestResp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/competitor-serp/latest`,
        { accessToken: session.accessToken },
      );
      const result = latestResp.ok ? await latestResp.json() : null;
      return json({ ...job, result });
    }
    return json(job);
  }

  return json({ error: "Unknown intent" }, { status: 400 });
};

export function shouldRevalidate() {
  return false;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function asNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}

function asList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((v) => String(v ?? "").trim()).filter(Boolean);
}

function yesNo(value: unknown, locale: Locale): string {
  return value ? (locale === "fr" ? "Oui" : "Yes") : locale === "fr" ? "Non" : "No";
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
  return (labels[intent || "unknown"] ?? labels.unknown)[locale === "fr" ? 0 : 1];
}

function sourceLabel(source: string, locale: Locale): string {
  if (source === "domain_level") return locale === "fr" ? "Domain level" : "Domain level";
  if (source === "manual") return locale === "fr" ? "Manuel" : "Manual";
  return "SERP";
}

function sourceTone(source: string): "success" | "info" | "attention" {
  if (source === "domain_level") return "success";
  if (source === "manual") return "attention";
  return "info";
}

function metricLabel(label: string, value: string | number | React.ReactNode) {
  return (
    <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border">
      <BlockStack gap="050">
        <Text as="p" variant="bodySm" tone="subdued">{label}</Text>
        {typeof value === "string" || typeof value === "number" ? (
          <Text as="p" fontWeight="semibold">{value}</Text>
        ) : value}
      </BlockStack>
    </Box>
  );
}

function textOrDash(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

function ListBlock({ items, empty = "—" }: { items: string[]; empty?: string }) {
  if (!items.length) return <Text as="p" tone="subdued">{empty}</Text>;
  return (
    <BlockStack gap="050">
      {items.map((item, i) => (
        <Text as="p" variant="bodySm" key={`${item}-${i}`}>{item}</Text>
      ))}
    </BlockStack>
  );
}

function GapBadges({ gaps }: { gaps: CompetitorCrawlGap[] }) {
  if (!gaps.length) return null;
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

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <Text as="h2" variant="headingSm">{children}</Text>;
}

// ── URL Card ──────────────────────────────────────────────────────────────────

function CompetitorUrlCard({ page, locale }: { page: CompetitorSerpUrl; locale: Locale }) {
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

  if (page.blocked_by_robots) {
    return (
      <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
        <InlineStack gap="200" align="space-between">
          <BlockStack gap="100">
            <InlineStack gap="100">
              <Badge>{`Rank ${page.rank}`}</Badge>
              <Badge tone="critical">Robots.txt bloqué</Badge>
            </InlineStack>
            <Text as="p" variant="bodySm" tone="subdued">{page.keyword} · {page.url}</Text>
          </BlockStack>
        </InlineStack>
      </Box>
    );
  }

  if (page.error && !Object.keys(page.feature_summary ?? {}).length) {
    return (
      <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
        <InlineStack gap="200" align="space-between">
          <BlockStack gap="100">
            <InlineStack gap="100">
              <Badge>{`Rank ${page.rank}`}</Badge>
              <Badge tone="warning">Erreur crawl</Badge>
              {page.from_cache && <Badge tone="info">Cache</Badge>}
            </InlineStack>
            <Text as="p" variant="bodySm" tone="subdued">{page.keyword} · {page.url}</Text>
          </BlockStack>
        </InlineStack>
      </Box>
    );
  }

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="start" gap="300" wrap>
          <BlockStack gap="150">
            <InlineStack gap="150" wrap>
              <Badge tone="success">{`Rank ${page.rank}`}</Badge>
              <Badge tone="info">{pageTypeLabel(page.page_type, locale)}</Badge>
              <Badge>{intentLabel(page.keyword_intent_type, locale)}</Badge>
              {page.from_cache && <Badge tone="info">{locale === "fr" ? "Cache" : "Cache"}</Badge>}
            </InlineStack>
            <Text as="p" variant="bodySm" tone="subdued">{page.keyword}</Text>
          </BlockStack>
          <Button url={page.final_url || page.url} target="_blank" variant="secondary" size="slim">
            {locale === "fr" ? "Ouvrir" : "Open"}
          </Button>
        </InlineStack>
        <Text as="p" variant="bodySm" tone="subdued">{page.final_url || page.url}</Text>

        <Divider />

        <BlockStack gap="300">
          <SectionHeading>SERP</SectionHeading>
          <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
            {metricLabel("Mot-clé", page.keyword)}
            {metricLabel("Position", `#${page.rank}`)}
            {metricLabel("Intention", intentLabel(page.keyword_intent_type, locale))}
            {metricLabel("Featured snippet", yesNoBadge(serp.featured_snippet_present, locale))}
          </InlineGrid>
          {paa.length > 0 && (
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">PAA / questions SERP</Text>
                <ListBlock items={paa} />
              </BlockStack>
            </Box>
          )}
        </BlockStack>

        <BlockStack gap="300">
          <SectionHeading>SEO</SectionHeading>
          <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">Title SEO</Text>
                <Text as="p">{textOrDash(seo.title || page.title)}</Text>
                <InlineStack gap="100" wrap>
                  <Badge>{`${asNumber(seo.title_length)} car.`}</Badge>
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
                  <Badge>{`${asNumber(seo.meta_description_length)} car.`}</Badge>
                  <Badge tone={seo.meta_has_commercial_angle ? "success" : "info"}>
                    {`Angle ${yesNo(seo.meta_has_commercial_angle, locale)}`}
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
            {metricLabel("Longueur", `${asNumber(structure.word_count || fallback.word_count)} mots`)}
            {metricLabel("Paragraphes", asNumber(structure.paragraph_count))}
            {metricLabel("Listes", yesNoBadge(structure.has_bullet_lists, locale))}
            {metricLabel("Tableau comparatif", yesNoBadge(structure.has_comparison_table, locale))}
            {metricLabel("Specs produit", yesNoBadge(structure.has_product_specs_table, locale))}
          </InlineGrid>
          <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">H2</Text>
                <ListBlock items={h2} />
              </BlockStack>
            </Box>
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">H3</Text>
                <ListBlock items={h3} />
              </BlockStack>
            </Box>
          </InlineGrid>
        </BlockStack>

        <BlockStack gap="300">
          <SectionHeading>GEO / AEO / Schema</SectionHeading>
          <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
            {metricLabel("FAQ visible", `${yesNo(geo.has_faq_block, locale)} · ${asNumber(geo.faq_question_count)} q.`)}
            {metricLabel("Blocs réponse courte", `${yesNo(geo.has_short_answer_block, locale)} · ${asNumber(geo.short_answer_block_count)}`)}
            {metricLabel("Answerability", `${asNumber(geo.answerability_score)}/100`)}
            {metricLabel("AI readability", `${asNumber(geo.ai_readability_score)}/100`)}
            {metricLabel("JSON-LD", `${asNumber(schema.jsonld_count)} blocs`)}
            {metricLabel("Product / Offer", `${yesNo(schema.has_product_schema, locale)} / ${yesNo(schema.has_offer_schema, locale)}`)}
            {metricLabel("Breadcrumb / FAQPage", `${yesNo(schema.has_breadcrumb_schema, locale)} / ${yesNo(schema.has_faq_schema, locale)}`)}
            {metricLabel("Article / Org.", `${yesNo(schema.has_article_schema, locale)} / ${yesNo(schema.has_organization_schema, locale)}`)}
          </InlineGrid>
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="150">
              <Text as="p" variant="bodySm" tone="subdued">Types Schema détectés</Text>
              <InlineStack gap="100" wrap>
                {schemaTypes.length
                  ? schemaTypes.map((item) => <Badge key={item}>{item}</Badge>)
                  : <Text as="p" tone="subdued">—</Text>}
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
            {metricLabel("Alt descriptifs", `${asNumber(images.descriptive_image_alt_count)}/${asNumber(images.image_alt_count)}`)}
            {metricLabel("Alt manquants", asNumber(images.images_missing_alt_count))}
            {metricLabel("Breadcrumb", yesNoBadge(structure.has_breadcrumb_block || schema.has_breadcrumb_schema, locale))}
            {metricLabel("Confiance", yesNoBadge(trust.has_trust_proof || trust.has_reviews_or_social_proof, locale))}
            {metricLabel("Avantages/Inconvénients", yesNoBadge(structure.has_pros_cons, locale))}
          </InlineGrid>
          {linkExamples.length > 0 && (
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">Ancres internes</Text>
                <BlockStack gap="100">
                  {linkExamples.map((link, i) => (
                    <InlineStack key={`${link.href}-${i}`} gap="100" wrap>
                      <Badge>{link.target_type}</Badge>
                      <Text as="p" variant="bodySm">{textOrDash(link.anchor)}</Text>
                    </InlineStack>
                  ))}
                </BlockStack>
              </BlockStack>
            </Box>
          )}
          {altExamples.length > 0 && (
            <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
              <BlockStack gap="150">
                <Text as="p" variant="bodySm" tone="subdued">Alt text exemples</Text>
                <ListBlock items={altExamples} />
              </BlockStack>
            </Box>
          )}
        </BlockStack>

        <BlockStack gap="200">
          <SectionHeading>Profondeur produit</SectionHeading>
          <InlineStack gap="100" wrap>
            <Badge tone={depth.materials ? "success" : "info"}>{`Matériaux ${yesNo(depth.materials, locale)}`}</Badge>
            <Badge tone={depth.dimensions ? "success" : "info"}>{`Dimensions ${yesNo(depth.dimensions, locale)}`}</Badge>
            <Badge tone={depth.usage ? "success" : "info"}>{`Usage ${yesNo(depth.usage, locale)}`}</Badge>
            <Badge tone={depth.compatibility ? "success" : "info"}>{`Compatibilité ${yesNo(depth.compatibility, locale)}`}</Badge>
            <Badge tone={depth.care ? "success" : "info"}>{`Entretien ${yesNo(depth.care, locale)}`}</Badge>
          </InlineStack>
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

// ── Competitor section ────────────────────────────────────────────────────────

function CompetitorSection({
  competitor,
  locale,
  pageTypeFilter,
}: {
  competitor: CompetitorSerpDomain;
  locale: Locale;
  pageTypeFilter: string;
}) {
  const [open, setOpen] = useState(true);
  const filteredUrls = competitor.urls.filter(
    (u) => pageTypeFilter === "all" || (u.page_type || "unknown") === pageTypeFilter,
  );
  if (filteredUrls.length === 0) return null;

  const typeCounts = competitor.urls.reduce<Record<string, number>>((acc, u) => {
    const t = u.page_type || "unknown";
    acc[t] = (acc[t] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="center" wrap gap="300">
          <BlockStack gap="100">
            <InlineStack gap="150" wrap>
              <Text as="h2" variant="headingMd">{competitor.domain}</Text>
              <Badge tone={sourceTone(competitor.source)}>{sourceLabel(competitor.source, locale)}</Badge>
              <Badge tone="info">{`Force ${competitor.estimated_strength}`}</Badge>
            </InlineStack>
            <InlineStack gap="100" wrap>
              {Object.entries(typeCounts).map(([type, count]) => (
                <Badge key={type}>{`${pageTypeLabel(type, locale)} ×${count}`}</Badge>
              ))}
            </InlineStack>
          </BlockStack>
          <Button variant="plain" onClick={() => setOpen((o) => !o)}>
            {open
              ? locale === "fr" ? "Réduire" : "Collapse"
              : locale === "fr" ? `Voir ${filteredUrls.length} URLs` : `Show ${filteredUrls.length} URLs`}
          </Button>
        </InlineStack>

        <Collapsible id={`competitor-${competitor.domain}`} open={open}>
          <BlockStack gap="400">
            {filteredUrls.map((url, i) => (
              <CompetitorUrlCard key={`${url.url}-${i}`} page={url} locale={locale} />
            ))}
          </BlockStack>
        </Collapsible>
      </BlockStack>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CompetitorCrawlPage() {
  const { locale, result: initialResult, error: loaderError } = useLoaderData<typeof loader>() as LoaderData;
  const fetcher = useFetcher<ActionResult>();

  const [currentResult, setCurrentResult] = useState<CompetitorSerpResult | null>(initialResult);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const pollerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobIdRef = useRef<string | null>(null);
  // Always up-to-date fetcher reference — avoids stale closure in setInterval
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const [domainFilter, setDomainFilter] = useState("all");
  const [pageTypeFilter, setPageTypeFilter] = useState("all");

  const isRunning = jobStatus === "pending" || jobStatus === "running";

  const stopPolling = () => {
    if (pollerRef.current) {
      clearInterval(pollerRef.current);
      pollerRef.current = null;
    }
  };

  const startPolling = () => {
    stopPolling();
    pollerRef.current = setInterval(() => {
      if (fetcherRef.current.state === "idle" && jobIdRef.current) {
        fetcherRef.current.submit(
          { intent: "poll", jobId: jobIdRef.current },
          { method: "post" },
        );
      }
    }, 5000);
  };

  useEffect(() => () => stopPolling(), []);

  useEffect(() => {
    if (!fetcher.data) return;
    const data = fetcher.data as Record<string, unknown>;

    if (typeof data.job_id === "string") {
      setJobId(data.job_id);
      setJobStatus(String(data.status ?? "pending"));
      jobIdRef.current = data.job_id;
      startPolling();
      return;
    }

    if (typeof data.status === "string") {
      setJobStatus(data.status);
      if (data.status === "completed") {
        stopPolling();
        setJobId(null);
        jobIdRef.current = null;
        if (data.result) {
          setCurrentResult(data.result as CompetitorSerpResult);
        }
      } else if (data.status === "failed") {
        stopPolling();
        setJobId(null);
        jobIdRef.current = null;
        setActionError(String(data.error ?? "Crawl échoué"));
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher.data]);

  const handleStart = () => {
    setActionError(null);
    setJobStatus("pending");
    fetcher.submit({ intent: "start_job" }, { method: "post" });
  };

  const competitors = currentResult?.competitors ?? [];
  const filteredCompetitors = competitors.filter(
    (c) => domainFilter === "all" || c.domain === domainFilter,
  );

  const allPageTypes = Array.from(
    new Set(competitors.flatMap((c) => c.urls.map((u) => u.page_type || "unknown"))),
  );

  const domainOptions = [
    { label: locale === "fr" ? "Tous les concurrents" : "All competitors", value: "all" },
    ...competitors.map((c) => ({ label: c.domain, value: c.domain })),
  ];

  const pageTypeOptions = [
    { label: locale === "fr" ? "Tous les types de pages" : "All page types", value: "all" },
    ...["product", "collection", "blog", "faq", "guide", "unknown"]
      .filter((t) => allPageTypes.includes(t))
      .map((t) => ({ label: pageTypeLabel(t, locale), value: t })),
  ];

  const totalUrls = currentResult?.total_urls_crawled ?? 0;
  const keywordsUsed = currentResult?.keywords_used ?? 0;

  return (
    <Page
      title={locale === "fr" ? "Analyse concurrentielle SERP" : "SERP Competitor Analysis"}
      subtitle={
        locale === "fr"
          ? "Tous les concurrents identifiés, leurs URLs rankantes et métriques SEO/GEO."
          : "All identified competitors, their ranking URLs and SEO/GEO metrics."
      }
      backAction={{ content: locale === "fr" ? "Accueil" : "Dashboard", url: localizedPath("/app", locale) }}
      primaryAction={
        <Button
          variant="primary"
          onClick={handleStart}
          loading={isRunning}
          disabled={isRunning}
        >
          {isRunning
            ? locale === "fr" ? "Crawl en cours…" : "Crawling…"
            : locale === "fr" ? "Lancer l'analyse SERP" : "Run SERP analysis"}
        </Button>
      }
    >
      <BlockStack gap="400">
        {(loaderError || actionError) && (
          <Banner tone="critical">
            <Text as="p">{loaderError ?? actionError}</Text>
          </Banner>
        )}

        {isRunning && (
          <Card>
            <BlockStack gap="300">
              <InlineStack gap="200" blockAlign="center">
                <Spinner size="small" />
                <Text as="p">
                  {locale === "fr" ? "Crawl concurrent en cours — cela peut prendre 1 à 2 minutes…" : "Competitor crawl running — this may take 1–2 minutes…"}
                </Text>
              </InlineStack>
              <ProgressBar progress={jobStatus === "running" ? 50 : 10} />
            </BlockStack>
          </Card>
        )}

        {currentResult && (
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center" wrap>
                <BlockStack gap="050">
                  <Text as="h2" variant="headingMd">
                    {locale === "fr" ? "Vue concurrentielle" : "Competitor overview"}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {locale === "fr"
                      ? `Mis à jour le ${new Date(currentResult.created_at).toLocaleDateString("fr-FR")}`
                      : `Updated ${new Date(currentResult.created_at).toLocaleDateString("en-US")}`}
                  </Text>
                </BlockStack>
              </InlineStack>
              <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
                {metricLabel(locale === "fr" ? "Concurrents" : "Competitors", competitors.length)}
                {metricLabel("URLs crawlées", totalUrls)}
                {metricLabel(locale === "fr" ? "Mots-clés SERP" : "SERP keywords", keywordsUsed)}
                {metricLabel(
                  locale === "fr" ? "Produit / Collection / Blog / FAQ" : "Product / Collection / Blog / FAQ",
                  (() => {
                    const urls = competitors.flatMap((c) => c.urls);
                    const cnt = (t: string) => urls.filter((u) => (u.page_type || "unknown") === t).length;
                    return `${cnt("product")} / ${cnt("collection")} / ${cnt("blog")} / ${cnt("faq")}`;
                  })(),
                )}
              </InlineGrid>
              <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
                <Select
                  label={locale === "fr" ? "Concurrent" : "Competitor"}
                  options={domainOptions}
                  value={domainFilter}
                  onChange={setDomainFilter}
                />
                <Select
                  label={locale === "fr" ? "Type de page" : "Page type"}
                  options={pageTypeOptions}
                  value={pageTypeFilter}
                  onChange={setPageTypeFilter}
                />
              </InlineGrid>
            </BlockStack>
          </Card>
        )}

        {!currentResult && !isRunning && (
          <EmptyState
            heading={locale === "fr" ? "Aucune analyse concurrentielle" : "No competitor analysis yet"}
            action={{ content: locale === "fr" ? "Lancer l'analyse SERP" : "Run SERP analysis", onAction: handleStart }}
            image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
          >
            <Text as="p">
              {locale === "fr"
                ? "Lancez l'analyse pour crawler tous les concurrents identifiés par DataForSeo sur vos mots-clés produits."
                : "Run the analysis to crawl all competitors identified by DataForSeo on your product keywords."}
            </Text>
          </EmptyState>
        )}

        {currentResult?.error === "no_market_analysis" && (
          <Banner tone="warning">
            <Text as="p">
              {locale === "fr"
                ? "Aucune analyse marché trouvée. Lancez d'abord une analyse marché pour alimenter le cache SERP."
                : "No market analysis found. Run a market analysis first to populate the SERP cache."}
            </Text>
            <Button url={localizedPath("/app/market-analysis", locale)} variant="plain">
              {locale === "fr" ? "Lancer l'analyse marché" : "Run market analysis"}
            </Button>
          </Banner>
        )}

        {filteredCompetitors.length > 0 && (
          <BlockStack gap="400">
            {filteredCompetitors.map((competitor) => (
              <CompetitorSection
                key={competitor.domain}
                competitor={competitor}
                locale={locale}
                pageTypeFilter={pageTypeFilter}
              />
            ))}
          </BlockStack>
        )}

        {currentResult && filteredCompetitors.length === 0 && !currentResult.error && (
          <Banner tone="info">
            <Text as="p">
              {locale === "fr" ? "Aucun concurrent ne correspond aux filtres." : "No competitor matches the filters."}
            </Text>
          </Banner>
        )}
      </BlockStack>
    </Page>
  );
}
