import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useFetcher, useLoaderData, useSubmit } from "@remix-run/react";
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
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import { PlanBadge } from "../components/PlanBadge";
import { CheckCircleIcon, LockIcon } from "@shopify/polaris-icons";
import { useState, useEffect } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { pickLang, t, type Locale } from "../lib/i18n";
import { resolveLocale } from "../lib/i18n.server";
import { showToast } from "../lib/toast";
import { UsageMeter } from "../components/UsageMeter";

interface PlanQuotas {
  products: number;
  analysis: number;
  product_analysis: number;
  blog: number;
  auto_analysis: boolean;
}

interface Plan {
  id: string;
  display_name: string;
  price: number;
  currency: string;
  features: string[];
  quotas: PlanQuotas;
  current: boolean;
}

interface LoaderData {
  shop: string;
  locale: Locale;
  plans: Plan[];
  currentPlan: string;
  override: boolean;
  usage: { analysis: number; blog: number } | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = await resolveLocale(request, session.shop, session.accessToken);

  let plans: Plan[] = [];
  let currentPlan = "free";
  let override = false;
  let usage: LoaderData["usage"] = null;
  try {
    const [plansResp, statusResp] = await Promise.all([
      callBackendForShop(shop, `/api/shops/${shop}/billing/plans`, {
        accessToken: session.accessToken,
      }),
      callBackendForShop(shop, `/api/shops/${shop}/billing/status`, {
        accessToken: session.accessToken,
      }),
    ]);
    if (plansResp.ok) {
      const data = (await plansResp.json()) as { plans: Plan[]; current_plan: string };
      plans = data.plans;
      currentPlan = data.current_plan ?? "free";
    }
    if (statusResp.ok) {
      const status = (await statusResp.json()) as {
        override?: boolean;
        usage?: { analysis: number; blog: number };
      };
      override = Boolean(status.override);
      usage = status.usage ?? null;
    }
  } catch {
    // Python backend unavailable
  }

  return json<LoaderData>({ shop, locale, plans, currentPlan, override, usage });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;

  const formData = await request.formData();
  const intent = formData.get("intent") as string;

  if (intent === "redeem") {
    const code = String(formData.get("code") ?? "").trim();
    // GEO- codes are single-use quota reset codes; others are partner plan codes.
    if (/^GEO(PRO|BIG)?-/i.test(code)) {
      const resp = await callBackendForShop(shop, `/api/shops/${shop}/quota-code/redeem`, {
        method: "POST",
        accessToken: session.accessToken,
        body: JSON.stringify({ code }),
      });
      if (resp.ok) return json({ redeemed: "quota", redeemError: false });
      return json({ redeemed: null, redeemError: true });
    }
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/billing/redeem-code`, {
      method: "POST",
      accessToken: session.accessToken,
      body: JSON.stringify({ code }),
    });
    if (resp.ok) {
      const data = (await resp.json()) as { plan: string };
      return json({ redeemed: data.plan, redeemError: false });
    }
    return json({ redeemed: null, redeemError: true });
  }

  if (intent === "cancel") {
    await callBackendForShop(shop, `/api/shops/${shop}/billing/cancel`, {
      method: "POST",
      accessToken: session.accessToken,
    });
    return redirect("/app/billing");
  }

  const planId = formData.get("plan") as string;
  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/billing/subscribe`, {
      method: "POST",
      accessToken: session.accessToken,
      body: JSON.stringify({ plan: planId }),
    });
    const data = (await resp.json()) as { confirmation_url: string };
    if (data.confirmation_url) {
      return redirect(data.confirmation_url);
    }
  } catch {
    // error handled by redirect back
  }
  return redirect("/app/billing");
};

function planCopy(plan: Plan, locale: Locale) {
  const q = plan.quotas;
  const per28 = t(locale, "billPer28");
  const countLine = (n: number, singularKey: string, pluralKey: string) =>
    `${t(locale, n > 1 ? pluralKey : singularKey).replace("{n}", String(n))} ${per28}`;
  const lines: { text: string; included: boolean }[] = [
    {
      text: t(locale, "billProductsOptimized").replace("{n}", String(q.products)),
      included: true,
    },
    {
      text: countLine(q.analysis, "billAnalysisSingular", "billAnalysesPlural"),
      included: true,
    },
    {
      text: countLine(q.product_analysis, "billProductAnalysisSingular", "billProductAnalysesPlural"),
      included: true,
    },
    {
      text: countLine(q.blog, "billBlogArticleSingular", "billBlogArticlesPlural"),
      included: true,
    },
    {
      text: t(locale, "billAutoAnalysis"),
      included: q.auto_analysis,
    },
    {
      text: t(locale, "billThemeExtension"),
      included: plan.id !== "free",
    },
    {
      text: t(locale, "billLlmsTxt"),
      included: true,
    },
    {
      text: t(locale, "billTrendsWatch"),
      included: plan.id === "agency",
    },
  ];
  return lines;
}

const PLAN_LABELS: Record<string, { fr: string; en: string; taglineFr: string; taglineEn: string }> = {
  free: {
    fr: "Découverte",
    en: "Starter",
    taglineFr: "Pour tester la puissance du GEO",
    taglineEn: "Try the power of GEO",
  },
  pro: {
    fr: "Pro",
    en: "Pro",
    taglineFr: "Surfez sur les tendances et gardez une longueur d'avance sur vos concurrents",
    taglineEn: "Ride the trends and stay one step ahead of your competitors",
  },
  agency: {
    fr: "Grande boutique",
    en: "Large store",
    taglineFr: "Toute la puissance, à l'échelle de votre catalogue",
    taglineEn: "Full power, at the scale of your catalog",
  },
};

export default function Billing() {
  const { locale, plans, currentPlan, override, usage } = useLoaderData<typeof loader>();
  const submit = useSubmit();
  const redeemFetcher = useFetcher<{ redeemed: string | null; redeemError: boolean }>();
  const [codeOpen, setCodeOpen] = useState(false);
  const [code, setCode] = useState("");

  const redeemed = redeemFetcher.data?.redeemed;
  useEffect(() => {
    if (redeemFetcher.data?.redeemed) showToast(t(locale, "toastCodeRedeemed"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [redeemFetcher.data]);
  const redeemError = redeemFetcher.data?.redeemError;

  const formatPrice = (plan: Plan) => {
    if (plan.price === 0) return t(locale, "billFreePrice");
    const amount = plan.price.toLocaleString(
      { fr: "fr-FR", en: "en-US", de: "de-DE", es: "es-ES" }[locale], {
      minimumFractionDigits: 2,
    });
    return plan.currency === "EUR" ? `${amount} €` : `$${amount}`;
  };

  return (
    <Page
      title={t(locale, "navPlans")}
      titleMetadata={<PlanBadge />}
      subtitle={t(locale, "billSubtitle")}
    >
      <BlockStack gap="500">
        {redeemed && (
          <Banner tone="success" title={t(locale, "billPartnerEnabled")}>
            <Text as="p">
              {t(locale, "billPartnerRedeemed").replace(
                "{plan}",
                PLAN_LABELS[redeemed]
                  ? pickLang(locale, PLAN_LABELS[redeemed].fr, PLAN_LABELS[redeemed].en)
                  : redeemed,
              )}
            </Text>
          </Banner>
        )}
        {override && !redeemed && (
          <Banner tone="success" title={t(locale, "billPartnerActive")} />
        )}

        {usage && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingSm">
                {t(locale, "billUsageTitle")}
              </Text>
              <InlineGrid columns={{ xs: 1, sm: 2 }} gap="300">
                <UsageMeter
                  label={t(locale, "billAnalysesLabel")}
                  used={usage.analysis}
                  quota={Number(plans.find((p) => p.current)?.quotas.analysis ?? 1)}
                  locale={locale}
                  showUpgrade={currentPlan !== "agency"}
                />
                <UsageMeter
                  label={t(locale, "billBlogLabel")}
                  used={usage.blog}
                  quota={Number(plans.find((p) => p.current)?.quotas.blog ?? 3)}
                  locale={locale}
                  showUpgrade={currentPlan !== "agency"}
                />
              </InlineGrid>
            </BlockStack>
          </Card>
        )}

        <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
          {plans.map((plan) => {
            const labels = PLAN_LABELS[plan.id];
            const isPro = plan.id === "pro";
            const isPaid = plan.id !== "free";
            return (
              <div
                key={plan.id}
                style={{
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  background: "var(--p-color-bg-surface)",
                  borderRadius: "var(--p-border-radius-300)",
                  boxShadow: "var(--p-shadow-100)",
                  padding: "var(--p-space-400)",
                  ...(isPro
                    ? { outline: "2px solid var(--p-color-border-emphasis)" }
                    : undefined),
                }}
              >
                  <BlockStack gap="300">
                    <InlineStack align="space-between" blockAlign="center">
                      <Text as="h2" variant="headingMd">
                        {labels ? pickLang(locale, labels.fr, labels.en) : plan.display_name}
                      </Text>
                      {isPro && (
                        <Badge tone="info">{t(locale, "billMostPopular")}</Badge>
                      )}
                      {plan.current && (
                        <Badge tone="success">{t(locale, "billCurrentPlan")}</Badge>
                      )}
                    </InlineStack>
                    <div style={{ minHeight: "2.5rem" }}>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {labels ? pickLang(locale, labels.taglineFr, labels.taglineEn) : ""}
                      </Text>
                    </div>
                    <InlineStack gap="100" blockAlign="end">
                      <Text as="p" variant="heading2xl" fontWeight="bold">
                        {formatPrice(plan)}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {t(locale, "billPerMonth")}
                      </Text>
                    </InlineStack>
                    {isPaid ? (
                      <Badge tone="success">
                        {t(locale, "billFreeTrial")}
                      </Badge>
                    ) : (
                      <div style={{ visibility: "hidden" }} aria-hidden="true">
                        <Badge tone="success">
                          {t(locale, "billFreeTrial")}
                        </Badge>
                      </div>
                    )}
                    <BlockStack gap="150">
                      {planCopy(plan, locale).map((line, i) => (
                        <InlineStack key={i} gap="150" blockAlign="center" wrap={false}>
                          <span style={{ opacity: line.included ? 1 : 0.35, display: "inline-flex" }}>
                            <Icon
                              source={line.included ? CheckCircleIcon : LockIcon}
                              tone={line.included ? "success" : "subdued"}
                            />
                          </span>
                          <Text
                            as="p"
                            variant="bodySm"
                            tone={line.included ? undefined : "subdued"}
                          >
                            {line.text}
                          </Text>
                        </InlineStack>
                      ))}
                    </BlockStack>
                  </BlockStack>
                  <div style={{ flexGrow: 1, minHeight: "var(--p-space-300)" }} />
                  {!plan.current && isPaid && (
                    <Button
                      variant={isPro ? "primary" : "secondary"}
                      fullWidth
                      onClick={() => submit({ plan: plan.id }, { method: "post" })}
                    >
                      {t(locale, "billStartTrial")}
                    </Button>
                  )}
                  {!plan.current && !isPaid && (
                    <Text as="p" variant="bodySm" tone="subdued" alignment="center">
                      {t(locale, "billIncludedInstall")}
                    </Text>
                  )}
                  {plan.current && isPaid && (
                    <Button
                      variant="plain"
                      tone="critical"
                      onClick={() => submit({ intent: "cancel" }, { method: "post" })}
                    >
                      {t(locale, "billCancelSub")}
                    </Button>
                  )}
              </div>
            );
          })}
        </InlineGrid>

        {plans.length > 0 && (
          <Box background="bg-surface-secondary" padding="300" borderRadius="200">
            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              {t(locale, "billSecureNote")}
            </Text>
          </Box>
        )}

        {plans.length === 0 && (
          <Card>
            <Text as="p" tone="subdued">
              {t(locale, "billLoadError")}
            </Text>
          </Card>
        )}

        <Card>
          <BlockStack gap="200">
            <Button variant="plain" onClick={() => setCodeOpen((v) => !v)} disclosure={codeOpen ? "up" : "down"}>
              {t(locale, "billPartnerCodeToggle")}
            </Button>
            <Collapsible id="partner-code" open={codeOpen}>
              <InlineStack gap="200" blockAlign="end" wrap={false}>
                <div style={{ flexGrow: 1 }}>
                  <TextField
                    label={t(locale, "billPartnerCodeLabel")}
                    labelHidden
                    value={code}
                    onChange={setCode}
                    autoComplete="off"
                    placeholder={t(locale, "billCodePlaceholder")}
                    error={redeemError ? t(locale, "billCodeInvalid") : undefined}
                  />
                </div>
                <Button
                  onClick={() =>
                    redeemFetcher.submit({ intent: "redeem", code }, { method: "post" })
                  }
                  loading={redeemFetcher.state !== "idle"}
                  disabled={!code.trim()}
                >
                  {t(locale, "billRedeem")}
                </Button>
              </InlineStack>
            </Collapsible>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
