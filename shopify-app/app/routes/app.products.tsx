import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useFetcher, useRevalidator } from "@remix-run/react";
import type { ShouldRevalidateFunction } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  Collapsible,
  Icon,
  InlineGrid,
  InlineStack,
  Modal,
  Page,
  Spinner,
  Text,
  TextField,
  Thumbnail,
} from "@shopify/polaris";
import { PlanBadge } from "../components/PlanBadge";
import { AlertTriangleIcon, CheckIcon, ProductIcon as ProductAddIcon } from "@shopify/polaris-icons";
import { Component, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode, ErrorInfo } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, loaderPhrases, localizedPath, t, type Locale } from "../lib/i18n";
import { ResearchConsole, type ResearchJobEvent } from "../components/ResearchConsole";
import { QuotaPill } from "../components/UsageMeter";
import { buildAnalysisCounters, buildAnalysisSteps } from "../lib/researchSteps";
import { ProductContentProposals, type FieldKey } from "../components/ProductContentProposals";
import { ProductCard } from "../components/ProductCard";
import { handleProductCardIntent } from "../lib/productCardActions.server";

// ── Types ─────────────────────────────────────────────────────────────────────

type KeywordSource = "gsc" | "ga4" | "trends" | "shopify" | "llm_estimated" | "llm_proposed" | "google_suggest" | "dataforseo" | "google_ads" | "parent_estimated";
type DifficultySource = "free_estimated" | "dataforseo" | "google_ads";
type BusinessProfileContextStatus = "current" | "stale" | "unknown" | "missing_profile";

type IntentTypeSource = "serp_classified" | "llm_guessed" | "unclassified";
type SerpFeatureTarget = "paa" | "featured_snippet" | "ai_overview";

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
  intent_type_source?: IntentTypeSource;
  serp_feature_targets?: SerpFeatureTarget[];
}

interface KeywordCluster {
  cluster_id: string;
  head_keyword: string;
  member_queries: string[];
}

interface CannibalizationAlertProduct {
  product_id: string;
  product_title: string;
  product_url: string;
  primary_keyword: string;
  gsc_impressions: number;
  opportunity_score: number;
}

interface CannibalizationAlert {
  cluster_head: string;
  cluster_key: string[];
  product_ids: string[];
  products: CannibalizationAlertProduct[];
  winner_suggested: string;
  action: "reorient_secondary";
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
  trends?: { status?: string; detail?: string; count?: number };
}

interface BusinessProfileContextMeta {
  hash?: string | null;
  status?: string;
  field_names?: string[];
  brand_name?: string | null;
  generated_at?: string | null;
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

interface GuardrailReflectionQuestion {
  key: string;
  question: string;
  score: number;
  status: "pass" | "needs_review" | "blocked";
  evidence: string[];
  recommendation: string;
}

interface GuardrailReflectionAttempt {
  attempt: number;
  score: number;
  status: "pass" | "needs_retry" | "blocked";
  questions: GuardrailReflectionQuestion[];
  quality_issues?: string[];
}

interface ContentGuardrailReflection {
  enabled: boolean;
  threshold: number;
  max_retries: number;
  retry_count: number;
  final_score: number;
  final_status: "pass" | "needs_retry" | "blocked";
  questions: { key: string; question: string }[];
  attempts: GuardrailReflectionAttempt[];
}

interface EnrichmentQuestion {
  key: string;
  question: string;
  placeholder: string;
  why_it_matters: string;
  target_keyword: string;
  unlocks_surfaces: string[];
}

interface ConfirmedFact {
  key: string;
  label: string;
  value: string | string[];
  source: string;
  confidence: string;
}

interface EeatSignal {
  kind: string;
  label: string;
  source: string;
  confidence: string;
}

interface ComparisonTableRow {
  ["critère"]?: string;
  criterion?: string;
  valeur?: string;
  value?: string;
}

interface SchemaJsonLd {
  product?: Record<string, unknown>;
  faq?: Record<string, unknown>;
  breadcrumb?: Record<string, unknown>;
}

interface InternalLinkSuggestion {
  target_url: string;
  target_title: string;
  anchors: string[];
  reason: "sibling_product" | "collection_parent" | "informational_support";
  confidence: "high" | "medium" | "low";
}

interface BlogGapSuggestion {
  cluster_head: string;
  suggested_title: string;
  reason: string;
}

type ImprovementTagStatus = "positive" | "neutral" | "negative" | "forced";

interface ImprovementTag {
  tag_id: string;
  label: string;
  tag_type: "keyword" | "analysis_axis" | "content_axis" | "risk" | "merchant";
  status: ImprovementTagStatus;
  score: number;
  source: string;
  locked_by_merchant: boolean;
  reason?: string;
}

interface ImprovementElement {
  key: string;
  label: string;
  improved: boolean;
  status: "improved" | "not_improved";
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
  current_product_images?: { id: string; url: string; current_alt: string | null }[];
  proposed_image_alts?: { image_id: string; proposed_alt: string }[];
  proposed_faq: { q: string; a: string }[];
  proposed_geo_answer_block: string;
  proposed_geo_definition_block?: string;
  proposed_geo_quick_facts?: string[];
  proposed_geo_comparison_table?: ComparisonTableRow[];
  proposed_schema_jsonld?: SchemaJsonLd;
  recommended_internal_links?: InternalLinkSuggestion[];
  proposed_blog_title: string;
  proposed_blog_outline: string[];
  proposed_blog_intro: string;
  proposed_blog_ideas?: BlogIdea[];
  facts_used: string[];
  facts_missing: string[];
  confidence: string;
  confirmed_facts?: ConfirmedFact[];
  eeat_signals?: EeatSignal[];
  content_quality?: ContentQuality;
  enrichment_questions?: EnrichmentQuestion[];
  retired_question_keys?: string[];
  retired_questions?: EnrichmentQuestion[];
  completed_questions?: Array<{ key: string; question: string; why_it_matters: string; placeholder: string; is_retired: boolean; answer: string }>;
  content_guardrail_reflection?: ContentGuardrailReflection;
  /** Field key → ISO timestamp of the live Shopify apply ("Valider les propositions"). */
  applied_fields?: Record<string, string>;
  faq_sync?: {
    applied: boolean;
    error: string | null;
    entry_count: number;
    applied_at: string | null;
  } | null;
  schema_facts_sync?: {
    applied: boolean;
    error: string | null;
    entry_count: number;
    applied_at: string | null;
  } | null;
}

interface BlogIdea {
  title: string;
  target_keyword: string;
  intro: string;
  outline: string[];
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
  geo_score?: number;
  geo_score_potential?: number;
  geo_score_field_deltas?: Record<string, number>;
  geo_score_components?: Record<string, { score: number; weight: number }>;
  sources_used: string[];
  business_profile_context_hash?: string | null;
  business_profile_context_status?: BusinessProfileContextStatus;
  keyword_clusters?: KeywordCluster[];
  improvement_tags?: ImprovementTag[];
  improvement_elements?: ImprovementElement[];
  optimization_context?: Record<string, unknown>;
}

interface JobState {
  job_id?: string;
  status: "queued" | "pending" | "running" | "completed" | "failed";
  phase?: "targeting" | "content";
  progress: number;
  total: number;
  queue_position?: number;
  products: ProductResult[];
  analyzed_at: string | null;
  active_product_count: number;
  analyzed_product_count: number;
  total_opportunity_count: number;
  sources_used: string[];
  provider_status?: ProviderStatus;
  competitor_signals?: CompetitorSignal[];
  cannibalization_alerts?: CannibalizationAlert[];
  orphan_products?: string[];
  blog_gap_suggestions?: BlogGapSuggestion[];
  business_profile_context?: BusinessProfileContextMeta;
  current_business_profile_context?: BusinessProfileContextMeta;
  business_profile_context_status?: BusinessProfileContextStatus;
  reflection_test?: boolean;
  events?: ResearchJobEvent[];
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
  activeJob: JobState | null;
  latestIdentification: {
    labels: Record<string, string>;
    product_titles: Record<string, string>;
  } | null;
  gscConnected: boolean;
  gscReauthRequired: boolean;
  ga4Connected: boolean;
  activeHandles: string[];
  /** Products currently active in the snapshot but absent from the latest analysis. */
  /** Product IDs present in the latest analysis but no longer active. */
  removedProductIds: string[];
  analysisUsage: { used: number; quota: number; productCap: number; plan: string } | null;
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

  const [latestJobResp, identifyResp, gscResp, ga4Resp, activeProductsResp, activeJobResp, billingResp] = await Promise.allSettled([
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
    callBackendForShop(session.shop, `/api/shops/${session.shop}/market-analysis/active-job`, {
      ...fetchOpt,
      signal: AbortSignal.timeout(5_000),
    }),
    callBackendForShop(session.shop, `/api/shops/${session.shop}/billing/status`, {
      ...fetchOpt,
      signal: AbortSignal.timeout(5_000),
    }),
  ]);

  let analysisUsage: { used: number; quota: number; productCap: number; plan: string } | null = null;
  if (billingResp.status === "fulfilled" && billingResp.value.ok) {
    try {
      const status = (await billingResp.value.json()) as {
        plan?: string;
        quotas?: { analysis?: number; products?: number };
        usage?: { analysis?: number };
      };
      if (status.quotas?.analysis !== undefined && status.usage?.analysis !== undefined) {
        analysisUsage = {
          used: status.usage.analysis,
          quota: status.quotas.analysis,
          productCap: status.quotas.products ?? 3,
          plan: status.plan ?? "free",
        };
      }
    } catch { /* ignore */ }
  }

  let latestJob: JobState | null = null;
  if (latestJobResp.status === "fulfilled" && latestJobResp.value.ok) {
    latestJob = await latestJobResp.value.json() as JobState;
  }

  // An analysis still running server-side after the merchant navigated away:
  // resume the progress bar + polling instead of showing the initial state.
  let activeJob: JobState | null = null;
  if (activeJobResp.status === "fulfilled" && activeJobResp.value.ok) {
    try {
      activeJob = (await activeJobResp.value.json()) as JobState | null;
    } catch { /* ignore */ }
  }

  let latestIdentification: { labels: Record<string, string>; product_titles: Record<string, string> } | null = null;
  if (identifyResp.status === "fulfilled" && identifyResp.value.ok) {
    latestIdentification = await identifyResp.value.json() as typeof latestIdentification;
  }

  let gscConnected = false;
  let gscReauthRequired = false;
  if (gscResp.status === "fulfilled" && gscResp.value.ok) {
    const data = await gscResp.value.json() as { connected?: boolean; reauth_required?: boolean };
    gscConnected = data.connected === true;
    gscReauthRequired = data.reauth_required === true;
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
  let removedProductIds: string[] = [];
  if (latestJob && activeProductsFull.length > 0) {
    const activeHandleSet = new Set(activeHandles);
    removedProductIds = (latestJob.products ?? [])
      .filter((p) => !activeHandleSet.has(p.product_handle))
      .map((p) => p.product_id);
  }

  return json({ locale, shop: session.shop, latestJob, activeJob, latestIdentification, gscConnected, gscReauthRequired, ga4Connected, activeHandles, removedProductIds, analysisUsage });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const formData = await request.formData();
  const intent = formData.get("intent") as string;

  // Shared ProductCard intents (apply, tags, keywords, questions, schema sync, proposal edits).
  const shared = await handleProductCardIntent(intent, formData, session);
  if (shared) return shared;

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
  if (intent === "startSingle" || intent === "saveFactsAndStartSingle") {
    const productId = formData.get("productId") as string;
    try {
      if (intent === "saveFactsAndStartSingle") {
        const answers = JSON.parse(formData.get("answers") as string) as Record<string, string>;
        const saveResp = await callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/market-analysis/facts/${encodeURIComponent(productId)}`,
          {
            accessToken: session.accessToken,
            method: "POST",
            body: JSON.stringify({ answers }),
            signal: AbortSignal.timeout(10_000),
          },
        );
        if (!saveResp.ok) {
          const err = await saveResp.text();
          return json({ type: "startSingle", jobId: null, productId, error: `Erreur ${saveResp.status}: ${err}` });
        }
      }
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs?product_ids=${encodeURIComponent(productId)}${intent === "saveFactsAndStartSingle" ? "&persist_product_result=true" : ""}`,
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

  if (intent === "loadManagedProducts") {
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/managed-products`,
        { accessToken: session.accessToken, signal: AbortSignal.timeout(20_000) },
      );
      if (!resp.ok) return json({ type: "loadManagedProducts", managed: null, error: `${resp.status}` });
      const managed = await resp.json();
      return json({ type: "loadManagedProducts", managed, error: null });
    } catch (err) {
      return json({ type: "loadManagedProducts", managed: null, error: String(err) });
    }
  }

  if (intent === "addManagedProduct") {
    const productId = String(formData.get("productId") ?? "");
    const currentIdsRaw = String(formData.get("currentIds") ?? "[]");
    try {
      const currentIds = JSON.parse(currentIdsRaw) as string[];
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/managed-products`,
        {
          accessToken: session.accessToken,
          method: "PUT",
          body: JSON.stringify({ product_ids: [...currentIds, productId] }),
          signal: AbortSignal.timeout(20_000),
        },
      );
      if (!resp.ok) {
        const detail = await resp.text();
        return json({ type: "addManagedProduct", added: false, error: `HTTP ${resp.status}: ${detail}` });
      }
      return json({ type: "addManagedProduct", added: true, productId, error: null });
    } catch (err) {
      return json({ type: "addManagedProduct", added: false, error: String(err) });
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




function progressLabel(locale: Locale, done: number, total: number): string {
  return t(locale, "marketAnalysisProgress")
    .replace("{done}", String(done))
    .replace("{total}", String(total));
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
              <Button variant="plain" size="slim" url={localizedPath("/app/onboarding", locale)}>
                {locale === "fr" ? "Se connecter" : "Connect"}
              </Button>
            )}
          </InlineStack>
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="bodySm">Google Analytics 4</Text>
            {ga4Connected ? (
              <Badge tone="success">{t(locale, "marketAnalysisBadgeReal")}</Badge>
            ) : (
              <Button variant="plain" size="slim" url={localizedPath("/app/onboarding", locale)}>
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



function SummaryCard({
  job,
  locale,
  onAnalyzeAll,
  onEditIdentification,
  onAddProduct,
  analyzeDisabled,
}: {
  job: JobState;
  locale: Locale;
  onAnalyzeAll?: () => void;
  onEditIdentification?: () => void;
  onAddProduct?: () => void;
  analyzeDisabled?: boolean;
}) {
  const contextStatus = job.business_profile_context_status;

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          {job.status === "completed" ? (
            <InlineStack gap="100" blockAlign="center">
              <span style={{ display: "inline-flex" }}>
                <Icon source={CheckIcon} tone="success" />
              </span>
              <Text as="span" variant="bodySm" tone="subdued">
                {t(locale, "marketAnalysisCompleted")} —{" "}
                {job.analyzed_product_count} {t(locale, "marketAnalysisProductCount")}
              </Text>
            </InlineStack>
          ) : (
            <div />
          )}
          {(onAnalyzeAll || onEditIdentification || onAddProduct) && (
            <InlineStack gap="200">
              {onAnalyzeAll && (
                <Button variant="primary" onClick={onAnalyzeAll} disabled={analyzeDisabled} loading={analyzeDisabled}>
                  {t(locale, "marketAnalysisAnalyzeAll")}
                </Button>
              )}
              {onAddProduct && (
                <Button onClick={onAddProduct} disabled={analyzeDisabled}>
                  {t(locale, "addProductAction")}
                </Button>
              )}
              {onEditIdentification && (
                <Button onClick={onEditIdentification} disabled={analyzeDisabled}>
                  {t(locale, "marketAnalysisEditIdentification")}
                </Button>
              )}
            </InlineStack>
          )}
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

function BusinessProfileContextBanner({
  job,
  locale,
  onRerun,
  disabled,
}: {
  job: JobState | null;
  locale: Locale;
  onRerun: () => void;
  disabled: boolean;
}) {
  if (job?.status !== "completed") return null;
  if (job.business_profile_context_status === "stale") {
    return (
      <Banner tone="warning" title={t(locale, "marketAnalysisProfileContextStaleTitle")}>
        <BlockStack gap="200">
          <Text as="p">{t(locale, "marketAnalysisProfileContextStaleBody")}</Text>
          <InlineStack>
            <Button onClick={onRerun} disabled={disabled}>
              {t(locale, "marketAnalysisAnalyzeAll")}
            </Button>
          </InlineStack>
        </BlockStack>
      </Banner>
    );
  }
  if (job.business_profile_context_status === "unknown") {
    return (
      <Banner tone="info" title={t(locale, "marketAnalysisProfileContextUnknownTitle")}>
        <BlockStack gap="200">
          <Text as="p">{t(locale, "marketAnalysisProfileContextUnknownBody")}</Text>
          <InlineStack>
            <Button onClick={onRerun} disabled={disabled}>
              {t(locale, "marketAnalysisAnalyzeAll")}
            </Button>
          </InlineStack>
        </BlockStack>
      </Banner>
    );
  }
  return null;
}


function GeoPackSection({
  productId,
  pack,
  locale,
}: {
  productId: string;
  pack: ContentTestPack;
  locale: Locale;
}) {
  const jsonld = pack.proposed_schema_jsonld;
  const syncFetcher = useFetcher<{
    type: string;
    error: string | null;
    data?: {
      saved?: boolean;
      schema_facts_sync?: {
        applied: boolean;
        error: string | null;
        entry_count: number;
        applied_at: string | null;
      };
    };
  }>();
  const syncState = syncFetcher.data?.data?.schema_facts_sync ?? pack.schema_facts_sync;
  const canSyncFacts = (pack.confirmed_facts ?? []).length > 0;

  const syncSchemaFacts = () => {
    const form = new FormData();
    form.set("intent", "syncSchemaFacts");
    form.set("productId", productId);
    syncFetcher.submit(form, { method: "post" });
  };

  return (
    <BlockStack gap="300">
      {pack.eeat_signals && pack.eeat_signals.length > 0 ? (
        <Box>
          <Text as="p" variant="headingXs">{t(locale, "marketAnalysisEeatSignals")}</Text>
          <InlineStack gap="100" wrap>
            {pack.eeat_signals.map((s, i) => (
              <Badge key={i} tone="success">{s.label}</Badge>
            ))}
          </InlineStack>
        </Box>
      ) : null}

      {jsonld && (jsonld.product || jsonld.faq || jsonld.breadcrumb) ? (
        <Box>
          <InlineStack gap="200" align="space-between" blockAlign="center">
            <Text as="p" variant="headingXs">{t(locale, "marketAnalysisGeoJsonLd")}</Text>
            <InlineStack gap="150" blockAlign="center">
              {syncState?.applied && syncState.applied_at ? (
                <Badge tone="success">
                  {locale === "fr" ? "Faits synchronisés" : "Facts synced"}
                </Badge>
              ) : null}
              <Button
                size="slim"
                disabled={!canSyncFacts}
                loading={syncFetcher.state !== "idle"}
                onClick={syncSchemaFacts}
              >
                {locale === "fr" ? "Synchroniser avec le thème" : "Sync to theme"}
              </Button>
              <Button
                size="slim"
                onClick={() => {
                  if (typeof navigator !== "undefined" && navigator.clipboard) {
                    navigator.clipboard.writeText(JSON.stringify(jsonld, null, 2));
                  }
                }}
              >
                {t(locale, "marketAnalysisGeoCopyJsonLd")}
              </Button>
            </InlineStack>
          </InlineStack>
          {syncFetcher.data?.error ? (
            <Box paddingBlockStart="100">
              <Banner tone="warning">
                <Text as="p" variant="bodySm">{syncFetcher.data.error}</Text>
              </Banner>
            </Box>
          ) : null}
          {syncState?.applied === false && syncState.error ? (
            <Box paddingBlockStart="100">
              <Banner tone="warning">
                <Text as="p" variant="bodySm">{syncState.error}</Text>
              </Banner>
            </Box>
          ) : null}
          <Box paddingBlockStart="100" background="bg-surface-secondary" borderRadius="200" padding="200">
            <Text as="p" variant="bodySm" tone="subdued">
              <code style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                {JSON.stringify(jsonld, null, 2).slice(0, 800)}
                {JSON.stringify(jsonld, null, 2).length > 800 ? "…" : ""}
              </code>
            </Text>
          </Box>
        </Box>
      ) : null}
    </BlockStack>
  );
}

function OrphanGapsBanner({
  orphanProducts,
  blogGaps,
  productsById,
  locale,
}: {
  orphanProducts: string[];
  blogGaps: BlogGapSuggestion[];
  productsById: Record<string, ProductResult>;
  locale: Locale;
}) {
  if (orphanProducts.length === 0 && blogGaps.length === 0) return null;
  return (
    <Banner tone="info">
      <BlockStack gap="200">
        {orphanProducts.length > 0 ? (
          <BlockStack gap="050">
            <Text as="p" variant="bodySm">
              <strong>{t(locale, "marketAnalysisOrphanProducts")}</strong>
            </Text>
            <Text as="p" variant="bodySm" tone="subdued">
              {t(locale, "marketAnalysisOrphanProductsExplain")}
            </Text>
            {orphanProducts.map((pid) => {
              const p = productsById[pid];
              return (
                <Text key={pid} as="p" variant="bodySm">
                  • {p ? p.product_title : pid}
                </Text>
              );
            })}
          </BlockStack>
        ) : null}
        {blogGaps.length > 0 ? (
          <BlockStack gap="050">
            <Text as="p" variant="bodySm">
              <strong>{t(locale, "marketAnalysisBlogGaps")}</strong>
            </Text>
            <Text as="p" variant="bodySm" tone="subdued">
              {t(locale, "marketAnalysisBlogGapsExplain")}
            </Text>
            {blogGaps.map((gap, i) => (
              <InlineStack key={i} gap="200" align="start" blockAlign="center">
                <Text as="p" variant="bodySm">
                  • {gap.suggested_title}
                </Text>
                <Button
                  size="slim"
                  variant="plain"
                  url={`/app/blog?cluster=${encodeURIComponent(gap.cluster_head)}&title=${encodeURIComponent(gap.suggested_title)}`}
                >
                  {t(locale, "marketAnalysisBlogGapCreate")}
                </Button>
              </InlineStack>
            ))}
          </BlockStack>
        ) : null}
      </BlockStack>
    </Banner>
  );
}

function CannibalizationBanner({
  alerts,
  locale,
}: {
  alerts: CannibalizationAlert[];
  locale: Locale;
}) {
  if (!alerts || alerts.length === 0) return null;
  const heading = t(locale, "marketAnalysisCannibalizationHeading").replace(
    "{count}",
    String(alerts.length),
  );
  return (
    <Banner tone="warning" title={heading}>
      <BlockStack gap="200">
        <Text as="p" variant="bodySm">
          {t(locale, "marketAnalysisCannibalizationIntro")}
        </Text>
        <BlockStack gap="200">
          {alerts.map((alert) => {
            const winner = alert.products.find(
              (p) => p.product_id === alert.winner_suggested,
            );
            const losers = alert.products.filter(
              (p) => p.product_id !== alert.winner_suggested,
            );
            return (
              <Box
                key={`${alert.cluster_head}-${alert.product_ids.join("-")}`}
                paddingBlock="200"
                paddingInline="300"
                background="bg-surface-secondary"
                borderRadius="200"
              >
                <BlockStack gap="100">
                  <InlineStack gap="200" blockAlign="center">
                    <Text as="span" variant="bodySm">
                      <strong>{alert.cluster_head}</strong>
                    </Text>
                    <Badge tone="warning">
                      {t(locale, "marketAnalysisCannibalizationConflict")}
                    </Badge>
                  </InlineStack>
                  {winner ? (
                    <Text as="p" variant="bodySm">
                      {t(locale, "marketAnalysisCannibalizationWinner")}{" "}
                      <strong>{winner.product_title}</strong>
                    </Text>
                  ) : null}
                  {losers.length > 0 ? (
                    <Text as="p" variant="bodySm" tone="subdued">
                      {t(locale, "marketAnalysisCannibalizationReorient")}{" "}
                      {losers.map((l) => l.product_title).join(", ")}
                    </Text>
                  ) : null}
                </BlockStack>
              </Box>
            );
          })}
        </BlockStack>
      </BlockStack>
    </Banner>
  );
}

// ── Page component ────────────────────────────────────────────────────────────

export default function ProductsPage() {
  const { locale, shop, latestJob, activeJob, latestIdentification, gscConnected, gscReauthRequired, ga4Connected, activeHandles, removedProductIds, analysisUsage } =
    useLoaderData<LoaderData>();

  const revalidator = useRevalidator();

  // ── UI step: "identification" (step 1) or "analysis" (step 2) ────────────
  const [step, setStep] = useState<"identification" | "analysis">(
    latestJob || activeJob ? "analysis" : "identification",
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
  // Resume an in-progress analysis (activeJob) after navigating away/back:
  // seeding jobId restarts the polling loop and the progress bar. Falls back to
  // the last completed result (latestJob) when nothing is running.
  const [jobId, setJobId] = useState<string | null>(activeJob?.job_id ?? null);
  const [job, setJob] = useState<JobState | null>(activeJob ?? latestJob);
  const [pollError, setPollError] = useState<string | null>(null);

  // ── Edit mode (came from "Modifier l'identification") ─────────────────────
  const [editMode, setEditMode] = useState(false);

  // ── Active-only filter ────────────────────────────────────────────────────
  const [showInactive, setShowInactive] = useState(false);

  // ── Full re-run confirmation modal ────────────────────────────────────────
  const [showRerunModal, setShowRerunModal] = useState(false);

  // ── "Add a product" modal (managed-products selection) ───────────────────
  type ManagedState = {
    selected_ids: string[] | null;
    cap: number;
    plan: string;
    available_products: Array<{ id: string; title: string; image_url: string | null }>;
  };
  const [showAddProductModal, setShowAddProductModal] = useState(false);
  const managedFetcher = useFetcher<{ type: string; managed: ManagedState | null; error?: string | null }>();
  const addProductFetcher = useFetcher<{ type: string; added?: boolean; error?: string | null }>();
  const managed = managedFetcher.data?.managed ?? null;
  const openAddProductModal = () => {
    setShowAddProductModal(true);
    const fd = new FormData();
    fd.set("intent", "loadManagedProducts");
    managedFetcher.submit(fd, { method: "post" });
  };
  const handleAddProduct = (productId: string) => {
    const fd = new FormData();
    fd.set("intent", "addManagedProduct");
    fd.set("productId", productId);
    fd.set("currentIds", JSON.stringify(managed?.selected_ids ?? []));
    addProductFetcher.submit(fd, { method: "post" });
  };
  useEffect(() => {
    if (addProductFetcher.data?.type === "addManagedProduct" && addProductFetcher.data.added) {
      setShowAddProductModal(false);
      revalidator.revalidate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addProductFetcher.data]);

  // ── Single-product analysis state ─────────────────────────────────────────
  const [singleProductJobId, setSingleProductJobId] = useState<string | null>(null);
  const [singleProductId, setSingleProductId] = useState<string | null>(null);
  const [singleProductJob, setSingleProductJob] = useState<JobState | null>(null);
  const [singleProductError, setSingleProductError] = useState<string | null>(null);

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

  // Notify the merchant via an App Bridge toast when an analysis just finished
  // (transition → completed only, so it doesn't fire on page load of an
  // already-completed analysis).
  // True while a single-product job was launched from "Améliorer" (enrich),
  // so we can show the "answers saved — validate the description" toast on
  // completion instead of the generic analysis-done toast.
  const enrichTriggeredRef = useRef(false);
  const prevJobStatusForToast = useRef<string | undefined>(undefined);
  const [showSuccessUpsell, setShowSuccessUpsell] = useState(false);
  useEffect(() => {
    const prev = prevJobStatusForToast.current;
    if (job?.status === "completed" && prev && prev !== "completed") {
      (window as unknown as { shopify?: { toast?: { show: (m: string) => void } } }).shopify
        ?.toast?.show(t(locale, "marketAnalysisDoneToast"));
      // Post-success upsell: the moment of realized value is the natural
      // breaking point where free merchants convert best.
      if (analysisUsage?.plan === "free") setShowSuccessUpsell(true);
    }
    prevJobStatusForToast.current = job?.status;
  }, [job?.status, locale, analysisUsage?.plan]);

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
        setSingleProductError(null);
      } else if (singleFetcher.data.error) {
        setSingleProductError(singleFetcher.data.error);
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
          if (enrichTriggeredRef.current) {
            (window as unknown as { shopify?: { toast?: { show: (m: string) => void } } }).shopify
              ?.toast?.show(t(locale, "enrichSavedToast"));
            enrichTriggeredRef.current = false;
          }
          setSingleProductJobId(null);
          setSingleProductId(null);
          setSingleProductJob(null);
          setSingleProductError(null);
        }
        if (d.job.status === "failed") {
          setSingleProductError(d.job.error || t(locale, "marketAnalysisSingleProductFailed"));
          setSingleProductJobId(null);
          setSingleProductId(null);
          setSingleProductJob(null);
        }
      }
      if (d.error) setSingleProductError(d.error);
    }
  }, [pollSingleFetcher.data, locale]);

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
  const anyError =
    startError ||
    pollError ||
    singleProductError ||
    (job?.status === "failed" ? job.error : null);

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
    setSingleProductError(null);
    const fd = new FormData();
    fd.set("intent", "startSingle");
    fd.set("productId", productId);
    singleFetcher.submit(fd, { method: "post" });
  };

  const handleEnrichAndAnalyze = (productId: string, answers: Record<string, string>) => {
    enrichTriggeredRef.current = true;
    setSingleProductJobId(null);
    setSingleProductId(productId);
    setSingleProductJob(null);
    setSingleProductError(null);
    const fd = new FormData();
    fd.set("intent", "saveFactsAndStartSingle");
    fd.set("productId", productId);
    fd.set("answers", JSON.stringify(answers));
    singleFetcher.submit(fd, { method: "post" });
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <Page
      title={t(locale, "navProducts")}
      titleMetadata={
        <InlineStack gap="200" blockAlign="center">
          <PlanBadge />
          {analysisUsage && (
            <QuotaPill
              used={analysisUsage.used}
              quota={analysisUsage.quota}
            />
          )}
        </InlineStack>
      }
      subtitle={t(locale, "marketAnalysisSubtitle")}
    >
      <BlockStack gap="400">
        {showSuccessUpsell && (
          <Banner
            tone="success"
            title={locale === "fr" ? "Belle progression !" : "Great progress!"}
            action={{
              content: locale === "fr" ? "Essayer Pro 7 jours gratuitement" : "Try Pro free for 7 days",
              url: "/app/billing",
            }}
            onDismiss={() => setShowSuccessUpsell(false)}
          >
            <Text as="p">
              {locale === "fr"
                ? "Votre analyse est terminée — c'était celle de votre cycle de 28 jours. Avec Pro, l'agent referait ce travail chaque jour, automatiquement, sur 15 produits."
                : "Your analysis is done — that was the one in your 28-day cycle. With Pro, the agent would redo this work every day, automatically, across 15 products."}
            </Text>
          </Banner>
        )}
        {gscReauthRequired ? (
          <Banner
            tone="critical"
            title={
              locale === "fr"
                ? "Reconnexion à Google requise"
                : "Google reconnection required"
            }
          >
            <BlockStack gap="200">
              <Text as="p">
                {locale === "fr"
                  ? "Google a déconnecté votre compte. Reconnectez-le pour que les analyses continuent d'utiliser vos vraies données de recherche."
                  : "Google disconnected your account. Reconnect it so analyses keep using your real search data."}
              </Text>
              <InlineStack>
                <Button url="/app/onboarding" variant="primary">
                  {locale === "fr" ? "Reconnecter Google" : "Reconnect Google"}
                </Button>
              </InlineStack>
            </BlockStack>
          </Banner>
        ) : !gscConnected ? (
          <Banner
            tone="warning"
            title={
              locale === "fr"
                ? "Google n'est pas connecté"
                : "Google is not connected"
            }
          >
            <BlockStack gap="200">
              <Text as="p">
                {locale === "fr"
                  ? "Sans Google, les recommandations seront basées sur le marché général, pas sur les vraies requêtes de vos clients."
                  : "Without Google, recommendations will be based on the general market, not on your customers' real queries."}
              </Text>
              <InlineStack>
                <Button url="/app/onboarding" variant="primary">
                  {locale === "fr" ? "Connecter Google" : "Connect Google"}
                </Button>
              </InlineStack>
            </BlockStack>
          </Banner>
        ) : null}

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
        {/* Competitor signals are surfaced on the dashboard "Concurrents" card. */}

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
              open={showAddProductModal}
              onClose={() => setShowAddProductModal(false)}
              title={t(locale, "addProductModalTitle")}
            >
              <Modal.Section>
                <BlockStack gap="300">
                  {managedFetcher.state !== "idle" && <Spinner size="small" />}
                  {addProductFetcher.data?.error && (
                    <Banner tone="critical">
                      <Text as="p">{addProductFetcher.data.error}</Text>
                    </Banner>
                  )}
                  {managed && (
                    <>
                      <Text as="p" fontWeight="semibold">
                        {t(locale, "productSelectionCount")
                          .replace("{selected}", String((managed.selected_ids ?? []).length))
                          .replace("{cap}", String(managed.cap))}
                      </Text>
                      {(managed.selected_ids ?? []).length >= managed.cap ? (
                        <Banner tone="warning">
                          <Text as="p">{t(locale, "productSelectionCapReached")}</Text>
                        </Banner>
                      ) : (
                        (() => {
                          const selectedSet = new Set(managed.selected_ids ?? []);
                          const addable = managed.available_products.filter((ap) => !selectedSet.has(ap.id));
                          if (addable.length === 0) {
                            return (
                              <Text as="p" tone="subdued">{t(locale, "addProductNoneLeft")}</Text>
                            );
                          }
                          return addable.map((ap) => (
                            <InlineStack key={ap.id} align="space-between" blockAlign="center" wrap={false}>
                              <InlineStack gap="300" blockAlign="center" wrap={false}>
                                <Thumbnail
                                  source={ap.image_url || ProductAddIcon}
                                  alt={ap.title}
                                  size="small"
                                />
                                <Text as="span">{ap.title}</Text>
                              </InlineStack>
                              <Button
                                size="slim"
                                loading={addProductFetcher.state !== "idle"}
                                onClick={() => handleAddProduct(ap.id)}
                              >
                                {t(locale, "addProductAdd")}
                              </Button>
                            </InlineStack>
                          ));
                        })()
                      )}
                    </>
                  )}
                </BlockStack>
              </Modal.Section>
            </Modal>

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

            <BusinessProfileContextBanner
              job={job}
              locale={locale}
              onRerun={() => setShowRerunModal(true)}
              disabled={isInProgress}
            />


            {/* Cannibalization alerts — two products sharing the same primary cluster */}
            {job?.cannibalization_alerts && job.cannibalization_alerts.length > 0 ? (
              <CannibalizationBanner alerts={job.cannibalization_alerts} locale={locale} />
            ) : null}

            {/* Orphan products + blog content gaps (internal linking engine) */}
            {job && (
              (job.orphan_products && job.orphan_products.length > 0) ||
              (job.blog_gap_suggestions && job.blog_gap_suggestions.length > 0)
            ) ? (
              <OrphanGapsBanner
                orphanProducts={job.orphan_products ?? []}
                blogGaps={job.blog_gap_suggestions ?? []}
                productsById={Object.fromEntries(
                  (job.products ?? []).map((p) => [p.product_id, p]),
                )}
                locale={locale}
              />
            ) : null}

            {/* Launch card — only shown when no job yet, job failed, or analysis running */}
            {(!job?.status || job.status === "failed" || isRunning) && (
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
                  {isRunning && job?.status === "queued" && (
                    <Banner tone="info">
                      <Text as="p">
                        {t(locale, "marketAnalysisQueued")}
                        {job.queue_position && job.queue_position > 0
                          ? ` ${t(locale, "marketAnalysisQueuePosition").replace("{n}", String(job.queue_position))}`
                          : ""}
                      </Text>
                    </Banner>
                  )}
                  {isRunning && job?.status !== "queued" && (
                    <ResearchConsole
                      locale={locale}
                      phrases={loaderPhrases(locale, "analysis")}
                      progress={job && job.total > 0 ? progressPct : undefined}
                      estimateMs={300_000}
                      title={
                        job && job.total > 0
                          ? progressLabel(locale, job.progress, job.total)
                          : t(locale, "marketAnalysisRunning")
                      }
                      steps={buildAnalysisSteps(locale, job?.status, job?.phase)}
                      events={job?.events}
                      counters={job ? buildAnalysisCounters(locale, job) : undefined}
                    />
                  )}
                </BlockStack>
              </Card>
            )}

            {/* Error */}
            {anyError && String(anyError).includes("402") && String(anyError).includes("quota_exceeded") ? (
              <Banner
                tone="warning"
                title={locale === "fr" ? "Limite d'analyses atteinte pour ce cycle de 28 jours" : "Analysis limit reached for this 28-day cycle"}
                action={{ content: locale === "fr" ? "Voir les plans" : "See plans", url: "/app/billing" }}
              >
                <Text as="p">
                  {locale === "fr"
                    ? "Passez au plan supérieur pour lancer plus d'analyses et couvrir plus de produits."
                    : "Upgrade your plan to run more analyses and cover more products."}
                </Text>
              </Banner>
            ) : anyError ? (
              <Banner tone="critical">
                <Text as="p">{anyError}</Text>
              </Banner>
            ) : null}

            {/* Completion recap — the deep-research "here is what I did" line */}
            {job?.status === "completed" &&
              (() => {
                const recap = (job.events ?? []).find((e) => e.code === "analysis_completed");
                if (!recap) return null;
                const p = recap.params;
                const seconds = Number(p.duration_s ?? 0);
                const duration =
                  seconds >= 60 ? `${Math.round(seconds / 60)} min` : `${Math.max(seconds, 1)} s`;
                return (
                  <Banner tone="success">
                    <Text as="p">
                      {t(locale, "researchRecapAnalysis")
                        .replace("{products}", String(p.products ?? 0))
                        .replace("{keywords}", String(p.keywords_evaluated ?? 0))
                        .replace("{sources}", String(p.sources ?? 0))
                        .replace("{duration}", duration)}
                    </Text>
                  </Banner>
                );
              })()}

            {/* Summary + export */}
            {job && job.analyzed_product_count > 0 && (
              <>
                <SummaryCard
                  job={job}
                  locale={locale}
                  onAnalyzeAll={() => setShowRerunModal(true)}
                  onAddProduct={openAddProductModal}
                  onEditIdentification={handleEditIdentification}
                  analyzeDisabled={isInProgress}
                />
              </>
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
                        shop={shop}
                        isAnalyzing={singleProductId === product.product_id && isSingleRunning}
                        onEnrichAndAnalyze={(answers) => handleEnrichAndAnalyze(product.product_id, answers)}
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

          </>
        )}
        <Box paddingBlockEnd="800" />
      </BlockStack>
    </Page>
  );
}
