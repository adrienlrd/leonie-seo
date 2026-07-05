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
  List,
  Page,
  Select,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, loaderPhrases, localizedPath, type Locale } from "../lib/i18n";
import { AnalysisLoader } from "../components/AnalysisLoader";
import type {
  CompetitorCrawlTopUrl,
  CompetitorProfile,
  CompetitorSerpResult,
} from "../lib/marketAnalysisShared";
import React, { useEffect, useMemo, useRef, useState } from "react";

interface LoaderData {
  shop: string;
  locale: Locale;
  preview: CompetitorSerpResult | null;
  latest: CompetitorSerpResult | null;
  error: string | null;
}

type ActionData =
  | { job_id: string; status: string }
  | { status: string; result?: CompetitorSerpResult | null; error?: string }
  | { error: string };

async function fetchJson(
  shop: string,
  path: string,
  accessToken?: string,
): Promise<{ ok: boolean; status: number; data: unknown }> {
  const resp = await callBackendForShop(shop, path, { accessToken });
  const data = resp.ok ? await resp.json() : null;
  return { ok: resp.ok, status: resp.status, data };
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  try {
    const [previewRes, latestRes] = await Promise.all([
      fetchJson(session.shop, `/api/shops/${session.shop}/competitor-serp/preview`, session.accessToken),
      fetchJson(session.shop, `/api/shops/${session.shop}/competitor-serp/latest`, session.accessToken),
    ]);
    return json<LoaderData>({
      shop: session.shop,
      locale,
      preview: previewRes.ok ? (previewRes.data as CompetitorSerpResult) : null,
      latest: latestRes.ok ? (latestRes.data as CompetitorSerpResult) : null,
      error: previewRes.ok ? null : `HTTP ${previewRes.status}`,
    });
  } catch (err) {
    return json<LoaderData>({
      shop: session.shop,
      locale,
      preview: null,
      latest: null,
      error: err instanceof Error ? err.message : "Network error",
    });
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
    const jobRaw = resp.ok ? await resp.json() : { status: "failed", error: `HTTP ${resp.status}` };
    if (jobRaw.status === "completed") {
      const latestRes = await fetchJson(
        session.shop,
        `/api/shops/${session.shop}/competitor-serp/latest`,
        session.accessToken,
      );
      return json({ ...jobRaw, result: latestRes.ok ? latestRes.data : null });
    }
    return json(jobRaw);
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

function strengthTone(label: string): "success" | "warning" | "critical" {
  if (label === "élevée") return "success";
  if (label === "moyenne") return "warning";
  return "critical";
}

function textOrDash(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
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

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <Text as="h3" variant="headingSm">{children}</Text>;
}

// ── Synthesis block (the narrative "what they do / how to inspire") ────────────

function SynthesisBlock({
  profile,
  locale,
  running,
}: {
  profile: CompetitorProfile;
  locale: Locale;
  running: boolean;
}) {
  const synthesis = profile.synthesis;

  if (synthesis === undefined || synthesis === null) {
    if (running) {
      return (
        <Box padding="300" background="bg-surface-secondary" borderRadius="200">
          <AnalysisLoader
            phrases={loaderPhrases(locale, "crawl")}
            estimateMs={120_000}
            title={locale === "fr" ? "Analyse détaillée en cours…" : "Detailed analysis in progress…"}
          />
        </Box>
      );
    }
    return (
      <Box padding="300" background="bg-surface-secondary" borderRadius="200">
        <Text as="p" tone="subdued">
          {locale === "fr"
            ? "Clique sur « Générer l'analyse détaillée » pour obtenir les forces, opportunités et actions inspirées de ce concurrent."
            : "Click “Generate detailed analysis” to get this competitor's strengths, opportunities and inspired actions."}
        </Text>
      </Box>
    );
  }

  return (
    <BlockStack gap="300">
      {synthesis.title_style && (
        <Box padding="300" background="bg-surface-secondary" borderRadius="200">
          <BlockStack gap="050">
            <Text as="p" variant="bodySm" tone="subdued">
              {locale === "fr" ? "Style de titres" : "Title style"}
            </Text>
            <Text as="p">{synthesis.title_style}</Text>
          </BlockStack>
        </Box>
      )}
      <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
        {synthesis.strengths.length > 0 && (
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="150">
              <Text as="p" fontWeight="semibold">
                {locale === "fr" ? "✓ Ce qu'ils font bien" : "✓ What they do well"}
              </Text>
              <List type="bullet">
                {synthesis.strengths.map((s, i) => (
                  <List.Item key={i}>{s}</List.Item>
                ))}
              </List>
            </BlockStack>
          </Box>
        )}
        {synthesis.opportunities.length > 0 && (
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="150">
              <Text as="p" fontWeight="semibold">
                {locale === "fr" ? "⚡ Opportunités pour toi" : "⚡ Your opportunities"}
              </Text>
              <List type="bullet">
                {synthesis.opportunities.map((o, i) => (
                  <List.Item key={i}>{o}</List.Item>
                ))}
              </List>
            </BlockStack>
          </Box>
        )}
      </InlineGrid>
      {synthesis.inspiration.length > 0 && (
        <Box padding="300" background="bg-surface-success" borderRadius="200">
          <BlockStack gap="150">
            <Text as="p" fontWeight="semibold">
              {locale === "fr" ? "→ À faire pour t'en inspirer" : "→ Actions to take"}
            </Text>
            <List type="number">
              {synthesis.inspiration.map((a, i) => (
                <List.Item key={i}>{a}</List.Item>
              ))}
            </List>
          </BlockStack>
        </Box>
      )}
    </BlockStack>
  );
}

// ── Technical detail (reuses the crawled-page metrics) ─────────────────────────

function TechnicalDetail({ page, locale }: { page: CompetitorCrawlTopUrl; locale: Locale }) {
  const seo = page.seo ?? {};
  const structure = page.structure ?? {};
  const geo = page.geo_aeo ?? {};
  const schema = page.schema ?? {};
  const links = page.links ?? {};
  const images = page.images ?? {};
  const trust = page.trust ?? {};
  const h2 = asList(structure.h2_texts);
  const schemaTypes = asList(schema.schema_types);

  return (
    <BlockStack gap="400">
      <Text as="p" variant="bodySm" tone="subdued">{page.final_url || page.url}</Text>

      <BlockStack gap="200">
        <SectionHeading>GEO</SectionHeading>
        <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="150">
              <Text as="p" variant="bodySm" tone="subdued">Title</Text>
              <Text as="p">{textOrDash(seo.title || page.title)}</Text>
              <InlineStack gap="100" wrap>
                <Badge>{`${asNumber(seo.title_length)} car.`}</Badge>
                <Badge tone={seo.title_keyword_present ? "success" : "attention"}>
                  {`Mot-clé ${yesNo(seo.title_keyword_present, locale)}`}
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
                <Badge tone={seo.meta_has_cta ? "success" : "info"}>
                  {`CTA ${yesNo(seo.meta_has_cta, locale)}`}
                </Badge>
              </InlineStack>
            </BlockStack>
          </Box>
        </InlineGrid>
      </BlockStack>

      <BlockStack gap="200">
        <SectionHeading>{locale === "fr" ? "Structure et contenu" : "Structure & content"}</SectionHeading>
        <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
          {metricLabel("H1", asNumber(structure.h1_count))}
          {metricLabel("H2", asNumber(structure.h2_count))}
          {metricLabel("H3", asNumber(structure.h3_count))}
          {metricLabel(locale === "fr" ? "Longueur" : "Length", `${asNumber(structure.word_count)} ${locale === "fr" ? "mots" : "words"}`)}
          {metricLabel(locale === "fr" ? "Listes" : "Lists", yesNoBadge(structure.has_bullet_lists, locale))}
          {metricLabel(locale === "fr" ? "Tableau comparatif" : "Comparison table", yesNoBadge(structure.has_comparison_table, locale))}
          {metricLabel("Specs produit", yesNoBadge(structure.has_product_specs_table, locale))}
          {metricLabel(locale === "fr" ? "Av./Inconv." : "Pros/Cons", yesNoBadge(structure.has_pros_cons, locale))}
        </InlineGrid>
        {h2.length > 0 && (
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="150">
              <Text as="p" variant="bodySm" tone="subdued">H2</Text>
              <BlockStack gap="050">
                {h2.map((item, i) => (
                  <Text as="p" variant="bodySm" key={`${item}-${i}`}>{item}</Text>
                ))}
              </BlockStack>
            </BlockStack>
          </Box>
        )}
      </BlockStack>

      <BlockStack gap="200">
        <SectionHeading>GEO / AEO / Schema</SectionHeading>
        <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
          {metricLabel("FAQ visible", `${yesNo(geo.has_faq_block, locale)} · ${asNumber(geo.faq_question_count)} q.`)}
          {metricLabel(locale === "fr" ? "Blocs réponse" : "Answer blocks", yesNoBadge(geo.has_short_answer_block, locale))}
          {metricLabel("Answerability", `${asNumber(geo.answerability_score)}/100`)}
          {metricLabel("AI readability", `${asNumber(geo.ai_readability_score)}/100`)}
          {metricLabel("JSON-LD", `${asNumber(schema.jsonld_count)} blocs`)}
          {metricLabel("Product / Offer", `${yesNo(schema.has_product_schema, locale)} / ${yesNo(schema.has_offer_schema, locale)}`)}
          {metricLabel("Breadcrumb / FAQPage", `${yesNo(schema.has_breadcrumb_schema, locale)} / ${yesNo(schema.has_faq_schema, locale)}`)}
          {metricLabel(locale === "fr" ? "Liens internes" : "Internal links", asNumber(links.internal_link_count))}
        </InlineGrid>
        {schemaTypes.length > 0 && (
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="150">
              <Text as="p" variant="bodySm" tone="subdued">{locale === "fr" ? "Schémas détectés" : "Detected schemas"}</Text>
              <InlineStack gap="100" wrap>
                {schemaTypes.map((item) => <Badge key={item}>{item}</Badge>)}
              </InlineStack>
            </BlockStack>
          </Box>
        )}
        <InlineStack gap="100" wrap>
          {metricLabel(locale === "fr" ? "Images (alt)" : "Images (alt)", `${asNumber(images.descriptive_image_alt_count)}/${asNumber(images.image_count)}`)}
          {metricLabel(locale === "fr" ? "Confiance" : "Trust", yesNoBadge(trust.has_trust_proof || trust.has_reviews_or_social_proof, locale))}
        </InlineStack>
      </BlockStack>
    </BlockStack>
  );
}

// ── Competitor card ───────────────────────────────────────────────────────────

function CompetitorCard({
  profile,
  locale,
  running,
}: {
  profile: CompetitorProfile;
  locale: Locale;
  running: boolean;
}) {
  const [detailOpen, setDetailOpen] = useState(false);
  const topKeywords = profile.ranked_keywords.slice(0, 8);

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="start" gap="300" wrap>
          <BlockStack gap="150">
            <InlineStack gap="150" blockAlign="center" wrap>
              <Text as="h2" variant="headingMd">{profile.domain}</Text>
              <Badge tone={strengthTone(profile.strength_label)}>
                {`${locale === "fr" ? "Force" : "Strength"} ${profile.strength_label}`}
              </Badge>
            </InlineStack>
            <Text as="p" tone="subdued">
              {profile.ranked_keyword_count > 0
                ? locale === "fr"
                  ? `${profile.ranked_keyword_count} mots-clés rankés · meilleure position #${profile.best_rank} · moyenne #${profile.avg_rank}`
                  : `${profile.ranked_keyword_count} ranked keywords · best #${profile.best_rank} · avg #${profile.avg_rank}`
                : profile.content_angle
                  ? profile.content_angle
                  : locale === "fr"
                    ? "Concurrent identifié au niveau du domaine"
                    : "Competitor identified at domain level"}
            </Text>
          </BlockStack>
          {profile.top_page_url && (
            <Button url={profile.top_page_url} target="_blank" variant="secondary" size="slim">
              {locale === "fr" ? "Voir leur page" : "View their page"}
            </Button>
          )}
        </InlineStack>

        <Divider />

        <SynthesisBlock profile={profile} locale={locale} running={running} />

        {topKeywords.length > 0 && (
          <BlockStack gap="200">
            <SectionHeading>{locale === "fr" ? "Mots-clés où ils apparaissent" : "Keywords they rank for"}</SectionHeading>
            <InlineStack gap="100" wrap>
              {topKeywords.map((kw, i) => (
                <Badge key={`${kw.keyword}-${i}`} tone={kw.rank <= 3 ? "success" : undefined}>
                  {`${kw.keyword} · #${kw.rank}`}
                </Badge>
              ))}
            </InlineStack>
          </BlockStack>
        )}

        {profile.top_page && (
          <BlockStack gap="200">
            <Button variant="plain" onClick={() => setDetailOpen((o) => !o)} disclosure={detailOpen ? "up" : "down"}>
              {locale === "fr" ? "Détail technique de leur page" : "Technical detail of their page"}
            </Button>
            <Collapsible id={`detail-${profile.domain}`} open={detailOpen}>
              <TechnicalDetail page={profile.top_page} locale={locale} />
            </Collapsible>
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function mostRecent(
  preview: CompetitorSerpResult | null,
  latest: CompetitorSerpResult | null,
): CompetitorSerpResult | null {
  if (latest?.enriched && latest.competitors.length > 0) return latest;
  return preview;
}

export default function CompetitorCrawlPage() {
  const { locale, preview, latest, error: loaderError } = useLoaderData<typeof loader>() as LoaderData;
  const fetcher = useFetcher<ActionData>();

  const [result, setResult] = useState<CompetitorSerpResult | null>(() => mostRecent(preview, latest));
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [domainFilter, setDomainFilter] = useState("all");

  const pollerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobIdRef = useRef<string | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const isEnriched = Boolean(latest?.enriched) && (result?.enriched ?? false);
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
        fetcherRef.current.submit({ intent: "poll", jobId: jobIdRef.current }, { method: "post" });
      }
    }, 5000);
  };

  const handleEnrich = () => {
    setActionError(null);
    setJobStatus("pending");
    fetcher.submit({ intent: "start_job" }, { method: "post" });
  };

  useEffect(() => () => stopPolling(), []);

  useEffect(() => {
    if (!fetcher.data) return;
    const data = fetcher.data as Record<string, unknown>;

    // Terminal states first: the completed/failed poll response also carries
    // job_id, so it must be handled before the "job started" branch below.
    if (data.status === "completed") {
      stopPolling();
      jobIdRef.current = null;
      setJobStatus("completed");
      if (data.result) setResult(data.result as CompetitorSerpResult);
      return;
    }
    if (data.status === "failed") {
      stopPolling();
      jobIdRef.current = null;
      setJobStatus("failed");
      setActionError(String(data.error ?? "Analyse échouée"));
      return;
    }

    // Job just started (start_job response) — begin polling.
    if (typeof data.job_id === "string" && !jobIdRef.current) {
      jobIdRef.current = data.job_id;
      setJobStatus(String(data.status ?? "pending"));
      startPolling();
      return;
    }

    // Intermediate poll (pending/running) — keep the status fresh.
    if (typeof data.status === "string") {
      setJobStatus(data.status);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher.data]);

  const competitors = result?.competitors ?? [];
  const filtered = useMemo(
    () => competitors.filter((c) => domainFilter === "all" || c.domain === domainFilter),
    [competitors, domainFilter],
  );

  const domainOptions = [
    { label: locale === "fr" ? "Tous les concurrents" : "All competitors", value: "all" },
    ...competitors.map((c) => ({ label: c.domain, value: c.domain })),
  ];

  const noMarketAnalysis = result?.error === "no_market_analysis";
  const hasData = competitors.length > 0;

  return (
    <Page
      title={locale === "fr" ? "Concurrents" : "Competitors"}
      subtitle={
        locale === "fr"
          ? "Ce que font tes concurrents et comment t'en inspirer pour ton GEO."
          : "What your competitors do and how to take inspiration for your GEO."
      }
      primaryAction={
        hasData
          ? {
              content: isEnriched
                ? locale === "fr" ? "Régénérer l'analyse" : "Regenerate analysis"
                : locale === "fr" ? "Générer l'analyse détaillée" : "Generate detailed analysis",
              onAction: handleEnrich,
              loading: isRunning,
              disabled: isRunning,
            }
          : undefined
      }
    >
      <BlockStack gap="400">
        {(loaderError || actionError) && (
          <Banner tone="critical"><Text as="p">{loaderError ?? actionError}</Text></Banner>
        )}

        {noMarketAnalysis && (
          <Banner tone="warning">
            <BlockStack gap="200">
              <Text as="p">
                {locale === "fr"
                  ? "Aucune analyse marché trouvée. Lance d'abord une analyse marché pour identifier tes concurrents."
                  : "No market analysis found. Run a market analysis first to identify your competitors."}
              </Text>
              <Button url={localizedPath("/app/products", locale)} variant="plain">
                {locale === "fr" ? "Lancer l'analyse marché" : "Run market analysis"}
              </Button>
            </BlockStack>
          </Banner>
        )}

        {hasData && (
          <Card>
            <BlockStack gap="300">
              <InlineStack align="space-between" blockAlign="center" wrap gap="300">
                <BlockStack gap="050">
                  <Text as="h2" variant="headingMd">
                    {locale === "fr" ? "Vue d'ensemble" : "Overview"}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {isEnriched
                      ? locale === "fr"
                        ? "Analyse détaillée disponible"
                        : "Detailed analysis available"
                      : locale === "fr"
                        ? "Profils SERP — génère l'analyse détaillée pour les recommandations"
                        : "SERP profiles — generate the detailed analysis for recommendations"}
                  </Text>
                </BlockStack>
              </InlineStack>
              <InlineGrid columns={{ xs: 1, sm: 3 }} gap="300">
                {metricLabel(locale === "fr" ? "Concurrents" : "Competitors", competitors.length)}
                {metricLabel(locale === "fr" ? "Mots-clés SERP" : "SERP keywords", asNumber(result?.keywords_used))}
                {metricLabel(
                  locale === "fr" ? "Analyse détaillée" : "Detailed analysis",
                  isEnriched ? (locale === "fr" ? "Oui" : "Yes") : (locale === "fr" ? "Non" : "No"),
                )}
              </InlineGrid>
              {competitors.length > 1 && (
                <Select
                  label={locale === "fr" ? "Filtrer par concurrent" : "Filter by competitor"}
                  options={domainOptions}
                  value={domainFilter}
                  onChange={setDomainFilter}
                />
              )}
            </BlockStack>
          </Card>
        )}

        {isRunning && (
          <Banner tone="info">
            <AnalysisLoader
              phrases={loaderPhrases(locale, "crawl")}
              estimateMs={30_000}
              title={locale === "fr"
                ? "Génération de l'analyse détaillée — ~30 s. Les recommandations apparaîtront ci-dessous."
                : "Generating detailed analysis — ~30s. Recommendations will appear below."}
            />
          </Banner>
        )}

        {!hasData && !noMarketAnalysis && (
          <EmptyState
            heading={locale === "fr" ? "Aucun concurrent identifié" : "No competitor identified"}
            action={{
              content: locale === "fr" ? "Lancer l'analyse marché" : "Run market analysis",
              url: localizedPath("/app/products", locale),
            }}
            image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
          >
            <Text as="p">
              {locale === "fr"
                ? "Lance une analyse marché : elle interroge DataForSeo et alimente cette page avec tes concurrents réels."
                : "Run a market analysis: it queries DataForSeo and populates this page with your real competitors."}
            </Text>
          </EmptyState>
        )}

        {filtered.map((profile) => (
          <CompetitorCard key={profile.domain} profile={profile} locale={locale} running={isRunning} />
        ))}

        {hasData && filtered.length === 0 && (
          <Banner tone="info">
            <Text as="p">{locale === "fr" ? "Aucun concurrent ne correspond au filtre." : "No competitor matches the filter."}</Text>
          </Banner>
        )}
      </BlockStack>
    </Page>
  );
}
