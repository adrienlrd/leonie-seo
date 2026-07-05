import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useFetcher, useLoaderData, useNavigate, useRevalidator } from "@remix-run/react";
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
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
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
  const locale = getLocale(request);
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

  return json({ locale, gsc, ga4, ga4Properties, learningSettings, llmsTxt, themeExt });
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
      { accessToken: session.accessToken, method: "DELETE" },
    );
    return json({ type: "resetAllData", ok: resp.ok });
  }

  if (intent === "saveAutomation") {
    const automationMode = String(form.get("automation_mode") ?? "semi_auto");
    // "manual" maps to enabled=false; the persisted `mode` then defaults back to
    // semi_auto, so a merchant who switches manual -> auto_apply lands on semi_auto
    // rather than their previous auto_apply choice. Acceptable simplification for
    // a 3-way UI control over a 2-field backend model.
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/learning/settings`,
      {
        method: "PUT",
        accessToken: session.accessToken,
        body: JSON.stringify({
          enabled: automationMode !== "manual",
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

  if (intent === "testReanalysis1h") {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/agent-schedule/test-in-1h`,
      { accessToken: session.accessToken, method: "POST" },
    );
    return json({ type: "testReanalysis1h", ok: resp.ok, error: resp.ok ? null : `Backend ${resp.status}` });
  }

  return json({ type: "unknown", ok: false, reset: 0 });
};

export default function AccountHub() {
  const { locale, gsc, ga4, ga4Properties, learningSettings, llmsTxt, themeExt } = useLoaderData<typeof loader>() as {
    locale: Locale;
    gsc: GSCStatus | null;
    ga4: GA4Status | null;
    ga4Properties: GA4Property[];
    learningSettings: LearningSettings | null;
    llmsTxt: LlmsTxtStatus | null;
    themeExt: { available?: boolean; enabled?: boolean | null } | null;
  };
  const fr = locale === "fr";
  const gscConnected = Boolean(gsc?.connected);
  const ga4Connected = Boolean(ga4?.ready);
  const resetFetcher = useFetcher<{ type: string; ok: boolean; reset: number }>();
  const resetAllFetcher = useFetcher<{ type: string; ok: boolean }>();
  const automationFetcher = useFetcher<{ type: string; ok: boolean; error: string | null }>();
  const testReanalysisFetcher = useFetcher<{ type: string; ok: boolean; error: string | null }>();
  const onboardingFetcher = useFetcher<OnboardingActionData>();
  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmResetAll, setConfirmResetAll] = useState(false);

  const initialMode: "manual" | "semi_auto" | "auto_apply" = !learningSettings?.enabled
    ? "manual"
    : learningSettings.mode === "auto_apply"
      ? "auto_apply"
      : "semi_auto";
  const [automationMode, setAutomationMode] = useState<"manual" | "semi_auto" | "auto_apply">(initialMode);
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

  // After a full reset, force the merchant back into onboarding as if the app
  // was just installed. Client-side navigation keeps the embedded auth context
  // (App Bridge), unlike a server redirect that would drop shop/host/id_token.
  const navigate = useNavigate();
  useEffect(() => {
    if (resetAllFetcher.state === "idle" && resetAllFetcher.data?.ok) {
      navigate(localizedPath("/app/onboarding", locale));
    }
  }, [resetAllFetcher.state, resetAllFetcher.data, navigate, locale]);

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
      description: fr
        ? "Plan actuel, facturation et passage Pro ou Agency."
        : "Current plan, billing, and upgrade to Pro or Agency.",
    },
    {
      titleKey: "settings",
      href: "/app/settings",
      description: fr
        ? "Préférences, budget IA, locales multilingues."
        : "Preferences, AI budget, multilingual locales.",
    },
    {
      titleKey: "privacy",
      href: "/app/privacy",
      description: fr
        ? "Confidentialité, export et suppression de vos données (RGPD)."
        : "Privacy, data export, and deletion (GDPR).",
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
    resetAllFetcher.submit(fd, { method: "post" });
    setConfirmResetAll(false);
  };

  return (
    <Page
      title={t(locale, "hubSettings")}
      subtitle={t(locale, "hubSettingsSubtitle")}
    >
      <BlockStack gap="600">
        <HubGrid items={items} locale={locale} />

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
                label={t(locale, "automationModeLabel")}
                options={[
                  { label: t(locale, "automationModeManual"), value: "manual" },
                  { label: t(locale, "automationModeSemiAuto"), value: "semi_auto" },
                  { label: t(locale, "automationModeAutoApply"), value: "auto_apply" },
                ]}
                value={automationMode}
                onChange={(value) => setAutomationMode(value as "manual" | "semi_auto" | "auto_apply")}
              />
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
              <InlineStack gap="300" blockAlign="center" wrap>
                <Button
                  url={localizedPath("/app/continuous-improvement", locale)}
                  variant="plain"
                >
                  {t(locale, "automationScheduleLink")}
                </Button>
                <Button
                  variant="plain"
                  loading={testReanalysisFetcher.state !== "idle"}
                  onClick={() => testReanalysisFetcher.submit({ intent: "testReanalysis1h" }, { method: "post" })}
                >
                  {t(locale, "testReanalysisLabel")}
                </Button>
              </InlineStack>
              <Button
                variant="primary"
                loading={automationFetcher.state !== "idle"}
                onClick={saveAutomation}
              >
                {t(locale, "automationSave")}
              </Button>
            </InlineStack>

            {testReanalysisFetcher.data?.ok && (
              <Banner tone="success">
                <Text as="p">{t(locale, "testReanalysisQueued")}</Text>
              </Banner>
            )}

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
                  {fr ? "Analyse GEO — sources de données" : "GEO Analysis — data sources"}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {fr
                    ? "L'analyse utilise le profil entreprise validé quand il existe et remonte des signaux pour l'améliorer."
                    : "The analysis uses the validated business profile when available and surfaces signals to improve it."}
                </Text>
              </BlockStack>
              <InlineStack gap="400" wrap>
                <InlineStack gap="200" blockAlign="center">
                  <Text as="span" variant="bodySm">Shopify</Text>
                  <Badge tone="success">{fr ? "Réel" : "Live"}</Badge>
                </InlineStack>
                <InlineStack gap="200" blockAlign="center">
                  <Text as="span" variant="bodySm">Google Search Console</Text>
                  <Badge tone={gscConnected ? "success" : "attention"}>
                    {gscConnected ? (fr ? "Réel" : "Live") : (fr ? "À connecter" : "Not connected")}
                  </Badge>
                </InlineStack>
                <InlineStack gap="200" blockAlign="center">
                  <Text as="span" variant="bodySm">Google Analytics 4</Text>
                  <Badge tone={ga4Connected ? "success" : "attention"}>
                    {ga4Connected
                      ? (fr ? "Réel" : "Live")
                      : ga4?.oauth_connected
                        ? (fr ? "Propriété à sélectionner" : "Select a property")
                        : (fr ? "À connecter" : "Not connected")}
                  </Badge>
                </InlineStack>
                <InlineStack gap="200" blockAlign="center">
                  <Text as="span" variant="bodySm">{fr ? "Extension de thème (FAQ, données structurées, fil d'Ariane)" : "Theme extension (FAQ, structured data, breadcrumb)"}</Text>
                  {themeExt?.available
                    ? (themeExt.enabled
                        ? <Badge tone="success">{fr ? "Activée" : "Enabled"}</Badge>
                        : <Badge tone="attention">{fr ? "Non activée" : "Not enabled"}</Badge>)
                    : <Badge tone="info">{fr ? "Indéterminé" : "Unknown"}</Badge>}
                </InlineStack>
              </InlineStack>
              {themeExt?.available && !themeExt.enabled && (
                <Text as="p" variant="bodySm" tone="subdued">
                  {fr
                    ? "Activez « GEO by Organically » dans Boutique en ligne → Personnaliser → Intégrations d'app pour publier la FAQ, les données structurées et le fil d'Ariane sur votre boutique."
                    : "Enable “GEO by Organically” in Online Store → Customize → App embeds to publish the FAQ, structured data and breadcrumb on your storefront."}
                </Text>
              )}
            </BlockStack>
          }
        />

        <Card>
          <BlockStack gap="300">
            <BlockStack gap="100">
              <Text as="h2" variant="headingMd">
                {t(locale, "aiCrawlerVisibilityTitle")}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "aiCrawlerVisibilityBody")}
              </Text>
            </BlockStack>
            <InlineStack align="space-between" blockAlign="center" wrap>
              <InlineStack gap="200" blockAlign="center">
                {llmsTxt?.divergent ? (
                  <Badge tone="attention">{t(locale, "llmsTxtStatusDivergent")}</Badge>
                ) : llmsTxt?.is_published ? (
                  <Badge tone="success">{t(locale, "llmsTxtStatusPublished")}</Badge>
                ) : (
                  <Badge>{t(locale, "llmsTxtStatusNotPublished")}</Badge>
                )}
              </InlineStack>
              <Button url={localizedPath("/app/geo-llms-txt", locale)} variant="plain">
                {t(locale, "aiCrawlerVisibilityManage")}
              </Button>
            </InlineStack>
          </BlockStack>
        </Card>

        <Divider />

        <Card>
          <BlockStack gap="300">
            <BlockStack gap="100">
              <Text as="h2" variant="headingMd">
                {fr ? "Zone de danger" : "Danger zone"}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                {fr
                  ? "Ces actions sont irréversibles."
                  : "These actions are irreversible."}
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
                    {fr ? "Réinitialiser les tags" : "Reset tags"}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {fr
                      ? "Supprime tous les tags ajoutés et retirés pour tous les produits."
                      : "Deletes all added and retired tags for all products."}
                  </Text>
                </BlockStack>
                {!confirmReset ? (
                  <Button tone="critical" onClick={() => setConfirmReset(true)}>
                    {fr ? "Réinitialiser" : "Reset"}
                  </Button>
                ) : (
                  <InlineStack gap="200">
                    <Button variant="plain" onClick={() => setConfirmReset(false)}>
                      {fr ? "Annuler" : "Cancel"}
                    </Button>
                    <Button
                      tone="critical"
                      loading={resetFetcher.state !== "idle"}
                      onClick={onResetConfirm}
                    >
                      {fr ? "Confirmer la réinitialisation" : "Confirm reset"}
                    </Button>
                  </InlineStack>
                )}
              </InlineStack>
            </Box>

            {resetFetcher.data?.ok && (
              <Banner tone="success">
                <Text as="p" variant="bodySm">
                  {fr
                    ? `${resetFetcher.data.reset} tag(s) supprimé(s).`
                    : `${resetFetcher.data.reset} tag(s) deleted.`}
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
                    {fr ? "Réinitialiser l'application" : "Reset the app"}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {fr
                      ? "Remet l'application à zéro, comme au premier lancement : supprime toutes vos données de nos serveurs (analyses, catalogue, tags, planification, connexions Google Search Console et Analytics) et relance la configuration initiale. Votre abonnement et l'installation sont conservés."
                      : "Resets the app to its first-open state: deletes all your data from our servers (analyses, catalog, tags, scheduling, Google Search Console and Analytics connections) and restarts the initial setup. Your subscription and installation are kept."}
                  </Text>
                </BlockStack>
                {!confirmResetAll ? (
                  <Button tone="critical" onClick={() => setConfirmResetAll(true)}>
                    {fr ? "Réinitialiser" : "Reset"}
                  </Button>
                ) : (
                  <InlineStack gap="200">
                    <Button variant="plain" onClick={() => setConfirmResetAll(false)}>
                      {fr ? "Annuler" : "Cancel"}
                    </Button>
                    <Button
                      tone="critical"
                      loading={resetAllFetcher.state !== "idle"}
                      onClick={onResetAllConfirm}
                    >
                      {fr ? "Tout supprimer" : "Delete everything"}
                    </Button>
                  </InlineStack>
                )}
              </InlineStack>
            </Box>
          </BlockStack>
        </Card>
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
