import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Form, useActionData, useLoaderData, useNavigation, useSubmit } from "@remix-run/react";
import { useEffect, useRef, useState } from "react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackend, callBackendForShop, callBackendMultipartForShop } from "../lib/api.server";
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
  email: string | null;
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
  key_source: "env" | "db" | null;
  available: boolean;
  row_count: number;
  url_count: number;
  imported_at: string | null;
  mobile_average: number | null;
  desktop_average: number | null;
  targets: string[];
  alerts: PageSpeedAlert[];
}

interface CrawlIssue {
  url: string;
  issue_type: string;
  severity: string;
  detail: string;
}

interface CrawlStatus {
  available: boolean;
  url_count: number;
  issue_count: number;
  by_severity: Record<string, number>;
  issues: CrawlIssue[];
  imported_at: string | null;
}

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
  let crawl: CrawlStatus | null = null;
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

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/crawl/status`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) crawl = (await resp.json()) as CrawlStatus;
  } catch {
    crawl = null;
  }

  return json<LoaderData>({ locale, shop, health, status, gsc, pagespeed, crawl, recentJobs });
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

    if (intent === "pagespeed_configure") {
      const apiKey = String(form.get("pagespeed_api_key") || "").trim();
      if (!apiKey) return json<ActionData>({ error: "Clé API manquante." });
      const resp = await callBackendForShop(shop, `/api/shops/${shop}/pagespeed/configure`, {
        method: "POST",
        accessToken: session.accessToken,
        body: JSON.stringify({ api_key: apiKey }),
      });
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      return json<ActionData>({ jobId: "Clé PageSpeed enregistrée." });
    }

    if (intent === "crawl_upload") {
      const overviewFile = form.get("overview");
      if (!overviewFile || !(overviewFile instanceof File) || overviewFile.size === 0) {
        return json<ActionData>({ error: "Fichier overview CSV manquant." });
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
      if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
      const data = (await resp.json()) as { url_count: number; issue_count: number };
      return json<ActionData>({ jobId: `Crawl: ${data.url_count} URLs · ${data.issue_count} issues` });
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
  const { locale, shop, health, status, gsc, pagespeed, crawl, recentJobs } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();
  const submit = useSubmit();
  const [psApiKey, setPsApiKey] = useState("");
  const openedGscUrl = useRef<string | null>(null);

  useEffect(() => {
    const url = actionData?.authorizationUrl;
    if (url && url !== openedGscUrl.current) {
      openedGscUrl.current = url;
      window.open(url, "_blank", "noopener,noreferrer");
    }
  }, [actionData?.authorizationUrl]);

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
              <Step
                label="Crawl technique"
                done={Boolean(crawl?.available)}
                detail={
                  crawl?.available
                    ? `${crawl.url_count} URLs · ${crawl.issue_count} issue(s)`
                    : "Exporter un CSV Screaming Frog et l'importer"
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
              <Text as="h2" variant="headingMd">Google Search Console</Text>
              <Badge tone={gsc?.connected ? "success" : "warning"}>
                {gsc?.connected ? "Connectée" : "À connecter"}
              </Badge>
            </InlineStack>

            {gsc?.connected ? (
              <BlockStack gap="100">
                <Text as="p" tone="subdued">
                  {`Compte : ${gsc.email ?? "—"}`}
                </Text>
                <Text as="p" tone="subdued">
                  {`Propriété : ${gsc.site_url ?? "—"}`}
                </Text>
                {gsc.latest_import.available && (
                  <Text as="p" tone="subdued">
                    {`Dernier import : ${gsc.latest_import.row_count} lignes`}
                  </Text>
                )}
              </BlockStack>
            ) : (
              <BlockStack gap="100">
                <Text as="p" tone="subdued">
                  Connectez votre compte Google pour importer vos données de recherche (requêtes, impressions, positions).
                </Text>
                {!gsc?.configured && (
                  <Text as="p" tone="critical" variant="bodySm">
                    OAuth Google non configuré côté backend (GOOGLE_OAUTH_CLIENT_CONFIG manquant).
                  </Text>
                )}
              </BlockStack>
            )}

            <InlineStack gap="300" wrap>
              {!gsc?.connected && (
                <Button
                  variant="primary"
                  disabled={!gsc?.configured}
                  loading={navigation.state !== "idle"}
                  onClick={() => submit({ intent: "gsc_connect" }, { method: "post" })}
                >
                  Connecter Google Search Console
                </Button>
              )}
              <Button
                disabled={!gsc?.connected}
                loading={navigation.state !== "idle"}
                onClick={() => submit({ intent: "gsc_import" }, { method: "post" })}
              >
                {gsc?.latest_import.available ? "Réimporter 90 jours" : "Importer 90 jours"}
              </Button>
            </InlineStack>

            {actionData?.authorizationUrl && (
              <Text as="p" tone="subdued" variant="bodySm">
                Une fenêtre Google s&apos;est ouverte. Si elle est bloquée,{" "}
                <a href={actionData.authorizationUrl} target="_blank" rel="noreferrer">
                  cliquez ici
                </a>.
              </Text>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between">
              <Text as="h2" variant="headingMd">PageSpeed / Core Web Vitals</Text>
              <Badge tone={pagespeed?.available ? "success" : "warning"}>
                {pagespeed?.available ? `${pagespeed.url_count} URL(s)` : "À analyser"}
              </Badge>
            </InlineStack>

            {/* Key status */}
            {pagespeed?.configured ? (
              <Text as="p" tone="subdued" variant="bodySm">
                {`Clé API configurée (source : ${pagespeed.key_source ?? "env"}) — quota élevé actif.`}
              </Text>
            ) : (
              <BlockStack gap="200">
                <Text as="p" tone="subdued">
                  L&apos;analyse fonctionne sans clé (quota réduit). Pour un usage régulier, ajoutez
                  une clé gratuite depuis{" "}
                  <a
                    href="https://developers.google.com/speed/docs/insights/v5/get-started"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Google Cloud Console
                  </a>{" "}
                  (API PageSpeed Insights → Créer une clé).
                </Text>
                <Form method="post">
                  <input type="hidden" name="intent" value="pagespeed_configure" />
                  <BlockStack gap="200">
                    <TextField
                      label="Clé API PageSpeed (optionnelle)"
                      value={psApiKey}
                      onChange={setPsApiKey}
                      name="pagespeed_api_key"
                      type="password"
                      autoComplete="off"
                      placeholder="AIzaSy…"
                    />
                    <Button submit disabled={psApiKey.trim().length === 0} loading={navigation.state !== "idle"}>
                      Enregistrer la clé
                    </Button>
                  </BlockStack>
                </Form>
              </BlockStack>
            )}

            {/* Scores */}
            {pagespeed?.available && (
              <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="300">
                <Text as="p" tone="subdued">
                  {`Mobile : ${pagespeed.mobile_average !== null && pagespeed.mobile_average !== undefined ? `${Math.round(pagespeed.mobile_average * 100)}%` : "—"}`}
                </Text>
                <Text as="p" tone="subdued">
                  {`Desktop : ${pagespeed.desktop_average !== null && pagespeed.desktop_average !== undefined ? `${Math.round(pagespeed.desktop_average * 100)}%` : "—"}`}
                </Text>
                <Text as="p" tone="subdued">
                  {`Alertes : ${pagespeed.alerts.length}`}
                </Text>
              </InlineGrid>
            )}

            <Button
              variant="primary"
              loading={navigation.state !== "idle"}
              onClick={() => submit({ intent: "pagespeed_import" }, { method: "post" })}
            >
              {pagespeed?.available ? "Réanalyser les URLs prioritaires" : "Analyser les URLs prioritaires"}
            </Button>

            {(pagespeed?.alerts ?? []).slice(0, 3).map((alert) => (
              <BlockStack gap="100" key={`${alert.url}-${alert.strategy}`}>
                <InlineStack gap="200">
                  <Badge tone={alert.severity === "critical" ? "critical" : "warning"}>
                    {alert.strategy}
                  </Badge>
                  <Text as="span" fontWeight="bold">
                    {`${Math.round((alert.performance_score ?? 0) * 100)}%`}
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

        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between">
              <Text as="h2" variant="headingMd">
                Crawl technique
              </Text>
              <Badge tone={crawl?.available ? "success" : "warning"}>
                {crawl?.available ? `${crawl.url_count} URLs` : "À importer"}
              </Badge>
            </InlineStack>
            <Text as="p" tone="subdued">
              Importez un export CSV Screaming Frog (vue «&nbsp;Internal&nbsp;») pour détecter les
              404, chaînes de redirection, canonicals et titres dupliqués.
            </Text>
            {crawl?.available && (
              <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="300">
                <Text as="p" tone="subdued">
                  Issues: {crawl.issue_count}
                </Text>
                <Text as="p" tone="subdued">
                  Critiques: {crawl.by_severity?.critical ?? 0}
                </Text>
                <Text as="p" tone="subdued">
                  Hautes: {crawl.by_severity?.high ?? 0}
                </Text>
              </InlineGrid>
            )}
            {(crawl?.issues ?? []).filter((i) => i.severity === "critical").slice(0, 3).map((issue) => (
              <BlockStack gap="100" key={issue.url + issue.issue_type}>
                <InlineStack gap="200">
                  <Badge tone="critical">{issue.issue_type.replace(/_/g, " ")}</Badge>
                  <Text as="span" tone="subdued">{issue.url}</Text>
                </InlineStack>
                <Text as="p" tone="subdued">{issue.detail}</Text>
              </BlockStack>
            ))}
            <Form method="post" encType="multipart/form-data">
              <input type="hidden" name="intent" value="crawl_upload" />
              <BlockStack gap="200">
                <Text as="p" variant="bodySm">
                  Overview CSV (obligatoire — export «&nbsp;Internal&nbsp;» Screaming Frog)
                </Text>
                <input type="file" name="overview" accept=".csv" />
                <Text as="p" variant="bodySm">
                  CSV codes réponse (optionnel — export «&nbsp;Response Codes&nbsp;» Screaming Frog)
                </Text>
                <input type="file" name="redirects" accept=".csv" />
                <Button submit variant="primary" loading={navigation.state !== "idle"}>
                  Analyser le crawl
                </Button>
              </BlockStack>
            </Form>
            {actionData?.error && (
              <Text as="p" tone="critical">{actionData.error}</Text>
            )}
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
