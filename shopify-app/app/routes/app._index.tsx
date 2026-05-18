import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useActionData, useLoaderData, useSubmit } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Link,
  Page,
  ProgressBar,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface ShopStatus {
  installed: boolean;
  snapshot_available: boolean;
  product_count: number;
  collection_count: number;
  plan: string;
}

interface GSCStatus {
  connected: boolean;
  configured: boolean;
}

interface MerchantAlert {
  type: string;
  severity: "critical" | "error" | "warning" | "info";
  message: string;
  url?: string | null;
}

interface AlertSummary {
  total: number;
  by_severity: Partial<Record<string, number>>;
  alerts: MerchantAlert[];
}

interface Job {
  id: string;
  queue: string;
  status: string;
  created_at: string;
}

interface LoaderData {
  shop: string;
  locale: Locale;
  status: ShopStatus | null;
  gsc: GSCStatus | null;
  alerts: AlertSummary | null;
  jobs: Job[];
  backendOk: boolean;
}

interface ActionData {
  jobId?: string;
  error?: string;
}

async function fetchJson<T>(
  shop: string,
  path: string,
  accessToken: string | undefined
): Promise<T | null> {
  try {
    const r = await callBackendForShop(shop, path, { accessToken });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const [status, gsc, alerts, jobsResp] = await Promise.all([
    fetchJson<ShopStatus>(shop, `/api/shops/${shop}/status`, session.accessToken),
    fetchJson<GSCStatus>(shop, `/api/shops/${shop}/gsc/status`, session.accessToken),
    fetchJson<AlertSummary>(shop, `/api/shops/${shop}/alerts/summary`, session.accessToken),
    fetchJson<{ jobs: Job[] }>(
      shop,
      `/api/shops/${shop}/jobs?limit=3`,
      session.accessToken
    ),
  ]);

  const backendOk = status !== null;

  return json<LoaderData>({
    shop,
    locale,
    status,
    gsc,
    alerts,
    jobs: jobsResp?.jobs ?? [],
    backendOk,
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  try {
    const resp = await callBackendForShop(shop, "/api/jobs", {
      method: "POST",
      accessToken: session.accessToken,
      body: JSON.stringify({ queue: "seo_audit", shop }),
    });
    if (!resp.ok) {
      return json<ActionData>({ error: `Erreur ${resp.status}` });
    }
    const data = (await resp.json()) as { job_id: string };
    return json<ActionData>({ jobId: data.job_id });
  } catch {
    return json<ActionData>({ error: "Service momentanément indisponible." });
  }
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface SetupStep {
  label: string;
  done: boolean;
  cta: string;
  href: string;
}

function buildSetupSteps(
  locale: Locale,
  status: ShopStatus | null,
  gsc: GSCStatus | null
): SetupStep[] {
  const fr = locale === "fr";
  return [
    {
      label: fr ? "Boutique connectée" : "Store connected",
      done: status?.installed ?? false,
      cta: fr ? "Reconnecter" : "Reconnect",
      href: "/app/account",
    },
    {
      label: fr ? "Premier audit SEO lancé" : "First SEO audit run",
      done: status?.snapshot_available ?? false,
      cta: fr ? "Lancer l'audit" : "Run audit",
      href: "/app/audit-hub",
    },
    {
      label: fr ? "Google Search Console relié" : "Google Search Console linked",
      done: gsc?.connected ?? false,
      cta: fr ? "Connecter Google" : "Connect Google",
      href: "/app/onboarding",
    },
    {
      label: fr ? "Abonnement actif" : "Subscription active",
      done: (status?.plan ?? "free") !== "free",
      cta: fr ? "Choisir un plan" : "Choose a plan",
      href: "/app/billing",
    },
  ];
}

const SEV_TONE = {
  critical: "critical" as const,
  error: "critical" as const,
  warning: "warning" as const,
  info: "info" as const,
};

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function SetupCard({
  steps,
  locale,
}: {
  steps: SetupStep[];
  locale: Locale;
}) {
  const done = steps.filter((s) => s.done).length;
  const progress = Math.round((done / steps.length) * 100);
  const fr = locale === "fr";
  const nextStep = steps.find((s) => !s.done);

  return (
    <Card>
      <BlockStack gap="400">
        <BlockStack gap="200">
          <InlineStack align="space-between" blockAlign="center">
            <Text as="h2" variant="headingMd">
              {fr ? "Configuration de votre boutique" : "Store setup"}
            </Text>
            <Badge tone={done === steps.length ? "success" : "attention"}>
              {`${done}/${steps.length}`}
            </Badge>
          </InlineStack>
          <ProgressBar progress={progress} size="small" />
        </BlockStack>

        <BlockStack gap="200">
          {steps.map((step) => (
            <InlineStack key={step.label} align="space-between" blockAlign="center">
              <InlineStack gap="200" blockAlign="center">
                <Badge tone={step.done ? "success" : "attention"}>
                  {step.done
                    ? locale === "fr" ? "Fait" : "Done"
                    : locale === "fr" ? "À faire" : "To do"}
                </Badge>
                <Text as="span">{step.label}</Text>
              </InlineStack>
              {!step.done && (
                <Link url={localizedPath(step.href, locale)} removeUnderline>
                  {step.cta} →
                </Link>
              )}
            </InlineStack>
          ))}
        </BlockStack>

        {nextStep && (
          <Box paddingBlockStart="200">
            <Button
              url={localizedPath(nextStep.href, locale)}
              variant="primary"
              fullWidth
            >
              {nextStep.cta}
            </Button>
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}

function AlertsCard({
  alerts,
  locale,
}: {
  alerts: AlertSummary | null;
  locale: Locale;
}) {
  const fr = locale === "fr";
  const total = alerts?.total ?? 0;
  const top = (alerts?.alerts ?? []).slice(0, 3);
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <Text as="h2" variant="headingMd">
            {fr ? "Alertes prioritaires" : "Top alerts"}
          </Text>
          <Badge tone={total === 0 ? "success" : "attention"}>
            {String(total)}
          </Badge>
        </InlineStack>

        {total === 0 ? (
          <Text as="p" tone="subdued">
            {fr ? "Aucune alerte active. Tout est OK." : "No active alerts. All clear."}
          </Text>
        ) : (
          <BlockStack gap="200">
            {top.map((a, i) => (
              <InlineStack key={i} gap="200" blockAlign="start" wrap={false}>
                <Badge tone={SEV_TONE[a.severity] ?? "info"}>{a.severity}</Badge>
                <Text as="span" variant="bodySm">
                  {a.message}
                </Text>
              </InlineStack>
            ))}
            <Link url={localizedPath("/app/alerts", locale)} removeUnderline>
              {fr ? "Voir toutes les alertes →" : "View all alerts →"}
            </Link>
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}

function ShortcutsCard({ locale }: { locale: Locale }) {
  const fr = locale === "fr";
  const hubs: { titleKey: string; href: string }[] = [
    { titleKey: "hubAudit", href: "/app/audit-hub" },
    { titleKey: "hubOptimization", href: "/app/optimization" },
    { titleKey: "hubContent", href: "/app/content-hub" },
    { titleKey: "hubInsights", href: "/app/insights" },
  ];
  return (
    <Card>
      <BlockStack gap="300">
        <Text as="h2" variant="headingMd">
          {fr ? "Accès rapide" : "Quick access"}
        </Text>
        <InlineGrid columns={{ xs: "1", sm: "2" }} gap="200">
          {hubs.map((h) => (
            <Button key={h.href} url={localizedPath(h.href, locale)} variant="secondary">
              {t(locale, h.titleKey)}
            </Button>
          ))}
        </InlineGrid>
      </BlockStack>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const { shop, locale, status, gsc, alerts, jobs, backendOk } =
    useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const submit = useSubmit();
  const fr = locale === "fr";

  const steps = buildSetupSteps(locale, status, gsc);
  const runningJob = jobs.find((j) => j.status === "running");

  return (
    <Page
      title={fr ? "Tableau de bord" : "Dashboard"}
      subtitle={shop}
      primaryAction={{
        content: fr ? "Lancer un audit SEO" : "Run SEO audit",
        onAction: () => submit({}, { method: "post" }),
        loading: false,
        disabled: !backendOk || !!runningJob,
      }}
    >
      <BlockStack gap="500">
        {!backendOk && (
          <Banner tone="warning" title={t(locale, "systemStatus")}>
            <Text as="p">{t(locale, "systemUnavailable")}</Text>
          </Banner>
        )}

        {actionData?.jobId && (
          <Banner tone="success">
            <Text as="p">
              {fr
                ? `Audit en cours — tâche ${actionData.jobId.slice(0, 8)}…`
                : `Audit running — job ${actionData.jobId.slice(0, 8)}…`}
            </Text>
          </Banner>
        )}

        {actionData?.error && (
          <Banner tone="critical">
            <Text as="p">{actionData.error}</Text>
          </Banner>
        )}

        {runningJob && (
          <Banner tone="info">
            <Text as="p">
              {fr
                ? `Une tâche est en cours d'exécution (${runningJob.queue}).`
                : `A task is currently running (${runningJob.queue}).`}
            </Text>
          </Banner>
        )}

        <InlineGrid columns={{ xs: "1", md: "twoThirds oneThird" }} gap="400">
          <BlockStack gap="400">
            <SetupCard steps={steps} locale={locale} />
            <ShortcutsCard locale={locale} />
          </BlockStack>
          <BlockStack gap="400">
            <AlertsCard alerts={alerts} locale={locale} />
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  {fr ? "Activité récente" : "Recent activity"}
                </Text>
                {jobs.length === 0 ? (
                  <Text as="p" tone="subdued">
                    {fr
                      ? "Aucune tâche récente."
                      : "No recent activity."}
                  </Text>
                ) : (
                  jobs.map((j) => (
                    <InlineStack key={j.id} align="space-between" blockAlign="center">
                      <Text as="span" variant="bodySm">
                        {j.queue}
                      </Text>
                      <Badge
                        tone={
                          j.status === "completed"
                            ? "success"
                            : j.status === "failed"
                            ? "critical"
                            : j.status === "running"
                            ? "info"
                            : "attention"
                        }
                      >
                        {j.status}
                      </Badge>
                    </InlineStack>
                  ))
                )}
                <Link url={localizedPath("/app/jobs", locale)} removeUnderline>
                  {fr ? "Voir toutes les tâches →" : "View all tasks →"}
                </Link>
              </BlockStack>
            </Card>
          </BlockStack>
        </InlineGrid>
      </BlockStack>
    </Page>
  );
}
