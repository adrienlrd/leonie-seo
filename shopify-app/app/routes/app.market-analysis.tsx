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
  Icon,
  InlineStack,
  Modal,
  Page,
  ProgressBar,
  Spinner,
  Text,
  TextField,
  Tooltip,
} from "@shopify/polaris";
import { AlertTriangleIcon } from "@shopify/polaris-icons";
import { Component, useEffect, useRef, useState } from "react";
import type { ReactNode, ErrorInfo } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { ProductContentProposals, type FieldKey } from "../components/ProductContentProposals";

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
  sources_used: string[];
  business_profile_context_hash?: string | null;
  business_profile_context_status?: BusinessProfileContextStatus;
  keyword_clusters?: KeywordCluster[];
  improvement_tags?: ImprovementTag[];
  improvement_elements?: ImprovementElement[];
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
  cannibalization_alerts?: CannibalizationAlert[];
  orphan_products?: string[];
  blog_gap_suggestions?: BlogGapSuggestion[];
  business_profile_context?: BusinessProfileContextMeta;
  current_business_profile_context?: BusinessProfileContextMeta;
  business_profile_context_status?: BusinessProfileContextStatus;
  reflection_test?: boolean;
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

  if (intent === "syncSchemaFacts") {
    const productId = formData.get("productId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/proposals/${encodeURIComponent(productId)}/schema-facts/sync`,
        {
          accessToken: session.accessToken,
          method: "POST",
          signal: AbortSignal.timeout(15_000),
        },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "syncSchemaFacts", error: `Erreur ${resp.status}: ${err}` });
      }
      const data = await resp.json();
      return json({ type: "syncSchemaFacts", error: null, data });
    } catch (err) {
      return json({ type: "syncSchemaFacts", error: String(err) });
    }
  }

  if (intent === "retireTag" || intent === "restoreTag") {
    const productId = formData.get("productId") as string;
    const tagId = formData.get("tagId") as string;
    const action = intent === "retireTag" ? "retire" : "restore";
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/products/${encodeURIComponent(productId)}/tags/${encodeURIComponent(tagId)}/${action}`,
      { accessToken: session.accessToken, method: "POST" },
    );
    const data = resp.ok ? await resp.json() : null;
    return json({ type: intent, ok: resp.ok, data });
  }

  if (intent === "addTag") {
    const productId = formData.get("productId") as string;
    const label = formData.get("label") as string;
    const tagType = (formData.get("tagType") as string) || "merchant";
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/products/${encodeURIComponent(productId)}/tags`,
      {
        accessToken: session.accessToken,
        method: "POST",
        body: JSON.stringify({ label, tag_type: tagType, status: "forced", locked_by_merchant: true }),
      },
    );
    const data = resp.ok ? await resp.json() : null;
    return json({ type: "addTag", ok: resp.ok, data });
  }

  if (intent === "retireKeyword") {
    const productId = formData.get("productId") as string;
    const label = formData.get("label") as string;
    const tagType = (formData.get("tagType") as string) || "keyword";
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/products/${encodeURIComponent(productId)}/tags`,
      {
        accessToken: session.accessToken,
        method: "POST",
        body: JSON.stringify({ label, tag_type: tagType, status: "negative", locked_by_merchant: true }),
      },
    );
    const data = resp.ok ? await resp.json() : null;
    return json({ type: "retireKeyword", ok: resp.ok, data });
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

  if (intent === "validateQuestion") {
    const productId = String(formData.get("productId") ?? "");
    const key = String(formData.get("key") ?? "");
    const answer = String(formData.get("answer") ?? "");
    if (key && answer.trim()) {
      try {
        await callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/market-analysis/facts/${encodeURIComponent(productId)}`,
          {
            accessToken: session.accessToken,
            method: "POST",
            body: JSON.stringify({ answers: { [key]: answer } }),
            signal: AbortSignal.timeout(10_000),
          },
        );
      } catch { /* best-effort */ }
    }
    return json({ type: "validateQuestion", ok: true, error: null });
  }

  if (intent === "retireQuestion" || intent === "restoreQuestion") {
    const productId = String(formData.get("productId") ?? "");
    const key = String(formData.get("key") ?? "");
    const action = intent === "retireQuestion" ? "retire" : "restore";
    try {
      await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/products/${encodeURIComponent(productId)}/questions/${encodeURIComponent(key)}/${action}`,
        { accessToken: session.accessToken, method: "POST", signal: AbortSignal.timeout(10_000) },
      );
    } catch { /* best-effort */ }
    return json({ type: intent, ok: true, error: null });
  }

  if (intent === "applyToShopify") {
    const productId = String(formData.get("productId") ?? "");
    const fields = JSON.parse(String(formData.get("fields") ?? "[]")) as string[];
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/proposals/${encodeURIComponent(productId)}/apply-to-shopify`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify({ fields, confirm_live_write: true }),
          signal: AbortSignal.timeout(30_000),
        },
      );
      const data = await resp.json().catch(() => ({})) as { results?: Record<string, { applied: boolean; error: string | null }>; detail?: string };
      return json({ type: "applyToShopify", ok: resp.ok, results: data.results ?? {}, error: resp.ok ? null : (data.detail ?? `Backend ${resp.status}`) });
    } catch (err) {
      return json({ type: "applyToShopify", ok: false, results: {}, error: String(err) });
    }
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

function KeywordSourceBadge({ source, locale }: { source: KeywordSource | undefined; locale: Locale }) {
  if (!source) return null;
  if (source === "gsc") return <Badge tone="success">{t(locale, "marketAnalysisSourceGsc")}</Badge>;
  if (source === "dataforseo") return <Badge tone="success">{t(locale, "marketAnalysisSourceDataforseo")}</Badge>;
  if (source === "ga4") return <Badge tone="success">{t(locale, "marketAnalysisSourceGa4")}</Badge>;
  if (source === "google_suggest") return <Badge tone="info">{t(locale, "marketAnalysisSourceSuggest")}</Badge>;
  if (source === "trends") return <Badge tone="info">{t(locale, "marketAnalysisSourceTrends")}</Badge>;
  if (source === "shopify") return <Badge tone="info">{t(locale, "marketAnalysisSourceShopify")}</Badge>;
  if (source === "parent_estimated") {
    return <Badge tone="info">{locale === "fr" ? "Estimé via parent" : "Parent-estimated"}</Badge>;
  }
  if (source === "llm_proposed") return <Badge tone="attention">{t(locale, "marketAnalysisSourceLlmProposed")}</Badge>;
  return <Badge tone="attention">{t(locale, "marketAnalysisSourceLlm")}</Badge>;
}

function tagToneInAdded(tag: ImprovementTag): "success" | "critical" | "attention" | "warning" | "info" {
  if (tag.tag_type === "keyword") return "attention";
  if (tag.tag_type === "risk") return "critical";
  if (tag.tag_type === "merchant" || tag.status === "forced") return "warning";
  if (tag.status === "positive") return "success";
  return "info";
}

function ImprovementTags({
  addedTags,
  retiredTags,
  openBucket,
  onToggle,
  onRetire,
  onRestore,
  newLabel,
  onNewLabelChange,
  onAdd,
  locale,
}: {
  addedTags: ImprovementTag[];
  retiredTags: ImprovementTag[];
  openBucket: "added" | "retired" | null;
  onToggle: (b: "added" | "retired") => void;
  onRetire: (tag: ImprovementTag) => void;
  onRestore: (tag: ImprovementTag) => void;
  newLabel: string;
  onNewLabelChange: (v: string) => void;
  onAdd: () => void;
  locale: Locale;
}) {
  const fr = locale === "fr";
  return (
    <BlockStack gap="200">
      <InlineStack gap="150">
        <Button
          size="slim"
          pressed={openBucket === "added"}
          onClick={() => onToggle("added")}
        >
          {fr ? `Tags ajoutés (${addedTags.length})` : `Added tags (${addedTags.length})`}
        </Button>
        {retiredTags.length > 0 && (
          <Button
            size="slim"
            pressed={openBucket === "retired"}
            onClick={() => onToggle("retired")}
          >
            {fr ? `Tags retirés (${retiredTags.length})` : `Retired tags (${retiredTags.length})`}
          </Button>
        )}
      </InlineStack>

      {openBucket === "added" && (
        <Box padding="300" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
          <BlockStack gap="200">
            {addedTags.length === 0 ? (
              <Text as="p" variant="bodySm" tone="subdued">
                {fr ? "Aucun tag actif." : "No active tags."}
              </Text>
            ) : (
              <BlockStack gap="100">
                {addedTags.map((tag) => (
                  <InlineStack key={tag.tag_id} align="space-between" blockAlign="center">
                    <Badge tone={tagToneInAdded(tag)}>{tag.label}</Badge>
                    <Button size="slim" variant="plain" tone="critical" onClick={() => onRetire(tag)}>
                      {fr ? "Retirer" : "Retire"}
                    </Button>
                  </InlineStack>
                ))}
              </BlockStack>
            )}
            <InlineStack gap="150" blockAlign="center">
              <div style={{ flex: 1 }}>
                <TextField
                  label=""
                  labelHidden
                  placeholder={fr ? "Nouveau tag…" : "New tag…"}
                  value={newLabel}
                  onChange={onNewLabelChange}
                  autoComplete="off"
                />
              </div>
              <Button size="slim" onClick={onAdd} disabled={!newLabel.trim()}>
                {fr ? "Ajouter" : "Add"}
              </Button>
            </InlineStack>
          </BlockStack>
        </Box>
      )}

      {openBucket === "retired" && retiredTags.length > 0 && (
        <Box padding="300" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
          <BlockStack gap="100">
            <Text as="p" variant="bodySm" tone="subdued">
              {fr
                ? "Ces sujets sont exclus des prochaines analyses."
                : "These topics are excluded from future analyses."}
            </Text>
            {retiredTags.map((tag) => (
              <InlineStack key={tag.tag_id} align="space-between" blockAlign="center">
                <Badge tone="critical">{tag.label}</Badge>
                <Button size="slim" variant="plain" onClick={() => onRestore(tag)}>
                  {fr ? "Restaurer" : "Restore"}
                </Button>
              </InlineStack>
            ))}
          </BlockStack>
        </Box>
      )}
    </BlockStack>
  );
}

function NotImprovedIcon({ elements, locale }: { elements?: ImprovementElement[]; locale: Locale }) {
  const notImproved = (elements ?? []).filter((e) => !e.improved);
  if (notImproved.length === 0) return null;
  const tip = notImproved.map((e) => e.label).join(", ");
  return (
    <Tooltip content={`${locale === "fr" ? "Non amélioré" : "Not improved"} : ${tip}`}>
      <span style={{ display: "inline-flex", cursor: "help" }}>
        <Icon source={AlertTriangleIcon} tone="warning" />
      </span>
    </Tooltip>
  );
}

function SummaryCard({
  job,
  locale,
  onAnalyzeAll,
  onEditIdentification,
  analyzeDisabled,
}: {
  job: JobState;
  locale: Locale;
  onAnalyzeAll?: () => void;
  onEditIdentification?: () => void;
  analyzeDisabled?: boolean;
}) {
  const contextStatus = job.business_profile_context_status;

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <div />
          {(onAnalyzeAll || onEditIdentification) && (
            <InlineStack gap="200">
              {onAnalyzeAll && (
                <Button variant="primary" onClick={onAnalyzeAll} disabled={analyzeDisabled} loading={analyzeDisabled}>
                  {t(locale, "marketAnalysisAnalyzeAll")}
                </Button>
              )}
              {onEditIdentification && (
                <Button variant="plain" onClick={onEditIdentification} disabled={analyzeDisabled}>
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

function ProductCard({
  product,
  locale,
  shop,
  isAnalyzing,
  onAnalyze,
  onEnrichAndAnalyze,
  analyzeDisabled,
}: {
  product: ProductResult;
  locale: Locale;
  shop: string;
  isAnalyzing: boolean;
  onAnalyze: () => void;
  onEnrichAndAnalyze: (answers: Record<string, string>) => void;
  analyzeDisabled: boolean;
}) {
  const fr = locale === "fr";
  const [openSection, setOpenSection] = useState<string | null>(null);
  const toggle = (s: string) => setOpenSection((p) => (p === s ? null : s));

  // ── Question retire/restore ───────────────────────────────────────────────
  const questionFetcher = useFetcher<{ type: string; ok: boolean }>();
  const onRetireQuestion = (key: string) =>
    questionFetcher.submit(
      { intent: "retireQuestion", productId: product.product_id, key },
      { method: "post" },
    );
  const onRestoreQuestion = (key: string) =>
    questionFetcher.submit(
      { intent: "restoreQuestion", productId: product.product_id, key },
      { method: "post" },
    );
  const onValidateQuestion = (key: string, answer: string) =>
    questionFetcher.submit(
      { intent: "validateQuestion", productId: product.product_id, key, answer },
      { method: "post" },
    );

  // ── Apply-to-Shopify state ─────────────────────────────────────────────────
  const applyFetcher = useFetcher<{ type: string; ok: boolean; results?: Record<string, { applied: boolean; error: string | null }>; error?: string | null }>();
  const applyLoading = applyFetcher.state !== "idle";

  const pack = product.content_test_pack;
  const APPLY_FIELDS: FieldKey[] = ["meta_title", "meta_description", "alt_text", "description"];

  const fieldHasProposal = (key: FieldKey): boolean => {
    switch (key) {
      case "meta_title": return Boolean(pack?.proposed_meta_title) && pack?.proposed_meta_title !== pack?.current_meta_title;
      case "meta_description": return Boolean(pack?.proposed_meta_description) && pack?.proposed_meta_description !== pack?.current_meta_description;
      case "description": return Boolean(pack?.proposed_product_description);
      case "alt_text": return (pack?.proposed_image_alts ?? []).some((a) => Boolean(a.proposed_alt));
      default: return false;
    }
  };

  const [checkedApplyFields, setCheckedApplyFields] = useState<Set<FieldKey>>(
    () => new Set(APPLY_FIELDS.filter(fieldHasProposal)),
  );

  const packSig = JSON.stringify(pack);
  useEffect(() => {
    setCheckedApplyFields(new Set(APPLY_FIELDS.filter(fieldHasProposal)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product.product_id, packSig]);

  const onToggleApplyField = (field: FieldKey) =>
    setCheckedApplyFields((prev) => {
      const next = new Set(prev);
      if (next.has(field)) next.delete(field); else next.add(field);
      return next;
    });

  const handleApplyProposals = () => {
    const fields = [...checkedApplyFields].map((f) => (f === "alt_text" ? "image_alts" : f));
    applyFetcher.submit(
      { intent: "applyToShopify", productId: product.product_id, fields: JSON.stringify(fields) },
      { method: "post" },
    );
  };

  const applyResult = applyFetcher.data?.type === "applyToShopify" ? applyFetcher.data : null;

  // ── Tag state managed at ProductCard level ─────────────────────────────────
  const [localTags, setLocalTags] = useState<ImprovementTag[]>(product.improvement_tags ?? []);
  useEffect(() => {
    const serverTags = product.improvement_tags ?? [];
    setLocalTags((prev) => {
      // Preserve pending optimistic tags (tmp- prefix) not yet confirmed by server
      const pending = prev.filter(
        (p) =>
          p.tag_id.startsWith("tmp-") &&
          !serverTags.some(
            (s) => s.label.toLowerCase() === p.label.toLowerCase() && s.tag_type === p.tag_type,
          ),
      );
      return [...serverTags, ...pending];
    });
  }, [product.product_id, product.improvement_tags]);
  const tagFetcher = useFetcher<{ ok?: boolean }>();
  const [openBucket, setOpenBucket] = useState<"added" | "retired" | null>(null);
  const [newTagLabel, setNewTagLabel] = useState("");

  const addedTags = localTags.filter((t) => t.status !== "negative");
  const retiredTags = localTags.filter((t) => t.status === "negative");
  const keywordTagLabels = new Set(
    localTags.filter((t) => t.tag_type === "keyword").map((t) => t.label.toLowerCase()),
  );

  const onToggleBucket = (b: "added" | "retired") =>
    setOpenBucket((p) => (p === b ? null : b));

  const retireTag = (tag: ImprovementTag) => {
    setLocalTags((prev) =>
      prev.map((t) =>
        t.tag_id === tag.tag_id
          ? { ...t, status: "negative" as ImprovementTagStatus, locked_by_merchant: true }
          : t,
      ),
    );
    tagFetcher.submit(
      { intent: "retireTag", productId: product.product_id, tagId: tag.tag_id },
      { method: "post" },
    );
  };

  const restoreTag = (tag: ImprovementTag) => {
    setLocalTags((prev) =>
      prev.map((t) =>
        t.tag_id === tag.tag_id ? { ...t, status: "positive" as ImprovementTagStatus } : t,
      ),
    );
    tagFetcher.submit(
      { intent: "restoreTag", productId: product.product_id, tagId: tag.tag_id },
      { method: "post" },
    );
  };

  const addManualTag = () => {
    const label = newTagLabel.trim();
    if (!label) return;
    const tempTag: ImprovementTag = {
      tag_id: `tmp-${Date.now()}`,
      label,
      tag_type: "merchant",
      status: "forced",
      score: 100,
      source: "merchant",
      locked_by_merchant: true,
    };
    setLocalTags((prev) => [...prev, tempTag]);
    setNewTagLabel("");
    tagFetcher.submit(
      { intent: "addTag", productId: product.product_id, label, tagType: "merchant" },
      { method: "post" },
    );
  };

  const addKeywordTag = (query: string) => {
    const tempTag: ImprovementTag = {
      tag_id: `tmp-${Date.now()}`,
      label: query,
      tag_type: "keyword",
      status: "forced",
      score: 100,
      source: "merchant",
      locked_by_merchant: true,
    };
    setLocalTags((prev) => [...prev, tempTag]);
    tagFetcher.submit(
      { intent: "addTag", productId: product.product_id, label: query, tagType: "keyword" },
      { method: "post" },
    );
  };

  const retireKeywordTag = (query: string) => {
    const existing = localTags.find(
      (t) => t.tag_type === "keyword" && t.label.toLowerCase() === query.toLowerCase(),
    );
    if (existing) {
      retireTag(existing);
    } else {
      const tempTag: ImprovementTag = {
        tag_id: `tmp-${Date.now()}`,
        label: query,
        tag_type: "keyword",
        status: "negative",
        score: 0,
        source: "merchant",
        locked_by_merchant: true,
      };
      setLocalTags((prev) => [...prev, tempTag]);
      tagFetcher.submit(
        { intent: "retireKeyword", productId: product.product_id, label: query, tagType: "keyword" },
        { method: "post" },
      );
    }
  };
  // Hide keywords with zero product fit — they are noise for the merchant.
  const displayedKeywords = product.seo_keywords.filter(
    (keyword) => (keyword.product_fit_score ?? 0) > 0,
  );
  const selectedTargets = product.seo_keywords
    .filter((keyword) => (keyword.target_rank ?? 999) <= 5)
    .slice(0, 5);
  const coverageTargets = selectedTargets.length > 0
    ? selectedTargets
    : product.seo_keywords.slice(0, 5);

  // Coverage badge reflects the saved pack; live edits revalidate on save.
  const coverageByKeyword = new Map(
    coverageTargets.map((keyword) => [
      keyword.query.toLowerCase(),
      keywordCoverage(keyword.query, pack),
    ]),
  );
  const usedKeywords = new Set(
    [...coverageByKeyword.entries()]
      .filter(([, fields]) => fields.length > 0)
      .map(([query]) => query),
  );


  return (
    <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface">
      <BlockStack gap="200">
        <InlineStack gap="200" align="space-between" wrap>
          <BlockStack gap="100">
            <InlineStack gap="150" blockAlign="center">
              <Text as="p" variant="bodyMd" fontWeight="semibold">{product.product_title}</Text>
              {(pack.facts_missing?.length ?? 0) > 0 && (
                <Tooltip content={`${t(locale, "marketAnalysisFactsMissing")} : ${(pack.facts_missing ?? []).join(" · ")}`}>
                  <span style={{ display: "inline-flex", cursor: "help" }}>
                    <Icon source={AlertTriangleIcon} tone="warning" />
                  </span>
                </Tooltip>
              )}
              <NotImprovedIcon elements={product.improvement_elements} locale={locale} />
            </InlineStack>
          </BlockStack>
          <InlineStack gap="200">
            <Badge tone={scoreTone(100 - product.opportunity_score)}>
              {`Potentiel SEO ${100 - product.opportunity_score}/100`}
            </Badge>
            {product.business_profile_context_status === "stale" && (
              <Badge tone="attention">{t(locale, "marketAnalysisProfileContextStaleBadge")}</Badge>
            )}
            {product.business_profile_context_status === "unknown" && (
              <Badge tone="attention">{t(locale, "marketAnalysisProfileContextUnknownBadge")}</Badge>
            )}
            {isAnalyzing ? (
              <Spinner size="small" />
            ) : (
              <Button size="slim" onClick={onAnalyze} disabled={analyzeDisabled}>
                {t(locale, "marketAnalysisAnalyzeOne")}
              </Button>
            )}
            {checkedApplyFields.size > 0 && (
              <Button size="slim" variant="primary" loading={applyLoading} onClick={handleApplyProposals}>
                {fr ? "Valider les propositions" : "Apply proposals"}
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

        <ImprovementTags
          addedTags={addedTags}
          retiredTags={retiredTags}
          openBucket={openBucket}
          onToggle={onToggleBucket}
          onRetire={retireTag}
          onRestore={restoreTag}
          newLabel={newTagLabel}
          onNewLabelChange={setNewTagLabel}
          onAdd={addManualTag}
          locale={locale}
        />

        {applyResult && (
          <Banner tone={applyResult.ok ? "success" : "critical"}>
            {applyResult.ok ? (
              <BlockStack gap="100">
                {Object.entries(applyResult.results ?? {}).map(([field, res]) => (
                  <Text key={field} as="p" variant="bodySm">
                    {field} : {res.applied ? (fr ? "✓ appliqué" : "✓ applied") : `✗ ${res.error ?? (fr ? "échec" : "failed")}`}
                  </Text>
                ))}
              </BlockStack>
            ) : (
              <Text as="p" variant="bodySm">{applyResult.error}</Text>
            )}
          </Banner>
        )}

        <ProductContentProposals
          product={product}
          locale={locale}
          isAnalyzing={isAnalyzing}
          onEnrichAndAnalyze={onEnrichAndAnalyze}
          analyzeDisabled={analyzeDisabled}
          layout="buttons"
          showKeywordSources={false}
          checkedApplyFields={checkedApplyFields}
          onToggleApplyField={onToggleApplyField}
          onRetireQuestion={onRetireQuestion}
          onRestoreQuestion={onRestoreQuestion}
          onValidateQuestion={onValidateQuestion}
        />

        {/* Uncommitted keywords = those not yet in localTags as keyword type */}
        {(() => {
          const uncommitted = displayedKeywords.filter(
            (k) => !keywordTagLabels.has(k.query.toLowerCase()),
          );
          return (
            <InlineStack gap="150" wrap>
              {displayedKeywords.length > 0 && (
                <Button size="slim" pressed={openSection === "keywords"} onClick={() => toggle("keywords")}>
                  {fr
                    ? `Mots-clés (${uncommitted.length})`
                    : `Keywords (${uncommitted.length})`}
                </Button>
              )}
              {pack.recommended_internal_links && pack.recommended_internal_links.length > 0 && (
                <Button size="slim" pressed={openSection === "links"} onClick={() => toggle("links")}>
                  {`${t(locale, "marketAnalysisInternalLinks")} (${pack.recommended_internal_links.length})`}
                </Button>
              )}
            </InlineStack>
          );
        })()}

        {displayedKeywords.length > 0 && (
          <Collapsible id={`kw-${product.product_id}`} open={openSection === "keywords"}>
              <Box paddingBlockStart="200">
                <BlockStack gap="200">
                  {displayedKeywords.filter((k) => !keywordTagLabels.has(k.query.toLowerCase())).map((k, idx) => (
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
                            <Badge tone="attention">{k.query}</Badge>
                            <Badge>{k.intent_type || "—"}</Badge>
                            {(k.target_role === "primary" || k.target_role === "secondary") && (
                              <Badge tone={k.target_role === "primary" ? "success" : "info"}>
                                {k.target_role === "primary"
                                  ? (fr ? "Cible principale" : "Primary target")
                                  : (fr ? "Cible secondaire" : "Secondary target")}
                              </Badge>
                            )}
                            <KeywordSourceBadge source={k.data_source} locale={locale} />
                            {usedKeywords.has(k.query.toLowerCase()) && (
                              <Badge tone="success">
                                {fr ? "Couvert" : "Covered"}
                              </Badge>
                            )}
                          </InlineStack>
                          <InlineStack gap="100" blockAlign="center">
                            {k.priority_score != null && (
                              <Badge tone={scoreTone(k.priority_score)}>
                                {`${fr ? "Priorité" : "Priority"} ${k.priority_score}`}
                              </Badge>
                            )}
                            <Badge
                              tone={
                                k.data_source === "llm_estimated" || k.data_source === "shopify" || k.data_source === "parent_estimated"
                                  ? undefined
                                  : scoreTone(k.demand_score)
                              }
                            >
                              {`${fr ? "Demande" : "Demand"} ${k.demand_score}${
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
                            <Button size="slim" onClick={() => addKeywordTag(k.query)}>
                              {fr ? "Ajouter" : "Add"}
                            </Button>
                            <Button size="slim" variant="plain" tone="critical" onClick={() => retireKeywordTag(k.query)}>
                              {fr ? "Retirer" : "Retire"}
                            </Button>
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
                                  ({fr ? "estimé via" : "estimated via"} « {k.estimated_from_parent} »)
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
                              {fr ? "SERP/PAA vérifié" : "SERP/PAA checked"}
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
        )}

        {pack.recommended_internal_links && pack.recommended_internal_links.length > 0 && (
          <Collapsible id={`links-${product.product_id}`} open={openSection === "links"}>
            <Box paddingBlockStart="200">
              <InternalLinksSection
                links={pack.recommended_internal_links}
                locale={locale}
              />
            </Box>
          </Collapsible>
        )}
      </BlockStack>
    </Box>
  );
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

function InternalLinksSection({
  links,
  locale,
}: {
  links: InternalLinkSuggestion[];
  locale: Locale;
}) {
  const reasonLabel = (reason: InternalLinkSuggestion["reason"]) => {
    if (reason === "sibling_product") return t(locale, "marketAnalysisInternalLinksReasonSibling");
    if (reason === "collection_parent") return t(locale, "marketAnalysisInternalLinksReasonCollection");
    return t(locale, "marketAnalysisInternalLinksReasonArticle");
  };
  return (
    <BlockStack gap="200">
      {links.map((link, i) => (
        <Box
          key={`${link.target_url}-${i}`}
          paddingBlock="200"
          paddingInline="300"
          background="bg-surface-secondary"
          borderRadius="200"
        >
          <BlockStack gap="100">
            <InlineStack gap="200" blockAlign="center">
              <Text as="span" variant="bodySm">
                <strong>{link.target_title || link.target_url}</strong>
              </Text>
              <Badge tone={link.confidence === "high" ? "success" : "info"}>
                {reasonLabel(link.reason)}
              </Badge>
            </InlineStack>
            <Text as="p" variant="bodySm" tone="subdued">
              {link.target_url}
            </Text>
            {link.anchors.length > 0 ? (
              <InlineStack gap="100" wrap>
                {link.anchors.map((anchor, j) => (
                  <Badge key={j}>{anchor}</Badge>
                ))}
              </InlineStack>
            ) : null}
          </BlockStack>
        </Box>
      ))}
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

export default function MarketAnalysisPage() {
  const { locale, shop, latestJob, latestIdentification, gscConnected, ga4Connected, activeHandles, newProducts, removedProductIds } =
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
          // Mark as analyzed so the delta banner hides this product
          setAnalyzedNewIds((prev) => new Set([...prev, updated.product_id]));
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
  // Client-side export of the current analysis as a JSON file the merchant can
  // share (keywords + sources, content packs, GEO questions, data sources used).
  const handleExportResults = () => {
    if (typeof document === "undefined" || !job) return;
    const payload = {
      exported_at: new Date().toISOString(),
      source: "market-analysis",
      analyzed_at: job.analyzed_at,
      analyzed_product_count: job.analyzed_product_count,
      total_opportunity_count: job.total_opportunity_count,
      sources_used: job.sources_used,
      provider_status: job.provider_status,
      business_profile_context: job.business_profile_context,
      products: job.products,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `analyse-marche-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  const handleExportReflection = () => {
    if (typeof document === "undefined" || !job) return;
    const payload = {
      exported_at: new Date().toISOString(),
      source: "market-analysis-reflection-test",
      analyzed_at: job.analyzed_at,
      reflection_test: job.reflection_test === true,
      threshold: job.products.find((product) => product.content_test_pack.content_guardrail_reflection)?.content_test_pack.content_guardrail_reflection?.threshold ?? null,
      products: job.products.map((product) => ({
        product_id: product.product_id,
        product_title: product.product_title,
        product_handle: product.product_handle,
        primary_keyword: product.seo_keywords.find((keyword) => keyword.target_role === "primary")?.query ?? product.seo_keywords[0]?.query ?? null,
        reflection: product.content_test_pack.content_guardrail_reflection ?? null,
        content_quality: product.content_test_pack.content_quality ?? null,
      })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `analyse-marche-reflection-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

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
      title={t(locale, "marketAnalysis")}
      subtitle={t(locale, "marketAnalysisSubtitle")}
      backAction={{
        content: t(locale, "hubInsights"),
        url: localizedPath("/app/insights", locale),
      }}
    >
      <BlockStack gap="400">
        {!gscConnected && (
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
        )}

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
            )}

            {/* Error */}
            {anyError && (
              <Banner tone="critical">
                <Text as="p">{anyError}</Text>
              </Banner>
            )}

            {/* Summary + export */}
            {job && job.analyzed_product_count > 0 && (
              <>
                <InlineStack align="end" gap="200">
                  {job.reflection_test === true && (
                    <Badge tone="info">
                      {locale === "fr" ? "Mode réflexion test" : "Reflection test mode"}
                    </Badge>
                  )}
                  <Button onClick={handleExportResults}>
                    {t(locale, "marketAnalysisExport")}
                  </Button>
                  <Button onClick={handleExportReflection}>
                    {locale === "fr" ? "Télécharger la réflexion" : "Download reflection"}
                  </Button>
                </InlineStack>
                <SummaryCard
                  job={job}
                  locale={locale}
                  onAnalyzeAll={() => setShowRerunModal(true)}
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
                        onAnalyze={() => handleAnalyzeSingle(product.product_id)}
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
