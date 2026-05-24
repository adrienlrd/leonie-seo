import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useFetcher } from "@remix-run/react";
import type { ShouldRevalidateFunction } from "@remix-run/react";
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
  Modal,
  Page,
  ProgressBar,
  Spinner,
  Text,
  TextField,
} from "@shopify/polaris";
import { useEffect, useRef, useState } from "react";
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
  data_source?: "gsc" | "llm_estimated";
  gsc_impressions?: number;
  gsc_clicks?: number;
  gsc_position?: number;
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

interface JobState {
  job_id?: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  total: number;
  products: ProductResult[];
  analyzed_at: string | null;
  active_product_count: number;
  analyzed_product_count: number;
  total_opportunity_count: number;
  sources_used: string[];
  error: string | null;
  // identification job fields
  labels?: Record<string, string>;
  product_titles?: Record<string, string>;
  product_count?: number;
}

interface LoaderData {
  locale: Locale;
  shop: string;
  latestJob: JobState | null;
  latestIdentification: {
    labels: Record<string, string>;
    product_titles: Record<string, string>;
  } | null;
  gscConnected: boolean;
  ga4Connected: boolean;
}

// ── Revalidation guard — polling actions must not re-run the loader ───────────

export const shouldRevalidate: ShouldRevalidateFunction = (args) => {
  const intent = args.formData?.get("intent");
  if (intent === "poll" || intent === "pollIdentify" || intent === "pollSingle") {
    return false;
  }
  return args.defaultShouldRevalidate;
};

// ── Remix loader / action ─────────────────────────────────────────────────────

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);

  const fetchOpt = { accessToken: session.accessToken, method: "GET" as const };

  const [latestJobResp, identifyResp, gscResp, ga4Resp] = await Promise.allSettled([
    callBackendForShop(session.shop, `/api/shops/${session.shop}/market-analysis/latest`, {
      ...fetchOpt,
      signal: AbortSignal.timeout(5_000),
    }),
    callBackendForShop(session.shop, `/api/shops/${session.shop}/market-analysis/identify/latest`, {
      ...fetchOpt,
      signal: AbortSignal.timeout(5_000),
    }),
    callBackendForShop(session.shop, `/api/shops/${session.shop}/gsc/status`, {
      ...fetchOpt,
      signal: AbortSignal.timeout(5_000),
    }),
    callBackendForShop(session.shop, `/api/shops/${session.shop}/ga4/status`, {
      ...fetchOpt,
      signal: AbortSignal.timeout(5_000),
    }),
  ]);

  let latestJob: JobState | null = null;
  if (latestJobResp.status === "fulfilled" && latestJobResp.value.ok) {
    latestJob = await latestJobResp.value.json() as JobState;
  }

  let latestIdentification: { labels: Record<string, string>; product_titles: Record<string, string> } | null = null;
  if (identifyResp.status === "fulfilled" && identifyResp.value.ok) {
    latestIdentification = await identifyResp.value.json() as typeof latestIdentification;
  }

  let gscConnected = false;
  if (gscResp.status === "fulfilled" && gscResp.value.ok) {
    const data = await gscResp.value.json() as { connected?: boolean };
    gscConnected = data.connected === true;
  }

  let ga4Connected = false;
  if (ga4Resp.status === "fulfilled" && ga4Resp.value.ok) {
    const data = await ga4Resp.value.json() as { ready?: boolean };
    ga4Connected = data.ready === true;
  }

  return json({ locale, shop: session.shop, latestJob, latestIdentification, gscConnected, ga4Connected });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const formData = await request.formData();
  const intent = formData.get("intent") as string;

  // ── Step 1: start identification job ──────────────────────────────────────
  if (intent === "startIdentify") {
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/identify`,
        { accessToken: session.accessToken, method: "POST", signal: AbortSignal.timeout(30_000) },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "startIdentify", jobId: null, error: `Erreur backend ${resp.status}: ${err}` });
      }
      const data = await resp.json() as { job_id: string };
      return json({ type: "startIdentify", jobId: data.job_id, error: null });
    } catch (err) {
      return json({ type: "startIdentify", jobId: null, error: String(err) });
    }
  }

  // ── Step 1: poll identification job ───────────────────────────────────────
  if (intent === "pollIdentify") {
    const jobId = formData.get("jobId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs/${jobId}`,
        { accessToken: session.accessToken, method: "GET", signal: AbortSignal.timeout(10_000) },
      );
      if (!resp.ok) return json({ type: "pollIdentify", job: null, error: `Erreur poll ${resp.status}` });
      const job = await resp.json() as JobState;
      return json({ type: "pollIdentify", job, error: null });
    } catch (err) {
      return json({ type: "pollIdentify", job: null, error: String(err) });
    }
  }

  // ── Step 1→2: save validated labels then start full analysis ──────────────
  if (intent === "saveAndStart") {
    const identificationsRaw = formData.get("identifications") as string;
    try {
      const identifications = JSON.parse(identificationsRaw) as Record<string, string>;
      // 1. Persist validated labels
      await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/identifications`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify({ identifications }),
          signal: AbortSignal.timeout(10_000),
        },
      );
    } catch {
      // Non-blocking — proceed to analysis even if persist fails
    }
    // 2. Start analysis job
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs`,
        { accessToken: session.accessToken, method: "POST", signal: AbortSignal.timeout(30_000) },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "start", jobId: null, error: `Erreur backend ${resp.status}: ${err}` });
      }
      const data = await resp.json() as { job_id: string };
      return json({ type: "start", jobId: data.job_id, error: null });
    } catch (err) {
      return json({ type: "start", jobId: null, error: String(err) });
    }
  }

  // ── Step 2: start analysis (re-run, skips step 1) ─────────────────────────
  if (intent === "start") {
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs`,
        { accessToken: session.accessToken, method: "POST", signal: AbortSignal.timeout(30_000) },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "start", jobId: null, error: `Erreur backend ${resp.status}: ${err}` });
      }
      const data = await resp.json() as { job_id: string };
      return json({ type: "start", jobId: data.job_id, error: null });
    } catch (err) {
      return json({ type: "start", jobId: null, error: String(err) });
    }
  }

  // ── Step 2: poll analysis job ─────────────────────────────────────────────
  if (intent === "poll") {
    const jobId = formData.get("jobId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs/${jobId}`,
        { accessToken: session.accessToken, method: "GET", signal: AbortSignal.timeout(10_000) },
      );
      if (!resp.ok) return json({ type: "poll", job: null, error: `Erreur poll ${resp.status}` });
      const job = await resp.json() as JobState;
      return json({ type: "poll", job, error: null });
    } catch (err) {
      return json({ type: "poll", job: null, error: String(err) });
    }
  }

  // ── Step 1→2: save validated labels only (no new analysis) ───────────────
  if (intent === "saveOnly") {
    const identificationsRaw = formData.get("identifications") as string;
    try {
      const identifications = JSON.parse(identificationsRaw) as Record<string, string>;
      await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/identifications`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify({ identifications }),
          signal: AbortSignal.timeout(10_000),
        },
      );
    } catch {
      // Non-blocking
    }
    return json({ type: "saveOnly", error: null });
  }

  // ── Single-product analysis ────────────────────────────────────────────────
  if (intent === "startSingle") {
    const productId = formData.get("productId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs?product_ids=${encodeURIComponent(productId)}`,
        { accessToken: session.accessToken, method: "POST", signal: AbortSignal.timeout(30_000) },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "startSingle", jobId: null, productId, error: `Erreur ${resp.status}: ${err}` });
      }
      const data = await resp.json() as { job_id: string };
      return json({ type: "startSingle", jobId: data.job_id, productId, error: null });
    } catch (err) {
      return json({ type: "startSingle", jobId: null, productId, error: String(err) });
    }
  }

  if (intent === "pollSingle") {
    const jobId = formData.get("jobId") as string;
    const productId = formData.get("productId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs/${jobId}`,
        { accessToken: session.accessToken, method: "GET", signal: AbortSignal.timeout(10_000) },
      );
      if (!resp.ok) return json({ type: "pollSingle", job: null, productId, error: `Erreur poll ${resp.status}` });
      const job = await resp.json() as JobState;
      return json({ type: "pollSingle", job, productId, error: null });
    } catch (err) {
      return json({ type: "pollSingle", job: null, productId, error: String(err) });
    }
  }

  return json({ type: "unknown", error: "Unknown intent" });
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
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function progressLabel(locale: Locale, done: number, total: number): string {
  return t(locale, "marketAnalysisProgress")
    .replace("{done}", String(done))
    .replace("{total}", String(total));
}

// ── Sub-components ────────────────────────────────────────────────────────────

function DataSourcesCard({
  gscConnected,
  ga4Connected,
  locale,
}: {
  gscConnected: boolean;
  ga4Connected: boolean;
  locale: Locale;
}) {
  return (
    <Card>
      <BlockStack gap="200">
        <Text as="h3" variant="headingSm">
          {locale === "fr" ? "Sources de données" : "Data sources"}
        </Text>
        <InlineStack gap="400" wrap>
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="bodySm">Google Search Console</Text>
            {gscConnected ? (
              <Badge tone="success">OK</Badge>
            ) : (
              <Button variant="plain" size="slim" url="/app/onboarding">
                {locale === "fr" ? "Se connecter" : "Connect"}
              </Button>
            )}
          </InlineStack>
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="bodySm">Google Analytics 4</Text>
            {ga4Connected ? (
              <Badge tone="success">OK</Badge>
            ) : (
              <Button variant="plain" size="slim" url="/app/ga4">
                {locale === "fr" ? "Se connecter" : "Connect"}
              </Button>
            )}
          </InlineStack>
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

function SummaryCard({ job, locale }: { job: JobState; locale: Locale }) {
  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack gap="400" wrap>
          {job.analyzed_at && (
            <Text as="p" variant="bodySm" tone="subdued">
              {t(locale, "marketAnalysisLastRun")} : {formatDate(job.analyzed_at)}
            </Text>
          )}
          <Text as="p" variant="bodySm">
            <strong>{job.analyzed_product_count}</strong>{" "}
            {t(locale, "marketAnalysisProductCount")}
          </Text>
          <Text as="p" variant="bodySm">
            <strong>{job.total_opportunity_count}</strong>{" "}
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
  isAnalyzing,
  onAnalyze,
  analyzeDisabled,
}: {
  product: ProductResult;
  locale: Locale;
  isAnalyzing: boolean;
  onAnalyze: () => void;
  analyzeDisabled: boolean;
}) {
  const [openSection, setOpenSection] = useState<string | null>(null);
  const toggle = (s: string) => setOpenSection((p) => (p === s ? null : s));
  const pack = product.content_test_pack;

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack gap="200" align="space-between" wrap>
          <BlockStack gap="100">
            <Text as="h3" variant="headingSm">{product.product_title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">/{product.product_handle}</Text>
          </BlockStack>
          <InlineStack gap="200">
            <Badge tone={scoreTone(product.opportunity_score)}>
              {`Score ${product.opportunity_score}/100`}
            </Badge>
            <Badge tone={confidenceTone(product.confidence)}>{product.confidence}</Badge>
            {isAnalyzing ? (
              <Spinner size="small" />
            ) : (
              <Button size="slim" onClick={onAnalyze} disabled={analyzeDisabled}>
                {t(locale, "marketAnalysisAnalyzeOne")}
              </Button>
            )}
          </InlineStack>
        </InlineStack>

        {product.product_summary && (
          <Text as="p" variant="bodySm">{product.product_summary}</Text>
        )}
        {product.target_customer && (
          <Text as="p" variant="bodySm" tone="subdued">
            {locale === "fr" ? "Client cible" : "Target customer"} : {product.target_customer}
          </Text>
        )}

        {product.seo_keywords.length > 0 && (
          <Box>
            <Button variant="plain" onClick={() => toggle("keywords")}>
              {`${t(locale, "marketAnalysisSeoKeywords")} (${product.seo_keywords.length})`}
            </Button>
            <Collapsible id={`kw-${product.product_id}`} open={openSection === "keywords"}>
              <Box paddingBlockStart="200">
                <DataTable
                  columnContentTypes={["text", "text", "numeric", "numeric", "numeric", "text", "text"]}
                  headings={[
                    locale === "fr" ? "Requête" : "Query",
                    "Intent",
                    locale === "fr" ? "Demande" : "Demand",
                    locale === "fr" ? "Concurrence" : "Competition",
                    "Fit",
                    locale === "fr" ? "Impr. GSC" : "GSC Impr.",
                    locale === "fr" ? "Pos. GSC" : "GSC Pos.",
                  ]}
                  rows={product.seo_keywords.map((k) => [
                    k.data_source === "gsc" ? `${k.query} ✓` : k.query,
                    k.intent_type,
                    String(k.demand_score),
                    String(k.competition_score),
                    String(k.product_fit_score),
                    k.data_source === "gsc" ? String(k.gsc_impressions ?? "") : "—",
                    k.data_source === "gsc" ? String(k.gsc_position ?? "") : "—",
                  ])}
                />
              </Box>
            </Collapsible>
          </Box>
        )}

        {product.geo_questions.length > 0 && (
          <Box>
            <Button variant="plain" onClick={() => toggle("geo")}>
              {`${t(locale, "marketAnalysisGeoQuestions")} (${product.geo_questions.length})`}
            </Button>
            <Collapsible id={`geo-${product.product_id}`} open={openSection === "geo"}>
              <Box paddingBlockStart="200">
                <DataTable
                  columnContentTypes={["text", "text", "text"]}
                  headings={[
                    "Question",
                    locale === "fr" ? "Angle de réponse" : "Answer angle",
                    locale === "fr" ? "Type de bloc" : "Block type",
                  ]}
                  rows={product.geo_questions.map((q) => [q.question, q.answer_angle, q.content_block_type])}
                />
              </Box>
            </Collapsible>
          </Box>
        )}

        {(pack.proposed_meta_title || pack.proposed_meta_description ||
          pack.proposed_product_description || pack.proposed_faq.length > 0 ||
          pack.proposed_blog_title) && (
          <Box>
            <Button variant="plain" onClick={() => toggle("proposals")}>
              {t(locale, "marketAnalysisProposals")}
            </Button>
            <Collapsible id={`prop-${product.product_id}`} open={openSection === "proposals"}>
              <Box paddingBlockStart="200">
                <BlockStack gap="300">
                  {pack.proposed_meta_title && (
                    <BlockStack gap="100">
                      <Text as="h4" variant="headingXs">Meta title</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {locale === "fr" ? "Actuel" : "Current"} : {pack.current_meta_title}
                      </Text>
                      <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
                        <Text as="p" variant="bodySm">{pack.proposed_meta_title}</Text>
                      </Box>
                    </BlockStack>
                  )}
                  {pack.proposed_meta_description && (
                    <BlockStack gap="100">
                      <Text as="h4" variant="headingXs">Meta description</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {locale === "fr" ? "Actuelle" : "Current"} :{" "}
                        {pack.current_meta_description || (locale === "fr" ? "absente" : "missing")}
                      </Text>
                      <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
                        <Text as="p" variant="bodySm">{pack.proposed_meta_description}</Text>
                      </Box>
                    </BlockStack>
                  )}
                  {pack.proposed_product_description && (
                    <BlockStack gap="100">
                      <Text as="h4" variant="headingXs">
                        {t(locale, "contentTypeProductDescription")}
                      </Text>
                      <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
                        <Text as="p" variant="bodySm">{pack.proposed_product_description}</Text>
                      </Box>
                    </BlockStack>
                  )}
                  {pack.proposed_faq.length > 0 && (
                    <BlockStack gap="100">
                      <Text as="h4" variant="headingXs">FAQ</Text>
                      {pack.proposed_faq.map((item, i) => (
                        <Box key={i} padding="200" borderWidth="025" borderRadius="200" borderColor="border">
                          <BlockStack gap="100">
                            <Text as="p" variant="headingXs">{item.q}</Text>
                            <Text as="p" variant="bodySm">{item.a}</Text>
                          </BlockStack>
                        </Box>
                      ))}
                    </BlockStack>
                  )}
                  {pack.proposed_blog_title && (
                    <BlockStack gap="100">
                      <Text as="h4" variant="headingXs">
                        {locale === "fr" ? "Idée d'article de blog" : "Blog article idea"}
                      </Text>
                      <Text as="p" variant="bodySm"><strong>{pack.proposed_blog_title}</strong></Text>
                      {pack.proposed_blog_intro && (
                        <Text as="p" variant="bodySm" tone="subdued">{pack.proposed_blog_intro}</Text>
                      )}
                      {pack.proposed_blog_outline.length > 0 && (
                        <BlockStack gap="050">
                          {pack.proposed_blog_outline.map((line, i) => (
                            <Text key={i} as="p" variant="bodySm" tone="subdued">• {line}</Text>
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

        {pack.facts_missing.length > 0 && (
          <Box>
            <Button variant="plain" onClick={() => toggle("facts")}>
              {`${t(locale, "marketAnalysisFactsMissing")} (${pack.facts_missing.length})`}
            </Button>
            <Collapsible id={`facts-${product.product_id}`} open={openSection === "facts"}>
              <Box paddingBlockStart="100">
                <BlockStack gap="050">
                  {pack.facts_missing.map((f, i) => (
                    <Text key={i} as="p" variant="bodySm" tone="subdued">• {f}</Text>
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
  const { locale, latestJob, latestIdentification, gscConnected, ga4Connected } =
    useLoaderData<LoaderData>();

  // ── UI step: "identification" (step 1) or "analysis" (step 2) ────────────
  const [step, setStep] = useState<"identification" | "analysis">(
    latestJob ? "analysis" : "identification",
  );

  // ── Identification state ──────────────────────────────────────────────────
  const [identifyJobId, setIdentifyJobId] = useState<string | null>(null);
  const [identifyJob, setIdentifyJob] = useState<JobState | null>(null);
  const [identifyError, setIdentifyError] = useState<string | null>(null);

  // Labels editable by the merchant — initialised from persisted identification
  const [identifications, setIdentifications] = useState<Record<string, string>>(
    latestIdentification?.labels ?? {},
  );
  // Raw Shopify product titles — shown read-only alongside the editable label
  const [productTitles, setProductTitles] = useState<Record<string, string>>(
    latestIdentification?.product_titles ?? {},
  );

  // ── Analysis state ────────────────────────────────────────────────────────
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobState | null>(latestJob);
  const [pollError, setPollError] = useState<string | null>(null);

  // ── Edit mode (came from "Modifier l'identification") ─────────────────────
  const [editMode, setEditMode] = useState(false);

  // ── Full re-run confirmation modal ────────────────────────────────────────
  const [showRerunModal, setShowRerunModal] = useState(false);

  // ── Single-product analysis state ─────────────────────────────────────────
  const [singleProductJobId, setSingleProductJobId] = useState<string | null>(null);
  const [singleProductId, setSingleProductId] = useState<string | null>(null);
  const [singleProductJob, setSingleProductJob] = useState<JobState | null>(null);

  // ── Fetchers ──────────────────────────────────────────────────────────────
  type ActionData = { type: string; jobId?: string | null; job?: JobState | null; error?: string | null; productId?: string | null };
  const identifyFetcher = useFetcher<ActionData>();
  const pollIdentifyFetcher = useFetcher<ActionData>();
  const startFetcher = useFetcher<ActionData>();
  const pollFetcher = useFetcher<ActionData>();
  const singleFetcher = useFetcher<ActionData>();
  const pollSingleFetcher = useFetcher<ActionData>();

  // ── Auto-start identification on first visit (no labels, no prior analysis) ──
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (autoStartedRef.current) return;
    if (step === "identification" && Object.keys(identifications).length === 0) {
      autoStartedRef.current = true;
      const fd = new FormData();
      fd.set("intent", "startIdentify");
      identifyFetcher.submit(fd, { method: "post" });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Refs for polling loops (avoid stale closures) ─────────────────────────
  const identifyJobIdRef = useRef<string | null>(null);
  const identifyStatusRef = useRef<string | undefined>(identifyJob?.status);
  const pollIdentifyRef = useRef(pollIdentifyFetcher);
  identifyJobIdRef.current = identifyJobId;
  identifyStatusRef.current = identifyJob?.status;
  pollIdentifyRef.current = pollIdentifyFetcher;

  const jobIdRef = useRef<string | null>(null);
  const jobStatusRef = useRef<string | undefined>(job?.status);
  const pollFetcherRef = useRef(pollFetcher);
  jobIdRef.current = jobId;
  jobStatusRef.current = job?.status;
  pollFetcherRef.current = pollFetcher;

  const singleJobIdRef = useRef<string | null>(null);
  const singleJobStatusRef = useRef<string | undefined>(undefined);
  const singleProductIdRef = useRef<string | null>(null);
  const pollSingleFetcherRef = useRef(pollSingleFetcher);
  singleJobIdRef.current = singleProductJobId;
  singleJobStatusRef.current = singleProductJob?.status;
  singleProductIdRef.current = singleProductId;
  pollSingleFetcherRef.current = pollSingleFetcher;

  // ── Effects: capture action responses ────────────────────────────────────

  // Identification job started
  useEffect(() => {
    if (identifyFetcher.data?.type === "startIdentify") {
      if (identifyFetcher.data.jobId) {
        setIdentifyJobId(identifyFetcher.data.jobId);
        setIdentifyJob(null);
        setIdentifyError(null);
      } else if (identifyFetcher.data.error) {
        setIdentifyError(identifyFetcher.data.error);
      }
    }
  }, [identifyFetcher.data]);

  // Poll identification job
  useEffect(() => {
    if (pollIdentifyFetcher.data?.type === "pollIdentify") {
      if (pollIdentifyFetcher.data.job) {
        const j = pollIdentifyFetcher.data.job;
        setIdentifyJob(j);
        if (j.status === "completed" && j.labels) {
          setIdentifications(j.labels);
          if (j.product_titles) setProductTitles(j.product_titles as Record<string, string>);
        }
      }
      if (pollIdentifyFetcher.data.error) setIdentifyError(pollIdentifyFetcher.data.error);
    }
  }, [pollIdentifyFetcher.data]);

  // Analysis job started (from saveAndStart or start)
  useEffect(() => {
    if (startFetcher.data?.type === "start") {
      if (startFetcher.data.jobId) {
        setJobId(startFetcher.data.jobId);
        setJob(null);
        setPollError(null);
        setStep("analysis");
      }
    }
  }, [startFetcher.data]);

  // Poll analysis job
  useEffect(() => {
    if (pollFetcher.data?.type === "poll") {
      if (pollFetcher.data.job) setJob(pollFetcher.data.job);
      if (pollFetcher.data.error) setPollError(pollFetcher.data.error);
    }
  }, [pollFetcher.data]);

  // saveOnly — labels saved, go back to step 2
  useEffect(() => {
    if (startFetcher.data?.type === "saveOnly") {
      setStep("analysis");
      setEditMode(false);
    }
  }, [startFetcher.data]);

  // Single product analysis started
  useEffect(() => {
    if (singleFetcher.data?.type === "startSingle") {
      if (singleFetcher.data.jobId) {
        setSingleProductJobId(singleFetcher.data.jobId);
        setSingleProductJob(null);
      }
    }
  }, [singleFetcher.data]);

  // Poll single product analysis
  useEffect(() => {
    if (pollSingleFetcher.data?.type === "pollSingle") {
      const d = pollSingleFetcher.data;
      if (d.job) {
        setSingleProductJob(d.job);
        if (d.job.status === "completed" && d.job.products && d.job.products.length > 0) {
          const updated = d.job.products[0];
          setJob((prev) => {
            if (!prev) return prev;
            const idx = prev.products.findIndex((p) => p.product_id === updated.product_id);
            const newProducts =
              idx >= 0
                ? prev.products.map((p, i) => (i === idx ? updated : p))
                : [...prev.products, updated];
            return { ...prev, products: newProducts };
          });
          setSingleProductJobId(null);
          setSingleProductId(null);
          setSingleProductJob(null);
        }
        if (d.job.status === "failed") {
          setSingleProductJobId(null);
          setSingleProductId(null);
          setSingleProductJob(null);
        }
      }
    }
  }, [pollSingleFetcher.data]);

  // ── Polling loop: identification job ─────────────────────────────────────
  useEffect(() => {
    if (!identifyJobId) return;
    const poll = () => {
      const status = identifyStatusRef.current;
      if (status === "completed" || status === "failed") return;
      const fd = new FormData();
      fd.set("intent", "pollIdentify");
      fd.set("jobId", identifyJobIdRef.current!);
      pollIdentifyRef.current.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 3_000);
    return () => clearInterval(id);
  }, [identifyJobId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Polling loop: analysis job ────────────────────────────────────────────
  useEffect(() => {
    if (!jobId) return;
    const poll = () => {
      const status = jobStatusRef.current;
      if (status === "completed" || status === "failed") return;
      const fd = new FormData();
      fd.set("intent", "poll");
      fd.set("jobId", jobIdRef.current!);
      pollFetcherRef.current.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Polling loop: single-product analysis ─────────────────────────────────
  useEffect(() => {
    if (!singleProductJobId) return;
    const poll = () => {
      const status = singleJobStatusRef.current;
      if (status === "completed" || status === "failed") return;
      const fd = new FormData();
      fd.set("intent", "pollSingle");
      fd.set("jobId", singleJobIdRef.current!);
      fd.set("productId", singleProductIdRef.current || "");
      pollSingleFetcherRef.current.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
  }, [singleProductJobId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Derived state ─────────────────────────────────────────────────────────
  const isIdentifying =
    identifyFetcher.state !== "idle" ||
    (identifyJobId !== null &&
      identifyJob?.status !== "completed" &&
      identifyJob?.status !== "failed");

  const hasLabels =
    identifyJob?.status === "completed" ||
    Object.keys(identifications).length > 0;

  const isStarting = startFetcher.state !== "idle";
  const isRunning =
    jobId !== null &&
    job?.status !== "completed" &&
    job?.status !== "failed" &&
    !pollError;
  const isInProgress = isStarting || isRunning;

  const progressPct =
    job && job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0;

  const startError =
    startFetcher.data?.type === "start" ? (startFetcher.data.error ?? null) : null;
  const anyError = startError || pollError || (job?.status === "failed" ? job.error : null);

  const isSingleRunning =
    singleFetcher.state !== "idle" ||
    (singleProductJobId !== null &&
      singleProductJob?.status !== "completed" &&
      singleProductJob?.status !== "failed");

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleStartIdentify = () => {
    setIdentifyJobId(null);
    setIdentifyJob(null);
    setIdentifyError(null);
    const fd = new FormData();
    fd.set("intent", "startIdentify");
    identifyFetcher.submit(fd, { method: "post" });
  };

  const handleSaveAndStart = () => {
    const fd = new FormData();
    fd.set("intent", "saveAndStart");
    fd.set("identifications", JSON.stringify(identifications));
    startFetcher.submit(fd, { method: "post" });
  };

  const handleRerun = () => {
    setJobId(null);
    setJob(null);
    setPollError(null);
    const fd = new FormData();
    fd.set("intent", "start");
    startFetcher.submit(fd, { method: "post" });
  };

  const handleEditIdentification = () => {
    setStep("identification");
    setEditMode(true);
    setIdentifyJobId(null);
    setIdentifyJob(null);
  };

  const handleSaveOnly = () => {
    const fd = new FormData();
    fd.set("intent", "saveOnly");
    fd.set("identifications", JSON.stringify(identifications));
    startFetcher.submit(fd, { method: "post" });
  };

  const handleCancelEdit = () => {
    setStep("analysis");
    setEditMode(false);
  };

  const handleAnalyzeSingle = (productId: string) => {
    setSingleProductJobId(null);
    setSingleProductId(productId);
    setSingleProductJob(null);
    const fd = new FormData();
    fd.set("intent", "startSingle");
    fd.set("productId", productId);
    singleFetcher.submit(fd, { method: "post" });
  };

  // ── Render ────────────────────────────────────────────────────────────────
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

        {/* Data sources status */}
        <DataSourcesCard gscConnected={gscConnected} ga4Connected={ga4Connected} locale={locale} />

        {/* ── STEP 1: Product identification ─────────────────────────────── */}
        {step === "identification" && (
          <Card>
            <BlockStack gap="400">
              <BlockStack gap="100">
                <Text as="h2" variant="headingMd">{t(locale, "marketAnalysisIdentificationTitle")}</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "marketAnalysisIdentificationSubtitle")}
                </Text>
              </BlockStack>

              {/* Generating spinner */}
              {isIdentifying && (
                <InlineStack gap="300" blockAlign="center">
                  <Spinner size="small" />
                  <Text as="p" variant="bodySm" tone="subdued">
                    {t(locale, "marketAnalysisGenerating")}
                  </Text>
                </InlineStack>
              )}

              {/* Error */}
              {identifyError && (
                <Banner tone="critical">
                  <Text as="p">{identifyError}</Text>
                </Banner>
              )}

              {/* Editable labels */}
              {hasLabels && !isIdentifying && (
                <BlockStack gap="300">
                  <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: "8px 16px", alignItems: "center" }}>
                    {/* Column headers */}
                    <Text as="p" variant="bodySm" tone="subdued" fontWeight="semibold">
                      {locale === "fr" ? "Titre boutique" : "Store title"}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued" fontWeight="semibold">
                      {locale === "fr" ? "Quel est le produit concrètement ?" : "What is the product concretely?"}
                    </Text>

                    {/* Product rows */}
                    {Object.entries(identifications).map(([productId, label]) => (
                      <>
                        <Text key={productId + "-title"} as="p" variant="bodyMd">
                          {productTitles[productId] || productId.slice(-8)}
                        </Text>
                        <TextField
                          key={productId + "-field"}
                          label=""
                          labelHidden
                          value={label}
                          onChange={(val) =>
                            setIdentifications((prev) => ({ ...prev, [productId]: val }))
                          }
                          placeholder={t(locale, "marketAnalysisLabelPlaceholder")}
                          autoComplete="off"
                        />
                      </>
                    ))}
                  </div>
                  {editMode ? (
                    /* Came from "Modifier l'identification" — save only, no new analysis */
                    <InlineStack gap="300">
                      <Button
                        variant="primary"
                        onClick={handleSaveOnly}
                        loading={isStarting}
                        disabled={isStarting}
                      >
                        {t(locale, "marketAnalysisSaveLabels")}
                      </Button>
                      <Button variant="plain" onClick={handleCancelEdit} disabled={isStarting}>
                        {t(locale, "marketAnalysisCancelEdit")}
                      </Button>
                    </InlineStack>
                  ) : (
                    /* First time — validate and launch analysis */
                    <Button
                      variant="primary"
                      onClick={handleSaveAndStart}
                      loading={isStarting}
                      disabled={isStarting}
                    >
                      {t(locale, "marketAnalysisValidateLabels")}
                    </Button>
                  )}
                </BlockStack>
              )}

              {/* No labels yet — generate button */}
              {!hasLabels && !isIdentifying && (
                <Button variant="primary" onClick={handleStartIdentify}>
                  {t(locale, "marketAnalysisGenerateLabels")}
                </Button>
              )}
            </BlockStack>
          </Card>
        )}

        {/* ── STEP 2: Full analysis ──────────────────────────────────────── */}
        {step === "analysis" && (
          <>
            {/* Action buttons (re-run / edit identification) */}
            {job?.status === "completed" && (
              <>
                <InlineStack gap="300" wrap>
                  <Button
                    variant="primary"
                    onClick={() => setShowRerunModal(true)}
                    loading={isInProgress}
                    disabled={isInProgress}
                  >
                    {t(locale, "marketAnalysisAnalyzeAll")}
                  </Button>
                  <Button variant="plain" onClick={handleEditIdentification} disabled={isInProgress}>
                    {t(locale, "marketAnalysisEditIdentification")}
                  </Button>
                </InlineStack>

                <Modal
                  open={showRerunModal}
                  onClose={() => setShowRerunModal(false)}
                  title={t(locale, "marketAnalysisAnalyzeAllTitle")}
                  primaryAction={{
                    content: locale === "fr" ? "Confirmer" : "Confirm",
                    onAction: () => { setShowRerunModal(false); handleRerun(); },
                  }}
                  secondaryActions={[{
                    content: locale === "fr" ? "Annuler" : "Cancel",
                    onAction: () => setShowRerunModal(false),
                  }]}
                >
                  <Modal.Section>
                    <Text as="p">{t(locale, "marketAnalysisAnalyzeAllWarning")}</Text>
                  </Modal.Section>
                </Modal>
              </>
            )}

            {/* Launch card */}
            <Card>
              <BlockStack gap="300">
                {!isInProgress && !job && (
                  <Text as="p" tone="subdued">{t(locale, "marketAnalysisEmpty")}</Text>
                )}

                {!job?.status || job.status === "failed" ? (
                  <Button
                    variant="primary"
                    onClick={handleRerun}
                    disabled={isInProgress}
                    loading={isInProgress}
                  >
                    {isInProgress
                      ? t(locale, "marketAnalysisRunning")
                      : t(locale, "marketAnalysisRun")}
                  </Button>
                ) : null}

                {isRunning && (
                  <BlockStack gap="100">
                    <Text as="p" variant="bodySm" tone="subdued">
                      {job && job.total > 0
                        ? progressLabel(locale, job.progress, job.total)
                        : t(locale, "marketAnalysisRunning")}
                    </Text>
                    <ProgressBar progress={progressPct} size="small" />
                  </BlockStack>
                )}
              </BlockStack>
            </Card>

            {/* Error */}
            {anyError && (
              <Banner tone="critical">
                <Text as="p">{anyError}</Text>
              </Banner>
            )}

            {/* Summary */}
            {job && job.analyzed_product_count > 0 && (
              <SummaryCard job={job} locale={locale} />
            )}

            {/* Product cards */}
            {job?.products?.map((product) => (
              <ProductCard
                key={product.product_id}
                product={product}
                locale={locale}
                isAnalyzing={singleProductId === product.product_id && isSingleRunning}
                onAnalyze={() => handleAnalyzeSingle(product.product_id)}
                analyzeDisabled={isSingleRunning || isInProgress}
              />
            ))}

            {/* Completion banner */}
            {job?.status === "completed" && (
              <Banner tone="success">
                <Text as="p">
                  {t(locale, "marketAnalysisCompleted")} —{" "}
                  {job.analyzed_product_count} {t(locale, "marketAnalysisProductCount")}
                </Text>
              </Banner>
            )}
          </>
        )}
      </BlockStack>
    </Page>
  );
}
