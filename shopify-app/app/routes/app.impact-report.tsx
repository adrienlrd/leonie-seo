import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  DataTable,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface EventScores {
  geo_before: number | null;
  geo_after: number | null;
  geo_delta: number | null;
  seo_before: number | null;
  seo_after: number | null;
  seo_delta: number | null;
}

interface EventGsc {
  impressions_before: number | null;
  impressions_after: number | null;
  impressions_delta: number | null;
  clicks_before: number | null;
  clicks_after: number | null;
  clicks_delta: number | null;
  ctr_before: number | null;
  ctr_after: number | null;
  position_before: number | null;
  position_after: number | null;
}

interface EventGa4 {
  sessions_before: number | null;
  sessions_after: number | null;
  conversions_before: number | null;
  conversions_after: number | null;
  revenue_before: number | null;
  revenue_after: number | null;
}

interface EventReport {
  event_id: number;
  resource_type: string;
  resource_id: string;
  resource_title: string;
  action_type: string;
  applied_at: string;
  scores: EventScores;
  gsc: EventGsc;
  ga4: EventGa4;
  confidence: { score: number; label: string };
  verdict: string;
  verdict_note: string;
  next_recommendation: string;
}

interface ImpactReportData {
  shop: string;
  generated_at: string;
  reports: EventReport[];
  markdown: string;
  summary: {
    total: number;
    by_verdict: Record<string, number>;
  };
}

interface LoaderData {
  shop: string;
  locale: Locale;
  data: ImpactReportData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/geo/impact-report`, {
      accessToken: session.accessToken,
    });

    if (!resp.ok) {
      return json<LoaderData>({
        shop,
        locale,
        data: null,
        error: `HTTP ${resp.status}`,
      });
    }

    const data = (await resp.json()) as ImpactReportData;
    return json<LoaderData>({ shop, locale, data, error: null });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    return json<LoaderData>({ shop, locale, data: null, error: message });
  }
};

const VERDICT_TONES: Record<string, "success" | "warning" | "critical" | undefined> = {
  positif_probable: "success",
  neutre: "warning",
  négatif_possible: "critical",
  inconclusif: undefined,
};

const fmtInt = (v: number | null) => (v === null ? "—" : Math.round(v).toLocaleString("fr-FR"));
const fmtDelta = (v: number | null) => {
  if (v === null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v}`;
};
const fmtPct = (v: number | null) => (v === null ? "—" : `${(v * 100).toFixed(2)}%`);
const fmtPos = (v: number | null) => (v === null ? "—" : v.toFixed(1));
const fmtEur = (v: number | null) => (v === null ? "—" : `${v.toFixed(2)} €`);

export default function ImpactReportPage() {
  const { locale, data, error } = useLoaderData<typeof loader>() as LoaderData;

  if (error || !data) {
    return (
      <Page
        title={t(locale, "impactReportTitle")}
        backAction={{
          content: t(locale, "impactTitle"),
          url: localizedPath("/app/impact", locale),
        }}
      >
        <Banner tone="critical" title={t(locale, "impactError")}>
          <p>{error ?? "Unknown error"}</p>
        </Banner>
      </Page>
    );
  }

  const rows = data.reports.map((r) => {
    const tone = VERDICT_TONES[r.verdict];
    return [
      r.resource_title || r.resource_id,
      r.action_type,
      r.applied_at.slice(0, 10),
      fmtInt(r.scores.geo_before),
      fmtDelta(r.scores.geo_delta),
      fmtInt(r.gsc.impressions_before),
      fmtDelta(r.gsc.impressions_delta),
      fmtPct(r.gsc.ctr_before),
      fmtPos(r.gsc.position_before),
      fmtEur(r.ga4.revenue_after),
      <Badge key={`conf-${r.event_id}`} tone={tone}>
        {r.verdict.replace(/_/g, " ")}
      </Badge>,
      r.next_recommendation,
    ];
  });

  const downloadHref = `data:text/markdown;charset=utf-8,${encodeURIComponent(data.markdown)}`;

  return (
    <Page
      title={t(locale, "impactReportTitle")}
      subtitle={t(locale, "impactReportSubtitle")}
      backAction={{
        content: t(locale, "impactTitle"),
        url: localizedPath("/app/impact", locale),
      }}
      primaryAction={
        <Button
          url={downloadHref}
          download="rapport-impact-geo.md"
          variant="primary"
        >
          {t(locale, "impactReportDownload")}
        </Button>
      }
    >
      <BlockStack gap="400">
        <Card>
          <BlockStack gap="200">
            <InlineStack gap="300">
              <Badge tone="info">
                {`${data.summary.total} ${t(locale, "impactReportEvents")}`}
              </Badge>
              {Object.entries(data.summary.by_verdict)
                .filter(([, count]) => count > 0)
                .map(([verdict, count]) => {
                  const tone = VERDICT_TONES[verdict];
                  return (
                    <Badge key={verdict} tone={tone}>
                      {`${verdict.replace(/_/g, " ")} : ${count}`}
                    </Badge>
                  );
                })}
            </InlineStack>
            <Text as="p" tone="subdued">
              {t(locale, "impactGenerated")}:{" "}
              {data.generated_at.slice(0, 19).replace("T", " ")}
            </Text>
          </BlockStack>
        </Card>

        {data.reports.length === 0 ? (
          <Card>
            <Text as="p" tone="subdued">
              {t(locale, "impactReportEmpty")}
            </Text>
          </Card>
        ) : (
          <Card>
            <DataTable
              columnContentTypes={[
                "text",
                "text",
                "text",
                "numeric",
                "numeric",
                "numeric",
                "numeric",
                "text",
                "text",
                "text",
                "text",
                "text",
              ]}
              headings={[
                t(locale, "impactColResource"),
                t(locale, "impactColType"),
                t(locale, "impactColAppliedAt"),
                t(locale, "impactReportGeoScore"),
                t(locale, "impactReportGeoDelta"),
                t(locale, "impactImpressions"),
                t(locale, "impactReportImpDelta"),
                t(locale, "impactCtr"),
                t(locale, "impactPosition"),
                t(locale, "impactRevenue"),
                t(locale, "impactReportVerdict"),
                t(locale, "impactReportRec"),
              ]}
              rows={rows}
            />
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
