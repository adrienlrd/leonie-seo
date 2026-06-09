import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { Form, useActionData, useFetcher, useLoaderData, useNavigation, useRevalidator } from "@remix-run/react";
import { useEffect, useRef } from "react";
import { Badge, Banner, BlockStack, Button, Card, InlineGrid, InlineStack, Link, Page, ProgressBar, Text } from "@shopify/polaris";
import { BusinessProfilePanel, type BusinessProfile } from "../components/BusinessProfilePanel";
import { ProductIdentificationPanel, type ProductLabels } from "../components/ProductIdentificationPanel";
import { callBackend, callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { authenticate } from "../shopify.server";

interface GSCStatus { connected?: boolean; site_url?: string | null }
interface GA4Status { connected?: boolean; property_id?: string | null }
interface JobData { job_id?: string; status?: string; error?: string | null; profile?: BusinessProfile; labels?: Record<string, string>; product_titles?: Record<string, string>; progress?: number; products?: unknown[] }
interface ActionData { authorizationUrl?: string; ga4AuthorizationUrl?: string; disconnected?: boolean; imported?: string; error?: string; job?: JobData; saved?: boolean; redirectTo?: string; intent?: string }
interface LoaderData { locale: Locale; shop: string; gsc: GSCStatus | null; ga4: GA4Status | null; profile: BusinessProfile | null; identification: ProductLabels | null; marketReady: boolean }

async function fetchOk<T>(promise: Promise<Response>): Promise<T | null> {
  try {
    const resp = await promise;
    if (!resp.ok) return null;
    return (await resp.json()) as T;
  } catch (_error) {
    return null;
  }
}

function textLines(value: FormDataEntryValue | null): string[] {
  return String(value || "").split("\n").map((item) => item.trim()).filter(Boolean);
}

function personasFromText(value: FormDataEntryValue | null) {
  return textLines(value).map((line) => {
    const [name = "", description = "", mainNeed = "", buyingTrigger = ""] = line.split("—").map((part) => part.trim());
    return { name, description, main_need: mainNeed, buying_trigger: buyingTrigger };
  });
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const be = (path: string) => callBackendForShop(shop, path, { accessToken: session.accessToken });

  const [gsc, ga4, profile, identification, latestAnalysis] = await Promise.all([
    fetchOk<GSCStatus>(be(`/api/shops/${shop}/gsc/status`)),
    fetchOk<GA4Status>(be(`/api/shops/${shop}/ga4/status`)),
    fetchOk<BusinessProfile>(be(`/api/shops/${shop}/business-profile/latest`)),
    fetchOk<ProductLabels>(be(`/api/shops/${shop}/market-analysis/identify/latest`)),
    fetchOk<{ products?: unknown[] }>(be(`/api/shops/${shop}/market-analysis/latest`)),
  ]);

  return json<LoaderData>({
    locale,
    shop,
    gsc,
    ga4,
    profile,
    identification,
    marketReady: Boolean(latestAnalysis?.products?.length),
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const form = await request.formData();
  const intent = String(form.get("intent") || "");
  const be = (path: string, init: RequestInit = {}) => callBackendForShop(shop, path, { accessToken: session.accessToken, ...init });

  try {
    if (intent === "gsc_connect") {
      const resp = await be(`/api/shops/${shop}/gsc/authorize`, { method: "POST" });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { authorization_url: string };
      return json<ActionData>({ authorizationUrl: data.authorization_url });
    }
    if (intent === "ga4_connect") {
      const resp = await be(`/api/shops/${shop}/ga4/authorize`, { method: "POST" });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { authorization_url: string };
      return json<ActionData>({ ga4AuthorizationUrl: data.authorization_url });
    }
    if (intent === "gsc_import") {
      const resp = await be(`/api/shops/${shop}/gsc/import`, { method: "POST", body: JSON.stringify({ days: 90 }) });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { job_id: string };
      return json<ActionData>({ imported: data.job_id });
    }
    if (intent === "business_profile_analyze") {
      const resp = await be(`/api/shops/${shop}/business-profile/analyze`, { method: "POST", body: JSON.stringify({ force_refresh: true }) });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      return json<ActionData>({ job: (await resp.json()) as JobData, intent });
    }
    if (intent === "business_profile_poll") {
      const jobId = String(form.get("job_id") || "");
      const resp = await be(`/api/shops/${shop}/business-profile/job/${jobId}`);
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      return json<ActionData>({ job: (await resp.json()) as JobData, intent });
    }
    if (intent === "business_profile_save") {
      const body = {
        niche_summary: String(form.get("niche_summary") || ""),
        brand_name: String(form.get("brand_name") || ""),
        brand_voice: String(form.get("brand_voice") || ""),
        target_personas: personasFromText(form.get("target_personas_text")),
        competitor_domains: textLines(form.get("competitor_domains_text")),
        key_themes: textLines(form.get("key_themes_text")),
      };
      const resp = await be(`/api/shops/${shop}/business-profile`, { method: "POST", body: JSON.stringify(body) });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      return json<ActionData>({ saved: true });
    }
    if (intent === "identify_start") {
      const resp = await be(`/api/shops/${shop}/market-analysis/identify`, { method: "POST" });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      return json<ActionData>({ job: (await resp.json()) as JobData, intent });
    }
    if (intent === "identify_poll" || intent === "deep_poll") {
      const jobId = String(form.get("job_id") || "");
      const resp = await be(`/api/shops/${shop}/market-analysis/jobs/${jobId}`);
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      return json<ActionData>({ job: (await resp.json()) as JobData, intent });
    }
    if (intent === "save_identifications") {
      const identifications: Record<string, string> = {};
      for (const [key, value] of form.entries()) {
        if (key.startsWith("label_")) identifications[key.slice(6)] = String(value || "").trim();
      }
      const resp = await be(`/api/shops/${shop}/market-analysis/identifications`, { method: "POST", body: JSON.stringify({ identifications }) });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      return json<ActionData>({ saved: true });
    }
    if (intent === "deep_start") {
      const resp = await be(`/api/shops/${shop}/market-analysis/jobs`, { method: "POST" });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      return json<ActionData>({ job: (await resp.json()) as JobData, intent });
    }
    if (intent === "finish") return redirect(localizedPath("/app", locale));
  } catch (_error) {
    return json<ActionData>({ error: t(locale, "backendOffline") });
  }
  return json<ActionData>({ error: "Unsupported intent" });
};

function StepCard({ index, title, body, done, active, children }: { index: number; title: string; body: string; done: boolean; active: boolean; children: React.ReactNode }) {
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <InlineStack gap="200" blockAlign="center"><Badge tone={done ? "success" : active ? "info" : undefined}>{String(index)}</Badge><Text as="h2" variant="headingMd">{title}</Text></InlineStack>
          <Badge tone={done ? "success" : active ? "info" : undefined}>{done ? "OK" : active ? "Now" : "Next"}</Badge>
        </InlineStack>
        <Text as="p" tone="subdued">{body}</Text>
        {(active || done) ? children : null}
      </BlockStack>
    </Card>
  );
}

function usePollingJob(intent: "business_profile_poll" | "identify_poll" | "deep_poll", jobId?: string) {
  const fetcher = useFetcher<ActionData>();
  useEffect(() => {
    if (!jobId) return undefined;
    const timer = window.setInterval(() => {
      const data = new FormData();
      data.set("intent", intent);
      data.set("job_id", jobId);
      fetcher.submit(data, { method: "post" });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [fetcher, intent, jobId]);
  return fetcher.data?.job;
}

export default function Onboarding() {
  const { locale, gsc, ga4, profile, identification, marketReady } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>() as ActionData | undefined;
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  const openedUrlRef = useRef<string | null>(null);
  const fr = locale === "fr";
  const submittingAction = String(navigation.formData?.get("intent") || "");
  const startedJob = actionData?.job;
  const businessJob = usePollingJob("business_profile_poll", startedJob?.job_id && actionData?.intent === "business_profile_analyze" ? startedJob.job_id : undefined);
  const identifyJob = usePollingJob("identify_poll", startedJob?.job_id && actionData?.intent === "identify_start" ? startedJob.job_id : undefined);
  const deepJob = usePollingJob("deep_poll", startedJob?.job_id && actionData?.intent === "deep_start" ? startedJob.job_id : undefined);
  const displayedProfile = businessJob?.profile ?? actionData?.job?.profile ?? profile;
  const displayedIdentification = identifyJob?.labels ? { labels: identifyJob.labels, product_titles: identifyJob.product_titles } : identification;
  const googleReady = Boolean(gsc?.connected && ga4?.connected);
  const profileValidated = Boolean(displayedProfile?.status === "validated" || actionData?.saved);
  const labelsReady = Boolean(displayedIdentification?.labels && Object.keys(displayedIdentification.labels).length > 0);
  const activeStep = !googleReady ? 1 : !profileValidated ? 2 : !labelsReady ? 3 : 4;

  useEffect(() => {
    const url = actionData?.authorizationUrl ?? actionData?.ga4AuthorizationUrl;
    if (!url || openedUrlRef.current === url || typeof window === "undefined") return;
    openedUrlRef.current = url;
    window.open(url, "leonie-google-oauth", "width=520,height=720,menubar=no,toolbar=no");
  }, [actionData?.authorizationUrl, actionData?.ga4AuthorizationUrl]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const onMessage = (event: MessageEvent) => {
      const data = event.data as { source?: string; ok?: boolean } | null;
      if (data?.source === "leonie-google-oauth" && data.ok) revalidator.revalidate();
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [revalidator]);

  useEffect(() => {
    if (businessJob?.status === "completed" || identifyJob?.status === "completed" || deepJob?.status === "completed" || actionData?.saved || actionData?.imported) revalidator.revalidate();
  }, [actionData?.imported, actionData?.saved, businessJob?.status, deepJob?.status, identifyJob?.status, revalidator]);

  return (
    <Page title={t(locale, "onboardingJourneyTitle")} backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}>
      <BlockStack gap="400">
        {actionData?.error ? <Banner tone="critical" title={actionData.error} /> : null}
        <Banner tone="info" title={t(locale, "onboardingJourneyIntroTitle")}><Text as="p">{t(locale, "onboardingJourneyIntroBody")}</Text></Banner>
        <StepCard index={1} title={t(locale, "onboardingConnectGoogleTitle")} body={t(locale, "onboardingConnectGoogleBody")} done={googleReady} active={activeStep === 1}>
          <InlineGrid columns={{ xs: 1, md: 2 }} gap="300">
            <Card><BlockStack gap="200"><Text as="h3" variant="headingSm">Google Search Console</Text><Badge tone={gsc?.connected ? "success" : "attention"}>{gsc?.connected ? t(locale, "connected") : t(locale, "missing")}</Badge><Form method="post"><input type="hidden" name="intent" value="gsc_connect" /><Button submit loading={submittingAction === "gsc_connect"}>{t(locale, "onboardingConnect")}</Button></Form><Form method="post"><input type="hidden" name="intent" value="gsc_import" /><Button submit variant="plain" loading={submittingAction === "gsc_import"}>{t(locale, "onboardingImportGsc")}</Button></Form></BlockStack></Card>
            <Card><BlockStack gap="200"><Text as="h3" variant="headingSm">Google Analytics 4</Text><Badge tone={ga4?.connected ? "success" : "attention"}>{ga4?.connected ? t(locale, "connected") : t(locale, "missing")}</Badge><Form method="post"><input type="hidden" name="intent" value="ga4_connect" /><Button submit loading={submittingAction === "ga4_connect"}>{t(locale, "onboardingConnect")}</Button></Form></BlockStack></Card>
          </InlineGrid>
          {(actionData?.authorizationUrl || actionData?.ga4AuthorizationUrl) ? <Text as="p" tone="subdued"><Link url={actionData.authorizationUrl ?? actionData.ga4AuthorizationUrl ?? "#"} target="_blank">{t(locale, "onboardingPopupFallback")}</Link></Text> : null}
        </StepCard>
        <StepCard index={2} title={t(locale, "onboardingFirstAnalysisTitle")} body={t(locale, "onboardingFirstAnalysisBody")} done={profileValidated} active={activeStep === 2}>
          <Form method="post"><input type="hidden" name="intent" value="business_profile_analyze" /><Button submit variant="primary" loading={submittingAction === "business_profile_analyze"}>{t(locale, "onboardingRunFirstAnalysis")}</Button></Form>
          {startedJob?.status || businessJob?.status ? <ProgressBar progress={(businessJob?.status ?? startedJob?.status) === "completed" ? 100 : 45} /> : null}
          {displayedProfile ? <Form method="post"><input type="hidden" name="intent" value="business_profile_save" /><BusinessProfilePanel profile={displayedProfile} locale={locale} /><Button submit variant="primary" loading={submittingAction === "business_profile_save"}>{t(locale, "onboardingValidateProfile")}</Button></Form> : null}
        </StepCard>
        <StepCard index={3} title={t(locale, "onboardingAdjustProductsTitle")} body={t(locale, "onboardingAdjustProductsBody")} done={labelsReady} active={activeStep === 3}>
          <Form method="post"><input type="hidden" name="intent" value="identify_start" /><Button submit variant="primary" loading={submittingAction === "identify_start"}>{t(locale, "onboardingIdentifyProducts")}</Button></Form>
          {identifyJob?.status ? <ProgressBar progress={identifyJob.status === "completed" ? 100 : 50} /> : null}
          {displayedIdentification ? <Form method="post"><input type="hidden" name="intent" value="save_identifications" /><ProductIdentificationPanel identification={displayedIdentification} locale={locale} /><Button submit variant="primary" loading={submittingAction === "save_identifications"}>{t(locale, "onboardingSaveLabels")}</Button></Form> : null}
        </StepCard>
        <StepCard index={4} title={t(locale, "onboardingDeepAnalysisTitle")} body={t(locale, "onboardingDeepAnalysisBody")} done={marketReady} active={activeStep === 4}>
          <Form method="post"><input type="hidden" name="intent" value="deep_start" /><Button submit variant="primary" loading={submittingAction === "deep_start"}>{t(locale, "onboardingRunDeepAnalysis")}</Button></Form>
          {deepJob?.status || (startedJob?.status && submittingAction === "deep_start") ? <ProgressBar progress={(deepJob?.status ?? startedJob?.status) === "completed" ? 100 : Number(deepJob?.progress ?? 55)} /> : null}
          {(deepJob?.status === "completed" || marketReady) ? <Button url={localizedPath("/app", locale)} variant="primary">{fr ? "Aller au Dashboard" : "Go to Dashboard"}</Button> : null}
        </StepCard>
      </BlockStack>
    </Page>
  );
}
