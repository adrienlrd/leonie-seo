import type { LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Page,
  ProgressBar,
  Text,
  Tooltip,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { Sparkline } from "../components/Sparkline";

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

interface LoaderData {
  shop: string;
  locale: Locale;
  plan: string;
  dashboard: DashboardData | null;
  activeProducts: ActiveProduct[];
  error: string | null;
}

// ── Loader ────────────────────────────────────────────────────────────────────

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  // Detect plan from query param (forwarded from billing session) — defaults to "free"
  const url = new URL(request.url);
  const plan = (url.searchParams.get("plan") ?? "free") as "free" | "pro" | "agency";

  let activeProducts: ActiveProduct[] = [];

  try {
    const [dashResp, productsResp] = await Promise.allSettled([
      callBackendForShop(shop, `/api/shops/${shop}/dashboard?plan=${plan}`, { accessToken: session.accessToken }),
      callBackendForShop(shop, `/api/shops/${shop}/products/active`, { accessToken: session.accessToken }),
    ]);

    // Resolve active products (non-blocking — graceful degradation)
    if (productsResp.status === "fulfilled" && productsResp.value.ok) {
      try {
        activeProducts = (await productsResp.value.json()) as ActiveProduct[];
      } catch (_parseErr) { /* ignore */ }
    }

    // Dashboard failed — likely no snapshot yet. Trigger one in the background.
    if (dashResp.status !== "fulfilled" || !dashResp.value.ok) {
      callBackendForShop(shop, "/api/jobs", {
        accessToken: session.accessToken,
        method: "POST",
        body: JSON.stringify({ queue: "seo_audit" }),
      }).catch(() => {});
      const errStatus = dashResp.status === "fulfilled" ? dashResp.value.status : 0;
      return json<LoaderData>({
        shop, locale, plan,
        dashboard: null,
        activeProducts,
        error: errStatus ? `HTTP ${errStatus}` : "Network error",
      });
    }

    const dashboard = (await dashResp.value.json()) as DashboardData;

    // Auto-refresh snapshot in the background when stale — fire and forget
    if (dashboard.banners.stale_snapshot) {
      callBackendForShop(shop, "/api/jobs", {
        accessToken: session.accessToken,
        method: "POST",
        body: JSON.stringify({ queue: "seo_audit" }),
      }).catch(() => {});
    }

    // New merchant with no niche analysis → send to guided onboarding
    if (!dashboard.zone1.niche_available) {
      return redirect(localizedPath("/app/onboarding", locale));
    }

    return json<LoaderData>({ shop, locale, plan, dashboard, activeProducts, error: null });
  } catch (err) {
    return json<LoaderData>({
      shop, locale, plan,
      dashboard: null,
      activeProducts,
      error: err instanceof Error ? err.message : "Network error",
    });
  }
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
        <InlineStack gap="200" blockAlign="center">
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
        <Text as="h2" variant="headingMd">{t(locale, "dashboardZone1Title")}</Text>
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
        <InlineStack gap="200" blockAlign="center">
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

function ActiveProductsCard({
  products,
  locale,
}: {
  products: ActiveProduct[];
  locale: Locale;
}) {
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <Text as="h2" variant="headingMd">{t(locale, "dashboardActiveProductsTitle")}</Text>
          {products.length > 0 && <Badge>{String(products.length)}</Badge>}
        </InlineStack>
        {products.length === 0 ? (
          <Text as="p" tone="subdued">{t(locale, "dashboardActiveProductsEmpty")}</Text>
        ) : (
          <BlockStack gap="200">
            {products.map((product) => (
              <InlineStack key={product.id} align="space-between" blockAlign="center">
                <BlockStack gap="050">
                  <Text as="p" variant="bodyMd" fontWeight="semibold">{product.title}</Text>
                  <Text as="p" variant="bodySm" tone="subdued">/{product.handle}</Text>
                </BlockStack>
                <Button
                  url={localizedPath("/app/market-analysis", locale)}
                  variant="plain"
                  size="slim"
                >
                  {t(locale, "dashboardActiveProductsAnalyse")}
                </Button>
              </InlineStack>
            ))}
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
      <Text as="h2" variant="headingMd">{t(locale, "dashboardZone2Title")}</Text>
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
          <Text as="h2" variant="headingMd">{t(locale, "dashboardZone3Title")}</Text>
          {data.trend !== "flat" && (
            <Badge tone={trendTone}>{data.trend === "up" ? "↑" : "↓"}</Badge>
          )}
        </InlineStack>
        {data.active_optimizations_count > 0 ? (
          <>
            <InlineStack gap="200" blockAlign="center">
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
        <Text as="h2" variant="headingMd">{t(locale, "dashboardZone4Title")}</Text>
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
      <Text as="h2" variant="headingMd">{t(locale, "dashboardZone5Title")}</Text>
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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function IndexPage() {
  const { locale, plan, dashboard, activeProducts, error } = useLoaderData<typeof loader>() as LoaderData;

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
        {banners.stale_snapshot && (
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

        {/* Zone 1 — Store health */}
        <Zone1 data={zone1} locale={locale} />

        {/* Zone 2 — Active products */}
        <ActiveProductsCard products={activeProducts} locale={locale} />

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
