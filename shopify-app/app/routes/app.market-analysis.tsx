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
import { Component, useEffect, useRef, useState } from "react";
import type { ReactNode, ErrorInfo } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

// ── Types ─────────────────────────────────────────────────────────────────────

type KeywordSource = "gsc" | "ga4" | "trends" | "shopify" | "llm_estimated" | "dataforseo" | "google_ads" | "parent_estimated";
type DifficultySource = "free_estimated" | "dataforseo" | "google_ads";

interface SeoKeyword {
  query: string;
  intent_type: string;
  demand_score: number;
  competition_score: number;
  product_fit_score: number;
  reason: string;
  data_source?: KeywordSource;
  difficulty_source?: DifficultySource;
  gsc_impressions?: number | null;
  gsc_clicks?: number | null;
  gsc_position?: number | null;
  search_volume?: number | null;
  search_volume_estimated_ceiling?: number | null;
  estimated_from_parent?: string | null;
  cpc?: number | null;
  ads_competition?: number | null;
  notes?: string[];
  priority_score?: number;
  target_rank?: number;
  target_role?: "primary" | "secondary" | "supporting";
  serp_evidence?: boolean;
  paa_questions?: string[];
  serp_competitor_count?: number;
}

interface CompetitorSignal {
  domain: string;
  url?: string | null;
  matched_keyword?: string;
  detected_from: "manual" | "gsc" | "merchant_input" | "paid_provider";
  content_angle?: string;
  estimated_strength?: number;
  confidence?: "high" | "medium" | "low";
}

interface ProviderStatus {
  free?: boolean;
  dataforseo?: boolean;
  google_ads?: boolean;
}

interface GeoQuestion {
  question: string;
  answer_angle: string;
  content_block_type: string;
  confidence: string;
}

interface ContentQuality {
  publish_ready: boolean;
  issues: string[];
  advisories?: string[];
  covered_target_count?: number;
  target_count?: number;
  evidence_ledger?: { claim: string; facts: { key: string; source: string }[] }[];
  skipped_surfaces?: string[];
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
  content_quality?: ContentQuality;
  faq_sync?: {
    applied: boolean;
    error: string | null;
    entry_count: number;
    applied_at: string | null;
  } | null;
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
  phase?: "targeting" | "content";
  progress: number;
  total: number;
  products: ProductResult[];
  analyzed_at: string | null;
  active_product_count: number;
  analyzed_product_count: number;
  total_opportunity_count: number;
  sources_used: string[];
  provider_status?: ProviderStatus;
  competitor_signals?: CompetitorSignal[];
  error: string | null;
  // identification job fields
  labels?: Record<string, string>;
  product_titles?: Record<string, string>;
  product_count?: number;
}

interface ActiveProduct {
  id: string;
  title: string;
  handle: string;
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
  activeHandles: string[];
  /** Products currently active in the snapshot but absent from the latest analysis. */
  newProducts: ActiveProduct[];
  /** Product IDs present in the latest analysis but no longer active. */
  removedProductIds: string[];
}

// ── Revalidation guard — polling actions must not re-run the loader ───────────

export const shouldRevalidate: ShouldRevalidateFunction = (args) => {
  const intent = args.formData?.get("intent");
  if (intent === "poll" || intent === "pollIdentify" || intent === "pollSingle" || intent === "saveProposals" || intent === "removeProducts") {
    return false;
  }
  return args.defaultShouldRevalidate;
};

// ── Remix loader / action ─────────────────────────────────────────────────────

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);

  const fetchOpt = { accessToken: session.accessToken, method: "GET" as const };

  const [latestJobResp, identifyResp, gscResp, ga4Resp, activeProductsResp] = await Promise.allSettled([
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
    callBackendForShop(session.shop, `/api/shops/${session.shop}/products/active`, {
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

  let activeHandles: string[] = [];
  let activeProductsFull: ActiveProduct[] = [];
  if (activeProductsResp.status === "fulfilled" && activeProductsResp.value.ok) {
    try {
      const prods = (await activeProductsResp.value.json()) as { id: string; title: string; handle: string }[];
      activeHandles = prods.map((p) => p.handle);
      activeProductsFull = prods.map((p) => ({ id: String(p.id), title: p.title, handle: p.handle }));
    } catch { /* ignore */ }
  }

  // ── Delta detection ───────────────────────────────────────────────────────
  let newProducts: ActiveProduct[] = [];
  let removedProductIds: string[] = [];
  if (latestJob && activeProductsFull.length > 0) {
    const analyzedHandles = new Set((latestJob.products ?? []).map((p) => p.product_handle));
    newProducts = activeProductsFull.filter((p) => !analyzedHandles.has(p.handle));

    const activeHandleSet = new Set(activeHandles);
    removedProductIds = (latestJob.products ?? [])
      .filter((p) => !activeHandleSet.has(p.product_handle))
      .map((p) => p.product_id);
  }

  return json({ locale, shop: session.shop, latestJob, latestIdentification, gscConnected, ga4Connected, activeHandles, newProducts, removedProductIds });
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

  // ── Save edited proposals for one product ─────────────────────────────────
  if (intent === "saveProposals") {
    const productId = formData.get("productId") as string;
    const proposalsRaw = formData.get("proposals") as string;
    try {
      const proposals = JSON.parse(proposalsRaw);
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/proposals/${encodeURIComponent(productId)}`,
        {
          accessToken: session.accessToken,
          method: "PATCH",
          body: JSON.stringify(proposals),
          signal: AbortSignal.timeout(10_000),
        },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "saveProposals", error: `Erreur ${resp.status}: ${err}` });
      }
      return json({ type: "saveProposals", error: null });
    } catch (err) {
      return json({ type: "saveProposals", error: String(err) });
    }
  }

  // ── Auto-remove products no longer active in the store ───────────────────
  if (intent === "removeProducts") {
    const productIdsRaw = formData.get("productIds") as string;
    try {
      const product_ids = JSON.parse(productIdsRaw) as string[];
      await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/products/remove`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify({ product_ids }),
          signal: AbortSignal.timeout(10_000),
        },
      );
    } catch {
      // Non-blocking — silent best-effort cleanup
    }
    return json({ type: "removeProducts", error: null });
  }

  return json({ type: "unknown", error: "Unknown intent" });
};

// ── Error boundary (captures render crash + shows actual message) ─────────────

interface EBState { error: Error | null }
class RenderErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  state: EBState = { error: null };
  static getDerivedStateFromError(error: Error): EBState { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[MarketAnalysis render crash]", error, info.componentStack);
  }
  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <Banner tone="critical" title="Erreur d'affichage — détails pour le support">
        <Text as="p" variant="bodySm">{error.message}</Text>
        <Text as="p" variant="bodySm" tone="subdued">
          {error.stack?.split("\n").slice(0, 4).join(" | ")}
        </Text>
      </Banner>
    );
  }
}

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

const FR_STOP_WORDS = new Set([
  "de", "du", "la", "le", "les", "des", "pour", "avec", "sans", "sur", "par",
  "en", "au", "aux", "un", "une", "et", "ou", "à", "dans", "que", "qui", "ne",
  "pas", "se", "ce", "cet", "cette", "ces", "mon", "ma", "mes", "son", "sa",
  "ses", "nos", "vos", "leur", "leurs", "est", "sont", "être", "avoir",
]);

function contentWords(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[\s\-_/]+/)
    .map((w) => w.replace(/[^a-zàâäéèêëîïôùûüç]/g, ""))
    .filter((w) => w.length >= 3 && !FR_STOP_WORDS.has(w));
}

function keywordIsUsed(keyword: string, proposalWords: string[]): boolean {
  const kwWords = contentWords(keyword);
  if (kwWords.length === 0) return false;
  return kwWords.every((kw) =>
    proposalWords.some(
      (pw) =>
        pw === kw ||          // exact
        pw === kw + "s" ||    // singular keyword → plural proposal (chien→chiens)
        pw === kw + "x" ||    // singular keyword → plural-x proposal (eau→eaux)
        pw === kw + "es" ||   // singular keyword → plural-es proposal
        kw === pw + "s" ||    // plural keyword → singular proposal
        kw === pw + "x",      // plural-x keyword → singular proposal
    ),
  );
}

function keywordCoverage(keyword: string, pack: ContentTestPack): string[] {
  const fields: Array<[string, string]> = [
    ["Meta title", pack.proposed_meta_title],
    ["Meta description", pack.proposed_meta_description],
    ["Description", pack.proposed_product_description],
    ["FAQ", pack.proposed_faq.map((item) => `${item.q} ${item.a}`).join(" ")],
    ["GEO", pack.proposed_geo_answer_block],
    ["Blog", [pack.proposed_blog_title, pack.proposed_blog_intro, ...pack.proposed_blog_outline].join(" ")],
  ];
  return fields
    .filter(([, text]) => keywordIsUsed(keyword, contentWords(text)))
    .map(([label]) => label);
}

function qualityIssueLabel(issue: string, locale: Locale): string {
  const labels: Record<string, [string, string]> = {
    missing_primary_keyword_target: ["Aucune cible principale fiable", "No reliable primary target"],
    meta_title_missing_primary_target: ["Cible principale absente du meta title", "Primary target missing from meta title"],
    meta_description_missing_primary_target: ["Cible principale absente de la meta description", "Primary target missing from meta description"],
    description_missing_primary_target: ["Cible principale absente de la description", "Primary target missing from description"],
    description_has_insufficient_target_coverage: ["Description trop peu alignée aux cibles", "Description has insufficient target coverage"],
    faq_missing_available_paa_question: ["FAQ non alignée aux questions SERP disponibles", "FAQ does not cover available SERP questions"],
    missing_geo_answer_block: ["Bloc de réponse GEO manquant", "GEO answer block is missing"],
    missing_recommended_product_description: ["Description recommandée mais non générée", "Recommended description was not generated"],
    product_description_too_generic: ["Description trop courte ou générique pour être publiée automatiquement", "Description is too short or generic for automated publishing"],
    unjustified_product_description_surface: ["Description générée sans faits suffisants", "Description generated without enough supporting facts"],
    missing_recommended_faq: ["FAQ justifiée mais non générée", "Supported FAQ was not generated"],
    unjustified_faq_surface: ["FAQ générée sans question ou preuve suffisante", "FAQ generated without sufficient question or factual evidence"],
    unjustified_geo_answer_surface: ["Réponse GEO générée sans faits suffisants", "GEO answer generated without enough supporting facts"],
    missing_recommended_blog_support: ["Contenu support recommandé mais non généré", "Recommended support content was not generated"],
    unjustified_blog_surface: ["Article proposé sans intention informationnelle ou faits suffisants", "Blog suggested without sufficient informational intent or facts"],
    missing_claim_evidence_ledger: ["Aucune preuve structurée pour les affirmations générées", "No structured evidence for generated claims"],
    unverified_claim_reference: ["Une affirmation cite une preuve absente des données Shopify", "A claim references evidence absent from Shopify data"],
    missing_informative_confirmed_fact: ["Aucun fait produit informatif confirmé pour publier ce texte", "No informative confirmed product fact supports publishing this text"],
    unsupported_product_claims: ["La proposition contient une promesse produit non prouvée", "Proposal contains an unsupported product claim"],
    keyword_stuffing_risk: ["Répétition excessive de la cible principale", "Primary target appears too repetitively"],
    forbidden_promise_detected: ["La proposition reprend une formulation interdite", "Proposal contains a forbidden promise"],
    primary_target_cannibalization_risk: ["Une autre page prioritaire cible déjà cette requête", "Another higher-priority page already targets this query"],
    duplicate_existing_meta_title: ["Meta title identique à une autre fiche existante", "Meta title duplicates another existing page"],
    duplicate_existing_meta_description: ["Meta description identique à une autre fiche existante", "Meta description duplicates another existing page"],
    duplicate_proposed_meta_title: ["Meta title identique dans plusieurs propositions", "Meta title duplicates another proposal"],
    duplicate_proposed_meta_description: ["Meta description identique dans plusieurs propositions", "Meta description duplicates another proposal"],
    near_duplicate_product_description: ["Description trop proche d'une autre proposition", "Description is too similar to another proposal"],
    low_generation_confidence: ["Confiance de génération insuffisante", "Generation confidence is too low"],
    merchant_edit_requires_revalidation: ["Contenu modifié : nouvelle validation requise", "Edited content requires revalidation"],
  };
  const label = labels[issue];
  return label ? label[locale === "fr" ? 0 : 1] : issue;
}

const HIGHLIGHT_STYLE = {
  backgroundColor: "#fff4a3",
  padding: "0 2px",
  borderRadius: "2px",
  fontWeight: 600,
} as const;

function highlightKeywords(text: string, keywords: string[]): ReactNode {
  if (!keywords.length || !text) return <>{text}</>;
  const sorted = [...keywords].sort((a, b) => b.length - a.length);
  const escaped = sorted.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const regex = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = text.split(regex);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark key={i} style={HIGHLIGHT_STYLE}>{part}</mark>
        ) : (
          part
        ),
      )}
    </>
  );
}

function surfaceLabel(surface: string, locale: Locale): string {
  const labels: Record<string, [string, string]> = {
    product_description: ["description produit", "product description"],
    faq: ["FAQ", "FAQ"],
    geo_answer: ["réponse GEO", "GEO answer"],
    blog: ["article support", "support article"],
  };
  const label = labels[surface];
  return label ? label[locale === "fr" ? 0 : 1] : surface;
}

function qualityAdvisoryLabel(advisory: string, locale: Locale): string {
  const labels: Record<string, [string, string]> = {
    meta_title_length_outside_guideline: ["Longueur du meta title à surveiller", "Review meta title length"],
    meta_description_length_outside_guideline: ["Longueur de la meta description à surveiller", "Review meta description length"],
  };
  const label = labels[advisory];
  return label ? label[locale === "fr" ? 0 : 1] : advisory;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function DataSourcesCard({
  gscConnected,
  ga4Connected,
  providerStatus,
  locale,
}: {
  gscConnected: boolean;
  ga4Connected: boolean;
  providerStatus: ProviderStatus | undefined;
  locale: Locale;
}) {
  const dataforseoOn = providerStatus?.dataforseo === true;
  return (
    <Card>
      <BlockStack gap="200">
        <Text as="h3" variant="headingSm">
          {t(locale, "marketAnalysisDataUsed")}
        </Text>
        <InlineStack gap="400" wrap>
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="bodySm">Shopify</Text>
            <Badge tone="success">{t(locale, "marketAnalysisBadgeReal")}</Badge>
          </InlineStack>
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="bodySm">Google Search Console</Text>
            {gscConnected ? (
              <Badge tone="success">{t(locale, "marketAnalysisBadgeReal")}</Badge>
            ) : (
              <Button variant="plain" size="slim" url="/app/onboarding">
                {locale === "fr" ? "Se connecter" : "Connect"}
              </Button>
            )}
          </InlineStack>
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="bodySm">Google Analytics 4</Text>
            {ga4Connected ? (
              <Badge tone="success">{t(locale, "marketAnalysisBadgeReal")}</Badge>
            ) : (
              <Button variant="plain" size="slim" url="/app/ga4">
                {locale === "fr" ? "Se connecter" : "Connect"}
              </Button>
            )}
          </InlineStack>
          {providerStatus !== undefined && (
            <InlineStack gap="200" blockAlign="center">
              <Text as="span" variant="bodySm">DataForSEO</Text>
              <Badge tone={dataforseoOn ? "success" : "attention"}>
                {dataforseoOn ? t(locale, "marketAnalysisBadgeReal") : t(locale, "marketAnalysisBadgePaid")}
              </Badge>
            </InlineStack>
          )}
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

function FreeLimitsCard({ providerStatus, locale }: { providerStatus: ProviderStatus | undefined; locale: Locale }) {
  if (providerStatus?.dataforseo) return null;
  return (
    <Banner tone="info" title={t(locale, "marketAnalysisFreeLimits")}>
      <p>{t(locale, "marketAnalysisFreeLimitsBody")}</p>
    </Banner>
  );
}

function PaidRecommendedCard({
  providerStatus,
  locale,
}: {
  providerStatus: ProviderStatus | undefined;
  locale: Locale;
}) {
  // Hide once at least one paid provider is on
  if (providerStatus?.dataforseo) return null;
  return (
    <Banner tone="warning" title={t(locale, "marketAnalysisPaidRecommended")}>
      <p>{t(locale, "marketAnalysisPaidRecommendedBody")}</p>
    </Banner>
  );
}

function CompetitorsCard({
  signals,
  isLoading,
  locale,
}: {
  signals: CompetitorSignal[] | undefined;
  isLoading: boolean;
  locale: Locale;
}) {
  const items = signals ?? [];
  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack align="space-between" blockAlign="center">
          <Text as="h3" variant="headingSm">
            {t(locale, "marketAnalysisCompetitors")}
          </Text>
          <Button
            variant="plain"
            size="slim"
            url={localizedPath("/app/settings/competitors", locale)}
          >
            {t(locale, "marketAnalysisAddCompetitor")}
          </Button>
        </InlineStack>
        {items.length === 0 ? (
          <Text as="p" variant="bodySm" tone="subdued">
            {isLoading
              ? t(locale, "marketAnalysisCompetitorsLoading")
              : t(locale, "marketAnalysisCompetitorsNone")}
          </Text>
        ) : (
          <BlockStack gap="100">
            {items.map((c) => (
              <InlineStack key={c.domain} gap="200" blockAlign="center" wrap>
                <Text as="span" variant="bodySm"><strong>{c.domain}</strong></Text>
                <Badge tone={c.detected_from === "paid_provider" ? "success" : "info"}>
                  {c.detected_from === "manual"
                    ? (locale === "fr" ? "manuel" : "manual")
                    : c.detected_from === "paid_provider"
                    ? (locale === "fr" ? "SERP réel" : "real SERP")
                    : c.detected_from}
                </Badge>
                {c.content_angle && (
                  <Text as="span" variant="bodySm" tone="subdued">{c.content_angle}</Text>
                )}
              </InlineStack>
            ))}
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}

function KeywordSourceBadge({ source, locale }: { source: KeywordSource | undefined; locale: Locale }) {
  if (!source) return null;
  if (source === "gsc") return <Badge tone="success">{t(locale, "marketAnalysisSourceGsc")}</Badge>;
  if (source === "dataforseo") return <Badge tone="success">{t(locale, "marketAnalysisSourceDataforseo")}</Badge>;
  if (source === "ga4") return <Badge tone="success">{t(locale, "marketAnalysisSourceGa4")}</Badge>;
  if (source === "shopify") return <Badge tone="info">{t(locale, "marketAnalysisSourceShopify")}</Badge>;
  if (source === "parent_estimated") {
    return <Badge tone="info">{locale === "fr" ? "Estimé via parent" : "Parent-estimated"}</Badge>;
  }
  return <Badge tone="attention">{t(locale, "marketAnalysisSourceLlm")}</Badge>;
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
  const selectedTargets = product.seo_keywords
    .filter((keyword) => (keyword.target_rank ?? 999) <= 5)
    .slice(0, 5);
  const coverageTargets = selectedTargets.length > 0
    ? selectedTargets
    : product.seo_keywords.slice(0, 5);
  const kwQueries = coverageTargets.map((keyword) => keyword.query);

  // ── Proposal edit mode ──────────────────────────────────────────────────
  const [editMode, setEditMode] = useState(false);
  const [editedPack, setEditedPack] = useState<ContentTestPack>({ ...pack });
  const saveFetcher = useFetcher<{ type: string; error: string | null }>();
  const isSaving = saveFetcher.state !== "idle";

  // Re-sync editedPack when the parent delivers a new pack (e.g. polling completes
  // after the card already mounted with empty data). Skip while editing so we
  // never wipe out in-progress merchant edits.
  const packSignature = JSON.stringify(pack);
  useEffect(() => {
    if (!editMode) {
      setEditedPack({ ...pack });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packSignature]);

  useEffect(() => {
    if (saveFetcher.data?.type === "saveProposals" && !saveFetcher.data.error) {
      setEditedPack((previous) => ({
        ...previous,
        content_quality: {
          publish_ready: false,
          issues: ["merchant_edit_requires_revalidation"],
        },
      }));
      setEditMode(false);
    }
  }, [saveFetcher.data]);

  const updateProp = (key: keyof ContentTestPack, value: string) =>
    setEditedPack((prev) => ({ ...prev, [key]: value }));

  const updateFaq = (idx: number, field: "q" | "a", value: string) =>
    setEditedPack((prev) => {
      const faq = [...prev.proposed_faq];
      faq[idx] = { ...faq[idx], [field]: value };
      return { ...prev, proposed_faq: faq };
    });

  const addFaqItem = () =>
    setEditedPack((prev) => ({
      ...prev,
      proposed_faq: [...prev.proposed_faq, { q: "", a: "" }],
    }));

  const removeFaqItem = (idx: number) =>
    setEditedPack((prev) => ({
      ...prev,
      proposed_faq: prev.proposed_faq.filter((_, i) => i !== idx),
    }));

  const handleSaveProposals = () => {
    const proposals = {
      proposed_meta_title: editedPack.proposed_meta_title,
      proposed_meta_description: editedPack.proposed_meta_description,
      proposed_product_description: editedPack.proposed_product_description,
      proposed_faq: editedPack.proposed_faq,
      proposed_blog_title: editedPack.proposed_blog_title,
      proposed_blog_intro: editedPack.proposed_blog_intro,
      proposed_blog_outline: editedPack.proposed_blog_outline,
    };
    saveFetcher.submit(
      { intent: "saveProposals", productId: product.product_id, proposals: JSON.stringify(proposals) },
      { method: "POST" },
    );
  };

  const coverageByKeyword = new Map(
    coverageTargets.map((keyword) => [
      keyword.query.toLowerCase(),
      keywordCoverage(keyword.query, editedPack),
    ]),
  );
  const usedKeywords = new Set(
    [...coverageByKeyword.entries()]
      .filter(([, fields]) => fields.length > 0)
      .map(([query]) => query),
  );

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack gap="200" align="space-between" wrap>
          <BlockStack gap="100">
            <Text as="h3" variant="headingSm">{product.product_title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">/{product.product_handle}</Text>
          </BlockStack>
          <InlineStack gap="200">
            <Badge tone={scoreTone(100 - product.opportunity_score)}>
              {`Potentiel SEO ${100 - product.opportunity_score}/100`}
            </Badge>
            {coverageTargets.length > 0 && (
              <Badge
                tone={
                  usedKeywords.size / coverageTargets.length >= 0.75
                    ? "success"
                    : usedKeywords.size / coverageTargets.length >= 0.5
                    ? "info"
                    : usedKeywords.size / coverageTargets.length >= 0.25
                    ? "warning"
                    : "critical"
                }
              >
                {locale === "fr"
                  ? `${usedKeywords.size}/${coverageTargets.length} cibles couvertes`
                  : `${usedKeywords.size}/${coverageTargets.length} targets covered`}
              </Badge>
            )}
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
            {locale === "fr" ? "Client cible" : "Target customer"} :{" "}
            {typeof product.target_customer === "string"
              ? product.target_customer
              : Object.values(product.target_customer as Record<string, string>).join(" — ")}
          </Text>
        )}

        {product.seo_keywords.length > 0 && (
          <Box>
            <Button variant="plain" onClick={() => toggle("keywords")}>
              {`${t(locale, "marketAnalysisSeoKeywords")} (${product.seo_keywords.length})`}
            </Button>
            <Collapsible id={`kw-${product.product_id}`} open={openSection === "keywords"}>
              <Box paddingBlockStart="200">
                <BlockStack gap="200">
                  {product.seo_keywords.map((k, idx) => (
                    <Box
                      key={`${k.query}-${idx}`}
                      padding="200"
                      borderWidth="025"
                      borderRadius="200"
                      borderColor="border"
                      background="bg-surface-secondary"
                    >
                      <BlockStack gap="100">
                        <InlineStack gap="200" align="space-between" wrap blockAlign="center">
                          <InlineStack gap="200" blockAlign="center" wrap>
                            <Text as="span" variant="bodyMd"><strong>{k.query}</strong></Text>
                            <Badge>{k.intent_type || "—"}</Badge>
                            {(k.target_role === "primary" || k.target_role === "secondary") && (
                              <Badge tone={k.target_role === "primary" ? "success" : "info"}>
                                {k.target_role === "primary"
                                  ? (locale === "fr" ? "Cible principale" : "Primary target")
                                  : (locale === "fr" ? "Cible secondaire" : "Secondary target")}
                              </Badge>
                            )}
                            <KeywordSourceBadge source={k.data_source} locale={locale} />
                            {usedKeywords.has(k.query.toLowerCase()) && (
                              <Badge tone="success">
                                {locale === "fr" ? "Couvert" : "Covered"}
                              </Badge>
                            )}
                          </InlineStack>
                          <InlineStack gap="100">
                            {k.priority_score != null && (
                              <Badge tone={scoreTone(k.priority_score)}>
                                {`${locale === "fr" ? "Priorité" : "Priority"} ${k.priority_score}`}
                              </Badge>
                            )}
                            <Badge
                              tone={
                                k.data_source === "llm_estimated" || k.data_source === "shopify" || k.data_source === "parent_estimated"
                                  ? undefined
                                  : scoreTone(k.demand_score)
                              }
                            >
                              {`${locale === "fr" ? "Demande" : "Demand"} ${k.demand_score}${
                                k.data_source === "llm_estimated" || k.data_source === "shopify" || k.data_source === "parent_estimated"
                                  ? " (estimé)"
                                  : ""
                              }`}
                            </Badge>
                            <Badge tone="info">
                              {`${t(locale, "marketAnalysisDifficulty")} ${k.competition_score}`}
                            </Badge>
                            <Badge tone={scoreTone(k.product_fit_score)}>
                              {`Fit ${k.product_fit_score}`}
                            </Badge>
                          </InlineStack>
                        </InlineStack>
                        <InlineStack gap="300" wrap>
                          <Text as="span" variant="bodySm" tone="subdued">
                            {t(locale, "marketAnalysisVolume")}:{" "}
                            {k.search_volume != null ? (
                              <strong>{k.search_volume.toLocaleString()}</strong>
                            ) : k.search_volume_estimated_ceiling != null && k.estimated_from_parent ? (
                              <>
                                <strong>≤ {k.search_volume_estimated_ceiling.toLocaleString()}</strong>
                                <em>
                                  {" "}
                                  ({locale === "fr" ? "estimé via" : "estimated via"} « {k.estimated_from_parent} »)
                                </em>
                              </>
                            ) : (
                              <em>{t(locale, "marketAnalysisPaidUnavailable")}</em>
                            )}
                          </Text>
                          <Text as="span" variant="bodySm" tone="subdued">
                            {t(locale, "marketAnalysisCpc")}:{" "}
                            {k.cpc != null ? <strong>{k.cpc}€</strong> : <em>—</em>}
                          </Text>
                          <Text as="span" variant="bodySm" tone="subdued">
                            {t(locale, "marketAnalysisAdsCompetition")}:{" "}
                            {k.ads_competition != null ? <strong>{k.ads_competition}</strong> : <em>—</em>}
                          </Text>
                          {k.gsc_impressions != null && (
                            <Text as="span" variant="bodySm" tone="subdued">
                              GSC: <strong>{k.gsc_impressions}</strong> impr., pos {k.gsc_position}
                            </Text>
                          )}
                          {k.serp_evidence && (
                            <Text as="span" variant="bodySm" tone="subdued">
                              {locale === "fr" ? "SERP/PAA vérifié" : "SERP/PAA checked"}
                            </Text>
                          )}
                        </InlineStack>
                        {(coverageByKeyword.get(k.query.toLowerCase())?.length ?? 0) > 0 && (
                          <Text as="p" variant="bodySm" tone="subdued">
                            {locale === "fr" ? "Présent dans : " : "Present in: "}
                            {coverageByKeyword.get(k.query.toLowerCase())!.join(", ")}
                          </Text>
                        )}
                        {k.notes && k.notes.length > 0 && (
                          <Text as="p" variant="bodySm" tone="subdued">
                            {k.notes.join(" · ")}
                          </Text>
                        )}
                      </BlockStack>
                    </Box>
                  ))}
                </BlockStack>
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

        {(editedPack.proposed_meta_title || editedPack.proposed_meta_description ||
          editedPack.proposed_product_description || editedPack.proposed_faq.length > 0 ||
          editedPack.proposed_blog_title) && (
          <Box>
            <Button variant="plain" onClick={() => toggle("proposals")}>
              {t(locale, "marketAnalysisProposals")}
            </Button>
            <Collapsible id={`prop-${product.product_id}`} open={openSection === "proposals"}>
              <Box paddingBlockStart="200">
                <BlockStack gap="300">
                  {/* ── Edit / save controls ── */}
                  <InlineStack gap="200" align="end">
                    {editMode ? (
                      <>
                        <Button
                          size="slim"
                          loading={isSaving}
                          onClick={handleSaveProposals}
                        >
                          {locale === "fr" ? "Sauvegarder" : "Save"}
                        </Button>
                        <Button size="slim" variant="plain" onClick={() => { setEditMode(false); setEditedPack({ ...pack }); }}>
                          {locale === "fr" ? "Annuler" : "Cancel"}
                        </Button>
                      </>
                    ) : (
                      <Button size="slim" variant="plain" onClick={() => setEditMode(true)}>
                        {locale === "fr" ? "Modifier" : "Edit"}
                      </Button>
                    )}
                  </InlineStack>

                  {saveFetcher.data?.type === "saveProposals" && saveFetcher.data.error && (
                    <Banner tone="critical">
                      <Text as="p" variant="bodySm">{saveFetcher.data.error}</Text>
                    </Banner>
                  )}

                  {!editMode && editedPack.content_quality && (
                    editedPack.content_quality.publish_ready ? (
                      <Banner tone="success">
                        <BlockStack gap="050">
                          <Text as="p" variant="bodySm">
                            {locale === "fr"
                              ? "Validation SEO/GEO réussie : cette proposition est éligible à une publication automatisée."
                              : "SEO/GEO validation passed: this proposal is eligible for automated publishing."}
                          </Text>
                          {(editedPack.content_quality.evidence_ledger?.length ?? 0) > 0 && (
                            <Text as="p" variant="bodySm">
                              {locale === "fr"
                                ? `${editedPack.content_quality.evidence_ledger?.length} affirmation(s) reliée(s) à des faits Shopify confirmés.`
                                : `${editedPack.content_quality.evidence_ledger?.length} claim(s) linked to confirmed Shopify facts.`}
                            </Text>
                          )}
                        </BlockStack>
                      </Banner>
                    ) : (
                      <Banner tone="warning">
                        <BlockStack gap="050">
                          <Text as="p" variant="bodySm">
                            {locale === "fr"
                              ? "À corriger avant toute publication automatique :"
                              : "Fix before any automated publishing:"}
                          </Text>
                          {editedPack.content_quality.issues.map((issue) => (
                            <Text key={issue} as="p" variant="bodySm">
                              • {qualityIssueLabel(issue, locale)}
                            </Text>
                          ))}
                        </BlockStack>
                      </Banner>
                    )
                  )}
                  {!editMode && (editedPack.content_quality?.skipped_surfaces?.length ?? 0) > 0 && (
                    <Text as="p" variant="bodySm" tone="subdued">
                      {locale === "fr" ? "Non généré automatiquement faute de preuve ou d'intention suffisante : " : "Not generated automatically because supporting evidence or intent is insufficient: "}
                      {editedPack.content_quality?.skipped_surfaces?.map((surface) => surfaceLabel(surface, locale)).join(", ")}.
                    </Text>
                  )}
                  {!editMode && (editedPack.content_quality?.advisories?.length ?? 0) > 0 && (
                    <Text as="p" variant="bodySm" tone="subdued">
                      {locale === "fr" ? "À surveiller : " : "Review: "}
                      {editedPack.content_quality?.advisories?.map((advisory) => qualityAdvisoryLabel(advisory, locale)).join(", ")}.
                    </Text>
                  )}

                  {/* ── Meta title ── */}
                  {editedPack.proposed_meta_title && (
                    <BlockStack gap="100">
                      <Text as="h4" variant="headingXs">Meta title</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {locale === "fr" ? "Actuel" : "Current"} : {pack.current_meta_title}
                      </Text>
                      {editMode ? (
                        <TextField
                          label=""
                          labelHidden
                          value={editedPack.proposed_meta_title}
                          onChange={(v) => updateProp("proposed_meta_title", v)}
                          autoComplete="off"
                          maxLength={70}
                          showCharacterCount
                        />
                      ) : (
                        <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
                          <Text as="p" variant="bodySm">{highlightKeywords(editedPack.proposed_meta_title, kwQueries)}</Text>
                        </Box>
                      )}
                    </BlockStack>
                  )}

                  {/* ── Meta description ── */}
                  {editedPack.proposed_meta_description && (
                    <BlockStack gap="100">
                      <Text as="h4" variant="headingXs">Meta description</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {locale === "fr" ? "Actuelle" : "Current"} :{" "}
                        {pack.current_meta_description || (locale === "fr" ? "absente" : "missing")}
                      </Text>
                      {editMode ? (
                        <TextField
                          label=""
                          labelHidden
                          value={editedPack.proposed_meta_description}
                          onChange={(v) => updateProp("proposed_meta_description", v)}
                          multiline={3}
                          autoComplete="off"
                          maxLength={160}
                          showCharacterCount
                        />
                      ) : (
                        <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
                          <Text as="p" variant="bodySm">{highlightKeywords(editedPack.proposed_meta_description, kwQueries)}</Text>
                        </Box>
                      )}
                    </BlockStack>
                  )}

                  {/* ── Product description ── */}
                  {editedPack.proposed_product_description && (
                    <BlockStack gap="100">
                      <Text as="h4" variant="headingXs">
                        {t(locale, "contentTypeProductDescription")}
                      </Text>
                      {editMode ? (
                        <TextField
                          label=""
                          labelHidden
                          value={editedPack.proposed_product_description}
                          onChange={(v) => updateProp("proposed_product_description", v)}
                          multiline={5}
                          autoComplete="off"
                        />
                      ) : (
                        <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
                          <Text as="p" variant="bodySm">{highlightKeywords(editedPack.proposed_product_description, kwQueries)}</Text>
                        </Box>
                      )}
                    </BlockStack>
                  )}

                  {/* ── FAQ ── */}
                  {(editedPack.proposed_faq.length > 0 || editMode) && (
                    <BlockStack gap="100">
                      <InlineStack gap="200" blockAlign="center">
                        <Text as="h4" variant="headingXs">FAQ</Text>
                        {editedPack.faq_sync?.applied && editedPack.faq_sync.applied_at && (
                          <Badge tone="success" size="small">
                            {locale === "fr"
                              ? `Synchronisée sur Shopify le ${new Date(editedPack.faq_sync.applied_at).toLocaleDateString("fr-FR")}`
                              : `Synced to Shopify on ${new Date(editedPack.faq_sync.applied_at).toLocaleDateString("en-US")}`}
                          </Badge>
                        )}
                        {editedPack.faq_sync?.applied === false && editedPack.faq_sync.error && (
                          <Badge tone="attention" size="small">
                            {locale === "fr" ? "Synchro Shopify en attente" : "Shopify sync pending"}
                          </Badge>
                        )}
                      </InlineStack>
                      {editedPack.proposed_faq.map((item, i) => (
                        <Box key={i} padding="200" borderWidth="025" borderRadius="200" borderColor="border">
                          <BlockStack gap="150">
                            {editMode ? (
                              <>
                                <InlineStack gap="200" align="space-between" blockAlign="start">
                                  <Box width="100%">
                                    <TextField
                                      label={locale === "fr" ? "Question" : "Question"}
                                      value={item.q}
                                      onChange={(v) => updateFaq(i, "q", v)}
                                      autoComplete="off"
                                    />
                                  </Box>
                                  <Button
                                    size="slim"
                                    variant="plain"
                                    tone="critical"
                                    onClick={() => removeFaqItem(i)}
                                  >
                                    ×
                                  </Button>
                                </InlineStack>
                                <TextField
                                  label={locale === "fr" ? "Réponse" : "Answer"}
                                  value={item.a}
                                  onChange={(v) => updateFaq(i, "a", v)}
                                  multiline={3}
                                  autoComplete="off"
                                />
                              </>
                            ) : (
                              <>
                                <Text as="p" variant="headingXs">{highlightKeywords(item.q, kwQueries)}</Text>
                                <Text as="p" variant="bodySm">{highlightKeywords(item.a, kwQueries)}</Text>
                              </>
                            )}
                          </BlockStack>
                        </Box>
                      ))}
                      {editMode && (
                        <Button size="slim" variant="plain" onClick={addFaqItem}>
                          {locale === "fr" ? "+ Ajouter une question" : "+ Add question"}
                        </Button>
                      )}
                    </BlockStack>
                  )}

                  {/* ── Blog ── */}
                  {editedPack.proposed_blog_title && (
                    <BlockStack gap="100">
                      <Text as="h4" variant="headingXs">
                        {locale === "fr" ? "Idée d'article de blog" : "Blog article idea"}
                      </Text>
                      {editMode ? (
                        <BlockStack gap="200">
                          <TextField
                            label={locale === "fr" ? "Titre" : "Title"}
                            value={editedPack.proposed_blog_title}
                            onChange={(v) => updateProp("proposed_blog_title", v)}
                            autoComplete="off"
                          />
                          <TextField
                            label="Intro"
                            value={editedPack.proposed_blog_intro}
                            onChange={(v) => updateProp("proposed_blog_intro", v)}
                            multiline={3}
                            autoComplete="off"
                          />
                          <TextField
                            label={locale === "fr" ? "Plan (une section par ligne)" : "Outline (one section per line)"}
                            value={editedPack.proposed_blog_outline.join("\n")}
                            onChange={(v) =>
                              setEditedPack((prev) => ({
                                ...prev,
                                proposed_blog_outline: v.split("\n"),
                              }))
                            }
                            multiline={4}
                            autoComplete="off"
                          />
                        </BlockStack>
                      ) : (
                        <>
                          <Text as="p" variant="bodySm"><strong>{highlightKeywords(editedPack.proposed_blog_title, kwQueries)}</strong></Text>
                          {editedPack.proposed_blog_intro && (
                            <Text as="p" variant="bodySm" tone="subdued">{highlightKeywords(editedPack.proposed_blog_intro, kwQueries)}</Text>
                          )}
                          {editedPack.proposed_blog_outline.length > 0 && (
                            <BlockStack gap="050">
                              {editedPack.proposed_blog_outline.map((line, i) => (
                                <Text key={i} as="p" variant="bodySm" tone="subdued">• {highlightKeywords(line, kwQueries)}</Text>
                              ))}
                            </BlockStack>
                          )}
                        </>
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

function NewProductsBanner({
  products,
  locale,
  onAnalyze,
  isAnalyzing,
}: {
  products: ActiveProduct[];
  locale: Locale;
  onAnalyze: (productId: string) => void;
  isAnalyzing: boolean;
}) {
  if (products.length === 0) return null;
  const label = t(locale, "marketAnalysisNewProductsBanner").replace("{count}", String(products.length));
  return (
    <Banner tone="info">
      <BlockStack gap="200">
        <Text as="p" variant="bodySm">{label}</Text>
        <BlockStack gap="100">
          {products.map((p) => (
            <InlineStack key={p.id} gap="300" blockAlign="center">
              <Text as="span" variant="bodySm"><strong>{p.title}</strong></Text>
              <Button
                size="slim"
                onClick={() => onAnalyze(p.id)}
                disabled={isAnalyzing}
                loading={isAnalyzing}
              >
                {t(locale, "marketAnalysisNewProductsAnalyze")}
              </Button>
            </InlineStack>
          ))}
        </BlockStack>
      </BlockStack>
    </Banner>
  );
}

// ── Page component ────────────────────────────────────────────────────────────

export default function MarketAnalysisPage() {
  const { locale, latestJob, latestIdentification, gscConnected, ga4Connected, activeHandles, newProducts, removedProductIds } =
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

  // ── Active-only filter ────────────────────────────────────────────────────
  const [showInactive, setShowInactive] = useState(false);

  // ── Delta banner: track analyzed new products to hide their banner entry ──
  const [analyzedNewIds, setAnalyzedNewIds] = useState<Set<string>>(new Set());

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
  const removeFetcher = useFetcher<ActionData>();

  // ── Auto-remove products that are no longer active in the store ───────────
  const autoRemovedRef = useRef(false);
  useEffect(() => {
    if (autoRemovedRef.current || removedProductIds.length === 0) return;
    autoRemovedRef.current = true;
    const fd = new FormData();
    fd.set("intent", "removeProducts");
    fd.set("productIds", JSON.stringify(removedProductIds));
    removeFetcher.submit(fd, { method: "post" });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // When auto-remove completes, also filter them out of the live job state
  useEffect(() => {
    if (removeFetcher.data?.type === "removeProducts" && removedProductIds.length > 0) {
      const removedSet = new Set(removedProductIds);
      setJob((prev) =>
        prev ? { ...prev, products: prev.products.filter((p) => !removedSet.has(p.product_id)) } : prev,
      );
    }
  }, [removeFetcher.data]); // eslint-disable-line react-hooks/exhaustive-deps

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
            if (!prev) {
              // No prior job — create one so the new product card can be shown
              return { ...d.job!, status: "completed", products: [updated] };
            }
            const idx = prev.products.findIndex((p) => p.product_id === updated.product_id);
            const updatedProducts =
              idx >= 0
                ? prev.products.map((p, i) => (i === idx ? updated : p))
                : [...prev.products, updated];
            return { ...prev, products: updatedProducts };
          });
          // Mark as analyzed so the delta banner hides this product
          setAnalyzedNewIds((prev) => new Set([...prev, updated.product_id]));
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

  const progressPct = (() => {
    if (!job || job.total <= 0) return 0;
    const frac = job.progress / job.total;
    // pass1 fills 0→50%, pass2 fills 50→100% so the bar advances continuously
    if (job.phase === "targeting") return Math.round(frac * 50);
    if (job.phase === "content") return Math.round(50 + frac * 50);
    return Math.round(frac * 100);
  })();

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
        <DataSourcesCard
          gscConnected={gscConnected}
          ga4Connected={ga4Connected}
          providerStatus={job?.provider_status ?? latestJob?.provider_status}
          locale={locale}
        />

        {/* Free-mode limits + paid recommendations — only when provider status is known */}
        {(() => {
          const ps = job?.provider_status ?? latestJob?.provider_status;
          return ps !== undefined && step === "analysis" ? (
            <>
              <FreeLimitsCard providerStatus={ps} locale={locale} />
              <PaidRecommendedCard providerStatus={ps} locale={locale} />
            </>
          ) : null;
        })()}
        {(job ?? latestJob) && (
          <CompetitorsCard
            signals={job?.competitor_signals?.length ? job.competitor_signals : latestJob?.competitor_signals}
            isLoading={job?.status === "running" || job?.status === "pending"}
            locale={locale}
          />
        )}

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
            {/* Rerun confirmation modal — always mounted so Polaris can animate close
                before the completed-job block disappears from the tree */}
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

            {/* Action buttons (re-run / edit identification) */}
            {job?.status === "completed" && (
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
            )}

            {/* Delta banner — new products not yet analysed */}
            {(() => {
              const pendingNew = newProducts.filter(
                (p) => !analyzedNewIds.has(p.id) && !(job?.products ?? []).some((jp) => jp.product_id === p.id),
              );
              return pendingNew.length > 0 ? (
                <NewProductsBanner
                  products={pendingNew}
                  locale={locale}
                  onAnalyze={(id) => {
                    setStep("analysis");
                    handleAnalyzeSingle(id);
                  }}
                  isAnalyzing={isSingleRunning}
                />
              ) : null;
            })()}

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
                    {job?.phase && (
                      <Text as="p" variant="bodySm" tone="subdued">
                        {job.phase === "targeting"
                          ? t(locale, "marketAnalysisPhaseTargeting")
                          : t(locale, "marketAnalysisPhaseContent")}
                      </Text>
                    )}
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

            {/* Product cards — filtered to active by default */}
            {(() => {
              const allProducts = job?.products ?? [];
              const activeSet = new Set(activeHandles);
              const hasFilter = activeHandles.length > 0;
              const visibleProducts =
                !hasFilter || showInactive
                  ? allProducts
                  : allProducts.filter((p) => activeSet.has(p.product_handle));
              const hiddenCount = allProducts.length - visibleProducts.length;

              return (
                <>
                  <RenderErrorBoundary>
                    {visibleProducts.map((product) => (
                      <ProductCard
                        key={product.product_id}
                        product={product}
                        locale={locale}
                        isAnalyzing={singleProductId === product.product_id && isSingleRunning}
                        onAnalyze={() => handleAnalyzeSingle(product.product_id)}
                        analyzeDisabled={isSingleRunning || isInProgress}
                      />
                    ))}
                  </RenderErrorBoundary>
                  {hiddenCount > 0 && (
                    <Button variant="plain" onClick={() => setShowInactive((v) => !v)}>
                      {showInactive
                        ? (locale === "fr" ? "Masquer les produits inactifs" : "Hide inactive products")
                        : (locale === "fr"
                            ? `Voir aussi les ${hiddenCount} produits inactifs`
                            : `Show ${hiddenCount} inactive product${hiddenCount > 1 ? "s" : ""}`)}
                    </Button>
                  )}
                </>
              );
            })()}

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
