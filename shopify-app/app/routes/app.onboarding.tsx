import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import {
  useActionData,
  useLoaderData,
  useNavigate,
  useRevalidator,
} from "@remix-run/react";
import { useEffect, useRef, useState } from "react";
import {
  Banner,
  BlockStack,
  Button,
  InlineStack,
  Link,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { BusinessProfilePanel } from "../components/BusinessProfilePanel";
import { ProductIdentificationPanel } from "../components/ProductIdentificationPanel";
import { MarketAnalysisProgressPanel } from "../components/MarketAnalysisProgressPanel";
import { GoogleConnectionsCard } from "../components/GoogleConnectionsCard";
import type { BusinessProfile, MarketJobState } from "../lib/marketAnalysisShared";
import {
  startBusinessAnalysis as startBusinessAnalysisAction,
  pollBusinessAnalysis as pollBusinessAnalysisAction,
  saveBusinessProfile as saveBusinessProfileAction,
  saveBusinessProfileAndStartIdentification as saveBusinessProfileAndStartIdentificationAction,
  fetchLatestBusinessProfile,
} from "../lib/businessProfileActions.server";
import { OnboardingDiscoveryPanel } from "../components/OnboardingDiscoveryPanel";
import { ProductSelectionPanel } from "../components/ProductSelectionPanel";
import { OnboardingFirstWinPanel } from "../components/OnboardingFirstWinPanel";
import {
  startProductAnalysis as startProductAnalysisAction,
  pollProductIdentification as pollProductIdentificationAction,
  saveProductIdentificationAndStartAnalysis as saveProductIdentificationAndStartAnalysisAction,
  pollProductAnalysis as pollProductAnalysisAction,
} from "../lib/productIdentificationActions.server";
import type {
  GA4Property,
  GA4Status,
  GSCStatus,
  OnboardingActionData,
} from "../components/onboarding/types";

type OnboardingStep = 1 | 2 | 3 | 4 | 5 | 6;

interface LoaderData {
  locale: Locale;
  shop: string;
  gsc: GSCStatus | null;
  ga4: GA4Status | null;
  ga4Properties: GA4Property[];
  businessProfile: BusinessProfile | null;
  startStep: OnboardingStep;
}

async function fetchOk<T>(promise: Promise<Response>): Promise<T | null> {
  try {
    const resp = await promise;
    if (!resp.ok) return null;
    return (await resp.json()) as T;
  } catch {
    return null;
  }
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const be = (path: string) =>
    callBackendForShop(shop, path, { accessToken: session.accessToken });

  const [gsc, ga4, businessProfile, latestAnalysis] = await Promise.all([
    fetchOk<GSCStatus>(be(`/api/shops/${shop}/gsc/status`)),
    fetchOk<GA4Status>(be(`/api/shops/${shop}/ga4/status`)),
    fetchLatestBusinessProfile(shop, session.accessToken),
    fetchOk<unknown>(be(`/api/shops/${shop}/market-analysis/latest`)),
  ]);

  const profileValidated = businessProfile?.status === "validated";

  const url = new URL(request.url);
  const forcedStepParam = Number(url.searchParams.get("step"));
  const forcedStep =
    forcedStepParam >= 1 && forcedStepParam <= 6 ? (forcedStepParam as OnboardingStep) : null;

  // Google is optional in the reordered flow: onboarding is done once the
  // merchant validated the profile and a market analysis exists.
  if (profileValidated && latestAnalysis && !forcedStep) {
    return redirect(localizedPath("/app", locale));
  }

  // Value-first order: discovery (1) → profile validation (2) → Google (3)
  // → product selection (4) → identification + deep analysis (5) → first win (6).
  let startStep: OnboardingStep = 1;
  if (businessProfile && !profileValidated) startStep = 2;
  if (profileValidated) startStep = 3;
  if (forcedStep) startStep = forcedStep;

  // GA4 authorized but no property selected → fetch the property list so the
  // card can show a selector.
  let ga4Properties: GA4Property[] = [];
  if (ga4?.oauth_connected && !ga4?.ready) {
    const props = await fetchOk<{ properties?: GA4Property[] }>(be(`/api/shops/${shop}/ga4/properties`));
    ga4Properties = props?.properties ?? [];
  }

  return json<LoaderData>({
    locale,
    shop,
    gsc,
    ga4,
    ga4Properties,
    businessProfile,
    startStep,
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const form = await request.formData();
  const intent = String(form.get("intent") || "audit");

  const be = (path: string, init: RequestInit = {}) =>
    callBackendForShop(shop, path, { accessToken: session.accessToken, ...init });

  try {
    if (intent === "gsc_connect") {
      const resp = await be(`/api/shops/${shop}/gsc/authorize`, { method: "POST" });
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { authorization_url: string };
      return json<OnboardingActionData>({ authorizationUrl: data.authorization_url });
    }

    if (intent === "gsc_disconnect") {
      const resp = await be(`/api/shops/${shop}/gsc/disconnect`, { method: "DELETE" });
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      return json<OnboardingActionData>({ disconnected: true });
    }

    if (intent === "gsc_import") {
      const resp = await be(`/api/shops/${shop}/gsc/import`, {
        method: "POST",
        body: JSON.stringify({ days: 90 }),
      });
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { job_id: string };
      return json<OnboardingActionData>({ jobId: data.job_id });
    }

    if (intent === "ga4_connect") {
      const resp = await be(`/api/shops/${shop}/ga4/authorize`, { method: "POST" });
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { authorization_url: string };
      return json<OnboardingActionData>({ authorizationUrl: data.authorization_url });
    }

    if (intent === "ga4_disconnect") {
      const resp = await be(`/api/shops/${shop}/ga4/disconnect`, { method: "DELETE" });
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      return json<OnboardingActionData>({ disconnected: true });
    }

    if (intent === "ga4_select_property") {
      const propertyId = String(form.get("property_id") ?? "");
      const propertyName = String(form.get("property_name") ?? "");
      const resp = await be(`/api/shops/${shop}/ga4/settings`, {
        method: "POST",
        body: JSON.stringify({ property_id: propertyId, property_name: propertyName }),
      });
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      return json<OnboardingActionData>({ ga4PropertySaved: true });
    }

    if (intent === "startDiscovery") {
      // Kick the catalog crawl so the discovery analysis has a fresh snapshot.
      // Deduplicated backend-side (enqueue_unique); a failure is non-fatal —
      // the profile analysis tolerates a missing snapshot.
      const resp = await be("/api/jobs", {
        method: "POST",
        body: JSON.stringify({ queue: "seo_audit" }),
      });
      if (!resp.ok) {
        return json({ type: "startDiscovery", crawlJobId: null, error: `${resp.status}` });
      }
      const data = (await resp.json()) as { job_id: string };
      return json({ type: "startDiscovery", crawlJobId: data.job_id, error: null });
    }

    if (intent === "pollCrawlJob") {
      const crawlJobId = String(form.get("crawlJobId") ?? "");
      const resp = await be(`/api/jobs/${crawlJobId}`);
      if (!resp.ok) {
        // Treat a vanished job as done so the discovery flow moves on.
        return json({ type: "pollCrawlJob", status: "completed", error: null });
      }
      const data = (await resp.json()) as { status?: string };
      return json({ type: "pollCrawlJob", status: data.status ?? "running", error: null });
    }

    if (intent === "saveBusinessProfileOnly") {
      const profileJson = form.get("profileJson") as string;
      try {
        const profileData = JSON.parse(profileJson) as BusinessProfile;
        const result = await saveBusinessProfileAction(
          session.shop,
          session.accessToken,
          profileData,
        );
        return json({ type: "saveBusinessProfileOnly", identifyJobId: null, ...result });
      } catch (err) {
        return json({
          type: "saveBusinessProfileOnly",
          profile: null,
          identifyJobId: null,
          error: String(err),
        });
      }
    }

    if (intent === "applyFirstWin") {
      const productId = String(form.get("productId") ?? "");
      const resp = await be(
        `/api/shops/${shop}/market-analysis/proposals/${encodeURIComponent(productId)}/apply-to-shopify`,
        {
          method: "POST",
          body: JSON.stringify({ fields: ["meta_title"], confirm_live_write: true }),
        },
      );
      if (!resp.ok) {
        const txt = await resp.text();
        return json({ type: "applyFirstWin", ok: false, error: `HTTP ${resp.status}: ${txt}` });
      }
      const data = (await resp.json()) as {
        results?: Record<string, { applied?: boolean; error?: string | null }>;
      };
      const outcome = data.results?.meta_title;
      return json({
        type: "applyFirstWin",
        ok: Boolean(outcome?.applied),
        error: outcome?.applied ? null : (outcome?.error ?? "not applied"),
      });
    }

    if (intent === "startBusinessAnalysis") {
      let shopName = "";
      try {
        const shopResp = await admin.graphql(`#graphql
          query { shop { name } }
        `);
        const shopData = (await shopResp.json()) as { data?: { shop?: { name?: string } } };
        shopName = shopData.data?.shop?.name ?? "";
      } catch { /* non-fatal */ }

      const rawKeywords = form.get("focusKeywords");
      const focusKeywords: string[] = rawKeywords ? (JSON.parse(rawKeywords as string) as string[]) : [];

      const result = await startBusinessAnalysisAction(session.shop, session.accessToken, {
        shopName,
        focusKeywords,
      });
      return json({ type: "startBusinessAnalysis", ...result });
    }

    if (intent === "pollBusinessAnalysis") {
      const bizJobId = form.get("bizJobId") as string;
      const result = await pollBusinessAnalysisAction(session.shop, session.accessToken, bizJobId);
      return json({ type: "pollBusinessAnalysis", ...result });
    }

    if (intent === "saveBusinessProfileAndStartIdentification") {
      const profileJson = form.get("profileJson") as string;
      try {
        const profileData = JSON.parse(profileJson) as BusinessProfile;
        const result = await saveBusinessProfileAndStartIdentificationAction(
          session.shop,
          session.accessToken,
          profileData,
        );
        return json({ type: "saveBusinessProfileAndStartIdentification", ...result });
      } catch (err) {
        return json({
          type: "saveBusinessProfileAndStartIdentification",
          profile: null,
          identifyJobId: null,
          error: String(err),
        });
      }
    }

    if (intent === "loadManagedProducts") {
      const resp = await be(`/api/shops/${shop}/managed-products`);
      if (!resp.ok) {
        return json({ type: "loadManagedProducts", managed: null, error: `${resp.status}` });
      }
      const managed = await resp.json();
      return json({ type: "loadManagedProducts", managed, error: null });
    }

    if (intent === "saveManagedProducts") {
      const productIds = JSON.parse(String(form.get("productIds") ?? "[]")) as string[];
      const resp = await be(`/api/shops/${shop}/managed-products`, {
        method: "PUT",
        body: JSON.stringify({ product_ids: productIds }),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        return json({ type: "saveManagedProducts", saved: false, error: `HTTP ${resp.status}: ${detail}` });
      }
      return json({ type: "saveManagedProducts", saved: true, error: null });
    }

    if (intent === "startProductAnalysis") {
      const result = await startProductAnalysisAction(session.shop, session.accessToken);
      return json({ type: "startProductAnalysis", ...result });
    }

    if (intent === "pollProductIdentification") {
      const identifyJobId = form.get("identifyJobId") as string;
      const result = await pollProductIdentificationAction(session.shop, session.accessToken, identifyJobId);
      return json({ type: "pollProductIdentification", ...result });
    }

    if (intent === "saveProductIdentificationAndStartAnalysis") {
      const identificationsRaw = form.get("identifications") as string;
      try {
        const identifications = JSON.parse(identificationsRaw) as Record<string, string>;
        const result = await saveProductIdentificationAndStartAnalysisAction(
          session.shop,
          session.accessToken,
          identifications,
        );
        return json({ type: "saveProductIdentificationAndStartAnalysis", ...result });
      } catch (err) {
        return json({
          type: "saveProductIdentificationAndStartAnalysis",
          productJobId: null,
          error: String(err),
        });
      }
    }

    if (intent === "pollProductAnalysis") {
      const productJobId = form.get("productJobId") as string;
      const result = await pollProductAnalysisAction(session.shop, session.accessToken, productJobId);
      return json({ type: "pollProductAnalysis", ...result });
    }

    // Default intent: launch a full audit.
    const resp = await be("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ queue: "seo_audit" }),
    });
    if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
    const data = (await resp.json()) as { job_id: string };
    return json<OnboardingActionData>({ jobId: data.job_id });
  } catch {
    return json<OnboardingActionData>({ error: t(locale, "backendOffline") });
  }
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Onboarding() {
  const { locale, gsc, ga4, ga4Properties, businessProfile, startStep } =
    useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const revalidator = useRevalidator();
  const navigate = useNavigate();
  const openedUrlRef = useRef<string | null>(null);

  const legacyActionData: OnboardingActionData | undefined =
    actionData && !("type" in actionData) ? actionData : undefined;

  const [step, setStep] = useState<OnboardingStep>(startStep);
  const [discoveredProfile, setDiscoveredProfile] = useState<BusinessProfile | null>(null);
  const [productJobId, setProductJobId] = useState<string | null>(null);
  const [completedJob, setCompletedJob] = useState<MarketJobState | null>(null);

  // Auto-open Google's consent screen in a centered popup when the action returns
  // an authorization URL. The OAuth callback posts a "leonie-google-oauth" message
  // back to this window, so we revalidate status as soon as it succeeds.
  useEffect(() => {
    const url = legacyActionData?.authorizationUrl;
    if (!url || openedUrlRef.current === url) return;
    if (typeof window === "undefined") return;
    openedUrlRef.current = url;
    const w = 520;
    const h = 720;
    const left = window.screenX + Math.max(0, (window.outerWidth - w) / 2);
    const top = window.screenY + Math.max(0, (window.outerHeight - h) / 2);
    window.open(
      url,
      "leonie-google-oauth",
      `width=${w},height=${h},left=${left},top=${top},menubar=no,toolbar=no`,
    );
  }, [legacyActionData?.authorizationUrl]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onMessage = (event: MessageEvent) => {
      const data = event.data as { source?: string; ok?: boolean } | null;
      if ((data?.source === "leonie-google-oauth" || data?.source === "leonie-google-oauth-ga4") && data.ok) {
        revalidator.revalidate();
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [revalidator]);

  // Refresh status after a disconnect so the UI flips back to "Connect".
  useEffect(() => {
    if (legacyActionData?.disconnected) revalidator.revalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [legacyActionData?.disconnected]);

  // Auto-advance from the Google step only on the connect transition (the OAuth
  // popup just completed), NOT when arriving with Search Console already connected
  // — otherwise the dashboard "Connect GA4" link (which forces ?step=3 to manage
  // connections) would immediately skip past the Google step. Also hold the step
  // while GA4 is half-connected (authorized, property not chosen): advancing then
  // would silently leave GA4 incomplete behind the merchant.
  const ga4Pending = Boolean(ga4?.oauth_connected) && !ga4?.ready;
  const prevGscConnected = useRef(gsc?.connected ?? false);
  useEffect(() => {
    const now = gsc?.connected ?? false;
    const justConnected = now && !prevGscConnected.current;
    prevGscConnected.current = now;
    if (step === 3 && justConnected && !ga4Pending) setStep(4);
  }, [step, gsc?.connected, ga4Pending]);

  const handleDiscoveryConfirmed = (profile: BusinessProfile) => {
    setDiscoveredProfile(profile);
    setStep(2);
  };

  const handleProfileValidated = (_profile: BusinessProfile, _identifyJobId: string | null) => {
    setStep(3);
  };

  const handleProductsSaved = (jobId: string) => {
    setProductJobId(jobId);
  };

  const handleAnalysisComplete = (job: MarketJobState) => {
    setCompletedJob(job);
    setStep(6);
  };

  const handleFinish = () => {
    navigate(localizedPath("/app", locale));
  };

  return (
    <Page
      title={t(locale, "onboarding")}
    >
      <BlockStack gap="400">
        {legacyActionData?.authorizationUrl && (
          <Banner
            tone="info"
            title={
              locale === "fr"
                ? "Autorisation Google requise"
                : "Google authorization required"
            }
          >
            <Text as="p">
              {locale === "fr"
                ? "Une fenêtre Google s'est ouverte. Termine le consentement, puis cette page se mettra à jour automatiquement."
                : "A Google window opened. Complete the consent and this page will refresh automatically."}
            </Text>
            <Text as="p" variant="bodySm" tone="subdued">
              {locale === "fr" ? "Si la fenêtre est bloquée :" : "If the popup is blocked:"}{" "}
              <Link
                url={legacyActionData.authorizationUrl}
                target="_blank"
                accessibilityLabel={
                  locale === "fr"
                    ? "Ouvrir l'autorisation Google dans un nouvel onglet"
                    : "Open Google authorization in a new tab"
                }
              >
                {locale === "fr" ? "ouvrir l'autorisation Google →" : "open Google authorization →"}
              </Link>
            </Text>
          </Banner>
        )}

        {step === 1 && (
          <OnboardingDiscoveryPanel
            locale={locale}
            existingProfile={businessProfile}
            onConfirm={handleDiscoveryConfirmed}
          />
        )}

        {step === 2 && (
          <BusinessProfilePanel
            locale={locale}
            initialProfile={businessProfile}
            initialDraft={discoveredProfile}
            saveOnly
            onValidated={handleProfileValidated}
          />
        )}

        {step === 3 && (
          <GoogleConnectionsCard
            locale={locale}
            gsc={gsc}
            ga4={ga4}
            ga4Properties={ga4Properties}
            legacyActionData={legacyActionData}
            title={t(locale, "onboardingStepGoogleTitle")}
            description={t(locale, "onboardingStepGoogleBody")}
            onContinue={() => setStep(4)}
            footer={
              <BlockStack gap="200">
                {/* The estimated-vs-measured pitch only makes sense BEFORE connecting. */}
                {!gsc?.connected && (
                  <>
                    <Text as="p" variant="bodySm" fontWeight="semibold">
                      {t(locale, "onboardingGoogleExampleTitle")}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      {t(locale, "onboardingGoogleExampleEstimated")}
                    </Text>
                    <Text as="p" variant="bodySm">
                      {t(locale, "onboardingGoogleExampleMeasured")}
                    </Text>
                  </>
                )}
                <InlineStack align="end">
                  <Button variant="tertiary" onClick={() => setStep(4)}>
                    {t(locale, "onboardingGoogleSkip")}
                  </Button>
                </InlineStack>
              </BlockStack>
            }
          />
        )}

        {step === 4 && (
          <ProductSelectionPanel locale={locale} onSaved={() => setStep(5)} />
        )}

        {step === 5 && !productJobId && (
          <ProductIdentificationPanel
            locale={locale}
            initialJobId={null}
            onSaved={handleProductsSaved}
          />
        )}

        {step === 5 && productJobId && (
          <MarketAnalysisProgressPanel
            locale={locale}
            jobId={productJobId}
            onComplete={handleAnalysisComplete}
          />
        )}

        {step === 6 && completedJob && (
          <OnboardingFirstWinPanel locale={locale} job={completedJob} onDone={handleFinish} />
        )}
        {step === 6 && !completedJob && (
          // Forced ?step=5 without a fresh analysis in memory — nothing to apply.
          <Banner tone="info">
            <Text as="p">{t(locale, "marketAnalysisEmpty")}</Text>
          </Banner>
        )}
      </BlockStack>
    </Page>
  );
}
