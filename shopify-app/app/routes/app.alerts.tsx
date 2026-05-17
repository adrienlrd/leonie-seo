import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Card,
  DataTable,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type AlertSeverity = "critical" | "error" | "warning" | "info";
type AlertType = "cwv" | "crawl_404" | "low_ctr" | "llm_budget" | "job_failed";

interface MerchantAlert {
  type: AlertType;
  severity: AlertSeverity;
  message: string;
  detail?: string;
  url?: string | null;
  job_id?: string;
}

interface AlertSummary {
  shop: string;
  total: number;
  by_severity: Partial<Record<AlertSeverity, number>>;
  alerts: MerchantAlert[];
}

interface LoaderData {
  summary: AlertSummary;
  locale: Locale;
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const res = await callBackendForShop(shop, `/api/shops/${shop}/alerts/summary`, {
    accessToken: session.accessToken,
  });

  const summary: AlertSummary = res.ok
    ? await res.json()
    : { shop, total: 0, by_severity: {}, alerts: [] };

  return json<LoaderData>({ summary, locale });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SEV_TONE: Record<AlertSeverity, "critical" | "warning" | "info"> = {
  critical: "critical",
  error: "critical",
  warning: "warning",
  info: "info",
};

const SEV_LABEL: Record<AlertSeverity, string> = {
  critical: "Critique",
  error: "Erreur",
  warning: "Attention",
  info: "Info",
};

const TYPE_LABEL: Record<AlertType, string> = {
  cwv: "CWV / PageSpeed",
  crawl_404: "404",
  low_ctr: "CTR faible",
  llm_budget: "Budget LLM",
  job_failed: "Job échoué",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AlertsPage() {
  const { summary, locale } = useLoaderData<typeof loader>();

  const rows = summary.alerts.map((alert) => [
    <Badge key="sev" tone={SEV_TONE[alert.severity]}>{SEV_LABEL[alert.severity]}</Badge>,
    TYPE_LABEL[alert.type] ?? alert.type,
    alert.message,
    alert.detail ?? "—",
  ]);

  return (
    <Page
      title={t(locale, "alerts")}
      subtitle={t(locale, "alertsSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        {summary.total === 0 ? (
          <Banner tone="success">
            <Text as="p">{t(locale, "alertsNoIssue")}</Text>
          </Banner>
        ) : (
          <>
            <Card>
              <InlineStack gap="400" blockAlign="center">
                <Text variant="headingMd" as="h2">
                  {summary.total} {t(locale, "alertsTotal")}
                </Text>
                {(Object.entries(summary.by_severity) as [AlertSeverity, number][]).map(
                  ([sev, count]) => (
                    <Badge key={sev} tone={SEV_TONE[sev]}>
                      {`${count} ${SEV_LABEL[sev]}`}
                    </Badge>
                  )
                )}
              </InlineStack>
            </Card>

            <Card>
              <DataTable
                columnContentTypes={["text", "text", "text", "text"]}
                headings={[t(locale, "status"), "Type", "Message", "Détail"]}
                rows={rows}
              />
            </Card>
          </>
        )}

        <Box paddingBlockStart="200">
          <Text as="p" tone="subdued" variant="bodySm">
            Les alertes sont recalculées à chaque chargement depuis les données locales (PageSpeed, crawl, GSC, jobs).
          </Text>
        </Box>
      </BlockStack>
    </Page>
  );
}
