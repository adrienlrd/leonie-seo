import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useActionData, useLoaderData } from "@remix-run/react";
import { useEffect, useRef } from "react";
import { Banner, BlockStack, InlineGrid, Page, Text } from "@shopify/polaris";
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

  const [health, status, jobs, gsc, pagespeed, crawl] = await Promise.all([
    fetchOk<Health>(callBackend("/health")),
    fetchOk<ShopStatus>(be(`/api/shops/${shop}/status`)),
    fetchOk<{ count: number }>(be(`/api/shops/${shop}/jobs?limit=10`)),
    fetchOk<GSCStatus>(be(`/api/shops/${shop}/gsc/status`)),
    fetchOk<PageSpeedStatus>(be(`/api/shops/${shop}/pagespeed/status`)),
    fetchOk<CrawlStatus>(be(`/api/shops/${shop}/crawl/status`)),
  ]);

  return json<LoaderData>({
    locale,
    shop,
    health,
    status,
    gsc,
    pagespeed,
    crawl,
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
  pagespeed: PageSpeedStatus | null,
  crawl: CrawlStatus | null,
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
      label: fr ? "Connecter Google Search Console" : "Connect Google Search Console",
    };
  }
  if (!pagespeed?.available) {
    return {
      label: fr ? "Lancer une analyse performance" : "Run performance analysis",
    };
  }
  if (!crawl?.available) {
    return { label: fr ? "Importer un crawl technique" : "Import technical crawl" };
  }
  return null;
}

export default function Onboarding() {
  const { locale, shop, health, status, gsc, pagespeed, crawl, recentJobs } =
    useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const openedGscUrl = useRef<string | null>(null);

  useEffect(() => {
    const url = actionData?.authorizationUrl;
    if (url && url !== openedGscUrl.current) {
      openedGscUrl.current = url;
      window.open(url, "_blank", "noopener,noreferrer");
    }
  }, [actionData?.authorizationUrl]);

  const nextAction = computeNextAction(locale, status, health, gsc, pagespeed, crawl);

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
    </Page>
  );
}
