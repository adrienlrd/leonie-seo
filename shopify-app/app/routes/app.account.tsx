import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useFetcher, useLoaderData, useRevalidator } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  ChoiceList,
  Divider,
  InlineStack,
  Page,
  Select,
  Text,
} from "@shopify/polaris";
import { PlanBadge } from "../components/PlanBadge";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { localizedPath, t, type Locale } from "../lib/i18n";
import { invalidateLocaleCache, resolveLocale } from "../lib/i18n.server";
import { showToast } from "../lib/toast";
import { HubGrid, type HubItem } from "../components/HubGrid";
import { GoogleConnectionsCard } from "../components/GoogleConnectionsCard";
import type { GA4Property, GA4Status, GSCStatus, OnboardingActionData } from "../components/onboarding/types";

interface LearningSettings {
  enabled: boolean;
  mode: "semi_auto" | "auto_apply";
  reanalysis_frequency_days: number;
  auto_publish_scopes: string[];
}

interface LlmsTxtStatus {
  is_published: boolean;
  divergent: boolean;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = await resolveLocale(request, session.shop, session.accessToken);
  const [gscResp, ga4Resp, learningResp, llmsResp, themeExtResp] = await Promise.allSettled([
    callBackendForShop(session.shop, `/api/shops/${session.shop}/gsc/status`, { accessToken: session.accessToken }),
    callBackendForShop(session.shop, `/api/shops/${session.shop}/ga4/status`, { accessToken: session.accessToken }),
    callBackendForShop(session.shop, `/api/shops/${session.shop}/learning/settings`, { accessToken: session.accessToken }),
    callBackendForShop(session.shop, `/api/shops/${session.shop}/llms-txt/status`, { accessToken: session.accessToken }),
    callBackendForShop(session.shop, `/api/shops/${session.shop}/geo/theme-extension-status`, { accessToken: session.accessToken }),
  ]);
  const gsc = gscResp.status === "fulfilled" && gscResp.value.ok
    ? ((await gscResp.value.json().catch(() => null)) as GSCStatus | null)
    : null;
  const ga4 = ga4Resp.status === "fulfilled" && ga4Resp.value.ok
    ? ((await ga4Resp.value.json().catch(() => null)) as GA4Status | null)
    : null;
  const learningSettings = learningResp.status === "fulfilled" && learningResp.value.ok
    ? (((await learningResp.value.json().catch(() => null)) as { settings?: LearningSettings } | null)?.settings ?? null)
    : null;
  const llmsTxt = llmsResp.status === "fulfilled" && llmsResp.value.ok
    ? ((await llmsResp.value.json().catch(() => null)) as LlmsTxtStatus | null)
    : null;
  const themeExt = themeExtResp.status === "fulfilled" && themeExtResp.value.ok
    ? ((await themeExtResp.value.json().catch(() => null)) as { available?: boolean; enabled?: boolean | null } | null)
    : null;

  // When GA4 is authorized but no property is selected yet, fetch the property
  // list so the card can show a selector (the only way to finish GA4 setup).
  let ga4Properties: GA4Property[] = [];
  if (ga4?.oauth_connected && !ga4?.ready) {
    try {
      const propsResp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/ga4/properties`,
        { accessToken: session.accessToken },
      );
      if (propsResp.ok) {
        ga4Properties = (((await propsResp.json()) as { properties?: GA4Property[] }).properties ?? []);
      }
    } catch { /* ignore */ }
  }

  return json({ locale, gsc, ga4, ga4Properties, learningSettings, llmsTxt, themeExt, backendUrl: process.env.PYTHON_BACKEND_URL || "http://localhost:8000" });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const intent = String(form.get("intent") ?? "");

  if (intent === "resetTags") {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/tags/reset`,
      { accessToken: session.accessToken, method: "DELETE" },
    );
    const data = resp.ok ? (await resp.json()) as { reset: number } : null;
    return json({ type: "resetTags", ok: resp.ok, reset: data?.reset ?? 0 });
  }

  if (intent === "resetAllData") {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/reset-all`,
      { accessToken: session.accessToken, method: "DELETE", signal: AbortSignal.timeout(25_000) },
    );
    if (resp.ok) {
      // Server-side redirect (followed by the fetcher) is the reliable way to
      // navigate inside the embedded iframe. Land the merchant back on the now
      // first-open home page.
      return redirect(localizedPath("/app", await resolveLocale(request, session.shop, session.accessToken)));
    }
    const error = (await resp.text()).slice(0, 300);
    return json({ type: "resetAllData", ok: false, error });
  }

  if (intent === "setLanguage") {
    const language = String(form.get("language") ?? "");
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/language`,
      {
        accessToken: session.accessToken,
        method: "PUT",
        body: JSON.stringify({ language }),
        signal: AbortSignal.timeout(10_000),
      },
    );
    if (resp.ok) invalidateLocaleCache(session.shop);
    // Redirect with the new locale so the whole app re-renders in it at once.
    return redirect(localizedPath("/app/account", language as Locale));
  }

  if (intent === "saveAutomation") {
    const automationMode = String(form.get("automation_mode") ?? "semi_auto");
    // Learning is always enabled; the mode only decides manual (semi_auto) vs
    // automatic (auto_apply) publishing. There is no "no learning" state anymore.
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/learning/settings`,
      {
        method: "PUT",
        accessToken: session.accessToken,
        body: JSON.stringify({
          enabled: true,
          mode: automationMode === "auto_apply" ? "auto_apply" : "semi_auto",
          reanalysis_frequency_days: Number(form.get("reanalysis_frequency_days") ?? 28),
        }),
      },
    );
    const data = await resp.json().catch(() => ({}));
    return json({
      type: "saveAutomation",
      ok: resp.ok,
      error: resp.ok ? null : ((data as { detail?: string }).detail ?? `Backend ${resp.status}`),
    });
  }

  return json({ type: "unknown", ok: false, reset: 0 });
};

export default function AccountHub() {
  const { locale, gsc, ga4, ga4Properties, learningSettings, llmsTxt, themeExt, backendUrl } = useLoaderData<typeof loader>() as {
    locale: Locale;
    gsc: GSCStatus | null;
    ga4: GA4Status | null;
    ga4Properties: GA4Property[];
    learningSettings: LearningSettings | null;
    llmsTxt: LlmsTxtStatus | null;
    themeExt: { available?: boolean; enabled?: boolean | null } | null;
    backendUrl: string;
  };
  const gscConnected = Boolean(gsc?.connected);
  const ga4Connected = Boolean(ga4?.ready);
  const resetFetcher = useFetcher<{ type: string; ok: boolean; reset: number }>();
  const resetAllFetcher = useFetcher<{ type: string; ok: boolean; error?: string | null }>();
  const automationFetcher = useFetcher<{ type: string; ok: boolean; error: string | null }>();
  useEffect(() => {
    if (automationFetcher.data?.ok) showToast(t(locale, "toastSaved"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [automationFetcher.data]);
  const onboardingFetcher = useFetcher<OnboardingActionData>();
  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmResetAll, setConfirmResetAll] = useState(false);

  // Two publish modes only; learning + 28-day re-analysis are always on. A legacy
  // enabled=false shop maps to manual publish (semi_auto) — never a "no learning" state.
  const initialMode: "semi_auto" | "auto_apply" =
    learningSettings?.mode === "auto_apply" ? "auto_apply" : "semi_auto";
  const [automationMode, setAutomationMode] = useState<"semi_auto" | "auto_apply">(initialMode);
  const [reanalysisFrequency, setReanalysisFrequency] = useState(
    String(learningSettings?.reanalysis_frequency_days ?? 28),
  );

  useEffect(() => {
    setAutomationMode(initialMode);
    setReanalysisFrequency(String(learningSettings?.reanalysis_frequency_days ?? 28));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [learningSettings]);

  const saveAutomation = () => {
    const fd = new FormData();
    fd.set("intent", "saveAutomation");
    fd.set("automation_mode", automationMode);
    fd.set("reanalysis_frequency_days", reanalysisFrequency);
    automationFetcher.submit(fd, { method: "post" });
  };

  // Open Google's consent screen in a popup when the onboarding action returns an
  // authorization URL, mirroring the onboarding wizard's connect flow.
  const revalidator = useRevalidator();

  // On success the action redirects home, so we only reach here on failure:
  // collapse the confirm buttons so the error banner below is clearly visible.
  useEffect(() => {
    if (resetAllFetcher.state === "idle" && resetAllFetcher.data) {
      setConfirmResetAll(false);
    }
  }, [resetAllFetcher.state, resetAllFetcher.data]);

  const openedUrlRef = useRef<string | null>(null);
  useEffect(() => {
    const url = onboardingFetcher.data?.authorizationUrl;
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
  }, [onboardingFetcher.data?.authorizationUrl]);

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

  useEffect(() => {
    if (onboardingFetcher.data?.disconnected) revalidator.revalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onboardingFetcher.data?.disconnected]);

  const items: HubItem[] = [
    {
      titleKey: "billing",
      href: "/app/billing",
      description: t(locale, "acctBillingDesc"),
    },
    {
      titleKey: "privacyPolicy",
      href: `${backendUrl}/privacy`,
      external: true,
      description: t(locale, "acctPrivacyDesc"),
    },
  ];

  const onResetConfirm = () => {
    const fd = new FormData();
    fd.set("intent", "resetTags");
    resetFetcher.submit(fd, { method: "post" });
    setConfirmReset(false);
  };

  const onResetAllConfirm = () => {
    const fd = new FormData();
    fd.set("intent", "resetAllData");
    // Keep the confirm buttons mounted so the loading spinner stays visible;
    // on success the action redirects home, so we leave the page anyway.
    resetAllFetcher.submit(fd, { method: "post" });
  };

  return (
    <Page
      title={t(locale, "hubSettings")}
      titleMetadata={<PlanBadge />}
      subtitle={t(locale, "hubSettingsSubtitle")}
    >
      <BlockStack gap="600">
        <LanguageCard locale={locale} />

        <Card>
          <BlockStack gap="300">
            <BlockStack gap="100">
              <Text as="h2" variant="headingMd">
                {t(locale, "automationTitle")}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "automationBody")}
              </Text>
            </BlockStack>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
              <Select
                label={t(locale, "automationFrequencyLabel")}
                options={[
                  { label: t(locale, "automationFrequency1"), value: "1" },
                  { label: t(locale, "automationFrequency14"), value: "14" },
                  { label: t(locale, "automationFrequency28"), value: "28" },
                ]}
                value={reanalysisFrequency}
                onChange={setReanalysisFrequency}
              />
            </div>

            <Text as="p" variant="bodySm" tone="subdued">
              {t(locale, "automationScopesMovedNote")}
            </Text>

            <InlineStack align="space-between" blockAlign="center" wrap>
              <div />
              <Button
                variant="primary"
                loading={automationFetcher.state !== "idle"}
                onClick={saveAutomation}
              >
                {t(locale, "automationSave")}
              </Button>
            </InlineStack>

            {automationFetcher.data?.ok && (
              <Banner tone="success">
                <Text as="p">{t(locale, "automationSaved")}</Text>
              </Banner>
            )}
            {automationFetcher.data && !automationFetcher.data.ok && (
              <Banner tone="warning">
                <Text as="p">{automationFetcher.data.error}</Text>
              </Banner>
            )}
          </BlockStack>
        </Card>

        <GoogleConnectionsCardWrapper
          locale={locale}
          gsc={gsc}
          ga4={ga4}
          ga4Properties={ga4Properties}
          fetcher={onboardingFetcher}
          footer={
            <BlockStack gap="300">
              <BlockStack gap="100">
                <Text as="h3" variant="headingSm">
                  {t(locale, "acctGeoSourcesTitle")}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "acctGeoSourcesDesc")}
                </Text>
              </BlockStack>
              <InlineStack gap="400" wrap>
                <InlineStack gap="200" blockAlign="center">
                  <Text as="span" variant="bodySm">Shopify</Text>
                  <Badge tone="success">{t(locale, "acctLive")}</Badge>
                </InlineStack>
                <InlineStack gap="200" blockAlign="center">
                  <Text as="span" variant="bodySm">Google Search Console</Text>
                  <Badge tone={gscConnected ? "success" : "attention"}>
                    {t(locale, gscConnected ? "acctLive" : "acctNotConnected")}
                  </Badge>
                </InlineStack>
                <InlineStack gap="200" blockAlign="center">
                  <Text as="span" variant="bodySm">Google Analytics 4</Text>
                  <Badge tone={ga4Connected ? "success" : "attention"}>
                    {t(locale, ga4Connected ? "acctLive" : ga4?.oauth_connected ? "acctSelectProperty" : "acctNotConnected")}
                  </Badge>
                </InlineStack>
                <InlineStack gap="200" blockAlign="center">
                  <Text as="span" variant="bodySm">{t(locale, "acctThemeExtLabel")}</Text>
                  {themeExt?.available
                    ? (themeExt.enabled
                        ? <Badge tone="success">{t(locale, "acctEnabled")}</Badge>
                        : <Badge tone="attention">{t(locale, "acctNotEnabled")}</Badge>)
                    : <Badge tone="info">{t(locale, "acctUnknown")}</Badge>}
                </InlineStack>
              </InlineStack>
              {themeExt?.available && !themeExt.enabled && (
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "acctThemeExtHowTo")}
                </Text>
              )}
            </BlockStack>
          }
        />

        <Card>
          <BlockStack gap="300">
            <BlockStack gap="100">
              <Text as="h2" variant="headingMd">
                {t(locale, "acctDangerZone")}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "acctIrreversible")}
              </Text>
            </BlockStack>

            <Box
              padding="400"
              background="bg-surface-critical"
              borderRadius="200"
              borderColor="border-critical"
              borderWidth="025"
            >
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="050">
                  <Text as="p" variant="bodyMd" fontWeight="semibold">
                    {t(locale, "acctResetTags")}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {t(locale, "acctResetTagsDesc")}
                  </Text>
                </BlockStack>
                {!confirmReset ? (
                  <Button tone="critical" onClick={() => setConfirmReset(true)}>
                    {t(locale, "acctReset")}
                  </Button>
                ) : (
                  <InlineStack gap="200">
                    <Button variant="plain" onClick={() => setConfirmReset(false)}>
                      {t(locale, "acctCancel")}
                    </Button>
                    <Button
                      tone="critical"
                      loading={resetFetcher.state !== "idle"}
                      onClick={onResetConfirm}
                    >
                      {t(locale, "acctConfirmReset")}
                    </Button>
                  </InlineStack>
                )}
              </InlineStack>
            </Box>

            {resetFetcher.data?.ok && (
              <Banner tone="success">
                <Text as="p" variant="bodySm">
                  {t(locale, "acctTagsDeleted").replace("{n}", String(resetFetcher.data.reset))}
                </Text>
              </Banner>
            )}

            <Box
              padding="400"
              background="bg-surface-critical"
              borderRadius="200"
              borderColor="border-critical"
              borderWidth="025"
            >
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="050">
                  <Text as="p" variant="bodyMd" fontWeight="semibold">
                    {t(locale, "acctResetApp")}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {t(locale, "acctResetAppDesc")}
                  </Text>
                </BlockStack>
                {!confirmResetAll ? (
                  <Button tone="critical" onClick={() => setConfirmResetAll(true)}>
                    {t(locale, "acctReset")}
                  </Button>
                ) : (
                  <InlineStack gap="200">
                    <Button variant="plain" onClick={() => setConfirmResetAll(false)}>
                      {t(locale, "acctCancel")}
                    </Button>
                    <Button
                      tone="critical"
                      loading={resetAllFetcher.state !== "idle"}
                      onClick={onResetAllConfirm}
                    >
                      {t(locale, "acctDeleteEverything")}
                    </Button>
                  </InlineStack>
                )}
              </InlineStack>
            </Box>

            {resetAllFetcher.data && !resetAllFetcher.data.ok && (
              <Banner tone="critical">
                <Text as="p" variant="bodySm">
                  {`${t(locale, "acctResetFailed")} ${resetAllFetcher.data.error ?? ""}`}
                </Text>
              </Banner>
            )}
          </BlockStack>
        </Card>
        <HubGrid items={items} locale={locale} />

      </BlockStack>
    </Page>
  );
}

/**
 * Wraps GoogleConnectionsCard with a fetcher targeting /app/onboarding's action,
 * since GSC/GA4 connect/disconnect intents live there.
 */
function GoogleConnectionsCardWrapper({
  locale,
  gsc,
  ga4,
  ga4Properties,
  fetcher,
  footer,
}: {
  locale: Locale;
  gsc: GSCStatus | null;
  ga4: GA4Status | null;
  ga4Properties: GA4Property[];
  fetcher: ReturnType<typeof useFetcher<OnboardingActionData>>;
  footer?: ReactNode;
}) {
  return (
    <GoogleConnectionsCard
      locale={locale}
      gsc={gsc}
      ga4={ga4}
      ga4Properties={ga4Properties}
      title={t(locale, "connectionsTitle")}
      description={t(locale, "connectionsBody")}
      actionPath={localizedPath("/app/onboarding", locale)}
      fetcher={fetcher}
      footer={footer}
    />
  );
}

function LanguageCard({ locale }: { locale: Locale }) {
  const fetcher = useFetcher();
  const options = [
    { label: "Français", value: "fr" },
    { label: "English", value: "en" },
    { label: "Deutsch", value: "de" },
    { label: "Español", value: "es" },
  ];
  return (
    <Card>
      <BlockStack gap="300">
        <Text as="h2" variant="headingMd">
          {t(locale, "languageCardTitle")}
        </Text>
        <Text as="p" variant="bodySm" tone="subdued">
          {t(locale, "languageCardBody")}
        </Text>
        <Box width="280px">
          <Select
            label={t(locale, "languageCardTitle")}
            labelHidden
            options={options}
            value={locale}
            onChange={(value) => {
              const fd = new FormData();
              fd.set("intent", "setLanguage");
              fd.set("language", value);
              fetcher.submit(fd, { method: "post" });
            }}
          />
        </Box>
      </BlockStack>
    </Card>
  );
}
