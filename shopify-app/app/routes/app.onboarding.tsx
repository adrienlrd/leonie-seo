import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import {
  useActionData,
  useLoaderData,
  useNavigate,
  useRevalidator,
  useSubmit,
  useNavigation,
} from "@remix-run/react";
import { useEffect, useRef, useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Link,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import {
  callBackend,
  callBackendForShop,
  callBackendMultipartForShop,
} from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { AuditLauncherCard } from "../components/onboarding/AuditLauncherCard";
import { CrawlCard } from "../components/onboarding/CrawlCard";
import { GoogleSearchConsoleCard } from "../components/onboarding/GoogleSearchConsoleCard";
import { InstallationChecklistCard } from "../components/onboarding/InstallationChecklistCard";
import { PageSpeedCard } from "../components/onboarding/PageSpeedCard";
import { BusinessProfilePanel } from "../components/BusinessProfilePanel";
import { ProductIdentificationPanel } from "../components/ProductIdentificationPanel";
import { MarketAnalysisProgressPanel } from "../components/MarketAnalysisProgressPanel";
import { SectionTitle, type BusinessProfile, type MarketJobState } from "../lib/marketAnalysisShared";
import {
  startBusinessAnalysis as startBusinessAnalysisAction,
  pollBusinessAnalysis as pollBusinessAnalysisAction,
  saveBusinessProfileAndStartIdentification as saveBusinessProfileAndStartIdentificationAction,
  fetchLatestBusinessProfile,
} from "../lib/businessProfileActions.server";
import {
  startProductAnalysis as startProductAnalysisAction,
  pollProductIdentification as pollProductIdentificationAction,
  saveProductIdentificationAndStartAnalysis as saveProductIdentificationAndStartAnalysisAction,
  pollProductAnalysis as pollProductAnalysisAction,
} from "../lib/productIdentificationActions.server";
import { GlobeIcon } from "@shopify/polaris-icons";
import type {
  CrawlStatus,
  GA4Status,
  GSCStatus,
  Health,
  OnboardingActionData,
  PageSpeedStatus,
  ShopStatus,
} from "../components/onboarding/types";

interface LoaderData {
  locale: Locale;
  shop: string;
  health: Health | null;
  status: ShopStatus | null;
  gsc: GSCStatus | null;
  ga4: GA4Status | null;
  pagespeed: PageSpeedStatus | null;
  crawl: CrawlStatus | null;
  recentJobs: number;
  businessProfile: BusinessProfile | null;
  startStep: 1 | 2 | 3 | 4;
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

  const [health, status, jobs, gsc, ga4, pagespeed, crawl, businessProfile, latestAnalysis] =
    await Promise.all([
      fetchOk<Health>(callBackend("/health")),
      fetchOk<ShopStatus>(be(`/api/shops/${shop}/status`)),
      fetchOk<{ count: number }>(be(`/api/shops/${shop}/jobs?limit=10`)),
      fetchOk<GSCStatus>(be(`/api/shops/${shop}/gsc/status`)),
      fetchOk<GA4Status>(be(`/api/shops/${shop}/ga4/status`)),
      fetchOk<PageSpeedStatus>(be(`/api/shops/${shop}/pagespeed/status`)),
      fetchOk<CrawlStatus>(be(`/api/shops/${shop}/crawl/status`)),
      fetchLatestBusinessProfile(shop, session.accessToken),
      fetchOk<unknown>(be(`/api/shops/${shop}/market-analysis/latest`)),
    ]);

  const gscConnected = Boolean(gsc?.connected);
  const profileValidated = businessProfile?.status === "validated";

  if (gscConnected && profileValidated && latestAnalysis) {
    return redirect(localizedPath("/app", locale));
  }

  let startStep: 1 | 2 | 3 | 4 = 1;
  if (gscConnected) startStep = 2;
  if (gscConnected && profileValidated) startStep = 3;

  return json<LoaderData>({
    locale,
    shop,
    health,
    status,
    gsc,
    ga4,
    pagespeed,
    crawl,
    recentJobs: jobs?.count ?? 0,
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

    if (intent === "pagespeed_import") {
      const resp = await be(`/api/shops/${shop}/pagespeed/import`, {
        method: "POST",
        body: JSON.stringify({ max_urls: 3 }),
      });
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { job_id: string };
      return json<OnboardingActionData>({ jobId: data.job_id });
    }

    if (intent === "pagespeed_configure") {
      const apiKey = String(form.get("pagespeed_api_key") || "").trim();
      if (!apiKey) return json<OnboardingActionData>({ error: "Clé API manquante." });
      const resp = await be(`/api/shops/${shop}/pagespeed/configure`, {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey }),
      });
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      return json<OnboardingActionData>({ jobId: "Clé PageSpeed enregistrée." });
    }

    if (intent === "crawl_upload") {
      const overviewFile = form.get("overview");
      if (!overviewFile || !(overviewFile instanceof File) || overviewFile.size === 0) {
        return json<OnboardingActionData>({ error: "Fichier overview CSV manquant." });
      }
      const backendForm = new FormData();
      backendForm.append("overview", overviewFile, overviewFile.name);
      const redirectsFile = form.get("redirects");
      if (redirectsFile instanceof File && redirectsFile.size > 0) {
        backendForm.append("redirects", redirectsFile, redirectsFile.name);
      }
      const resp = await callBackendMultipartForShop(
        shop,
        `/api/shops/${shop}/crawl/upload`,
        backendForm,
        session.accessToken,
      );
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { url_count: number; issue_count: number };
      return json<OnboardingActionData>({
        jobId: `Crawl: ${data.url_count} URLs · ${data.issue_count} issues`,
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

function ConnectGoogleStep({
  locale,
  gsc,
  ga4,
  legacyActionData,
  onContinue,
}: {
  locale: Locale;
  gsc: GSCStatus | null;
  ga4: GA4Status | null;
  legacyActionData: OnboardingActionData | undefined;
  onContinue: () => void;
}) {
  const submit = useSubmit();
  const navigation = useNavigation();
  const submittingAction = String(navigation.formData?.get("intent") || "");
  const gscConnected = Boolean(gsc?.connected);
  const ga4Ready = Boolean(ga4?.ready);
  const ga4OauthPending = Boolean(ga4?.oauth_connected) && !ga4Ready;

  return (
    <Card>
      <BlockStack gap="300">
        <SectionTitle source={GlobeIcon}>{t(locale, "onboardingStepGoogleTitle")}</SectionTitle>
        <Text as="p" tone="subdued">
          {t(locale, "onboardingStepGoogleBody")}
        </Text>

        <InlineStack gap="300" wrap blockAlign="center">
          {gscConnected ? (
            <Badge tone="success">{t(locale, "onboardingGSCConnected")}</Badge>
          ) : (
            <Button
              variant="primary"
              disabled={!gsc?.configured}
              loading={navigation.state !== "idle" && submittingAction === "gsc_connect"}
              onClick={() => submit({ intent: "gsc_connect" }, { method: "post" })}
            >
              {t(locale, "onboardingConnectGSC")}
            </Button>
          )}

          {ga4Ready ? (
            <Badge tone="success">{t(locale, "onboardingGA4Connected")}</Badge>
          ) : ga4OauthPending ? (
            <Badge tone="info">{t(locale, "onboardingGA4PropertyPending")}</Badge>
          ) : (
            <Button
              loading={navigation.state !== "idle" && submittingAction === "ga4_connect"}
              onClick={() => submit({ intent: "ga4_connect" }, { method: "post" })}
            >
              {t(locale, "onboardingConnectGA4")}
            </Button>
          )}
        </InlineStack>

        {legacyActionData?.error && (
          <Banner tone="critical">
            <Text as="p">{legacyActionData.error}</Text>
          </Banner>
        )}

        {gscConnected && (
          <InlineStack align="end">
            <Button variant="primary" onClick={onContinue}>
              {t(locale, "onboardingGoogleContinue")}
            </Button>
          </InlineStack>
        )}
      </BlockStack>
    </Card>
  );
}

export default function Onboarding() {
  const { locale, shop, health, status, gsc, ga4, pagespeed, crawl, recentJobs, businessProfile, startStep } =
    useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const revalidator = useRevalidator();
  const navigate = useNavigate();
  const openedUrlRef = useRef<string | null>(null);

  const legacyActionData: OnboardingActionData | undefined =
    actionData && !("type" in actionData) ? actionData : undefined;

  const [step, setStep] = useState<1 | 2 | 3 | 4>(startStep);
  const [identifyJobId, setIdentifyJobId] = useState<string | null>(null);
  const [productJobId, setProductJobId] = useState<string | null>(null);

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

  // Auto-advance from step 1 to step 2 once Google Search Console connects.
  useEffect(() => {
    if (step === 1 && gsc?.connected) setStep(2);
  }, [step, gsc?.connected]);

  const handleProfileValidated = (_profile: BusinessProfile, identifyJobId: string | null) => {
    setIdentifyJobId(identifyJobId);
    setStep(3);
  };

  const handleProductsSaved = (jobId: string) => {
    setProductJobId(jobId);
    setStep(4);
  };

  const handleAnalysisComplete = (_job: MarketJobState) => {
    navigate(localizedPath("/app", locale));
  };

  return (
    <Page
      title={t(locale, "onboarding")}
      backAction={{
        content: t(locale, "backDashboard"),
        url: localizedPath("/app", locale),
      }}
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
          <ConnectGoogleStep
            locale={locale}
            gsc={gsc}
            ga4={ga4}
            legacyActionData={legacyActionData}
            onContinue={() => setStep(2)}
          />
        )}

        {step === 2 && (
          <BusinessProfilePanel
            locale={locale}
            initialProfile={businessProfile}
            onValidated={handleProfileValidated}
          />
        )}

        {step === 3 && (
          <ProductIdentificationPanel
            locale={locale}
            initialJobId={identifyJobId}
            onSaved={handleProductsSaved}
          />
        )}

        {step === 4 && productJobId && (
          <MarketAnalysisProgressPanel
            locale={locale}
            jobId={productJobId}
            onComplete={handleAnalysisComplete}
          />
        )}

        <details>
          <summary>{locale === "fr" ? "Outils avancés" : "Advanced tools"}</summary>
          <div style={{ marginTop: "var(--p-space-300)" }}>
            <BlockStack gap="400">
              <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
                <InstallationChecklistCard
                  locale={locale}
                  shop={shop}
                  status={status}
                  health={health}
                  gsc={gsc}
                  pagespeed={pagespeed}
                  crawl={crawl}
                />
                <AuditLauncherCard locale={locale} recentJobs={recentJobs} actionData={legacyActionData} />
              </InlineGrid>

              <GoogleSearchConsoleCard locale={locale} gsc={gsc} actionData={legacyActionData} />
              <PageSpeedCard locale={locale} pagespeed={pagespeed} />
              <CrawlCard locale={locale} crawl={crawl} actionData={legacyActionData} />
            </BlockStack>
          </div>
        </details>
      </BlockStack>
    </Page>
  );
}
