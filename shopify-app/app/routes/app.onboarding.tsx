import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useActionData, useLoaderData, useNavigation, useSubmit } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackend, callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface ShopStatus {
  installed: boolean;
  snapshot_available: boolean;
  product_count: number;
  collection_count: number;
  plan: string;
  can_apply: boolean;
}

interface Health {
  status: string;
  missing_env: string[];
}

interface GSCStatus {
  configured: boolean;
  connected: boolean;
  site_url: string;
  latest_import: {
    available: boolean;
    row_count: number;
    imported_at: string | null;
  };
  action_required: string | null;
}

interface PageSpeedAlert {
  url: string;
  strategy: string;
  performance_score: number | null;
  lcp_ms: number | null;
  cls: number | null;
  severity: string;
  recommendations: string[];
}

interface PageSpeedStatus {
  configured: boolean;
  available: boolean;
  row_count: number;
  url_count: number;
  imported_at: string | null;
  mobile_average: number | null;
  desktop_average: number | null;
  targets: string[];
  alerts: PageSpeedAlert[];
}

interface LoaderData {
  locale: Locale;
  shop: string;
  health: Health | null;
  status: ShopStatus | null;
  gsc: GSCStatus | null;
  pagespeed: PageSpeedStatus | null;
  recentJobs: number;
}

interface ActionData {
  jobId?: string;
  authorizationUrl?: string;
  error?: string;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let health: Health | null = null;
  let status: ShopStatus | null = null;
  let gsc: GSCStatus | null = null;
  let pagespeed: PageSpeedStatus | null = null;
  let recentJobs = 0;

  try {
    const resp = await callBackend("/health");
    if (resp.ok) health = (await resp.json()) as Health;
  } catch {
    health = null;
  }

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/status`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) status = (await resp.json()) as ShopStatus;
  } catch {
    status = null;
  }

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/jobs?limit=10`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) {
      const data = (await resp.json()) as { count: number };
      recentJobs = data.count;
    }
  } catch {
    recentJobs = 0;
  }

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/gsc/status`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) gsc = (await resp.json()) as GSCStatus;
  } catch {
    gsc = null;
  }

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/pagespeed/status`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) pagespeed = (await resp.json()) as PageSpeedStatus;
  } catch {
    pagespeed = null;
  }

  return json<LoaderData>({ locale, shop, health, status, gsc, pagespeed, recentJobs });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const form = await request.formData();
  const intent = String(form.get("intent") || "audit");
  try {
    if (intent === "gsc_connect") {
      const resp = await callBackendForShop(shop, `/api/shops/${shop}/gsc/authorize`, {
        method: "POST",
        accessToken: session.accessToken,
      });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { authorization_url: string };
      return json<ActionData>({ authorizationUrl: data.authorization_url });
    }

    if (intent === "gsc_import") {
      const resp = await callBackendForShop(shop, `/api/shops/${shop}/gsc/import`, {
        method: "POST",
        accessToken: session.accessToken,
        body: JSON.stringify({ days: 90 }),
      });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { job_id: string };
      return json<ActionData>({ jobId: data.job_id });
    }

    if (intent === "pagespeed_import") {
      const resp = await callBackendForShop(shop, `/api/shops/${shop}/pagespeed/import`, {
        method: "POST",
        accessToken: session.accessToken,
        body: JSON.stringify({ max_urls: 5 }),
      });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { job_id: string };
      return json<ActionData>({ jobId: data.job_id });
    }

    const resp = await callBackendForShop(shop, "/api/jobs", {
      method: "POST",
      accessToken: session.accessToken,
      body: JSON.stringify({ queue: "seo_audit" }),
    });
    if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
    const data = (await resp.json()) as { job_id: string };
    return json<ActionData>({ jobId: data.job_id });
  } catch {
    return json<ActionData>({ error: t(locale, "backendOffline") });
  }
};

function Step({
  label,
  done,
  detail,
}: {
  label: string;
  done: boolean;
  detail?: string;
}) {
  return (
    <InlineStack align="space-between" gap="300">
      <BlockStack gap="050">
        <Text as="span" fontWeight="bold">
          {label}
        </Text>
        {detail && (
          <Text as="span" tone="subdued" variant="bodySm">
            {detail}
          </Text>
        )}
      </BlockStack>
      <Badge tone={done ? "success" : "warning"}>{done ? "OK" : "TODO"}</Badge>
    </InlineStack>
  );
}

export default function Onboarding() {
  const { locale, shop, health, status, gsc, pagespeed, recentJobs } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();
  const submit = useSubmit();

  return (
    <Page title={t(locale, "onboarding")} backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}>
      <BlockStack gap="400">
        <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                {t(locale, "installation")}
              </Text>
              <Step label={t(locale, "shopify")} done={Boolean(status?.installed)} detail={shop} />
              <Step
                label={t(locale, "backend")}
                done={health?.status === "ok"}
                detail={health?.missing_env?.length ? health.missing_env.join(", ") : "ok"}
              />
              <Step
                label={t(locale, "crawl")}
                done={Boolean(status?.snapshot_available)}
                detail={`${status?.product_count ?? 0} ${t(locale, "products")}`}
              />
              <Step
                label={t(locale, "billing")}
                done={Boolean(status?.plan)}
                detail={status?.plan ?? "free"}
              />
              <Step
                label="Google Search Console"
                done={Boolean(gsc?.connected && gsc.latest_import.available)}
                detail={
                  gsc?.connected
                    ? `${gsc.site_url} · ${gsc.latest_import.row_count ?? 0} lignes`
                    : gsc?.action_required ?? "Connexion requise"
                }
              />
              <Step
                label="PageSpeed / Core Web Vitals"
                done={Boolean(pagespeed?.available)}
                detail={
                  pagespeed?.available
                    ? `${pagespeed.url_count} URL(s) · mobile ${Math.round((pagespeed.mobile_average ?? 0) * 100)}%`
                    : "Analyse performance à lancer"
                }
              />
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                {t(locale, "jobs")}
              </Text>
              <Text as="p" variant="headingLg">
                {recentJobs}
              </Text>
              <Button
                variant="primary"
                loading={navigation.state !== "idle"}
                onClick={() => submit({}, { method: "post" })}
              >
                {t(locale, "launchAudit")}
              </Button>
              {actionData?.jobId && (
                <Text as="p" tone="success">
                  {t(locale, "jobQueued")} {actionData.jobId.slice(0, 8)}
                </Text>
              )}
              {actionData?.error && (
                <Text as="p" tone="critical">
                  {actionData.error}
                </Text>
              )}
            </BlockStack>
          </Card>
        </InlineGrid>

        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between">
              <Text as="h2" variant="headingMd">
                Google Search Console
              </Text>
              <Badge tone={gsc?.connected ? "success" : "warning"}>
                {gsc?.connected ? "Connectée" : "À connecter"}
              </Badge>
            </InlineStack>
            <Text as="p" tone="subdued">
              {gsc?.site_url ?? "Propriété Search Console non configurée"}
            </Text>
            <InlineStack gap="300">
              <Button
                disabled={!gsc?.configured}
                onClick={() => submit({ intent: "gsc_connect" }, { method: "post" })}
              >
                Connecter GSC
              </Button>
              <Button
                variant="primary"
                disabled={!gsc?.connected}
                loading={navigation.state !== "idle"}
                onClick={() => submit({ intent: "gsc_import" }, { method: "post" })}
              >
                Importer 90 jours
              </Button>
            </InlineStack>
            {actionData?.authorizationUrl && (
              <Text as="p">
                <a href={actionData.authorizationUrl} target="_blank" rel="noreferrer">
                  Ouvrir le consentement Google
                </a>
              </Text>
            )}
            {gsc?.latest_import.available && (
              <Text as="p" tone="subdued">
                Dernier import: {gsc.latest_import.row_count} lignes
              </Text>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between">
              <Text as="h2" variant="headingMd">
                PageSpeed / Core Web Vitals
              </Text>
              <Badge tone={pagespeed?.available ? "success" : "warning"}>
                {pagespeed?.available ? `${pagespeed.url_count} URL(s)` : "À analyser"}
              </Badge>
            </InlineStack>
            <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="300">
              <Text as="p" tone="subdued">
                Mobile: {pagespeed?.mobile_average !== null && pagespeed?.mobile_average !== undefined ? `${Math.round(pagespeed.mobile_average * 100)}%` : "—"}
              </Text>
              <Text as="p" tone="subdued">
                Desktop: {pagespeed?.desktop_average !== null && pagespeed?.desktop_average !== undefined ? `${Math.round(pagespeed.desktop_average * 100)}%` : "—"}
              </Text>
              <Text as="p" tone="subdued">
                Alertes: {pagespeed?.alerts.length ?? 0}
              </Text>
            </InlineGrid>
              <Button
                variant="primary"
                disabled={!pagespeed?.configured}
                loading={navigation.state !== "idle"}
                onClick={() => submit({ intent: "pagespeed_import" }, { method: "post" })}
              >
                Analyser les URLs prioritaires
              </Button>
            {pagespeed && !pagespeed.configured && (
              <Text as="p" tone="critical">
                Clé PageSpeed manquante côté backend.
              </Text>
            )}
            {(pagespeed?.alerts ?? []).slice(0, 3).map((alert) => (
              <BlockStack gap="100" key={`${alert.url}-${alert.strategy}`}>
                <InlineStack gap="200">
                  <Badge tone={alert.severity === "critical" ? "critical" : "warning"}>
                    {alert.strategy}
                  </Badge>
                  <Text as="span" fontWeight="bold">
                    {Math.round((alert.performance_score ?? 0) * 100)}%
                  </Text>
                  <Text as="span" tone="subdued">
                    {alert.url}
                  </Text>
                </InlineStack>
                <Text as="p" tone="subdued">
                  {alert.recommendations[0] ?? "Revoir les éléments les plus lourds de cette page."}
                </Text>
              </BlockStack>
            ))}
            {!pagespeed?.available && (
              <Text as="p" tone="subdued">
                Lancez une analyse pour mesurer mobile/desktop sur les URLs les plus importantes.
              </Text>
            )}
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
