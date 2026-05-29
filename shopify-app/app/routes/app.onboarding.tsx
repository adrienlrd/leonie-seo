import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import {
  Form,
  useActionData,
  useLoaderData,
  useNavigation,
  useRevalidator,
} from "@remix-run/react";
import { useEffect, useRef, type ReactNode } from "react";
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
import type {
  CrawlStatus,
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
  pagespeed: PageSpeedStatus | null;
  crawl: CrawlStatus | null;
  niche: { available: boolean; status: string | null };
  recentJobs: number;
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

  const [health, status, jobs, gsc, pagespeed, crawl, niche] = await Promise.all([
    fetchOk<Health>(callBackend("/health")),
    fetchOk<ShopStatus>(be(`/api/shops/${shop}/status`)),
    fetchOk<{ count: number }>(be(`/api/shops/${shop}/jobs?limit=10`)),
    fetchOk<GSCStatus>(be(`/api/shops/${shop}/gsc/status`)),
    fetchOk<PageSpeedStatus>(be(`/api/shops/${shop}/pagespeed/status`)),
    fetchOk<CrawlStatus>(be(`/api/shops/${shop}/crawl/status`)),
    fetchOk<{ hypothesis?: { status?: string } | null }>(be(`/api/shops/${shop}/niche/hypothesis`)),
  ]);

  return json<LoaderData>({
    locale,
    shop,
    health,
    status,
    gsc,
    pagespeed,
    crawl,
    niche: {
      available: Boolean(niche?.hypothesis),
      status: niche?.hypothesis?.status ?? null,
    },
    recentJobs: jobs?.count ?? 0,
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
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

    if (intent === "niche_understand") {
      const resp = await be(`/api/shops/${shop}/niche/understand`, {
        method: "POST",
        body: JSON.stringify({ force_refresh: true, use_llm: true }),
        headers: { "Content-Type": "application/json" },
      });
      if (!resp.ok) return json<OnboardingActionData>({ error: `${resp.status}` });
      return json<OnboardingActionData>({
        jobId: locale === "fr" ? "Analyse IA terminée." : "AI analysis completed.",
      });
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

function computeNextAction(
  locale: Locale,
  status: ShopStatus | null,
  health: Health | null,
  gsc: GSCStatus | null,
  niche: { available: boolean; status: string | null },
): { label: string } | null {
  const fr = locale === "fr";
  if (!status?.installed) return { label: fr ? "Réinstaller la boutique" : "Reinstall store" };
  if (health?.status !== "ok") {
    return { label: fr ? "Vérifier la configuration serveur" : "Check server configuration" };
  }
  if (!status.snapshot_available) {
    return { label: fr ? "Lancer le premier audit" : "Run first audit" };
  }
  if (!gsc?.connected) {
    return {
      label: fr ? "Connecter Google" : "Connect Google",
    };
  }
  if (!niche.available) {
    return {
      label: fr ? "Analyser ma boutique avec l'IA" : "Analyze my store with AI",
    };
  }
  if (niche.status !== "validated_by_merchant") {
    return { label: fr ? "Valider ce que l'IA a compris" : "Validate what the AI understood" };
  }
  return { label: fr ? "Voir les 3 actions prioritaires" : "See the 3 priority actions" };
}

function GuidedStep({
  index,
  title,
  body,
  done,
  active,
  children,
  locale,
  keepChildrenWhenDone = false,
}: {
  index: number;
  title: string;
  body: string;
  done: boolean;
  active: boolean;
  children?: ReactNode;
  locale: Locale;
  keepChildrenWhenDone?: boolean;
}) {
  const statusLabel = done
    ? locale === "fr" ? "Terminé" : "Done"
    : active
      ? locale === "fr" ? "À faire maintenant" : "Do now"
      : locale === "fr" ? "Ensuite" : "Next";

  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack align="space-between" blockAlign="center" gap="200">
          <InlineStack gap="200" blockAlign="center">
            <Badge tone={done ? "success" : active ? "info" : undefined}>{String(index)}</Badge>
            <Text as="h3" variant="headingSm">{title}</Text>
          </InlineStack>
          <Badge tone={done ? "success" : active ? "info" : undefined}>{statusLabel}</Badge>
        </InlineStack>
        <Text as="p" tone="subdued">{body}</Text>
        {(active || (done && keepChildrenWhenDone)) && children}
      </BlockStack>
    </Card>
  );
}

function GuidedOnboardingFlow({
  locale,
  gsc,
  niche,
}: {
  locale: Locale;
  gsc: GSCStatus | null;
  niche: { available: boolean; status: string | null };
}) {
  const navigation = useNavigation();
  const submittingAction = String(navigation.formData?.get("intent") || "");
  const fr = locale === "fr";
  const googleReady = Boolean(gsc?.connected);
  const nicheReady = Boolean(niche.available);
  const nicheValidated = niche.status === "validated_by_merchant";
  const activeStep = !googleReady ? 1 : !nicheReady ? 2 : !nicheValidated ? 3 : 4;

  return (
    <Card>
      <BlockStack gap="400">
        <BlockStack gap="100">
          <Text as="h2" variant="headingMd">
            {fr ? "Démarrer en 4 étapes" : "Start in 4 steps"}
          </Text>
          <Text as="p" tone="subdued">
            {fr
              ? "Suivez ce chemin une seule fois, puis Léonie pourra vous proposer les actions prioritaires."
              : "Follow this path once, then Léonie can suggest your priority actions."}
          </Text>
        </BlockStack>

        <GuidedStep
          index={1}
          title={fr ? "Connecter Google" : "Connect Google"}
          body={
            fr
              ? "Léonie lit vos requêtes Google pour comprendre où votre boutique est déjà visible."
              : "Léonie reads your Google queries to understand where your store is already visible."
          }
          done={googleReady}
          active={activeStep === 1}
          locale={locale}
          keepChildrenWhenDone
        >
          {gsc?.connected ? (
            <BlockStack gap="200">
              <Text as="p" tone="subdued">
                {fr ? "Connecté" : "Connected"}
                {gsc.email ? ` : ${gsc.email}` : ""}
              </Text>
              <Form method="post">
                <input type="hidden" name="intent" value="gsc_disconnect" />
                <InlineStack gap="200">
                  <Button
                    submit
                    tone="critical"
                    loading={
                      navigation.state !== "idle" && submittingAction === "gsc_disconnect"
                    }
                  >
                    {fr ? "Déconnecter Google" : "Disconnect Google"}
                  </Button>
                  <Text as="span" tone="subdued" variant="bodySm">
                    {fr
                      ? "(libère le token — un nouveau consentement couvrira GSC + Analytics)"
                      : "(clears the token — a new consent will cover GSC + Analytics)"}
                  </Text>
                </InlineStack>
              </Form>
            </BlockStack>
          ) : (
            <Form method="post">
              <input type="hidden" name="intent" value="gsc_connect" />
              <Button
                submit
                variant="primary"
                disabled={!gsc?.configured}
                loading={navigation.state !== "idle" && submittingAction === "gsc_connect"}
              >
                {fr ? "Connecter Google" : "Connect Google"}
              </Button>
            </Form>
          )}
        </GuidedStep>

        <GuidedStep
          index={2}
          title={fr ? "Analyser ma boutique avec l'IA" : "Analyze my store with AI"}
          body={
            fr
              ? "L'IA lit vos produits, collections et signaux Google pour formuler une première compréhension."
              : "The AI reads your products, collections, and Google signals to form its first understanding."
          }
          done={nicheReady}
          active={activeStep === 2}
          locale={locale}
        >
          <Form method="post">
            <input type="hidden" name="intent" value="niche_understand" />
            <Button
              submit
              variant="primary"
              loading={navigation.state !== "idle" && submittingAction === "niche_understand"}
            >
              {fr ? "Analyser ma boutique avec l'IA" : "Analyze my store with AI"}
            </Button>
          </Form>
        </GuidedStep>

        <GuidedStep
          index={3}
          title={fr ? "Valider ce que l'IA a compris" : "Validate what the AI understood"}
          body={
            fr
              ? "Corrigez les clients, intentions et promesses à éviter avant toute recommandation."
              : "Correct customers, intents, and promises to avoid before any recommendation."
          }
          done={nicheValidated}
          active={activeStep === 3}
          locale={locale}
        >
          <Button url={localizedPath("/app/niche-understanding", locale)} variant="primary">
            {fr ? "Valider la compréhension IA" : "Validate store understanding"}
          </Button>
        </GuidedStep>

        <GuidedStep
          index={4}
          title={fr ? "Voir les 3 actions prioritaires" : "See the 3 priority actions"}
          body={
            fr
              ? "Une fois la compréhension validée, Léonie limite le choix aux actions les plus utiles maintenant."
              : "Once the understanding is validated, Léonie limits the choice to the most useful actions now."
          }
          done={false}
          active={activeStep === 4}
          locale={locale}
        >
          <Button url={localizedPath("/app/priorities", locale)} variant="primary">
            {fr ? "Voir mes actions" : "See my actions"}
          </Button>
        </GuidedStep>
      </BlockStack>
    </Card>
  );
}

export default function Onboarding() {
  const { locale, shop, health, status, gsc, pagespeed, crawl, niche, recentJobs } =
    useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const revalidator = useRevalidator();
  const openedUrlRef = useRef<string | null>(null);

  // Auto-open Google's consent screen in a centered popup when the action returns
  // an authorization URL. The OAuth callback posts a "leonie-google-oauth" message
  // back to this window, so we revalidate status as soon as it succeeds.
  useEffect(() => {
    const url = actionData?.authorizationUrl;
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
  }, [actionData?.authorizationUrl]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onMessage = (event: MessageEvent) => {
      const data = event.data as { source?: string; ok?: boolean } | null;
      if (data?.source === "leonie-google-oauth" && data.ok) {
        revalidator.revalidate();
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [revalidator]);

  // Refresh status after a disconnect so the UI flips back to "Connect".
  useEffect(() => {
    if (actionData?.disconnected) revalidator.revalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionData?.disconnected]);

  const nextAction = computeNextAction(locale, status, health, gsc, niche);

  return (
    <Page
      title={t(locale, "onboarding")}
      backAction={{
        content: t(locale, "backDashboard"),
        url: localizedPath("/app", locale),
      }}
    >
      <BlockStack gap="400">
        {nextAction && (
          <Banner
            tone="info"
            title={locale === "fr" ? "Prochaine étape recommandée" : "Recommended next step"}
          >
            <Text as="p">{nextAction.label}</Text>
          </Banner>
        )}

        {actionData?.authorizationUrl && (
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
                url={actionData.authorizationUrl}
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

        <GuidedOnboardingFlow locale={locale} gsc={gsc} niche={niche} />

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
                <AuditLauncherCard locale={locale} recentJobs={recentJobs} actionData={actionData} />
              </InlineGrid>

              <GoogleSearchConsoleCard locale={locale} gsc={gsc} actionData={actionData} />
              <PageSpeedCard locale={locale} pagespeed={pagespeed} />
              <CrawlCard locale={locale} crawl={crawl} actionData={actionData} />
            </BlockStack>
          </div>
        </details>
      </BlockStack>
    </Page>
  );
}
