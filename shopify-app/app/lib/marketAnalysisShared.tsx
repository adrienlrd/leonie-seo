/**
 * Shared types and pure helpers for market-analysis content proposals.
 *
 * Used by both the market-analysis route and the dashboard active-products
 * panel so the per-product content proposals render identically in both places.
 */

import { Badge } from "@shopify/polaris";
import type { ReactNode } from "react";
import { t, type Locale } from "./i18n";

// ── Types ───────────────────────────────────────────────────────────────────

export type KeywordSource =
  | "gsc"
  | "ga4"
  | "trends"
  | "shopify"
  | "llm_estimated"
  | "llm_proposed"
  | "google_suggest"
  | "dataforseo"
  | "google_ads"
  | "parent_estimated";
export type DifficultySource = "free_estimated" | "dataforseo" | "google_ads";

export type IntentTypeSource = "serp_classified" | "llm_guessed" | "unclassified";
export type SerpFeatureTarget = "paa" | "featured_snippet" | "ai_overview";

export interface SeoKeyword {
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

export interface KeywordCluster {
  cluster_id: string;
  head_keyword: string;
  member_queries: string[];
}

export interface CannibalizationAlertProduct {
  product_id: string;
  product_title: string;
  product_url: string;
  primary_keyword: string;
  gsc_impressions: number;
  opportunity_score: number;
}

export interface CannibalizationAlert {
  cluster_head: string;
  cluster_key: string[];
  product_ids: string[];
  products: CannibalizationAlertProduct[];
  winner_suggested: string;
  action: "reorient_secondary";
}

export interface GeoQuestion {
  question: string;
  answer_angle: string;
  content_block_type: string;
  confidence: string;
}

export interface ContentQuality {
  publish_ready: boolean;
  issues: string[];
  advisories?: string[];
  covered_target_count?: number;
  target_count?: number;
  evidence_ledger?: { claim: string; facts: { key: string; source: string }[] }[];
  skipped_surfaces?: string[];
}

export interface EnrichmentQuestion {
  key: string;
  question: string;
  placeholder: string;
  why_it_matters: string;
  target_keyword: string;
  unlocks_surfaces: string[];
}

export interface ContentGuardrailReflection {
  enabled: boolean;
  threshold: number;
  max_retries: number;
  retry_count: number;
  final_score: number;
  final_status: "pass" | "needs_retry" | "blocked";
  questions: { key: string; question: string }[];
  attempts: {
    attempt: number;
    score: number;
    status: "pass" | "needs_retry" | "blocked";
    questions: {
      key: string;
      question: string;
      score: number;
      status: "pass" | "needs_review" | "blocked";
      evidence: string[];
      recommendation: string;
    }[];
    quality_issues?: string[];
  }[];
}

export interface ConfirmedFact {
  key: string;
  label: string;
  value: string | string[];
  source: string;
  confidence: string;
}

export interface ContentTestPack {
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
  proposed_blog_ideas?: BlogIdea[];
  facts_used: string[];
  facts_missing: string[];
  confidence: string;
  confirmed_facts?: ConfirmedFact[];
  content_quality?: ContentQuality;
  enrichment_questions?: EnrichmentQuestion[];
  retired_question_keys?: string[];
  retired_questions?: EnrichmentQuestion[];
  completed_questions?: Array<{ key: string; question: string; why_it_matters: string; placeholder: string; is_retired: boolean; answer: string }>;
  content_guardrail_reflection?: ContentGuardrailReflection;
  current_product_images?: { id: string; url: string; current_alt: string | null }[];
  proposed_image_alts?: { image_id: string; proposed_alt: string }[];
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

export interface BlogIdea {
  title: string;
  target_keyword: string;
  intro: string;
  outline: string[];
}

export type ImprovementTagStatus = "positive" | "neutral" | "negative" | "forced";

export interface ImprovementTag {
  tag_id: string;
  label: string;
  tag_type: "keyword" | "analysis_axis" | "content_axis" | "risk" | "merchant";
  status: ImprovementTagStatus;
  score: number;
  source: string;
  locked_by_merchant: boolean;
  reason?: string;
}

export interface ImprovementElement {
  key: string;
  label: string;
  improved: boolean;
  status: "improved" | "not_improved";
}

export interface CompetitorInternalLinkExample {
  href: string;
  anchor: string;
  target_type: "product" | "collection" | "blog" | "faq" | "other" | string;
}

export interface CompetitorCrawlTopUrl {
  url: string;
  final_url?: string;
  domain: string;
  rank: number;
  keyword: string;
  keyword_intent_type?: string;
  title: string;
  page_type?: string;
  feature_summary?: {
    has_faq_block?: boolean;
    has_product_schema?: boolean;
    has_breadcrumb_schema?: boolean;
    word_count?: number;
    internal_link_count?: number;
  };
  seo?: {
    title?: string;
    title_length?: number;
    title_keyword_present?: boolean;
    title_promise_detected?: boolean;
    meta_description?: string;
    meta_description_length?: number;
    meta_keyword_present?: boolean;
    meta_has_commercial_angle?: boolean;
    meta_has_cta?: boolean;
    canonical_present?: boolean;
  };
  structure?: {
    h1_count?: number;
    h1_text?: string;
    h2_count?: number;
    h2_texts?: string[];
    h3_count?: number;
    h3_texts?: string[];
    word_count?: number;
    paragraph_count?: number;
    has_bullet_lists?: boolean;
    has_comparison_table?: boolean;
    has_product_specs_table?: boolean;
    has_pros_cons?: boolean;
    has_buying_guide?: boolean;
    has_how_to_structure?: boolean;
    has_breadcrumb_block?: boolean;
    breadcrumb_structure?: string;
  };
  geo_aeo?: {
    has_faq_block?: boolean;
    faq_question_count?: number;
    has_short_answer_block?: boolean;
    short_answer_block_count?: number;
    has_definition_block?: boolean;
    answerability_score?: number;
    ai_readability_score?: number;
  };
  schema?: {
    jsonld_count?: number;
    schema_types?: string[];
    has_product_schema?: boolean;
    has_offer_schema?: boolean;
    has_breadcrumb_schema?: boolean;
    has_faq_schema?: boolean;
    has_article_schema?: boolean;
    has_organization_schema?: boolean;
    schema_completeness_score?: number;
  };
  links?: {
    internal_link_count?: number;
    external_link_count?: number;
    internal_link_examples?: CompetitorInternalLinkExample[];
    product_link_count?: number;
    collection_link_count?: number;
    blog_link_count?: number;
  };
  images?: {
    image_count?: number;
    image_alt_count?: number;
    images_missing_alt_count?: number;
    descriptive_image_alt_count?: number;
    image_alt_examples?: string[];
  };
  trust?: {
    has_reviews_or_social_proof?: boolean;
    has_trust_proof?: boolean;
    trust_proof_types?: string[];
  };
  product_depth?: {
    materials?: boolean;
    dimensions?: boolean;
    usage?: boolean;
    compatibility?: boolean;
    care?: boolean;
  };
  serp?: {
    paa_questions?: string[];
    featured_snippet?: string | null;
    featured_snippet_present?: boolean;
    serp_feature_targets?: string[];
  };
}

export interface CompetitorCrawlGap {
  gap: string;
  action_type: string;
  priority_boost: number;
  reason: string;
}

export interface CompetitorCrawlInsights {
  enabled: boolean;
  sample_size: number;
  top_urls: CompetitorCrawlTopUrl[];
  dominant_patterns: Record<string, number | string | boolean>;
  merchant_gaps: CompetitorCrawlGap[];
  priority_boost_total: number;
  prompt_summary: string;
}

export interface ProductResult {
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
  keyword_clusters?: KeywordCluster[];
  improvement_tags?: ImprovementTag[];
  improvement_elements?: ImprovementElement[];
  competitor_crawl_insights?: CompetitorCrawlInsights;
  competitor_pattern_boost?: number;
  competitor_pattern_gaps?: CompetitorCrawlGap[];
  opportunity_score_before_competitor_boost?: number;
}

// ── Competitor SERP page types ────────────────────────────────────────────────

export interface CompetitorSerpUrl extends CompetitorCrawlTopUrl {
  from_cache?: boolean;
  error?: string;
  blocked_by_robots?: boolean;
}

export interface CompetitorSerpDomain {
  domain: string;
  source: "serp_per_product" | "domain_level" | "manual" | string;
  estimated_strength: number;
  urls: CompetitorSerpUrl[];
}

export interface CompetitorSerpResult {
  created_at: string;
  shop?: string;
  competitors: CompetitorSerpDomain[];
  total_urls_crawled: number;
  keywords_used: number;
  error?: string;
}

// ── Pure helpers ──────────────────────────────────────────────────────────────

export function scoreTone(score: number): "success" | "warning" | "critical" {
  if (score >= 65) return "success";
  if (score >= 35) return "warning";
  return "critical";
}

export function confidenceTone(c: string): "success" | "warning" | "critical" | "info" {
  if (c === "high") return "success";
  if (c === "medium") return "warning";
  if (c === "low") return "critical";
  return "info";
}

const FR_STOP_WORDS = new Set([
  "de", "du", "la", "le", "les", "des", "pour", "avec", "sans", "sur", "par",
  "en", "au", "aux", "un", "une", "et", "ou", "à", "dans", "que", "qui", "ne",
  "pas", "se", "ce", "cet", "cette", "ces", "mon", "ma", "mes", "son", "sa",
  "ses", "nos", "vos", "leur", "leurs", "est", "sont", "être", "avoir",
]);

export function contentWords(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[\s\-_/]+/)
    .map((w) => w.replace(/[^a-zàâäéèêëîïôùûüç]/g, ""))
    .filter((w) => w.length >= 3 && !FR_STOP_WORDS.has(w));
}

export function keywordIsUsed(keyword: string, proposalWords: string[]): boolean {
  const kwWords = contentWords(keyword);
  if (kwWords.length === 0) return false;
  return kwWords.every((kw) =>
    proposalWords.some(
      (pw) =>
        pw === kw ||
        pw === kw + "s" ||
        pw === kw + "x" ||
        pw === kw + "es" ||
        kw === pw + "s" ||
        kw === pw + "x",
    ),
  );
}

export function keywordCoverage(keyword: string, pack: ContentTestPack): string[] {
  const fields: Array<[string, string]> = [
    ["Meta title", pack.proposed_meta_title],
    ["Meta description", pack.proposed_meta_description],
    ["Description", pack.proposed_product_description],
    ["FAQ", (pack.proposed_faq ?? []).map((item) => `${item.q} ${item.a}`).join(" ")],
    ["GEO", pack.proposed_geo_answer_block],
    ["Blog", [pack.proposed_blog_title, pack.proposed_blog_intro, ...(pack.proposed_blog_outline ?? [])].join(" ")],
    ["Image alts", (pack.proposed_image_alts ?? []).map((a) => a.proposed_alt).join(" ")],
  ];
  return fields
    .filter(([, text]) => keywordIsUsed(keyword, contentWords(text)))
    .map(([label]) => label);
}

export function qualityIssueLabel(issue: string, locale: Locale): string {
  const labels: Record<string, [string, string]> = {
    missing_primary_keyword_target: ["Aucune cible principale fiable", "No reliable primary target"],
    meta_title_missing_primary_target: ["Cible principale absente du meta title", "Primary target missing from meta title"],
    meta_description_missing_primary_target: ["Cible principale absente de la meta description", "Primary target missing from meta description"],
    description_missing_primary_target: ["Cible principale absente de la description", "Primary target missing from description"],
    description_has_insufficient_target_coverage: ["Description trop peu alignée aux cibles", "Description has insufficient target coverage"],
    faq_missing_available_paa_question: ["FAQ non alignée aux questions SERP disponibles", "FAQ does not cover available SERP questions"],
    faq_missing_primary_target: ["FAQ non alignée au mot-clé principal", "FAQ does not cover the primary target"],
    missing_geo_answer_block: ["Bloc de réponse GEO manquant", "GEO answer block is missing"],
    missing_recommended_product_description: ["Description recommandée mais non générée", "Recommended description was not generated"],
    product_description_too_generic: ["Description trop courte ou générique pour être publiée automatiquement", "Description is too short or generic for automated publishing"],
    unjustified_product_description_surface: ["Description générée sans faits suffisants", "Description generated without enough supporting facts"],
    missing_recommended_faq: ["FAQ justifiée mais non générée", "Supported FAQ was not generated"],
    unjustified_faq_surface: ["FAQ générée sans question ou preuve suffisante", "FAQ generated without sufficient question or factual evidence"],
    unjustified_geo_answer_surface: ["Réponse GEO générée sans faits suffisants", "GEO answer generated without enough supporting facts"],
    missing_recommended_blog_support: ["Contenu support recommandé mais non généré", "Recommended support content was not generated"],
    blog_missing_primary_target: ["Article support non aligné au mot-clé principal", "Support article does not cover the primary target"],
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

export function highlightKeywords(text: string, keywords: string[]): ReactNode {
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

export function surfaceLabel(surface: string, locale: Locale): string {
  const labels: Record<string, [string, string]> = {
    product_description: ["description produit", "product description"],
    faq: ["FAQ", "FAQ"],
    geo_answer: ["réponse GEO", "GEO answer"],
    blog: ["article support", "support article"],
  };
  const label = labels[surface];
  return label ? label[locale === "fr" ? 0 : 1] : surface;
}

export function qualityAdvisoryLabel(advisory: string, locale: Locale): string {
  const labels: Record<string, [string, string]> = {
    meta_title_length_outside_guideline: ["Longueur du meta title à surveiller", "Review meta title length"],
    meta_description_length_outside_guideline: ["Longueur de la meta description à surveiller", "Review meta description length"],
  };
  const label = labels[advisory];
  return label ? label[locale === "fr" ? 0 : 1] : advisory;
}

export function qualityWarningText(pack: ContentTestPack, locale: Locale): string {
  const quality = pack.content_quality;
  if (!quality) return "";
  const parts: string[] = [];
  if (!quality.publish_ready && (quality.issues?.length ?? 0) > 0) {
    const prefix = locale === "fr" ? "À corriger avant publication" : "Fix before publishing";
    parts.push(`${prefix} : ${(quality.issues ?? []).map((issue) => qualityIssueLabel(issue, locale)).join(" · ")}`);
  }
  if ((quality.skipped_surfaces?.length ?? 0) > 0) {
    const prefix = locale === "fr"
      ? "Non généré faute de preuve ou d'intention suffisante"
      : "Not generated due to insufficient evidence or intent";
    parts.push(`${prefix} : ${quality.skipped_surfaces!.map((surface) => surfaceLabel(surface, locale)).join(", ")}`);
  }
  return parts.join(" — ");
}

/**
 * Badge showing where a keyword's metrics come from. Real-data sources (GSC,
 * DataForSEO, GA4, Suggest, Trends) render as positive/info; estimated sources
 * (AI-proposed/estimated, parent-extrapolated) render as a cautionary badge so the
 * merchant can tell observed demand from a guess at a glance.
 */
export function KeywordSourceBadge({
  source,
  locale,
}: {
  source: KeywordSource | undefined;
  locale: Locale;
}): ReactNode {
  if (!source) return null;
  switch (source) {
    case "gsc":
      return <Badge tone="success">{t(locale, "marketAnalysisSourceGsc")}</Badge>;
    case "dataforseo":
      return <Badge tone="success">{t(locale, "marketAnalysisSourceDataforseo")}</Badge>;
    case "ga4":
      return <Badge tone="success">{t(locale, "marketAnalysisSourceGa4")}</Badge>;
    case "google_suggest":
      return <Badge tone="info">{t(locale, "marketAnalysisSourceSuggest")}</Badge>;
    case "trends":
      return <Badge tone="info">{t(locale, "marketAnalysisSourceTrends")}</Badge>;
    case "shopify":
      return <Badge tone="info">{t(locale, "marketAnalysisSourceShopify")}</Badge>;
    case "parent_estimated":
      return (
        <Badge tone="info">{locale === "fr" ? "Estimé via parent" : "Parent-estimated"}</Badge>
      );
    case "llm_proposed":
      return <Badge tone="attention">{t(locale, "marketAnalysisSourceLlmProposed")}</Badge>;
    default:
      return <Badge tone="attention">{t(locale, "marketAnalysisSourceLlm")}</Badge>;
  }
}

export function merchantAnswersFromPack(pack: ContentTestPack): Record<string, string> {
  const answers: Record<string, string> = {};
  for (const fact of (pack.confirmed_facts ?? [])) {
    if (fact.source === "merchant_confirmation" && fact.key) {
      answers[fact.key] = Array.isArray(fact.value)
        ? fact.value.join(", ")
        : String(fact.value ?? "");
    }
  }
  return answers;
}
