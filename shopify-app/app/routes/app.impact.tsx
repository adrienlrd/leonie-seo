import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  DataTable,
  InlineGrid,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { Sparkline } from "../components/Sparkline";

interface SeriesPoint {
  date: string;
  value: number;
}

interface ImpactPoint {
  date: string;
  estimated: number;
  observed: number;
}

interface ProgressCurve {
  shop: string;
  window_days: number;
  generated_at: string;
  series: {
    geo_score: SeriesPoint[];
    seo_score: SeriesPoint[];
    impressions: SeriesPoint[];
    clicks: SeriesPoint[];
    ctr: SeriesPoint[];
    position: SeriesPoint[];
    sessions: SeriesPoint[];
    conversions: SeriesPoint[];
    revenue: SeriesPoint[];
    impact_estimated_vs_observed: ImpactPoint[];
  };
  optimizations_in_validation: {
    event_id: number;
    resource_type: string;
    resource_id: string;
    resource_title: string;
    applied_at: string;
    status: string;
    measurement_status: string;
  }[];
  flags: {
    low_volume: boolean;
    incomplete_tracking: boolean;
    out_of_stock_pages: number;
    price_changed_pages: number;
  };
  totals: {
    snapshots_in_window: number;
    events_in_window: number;
    total_impressions: number;
  };
}

interface ConfidenceEntry {
  event_id: number;
  score: number;
  label: string;
}

interface ConfidenceData {
  scores: ConfidenceEntry[];
  summary: {
    total_events: number;
    by_label: Record<string, number>;
    avg_score: number;
  };
}

interface LoaderData {
  shop: string;
  locale: Locale;
  curve: ProgressCurve | null;
  confidence: ConfidenceData | null;
  error: string | null;
}

const CONFIDENCE_TONES: Record<
  string,
  "warning" | "info" | "success" | undefined
> = {
  données_insuffisantes: undefined,
  signal_faible: "warning",
  impact_probable: "info",
  impact_fort: "success",
};

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const be = (path: string) =>
    callBackendForShop(shop, path, { accessToken: session.accessToken });

  try {
    const [curveResp, confResp] = await Promise.allSettled([
      be(`/api/shops/${shop}/geo/progress-curve?days=90`),
      be(`/api/shops/${shop}/geo/confidence-scores`),
    ]);

    if (
      curveResp.status === "rejected" ||
      !curveResp.value.ok
    ) {
      const status =
        curveResp.status === "fulfilled"
          ? `HTTP ${curveResp.value.status}`
          : curveResp.reason?.message ?? "Network error";
      return json<LoaderData>({
        shop,
        locale,
        curve: null,
        confidence: null,
        error: status,
      });
    }

    const curve = (await curveResp.value.json()) as ProgressCurve;
    const confidence =
      confResp.status === "fulfilled" && confResp.value.ok
        ? ((await confResp.value.json()) as ConfidenceData)
        : null;

    return json<LoaderData>({ shop, locale, curve, confidence, error: null });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    return json<LoaderData>({
      shop,
      locale,
      curve: null,
      confidence: null,
      error: message,
    });
  }
};

const fmtInt = (v: number) => Math.round(v).toLocaleString("fr-FR");
const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;
const fmtPos = (v: number) => v.toFixed(1);
const fmtEur = (v: number) => `${v.toFixed(2)} €`;

export default function ImpactPage() {
  const { locale, curve, confidence, error } =
    useLoaderData<typeof loader>() as LoaderData;

  if (error || !curve) {
    return (
      <Page
        title={t(locale, "impactTitle")}
        backAction={{
          content: t(locale, "backDashboard"),
          url: localizedPath("/app/insights", locale),
        }}
      >
        <Banner tone="critical" title={t(locale, "impactError")}>
          <p>{error ?? "Unknown error"}</p>
        </Banner>
      </Page>
    );
  }

  const flagsActive =
    curve.flags.incomplete_tracking ||
    curve.flags.low_volume ||
    curve.flags.out_of_stock_pages > 0 ||
    curve.flags.price_changed_pages > 0;

  // Build a map event_id → confidence entry for the DataTable
  const confByEventId = new Map<number, ConfidenceEntry>(
    (confidence?.scores ?? []).map((entry) => [entry.event_id, entry]),
  );

  const optimRows = curve.optimizations_in_validation.map((opt) => {
    const conf = confByEventId.get(opt.event_id);
    const tone = conf ? CONFIDENCE_TONES[conf.label] : undefined;
    const labelText = conf
      ? `${conf.label.replace(/_/g, " ")} (${conf.score})`
      : "—";
    return [
      opt.resource_title || opt.resource_id,
      opt.resource_type,
      opt.applied_at.slice(0, 10),
      opt.status,
      opt.measurement_status,
      <Badge key={`conf-${opt.event_id}`} tone={tone}>
        {labelText}
      </Badge>,
    ];
  });

  return (
    <Page
      title={t(locale, "impactTitle")}
      subtitle={t(locale, "impactSubtitle")}
      backAction={{
        content: t(locale, "backDashboard"),
        url: localizedPath("/app/insights", locale),
      }}
    >
      <BlockStack gap="400">
        {flagsActive && (
          <Banner tone="warning" title={t(locale, "impactFlagsTitle")}>
            <BlockStack gap="100">
              {curve.flags.incomplete_tracking && (
                <p>{t(locale, "impactFlagIncomplete")}</p>
              )}
              {curve.flags.low_volume && (
                <p>{t(locale, "impactFlagLowVolume")}</p>
              )}
              {curve.flags.out_of_stock_pages > 0 && (
                <p>
                  {t(locale, "impactFlagOos")}: {curve.flags.out_of_stock_pages}
                </p>
              )}
              {curve.flags.price_changed_pages > 0 && (
                <p>
                  {t(locale, "impactFlagPrice")}:{" "}
                  {curve.flags.price_changed_pages}
                </p>
              )}
            </BlockStack>
          </Banner>
        )}

        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">
              {t(locale, "impactScoreCard")}
            </Text>
            <InlineGrid columns={{ xs: 1, md: 2 }} gap="400">
              <Sparkline
                data={curve.series.geo_score}
                label={t(locale, "impactGeoScore")}
                formatValue={fmtInt}
              />
              <Sparkline
                data={curve.series.seo_score}
                label={t(locale, "impactSeoScore")}
                color="#6371c7"
                formatValue={fmtInt}
              />
            </InlineGrid>
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">
              {t(locale, "impactSearchCard")}
            </Text>
            <InlineGrid columns={{ xs: 1, md: 2 }} gap="400">
              <Sparkline
                data={curve.series.impressions}
                label={t(locale, "impactImpressions")}
                formatValue={fmtInt}
              />
              <Sparkline
                data={curve.series.clicks}
                label={t(locale, "impactClicks")}
                color="#1f6feb"
                formatValue={fmtInt}
              />
              <Sparkline
                data={curve.series.ctr}
                label={t(locale, "impactCtr")}
                color="#bf5af2"
                formatValue={fmtPct}
              />
              <Sparkline
                data={curve.series.position}
                label={t(locale, "impactPosition")}
                color="#d97706"
                invertY
                formatValue={fmtPos}
              />
            </InlineGrid>
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">
              {t(locale, "impactGa4Card")}
            </Text>
            <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
              <Sparkline
                data={curve.series.sessions}
                label={t(locale, "impactSessions")}
                formatValue={fmtInt}
              />
              <Sparkline
                data={curve.series.conversions}
                label={t(locale, "impactConversions")}
                color="#6371c7"
                formatValue={fmtInt}
              />
              <Sparkline
                data={curve.series.revenue}
                label={t(locale, "impactRevenue")}
                color="#198038"
                formatValue={fmtEur}
              />
            </InlineGrid>
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">
              {t(locale, "impactValidationCard")}
            </Text>
            <Text as="p" tone="subdued">
              {t(locale, "impactValidationHint")}
            </Text>
            {optimRows.length === 0 ? (
              <Text as="p" tone="subdued">
                {t(locale, "impactValidationEmpty")}
              </Text>
            ) : (
              <DataTable
                columnContentTypes={[
                  "text",
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
                  t(locale, "impactColStatus"),
                  t(locale, "impactColMeasurement"),
                  t(locale, "impactColConfidence"),
                ]}
                rows={optimRows}
              />
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="200">
            <Button url={localizedPath("/app/impact-report", locale)} variant="secondary">
              {t(locale, "impactReportLink")}
            </Button>
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="100">
            <Text as="p" tone="subdued">
              {t(locale, "impactGenerated")}:{" "}
              {curve.generated_at.slice(0, 19).replace("T", " ")}
            </Text>
            <Box>
              <Badge tone="info">
                {`${curve.totals.snapshots_in_window} snapshots`}
              </Badge>{" "}
              <Badge tone="info">
                {`${curve.totals.events_in_window} events`}
              </Badge>{" "}
              <Badge tone="info">
                {`${curve.totals.total_impressions.toLocaleString("fr-FR")} ${t(locale, "impactImpressions").toLowerCase()}`}
              </Badge>
            </Box>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
