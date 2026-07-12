import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useFetcher, useLoaderData, useRevalidator } from "@remix-run/react";
import type { ShouldRevalidateFunction } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  Checkbox,
  Divider,
  Icon,
  FormLayout,
  InlineGrid,
  InlineStack,
  Modal,
  Page,
  ProgressBar,
  Select,
  Spinner,
  Text,
  TextField,
  Tooltip,
} from "@shopify/polaris";
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  EditIcon,
  AutomationIcon,
  BookOpenIcon,
  CalendarIcon,
  CameraIcon,
  ChartHistogramGrowthIcon,
  CheckCircleIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
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
  InfoIcon,
  LockIcon,
  QuestionCircleIcon,
  PhoneIcon,
  ProductIcon,
  RefreshIcon,
  SportsIcon,
  StarFilledIcon,
  StoreIcon,
  WatchIcon,
} from "@shopify/polaris-icons";
import type { IconSource } from "@shopify/polaris";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { handleProductCardIntent } from "../lib/productCardActions.server";
import { getLocale, loaderPhrases, localizedPath, t, type Locale } from "../lib/i18n";
import { ResearchConsole } from "../components/ResearchConsole";
import { ProductCard } from "../components/ProductCard";
import { Sparkline } from "../components/Sparkline";
import { ProductContentProposals } from "../components/ProductContentProposals";
import { UsageMeter } from "../components/UsageMeter";
import {
  linesFromText,
  qualityWarningText,
  SectionTitle,
  textFromLines,
  type BusinessPersona,
  type ContentStyle,
  type ProductResult,
  type MarketJobState,
  type BusinessProfile,
} from "../lib/marketAnalysisShared";

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

interface BillingInfo {
  plan: string;
  quotas: { analysis: number; blog: number; products: number };
  usage: { analysis: number; blog: number };
}

interface LoaderData {
  shop: string;
  locale: Locale;
  plan: string;
  dashboard: DashboardData | null;
  activeProducts: ActiveProduct[];
  productResults: Record<string, ProductResult>;
  competitorSignals: string[];
  manualCompetitors: string[];
  excludedDomains: string[];
  auditJobId: string | null;
  businessProfile: BusinessProfile | null;
  inspirationIdeas: Array<{ title: string; product_title: string }>;
  gscStatus: GscStatus | null;
  ga4Connected: boolean;
  themeExt: ThemeExtStatus | null;
  learningMode: "semi_auto" | "auto_apply";
  autoAllowed: boolean;
  billing: BillingInfo | null;
  scheduleStatus: ScheduleStatus | null;
  latestAnalysisAt: string | null;
  error: string | null;
}

interface GscStatus {
  connected: boolean;
  reauth_required: boolean;
}

interface ThemeExtStatus {
  available?: boolean;
  enabled?: boolean | null;
}

interface ScheduleStatus {
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  last_reanalysis_at: string | null;
  reanalysis_frequency_days: number;
  recent_runs: Array<{ created_at?: string; status?: string }>;
}

// ── Loader ────────────────────────────────────────────────────────────────────

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const url = new URL(request.url);
  const plan = (url.searchParams.get("plan") ?? "free") as "free" | "pro" | "agency";

  // Redirect to onboarding while preserving the embedded auth context
  // (shop, host, embedded, id_token). Dropping these makes the onboarding
  // loader see a non-embedded request, fail to authenticate, and bounce to
  // /auth/login — the cause of the "asks for shop domain" loop on fresh installs.
  const redirectToOnboarding = () => {
    const params = new URLSearchParams(url.searchParams);
    params.set("locale", locale);
    return redirect(`/app/onboarding?${params.toString()}`);
  };

  let activeProducts: ActiveProduct[] = [];
  let productResults: Record<string, ProductResult> = {};
  let competitorSignals: string[] = [];
  let manualCompetitors: string[] = [];
  let excludedDomains: string[] = [];
  let auditJobId: string | null = null;
  let businessProfile: BusinessProfile | null = null;
  let inspirationIdeas: Array<{ title: string; product_title: string }> = [];
  let blogIdeaTeasers: Array<{ title: string; product_title: string }> = [];
  let gscStatus: GscStatus | null = null;
  let ga4Connected = false;
  let themeExt: ThemeExtStatus | null = null;
  let learningMode: "semi_auto" | "auto_apply" = "semi_auto";
  let autoAllowed = true;
  let billing: BillingInfo | null = null;
  let scheduleStatus: ScheduleStatus | null = null;
  // Timestamp of the last completed market analysis (incl. the one auto-run at
  // onboarding, which is NOT a scheduler run). Used as a fallback so the analysis
  // panel shows results instead of "no analysis yet" before the first scheduled tick.
  let latestAnalysisAt: string | null = null;

  try {
    // Bound every backend call so a cold/slow backend cannot hang the page
    // indefinitely. The dashboard call drives the above-the-fold content (and the
    // onboarding redirect) so it gets a more generous budget; the secondary calls
    // degrade to their default empty values on timeout via Promise.allSettled.
    const DASHBOARD_TIMEOUT_MS = 12_000;
    const SECONDARY_TIMEOUT_MS = 8_000;
    const [dashResp, productsResp, bizProfileResp, marketResp, competitorsResp, gscStatusResp, learningResp, suggResp, scheduleResp, ga4StatusResp, themeExtResp, billingResp] = await Promise.allSettled([
      callBackendForShop(shop, `/api/shops/${shop}/dashboard?plan=${plan}`, { accessToken: session.accessToken, signal: AbortSignal.timeout(DASHBOARD_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/products/active`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/business-profile/latest`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/market-analysis/latest`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/market-analysis/competitors`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/gsc/status`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/learning/settings`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/blog/idea-suggestions`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/agent-schedule/status`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/ga4/status`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/geo/theme-extension-status`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
      callBackendForShop(shop, `/api/shops/${shop}/billing/status`, { accessToken: session.accessToken, signal: AbortSignal.timeout(SECONDARY_TIMEOUT_MS) }),
    ]);

    if (billingResp.status === "fulfilled" && billingResp.value.ok) {
      try {
        const data = (await billingResp.value.json()) as {
          plan?: string;
          quotas?: { auto_analysis?: boolean; analysis?: number; blog?: number; products?: number };
          usage?: { analysis?: number; blog?: number };
        };
        autoAllowed = data.quotas?.auto_analysis !== false;
        if (data.plan && data.quotas && data.usage) {
          billing = {
            plan: data.plan,
            quotas: {
              analysis: data.quotas.analysis ?? 1,
              blog: data.quotas.blog ?? 3,
              products: data.quotas.products ?? 3,
            },
            usage: { analysis: data.usage.analysis ?? 0, blog: data.usage.blog ?? 0 },
          };
        }
      } catch (_parseErr) { /* ignore */ }
    }

    if (gscStatusResp.status === "fulfilled" && gscStatusResp.value.ok) {
      try {
        const data = (await gscStatusResp.value.json()) as { connected?: boolean; reauth_required?: boolean };
        gscStatus = { connected: data.connected === true, reauth_required: data.reauth_required === true };
      } catch (_parseErr) { /* ignore */ }
    }

    if (ga4StatusResp.status === "fulfilled" && ga4StatusResp.value.ok) {
      try {
        const data = (await ga4StatusResp.value.json()) as { ready?: boolean };
        ga4Connected = data.ready === true;
      } catch (_parseErr) { /* ignore */ }
    }

    if (themeExtResp.status === "fulfilled" && themeExtResp.value.ok) {
      try {
        themeExt = (await themeExtResp.value.json()) as ThemeExtStatus;
      } catch (_parseErr) { /* ignore */ }
    }

    if (learningResp.status === "fulfilled" && learningResp.value.ok) {
      try {
        const data = (await learningResp.value.json()) as { settings?: { mode?: string } };
        if (data.settings?.mode === "auto_apply") learningMode = "auto_apply";
      } catch (_parseErr) { /* ignore */ }
    }

    if (scheduleResp.status === "fulfilled" && scheduleResp.value.ok) {
      try {
        const data = (await scheduleResp.value.json()) as Partial<ScheduleStatus>;
        scheduleStatus = {
          enabled: data.enabled === true,
          next_run_at: data.next_run_at ?? null,
          last_run_at: data.last_run_at ?? null,
          last_reanalysis_at: data.last_reanalysis_at ?? null,
          reanalysis_frequency_days: data.reanalysis_frequency_days ?? 28,
          recent_runs: data.recent_runs ?? [],
        };
      } catch (_parseErr) { /* ignore */ }
    }

    if (competitorsResp.status === "fulfilled" && competitorsResp.value.ok) {
      try {
        const data = (await competitorsResp.value.json()) as {
          competitors?: { domain?: string }[];
          excluded?: string[];
        };
        manualCompetitors = [
          ...new Set((data.competitors ?? []).map((c) => (c.domain ?? "").trim()).filter(Boolean)),
        ];
        excludedDomains = [...new Set((data.excluded ?? []).map((d) => d.trim()).filter(Boolean))];
      } catch (_parseErr) { /* ignore */ }
    }

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
          products?: Array<ProductResult & { product_title?: string; content_test_pack?: { proposed_blog_ideas?: Array<{ title?: string }> } }>;
          competitor_signals?: { domain?: string }[];
          analyzed_at?: string | null;
        };
        latestAnalysisAt = job.analyzed_at ?? null;
        for (const result of job.products ?? []) {
          if (result.product_id) productResults[result.product_id] = result;
          if (result.product_handle) productResults[result.product_handle] = result;
        }
        // Blog ideas from the analysis (combined later with suggested ideas).
        blogIdeaTeasers = (job.products ?? [])
          .flatMap((p) => (p.content_test_pack?.proposed_blog_ideas ?? []).map((idea) => ({
            title: idea.title ?? "",
            product_title: p.product_title ?? "",
          })))
          .filter((i) => i.title);
        competitorSignals = [
          ...new Set(
            (job.competitor_signals ?? [])
              .map((c) => (c.domain ?? "").trim())
              .filter(Boolean),
          ),
        ];
      } catch (_parseErr) { /* ignore */ }
    }

    // Same source as the Blog page "Inspiration" grid: suggested ideas (seasonal/
    // competitor/advantages) first, then analysis blog ideas — capped at 4.
    let suggestionTeasers: Array<{ title: string; product_title: string }> = [];
    if (suggResp.status === "fulfilled" && suggResp.value.ok) {
      try {
        const data = (await suggResp.value.json()) as { suggestions?: Array<{ title?: string; product_title?: string }> };
        suggestionTeasers = (data.suggestions ?? [])
          .map((s) => ({ title: s.title ?? "", product_title: s.product_title ?? "" }))
          .filter((i) => i.title);
      } catch (_parseErr) { /* ignore */ }
    }
    inspirationIdeas = [...suggestionTeasers, ...blogIdeaTeasers].slice(0, 4);

    if (dashResp.status !== "fulfilled" || !dashResp.value.ok) {
      const errStatus = dashResp.status === "fulfilled" ? dashResp.value.status : 0;
      // 404 = no crawl/snapshot yet (fresh install). The dashboard has nothing to
      // show, so guide the merchant to onboarding to run the first audit instead of
      // surfacing a raw "HTTP 404". This is also the first-open experience for
      // App Store reviewers, who would otherwise land on an error screen.
      if (errStatus === 404) {
        return redirectToOnboarding();
      }
      return json<LoaderData>({
        shop, locale, plan,
        dashboard: null,
        activeProducts,
        productResults,
        competitorSignals,
        manualCompetitors,
        excludedDomains,
        auditJobId: null,
        businessProfile,
        inspirationIdeas,
        gscStatus,
        ga4Connected,
        themeExt,
        learningMode,
        autoAllowed,
        billing,
        scheduleStatus,
        latestAnalysisAt,
        error: errStatus ? `HTTP ${errStatus}` : "Network error",
      });
    }

    const dashboard = (await dashResp.value.json()) as DashboardData;

    if (!businessProfile || businessProfile.status !== "validated") {
      return redirectToOnboarding();
    }

    return json<LoaderData>({ shop, locale, plan, dashboard, activeProducts, productResults, competitorSignals, manualCompetitors, excludedDomains, auditJobId, businessProfile, inspirationIdeas, gscStatus, ga4Connected, themeExt, learningMode, autoAllowed, billing, scheduleStatus, latestAnalysisAt, error: null });
  } catch (err) {
    return json<LoaderData>({
      shop, locale, plan,
      dashboard: null,
      activeProducts,
      productResults,
      competitorSignals,
      manualCompetitors,
      excludedDomains,
      auditJobId,
      businessProfile,
      inspirationIdeas,
      gscStatus,
      ga4Connected,
      themeExt,
      learningMode,
      autoAllowed,
      billing,
      scheduleStatus,
      latestAnalysisAt,
      error: err instanceof Error ? err.message : "Network error",
    });
  }
};

// ── Action (refresh + audit job polling) ──────────────────────────────────────

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const formData = await request.formData();
  const intent = formData.get("intent") as string | null;

  // Shared ProductCard intents (apply, tags, keywords, questions…) so the dashboard
  // cards behave exactly like the Products page.
  if (intent) {
    const shared = await handleProductCardIntent(intent, formData, session);
    if (shared) return shared;
  }

  // Save merchant edits to the business profile. The profile feeds the LLM prompts
  // (brand voice, personas, content style, seasonality), so edits change future
  // analyses — that's the whole point of letting the merchant correct it here.
  if (intent === "saveBusinessProfile") {
    try {
      const profile = JSON.parse(String(formData.get("profile") ?? "{}"));
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/business-profile`,
        { accessToken: session.accessToken, method: "POST", body: JSON.stringify(profile) },
      );
      return json({ type: "saveBusinessProfile", ok: resp.ok, error: resp.ok ? null : `HTTP ${resp.status}` });
    } catch (err) {
      return json({ type: "saveBusinessProfile", ok: false, error: String(err) });
    }
  }

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

  if (intent === "setPublishMode") {
    const mode = formData.get("mode") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/learning/settings`,
        {
          accessToken: session.accessToken,
          method: "PUT",
          body: JSON.stringify({ mode }),
        },
      );
      if (!resp.ok) return json({ type: "setPublishMode", ok: false, error: `HTTP ${resp.status}` });
      // Switching back to manual also turns off the daily/28-day autonomous agent
      // so nothing is published or re-analysed in the background.
      if (mode === "semi_auto") {
        await callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/agent-schedule/disable`,
          { accessToken: session.accessToken, method: "POST" },
        ).catch(() => {});
      }
      return json({ type: "setPublishMode", ok: true, error: null });
    } catch (err) {
      return json({ type: "setPublishMode", ok: false, error: String(err) });
    }
  }

  if (intent === "activateAutoPublish") {
    try {
      // 1. Enable the daily continuous-improvement agent in auto mode. This also
      // syncs merchant_learning_settings (enabled + mode=auto_apply) and turns on
      // the 28-day background re-analysis (runs server-side via the scheduler tick,
      // no need to open the app).
      const setResp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/agent-schedule/settings`,
        { accessToken: session.accessToken, method: "PUT", body: JSON.stringify({ enabled: true, mode: "auto_apply" }) },
      );
      if (!setResp.ok) {
        return json({ type: "activateAutoPublish", ok: false, error: `HTTP ${setResp.status}`, summary: null });
      }
      // 2. Start a fresh full re-analysis (async job). It persists + auto-publishes
      // the checked proposals server-side; we don't block on it (it takes minutes).
      const pubResp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/agent-schedule/run-and-publish`,
        { accessToken: session.accessToken, method: "POST" },
      );
      const data = pubResp.ok ? ((await pubResp.json()) as { job_id?: string }) : null;
      return json({ type: "activateAutoPublish", ok: true, error: null, jobId: data?.job_id ?? null });
    } catch (err) {
      return json({ type: "activateAutoPublish", ok: false, error: String(err), jobId: null });
    }
  }

  // ── Manual scheduled re-analysis (async job + polling) ──────────────
  if (intent === "startReanalysis") {
    try {
      const selectionRaw = formData.get("selection") as string | null;
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/agent-schedule/run-and-publish`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: selectionRaw ? JSON.stringify({ selection: JSON.parse(selectionRaw) }) : undefined,
        },
      );
      if (!resp.ok) {
        return json({ type: "startReanalysis", jobId: null, error: `HTTP ${resp.status}` });
      }
      const data = (await resp.json()) as { job_id: string };
      return json({ type: "startReanalysis", jobId: data.job_id, error: null });
    } catch (err) {
      return json({ type: "startReanalysis", jobId: null, error: String(err) });
    }
  }

  if (intent === "pollReanalysis") {
    const reJobId = formData.get("jobId") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/agent-schedule/run-and-publish/${reJobId}`,
        { accessToken: session.accessToken },
      );
      if (!resp.ok) return json({ type: "pollReanalysis", job: null, error: `HTTP ${resp.status}` });
      const job = (await resp.json()) as {
        status?: string;
        error?: string | null;
        reanalysis_status?: string | null;
        reanalysis_reason?: string | null;
        auto_publish?: { mode?: string; published?: number; held?: number; skipped_reason?: string } | null;
      };
      return json({ type: "pollReanalysis", job, error: null });
    } catch (err) {
      return json({ type: "pollReanalysis", job: null, error: String(err) });
    }
  }

  if (intent === "exportReanalysis") {
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/agent-schedule/export`,
        { accessToken: session.accessToken },
      );
      if (!resp.ok) return json({ type: "exportReanalysis", payload: null, error: `HTTP ${resp.status}` });
      const payload = await resp.json();
      return json({ type: "exportReanalysis", payload, error: null });
    } catch (err) {
      return json({ type: "exportReanalysis", payload: null, error: String(err) });
    }
  }

  if (intent === "saveCompetitors") {
    const payload = formData.get("competitorsJson") as string;
    try {
      const body = JSON.parse(payload) as { competitors: { domain: string }[]; excluded: string[] };
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/market-analysis/competitors`,
        {
          accessToken: session.accessToken,
          method: "PUT",
          body: JSON.stringify(body),
        },
      );
      if (!resp.ok) {
        return json({ type: "saveCompetitors", ok: false, error: `HTTP ${resp.status}` });
      }
      return json({ type: "saveCompetitors", ok: true, error: null });
    } catch (err) {
      return json({ type: "saveCompetitors", ok: false, error: String(err) });
    }
  }

  // ── Single-product market analysis (mirror of app.products) ────────
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

// Mirrors PRODUCT_CARD_INTENTS in productCardActions.server (kept here so this
// client-side guard does not import a .server module).
const PRODUCT_CARD_MUTATION_INTENTS = new Set([
  "saveProposals", "syncSchemaFacts", "retireTag", "restoreTag", "addTag",
  "retireKeyword", "validateQuestion", "retireQuestion", "restoreQuestion", "applyToShopify",
]);

export const shouldRevalidate: ShouldRevalidateFunction = ({ formData }) => {
  if (formData?.get("jobId")) return false;
  const intent = formData?.get("intent");
  if (intent === "refresh") return false;
  if (intent === "setPublishMode") return false;
  if (intent === "activateAutoPublish") return false;
  if (intent === "startSingle") return false;
  if (intent === "saveFactsAndStartSingle") return false;
  if (intent === "pollSingle") return false;
  if (intent === "startReanalysis") return false;
  if (intent === "pollReanalysis") return false;
  if (intent === "exportReanalysis") return false;
  if (typeof intent === "string" && PRODUCT_CARD_MUTATION_INTENTS.has(intent)) return false;
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


const SUB_SCORE_KEYS: Array<{ key: keyof NonNullable<DashboardData["zone1"]["sub_scores"]>; i18n: string; help: string }> = [
  { key: "seo", i18n: "seoSubScore", help: "seoSubScoreHelp" },
  { key: "geo", i18n: "geoSubScore", help: "geoSubScoreHelp" },
  { key: "content", i18n: "contentSubScore", help: "contentSubScoreHelp" },
  { key: "technical", i18n: "technicalSubScore", help: "technicalSubScoreHelp" },
];

function DataSourcesPanel({
  locale,
  gscConnected,
  ga4Connected,
  themeExt,
  themeExtLocked = false,
}: {
  locale: Locale;
  gscConnected: boolean;
  ga4Connected: boolean;
  themeExt: ThemeExtStatus | null;
  /** True on the free plan: the theme extension is a Pro feature. */
  themeExtLocked?: boolean;
}) {
  const fr = locale === "fr";
  // Post-onboarding, connections are managed in Réglages — sending an onboarded
  // merchant back into the wizard (step framing + sales pitch) is jarring.
  const connectionsUrl = localizedPath("/app/account", locale);
  const themeEnabled = themeExt?.available ? themeExt.enabled === true : null;
  const themeWhat = fr
    ? "Publie sur votre boutique la FAQ, les données structurées et le fil d'Ariane."
    : "Publishes the FAQ, structured data and breadcrumb on your storefront.";
  const themeHowTo = fr
    ? "Activez « GEO by Organically » dans Boutique en ligne → Personnaliser → Intégrations d'app."
    : "Enable “GEO by Organically” in Online Store → Customize → App embeds.";
  const themeTooltip = themeEnabled === false ? `${themeWhat} ${themeHowTo}` : themeWhat;

  return (
    <Box background="bg-surface-secondary" padding="200" borderRadius="200">
      <BlockStack gap="100">
        <InlineStack gap="400" wrap>
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="bodySm">Shopify</Text>
            <Badge tone="success">{fr ? "Connecté" : "Connected"}</Badge>
          </InlineStack>

          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="bodySm">Google Search Console</Text>
            {gscConnected ? (
              <Badge tone="success">{fr ? "Connecté" : "Connected"}</Badge>
            ) : (
              <Button url={connectionsUrl} size="micro">{fr ? "Connecter" : "Connect"}</Button>
            )}
          </InlineStack>

          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="bodySm">Google Analytics 4</Text>
            {ga4Connected ? (
              <Badge tone="success">{fr ? "Connecté" : "Connected"}</Badge>
            ) : (
              <Button url={connectionsUrl} size="micro">{fr ? "Connecter" : "Connect"}</Button>
            )}
          </InlineStack>

          <InlineStack gap="100" blockAlign="center" wrap={false}>
            <Text as="span" variant="bodySm">{fr ? "Extension de thème" : "Theme extension"}</Text>
            <Tooltip content={themeTooltip}>
              <span style={{ display: "inline-flex", cursor: "help" }}>
                <Icon source={QuestionCircleIcon} tone="subdued" />
              </span>
            </Tooltip>
            {themeExtLocked ? (
              <Button url={localizedPath("/app/billing", locale)} size="micro" icon={LockIcon}>
                Pro
              </Button>
            ) : themeEnabled === true ? (
              <Badge tone="success">{fr ? "Activée" : "Enabled"}</Badge>
            ) : themeEnabled === false ? (
              <Badge tone="critical">{fr ? "Non activée" : "Not enabled"}</Badge>
            ) : (
              <Badge tone="info">{fr ? "Indéterminé" : "Unknown"}</Badge>
            )}
          </InlineStack>
        </InlineStack>
        {gscConnected && (
          <Text as="p" variant="bodySm">
            <a
              href="https://search.google.com/search-console"
              target="_blank"
              rel="noreferrer"
              style={{ color: "inherit" }}
            >
              {fr
                ? "Vérifiez si vos pages sont indexées sur Google Search Console →"
                : "Check if your pages are indexed on Google Search Console →"}
            </a>
          </Text>
        )}
      </BlockStack>
    </Box>
  );
}

interface EduTopic {
  id: string;
  icon: IconSource;
  question: string;
  lead: string;
  steps: string[];
  stat: string;
  close: string;
  cta?: { label: string; url: string };
}

function EducationPanel({ locale }: { locale: Locale }) {
  const fr = locale === "fr";
  const [openTopic, setOpenTopic] = useState<EduTopic | null>(null);

  const topics: EduTopic[] = [
    {
      id: "improve-geo",
      icon: GlobeIcon,
      question: fr ? "Comment améliorer son GEO ?" : "How do I improve my GEO?",
      lead: fr
        ? "ChatGPT, Perplexity ou Gemini recommandent les boutiques qu'ils comprennent le mieux. Des pages claires, factuelles et structurées font toute la différence."
        : "ChatGPT, Perplexity and Gemini recommend the stores they understand best. Clear, factual, well-structured pages make all the difference.",
      steps: fr
        ? ["Un client pose une question à l'IA", "L'IA lit vos pages produits", "Elle recommande votre boutique"]
        : ["A customer asks the AI a question", "The AI reads your product pages", "It recommends your store"],
      stat: fr
        ? "Un contenu riche en faits augmente la visibilité dans les réponses IA jusqu'à +40 %."
        : "Fact-rich content boosts visibility in AI answers by up to +40%.",
      close: fr
        ? "L'app optimise vos titres, descriptions et données structurées pour que les IA vous choisissent."
        : "The app optimizes your titles, descriptions and structured data so AIs pick you.",
      cta: { label: fr ? "Voir mes optimisations" : "See my optimizations", url: localizedPath("/app/analyse", locale) },
    },
    {
      id: "number-one",
      icon: StarFilledIcon,
      question: fr ? "Comment être numéro 1 sur les IA ?" : "How do I rank #1 on AI?",
      lead: fr
        ? "Être 1er sur Google ne suffit plus : moins de 20 % des sources citées par les IA viennent du top Google. Le classement se rejoue — et les premiers arrivés prennent la place."
        : "Ranking #1 on Google is no longer enough: less than 20% of AI-cited sources come from Google's top results. The rankings are being reshuffled — and early movers take the spot.",
      steps: fr
        ? ["Contenu structuré, lisible par les IA", "FAQ qui répond aux vraies questions clients", "Les IA vous citent comme référence"]
        : ["Structured content AIs can read", "FAQ answering real customer questions", "AIs cite you as the reference"],
      stat: fr
        ? "Le contenu structuré + FAQ est le format que les IA extraient et citent le plus volontiers."
        : "Structured content + FAQ is the format AIs extract and cite the most.",
      close: fr
        ? "L'app structure vos pages et génère vos FAQ automatiquement — pendant que vos concurrents optimisent encore pour l'ancien Google."
        : "The app structures your pages and generates your FAQs automatically — while your competitors still optimize for the old Google.",
      cta: { label: fr ? "Lancer une analyse" : "Run an analysis", url: localizedPath("/app/analyse", locale) },
    },
    {
      id: "why-28-days",
      icon: CalendarIcon,
      question: fr ? "Pourquoi attendre 28 jours ?" : "Why wait 28 days?",
      lead: fr
        ? "Google mesure l'impact d'un changement SEO sur une fenêtre d'environ 28 jours. Réagir avant, c'est décider sans données."
        : "Google measures the impact of an SEO change over a ~28-day window. Reacting sooner means deciding without data.",
      steps: fr
        ? ["J0 : optimisation publiée", "J+14 : premier signal", "J+28 : verdict fiable", "On garde ce qui marche"]
        : ["Day 0: change published", "Day 14: first signal", "Day 28: reliable verdict", "Keep what works"],
      stat: fr
        ? "L'app mesure chaque optimisation à J+14, J+28 et J+60 avec vos vraies données Google."
        : "The app measures every change at day 14, 28 and 60 with your real Google data.",
      close: fr
        ? "Chaque cycle améliore le précédent, sans jamais dégrader ce qui fonctionne."
        : "Each cycle improves on the last, without ever degrading what works.",
      cta: { label: fr ? "Suivre mes résultats" : "Track my results", url: localizedPath("/app/analyse", locale) },
    },
    {
      id: "llms-txt",
      icon: ContentIcon,
      question: fr ? "L'importance du llms.txt ?" : "Why does llms.txt matter?",
      lead: fr
        ? "Le llms.txt est le panneau d'accueil de votre boutique pour les IA : un fichier qu'elles lisent pour comprendre vos produits et vous citer correctement."
        : "llms.txt is your store's welcome sign for AIs: a file they read to understand your products and cite you correctly.",
      steps: fr
        ? ["L'app génère votre llms.txt", "Publié en 1 clic sur votre boutique", "Les IA vous lisent et vous citent"]
        : ["The app generates your llms.txt", "Published to your store in 1 click", "AIs read you and cite you"],
      stat: fr
        ? "Seulement ~10 % des sites en ont un : un vrai avantage de pionnier."
        : "Only ~10% of websites have one: a real first-mover advantage.",
      close: fr
        ? "Pendant que vos concurrents attendent, les IA apprennent à vous connaître."
        : "While your competitors wait, AIs are getting to know you.",
      cta: { label: fr ? "Publier mon llms.txt" : "Publish my llms.txt", url: localizedPath("/app/geo-llms-txt", locale) },
    },
    {
      id: "keywords",
      icon: CompassIcon,
      question: fr ? "L'importance des mots-clés ?" : "Why do keywords matter?",
      lead: fr
        ? "53 % du trafic web vient de la recherche organique. Les bons mots-clés, placés au bon endroit, amènent des clients — pas juste des visiteurs."
        : "53% of web traffic comes from organic search. The right keywords, in the right place, bring customers — not just visitors.",
      steps: fr
        ? ["Vraies données Google (GSC)", "Volumes et difficulté réels", "Injectés au bon endroit"]
        : ["Real Google data (GSC)", "Real volumes and difficulty", "Placed where they count"],
      stat: fr
        ? "Une boutique moyenne se positionne sur ~1 800 mots-clés : chacun est une porte d'entrée."
        : "An average store ranks for ~1,800 keywords: each one is a door into your shop.",
      close: fr
        ? "L'app s'appuie sur vos données réelles, pas sur des estimations — et vous donne une longueur d'avance sur les tendances avant vos concurrents."
        : "The app relies on your real data, not guesses — and puts you one step ahead of the trends before your competitors.",
      cta: { label: fr ? "Explorer mes mots-clés" : "Explore my keywords", url: localizedPath("/app/market-analysis", locale) },
    },
    {
      id: "auto-analysis",
      icon: AutomationIcon,
      question: fr ? "Comment l'Analyse automatique améliore mon ranking ?" : "How does Auto-analysis improve my ranking?",
      lead: fr
        ? "Un agent travaille pour vous chaque jour : il optimise, publie, mesure, puis recommence — uniquement sur les champs que vous avez validés."
        : "An agent works for you every day: it optimizes, publishes, measures, then repeats — only on the fields you approved.",
      steps: fr
        ? ["Analyser", "Publier", "Mesurer (28 j)", "Améliorer ↺"]
        : ["Analyze", "Publish", "Measure (28 d)", "Improve ↺"],
      stat: fr
        ? "Tous les 28 jours, vos produits sont réanalysés et seules les versions qui performent mieux sont conservées."
        : "Every 28 days your products are re-analyzed, and only better-performing versions are kept.",
      close: fr
        ? "Votre SEO progresse en continu, même quand vous dormez. Activez-la dans « Mode de publication » ci-dessous."
        : "Your SEO keeps improving, even while you sleep. Enable it in “Publish mode” below.",
    },
  ];

  return (
    <Card>
      <BlockStack gap="300">
        <BlockStack gap="100">
          <SectionTitle source={QuestionCircleIcon}>
            {fr ? "Comprendre le GEO en 2 minutes" : "Understand GEO in 2 minutes"}
          </SectionTitle>
          <Text as="p" variant="bodySm" tone="subdued">
            {fr
              ? "Pourquoi votre boutique va gagner du trafic — expliqué simplement."
              : "Why your store is going to win more traffic — explained simply."}
          </Text>
        </BlockStack>
        <InlineGrid columns={{ xs: 1, sm: 2, md: 3 }} gap="200">
          {topics.map((topic) => (
            <button
              key={topic.id}
              type="button"
              onClick={() => setOpenTopic(topic)}
              style={{ all: "unset", cursor: "pointer", display: "block", width: "100%" }}
            >
              <Box padding="300" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
                <InlineStack align="space-between" blockAlign="center" wrap={false} gap="200">
                  <InlineStack gap="200" blockAlign="center" wrap={false}>
                    <Icon source={topic.icon} tone="subdued" />
                    <Text as="h3" variant="bodySm" fontWeight="medium">{topic.question}</Text>
                  </InlineStack>
                  <Icon source={ChevronRightIcon} tone="subdued" />
                </InlineStack>
              </Box>
            </button>
          ))}
        </InlineGrid>
      </BlockStack>
      <Modal
        open={openTopic !== null}
        onClose={() => setOpenTopic(null)}
        title={openTopic?.question ?? ""}
        primaryAction={
          openTopic?.cta
            ? { content: openTopic.cta.label, url: openTopic.cta.url }
            : { content: fr ? "Compris" : "Got it", onAction: () => setOpenTopic(null) }
        }
        secondaryActions={
          openTopic?.cta ? [{ content: fr ? "Fermer" : "Close", onAction: () => setOpenTopic(null) }] : []
        }
      >
        {openTopic && (
          <Modal.Section>
            <BlockStack gap="400">
              <Text as="p" variant="bodyMd">{openTopic.lead}</Text>
              <Box background="bg-surface-secondary" padding="300" borderRadius="200">
                <InlineStack gap="200" blockAlign="center" align="center" wrap>
                  {openTopic.steps.map((step, i) => (
                    <React.Fragment key={i}>
                      {i > 0 && (
                        <Text as="span" variant="bodyMd" tone="subdued">→</Text>
                      )}
                      <Box background="bg-surface" padding="200" borderRadius="200" borderWidth="025" borderColor="border">
                        <Text as="p" variant="bodySm" fontWeight="medium" alignment="center">{step}</Text>
                      </Box>
                    </React.Fragment>
                  ))}
                </InlineStack>
              </Box>
              <Box background="bg-surface-info" padding="300" borderRadius="200">
                <Text as="p" variant="bodySm" fontWeight="medium">{openTopic.stat}</Text>
              </Box>
              <Text as="p" variant="bodyMd" tone="subdued">{openTopic.close}</Text>
            </BlockStack>
          </Modal.Section>
        )}
      </Modal>
    </Card>
  );
}

function FreePlanUpsell({ billing, locale }: { billing: BillingInfo; locale: Locale }) {
  const fr = locale === "fr";
  if (billing.plan !== "free") return null;
  const lockedPerks: string[] = fr
    ? [
        "Analyse automatique — votre SEO progresse même quand vous dormez",
        "15 produits couverts au lieu de 3",
        "Extension de thème : FAQ + données structurées sur votre boutique",
        "Une longueur d'avance sur les mots-clés et les tendances de votre niche",
      ]
    : [
        "Auto-analysis — your SEO keeps improving while you sleep",
        "15 products covered instead of 3",
        "Theme extension: FAQ + structured data on your storefront",
        "Stay ahead on the keywords and trends of your niche",
      ];
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" gap="200">
          <Text as="h2" variant="headingMd">
            {fr ? "Passez à la vitesse supérieure" : "Move up a gear"}
          </Text>
          <Badge>{fr ? "Plan Découverte" : "Starter plan"}</Badge>
        </InlineStack>
        <Text as="p" variant="bodySm" tone="subdued">
          {fr
            ? "Vos concurrents n'attendent pas. Pro analyse, publie et mesure pour vous — en continu."
            : "Your competitors aren't waiting. Pro analyzes, publishes and measures for you — continuously."}
        </Text>
        <InlineGrid columns={{ xs: 1, sm: 2 }} gap="200">
          <UsageMeter
            label={fr ? "Analyses ce cycle" : "Analyses this cycle"}
            used={billing.usage.analysis}
            quota={billing.quotas.analysis}
            locale={locale}
            showUpgrade={false}
          />
          <UsageMeter
            label={fr ? "Articles de blog ce cycle" : "Blog articles this cycle"}
            used={billing.usage.blog}
            quota={billing.quotas.blog}
            locale={locale}
            showUpgrade={false}
          />
        </InlineGrid>
        <BlockStack gap="100">
          {lockedPerks.map((perk, i) => (
            <InlineStack key={i} gap="150" blockAlign="center" wrap={false}>
              <span style={{ display: "inline-flex", opacity: 0.5 }}>
                <Icon source={LockIcon} tone="subdued" />
              </span>
              <Text as="p" variant="bodySm" tone="subdued">{perk}</Text>
            </InlineStack>
          ))}
        </BlockStack>
        <Button url={localizedPath("/app/billing", locale)} variant="primary" fullWidth>
          {fr ? "Essayer Pro 7 jours gratuitement" : "Try Pro free for 7 days"}
        </Button>
        <Text as="p" variant="bodySm" tone="subdued" alignment="center">
          {fr ? "Sans engagement · Annulation en 1 clic" : "No commitment · Cancel in 1 click"}
        </Text>
      </BlockStack>
    </Card>
  );
}

function Zone1({
  data,
  locale,
  llmsPublished,
  dataSources,
  analysisPanels,
  publishMode,
}: {
  data: DashboardData["zone1"];
  locale: Locale;
  llmsPublished: boolean;
  dataSources?: React.ReactNode;
  analysisPanels?: React.ReactNode;
  publishMode?: React.ReactNode;
}) {
  const level = data.global_level ?? "faible";
  const tone = LEVEL_TONES[level] ?? "info";
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" gap="300" wrap={false}>
          <SectionTitle source={GaugeIcon}>{t(locale, "dashboardZone1Title")}</SectionTitle>
          {data.global_score !== null && (
            <InlineStack gap="200" blockAlign="center" wrap={false}>
              <Text as="p" variant="headingXl" fontWeight="bold">
                {data.global_score}/100
              </Text>
              <Tooltip content={t(locale, "globalScoreHelp")}>
                <span style={{ display: "inline-flex", cursor: "help" }}>
                  <Icon source={InfoIcon} tone="subdued" />
                </span>
              </Tooltip>
            </InlineStack>
          )}
        </InlineStack>
        {data.global_score !== null ? (
          data.sub_scores && (
            <InlineGrid columns={4} gap="200">
              {SUB_SCORE_KEYS.map(({ key, i18n, help }) => (
                <Box key={key} background="bg-surface-secondary" padding="200" borderRadius="200">
                  <BlockStack gap="050">
                    <InlineStack gap="100" blockAlign="center" wrap={false}>
                      <Text as="p" variant="bodySm" tone="subdued">{t(locale, i18n)}</Text>
                      <Tooltip content={t(locale, help)}>
                        <span style={{ display: "inline-flex", cursor: "help" }}>
                          <Icon source={InfoIcon} tone="subdued" />
                        </span>
                      </Tooltip>
                    </InlineStack>
                    <Text as="p" variant="bodyMd" fontWeight="semibold">
                      {data.sub_scores![key]}/100
                    </Text>
                  </BlockStack>
                </Box>
              ))}
            </InlineGrid>
          )
        ) : (
          <Text as="p" tone="subdued">
            {locale === "fr" ? "Importation Shopify en cours…" : "Shopify import in progress…"}
          </Text>
        )}
        <Box background="bg-surface-secondary" padding="200" borderRadius="200">
          <InlineStack align="space-between" blockAlign="center">
            <InlineStack gap="100" blockAlign="center">
              <Text as="p" variant="bodySm">{t(locale, "llmsTxtTitle")}</Text>
              <Tooltip content={t(locale, "llmsTxtHelp")}>
                <span style={{ display: "inline-flex", cursor: "help" }}>
                  <Icon source={QuestionCircleIcon} tone="subdued" />
                </span>
              </Tooltip>
              <Badge tone={llmsPublished ? "success" : "critical"}>
                {t(locale, llmsPublished ? "llmsTxtStatusPublished" : "llmsTxtStatusNotPublished")}
              </Badge>
            </InlineStack>
            <Button url="/app/geo-llms-txt" size="slim" variant="plain">
              {t(locale, llmsPublished ? "llmsTxtManage" : "llmsTxtPublish")}
            </Button>
          </InlineStack>
        </Box>
        {dataSources}
        {publishMode && (
          <>
            <Divider />
            {publishMode}
          </>
        )}
        {analysisPanels && (
          <>
            <Divider />
            {analysisPanels}
          </>
        )}
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
          url={`${localizedPath("/app/products", locale)}&product=${encodeURIComponent(action.action_id)}`}
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
  shop,
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
  shop: string;
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
            {products.slice(0, 2).map((product) => {
              const pack = productPacks[product.id] ?? productPacks[product.handle];
              const analyzingThis = analyzingProductId === product.id;
              // With a pack → the full Products-page card. Without → a compact
              // "analyze this product" prompt.
              if (pack) {
                return (
                  <ProductCard
                    key={product.id}
                    product={pack}
                    locale={locale}
                    shop={shop}
                    isAnalyzing={analyzingThis}
                    onEnrichAndAnalyze={(answers) => onEnrichAndAnalyze(product.id, answers)}
                    analyzeDisabled={isAnalyzingSingle}
                  />
                );
              }
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
                      </InlineStack>
                      {!analyzingThis && (
                        <Button
                          size="slim"
                          onClick={() => onAnalyzeProduct(product.id)}
                          disabled={isAnalyzingSingle}
                        >
                          {t(locale, "dashboardAnalyseProduct")}
                        </Button>
                      )}
                    </InlineStack>
                    {analyzingThis && (
                      <ResearchConsole
                        locale={locale}
                        phrases={loaderPhrases(locale, "analysis")}
                        estimateMs={150_000}
                      />
                    )}
                  </BlockStack>
                </Box>
              );
            })}
            <InlineStack align="center">
              <Button url={localizedPath("/app/products", locale)} variant="plain">
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
            <Button url={localizedPath("/app/analyse", locale)} variant="secondary" size="slim">
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
    // Connections are managed in Réglages once onboarding is behind the merchant.
    gsc: "/app/account",
    ga4: "/app/account",
    niche: "/app/onboarding",
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

/** Flat rocket glyph (Polaris has no rocket icon). Inherits `color` via currentColor. */
function RocketIcon({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
      <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </svg>
  );
}

function PublishModeCard({
  currentMode,
  locale,
  bare = false,
  autoAllowed = true,
}: {
  currentMode: "semi_auto" | "auto_apply";
  locale: Locale;
  /** When true, render the content without the outer Card (to embed inside another card). */
  bare?: boolean;
  /** False when the shop's plan does not include auto-analysis (free plan). */
  autoAllowed?: boolean;
}) {
  const fetcher = useFetcher<{ type: string; ok: boolean; error: string | null }>();
  const activateFetcher = useFetcher<{ type: string; ok: boolean; error: string | null; summary: { published?: number } | null }>();
  const [selected, setSelected] = useState<"semi_auto" | "auto_apply">(currentMode);
  const [activating, setActivating] = useState(false);
  const [activateProgress, setActivateProgress] = useState(0);

  const handleToggle = (mode: "semi_auto" | "auto_apply") => {
    setSelected(mode);
    const fd = new FormData();
    fd.set("intent", "setPublishMode");
    fd.set("mode", mode);
    fetcher.submit(fd, { method: "post" });
  };

  // Turning ON automatic publishing: show an artificial progress bar
  // ("Activation… en cours" → "Activée"), set the mode AND publish everything
  // currently checked now (the action chains both backend calls).
  const handleActivateAuto = () => {
    setSelected("auto_apply");
    setActivating(true);
    setActivateProgress(8);
    const fd = new FormData();
    fd.set("intent", "activateAutoPublish");
    activateFetcher.submit(fd, { method: "post" });
  };

  useEffect(() => {
    if (!activating) return;
    const id = setInterval(() => {
      setActivateProgress((p) => (p < 90 ? p + 6 : p));
    }, 130);
    return () => clearInterval(id);
  }, [activating]);

  useEffect(() => {
    if (activateFetcher.state === "idle" && activateFetcher.data?.type === "activateAutoPublish") {
      setActivateProgress(100);
      const id = setTimeout(() => {
        setActivating(false);
      }, 450);
      return () => clearTimeout(id);
    }
  }, [activateFetcher.state, activateFetcher.data]);

  const busy = fetcher.state !== "idle";
  const isAuto = selected === "auto_apply";

  const content = (
    <BlockStack gap="300">
      <InlineGrid columns={["oneThird", "twoThirds"]} gap="300">
          {/* Publication manuelle — grisé quand l'auto est actif */}
          <div style={{ opacity: isAuto ? 0.45 : 1, display: "flex", flexDirection: "column" }}>
            <Box
              padding="300"
              borderWidth="025"
              borderRadius="200"
              borderColor="border"
              background="bg-surface-secondary"
            >
              <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: "var(--p-space-200)" }}>
                <div style={{ display: "flex", width: "100%", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ display: "inline-flex", flex: "0 0 auto", width: "1.25rem", height: "1.25rem" }}>
                    <Icon source={ContentIcon} />
                  </span>
                  <Text as="p" variant="bodyMd" fontWeight="semibold">
                    {t(locale, "publishModeManualTitle")}
                  </Text>
                </div>
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "publishModeManualDesc")}
                </Text>
                <div style={{ flex: "1 1 auto" }} />
                {!isAuto ? (
                  <span style={{ fontWeight: 700, fontSize: "0.8125rem", color: "#000" }}>
                    {locale === "fr" ? "Actif" : "Active"}
                  </span>
                ) : (
                  <Button size="slim" onClick={() => handleToggle("semi_auto")} loading={busy}>
                    {locale === "fr" ? "Activer" : "Activate"}
                  </Button>
                )}
              </div>
            </Box>
          </div>

          <div
            style={{
              background: "#000",
              color: "#fff",
              borderRadius: "var(--p-border-radius-200)",
              overflow: "hidden",
              display: "flex",
              alignItems: "stretch",
              ["--p-color-text"]: "#fff",
              ["--p-color-text-secondary"]: "#fff",
              ["--p-color-icon"]: "#fff",
            } as React.CSSProperties}
          >
            <div style={{ flex: "0 0 30%", minWidth: 88, maxWidth: 160 }}>
              <img
                src="/Logo.png"
                alt="GEO by Organically"
                style={{ width: "100%", aspectRatio: "1 / 1", objectFit: "cover", display: "block" }}
              />
            </div>
            <div style={{ flex: 1, minWidth: 0, padding: "var(--p-space-300)", display: "flex", flexDirection: "column", height: "100%", gap: "var(--p-space-200)" }}>
              <div style={{ display: "flex", width: "100%", alignItems: "center", gap: "0.5rem", justifyContent: "flex-start" }}>
                <span style={{ display: "inline-flex", flex: "0 0 auto", width: "1.25rem", height: "1.25rem" }}>
                  <RocketIcon size={20} />
                </span>
                <Text as="p" variant="bodyMd" fontWeight="semibold">
                  {t(locale, "publishModeAutoTitle")}{" "}
                  <span style={{ color: "#4285F4" }} aria-hidden="true">✦</span>
                </Text>
                <span style={{ marginLeft: "auto", flex: "0 0 auto", display: "inline-flex" }}>
                  <Tooltip content={t(locale, "publishModeAutoDisclaimer")}>
                    <span style={{ display: "inline-flex", cursor: "help" }}>
                      <Icon source={QuestionCircleIcon} />
                    </span>
                  </Tooltip>
                </span>
              </div>
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "publishModeAutoDesc")}
              </Text>
              <div style={{ flex: "1 1 auto" }} />
              {activating ? (
                <BlockStack gap="100">
                  <Text as="p" variant="bodySm">{t(locale, "publishModeActivating")}</Text>
                  <ProgressBar progress={activateProgress} size="small" tone="highlight" />
                </BlockStack>
              ) : isAuto ? (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.375rem",
                    alignSelf: "flex-start",
                    background: "#fff",
                    color: "#000",
                    borderRadius: "999px",
                    padding: "0.25rem 0.625rem",
                    fontSize: "0.75rem",
                    lineHeight: 1,
                    fontWeight: 600,
                  }}
                >
                  <RocketIcon size={14} />
                  {t(locale, "publishModeBoostedActive")}
                </span>
              ) : (
                <span
                  style={{
                    display: "block",
                    ["--p-color-bg-fill-brand"]: "#fff",
                    ["--p-color-bg-fill-brand-hover"]: "#f0f0f0",
                    ["--p-color-bg-fill-brand-active"]: "#e0e0e0",
                    ["--p-color-text-brand-on-bg-fill"]: "#000",
                  } as React.CSSProperties}
                >
                  {autoAllowed ? (
                    <Button fullWidth variant="primary" onClick={handleActivateAuto}>
                      {locale === "fr" ? "Activer" : "Activate"}
                    </Button>
                  ) : (
                    <BlockStack gap="100">
                      <Button fullWidth variant="primary" url={localizedPath("/app/billing", locale)} icon={LockIcon}>
                        {locale === "fr" ? "Débloquer avec Pro" : "Unlock with Pro"}
                      </Button>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {locale === "fr" ? "Essai gratuit 7 jours" : "7-day free trial"}
                      </Text>
                    </BlockStack>
                  )}
                </span>
              )}
            </div>
          </div>
        </InlineGrid>
    </BlockStack>
  );

  return bare ? content : <Card>{content}</Card>;
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

// ── Business Profile Section ──────────────────────────────────────────────────

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

function normalizeDomain(value: string): string {
  let raw = value.trim().toLowerCase();
  if (!raw) return "";
  raw = raw.replace(/^https?:\/\//, "").split("/")[0].split(":")[0];
  return raw.replace(/^www\./, "");
}

function CompetitorsCard({
  competitorSignals,
  manualCompetitors,
  excludedDomains,
  insights,
  locale,
}: {
  competitorSignals: string[];
  manualCompetitors: string[];
  excludedDomains: string[];
  insights: string[];
  locale: Locale;
}) {
  const fetcher = useFetcher();
  const [manual, setManual] = useState<string[]>(() =>
    [...new Set(manualCompetitors.map(normalizeDomain).filter(Boolean))],
  );
  const [excluded, setExcluded] = useState<string[]>(() =>
    [...new Set(excludedDomains.map(normalizeDomain).filter(Boolean))],
  );
  const [draft, setDraft] = useState("");

  const signals = useMemo(
    () => [...new Set(competitorSignals.map(normalizeDomain).filter(Boolean))],
    [competitorSignals],
  );
  const manualSet = useMemo(() => new Set(manual), [manual]);
  const excludedSet = useMemo(() => new Set(excluded), [excluded]);
  const displayed = useMemo(
    () => [...new Set([...signals, ...manual])].filter((d) => !excludedSet.has(d)).sort(),
    [signals, manual, excludedSet],
  );

  const persist = (nextManual: string[], nextExcluded: string[]) => {
    setManual(nextManual);
    setExcluded(nextExcluded);
    const fd = new FormData();
    fd.set("intent", "saveCompetitors");
    fd.set(
      "competitorsJson",
      JSON.stringify({
        competitors: nextManual.map((domain) => ({ domain })),
        excluded: nextExcluded,
      }),
    );
    fetcher.submit(fd, { method: "post" });
  };

  const handleAdd = () => {
    const d = normalizeDomain(draft);
    if (!d) return;
    setDraft("");
    persist(
      [...new Set([...manual, d])],
      excluded.filter((x) => x !== d),
    );
  };

  const handleRemove = (d: string) => {
    persist(
      manual.filter((x) => x !== d),
      [...new Set([...excluded, d])],
    );
  };

  return (
    <Card>
      <BlockStack gap="300">
        <SectionTitle source={GlobeIcon}>{locale === "fr" ? "Concurrents" : "Competitors"}</SectionTitle>
        <Text as="p" tone="subdued" variant="bodySm">
          {locale === "fr"
            ? "Ces concurrents nourrissent l'analyse produit. Ajoute les tiens ou retire ceux qui ne sont pas pertinents."
            : "These competitors feed the product analysis. Add your own or remove the irrelevant ones."}
        </Text>

        {displayed.length > 0 ? (
          <BlockStack gap="100">
            {displayed.map((d) => (
              <InlineStack key={d} align="space-between" blockAlign="center" gap="200">
                <InlineStack gap="150" blockAlign="center">
                  <Text as="span" variant="bodyMd">{d}</Text>
                  {!manualSet.has(d) && (
                    <Badge tone="info" size="small">{locale === "fr" ? "auto" : "auto"}</Badge>
                  )}
                </InlineStack>
                <Button
                  variant="plain"
                  tone="critical"
                  onClick={() => handleRemove(d)}
                  accessibilityLabel={`${locale === "fr" ? "Retirer" : "Remove"} ${d}`}
                >
                  ✕
                </Button>
              </InlineStack>
            ))}
          </BlockStack>
        ) : (
          <Text as="p" tone="subdued" variant="bodySm">
            {locale === "fr" ? "Aucun concurrent pour l'instant." : "No competitor yet."}
          </Text>
        )}

        <InlineStack gap="200" blockAlign="end">
          <div style={{ flex: 1 }}>
            <TextField
              label={locale === "fr" ? "Ajouter un concurrent" : "Add a competitor"}
              labelHidden
              placeholder={locale === "fr" ? "exemple.fr" : "example.com"}
              autoComplete="off"
              value={draft}
              onChange={setDraft}
            />
          </div>
          <Button onClick={handleAdd} disabled={!normalizeDomain(draft)}>
            {locale === "fr" ? "Ajouter" : "Add"}
          </Button>
        </InlineStack>

        {insights.length > 0 && (
          <BlockStack gap="050">
            {insights.map((i) => (
              <Text as="p" tone="subdued" variant="bodySm" key={i}>• {i}</Text>
            ))}
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}

type ProfileSection = null | "niche" | "voice" | "personas" | "style" | "seasonal";

function BizProfileCards({ profile, competitorSignals, manualCompetitors, excludedDomains, locale, afterRow1, variant = "all" }: { profile: BusinessProfile; competitorSignals: string[]; manualCompetitors: string[]; excludedDomains: string[]; locale: Locale; afterRow1?: React.ReactNode; variant?: "all" | "top" | "bottom" }) {
  const fr = locale === "fr";
  const intensityTone = (i: string): "success" | "warning" | "info" =>
    i === "high" ? "success" : i === "medium" ? "warning" : "info";
  const NicheIcon = getNicheIcon(profile);

  const saveFetcher = useFetcher<{ type: string; ok: boolean; error: string | null }>();
  const [editSection, setEditSection] = useState<ProfileSection>(null);
  const [draft, setDraft] = useState<BusinessProfile>(profile);
  // Edits feed the LLM prompts (brand voice, personas, content style, seasonality),
  // so saving here changes future analyses.
  useEffect(() => { setDraft(profile); }, [profile]);
  useEffect(() => {
    if (saveFetcher.state === "idle" && saveFetcher.data?.type === "saveBusinessProfile" && saveFetcher.data.ok) {
      setEditSection(null);
    }
  }, [saveFetcher.state, saveFetcher.data]);

  const cs: ContentStyle = draft.content_style ?? { tone: "", typical_article_length: "", h2_structure: [], vocabulary_to_use: [], vocabulary_to_avoid: [], hook_patterns: [] };
  const setField = (patch: Partial<BusinessProfile>) => setDraft((d) => ({ ...d, ...patch }));
  const setCS = (patch: Partial<ContentStyle>) => setDraft((d) => ({ ...d, content_style: { ...cs, ...patch } }));
  const personas = draft.target_personas ?? [];
  const setPersona = (i: number, patch: Partial<BusinessPersona>) =>
    setField({ target_personas: personas.map((p, idx) => (idx === i ? { ...p, ...patch } : p)) });
  const seasonal = draft.seasonal_patterns ?? [];
  const setSeason = (i: number, patch: Partial<{ period: string; theme: string; intensity: string }>) =>
    setField({ seasonal_patterns: seasonal.map((s, idx) => (idx === i ? { ...s, ...patch } : s)) });

  const onSave = () => saveFetcher.submit(
    { intent: "saveBusinessProfile", profile: JSON.stringify(draft) },
    { method: "post" },
  );
  const saving = saveFetcher.state !== "idle";
  const openEdit = (section: ProfileSection) => { setDraft(profile); setEditSection(section); };
  const EditBtn = ({ section }: { section: ProfileSection }) => (
    <Button variant="tertiary" icon={EditIcon} accessibilityLabel={fr ? "Modifier" : "Edit"} onClick={() => openEdit(section)} />
  );

  const sectionTitles: Record<NonNullable<ProfileSection>, string> = {
    niche: fr ? "Niche & Marque" : "Niche & Brand",
    voice: fr ? "Voix de marque" : "Brand voice",
    personas: "Personas",
    style: fr ? "Style de contenu" : "Content style",
    seasonal: fr ? "Saisonnalité & Opportunités" : "Seasonality & Gaps",
  };

  const showTop = variant !== "bottom";
  const showBottom = variant !== "top";
  return (
    <BlockStack gap="400">
      {showTop && (
      <>
      {/* Row 1 — Niche + Voix */}
      <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
        <Card>
          <BlockStack gap="200">
            <InlineStack align="space-between" blockAlign="center">
              <SectionTitle source={NicheIcon}>{sectionTitles.niche}</SectionTitle>
              <EditBtn section="niche" />
            </InlineStack>
            <Text as="p" variant="headingLg">{profile.brand_name}</Text>
            <Text as="p" tone="subdued">{profile.niche_summary}</Text>
            {(profile.key_themes ?? []).length > 0 && (
              <InlineStack gap="100" wrap>
                {profile.key_themes.map((theme) => (<Badge key={theme} tone="info">{theme}</Badge>))}
              </InlineStack>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="200">
            <InlineStack align="space-between" blockAlign="center">
              <SectionTitle source={MegaphoneIcon}>{sectionTitles.voice}</SectionTitle>
              <EditBtn section="voice" />
            </InlineStack>
            <Text as="p" variant="headingLg">{profile.content_style?.tone ?? "—"}</Text>
            <Text as="p" tone="subdued">{profile.brand_voice}</Text>
            {(profile.content_style?.vocabulary_to_use ?? []).length > 0 && (
              <InlineStack gap="100" wrap>
                {profile.content_style.vocabulary_to_use.map((v) => (<Badge key={v} tone="success">{v}</Badge>))}
                {(profile.content_style?.vocabulary_to_avoid ?? []).map((v) => (<Badge key={v} tone="critical">{v}</Badge>))}
              </InlineStack>
            )}
          </BlockStack>
        </Card>
      </InlineGrid>

      {afterRow1}
      </>
      )}

      {showBottom && (
      <>
      {/* Row 2 — Personas + Style contenu */}
      <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <SectionTitle source={PersonIcon}>{sectionTitles.personas}</SectionTitle>
              <EditBtn section="personas" />
            </InlineStack>
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
            <InlineStack align="space-between" blockAlign="center">
              <SectionTitle source={ContentIcon}>{sectionTitles.style}</SectionTitle>
              <EditBtn section="style" />
            </InlineStack>
            <Text as="p" variant="bodySm" fontWeight="semibold">
              {profile.content_style?.typical_article_length ?? ""}
            </Text>
            {(profile.content_style?.h2_structure ?? []).length > 0 && (
              <BlockStack gap="050">
                {profile.content_style.h2_structure.map((h) => (<Text as="p" tone="subdued" variant="bodySm" key={h}>• {h}</Text>))}
              </BlockStack>
            )}
            {(profile.content_style?.hook_patterns ?? []).length > 0 && (
              <BlockStack gap="050">
                {profile.content_style.hook_patterns.map((h) => (<Text as="p" tone="subdued" variant="bodySm" key={h}>→ {h}</Text>))}
              </BlockStack>
            )}
          </BlockStack>
        </Card>
      </InlineGrid>

      {/* Row 3 — Concurrents + Opportunités */}
      <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
        <CompetitorsCard
          competitorSignals={competitorSignals}
          manualCompetitors={manualCompetitors}
          excludedDomains={excludedDomains}
          insights={profile.competitor_insights ?? []}
          locale={locale}
        />

        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <SectionTitle source={CalendarIcon}>{sectionTitles.seasonal}</SectionTitle>
              <EditBtn section="seasonal" />
            </InlineStack>
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
                  {fr ? "Lacunes de contenu" : "Content gaps"}
                </Text>
                {profile.content_gaps.map((g) => (<Text as="p" tone="subdued" variant="bodySm" key={g}>• {g}</Text>))}
              </BlockStack>
            )}
          </BlockStack>
        </Card>
      </InlineGrid>
      </>
      )}

      {/* ── Edit modal (one per section) ───────────────────────────────────── */}
      <Modal
        open={editSection !== null}
        onClose={() => setEditSection(null)}
        title={editSection ? `${fr ? "Modifier" : "Edit"} — ${sectionTitles[editSection]}` : ""}
        primaryAction={{ content: fr ? "Enregistrer" : "Save", onAction: onSave, loading: saving }}
        secondaryActions={[{ content: fr ? "Annuler" : "Cancel", onAction: () => setEditSection(null) }]}
      >
        <Modal.Section>
          <BlockStack gap="300">
            <Text as="p" variant="bodySm" tone="subdued">
              {fr
                ? "Tes modifications sont prises en compte dans les prochaines analyses (génération de contenu, fiches, articles)."
                : "Your edits are applied to future analyses (content generation, products, articles)."}
            </Text>
            {editSection === "niche" && (
              <FormLayout>
                <TextField label={fr ? "Nom de marque" : "Brand name"} value={draft.brand_name ?? ""} onChange={(v) => setField({ brand_name: v })} autoComplete="off" />
                <TextField label={fr ? "Résumé de la niche" : "Niche summary"} value={draft.niche_summary ?? ""} onChange={(v) => setField({ niche_summary: v })} multiline={3} autoComplete="off" />
                <TextField label={fr ? "Thèmes clés (un par ligne)" : "Key themes (one per line)"} value={textFromLines(draft.key_themes)} onChange={(v) => setField({ key_themes: linesFromText(v) })} multiline={4} autoComplete="off" />
              </FormLayout>
            )}
            {editSection === "voice" && (
              <FormLayout>
                <TextField label={fr ? "Ton éditorial" : "Editorial tone"} value={cs.tone ?? ""} onChange={(v) => setCS({ tone: v })} autoComplete="off" />
                <TextField label={fr ? "Voix de marque" : "Brand voice"} value={draft.brand_voice ?? ""} onChange={(v) => setField({ brand_voice: v })} multiline={3} autoComplete="off" />
                <TextField label={fr ? "Vocabulaire à utiliser (un par ligne)" : "Vocabulary to use (one per line)"} value={textFromLines(cs.vocabulary_to_use)} onChange={(v) => setCS({ vocabulary_to_use: linesFromText(v) })} multiline={3} autoComplete="off" />
                <TextField label={fr ? "Vocabulaire à éviter (un par ligne)" : "Vocabulary to avoid (one per line)"} value={textFromLines(cs.vocabulary_to_avoid)} onChange={(v) => setCS({ vocabulary_to_avoid: linesFromText(v) })} multiline={3} autoComplete="off" />
              </FormLayout>
            )}
            {editSection === "personas" && (
              <BlockStack gap="300">
                {personas.map((p, i) => (
                  <Box key={i} padding="300" background="bg-surface-secondary" borderRadius="200">
                    <BlockStack gap="200">
                      <InlineStack align="space-between" blockAlign="center">
                        <Text as="p" variant="bodySm" fontWeight="semibold">{`${fr ? "Persona" : "Persona"} ${i + 1}`}</Text>
                        <Button variant="plain" tone="critical" onClick={() => setField({ target_personas: personas.filter((_, idx) => idx !== i) })}>
                          {fr ? "Retirer" : "Remove"}
                        </Button>
                      </InlineStack>
                      <TextField label={fr ? "Nom" : "Name"} value={p.name ?? ""} onChange={(v) => setPersona(i, { name: v })} autoComplete="off" />
                      <TextField label={fr ? "Besoin principal" : "Main need"} value={p.main_need ?? ""} onChange={(v) => setPersona(i, { main_need: v })} autoComplete="off" />
                      <TextField label={fr ? "Déclencheur d'achat" : "Buying trigger"} value={p.buying_trigger ?? ""} onChange={(v) => setPersona(i, { buying_trigger: v })} autoComplete="off" />
                    </BlockStack>
                  </Box>
                ))}
                <Button onClick={() => setField({ target_personas: [...personas, { name: "", description: "", main_need: "", buying_trigger: "" }] })}>
                  {fr ? "Ajouter un persona" : "Add a persona"}
                </Button>
              </BlockStack>
            )}
            {editSection === "style" && (
              <FormLayout>
                <TextField label={fr ? "Longueur d'article typique" : "Typical article length"} value={cs.typical_article_length ?? ""} onChange={(v) => setCS({ typical_article_length: v })} autoComplete="off" />
                <TextField label={fr ? "Structure H2 (un par ligne)" : "H2 structure (one per line)"} value={textFromLines(cs.h2_structure)} onChange={(v) => setCS({ h2_structure: linesFromText(v) })} multiline={4} autoComplete="off" />
                <TextField label={fr ? "Accroches (une par ligne)" : "Hook patterns (one per line)"} value={textFromLines(cs.hook_patterns)} onChange={(v) => setCS({ hook_patterns: linesFromText(v) })} multiline={3} autoComplete="off" />
              </FormLayout>
            )}
            {editSection === "seasonal" && (
              <BlockStack gap="300">
                {seasonal.map((s, i) => (
                  <Box key={i} padding="300" background="bg-surface-secondary" borderRadius="200">
                    <BlockStack gap="200">
                      <InlineStack align="space-between" blockAlign="center">
                        <Text as="p" variant="bodySm" fontWeight="semibold">{`${fr ? "Période" : "Period"} ${i + 1}`}</Text>
                        <Button variant="plain" tone="critical" onClick={() => setField({ seasonal_patterns: seasonal.filter((_, idx) => idx !== i) })}>
                          {fr ? "Retirer" : "Remove"}
                        </Button>
                      </InlineStack>
                      <TextField label={fr ? "Période" : "Period"} value={s.period ?? ""} onChange={(v) => setSeason(i, { period: v })} autoComplete="off" />
                      <TextField label={fr ? "Thème" : "Theme"} value={s.theme ?? ""} onChange={(v) => setSeason(i, { theme: v })} autoComplete="off" />
                      <Select
                        label={fr ? "Intensité" : "Intensity"}
                        options={[{ label: "high", value: "high" }, { label: "medium", value: "medium" }, { label: "low", value: "low" }]}
                        value={s.intensity ?? "medium"}
                        onChange={(v) => setSeason(i, { intensity: v })}
                      />
                    </BlockStack>
                  </Box>
                ))}
                <Button onClick={() => setField({ seasonal_patterns: [...seasonal, { period: "", theme: "", intensity: "medium" }] })}>
                  {fr ? "Ajouter une période" : "Add a period"}
                </Button>
                <TextField label={fr ? "Lacunes de contenu (une par ligne)" : "Content gaps (one per line)"} value={textFromLines(draft.content_gaps)} onChange={(v) => setField({ content_gaps: linesFromText(v) })} multiline={4} autoComplete="off" />
              </BlockStack>
            )}
            {saveFetcher.data?.ok === false && (
              <Banner tone="critical"><p>{fr ? "Échec de l'enregistrement." : "Save failed."}</p></Banner>
            )}
          </BlockStack>
        </Modal.Section>
      </Modal>
    </BlockStack>
  );
}

function BusinessProfileSummary({
  profile,
  competitorSignals,
  manualCompetitors,
  excludedDomains,
  locale,
  afterRow1,
  variant = "all",
}: {
  profile: BusinessProfile | null;
  competitorSignals: string[];
  manualCompetitors: string[];
  excludedDomains: string[];
  locale: Locale;
  afterRow1?: React.ReactNode;
  variant?: "all" | "top" | "bottom";
}) {
  if (!profile || profile.status !== "validated") return null;

  return (
    <BizProfileCards
      profile={profile}
      competitorSignals={competitorSignals}
      manualCompetitors={manualCompetitors}
      excludedDomains={excludedDomains}
      locale={locale}
      afterRow1={afterRow1}
      variant={variant}
    />
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function IndexPage() {
  const { shop, locale, plan, dashboard, activeProducts, productResults, competitorSignals, manualCompetitors, excludedDomains, auditJobId, businessProfile, inspirationIdeas, gscStatus, ga4Connected, themeExt, learningMode, autoAllowed, billing, scheduleStatus, latestAnalysisAt, error } = useLoaderData<typeof loader>() as LoaderData;
  // OAuth status is authoritative; fall back to the per-product flag (GSC data
  // file present) only when the status call itself failed.
  const gscConnected = gscStatus ? gscStatus.connected : activeProducts.some((p) => p.gsc_connected);
  const gscReauthRequired = gscStatus?.reauth_required === true;

  // ── llms.txt status ───────────────────────────────────────────────────────
  const llmsFetcher = useFetcher<{ status: { is_published: boolean; divergent: boolean } | null }>();
  useEffect(() => {
    if (llmsFetcher.state === "idle" && !llmsFetcher.data) {
      llmsFetcher.load("/app/geo-llms-txt");
    }
  }, [llmsFetcher]);
  const llmsPublished = Boolean(llmsFetcher.data?.status?.is_published);

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
      <Page title="GEO by Organically">
        <Banner tone="critical" title={t(locale, "systemStatus")}>
          <p>{error ?? t(locale, "systemUnavailable")}</p>
        </Banner>
      </Page>
    );
  }

  const { banners, zone1, zone3, zone4, zone5 } = dashboard;

  return (
    <Page title="GEO by Organically">
      <BlockStack gap="400">
        {/* Banners */}
        {auditRunning && (
          <Banner tone="info">
            <ResearchConsole
              locale={locale}
              phrases={loaderPhrases(locale, "crawl")}
              estimateMs={25_000}
              title={t(locale, "dashboardRefreshing")}
            />
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
            <BlockStack gap="200">
              <p>{t(locale, "dashboardStaleSnapshot")}</p>
              <InlineStack>
                <Button
                  icon={RefreshIcon}
                  onClick={handleRefresh}
                  loading={isRefreshing}
                  disabled={isRefreshing}
                  variant="primary"
                >
                  {t(locale, "dashboardRefresh")}
                </Button>
              </InlineStack>
            </BlockStack>
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

        {/* Business profile — niche, brand, GEO score, personas, content style */}
        {businessProfile?.status === "validated" ? (
          <BusinessProfileSummary
            profile={businessProfile}
            competitorSignals={competitorSignals}
            manualCompetitors={manualCompetitors}
            excludedDomains={excludedDomains}
            locale={locale}
            variant="top"
            afterRow1={
              <>
              <EducationPanel locale={locale} />
              {billing && <FreePlanUpsell billing={billing} locale={locale} />}
              <Zone1
                data={zone1}
                locale={locale}
                llmsPublished={llmsPublished}
                dataSources={
                  <DataSourcesPanel
                    locale={locale}
                    gscConnected={gscConnected}
                    ga4Connected={ga4Connected}
                    themeExt={themeExt}
                    themeExtLocked={billing?.plan === "free"}
                  />
                }
                analysisPanels={
                  <AnalysisSchedulePanels
                    scheduleStatus={scheduleStatus}
                    latestAnalysisAt={latestAnalysisAt}
                    locale={locale}
                    productResults={productPacks}
                    learningMode={learningMode}
                    llmsPublished={llmsPublished}
                    geoScore={zone1.global_score}
                    geoLevel={zone1.global_level}
                  />
                }
                publishMode={<PublishModeCard currentMode={learningMode} locale={locale} bare autoAllowed={autoAllowed} />}
              />
              </>
            }
          />
        ) : (
          <>
          <EducationPanel locale={locale} />
          {billing && <FreePlanUpsell billing={billing} locale={locale} />}
          <Zone1
            data={zone1}
            locale={locale}
            llmsPublished={llmsPublished}
            dataSources={
              <DataSourcesPanel
                locale={locale}
                gscConnected={gscConnected}
                ga4Connected={ga4Connected}
                themeExt={themeExt}
                themeExtLocked={billing?.plan === "free"}
              />
            }
            analysisPanels={
              <AnalysisSchedulePanels
                scheduleStatus={scheduleStatus}
                latestAnalysisAt={latestAnalysisAt}
                locale={locale}
                productResults={productPacks}
                learningMode={learningMode}
                llmsPublished={llmsPublished}
                geoScore={zone1.global_score}
                geoLevel={zone1.global_level}
              />
            }
            publishMode={<PublishModeCard currentMode={learningMode} locale={locale} bare autoAllowed={autoAllowed} />}
          />
          </>
        )}

        {/* Zone 2 — Active products */}
        <ActiveProductsCard
          products={activeProducts}
          productPacks={productPacks}
          locale={locale}
          shop={shop}
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
          onAnalyzeProduct={handleAnalyzeProduct}
          onEnrichAndAnalyze={handleEnrichAndAnalyze}
          analyzingProductId={isAnalyzingSingle ? singleProductId : null}
          isAnalyzingSingle={isAnalyzingSingle}
        />

        {/* Inspiration — 4 blog/suggested idea teasers + a single link to the Blog page. */}
        {inspirationIdeas.length > 0 && (
          <Card>
            <BlockStack gap="300">
              <SectionTitle source={BookOpenIcon}>
                {locale === "fr" ? "Inspiration pour améliorer son référencement organique" : "Inspiration to improve your organic ranking"}
              </SectionTitle>
              <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
                {inspirationIdeas.map((idea, i) => (
                  <Box key={`insp-${i}`} padding="300" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
                    <BlockStack gap="100">
                      <Text as="h3" variant="headingSm">{idea.title}</Text>
                      {idea.product_title && (
                        <Text as="p" variant="bodySm" tone="subdued">{idea.product_title}</Text>
                      )}
                    </BlockStack>
                  </Box>
                ))}
              </InlineGrid>
              <Button url={localizedPath("/app/blog", locale)} variant="primary" fullWidth>
                {locale === "fr" ? "Voir toutes les idées sur le Blog" : "See all ideas on the Blog"}
              </Button>
            </BlockStack>
          </Card>
        )}

        {/* Personas / Style de contenu / Concurrents / Saisonnalité — under Inspiration */}
        {businessProfile?.status === "validated" && (
          <BusinessProfileSummary
            profile={businessProfile}
            competitorSignals={competitorSignals}
            manualCompetitors={manualCompetitors}
            excludedDomains={excludedDomains}
            locale={locale}
            variant="bottom"
          />
        )}

        {/* Zone 5 — Alerts (conditional) */}
        <Zone5 data={zone5} locale={locale} />

        {/* Zone 6 — AI Visibility hidden until V2 */}

        {/* Bottom breathing room so the last panel isn't glued to the page edge. */}
        <Box paddingBlockEnd="800" />
      </BlockStack>
    </Page>
  );
}

// Applyable proposal fields, using the backend field names stored in
// `auto_publish_fields` / `applied_fields` (alt_text is "image_alts" there).
const VALIDATE_FIELDS = ["meta_title", "meta_description", "description", "image_alts"] as const;
type ValidateField = (typeof VALIDATE_FIELDS)[number];
const VALIDATE_FIELD_LABELS: Record<ValidateField, Parameters<typeof t>[1]> = {
  meta_title: "proposalFieldMetaTitle",
  meta_description: "proposalFieldMetaDescription",
  description: "proposalFieldDescription",
  image_alts: "proposalFieldAltText",
};

function proposedValueFor(pack: ProductResult["content_test_pack"], field: ValidateField): string {
  switch (field) {
    case "meta_title":
      return pack.proposed_meta_title || "";
    case "meta_description":
      return pack.proposed_meta_description || "";
    case "description":
      return pack.proposed_product_description || "";
    case "image_alts":
      return (pack.proposed_image_alts ?? []).map((a) => a.proposed_alt).filter(Boolean).join(" · ");
  }
}

function hasProposalFor(pack: ProductResult["content_test_pack"], field: ValidateField): boolean {
  switch (field) {
    case "meta_title":
      return Boolean(pack.proposed_meta_title) && pack.proposed_meta_title !== pack.current_meta_title;
    case "meta_description":
      return Boolean(pack.proposed_meta_description) && pack.proposed_meta_description !== pack.current_meta_description;
    case "description":
      return Boolean(pack.proposed_product_description);
    case "image_alts":
      return (pack.proposed_image_alts ?? []).some((a) => Boolean(a.proposed_alt));
  }
}

// Apple-calendar-style mini month: a red dot marks the next-result day, and
// hovering it shows what the analysis will produce. Polaris DatePicker can't
// render per-day markers, so we build a lightweight Monday-first grid instead.
type CalendarMarker = { date: Date; color: string; tooltip: string };

function MiniCalendar({
  month,
  year,
  markers,
  onPrev,
  onNext,
  locale,
}: {
  month: number;
  year: number;
  markers: CalendarMarker[];
  onPrev: () => void;
  onNext: () => void;
  locale: Locale;
}) {
  const intl = locale === "fr" ? "fr-FR" : "en-US";
  const monthLabel = new Date(year, month, 1).toLocaleDateString(intl, {
    month: "long",
    year: "numeric",
  });
  const weekdays =
    locale === "fr"
      ? ["L", "M", "M", "J", "V", "S", "D"]
      : ["M", "T", "W", "T", "F", "S", "S"];
  const offset = (new Date(year, month, 1).getDay() + 6) % 7; // Monday-first
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [];
  for (let i = 0; i < offset; i += 1) cells.push(null);
  for (let d = 1; d <= daysInMonth; d += 1) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);
  const markersFor = (d: number) =>
    markers.filter(
      (m) =>
        m.date.getDate() === d &&
        m.date.getMonth() === month &&
        m.date.getFullYear() === year,
    );

  return (
    <BlockStack gap="200">
      <InlineStack align="space-between" blockAlign="center">
        <Button variant="tertiary" icon={ChevronLeftIcon} onClick={onPrev} accessibilityLabel="<" />
        <Text as="span" variant="headingSm">{monthLabel}</Text>
        <Button variant="tertiary" icon={ChevronRightIcon} onClick={onNext} accessibilityLabel=">" />
      </InlineStack>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "2px", textAlign: "center" }}>
        {weekdays.map((w, i) => (
          <Text key={`wd-${i}`} as="span" variant="bodySm" tone="subdued">{w}</Text>
        ))}
        {cells.map((d, i) => {
          if (d == null) return <div key={`e-${i}`} />;
          const dayMarkers = markersFor(d);
          const cell = (
            <div style={{ position: "relative", padding: "6px 0", minHeight: "28px" }}>
              <Text as="span" variant="bodySm" fontWeight={dayMarkers.length > 0 ? "bold" : "regular"}>{d}</Text>
              {dayMarkers.length > 0 && (
                <span
                  style={{
                    position: "absolute",
                    bottom: "3px",
                    left: "50%",
                    transform: "translateX(-50%)",
                    display: "flex",
                    gap: "2px",
                  }}
                >
                  {dayMarkers.map((m, j) => (
                    <span
                      key={j}
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background: m.color,
                      }}
                    />
                  ))}
                </span>
              )}
            </div>
          );
          return dayMarkers.length > 0 ? (
            <Tooltip key={`d-${i}`} content={dayMarkers.map((m) => m.tooltip).join(" · ")}>{cell}</Tooltip>
          ) : (
            <div key={`d-${i}`}>{cell}</div>
          );
        })}
      </div>
    </BlockStack>
  );
}

/** Human-readable outcome of a finished run-and-publish job (why it did/didn't publish). */
function reanalysisResultMessage(
  locale: Locale,
  job: {
    reanalysis_status?: string | null;
    reanalysis_reason?: string | null;
    auto_publish?: { mode?: string; published?: number; held?: number; skipped_reason?: string } | null;
  },
): string {
  if (job.reanalysis_status === "skipped") {
    if (job.reanalysis_reason === "budget_exceeded") return t(locale, "reanalysisResultBudget");
    if (job.reanalysis_reason === "no_snapshot") return t(locale, "reanalysisResultNoSnapshot");
  }
  const ap = job.auto_publish;
  if (!ap || ap.mode !== "auto") return t(locale, "reanalysisResultManual");
  if (ap.skipped_reason === "no_token") return t(locale, "reanalysisResultNoToken");
  if ((ap.published ?? 0) > 0) {
    return t(locale, "reanalysisResultPublished").replace("{count}", String(ap.published));
  }
  if ((ap.held ?? 0) > 0) {
    return t(locale, "reanalysisResultHeld").replace("{count}", String(ap.held));
  }
  return t(locale, "reanalysisResultNoChange");
}

function AnalysisSchedulePanels({
  scheduleStatus,
  latestAnalysisAt,
  locale,
  productResults,
  learningMode,
  llmsPublished,
  geoScore,
  geoLevel,
}: {
  scheduleStatus: ScheduleStatus | null;
  latestAnalysisAt: string | null;
  locale: Locale;
  productResults: Record<string, ProductResult>;
  learningMode: "semi_auto" | "auto_apply";
  llmsPublished: boolean;
  geoScore: number | null;
  geoLevel: string | null;
}) {
  const isGreen = geoLevel ? LEVEL_TONES[geoLevel] === "success" : false;
  const dateLocale = locale === "fr" ? "fr-FR" : "en-US";
  const fmt = (iso: string | null | undefined): string | null => {
    if (!iso) return null;
    const d = new Date(iso);
    return Number.isNaN(d.getTime())
      ? null
      : d.toLocaleDateString(dateLocale, { day: "numeric", month: "long", year: "numeric" });
  };

  // Effective "last analysis" = the scheduled re-analysis if one ran, otherwise the
  // last market analysis (e.g. the one auto-run at onboarding, which is not a
  // scheduler run). Lets the panel show results before the first scheduled tick.
  const effectiveLastAnalysisIso = scheduleStatus?.last_reanalysis_at ?? latestAnalysisAt ?? null;
  const frequencyDays = scheduleStatus?.reanalysis_frequency_days ?? 28;

  // Next full analysis = last analysis + frequency (shown even when the daily
  // agent is off, so the merchant sees the projected result date), falling back to
  // the next agent run. Drives both the "upcoming" line and the calendar highlight.
  const nextFull = useMemo<Date | null>(() => {
    if (effectiveLastAnalysisIso) {
      const last = new Date(effectiveLastAnalysisIso);
      if (!Number.isNaN(last.getTime())) {
        return new Date(last.getTime() + frequencyDays * 86_400_000);
      }
    }
    if (scheduleStatus?.enabled && scheduleStatus.next_run_at) {
      const next = new Date(scheduleStatus.next_run_at);
      if (!Number.isNaN(next.getTime())) return next;
    }
    return null;
  }, [scheduleStatus, effectiveLastAnalysisIso, frequencyDays]);

  const lastAnalysis = useMemo<Date | null>(() => {
    if (!effectiveLastAnalysisIso) return null;
    const d = new Date(effectiveLastAnalysisIso);
    return Number.isNaN(d.getTime()) ? null : d;
  }, [effectiveLastAnalysisIso]);

  const calendarTarget = nextFull ?? new Date();
  const [{ month, year }, setCalendar] = useState({
    month: calendarTarget.getMonth(),
    year: calendarTarget.getFullYear(),
  });

  // Jump the calendar to the month of the next result whenever it changes (e.g.
  // after a re-analysis completes and the loader revalidates), so the highlighted
  // date is actually visible instead of staying on the initial month.
  useEffect(() => {
    if (nextFull) setCalendar({ month: nextFull.getMonth(), year: nextFull.getFullYear() });
  }, [nextFull?.getTime()]);

  const runs = (scheduleStatus?.recent_runs ?? []).slice(0, 5);
  const statusTone = (status?: string): "success" | "critical" | "attention" =>
    status === "completed" ? "success" : status === "error" ? "critical" : "attention";

  const startFetcher = useFetcher<{ type?: string; jobId?: string | null; error?: string | null }>();
  const pollFetcher = useFetcher<{
    type?: string;
    job?: {
      status?: string;
      reanalysis_status?: string | null;
      reanalysis_reason?: string | null;
      auto_publish?: { mode?: string; published?: number; held?: number; skipped_reason?: string } | null;
    } | null;
  }>();
  const exportFetcher = useFetcher<{ type?: string; payload?: unknown; error?: string | null }>();
  const revalidator = useRevalidator();

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [finished, setFinished] = useState<null | "completed" | "error">(null);
  const [resultMsg, setResultMsg] = useState<string | null>(null);

  // Capture the job_id returned by the start action and begin polling.
  useEffect(() => {
    if (startFetcher.data?.type !== "startReanalysis") return;
    if (startFetcher.data.jobId) {
      setJobId(startFetcher.data.jobId);
      setFinished(null);
    } else if (startFetcher.data.error) {
      setFinished("error");
    }
  }, [startFetcher.data]);

  // Poll the job every 5 s until it completes (analysis runs server-side).
  useEffect(() => {
    if (!jobId) return;
    const tick = () => pollFetcher.submit({ intent: "pollReanalysis", jobId }, { method: "post" });
    tick();
    const id = setInterval(tick, 5_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  // On completion, stop polling and refresh the loader data (history/next dates).
  useEffect(() => {
    const job = pollFetcher.data?.job;
    const status = job?.status;
    if (jobId && (status === "completed" || status === "error")) {
      setJobId(null);
      setFinished(status);
      // Surface *why* the auto-publish did (or did not) apply anything, so a
      // "success" banner never hides a manual-mode / held / no-change outcome.
      if (status === "completed" && job) {
        setResultMsg(reanalysisResultMessage(locale, job));
      }
      revalidator.revalidate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollFetcher.data]);

  // Download the export JSON client-side once the action returns the payload.
  useEffect(() => {
    if (exportFetcher.data?.type !== "exportReanalysis" || !exportFetcher.data.payload) return;
    const blob = new Blob([JSON.stringify(exportFetcher.data.payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `reanalysis-export-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, [exportFetcher.data]);

  const running = jobId !== null || startFetcher.state !== "idle";
  const exporting = exportFetcher.state !== "idle";

  // Warn when re-running before the configured cadence has elapsed (1/14/28 days).
  const tooSoon = useMemo<boolean>(() => {
    if (!scheduleStatus?.last_reanalysis_at) return false;
    const last = new Date(scheduleStatus.last_reanalysis_at);
    if (Number.isNaN(last.getTime())) return false;
    const elapsedDays = (Date.now() - last.getTime()) / 86_400_000;
    return elapsedDays < scheduleStatus.reanalysis_frequency_days;
  }, [scheduleStatus]);

  // ── Validation des résultats ────────────────────────────────────────────────
  const isAuto = learningMode === "auto_apply";

  // Dedup the analysis products (productResults is keyed by both id and handle).
  const analyzed = useMemo<ProductResult[]>(() => {
    const seen = new Set<string>();
    const out: ProductResult[] = [];
    for (const p of Object.values(productResults)) {
      if (!p?.product_id || seen.has(p.product_id)) continue;
      seen.add(p.product_id);
      out.push(p);
    }
    return out;
  }, [productResults]);

  const appliedFor = (pack: ProductResult["content_test_pack"], field: ValidateField): string | null =>
    (pack.applied_fields ?? {})[field] ?? null;

  // A product has something to validate when it carries an applyable proposal
  // that is not yet applied.
  const validatable = useMemo(
    () =>
      analyzed.filter((p) =>
        VALIDATE_FIELDS.some((f) => hasProposalFor(p.content_test_pack, f) && !appliedFor(p.content_test_pack, f)),
      ),
    [analyzed],
  );
  const hasUnapplied = validatable.length > 0;
  const hasApplied = useMemo(
    () => analyzed.some((p) => Object.keys(p.content_test_pack.applied_fields ?? {}).length > 0),
    [analyzed],
  );

  const [validateOpen, setValidateOpen] = useState(false);
  const [appliedOpen, setAppliedOpen] = useState(false);

  // Per-product checked set (backend field names), seeded from auto_publish_fields
  // (or, absent any saved selection, every unapplied field that has a proposal).
  const seedChecked = (): Record<string, Set<ValidateField>> => {
    const map: Record<string, Set<ValidateField>> = {};
    for (const p of analyzed) {
      const pack = p.content_test_pack;
      const persisted = pack.auto_publish_fields;
      const set = new Set<ValidateField>(
        persisted
          ? VALIDATE_FIELDS.filter((f) => persisted.includes(f))
          : VALIDATE_FIELDS.filter((f) => hasProposalFor(pack, f) && !appliedFor(pack, f)),
      );
      map[p.product_id] = set;
    }
    return map;
  };
  const [checked, setChecked] = useState<Record<string, Set<ValidateField>>>(seedChecked);
  const analyzedSig = useMemo(
    () => analyzed.map((p) => `${p.product_id}:${(p.content_test_pack.auto_publish_fields ?? []).join(",")}`).join("|"),
    [analyzed],
  );
  useEffect(() => {
    setChecked(seedChecked());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analyzedSig]);

  // Optimistically mark fields applied after a successful per-product apply, so
  // the validate list collapses and the "applied" icon appears without a reload.
  const [optimisticApplied, setOptimisticApplied] = useState<Record<string, Set<ValidateField>>>({});

  const autoPublishFetcher = useFetcher();
  const applyFetcher = useFetcher<{ type?: string; applied_fields?: Record<string, string> }>();
  const schemaFetcher = useFetcher();
  const llmsGenerateFetcher = useFetcher();
  const llmsPublishFetcher = useFetcher();
  const [applyingId, setApplyingId] = useState<string | null>(null);

  const toggleField = (productId: string, field: ValidateField) => {
    setChecked((prev) => {
      const next = { ...prev };
      const set = new Set(next[productId] ?? []);
      if (set.has(field)) set.delete(field);
      else set.add(field);
      next[productId] = set;
      autoPublishFetcher.submit(
        { intent: "setAutoPublishFields", productId, autoPublishFields: JSON.stringify([...set]) },
        { method: "post" },
      );
      return next;
    });
  };

  const validateProduct = (productId: string) => {
    const fields = [...(checked[productId] ?? [])];
    if (fields.length === 0) return;
    setApplyingId(productId);
    applyFetcher.submit(
      { intent: "applyToShopify", productId, fields: JSON.stringify(fields) },
      { method: "post" },
    );
    // Push the JSON-LD (schema facts) for this product alongside the text fields.
    schemaFetcher.submit({ intent: "syncSchemaFacts", productId }, { method: "post" });
  };

  // When an apply returns, record the applied fields optimistically.
  useEffect(() => {
    if (applyFetcher.data?.type !== "applyToShopify" || !applyingId) return;
    const appliedKeys = Object.keys(applyFetcher.data.applied_fields ?? {}) as ValidateField[];
    if (appliedKeys.length > 0) {
      setOptimisticApplied((prev) => ({
        ...prev,
        [applyingId]: new Set([...(prev[applyingId] ?? []), ...appliedKeys]),
      }));
    }
    setApplyingId(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applyFetcher.data]);

  const isApplied = (productId: string, pack: ProductResult["content_test_pack"], field: ValidateField): boolean =>
    Boolean(appliedFor(pack, field)) || (optimisticApplied[productId]?.has(field) ?? false);

  const republishLlms = () => {
    llmsGenerateFetcher.submit({ intent: "generate" }, { method: "post", action: "/app/geo-llms-txt" });
    llmsPublishFetcher.submit(
      { intent: "publish", confirm: "true" },
      { method: "post", action: "/app/geo-llms-txt" },
    );
  };
  const llmsBusy = llmsGenerateFetcher.state !== "idle" || llmsPublishFetcher.state !== "idle";

  // Show the validate-results CTA only in non-auto mode when something is pending.
  const showValidateButton = !isAuto && hasUnapplied;
  // The "applied" icon shows once anything is applied (immediate in auto mode).
  const hasAnyApplied =
    hasApplied || Object.values(optimisticApplied).some((s) => s.size > 0);

  return (
    <InlineGrid columns={{ xs: 1, md: 2 }} gap="400">
      <Box background="bg-surface-secondary" padding="300" borderRadius="200" minHeight="100%">
        <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: "var(--p-space-400)" }}>
          <Text as="h3" variant="headingSm">{t(locale, "analysisPanelTitle")}</Text>

          <BlockStack gap="200">
            {effectiveLastAnalysisIso && (
              <InlineStack align="space-between" blockAlign="center">
                <Text as="span" tone="subdued">{t(locale, "lastFullAnalysis")}</Text>
                <InlineStack gap="100" blockAlign="center">
                  <Text as="span">{fmt(effectiveLastAnalysisIso)}</Text>
                  {hasAnyApplied && (
                    <Tooltip content={t(locale, "appliedIconTooltip")}>
                      <Button
                        variant="plain"
                        icon={CheckCircleIcon}
                        accessibilityLabel={t(locale, "appliedIconTooltip")}
                        onClick={() => setAppliedOpen(true)}
                      />
                    </Tooltip>
                  )}
                </InlineStack>
              </InlineStack>
            )}
            {runs.length > 0 ? (
              runs.map((run, i) => (
                <InlineStack key={i} align="space-between" blockAlign="center">
                  <Text as="span">{fmt(run.created_at) ?? "—"}</Text>
                  <Badge tone={statusTone(run.status)}>{run.status ?? "—"}</Badge>
                </InlineStack>
              ))
            ) : (
              !effectiveLastAnalysisIso && (
                <Text as="p" tone="subdued">{t(locale, "analysisHistoryEmpty")}</Text>
              )
            )}
          </BlockStack>

          <Divider />

          {scheduleStatus?.enabled ? (
            <BlockStack gap="100">
              <InlineStack align="space-between">
                <Text as="span" tone="subdued">{t(locale, "nextDailyRun")}</Text>
                <Text as="span">{fmt(scheduleStatus.next_run_at) ?? "—"}</Text>
              </InlineStack>
              <InlineStack align="space-between">
                <Text as="span" tone="subdued">{t(locale, "nextFullAnalysis")}</Text>
                <Text as="span">{nextFull ? fmt(nextFull.toISOString()) : "—"}</Text>
              </InlineStack>
            </BlockStack>
          ) : (
            <Text as="p" tone="subdued">{t(locale, "noUpcomingAnalysis")}</Text>
          )}

          {running && (
            <ResearchConsole locale={locale} phrases={loaderPhrases(locale, "analysis")} estimateMs={150_000} />
          )}
          {!running && finished === "completed" && (
            <Banner tone="success">
              <BlockStack gap="100">
                <Text as="p">{t(locale, "runReanalysisSuccess")}</Text>
                {resultMsg && <Text as="p" fontWeight="medium">{resultMsg}</Text>}
              </BlockStack>
            </Banner>
          )}
          {!running && finished === "error" && (
            <Banner tone="critical">{t(locale, "runReanalysisError")}</Banner>
          )}
          {exportFetcher.data?.type === "exportReanalysis" && exportFetcher.data.error && (
            <Banner tone="critical">{t(locale, "exportReanalysisError")}</Banner>
          )}

          <div style={{ flex: "1 1 auto" }} />

          <BlockStack gap="200">
            <Button
              variant="primary"
              fullWidth
              icon={RefreshIcon}
              loading={running}
              disabled={running}
              onClick={() => setConfirmOpen(true)}
            >
              {t(locale, "runReanalysisNowButton")}
            </Button>
            {showValidateButton && (
              <Button fullWidth disabled={running} onClick={() => setValidateOpen(true)}>
                {t(locale, "validateResultsButton")}
              </Button>
            )}
            <Button
              fullWidth
              loading={exporting}
              disabled={running}
              onClick={() => exportFetcher.submit({ intent: "exportReanalysis" }, { method: "post" })}
            >
              {t(locale, "exportReanalysisButton")}
            </Button>
          </BlockStack>
        </div>
      </Box>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title={t(locale, "runReanalysisConfirmTitle")}
        primaryAction={{
          content: t(locale, "runReanalysisConfirmCta"),
          loading: running,
          onAction: () => {
            const selection = Object.fromEntries(
              analyzed.map((p) => [p.product_id, [...(checked[p.product_id] ?? [])]]),
            );
            startFetcher.submit(
              { intent: "startReanalysis", selection: JSON.stringify(selection) },
              { method: "post" },
            );
            setConfirmOpen(false);
          },
        }}
        secondaryActions={[{ content: t(locale, "runReanalysisCancel"), onAction: () => setConfirmOpen(false) }]}
      >
        <Modal.Section>
          <BlockStack gap="300">
            {tooSoon && (
              <Banner tone="warning">
                {t(locale, "runReanalysisTooSoonWarning").replace(
                  "{days}",
                  String(scheduleStatus?.reanalysis_frequency_days ?? ""),
                )}
              </Banner>
            )}
            <Text as="p">{t(locale, "runReanalysisConfirmBody")}</Text>
            {analyzed.length > 0 && (
              <BlockStack gap="300">
                <Text as="h3" variant="headingSm">{t(locale, "runReanalysisSelectTitle")}</Text>
                {analyzed.map((p) => {
                  const set = checked[p.product_id] ?? new Set<ValidateField>();
                  return (
                    <BlockStack key={p.product_id} gap="100">
                      <Text as="h4" variant="headingXs">{p.product_title}</Text>
                      {VALIDATE_FIELDS.map((f) => (
                        <Checkbox
                          key={f}
                          checked={set.has(f)}
                          onChange={() => toggleField(p.product_id, f)}
                          label={t(locale, VALIDATE_FIELD_LABELS[f])}
                        />
                      ))}
                    </BlockStack>
                  );
                })}
              </BlockStack>
            )}
          </BlockStack>
        </Modal.Section>
      </Modal>

      <Modal
        open={validateOpen}
        onClose={() => setValidateOpen(false)}
        title={t(locale, "validateResultsTitle")}
        secondaryActions={[{ content: t(locale, "runReanalysisCancel"), onAction: () => setValidateOpen(false) }]}
      >
        <Modal.Section>
          {validatable.length === 0 ? (
            <Text as="p" tone="subdued">{t(locale, "validateResultsEmpty")}</Text>
          ) : (
            <BlockStack gap="400">
              {geoScore !== null && (
                <Box background="bg-surface-secondary" padding="300" borderRadius="200">
                  <InlineStack align="space-between" blockAlign="center">
                    <Text as="span" variant="bodyMd" fontWeight="semibold">{t(locale, "impactScoreCard")}</Text>
                    <InlineStack gap="200" blockAlign="center">
                      <Text as="span" variant="headingMd" fontWeight="bold">{geoScore}/100</Text>
                      {geoLevel && LEVEL_I18N_KEYS[geoLevel] && (
                        <Badge tone={LEVEL_TONES[geoLevel] ?? "info"}>{t(locale, LEVEL_I18N_KEYS[geoLevel])}</Badge>
                      )}
                    </InlineStack>
                  </InlineStack>
                </Box>
              )}
              {geoScore !== null && !isGreen && (
                <Banner
                  tone="warning"
                  action={{
                    content: t(locale, "validateImproveCta"),
                    url: localizedPath("/app/analyse", locale),
                  }}
                >
                  {t(locale, "validateImproveBanner")}
                </Banner>
              )}
              {validatable.map((p) => {
                const pack = p.content_test_pack;
                const fields = VALIDATE_FIELDS.filter(
                  (f) => hasProposalFor(pack, f) && !isApplied(p.product_id, pack, f),
                );
                if (fields.length === 0) return null;
                const set = checked[p.product_id] ?? new Set<ValidateField>();
                return (
                  <BlockStack key={p.product_id} gap="200">
                    <Text as="h4" variant="headingSm">{p.product_title}</Text>
                    {fields.map((f) => (
                      <Checkbox
                        key={f}
                        checked={set.has(f)}
                        onChange={() => toggleField(p.product_id, f)}
                        label={t(locale, VALIDATE_FIELD_LABELS[f])}
                        helpText={proposedValueFor(pack, f) || undefined}
                      />
                    ))}
                    <InlineStack gap="200">
                      <Button
                        variant="primary"
                        loading={applyingId === p.product_id}
                        disabled={set.size === 0 || applyingId !== null}
                        onClick={() => validateProduct(p.product_id)}
                      >
                        {t(locale, "validateApplyCta")}
                      </Button>
                      {isGreen ? (
                        <Button
                          url={`${localizedPath("/app/products", locale)}&product=${encodeURIComponent(p.product_id)}`}
                        >
                          {t(locale, "validateMoreDetails")}
                        </Button>
                      ) : (
                        <Button
                          url={`${localizedPath("/app/products", locale)}&product=${encodeURIComponent(p.product_id)}`}
                        >
                          {t(locale, "validateImproveCta")}
                        </Button>
                      )}
                    </InlineStack>
                    <Divider />
                  </BlockStack>
                );
              })}
              {llmsPublished ? (
                <Button fullWidth loading={llmsBusy} onClick={republishLlms}>
                  {t(locale, "republishLlmsButton")}
                </Button>
              ) : (
                <Text as="p" tone="subdued" variant="bodySm">{t(locale, "llmsTxtSetupHint")}</Text>
              )}
            </BlockStack>
          )}
        </Modal.Section>
      </Modal>

      <Modal
        open={appliedOpen}
        onClose={() => setAppliedOpen(false)}
        title={t(locale, "appliedChangesTitle")}
        primaryAction={{
          content: t(locale, "appliedViewInAnalyse"),
          url: localizedPath("/app/analyse", locale),
        }}
        secondaryActions={[{ content: t(locale, "runReanalysisCancel"), onAction: () => setAppliedOpen(false) }]}
      >
        <Modal.Section>
          {(() => {
            const rows = analyzed
              .map((p) => {
                const pack = p.content_test_pack;
                const fields = VALIDATE_FIELDS.filter((f) => isApplied(p.product_id, pack, f));
                return { product: p, pack, fields };
              })
              .filter((r) => r.fields.length > 0);
            if (rows.length === 0) {
              return <Text as="p" tone="subdued">{t(locale, "appliedChangesEmpty")}</Text>;
            }
            return (
              <BlockStack gap="400">
                {isAuto && <Banner tone="info">{t(locale, "autoAppliedNote")}</Banner>}
                {rows.map(({ product, pack, fields }) => (
                  <BlockStack key={product.product_id} gap="100">
                    <Text as="h4" variant="headingSm">{product.product_title}</Text>
                    {fields.map((f) => {
                      const at = appliedFor(pack, f);
                      return (
                        <InlineStack key={f} align="space-between" blockAlign="center">
                          <Text as="span" tone="subdued">{t(locale, VALIDATE_FIELD_LABELS[f])}</Text>
                          <Text as="span">{at ? fmt(at) : "✓"}</Text>
                        </InlineStack>
                      );
                    })}
                    <Divider />
                  </BlockStack>
                ))}
              </BlockStack>
            );
          })()}
        </Modal.Section>
      </Modal>

      <Box background="bg-surface-secondary" padding="300" borderRadius="200">
        <BlockStack gap="300">
          <Text as="h3" variant="headingSm">{t(locale, "analysisCalendarTitle")}</Text>
          <MiniCalendar
            month={month}
            year={year}
            markers={[
              ...(lastAnalysis
                ? [{
                    date: lastAnalysis,
                    color: "#e8800c",
                    tooltip: `${t(locale, "calendarLastDotTooltip")} · ${fmt(lastAnalysis.toISOString())}`,
                  }]
                : []),
              ...(nextFull
                ? [{
                    date: nextFull,
                    color: "var(--p-color-bg-fill-critical)",
                    tooltip: `${t(locale, "calendarDotTooltip")} · ${fmt(nextFull.toISOString())}`,
                  }]
                : []),
            ]}
            onPrev={() => {
              const d = new Date(year, month - 1, 1);
              setCalendar({ month: d.getMonth(), year: d.getFullYear() });
            }}
            onNext={() => {
              const d = new Date(year, month + 1, 1);
              setCalendar({ month: d.getMonth(), year: d.getFullYear() });
            }}
            locale={locale}
          />
        </BlockStack>
      </Box>
    </InlineGrid>
  );
}
