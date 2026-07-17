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
import { useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { type Locale } from "../lib/i18n";
import { resolveLocale } from "../lib/i18n.server";
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
    if (code.toUpperCase().startsWith("GEO-")) {
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

function planCopy(plan: Plan, fr: boolean) {
  const q = plan.quotas;
  const per28 = fr ? "tous les 28 jours" : "every 28 days";
  const lines: { text: string; included: boolean }[] = [
    {
      text: fr ? `${q.products} produits optimisés` : `${q.products} optimized products`,
      included: true,
    },
    {
      text: fr
        ? `${q.analysis} analyse${q.analysis > 1 ? "s" : ""} ${per28}`
        : `${q.analysis} analys${q.analysis > 1 ? "es" : "is"} ${per28}`,
      included: true,
    },
    {
      text: fr
        ? `${q.product_analysis} analyse${q.product_analysis > 1 ? "s" : ""} par produit ${per28}`
        : `${q.product_analysis} analys${q.product_analysis > 1 ? "es" : "is"} per product ${per28}`,
      included: true,
    },
    {
      text: fr ? `${q.blog} articles de blog ${per28}` : `${q.blog} blog articles ${per28}`,
      included: true,
    },
    {
      text: fr ? "Analyse automatique (agent quotidien)" : "Auto-analysis (daily agent)",
      included: q.auto_analysis,
    },
    {
      text: fr
        ? "Extension de thème (FAQ + données structurées)"
        : "Theme extension (FAQ + structured data)",
      included: plan.id !== "free",
    },
    {
      text: fr ? "llms.txt + fichiers IA" : "llms.txt + AI files",
      included: true,
    },
    {
      text: fr
        ? "Tendances temps réel + veille concurrents (sourcées)"
        : "Real-time trends + competitor watch (sourced)",
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
  const fr = locale === "fr";
  const submit = useSubmit();
  const redeemFetcher = useFetcher<{ redeemed: string | null; redeemError: boolean }>();
  const [codeOpen, setCodeOpen] = useState(false);
  const [code, setCode] = useState("");

  const redeemed = redeemFetcher.data?.redeemed;
  const redeemError = redeemFetcher.data?.redeemError;

  const formatPrice = (plan: Plan) => {
    if (plan.price === 0) return fr ? "0 €" : "€0";
    const amount = plan.price.toLocaleString(fr ? "fr-FR" : "en-US", {
      minimumFractionDigits: 2,
    });
    return plan.currency === "EUR" ? `${amount} €` : `$${amount}`;
  };

  return (
    <Page
      title={fr ? "Forfaits" : "Plans"}
      titleMetadata={<PlanBadge />}
      subtitle={
        fr
          ? "Plus de produits optimisés, plus de trafic. Changez ou annulez à tout moment."
          : "More optimized products, more traffic. Change or cancel anytime."
      }
    >
      <BlockStack gap="500">
        {redeemed && (
          <Banner tone="success" title={fr ? "Accès partenaire activé" : "Partner access enabled"}>
            <Text as="p">
              {fr
                ? `Votre boutique bénéficie maintenant du plan ${PLAN_LABELS[redeemed]?.fr ?? redeemed} — offert.`
                : `Your store now has the ${PLAN_LABELS[redeemed]?.en ?? redeemed} plan — free of charge.`}
            </Text>
          </Banner>
        )}
        {override && !redeemed && (
          <Banner tone="success" title={fr ? "Accès partenaire actif" : "Partner access active"} />
        )}

        {usage && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingSm">
                {fr ? "Votre consommation ce cycle" : "Your usage this cycle"}
              </Text>
              <InlineGrid columns={{ xs: 1, sm: 2 }} gap="300">
                <UsageMeter
                  label={fr ? "Analyses" : "Analyses"}
                  used={usage.analysis}
                  quota={Number(plans.find((p) => p.current)?.quotas.analysis ?? 1)}
                  locale={locale}
                  showUpgrade={currentPlan !== "agency"}
                />
                <UsageMeter
                  label={fr ? "Articles de blog" : "Blog articles"}
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
                        {labels ? (fr ? labels.fr : labels.en) : plan.display_name}
                      </Text>
                      {isPro && (
                        <Badge tone="info">{fr ? "Le plus populaire" : "Most popular"}</Badge>
                      )}
                      {plan.current && (
                        <Badge tone="success">{fr ? "Plan actuel" : "Current plan"}</Badge>
                      )}
                    </InlineStack>
                    <div style={{ minHeight: "2.5rem" }}>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {labels ? (fr ? labels.taglineFr : labels.taglineEn) : ""}
                      </Text>
                    </div>
                    <InlineStack gap="100" blockAlign="end">
                      <Text as="p" variant="heading2xl" fontWeight="bold">
                        {formatPrice(plan)}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {fr ? "/ mois" : "/ month"}
                      </Text>
                    </InlineStack>
                    {isPaid ? (
                      <Badge tone="success">
                        {fr ? "7 jours d'essai gratuit" : "7-day free trial"}
                      </Badge>
                    ) : (
                      <div style={{ visibility: "hidden" }} aria-hidden="true">
                        <Badge tone="success">
                          {fr ? "7 jours d'essai gratuit" : "7-day free trial"}
                        </Badge>
                      </div>
                    )}
                    <BlockStack gap="150">
                      {planCopy(plan, fr).map((line, i) => (
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
                      {fr ? "Essayer 7 jours gratuitement" : "Start 7-day free trial"}
                    </Button>
                  )}
                  {!plan.current && !isPaid && (
                    <Text as="p" variant="bodySm" tone="subdued" alignment="center">
                      {fr ? "Inclus avec l'installation" : "Included with install"}
                    </Text>
                  )}
                  {plan.current && isPaid && (
                    <Button
                      variant="plain"
                      tone="critical"
                      onClick={() => submit({ intent: "cancel" }, { method: "post" })}
                    >
                      {fr ? "Annuler l'abonnement" : "Cancel subscription"}
                    </Button>
                  )}
              </div>
            );
          })}
        </InlineGrid>

        {plans.length > 0 && (
          <Box background="bg-surface-secondary" padding="300" borderRadius="200">
            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              {fr
                ? "Facturation sécurisée gérée par Shopify · Aucun paiement pendant l'essai · Annulation en 1 clic"
                : "Secure billing handled by Shopify · No charge during the trial · Cancel in 1 click"}
            </Text>
          </Box>
        )}

        {plans.length === 0 && (
          <Card>
            <Text as="p" tone="subdued">
              {fr
                ? "Impossible de charger les plans. Réessayez dans un instant."
                : "Could not load plans. Please try again shortly."}
            </Text>
          </Card>
        )}

        <Card>
          <BlockStack gap="200">
            <Button variant="plain" onClick={() => setCodeOpen((v) => !v)} disclosure={codeOpen ? "up" : "down"}>
              {fr ? "J'ai un code partenaire" : "I have a partner code"}
            </Button>
            <Collapsible id="partner-code" open={codeOpen}>
              <InlineStack gap="200" blockAlign="end" wrap={false}>
                <div style={{ flexGrow: 1 }}>
                  <TextField
                    label={fr ? "Code partenaire" : "Partner code"}
                    labelHidden
                    value={code}
                    onChange={setCode}
                    autoComplete="off"
                    placeholder={fr ? "Entrez votre code" : "Enter your code"}
                    error={redeemError ? (fr ? "Code invalide" : "Invalid code") : undefined}
                  />
                </div>
                <Button
                  onClick={() =>
                    redeemFetcher.submit({ intent: "redeem", code }, { method: "post" })
                  }
                  loading={redeemFetcher.state !== "idle"}
                  disabled={!code.trim()}
                >
                  {fr ? "Activer" : "Redeem"}
                </Button>
              </InlineStack>
            </Collapsible>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
