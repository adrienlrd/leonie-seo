import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import type { ShouldRevalidateFunction } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  FormLayout,
  Icon,
  InlineGrid,
  InlineStack,
  Modal,
  Page,
  ProgressBar,
  Spinner,
  Text,
  TextField,
  Tooltip,
} from "@shopify/polaris";
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  BookOpenIcon,
  CalendarIcon,
  CameraIcon,
  ChartHistogramGrowthIcon,
  CheckCircleIcon,
  CompassIcon,
  ContentIcon,
  EyeDropperIcon,
  FlowerIcon,
  FoodIcon,
  GamesIcon,
  GaugeIcon,
  GlobeIcon,
  HeartIcon,
  HomeIcon,
  MegaphoneIcon,
  MicrophoneIcon,
  NatureIcon,
  PersonIcon,
  PhoneIcon,
  ProductIcon,
  RefreshIcon,
  SportsIcon,
  StarFilledIcon,
  StoreIcon,
  WatchIcon,
} from "@shopify/polaris-icons";
import type { IconSource } from "@shopify/polaris";
import React, { useEffect, useRef, useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { Sparkline } from "../components/Sparkline";
import { ProductContentProposals } from "../components/ProductContentProposals";
import { qualityWarningText, type ProductResult } from "../lib/marketAnalysisShared";

interface MarketJobState {
  status: "pending" | "running" | "completed" | "failed";
  products: ProductResult[];
  progress?: number;
  total?: number;
  analyzed_product_count?: number;
  error?: string | null;
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface SparkPoint {
  date: string;
  value: number;
}

interface ActiveProduct {
  id: string;
  title: string;
  handle: string;
  image_url: string | null;
  gsc_visible: boolean;
  gsc_connected: boolean;
  gsc_issues: string[];
}

interface PriorityAction {
  action_id: string;
  rank: number;
  why_now: string;
  estimates?: { effort?: string; impact?: string };
  preview?: { product_title?: string; action_label?: string };
}

interface PendingStep {
  key: string;
  label: string;
}

interface Alert {
  type: string;
  severity: string;
  message: string;
  url?: string | null;
}

interface DashboardData {
  shop: string;
  plan: string;
  health: string;
  llm_budget: { used_usd: number; limit_usd: number; pct: number };
  zone1: {
    global_score: number | null;
    global_level: string | null;
    products_in_scope: number;
    niche_summary: string | null;
    niche_validated: boolean;
    niche_available: boolean;
    sub_scores: { seo: number; geo: number; content: number; technical: number } | null;
  };
  zone2: {
    actions: PriorityAction[];
    sparse_signal: boolean;
    no_action_reason: string | null;
  };
  zone3: {
    active_optimizations_count: number;
    next_milestone_at: string | null;
    search_performance_sparkline: SparkPoint[];
    trend: string;
  };
  zone4: { completed_steps: string[]; pending_steps: PendingStep[] };
  zone5: { alerts: Alert[] };
  zone6: { ai_visibility_enabled: boolean; available_in: string };
  banners: {
    pilot_safe: boolean;
    stale_snapshot: boolean;
    bulk_apply_in_progress: { running: boolean; current: number; total: number };
  };
  generated_at: string;
}

// ── Business profile types ────────────────────────────────────────────────────

interface BusinessPersona {
  name: string;
  description: string;
  main_need: string;
  buying_trigger: string;
}

interface ContentStyle {
  tone: string;
  typical_article_length: string;
  h2_structure: string[];
  vocabulary_to_use: string[];
  vocabulary_to_avoid: string[];
  hook_patterns: string[];
}

interface BusinessProfile {
  niche_summary: string;
  brand_name: string;
  brand_voice: string;
  target_personas: BusinessPersona[];
  content_style: ContentStyle;
  key_themes: string[];
  seasonal_patterns: Array<{ period: string; theme: string; intensity: string }>;
  competitor_domains: string[];
  competitor_insights: string[];
  content_gaps: string[];
  internal_link_priorities: string[];
  generated_at: string;
  status: "draft" | "validated" | "error";
  sources_used?: string[];
}

interface LoaderData {
  shop: string;
  locale: Locale;
  plan: string;
  dashboard: DashboardData | null;
  activeProducts: ActiveProduct[];
  productResults: Record<string, ProductResult>;
  competitorSignals: string[];
  auditJobId: string | null;
  businessProfile: BusinessProfile | null;
  error: string | null;
}

// ── Loader ────────────────────────────────────────────────────────────────────

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const url = new URL(request.url);
  const plan = (url.searchParams.get("plan") ?? "free") as "free" | "pro" | "agency";

  let activeProducts: ActiveProduct[] = [];
  let productResults: Record<string, ProductResult> = {};
  let competitorSignals: string[] = [];
  let auditJobId: string | null = null;
  let businessProfile: BusinessProfile | null = null;

  try {
    const [dashResp, productsResp, bizProfileResp, marketResp] = await Promise.allSettled([
      callBackendForShop(shop, `/api/shops/${shop}/dashboard?plan=${plan}`, { accessToken: session.accessToken }),
      callBackendForShop(shop, `/api/shops/${shop}/products/active`, { accessToken: session.accessToken }),
      callBackendForShop(shop, `/api/shops/${shop}/business-profile/latest`, { accessToken: session.accessToken }),
      callBackendForShop(shop, `/api/shops/${shop}/market-analysis/latest`, { accessToken: session.accessToken }),
    ]);

    if (productsResp.status === "fulfilled" && productsResp.value.ok) {
      try {
        activeProducts = (await productsResp.value.json()) as ActiveProduct[];
      } catch (_parseErr) { /* ignore */ }
    }

    if (bizProfileResp.status === "fulfilled" && bizProfileResp.value.ok) {
      try {
        businessProfile = (await bizProfileResp.value.json()) as BusinessProfile;
      } catch (_parseErr) { /* ignore */ }
    }

    // Index analyzed product packs by id and handle so the active-products panel
    // can reveal generated content proposals per product. Also surface the
    // detected competitor domains on the dashboard "Concurrents" card.
    if (marketResp.status === "fulfilled" && marketResp.value.ok) {
      try {
        const job = (await marketResp.value.json()) as {
          products?: ProductResult[];
          competitor_signals?: { domain?: string }[];
        };
        for (const result of job.products ?? []) {
          if (result.product_id) productResults[result.product_id] = result;
          if (result.product_handle) productResults[result.product_handle] = result;
        }
        competitorSignals = [
          ...new Set(
            (job.competitor_signals ?? [])
              .map((c) => (c.domain ?? "").trim())
              .filter(Boolean),
          ),
        ];
      } catch (_parseErr) { /* ignore */ }
    }

    if (dashResp.status !== "fulfilled" || !dashResp.value.ok) {
      const errStatus = dashResp.status === "fulfilled" ? dashResp.value.status : 0;
      return json<LoaderData>({
        shop, locale, plan,
        dashboard: null,
        activeProducts,
        productResults,
        competitorSignals,
        auditJobId: null,
        businessProfile,
        error: errStatus ? `HTTP ${errStatus}` : "Network error",
      });
    }

    const dashboard = (await dashResp.value.json()) as DashboardData;

    if (!dashboard.zone1.niche_available) {
      return redirect(localizedPath("/app/onboarding", locale));
    }

    return json<LoaderData>({ shop, locale, plan, dashboard, activeProducts, productResults, competitorSignals, auditJobId, businessProfile, error: null });
  } catch (err) {
    return json<LoaderData>({
      shop, locale, plan,
      dashboard: null,
      activeProducts,
      productResults,
      competitorSignals,
      auditJobId,
      businessProfile,
      error: err instanceof Error ? err.message : "Network error",
    });
  }
};

// ── Action (refresh + audit job polling) ──────────────────────────────────────

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);
  const formData = await request.formData();
  const intent = formData.get("intent") as string | null;

  // Manual refresh — fire seo_audit + gsc_import (pages only) and return the audit job ID.
  if (intent === "refresh") {
    try {
      const resp = await callBackendForShop(session.shop, "/api/jobs", {
        accessToken: session.accessToken,
        method: "POST",
        body: JSON.stringify({
          queue: "seo_audit",
          payload: { include_content_pages: false, force: true },
          max_retries: 1,
        }),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        return json({ type: "refresh", jobId: null, error: `HTTP ${resp.status}: ${txt}` });
      }
      const data = (await resp.json()) as { job_id: string };

      // Also kick off a lightweight GSC sync (pages-only, no retry if not connected).
      try {
        await callBackendForShop(session.shop, "/api/jobs", {
          method: "POST",
          body: JSON.stringify({
            queue: "gsc_import",
            payload: { days: 28, pages_only: true },
            max_retries: 1,
          }),
        });
      } catch { /* non-fatal — GSC might not be connected */ }

      return json({ type: "refresh", jobId: data.job_id, error: null });
    } catch (err) {
      return json({ type: "refresh", jobId: null, error: String(err) });
    }
  }

  if (intent === "startBusinessAnalysis" || intent === "startFullAnalysis") {
    try {
      let shopName = "";
      try {
        const shopResp = await admin.graphql(`#graphql
          query { shop { name } }
        `);
        const shopData = (await shopResp.json()) as { data?: { shop?: { name?: string } } };
        shopName = shopData.data?.shop?.name ?? "";
      } catch { /* non-fatal */ }

      const rawKeywords = formData.get("focusKeywords");
      const focusKeywords: string[] = rawKeywords ? (JSON.parse(rawKeywords as string) as string[]) : [];

      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/business-profile/analyze`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify({ shop_name: shopName, focus_keywords: focusKeywords }),
        },
      );
      if (!resp.ok) {
        const txt = await resp.text();
        return json({ type: intent, jobId: null, error: `HTTP ${resp.status}: ${txt}` });
      }
      const data = (await resp.json()) as { job_id: string };
      return json({ type: intent, jobId: data.job_id, error: null });
    } catch (err) {
      return json({ type: intent, jobId: null, error: String(err) });
    }
  }

  if (intent === "pollBusinessAnalysis") {
    const bizJobId = formData.get("bizJobId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/business-profile/job/${bizJobId}`,
        { accessToken: session.accessToken },
      );
      if (!resp.ok) return json({ type: "pollBusinessAnalysis", status: "unknown", profile: null, error: `HTTP ${resp.status}` });
      const job = (await resp.json()) as { status: string; profile?: BusinessProfile | null; error?: string | null };
      const jobError = (job.status === "failed" || job.status === "unknown") ? (job.error ?? "Analyse échouée") : null;
      return json({ type: "pollBusinessAnalysis", status: job.status, profile: job.profile ?? null, error: jobError });
    } catch (err) {
      return json({ type: "pollBusinessAnalysis", status: "unknown", profile: null, error: String(err) });
    }
  }

  if (intent === "pollFullBusinessAnalysis") {
    const bizJobId = formData.get("bizJobId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/business-profile/job/${bizJobId}`,
        { accessToken: session.accessToken },
      );
      if (!resp.ok) {
        return json({
          type: "pollFullBusinessAnalysis",
          status: "unknown",
          profile: null,
          productJobId: null,
          error: `HTTP ${resp.status}`,
        });
      }
      const job = (await resp.json()) as {
        status: string;
        profile?: BusinessProfile | null;
        error?: string | null;
      };
      const jobError =
        job.status === "failed" || job.status === "unknown"
          ? (job.error ?? "Analyse échouée")
          : null;
      if (job.status !== "completed" || !job.profile || job.profile.status === "error") {
        return json({
          type: "pollFullBusinessAnalysis",
          status: job.status,
          profile: job.profile ?? null,
          productJobId: null,
          error: jobError,
        });
      }

      const saveResp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/business-profile`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify(job.profile),
        },
      );
      if (!saveResp.ok) {
        const txt = await saveResp.text();
        return json({
          type: "pollFullBusinessAnalysis",
          status: "failed",
          profile: job.profile,
          productJobId: null,
          error: `HTTP ${saveResp.status}: ${txt}`,
        });
      }
      const savedProfile = (await saveResp.json()) as BusinessProfile;

      const productResp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs`,
        { accessToken: session.accessToken, method: "POST" },
      );
      if (!productResp.ok) {
        const txt = await productResp.text();
        return json({
          type: "pollFullBusinessAnalysis",
          status: "failed",
          profile: savedProfile,
          productJobId: null,
          error: `HTTP ${productResp.status}: ${txt}`,
        });
      }
      const productData = (await productResp.json()) as { job_id: string };
      return json({
        type: "pollFullBusinessAnalysis",
        status: "completed",
        profile: savedProfile,
        productJobId: productData.job_id,
        error: null,
      });
    } catch (err) {
      return json({
        type: "pollFullBusinessAnalysis",
        status: "unknown",
        profile: null,
        productJobId: null,
        error: String(err),
      });
    }
  }

  if (intent === "startProductAnalysis") {
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs`,
        { accessToken: session.accessToken, method: "POST" },
      );
      if (!resp.ok) {
        const txt = await resp.text();
        return json({ type: "startProductAnalysis", jobId: null, error: `HTTP ${resp.status}: ${txt}` });
      }
      const data = (await resp.json()) as { job_id: string };
      return json({ type: "startProductAnalysis", jobId: data.job_id, error: null });
    } catch (err) {
      return json({ type: "startProductAnalysis", jobId: null, error: String(err) });
    }
  }

  if (intent === "pollProductAnalysis") {
    const productJobId = formData.get("productJobId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs/${productJobId}`,
        { accessToken: session.accessToken },
      );
      if (!resp.ok) return json({ type: "pollProductAnalysis", job: null, error: `HTTP ${resp.status}` });
      const job = (await resp.json()) as MarketJobState;
      return json({ type: "pollProductAnalysis", job, error: null });
    } catch (err) {
      return json({ type: "pollProductAnalysis", job: null, error: String(err) });
    }
  }

  if (intent === "saveBusinessProfile") {
    const profileJson = formData.get("profileJson") as string;
    try {
      const profileData = JSON.parse(profileJson) as BusinessProfile;
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/business-profile`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify(profileData),
        },
      );
      if (!resp.ok) {
        const txt = await resp.text();
        return json({ type: "saveBusinessProfile", profile: null, error: `HTTP ${resp.status}: ${txt}` });
      }
      const saved = (await resp.json()) as BusinessProfile;
      return json({ type: "saveBusinessProfile", profile: saved, error: null });
    } catch (err) {
      return json({ type: "saveBusinessProfile", profile: null, error: String(err) });
    }
  }

  // ── Single-product market analysis (mirror of app.market-analysis) ────────
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
          },
        );
        if (!saveResp.ok) {
          const err = await saveResp.text();
          return json({ type: "startSingle", jobId: null, productId, error: `HTTP ${saveResp.status}: ${err}` });
        }
      }
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs?product_ids=${encodeURIComponent(productId)}&persist_product_result=true`,
        { accessToken: session.accessToken, method: "POST" },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "startSingle", jobId: null, productId, error: `HTTP ${resp.status}: ${err}` });
      }
      const data = (await resp.json()) as { job_id: string };
      return json({ type: "startSingle", jobId: data.job_id, productId, error: null });
    } catch (err) {
      return json({ type: "startSingle", jobId: null, productId, error: String(err) });
    }
  }

  if (intent === "pollSingle") {
    const singleJobId = formData.get("jobId") as string;
    const productId = formData.get("productId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/jobs/${singleJobId}`,
        { accessToken: session.accessToken },
      );
      if (!resp.ok) return json({ type: "pollSingle", job: null, productId, error: `HTTP ${resp.status}` });
      const job = (await resp.json()) as MarketJobState;
      return json({ type: "pollSingle", job, productId, error: null });
    } catch (err) {
      return json({ type: "pollSingle", job: null, productId, error: String(err) });
    }
  }

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
        },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ type: "saveProposals", error: `HTTP ${resp.status}: ${err}` });
      }
      return json({ type: "saveProposals", error: null });
    } catch (err) {
      return json({ type: "saveProposals", error: String(err) });
    }
  }

  // Default — poll a known audit job.
  const jobId = formData.get("jobId") as string;
  try {
    const resp = await callBackendForShop(session.shop, `/api/jobs/${jobId}`, {
      accessToken: session.accessToken,
    });
    if (!resp.ok) return json({ type: "poll", status: "unknown", error: `HTTP ${resp.status}` });
    const job = (await resp.json()) as { status: string; result?: { status?: string } };
    return json({
      type: "poll",
      status: job.status,
      // Surface "skipped_fresh" so the UI can show a distinct message.
      resultStatus: job.result?.status ?? null,
      error: null,
    });
  } catch (err) {
    return json({ type: "poll", status: "unknown", error: String(err) });
  }
};

// ── Revalidation guard — polling and refresh must not re-run the loader ─────

export const shouldRevalidate: ShouldRevalidateFunction = ({ formData }) => {
  if (formData?.get("jobId")) return false;
  if (formData?.get("bizJobId")) return false;
  const intent = formData?.get("intent");
  if (intent === "refresh") return false;
  if (intent === "startBusinessAnalysis") return false;
  if (intent === "startFullAnalysis") return false;
  if (intent === "pollBusinessAnalysis") return false;
  if (intent === "pollFullBusinessAnalysis") return false;
  if (intent === "startProductAnalysis") return false;
  if (intent === "pollProductAnalysis") return false;
  if (intent === "saveBusinessProfile") return false;
  if (intent === "startSingle") return false;
  if (intent === "saveFactsAndStartSingle") return false;
  if (intent === "pollSingle") return false;
  if (intent === "saveProposals") return false;
  return true;
};

// ── Score level helpers ────────────────────────────────────────────────────────

const LEVEL_TONES: Record<string, "success" | "info" | "warning" | "critical"> = {
  excellent: "success",
  bon: "info",
  good: "info",
  partiel: "warning",
  partial: "warning",
  faible: "critical",
  low: "critical",
};

const LEVEL_I18N_KEYS: Record<string, string> = {
  excellent: "levelExcellent",
  bon: "levelBon",
  good: "levelBon",
  partiel: "levelPartiel",
  partial: "levelPartiel",
  faible: "levelFaible",
  low: "levelFaible",
};

const SEV_TONES: Record<string, "critical" | "warning" | "info"> = {
  critical: "critical",
  error: "critical",
  warning: "warning",
  info: "info",
};

// ── Sub-components ────────────────────────────────────────────────────────────

function DashboardHeader({
  shop,
  plan,
  budget,
  locale,
}: {
  shop: string;
  plan: string;
  budget: DashboardData["llm_budget"];
  locale: Locale;
}) {
  const planTone = plan === "agency" ? "success" : plan === "pro" ? "info" : undefined;
  return (
    <Card>
      <InlineStack align="space-between" blockAlign="center" wrap={false}>
        <InlineStack gap="200" blockAlign="center" align="start">
          <Text as="p" variant="bodyMd" fontWeight="semibold">{shop}</Text>
          <Badge tone={planTone}>{plan.charAt(0).toUpperCase() + plan.slice(1)}</Badge>
        </InlineStack>
        <Tooltip content={t(locale, "dashboardHeaderLLMBudget")}>
          <BlockStack gap="050">
            <Text as="p" variant="bodySm" tone="subdued">
              {t(locale, "dashboardHeaderLLMBudget")}
            </Text>
            <InlineStack gap="100" blockAlign="center">
              <Text as="p" variant="bodyMd">
                {budget.used_usd.toFixed(2)} $ / {budget.limit_usd.toFixed(0)} $
              </Text>
              <ProgressBar
                progress={Math.min(budget.pct, 100)}
                tone={budget.pct >= 80 ? "critical" : "highlight"}
                size="small"
              />
            </InlineStack>
          </BlockStack>
        </Tooltip>
      </InlineStack>
    </Card>
  );
}

const SUB_SCORE_KEYS: Array<{ key: keyof NonNullable<DashboardData["zone1"]["sub_scores"]>; i18n: string }> = [
  { key: "seo", i18n: "seoSubScore" },
  { key: "geo", i18n: "geoSubScore" },
  { key: "content", i18n: "contentSubScore" },
  { key: "technical", i18n: "technicalSubScore" },
];

function Zone1({
  data,
  locale,
}: {
  data: DashboardData["zone1"];
  locale: Locale;
}) {
  const level = data.global_level ?? "faible";
  const tone = LEVEL_TONES[level] ?? "info";
  return (
    <Card>
      <BlockStack gap="300">
        <SectionTitle source={GaugeIcon}>{t(locale, "dashboardZone1Title")}</SectionTitle>
        {data.global_score !== null ? (
          <BlockStack gap="200">
            <InlineStack gap="300" blockAlign="center">
              <Tooltip content={t(locale, "dashboardScoreTooltip")}>
                <Text as="p" variant="headingXl" fontWeight="bold">
                  {data.global_score}/100
                </Text>
              </Tooltip>
              <Badge tone={tone}>{t(locale, LEVEL_I18N_KEYS[level] ?? level)}</Badge>
              <Text as="p" tone="subdued">
                {data.products_in_scope} {t(locale, "dashboardZone1Products")}
              </Text>
            </InlineStack>
            {data.sub_scores && (
              <InlineGrid columns={4} gap="200">
                {SUB_SCORE_KEYS.map(({ key, i18n }) => (
                  <Box key={key} background="bg-surface-secondary" padding="200" borderRadius="200">
                    <BlockStack gap="050">
                      <Text as="p" variant="bodySm" tone="subdued">{t(locale, i18n)}</Text>
                      <Text as="p" variant="bodyMd" fontWeight="semibold">
                        {data.sub_scores![key]}/100
                      </Text>
                    </BlockStack>
                  </Box>
                ))}
              </InlineGrid>
            )}
          </BlockStack>
        ) : (
          <Text as="p" tone="subdued">
            {locale === "fr" ? "Importation Shopify en cours…" : "Shopify import in progress…"}
          </Text>
        )}
        <Box background="bg-surface-secondary" padding="300" borderRadius="200">
          <BlockStack gap="200">
            <Text as="p" tone="subdued" variant="bodySm">{t(locale, "dashboardZone1Niche")}</Text>
            {data.niche_summary ? (
              <Text as="p">{data.niche_summary}</Text>
            ) : (
              <Text as="p" tone="subdued">{t(locale, "dashboardZone1NicheUnvalidated")}</Text>
            )}
            <Button
              url={localizedPath("/app/niche-understanding", locale)}
              variant={data.niche_validated ? "plain" : "primary"}
              size="slim"
            >
              {t(locale, "dashboardZone1Cta")}
            </Button>
          </BlockStack>
        </Box>
      </BlockStack>
    </Card>
  );
}

function ActionCard({
  action,
  locale,
}: {
  action: PriorityAction;
  locale: Locale;
}) {
  const title = action.preview?.product_title ?? action.action_id;
  const label = action.preview?.action_label ?? action.why_now;
  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack gap="200" blockAlign="center" align="start">
          <Badge tone="info">{`#${action.rank}`}</Badge>
          <Text as="p" variant="bodyMd" fontWeight="semibold">{title}</Text>
        </InlineStack>
        <Text as="p">{label}</Text>
        {action.why_now && action.why_now !== label && (
          <Text as="p" tone="subdued" variant="bodySm">{action.why_now}</Text>
        )}
        <InlineStack gap="200">
          {action.estimates?.effort && (
            <Badge>{`${locale === "fr" ? "Effort" : "Effort"}: ${action.estimates.effort}`}</Badge>
          )}
          {action.estimates?.impact && (
            <Badge tone="success">{`${locale === "fr" ? "Impact" : "Impact"}: ${action.estimates.impact}`}</Badge>
          )}
        </InlineStack>
        <Button
          url={`${localizedPath("/app/safe-apply", locale)}&highlight=${action.action_id}`}
          variant="primary"
          size="slim"
        >
          {t(locale, "dashboardZone2Cta")}
        </Button>
      </BlockStack>
    </Card>
  );
}

const GSC_ISSUE_KEYS: Record<string, Parameters<typeof t>[1]> = {
  recently_published: "gscIssueRecentlyPublished",
  thin_content: "gscIssueThinContent",
  no_images: "gscIssueNoImages",
  no_seo_meta: "gscIssueNoSeoMeta",
  no_collection: "gscIssueNoCollection",
};

function gscInvisibleTooltip(issues: string[], locale: Locale): string {
  const reasons = issues
    .map((code) => GSC_ISSUE_KEYS[code])
    .filter((key): key is Parameters<typeof t>[1] => Boolean(key))
    .map((key) => t(locale, key));
  if (reasons.length === 0) return t(locale, "dashboardGscInvisibleTooltip");
  return `${t(locale, "dashboardGscInvisiblePrefix")} ${reasons.join(" · ")}`;
}

function ActiveProductsCard({
  products,
  productPacks,
  locale,
  onRefresh,
  isRefreshing,
  onAnalyzeProduct,
  onEnrichAndAnalyze,
  analyzingProductId,
  isAnalyzingSingle,
}: {
  products: ActiveProduct[];
  productPacks: Record<string, ProductResult>;
  locale: Locale;
  onRefresh: () => void;
  isRefreshing: boolean;
  onAnalyzeProduct: (productId: string) => void;
  onEnrichAndAnalyze: (productId: string, answers: Record<string, string>) => void;
  analyzingProductId: string | null;
  isAnalyzingSingle: boolean;
}) {
  const gscConnected = products.some((p) => p.gsc_connected);
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <SectionTitle source={ProductIcon}>{t(locale, "dashboardActiveProductsTitle")}</SectionTitle>
          <Tooltip content={t(locale, "dashboardRefresh")}>
            <Button
              icon={RefreshIcon}
              onClick={onRefresh}
              loading={isRefreshing}
              disabled={isRefreshing}
              variant="tertiary"
              accessibilityLabel={t(locale, "dashboardRefresh")}
            />
          </Tooltip>
        </InlineStack>
        {products.length === 0 ? (
          <Text as="p" tone="subdued">{t(locale, "dashboardActiveProductsEmpty")}</Text>
        ) : (
          <BlockStack gap="300">
            {products.map((product) => {
              const pack = productPacks[product.id] ?? productPacks[product.handle];
              const analyzingThis = analyzingProductId === product.id;
              return (
                <Box
                  key={product.id}
                  padding="300"
                  borderWidth="025"
                  borderRadius="200"
                  borderColor="border"
                >
                  <BlockStack gap="200">
                    <InlineStack align="space-between" blockAlign="center" wrap>
                      <InlineStack gap="150" blockAlign="center">
                        <Text as="p" variant="bodyMd" fontWeight="semibold">{product.title}</Text>
                        {gscConnected && (
                          product.gsc_visible ? (
                            <Tooltip content={t(locale, "dashboardGscVisibleTooltip")}>
                              <Badge tone="success">{t(locale, "dashboardGscVisible")}</Badge>
                            </Tooltip>
                          ) : (
                            <Tooltip content={gscInvisibleTooltip(product.gsc_issues, locale)}>
                              <Badge tone="warning">{t(locale, "dashboardGscInvisible")}</Badge>
                            </Tooltip>
                          )
                        )}
                        {pack && qualityWarningText(pack.content_test_pack, locale) && (
                          <Tooltip content={qualityWarningText(pack.content_test_pack, locale)}>
                            <span style={{ display: "inline-flex", cursor: "help" }}>
                              <Icon source={AlertTriangleIcon} tone="warning" />
                            </span>
                          </Tooltip>
                        )}
                      </InlineStack>
                      {analyzingThis ? (
                        <Spinner size="small" />
                      ) : (
                        <Button
                          size="slim"
                          onClick={() => onAnalyzeProduct(product.id)}
                          disabled={isAnalyzingSingle}
                        >
                          {t(locale, "dashboardAnalyseProduct")}
                        </Button>
                      )}
                    </InlineStack>
                    {pack && (
                      <ProductContentProposals
                        product={pack}
                        locale={locale}
                        isAnalyzing={analyzingThis}
                        onEnrichAndAnalyze={(answers) => onEnrichAndAnalyze(product.id, answers)}
                        analyzeDisabled={isAnalyzingSingle}
                        layout="buttons"
                      />
                    )}
                  </BlockStack>
                </Box>
              );
            })}
            <InlineStack align="center">
              <Button url={localizedPath("/app/market-analysis", locale)} variant="plain">
                {t(locale, "dashboardShowMore")}
              </Button>
            </InlineStack>
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}

function Zone2({
  data,
  nicheValidated,
  locale,
}: {
  data: DashboardData["zone2"];
  nicheValidated: boolean;
  locale: Locale;
}) {
  if (!nicheValidated) {
    return (
      <Card>
        <BlockStack gap="200">
          <Text as="h2" variant="headingMd">{t(locale, "dashboardZone2NicheGateTitle")}</Text>
          <Text as="p" tone="subdued">{t(locale, "dashboardZone2NicheGateBody")}</Text>
        </BlockStack>
      </Card>
    );
  }

  return (
    <BlockStack gap="300">
      <SectionTitle source={StarFilledIcon}>{t(locale, "dashboardZone2Title")}</SectionTitle>
      {data.actions.length === 0 ? (
        <Card>
          <Text as="p" tone="subdued">
            {data.sparse_signal
              ? t(locale, "dashboardZone2SparseSignal")
              : t(locale, "dashboardZone2NoAction")}
          </Text>
        </Card>
      ) : (
        <>
          {data.sparse_signal && (
            <Banner tone="info">
              <p>{t(locale, "dashboardZone2SparseSignal")}</p>
            </Banner>
          )}
          <InlineGrid columns={{ xs: 1, sm: 1, md: 3 }} gap="300">
            {data.actions.map((action) => (
              <ActionCard key={action.action_id} action={action} locale={locale} />
            ))}
          </InlineGrid>
        </>
      )}
    </BlockStack>
  );
}

function Zone3({
  data,
  locale,
}: {
  data: DashboardData["zone3"];
  locale: Locale;
}) {
  const trendTone =
    data.trend === "up" ? "success" : data.trend === "down" ? "critical" : undefined;

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <SectionTitle source={ChartHistogramGrowthIcon}>{t(locale, "dashboardZone3Title")}</SectionTitle>
          {data.trend !== "flat" && (
            <Badge tone={trendTone}>{data.trend === "up" ? "↑" : "↓"}</Badge>
          )}
        </InlineStack>
        {data.active_optimizations_count > 0 ? (
          <>
            <InlineStack gap="200" blockAlign="center" align="start">
              <Text as="p" variant="headingLg" fontWeight="bold">
                {data.active_optimizations_count}
              </Text>
              <Text as="p" tone="subdued">{t(locale, "dashboardZone3ActiveCount")}</Text>
            </InlineStack>
            {data.search_performance_sparkline.length > 0 && (
              <Sparkline
                data={data.search_performance_sparkline}
                label={locale === "fr" ? "Vues Google (30 j)" : "Google views (30d)"}
                formatValue={(v: number) => Math.round(v).toLocaleString("fr-FR")}
              />
            )}
            {data.next_milestone_at && (
              <InlineStack gap="200">
                <Text as="p" tone="subdued" variant="bodySm">
                  {t(locale, "dashboardZone3NextMilestone")} :{" "}
                  {data.next_milestone_at.slice(0, 10)}
                </Text>
              </InlineStack>
            )}
            <Button url={localizedPath("/app/impact", locale)} variant="secondary" size="slim">
              {t(locale, "dashboardZone3Cta")}
            </Button>
          </>
        ) : (
          <Text as="p" tone="subdued">{t(locale, "dashboardZone3Empty")}</Text>
        )}
      </BlockStack>
    </Card>
  );
}

function Zone4({
  data,
  locale,
}: {
  data: DashboardData["zone4"];
  locale: Locale;
}) {
  if (data.pending_steps.length === 0) return null;

  const stepHref: Record<string, string> = {
    gsc: "/app/onboarding",
    ga4: "/app/onboarding",
    niche: "/app/niche-understanding",
    plan: "/app/billing",
  };

  return (
    <Card>
      <BlockStack gap="200">
        <SectionTitle source={CheckCircleIcon}>{t(locale, "dashboardZone4Title")}</SectionTitle>
        {data.pending_steps.map((step) => (
          <InlineStack key={step.key} align="space-between" blockAlign="center">
            <Text as="p">{step.label}</Text>
            <Button
              url={localizedPath(stepHref[step.key] ?? "/app/account", locale)}
              variant="plain"
              size="slim"
            >
              {locale === "fr" ? "Configurer" : "Set up"}
            </Button>
          </InlineStack>
        ))}
      </BlockStack>
    </Card>
  );
}

function Zone5({
  data,
  locale,
}: {
  data: DashboardData["zone5"];
  locale: Locale;
}) {
  if (data.alerts.length === 0) return null;
  return (
    <BlockStack gap="200">
      <SectionTitle source={AlertCircleIcon}>{t(locale, "dashboardZone5Title")}</SectionTitle>
      {data.alerts.slice(0, 3).map((alert, idx) => (
        <Banner
          key={idx}
          tone={SEV_TONES[alert.severity] ?? "info"}
        >
          <p>{alert.message}</p>
        </Banner>
      ))}
    </BlockStack>
  );
}

function Zone6({ locale }: { locale: Locale }) {
  return (
    <Card>
      <BlockStack gap="200">
        <Text as="h2" variant="headingMd">{t(locale, "dashboardZone6Title")}</Text>
        <Text as="p" tone="subdued">{t(locale, "dashboardZone6Body")}</Text>
        <InlineStack>
          <Badge>{t(locale, "aiVisibilityComingSoon")}</Badge>
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

// ── Analysis Controls ────────────────────────────────────────────────────────

type AnalysisMode = "full" | "profile" | "products";
type AnalysisResult = "full" | "profile" | "products";

type AnalysisControlData =
  | { type: "startFullAnalysis"; jobId: string | null; error: string | null }
  | { type: "startBusinessAnalysis"; jobId: string | null; error: string | null }
  | { type: "pollBusinessAnalysis"; status: string; profile: BusinessProfile | null; error: string | null }
  | {
      type: "pollFullBusinessAnalysis";
      status: string;
      profile: BusinessProfile | null;
      productJobId: string | null;
      error: string | null;
    }
  | { type: "startProductAnalysis"; jobId: string | null; error: string | null }
  | { type: "pollProductAnalysis"; job: MarketJobState | null; error: string | null };

function AnalysisControlPanel({
  locale,
  mode,
  lastResult,
  error,
  productJob,
  disabled,
  onFullAnalysis,
  onProfileAnalysis,
  onProductAnalysis,
}: {
  locale: Locale;
  mode: AnalysisMode | null;
  lastResult: AnalysisResult | null;
  error: string | null;
  productJob: MarketJobState | null;
  disabled: boolean;
  onFullAnalysis: () => void;
  onProfileAnalysis: () => void;
  onProductAnalysis: () => void;
}) {
  const productTotal = productJob?.total ?? productJob?.analyzed_product_count ?? 0;
  const productProgress = productJob?.progress ?? productJob?.analyzed_product_count ?? 0;
  const productProgressPct = productTotal > 0 ? Math.round((productProgress / productTotal) * 100) : 15;
  const statusText = (() => {
    if (mode === "full" && !productJob) return t(locale, "dashboardFullAnalysisProfileRunning");
    if (mode === "full" && productJob) return t(locale, "dashboardFullAnalysisProductsRunning");
    if (mode === "profile") return t(locale, "dashboardProfileAnalysisRunning");
    if (mode === "products") return t(locale, "dashboardProductAnalysisRunning");
    if (lastResult === "full") return t(locale, "dashboardFullAnalysisComplete");
    if (lastResult === "profile") return t(locale, "dashboardProfileAnalysisReady");
    if (lastResult === "products") return t(locale, "dashboardProductAnalysisComplete");
    return null;
  })();

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <SectionTitle source={RefreshIcon}>{t(locale, "dashboardAnalysisControlsTitle")}</SectionTitle>
          <InlineStack gap="200" wrap>
            <Button
              icon={RefreshIcon}
              variant="primary"
              onClick={onFullAnalysis}
              loading={mode === "full"}
              disabled={disabled}
            >
              {t(locale, "dashboardRunFullAnalysis")}
            </Button>
            <Button
              icon={CompassIcon}
              onClick={onProfileAnalysis}
              loading={mode === "profile"}
              disabled={disabled}
            >
              {t(locale, "dashboardRunProfileAnalysis")}
            </Button>
            <Button
              icon={ProductIcon}
              onClick={onProductAnalysis}
              loading={mode === "products"}
              disabled={disabled}
            >
              {t(locale, "dashboardRunProductAnalysis")}
            </Button>
          </InlineStack>
        </InlineStack>
        {error && (
          <Banner tone="critical">
            <Text as="p">{error.split("\n")[0]}</Text>
          </Banner>
        )}
        {!error && statusText && (
          <Banner tone={mode ? "info" : "success"}>
            <BlockStack gap="150">
              <Text as="p">{statusText}</Text>
              {productJob && productJob.status !== "completed" && (
                <ProgressBar progress={Math.min(productProgressPct, 95)} size="small" />
              )}
            </BlockStack>
          </Banner>
        )}
      </BlockStack>
    </Card>
  );
}

// ── Business Profile Section ──────────────────────────────────────────────────

type BizActionData =
  | { type: "startBusinessAnalysis"; jobId: string | null; error: string | null }
  | { type: "pollBusinessAnalysis"; status: string; profile: BusinessProfile | null; error: string | null }
  | { type: "saveBusinessProfile"; profile: BusinessProfile | null; error: string | null };

function SectionTitle({ source, children }: { source: IconSource; children: React.ReactNode }) {
  // The icon is wrapped in a fixed-size box because Polaris .Polaris-Icon has margin:auto,
  // which would otherwise absorb the free space in a full-width flex row and push the title right.
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--p-space-200)" }}>
      <span style={{ display: "inline-flex", flex: "0 0 auto", width: "1.25rem", height: "1.25rem" }}>
        <Icon source={source} tone="base" />
      </span>
      <Text as="span" variant="headingMd">
        {children}
      </Text>
    </div>
  );
}

function getNicheIcon(profile: BusinessProfile): IconSource {
  const text = [profile.niche_summary, ...(profile.key_themes ?? [])].join(" ").toLowerCase();
  // Animals & pets
  if (/chat|chien|animal|pet|félin|canin|poil|woof|meow|oiseau|reptile|aquarium/.test(text)) return HeartIcon;
  // Automotive & vehicles
  if (/voiture|auto|moto|véhicule|car\b|motor|tuning|pneu|conduite|bagnole|vitesse|garage/.test(text)) return GaugeIcon;
  // Beauty & cosmetics
  if (/beauté|cosméti|parfum|maquillage|soin du visage|skincare|beauty|soin de peau/.test(text)) return EyeDropperIcon;
  // Flowers & plants
  if (/fleur|bouquet|plante|jardinage|botanique|flower|garden|herb/.test(text)) return FlowerIcon;
  // Nature & eco
  if (/nature|organi|ecolog|durable|vert|green|eco|recyclé|environnement/.test(text)) return NatureIcon;
  // Food & gastronomy
  if (/alimentation|nourriture|food|cuisine|recette|gastronomie|épicerie|bio|repas|chef/.test(text)) return FoodIcon;
  // Sports & fitness
  if (/sport|fitness|muscl|yoga|running|vélo|natation|crossfit|athlétisme|gym/.test(text)) return SportsIcon;
  // Home & deco
  if (/maison|home|déco|décor|meubl|intérieur|aménagement|rénov|habitat/.test(text)) return HomeIcon;
  // Fashion & accessories (watches/jewelry)
  if (/mode|fashion|vêtement|bijou|montre|accessoire|jewelry|luxe|couture|sac|chaussure/.test(text)) return WatchIcon;
  // Electronics & tech
  if (/tech|électronique|informatiqu|téléphone|smartphone|gadget|digital|numérique|appareil/.test(text)) return PhoneIcon;
  // Photography
  if (/photo|photographi|camera|appareil photo|objectif/.test(text)) return CameraIcon;
  // Gaming & toys
  if (/jeu|game|jouet|gaming|console|enfant|baby|toy|bébé/.test(text)) return GamesIcon;
  // Music
  if (/musique|music|instrument|guitare|piano|vinyl|concert/.test(text)) return MicrophoneIcon;
  // Travel
  if (/voyage|travel|aventure|randonnée|plage|tourisme|destination/.test(text)) return CompassIcon;
  // Books & education
  if (/livre|book|formation|apprend|cours|éduc|e-learning|formation/.test(text)) return BookOpenIcon;
  // Commerce / retail
  if (/boutique|commerce|retail|marketplace|shop|magasin/.test(text)) return StoreIcon;
  return StarFilledIcon;
}

function BizProfileCards({ profile, competitorSignals, locale }: { profile: BusinessProfile; competitorSignals: string[]; locale: Locale }) {
  const intensityTone = (i: string): "success" | "warning" | "info" =>
    i === "high" ? "success" : i === "medium" ? "warning" : "info";
  const NicheIcon = getNicheIcon(profile);

  return (
    <BlockStack gap="400">
      {/* Row 1 — Niche + Voix */}
      <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
        <Card>
          <BlockStack gap="200">
            <SectionTitle source={NicheIcon}>{locale === "fr" ? "Niche & Marque" : "Niche & Brand"}</SectionTitle>
            <Text as="p" variant="headingLg">{profile.brand_name}</Text>
            <Text as="p" tone="subdued">{profile.niche_summary}</Text>
            {(profile.key_themes ?? []).length > 0 && (
              <InlineStack gap="100" wrap>
                {profile.key_themes.map((theme) => (
                  <Badge key={theme} tone="info">{theme}</Badge>
                ))}
              </InlineStack>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="200">
            <SectionTitle source={MegaphoneIcon}>{locale === "fr" ? "Voix de marque" : "Brand voice"}</SectionTitle>
            <Text as="p" variant="headingLg">{profile.content_style?.tone ?? "—"}</Text>
            <Text as="p" tone="subdued">{profile.brand_voice}</Text>
            {(profile.content_style?.vocabulary_to_use ?? []).length > 0 && (
              <InlineStack gap="100" wrap>
                {profile.content_style.vocabulary_to_use.map((v) => (
                  <Badge key={v} tone="success">{v}</Badge>
                ))}
                {(profile.content_style?.vocabulary_to_avoid ?? []).map((v) => (
                  <Badge key={v} tone="critical">{v}</Badge>
                ))}
              </InlineStack>
            )}
          </BlockStack>
        </Card>
      </InlineGrid>

      {/* Row 2 — Personas + Style contenu */}
      <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
        <Card>
          <BlockStack gap="300">
            <SectionTitle source={PersonIcon}>{locale === "fr" ? "Personas" : "Personas"}</SectionTitle>
            {(profile.target_personas ?? []).map((p) => (
              <BlockStack gap="100" key={p.name}>
                <Text as="p" fontWeight="semibold">{p.name}</Text>
                <Text as="p" tone="subdued" variant="bodySm">{p.main_need}</Text>
                <Text as="p" tone="subdued" variant="bodySm">→ {p.buying_trigger}</Text>
              </BlockStack>
            ))}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="200">
            <SectionTitle source={ContentIcon}>{locale === "fr" ? "Style de contenu" : "Content style"}</SectionTitle>
            <Text as="p" variant="bodySm" fontWeight="semibold">
              {profile.content_style?.typical_article_length ?? ""}
            </Text>
            {(profile.content_style?.h2_structure ?? []).length > 0 && (
              <BlockStack gap="050">
                {profile.content_style.h2_structure.map((h) => (
                  <Text as="p" tone="subdued" variant="bodySm" key={h}>• {h}</Text>
                ))}
              </BlockStack>
            )}
            {(profile.content_style?.hook_patterns ?? []).length > 0 && (
              <BlockStack gap="050">
                {profile.content_style.hook_patterns.map((h) => (
                  <Text as="p" tone="subdued" variant="bodySm" key={h}>→ {h}</Text>
                ))}
              </BlockStack>
            )}
          </BlockStack>
        </Card>
      </InlineGrid>

      {/* Row 3 — Concurrents + Opportunités */}
      <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
        <Card>
          <BlockStack gap="200">
            <SectionTitle source={GlobeIcon}>{locale === "fr" ? "Concurrents" : "Competitors"}</SectionTitle>
            {(() => {
              const domains = [...new Set([...(profile.competitor_domains ?? []), ...competitorSignals])];
              return domains.length > 0 ? (
                <InlineStack gap="150" wrap>
                  {domains.map((d) => (
                    <Badge key={d} tone="info">{d}</Badge>
                  ))}
                </InlineStack>
              ) : null;
            })()}
            {(profile.competitor_insights ?? []).length > 0 && (
              <BlockStack gap="050">
                {profile.competitor_insights.map((i) => (
                  <Text as="p" tone="subdued" variant="bodySm" key={i}>• {i}</Text>
                ))}
              </BlockStack>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <SectionTitle source={CalendarIcon}>{locale === "fr" ? "Saisonnalité & Opportunités" : "Seasonality & Gaps"}</SectionTitle>
            {(profile.seasonal_patterns ?? []).map((s) => (
              <InlineStack key={s.period} align="space-between" gap="200">
                <BlockStack gap="0">
                  <Text as="p" variant="bodySm" fontWeight="semibold">{s.period}</Text>
                  <Text as="p" tone="subdued" variant="bodySm">{s.theme}</Text>
                </BlockStack>
                <Badge tone={intensityTone(s.intensity)}>{s.intensity}</Badge>
              </InlineStack>
            ))}
            {(profile.content_gaps ?? []).length > 0 && (
              <BlockStack gap="050">
                <Text as="p" variant="bodySm" fontWeight="semibold">
                  {locale === "fr" ? "Lacunes de contenu" : "Content gaps"}
                </Text>
                {profile.content_gaps.map((g) => (
                  <Text as="p" tone="subdued" variant="bodySm" key={g}>• {g}</Text>
                ))}
              </BlockStack>
            )}
          </BlockStack>
        </Card>
      </InlineGrid>
    </BlockStack>
  );
}

function BusinessProfileSection({
  initialProfile,
  competitorSignals,
  locale,
}: {
  initialProfile: BusinessProfile | null;
  competitorSignals: string[];
  locale: Locale;
}) {
  const bizFetcher = useFetcher<BizActionData>();
  const [bizJobId, setBizJobId] = useState<string | null>(null);
  const [bizJobStatus, setBizJobStatus] = useState<string | null>(null);
  const [bizProfile, setBizProfile] = useState<BusinessProfile | null>(
    initialProfile?.status === "validated" ? initialProfile : null,
  );
  const [bizDraft, setBizDraft] = useState<BusinessProfile | null>(
    initialProfile && initialProfile.status !== "validated" ? initialProfile : null,
  );
  const [bizError, setBizError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editBuffer, setEditBuffer] = useState<BusinessProfile | null>(null);
  const [isKeywordsOpen, setIsKeywordsOpen] = useState(false);
  const [selectedKeywords, setSelectedKeywords] = useState<string[]>([]);
  const bizStatusRef = useRef<string | null>(null);
  bizStatusRef.current = bizJobStatus;

  useEffect(() => {
    if (!initialProfile) {
      setBizProfile(null);
      setBizDraft(null);
      return;
    }
    if (initialProfile.status === "validated") {
      setBizProfile(initialProfile);
      setBizDraft(null);
      return;
    }
    setBizProfile(null);
    setBizDraft(initialProfile);
  }, [initialProfile]);

  useEffect(() => {
    if (!bizFetcher.data) return;
    const data = bizFetcher.data;
    if (data.type === "startBusinessAnalysis" && data.jobId) {
      setBizJobId(data.jobId);
      setBizJobStatus(null);
      setBizError(null);
    }
    if (data.type === "startBusinessAnalysis" && data.error) {
      setBizError(data.error);
    }
    if (data.type === "pollBusinessAnalysis") {
      setBizJobStatus(data.status);
      if (data.status === "completed") {
        setBizJobId(null);
        if (data.profile && data.profile.status !== "error") {
          setBizDraft(data.profile);
        } else if (data.profile?.status === "error") {
          setBizError((data.profile as { error?: string }).error ?? "L'analyse IA a échoué");
        }
      }
      if (data.status === "failed" || data.status === "unknown") {
        setBizJobId(null);
        if (data.error) setBizError(data.error);
      }
    }
    if (data.type === "saveBusinessProfile" && data.profile) {
      setBizProfile(data.profile);
      setBizDraft(null);
    }
  }, [bizFetcher.data]);

  useEffect(() => {
    if (!bizJobId) return;
    const poll = () => {
      const s = bizStatusRef.current;
      if (s === "completed" || s === "failed") return;
      const fd = new FormData();
      fd.set("intent", "pollBusinessAnalysis");
      fd.set("bizJobId", bizJobId);
      bizFetcher.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
  }, [bizJobId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAnalyze = (keywords: string[] = []) => {
    setBizError(null);
    setIsKeywordsOpen(false);
    const fd = new FormData();
    fd.set("intent", "startBusinessAnalysis");
    if (keywords.length > 0) fd.set("focusKeywords", JSON.stringify(keywords));
    bizFetcher.submit(fd, { method: "post" });
  };

  const handleValidate = () => {
    if (!bizDraft) return;
    const fd = new FormData();
    fd.set("intent", "saveBusinessProfile");
    fd.set("profileJson", JSON.stringify(bizDraft));
    bizFetcher.submit(fd, { method: "post" });
  };

  const handleRegenerate = () => {
    const profile = bizDraft ?? bizProfile;
    if (profile) {
      setSelectedKeywords([]);
      setIsKeywordsOpen(true);
    } else {
      handleAnalyze();
    }
  };

  const handleConfirmKeywords = () => {
    setBizProfile(null);
    setBizDraft(null);
    handleAnalyze(selectedKeywords);
  };

  const toggleKeyword = (kw: string) => {
    setSelectedKeywords((prev) =>
      prev.includes(kw) ? prev.filter((k) => k !== kw) : [...prev, kw],
    );
  };

  const handleOpenEdit = () => {
    const source = bizDraft ?? bizProfile;
    if (!source) return;
    setEditBuffer({ ...source });
    setIsEditing(true);
  };

  const handleSaveEdit = () => {
    if (!editBuffer) return;
    setBizDraft(editBuffer);
    setIsEditing(false);
  };

  const isAnalyzing =
    bizFetcher.state !== "idle" ||
    (bizJobId !== null && bizJobStatus !== "completed" && bizJobStatus !== "failed");

  const isSaving = bizFetcher.state !== "idle" && !isAnalyzing;

  const displayProfile = bizDraft ?? bizProfile;

  const keywordsModal = (() => {
    const profile = bizDraft ?? bizProfile;
    if (!profile) return null;
    const suggestions = [
      ...(profile.key_themes ?? []),
      ...(profile.competitor_domains ?? []).slice(0, 5),
    ].filter(Boolean);
    return (
      <Modal
        open={isKeywordsOpen}
        onClose={() => setIsKeywordsOpen(false)}
        title={locale === "fr" ? "Orienter la régénération" : "Guide regeneration"}
        primaryAction={{
          content: locale === "fr" ? "Régénérer" : "Regenerate",
          onAction: handleConfirmKeywords,
        }}
        secondaryActions={[{
          content: locale === "fr" ? "Sans filtre" : "No filter",
          onAction: () => { setBizProfile(null); setBizDraft(null); handleAnalyze([]); },
        }]}
      >
        <Modal.Section>
          <BlockStack gap="300">
            <Text as="p" tone="subdued">
              {locale === "fr"
                ? "Sélectionnez les thèmes sur lesquels concentrer l'analyse."
                : "Select themes to focus the analysis on."}
            </Text>
            <InlineStack gap="200" wrap>
              {suggestions.map((kw) => (
                <Button
                  key={kw}
                  size="slim"
                  variant={selectedKeywords.includes(kw) ? "primary" : "secondary"}
                  onClick={() => toggleKeyword(kw)}
                >
                  {kw}
                </Button>
              ))}
            </InlineStack>
          </BlockStack>
        </Modal.Section>
      </Modal>
    );
  })();

  // ── Header card (always visible once we have any state) ──
  const headerCard = (
    <Card>
      <InlineStack align="space-between" blockAlign="center">
        <InlineStack gap="200" blockAlign="center" align="start">
          <SectionTitle source={CompassIcon}>{t(locale, "businessProfileTitle")}</SectionTitle>
          {displayProfile?.status === "validated" && (
            <Badge tone="success">{t(locale, "businessProfileValidated")}</Badge>
          )}
          {bizDraft && bizDraft.status !== "validated" && (
            <Badge tone="info">{locale === "fr" ? "Brouillon" : "Draft"}</Badge>
          )}
          {displayProfile?.sources_used?.includes("market_analysis_product_signals") && (
            <Badge tone="info">{t(locale, "businessProfileProductSignals")}</Badge>
          )}
        </InlineStack>
        <InlineStack gap="200">
          {displayProfile && (
            <Button onClick={handleOpenEdit} size="slim" variant="plain">
              {locale === "fr" ? "Modifier" : "Edit"}
            </Button>
          )}
          {bizDraft && (
            <Button onClick={handleValidate} variant="primary" size="slim" loading={isSaving}>
              {t(locale, "businessProfileValidate")}
            </Button>
          )}
          <Button
            onClick={displayProfile ? handleRegenerate : handleAnalyze}
            size="slim"
            variant={displayProfile ? "plain" : "primary"}
            loading={isAnalyzing}
          >
            {displayProfile ? t(locale, "businessProfileRegenerate") : t(locale, "businessProfileAnalyze")}
          </Button>
        </InlineStack>
      </InlineStack>
    </Card>
  );

  // Empty / error state
  if (!displayProfile && !isAnalyzing) {
    return (
      <BlockStack gap="300">
        {keywordsModal}
        {headerCard}
        {bizError && (
          <Banner tone="critical"><p>{bizError.split("\n")[0]}</p></Banner>
        )}
        {!bizError && (
          <Banner tone="info"><p>{t(locale, "businessProfileSubtitle")}</p></Banner>
        )}
      </BlockStack>
    );
  }

  // Analyzing spinner
  if (isAnalyzing && !displayProfile) {
    return (
      <BlockStack gap="300">
        {keywordsModal}
        {headerCard}
        <Card>
          <InlineStack gap="200" blockAlign="center" align="start">
            <Spinner size="small" />
            <Text as="p" tone="subdued">{t(locale, "businessProfileAnalyzing")}</Text>
          </InlineStack>
        </Card>
      </BlockStack>
    );
  }

  if (!displayProfile) return headerCard;

  const editModal = editBuffer && (
    <Modal
      open={isEditing}
      onClose={() => setIsEditing(false)}
      title={locale === "fr" ? "Modifier le profil entreprise" : "Edit business profile"}
      primaryAction={{ content: locale === "fr" ? "Enregistrer" : "Save", onAction: handleSaveEdit }}
      secondaryActions={[{ content: locale === "fr" ? "Annuler" : "Cancel", onAction: () => setIsEditing(false) }]}
    >
      <Modal.Section>
        <FormLayout>
          <TextField
            label={locale === "fr" ? "Résumé de niche" : "Niche summary"}
            value={editBuffer.niche_summary ?? ""}
            onChange={(v) => setEditBuffer({ ...editBuffer, niche_summary: v })}
            multiline={3}
            autoComplete="off"
          />
          <TextField
            label={locale === "fr" ? "Voix de marque" : "Brand voice"}
            value={editBuffer.brand_voice ?? ""}
            onChange={(v) => setEditBuffer({ ...editBuffer, brand_voice: v })}
            multiline={3}
            autoComplete="off"
          />
          <TextField
            label={locale === "fr" ? "Ton éditorial" : "Editorial tone"}
            value={editBuffer.content_style?.tone ?? ""}
            onChange={(v) => setEditBuffer({ ...editBuffer, content_style: { ...editBuffer.content_style, tone: v } })}
            autoComplete="off"
          />
          <TextField
            label={locale === "fr" ? "Thèmes clés (un par ligne)" : "Key themes (one per line)"}
            value={(editBuffer.key_themes ?? []).join("\n")}
            onChange={(v) => setEditBuffer({ ...editBuffer, key_themes: v.split("\n").filter(Boolean) })}
            multiline={4}
            autoComplete="off"
          />
          <TextField
            label={locale === "fr" ? "Insights concurrents (un par ligne)" : "Competitor insights (one per line)"}
            value={(editBuffer.competitor_insights ?? []).join("\n")}
            onChange={(v) => setEditBuffer({ ...editBuffer, competitor_insights: v.split("\n").filter(Boolean) })}
            multiline={4}
            autoComplete="off"
          />
          <TextField
            label={locale === "fr" ? "Lacunes de contenu (une par ligne)" : "Content gaps (one per line)"}
            value={(editBuffer.content_gaps ?? []).join("\n")}
            onChange={(v) => setEditBuffer({ ...editBuffer, content_gaps: v.split("\n").filter(Boolean) })}
            multiline={3}
            autoComplete="off"
          />
        </FormLayout>
      </Modal.Section>
    </Modal>
  );

  return (
    <BlockStack gap="400">
      {keywordsModal}
      {editModal}
      {headerCard}
      <Banner tone="info">
        <Text as="p">{t(locale, "businessProfileLoopHint")}</Text>
      </Banner>
      {isAnalyzing && (
        <Banner tone="info">
          <InlineStack gap="200" blockAlign="center" align="start">
            <Spinner size="small" />
            <Text as="p">{t(locale, "businessProfileAnalyzing")}</Text>
          </InlineStack>
        </Banner>
      )}
      {bizError && (
        <Banner tone="critical"><p>{bizError.split("\n")[0]}</p></Banner>
      )}
      <BizProfileCards profile={displayProfile} competitorSignals={competitorSignals} locale={locale} />
    </BlockStack>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function IndexPage() {
  const { locale, plan, dashboard, activeProducts, productResults, competitorSignals, auditJobId, businessProfile, error } = useLoaderData<typeof loader>() as LoaderData;
  const [profileForDashboard, setProfileForDashboard] = useState<BusinessProfile | null>(businessProfile);

  useEffect(() => {
    setProfileForDashboard(businessProfile);
  }, [businessProfile]);

  // ── Audit job polling ─────────────────────────────────────────────────────
  type PollData = { type?: string; status?: string; resultStatus?: string | null; error?: string | null };
  type RefreshData = { type: "refresh"; jobId: string | null; error: string | null };

  const auditFetcher = useFetcher<PollData>();
  const refreshFetcher = useFetcher<RefreshData>();

  // Active jobId: starts with loader value, can be overridden by manual refresh.
  const [activeJobId, setActiveJobId] = useState<string | null>(auditJobId);
  const [auditStatus, setAuditStatus] = useState<string | null>(null);
  const [resultStatus, setResultStatus] = useState<string | null>(null);
  // True only when the merchant clicked the Refresh button — guards the
  // post-completion reload so background audits triggered by the loader do
  // not trigger a reload loop.
  const [manualRefresh, setManualRefresh] = useState(false);
  const auditStatusRef = useRef<string | null>(null);
  auditStatusRef.current = auditStatus;

  // Progress bar — linear ramp up to 90% over the expected crawl window,
  // then snaps to 100% when the job actually completes.
  // Window calibrated for the optimized job (pagination 250 + parallel fetch).
  const PROGRESS_WINDOW_MS = 15_000;
  const [auditProgress, setAuditProgress] = useState(5);
  const auditStartRef = useRef<number>(0);

  // Capture the jobId returned by the manual refresh action.
  useEffect(() => {
    if (refreshFetcher.data?.type === "refresh" && refreshFetcher.data.jobId) {
      setActiveJobId(refreshFetcher.data.jobId);
      setAuditStatus(null);
      setResultStatus(null);
      setManualRefresh(true);
    }
  }, [refreshFetcher.data]);

  useEffect(() => {
    if (!activeJobId) return;
    const poll = () => {
      const s = auditStatusRef.current;
      if (s === "completed" || s === "failed") return;
      const fd = new FormData();
      fd.set("jobId", activeJobId);
      auditFetcher.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 2_000);
    return () => clearInterval(id);
  }, [activeJobId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (auditFetcher.data?.status) {
      setAuditStatus(auditFetcher.data.status);
      if (auditFetcher.data.resultStatus !== undefined) {
        setResultStatus(auditFetcher.data.resultStatus ?? null);
      }
    }
  }, [auditFetcher.data]);

  useEffect(() => {
    if (auditStatus !== "completed") return;
    setAuditProgress(100);
    // Only reload when the audit was triggered by the merchant's Refresh
    // click. Background audits launched by the loader must not trigger a
    // reload — that would re-fire the loader and create an audit/reload loop.
    if (!manualRefresh) return;
    const id = setTimeout(() => window.location.reload(), 1_200);
    return () => clearTimeout(id);
  }, [auditStatus, manualRefresh]);

  const auditRunning =
    activeJobId !== null && auditStatus !== "completed" && auditStatus !== "failed";
  const isRefreshing = refreshFetcher.state !== "idle" || auditRunning;

  // Animate progress while the audit runs.
  useEffect(() => {
    if (!auditRunning) return;
    auditStartRef.current = Date.now();
    setAuditProgress(5);
    const tick = setInterval(() => {
      const elapsed = Date.now() - auditStartRef.current;
      setAuditProgress(
        Math.min(Math.round(5 + (elapsed / PROGRESS_WINDOW_MS) * 85), 90),
      );
    }, 400);
    return () => clearInterval(tick);
  }, [auditRunning]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = () => {
    const fd = new FormData();
    fd.set("intent", "refresh");
    refreshFetcher.submit(fd, { method: "post" });
  };

  // Local pack store, seeded from the loader and updated as analyses complete.
  const [productPacks, setProductPacks] = useState<Record<string, ProductResult>>(productResults);

  useEffect(() => {
    setProductPacks(productResults);
  }, [productResults]);

  // ── Global analysis controls ─────────────────────────────────────────────
  const analysisFetcher = useFetcher<AnalysisControlData>();
  const analysisProfilePollFetcher = useFetcher<AnalysisControlData>();
  const analysisProductPollFetcher = useFetcher<AnalysisControlData>();
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisProfileJobId, setAnalysisProfileJobId] = useState<string | null>(null);
  const [analysisProfileStatus, setAnalysisProfileStatus] = useState<string | null>(null);
  const [analysisProductJobId, setAnalysisProductJobId] = useState<string | null>(null);
  const [analysisProductJob, setAnalysisProductJob] = useState<MarketJobState | null>(null);

  const analysisModeRef = useRef<AnalysisMode | null>(null);
  const analysisProfileStatusRef = useRef<string | null>(null);
  const analysisProductJobStatusRef = useRef<string | undefined>(undefined);
  const analysisProfilePollRef = useRef(analysisProfilePollFetcher);
  const analysisProductPollRef = useRef(analysisProductPollFetcher);
  analysisModeRef.current = analysisMode;
  analysisProfileStatusRef.current = analysisProfileStatus;
  analysisProductJobStatusRef.current = analysisProductJob?.status;
  analysisProfilePollRef.current = analysisProfilePollFetcher;
  analysisProductPollRef.current = analysisProductPollFetcher;

  const resetAnalysisState = (mode: AnalysisMode) => {
    setAnalysisMode(mode);
    setAnalysisResult(null);
    setAnalysisError(null);
    setAnalysisProfileStatus(null);
    setAnalysisProductJob(null);
  };

  const updateProductPacksFromJob = (job: MarketJobState) => {
    setProductPacks((prev) => {
      const next = { ...prev };
      for (const result of job.products ?? []) {
        if (result.product_id) next[result.product_id] = result;
        if (result.product_handle) next[result.product_handle] = result;
      }
      return next;
    });
  };

  useEffect(() => {
    const data = analysisFetcher.data;
    if (!data) return;
    if (data.type === "startFullAnalysis") {
      if (data.jobId) {
        setAnalysisProfileJobId(data.jobId);
        setAnalysisProfileStatus(null);
      } else if (data.error) {
        setAnalysisMode(null);
        setAnalysisError(data.error);
      }
    }
    if (data.type === "startBusinessAnalysis") {
      if (data.jobId) {
        setAnalysisProfileJobId(data.jobId);
        setAnalysisProfileStatus(null);
      } else if (data.error) {
        setAnalysisMode(null);
        setAnalysisError(data.error);
      }
    }
    if (data.type === "startProductAnalysis") {
      if (data.jobId) {
        setAnalysisProductJobId(data.jobId);
        setAnalysisProductJob(null);
      } else if (data.error) {
        setAnalysisMode(null);
        setAnalysisError(data.error);
      }
    }
  }, [analysisFetcher.data]);

  useEffect(() => {
    const data = analysisProfilePollFetcher.data;
    if (!data) return;
    if (data.type === "pollBusinessAnalysis") {
      setAnalysisProfileStatus(data.status);
      if (data.status === "completed") {
        setAnalysisProfileJobId(null);
        setAnalysisMode(null);
        setAnalysisResult("profile");
        if (data.profile && data.profile.status !== "error") {
          setProfileForDashboard(data.profile);
        }
      }
      if (data.status === "failed" || data.status === "unknown") {
        setAnalysisProfileJobId(null);
        setAnalysisMode(null);
        if (data.error) setAnalysisError(data.error);
      }
    }
    if (data.type === "pollFullBusinessAnalysis") {
      setAnalysisProfileStatus(data.status);
      if (data.profile && data.profile.status !== "error") {
        setProfileForDashboard(data.profile);
      }
      if (data.productJobId) {
        setAnalysisProfileJobId(null);
        setAnalysisProductJobId(data.productJobId);
        setAnalysisProductJob(null);
      }
      if ((data.status === "failed" || data.status === "unknown") && !data.productJobId) {
        setAnalysisProfileJobId(null);
        setAnalysisMode(null);
        if (data.error) setAnalysisError(data.error);
      }
    }
  }, [analysisProfilePollFetcher.data]);

  useEffect(() => {
    const data = analysisProductPollFetcher.data;
    if (data?.type !== "pollProductAnalysis") return;
    if (data.error) {
      setAnalysisProductJobId(null);
      setAnalysisMode(null);
      setAnalysisError(data.error);
      return;
    }
    if (!data.job) return;
    setAnalysisProductJob(data.job);
    if (data.job.status === "completed") {
      updateProductPacksFromJob(data.job);
      setAnalysisProductJobId(null);
      setAnalysisResult(analysisModeRef.current === "full" ? "full" : "products");
      setAnalysisMode(null);
    }
    if (data.job.status === "failed") {
      setAnalysisProductJobId(null);
      setAnalysisMode(null);
      setAnalysisError(data.job.error ?? "Analyse produits échouée");
    }
  }, [analysisProductPollFetcher.data]);

  useEffect(() => {
    if (!analysisProfileJobId) return;
    const poll = () => {
      const s = analysisProfileStatusRef.current;
      if (s === "completed" || s === "failed") return;
      const fd = new FormData();
      fd.set(
        "intent",
        analysisModeRef.current === "full" ? "pollFullBusinessAnalysis" : "pollBusinessAnalysis",
      );
      fd.set("bizJobId", analysisProfileJobId);
      analysisProfilePollRef.current.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
  }, [analysisProfileJobId]);

  useEffect(() => {
    if (!analysisProductJobId) return;
    const poll = () => {
      const s = analysisProductJobStatusRef.current;
      if (s === "completed" || s === "failed") return;
      const fd = new FormData();
      fd.set("intent", "pollProductAnalysis");
      fd.set("productJobId", analysisProductJobId);
      analysisProductPollRef.current.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
  }, [analysisProductJobId]);

  const isGlobalAnalysisRunning =
    analysisMode !== null ||
    analysisFetcher.state !== "idle" ||
    analysisProfilePollFetcher.state !== "idle" ||
    analysisProductPollFetcher.state !== "idle";

  const handleFullAnalysis = () => {
    resetAnalysisState("full");
    setAnalysisProfileJobId(null);
    setAnalysisProductJobId(null);
    const fd = new FormData();
    fd.set("intent", "startFullAnalysis");
    analysisFetcher.submit(fd, { method: "post" });
  };

  const handleProfileAnalysis = () => {
    resetAnalysisState("profile");
    setAnalysisProfileJobId(null);
    setAnalysisProductJobId(null);
    const fd = new FormData();
    fd.set("intent", "startBusinessAnalysis");
    analysisFetcher.submit(fd, { method: "post" });
  };

  const handleProductAnalysis = () => {
    resetAnalysisState("products");
    setAnalysisProfileJobId(null);
    setAnalysisProductJobId(null);
    const fd = new FormData();
    fd.set("intent", "startProductAnalysis");
    analysisFetcher.submit(fd, { method: "post" });
  };

  // ── Single-product market analysis (per active product) ───────────────────
  type SingleData =
    | { type: "startSingle"; jobId: string | null; productId: string; error: string | null }
    | { type: "pollSingle"; job: MarketJobState | null; productId: string; error: string | null };

  const singleFetcher = useFetcher<SingleData>();
  const pollSingleFetcher = useFetcher<SingleData>();

  const [singleProductId, setSingleProductId] = useState<string | null>(null);
  const [singleJobId, setSingleJobId] = useState<string | null>(null);
  const [singleStatus, setSingleStatus] = useState<string | undefined>(undefined);

  const singleJobIdRef = useRef<string | null>(null);
  const singleStatusRef = useRef<string | undefined>(undefined);
  const singleProductIdRef = useRef<string | null>(null);
  const pollSingleRef = useRef(pollSingleFetcher);
  singleJobIdRef.current = singleJobId;
  singleStatusRef.current = singleStatus;
  singleProductIdRef.current = singleProductId;
  pollSingleRef.current = pollSingleFetcher;

  useEffect(() => {
    if (singleFetcher.data?.type === "startSingle" && singleFetcher.data.jobId) {
      setSingleJobId(singleFetcher.data.jobId);
      setSingleStatus(undefined);
    }
  }, [singleFetcher.data]);

  useEffect(() => {
    const d = pollSingleFetcher.data;
    if (d?.type !== "pollSingle" || !d.job) return;
    setSingleStatus(d.job.status);
    if (d.job.status === "completed" && d.job.products && d.job.products.length > 0) {
      const updated = d.job.products[0];
      setProductPacks((prev) => ({
        ...prev,
        [updated.product_id]: updated,
        ...(updated.product_handle ? { [updated.product_handle]: updated } : {}),
      }));
      setSingleJobId(null);
      setSingleProductId(null);
      setSingleStatus(undefined);
    }
    if (d.job.status === "failed") {
      setSingleJobId(null);
      setSingleProductId(null);
      setSingleStatus(undefined);
    }
  }, [pollSingleFetcher.data]);

  useEffect(() => {
    if (!singleJobId) return;
    const poll = () => {
      const s = singleStatusRef.current;
      if (s === "completed" || s === "failed") return;
      const fd = new FormData();
      fd.set("intent", "pollSingle");
      fd.set("jobId", singleJobIdRef.current!);
      fd.set("productId", singleProductIdRef.current || "");
      pollSingleRef.current.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
  }, [singleJobId]); // eslint-disable-line react-hooks/exhaustive-deps

  const isAnalyzingSingle =
    singleFetcher.state !== "idle" ||
    (singleJobId !== null && singleStatus !== "completed" && singleStatus !== "failed");

  const handleAnalyzeProduct = (productId: string) => {
    setSingleProductId(productId);
    const fd = new FormData();
    fd.set("intent", "startSingle");
    fd.set("productId", productId);
    singleFetcher.submit(fd, { method: "post" });
  };

  const handleEnrichAndAnalyze = (productId: string, answers: Record<string, string>) => {
    setSingleProductId(productId);
    const fd = new FormData();
    fd.set("intent", "saveFactsAndStartSingle");
    fd.set("productId", productId);
    fd.set("answers", JSON.stringify(answers));
    singleFetcher.submit(fd, { method: "post" });
  };

  if (error || !dashboard) {
    return (
      <Page title="Léonie SEO">
        <Banner tone="critical" title={t(locale, "systemStatus")}>
          <p>{error ?? t(locale, "systemUnavailable")}</p>
        </Banner>
      </Page>
    );
  }

  const { banners, zone1, zone3, zone4, zone5 } = dashboard;

  return (
    <Page title="Léonie SEO">
      <BlockStack gap="400">
        {/* Banners */}
        {banners.pilot_safe && (
          <Banner tone="warning">
            <p>{t(locale, "dashboardPilotSafeBanner")}</p>
          </Banner>
        )}
        {auditRunning && (
          <Banner tone="info">
            <BlockStack gap="150">
              <InlineStack gap="200" blockAlign="center" align="space-between">
                <Text as="p">{t(locale, "dashboardRefreshing")}</Text>
                <Text as="p" variant="bodySm" tone="subdued">{auditProgress}%</Text>
              </InlineStack>
              <ProgressBar progress={auditProgress} size="small" tone="highlight" />
            </BlockStack>
          </Banner>
        )}
        {auditStatus === "completed" && manualRefresh && (
          <Banner tone="success">
            <Text as="p">
              {resultStatus === "skipped_fresh"
                ? t(locale, "dashboardRefreshSkippedFresh")
                : t(locale, "dashboardRefreshed")}
            </Text>
          </Banner>
        )}
        {refreshFetcher.data?.type === "refresh" && refreshFetcher.data.error && (
          <Banner tone="critical">
            <Text as="p">{refreshFetcher.data.error}</Text>
          </Banner>
        )}
        {!auditRunning && auditStatus !== "completed" && banners.stale_snapshot && (
          <Banner tone="info">
            <p>{t(locale, "dashboardStaleSnapshot")}</p>
          </Banner>
        )}
        {banners.bulk_apply_in_progress.running && (
          <Banner tone="info">
            <p>
              {t(locale, "dashboardBulkApplyBanner")}{" "}
              ({banners.bulk_apply_in_progress.current}/{banners.bulk_apply_in_progress.total})
            </p>
          </Banner>
        )}

        {/* Header — shop, plan, LLM budget */}
        <DashboardHeader
          shop={dashboard.shop}
          plan={dashboard.plan}
          budget={dashboard.llm_budget}
          locale={locale}
        />

        {/* Zone 1 — Store health */}
        <Zone1 data={zone1} locale={locale} />

        <AnalysisControlPanel
          locale={locale}
          mode={analysisMode}
          lastResult={analysisResult}
          error={analysisError}
          productJob={analysisProductJob}
          disabled={isGlobalAnalysisRunning}
          onFullAnalysis={handleFullAnalysis}
          onProfileAnalysis={handleProfileAnalysis}
          onProductAnalysis={handleProductAnalysis}
        />

        {/* Business profile — niche, brand, personas, content style */}
        <BusinessProfileSection initialProfile={profileForDashboard} competitorSignals={competitorSignals} locale={locale} />

        {/* Zone 2 — Active products */}
        <ActiveProductsCard
          products={activeProducts}
          productPacks={productPacks}
          locale={locale}
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
          onAnalyzeProduct={handleAnalyzeProduct}
          onEnrichAndAnalyze={handleEnrichAndAnalyze}
          analyzingProductId={isAnalyzingSingle ? singleProductId : null}
          isAnalyzingSingle={isAnalyzingSingle}
        />

        {/* Zone 3 — Ongoing optimizations */}
        <Zone3 data={zone3} locale={locale} />

        {/* Zone 4 — Onboarding (conditional) */}
        <Zone4 data={zone4} locale={locale} />

        {/* Zone 5 — Alerts (conditional) */}
        <Zone5 data={zone5} locale={locale} />

        {/* Zone 6 — AI Visibility hidden until V2 */}
      </BlockStack>
    </Page>
  );
}
