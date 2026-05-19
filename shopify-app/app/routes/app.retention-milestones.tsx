import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Card,
  InlineStack,
  Page,
  ProgressBar,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface Milestone {
  label: string;
  days: number;
  due_date: string;
  status: "completed" | "active" | "upcoming";
  events_reached: number;
  total_events: number;
  message_fr: string;
  message_en: string;
}

interface NextMilestone {
  label: string;
  due_date: string;
  days_remaining: number;
}

interface RetentionData {
  has_active_events: boolean;
  active_event_count: number;
  earliest_applied_at?: string;
  elapsed_days?: number;
  milestones: Milestone[];
  next_milestone: NextMilestone | null;
  retention_message_fr: string;
  retention_message_en: string;
  generated_at: string;
}

interface LoaderData {
  shop: string;
  locale: Locale;
  data: RetentionData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/retention-milestones`,
      { accessToken: session.accessToken },
    );

    if (!resp.ok) {
      return json<LoaderData>({
        shop,
        locale,
        data: null,
        error: `HTTP ${resp.status}`,
      });
    }

    const data = (await resp.json()) as RetentionData;
    return json<LoaderData>({ shop, locale, data, error: null });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    return json<LoaderData>({ shop, locale, data: null, error: message });
  }
};

const STATUS_TONES: Record<string, "success" | "warning" | undefined> = {
  completed: "success",
  active: "warning",
  upcoming: undefined,
};

export default function RetentionMilestonesPage() {
  const { locale, data, error } = useLoaderData<typeof loader>() as LoaderData;

  if (error || !data) {
    return (
      <Page
        title={t(locale, "retentionTitle")}
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

  const retentionMessage =
    locale === "fr" ? data.retention_message_fr : data.retention_message_en;

  return (
    <Page
      title={t(locale, "retentionTitle")}
      subtitle={t(locale, "retentionSubtitle")}
      backAction={{
        content: t(locale, "impactTitle"),
        url: localizedPath("/app/impact", locale),
      }}
    >
      <BlockStack gap="400">
        <Banner tone="info" title={t(locale, "retentionWhyTitle")}>
          <p>{retentionMessage}</p>
        </Banner>

        {!data.has_active_events ? (
          <Card>
            <Text as="p" tone="subdued">
              {t(locale, "retentionNoEvents")}
            </Text>
          </Card>
        ) : (
          <>
            <Card>
              <BlockStack gap="200">
                <InlineStack gap="300" align="space-between">
                  <Text as="h2" variant="headingMd">
                    {t(locale, "retentionProgress")}
                  </Text>
                  <Badge tone="info">
                    {`${data.active_event_count} ${t(locale, "retentionEventCount")}`}
                  </Badge>
                </InlineStack>
                {data.elapsed_days !== undefined && (
                  <Text as="p" tone="subdued">
                    {t(locale, "retentionElapsed")}: {data.elapsed_days}{" "}
                    {t(locale, "retentionDays")} ({data.earliest_applied_at})
                  </Text>
                )}
                {data.next_milestone && (
                  <Text as="p">
                    {t(locale, "retentionNext")}:{" "}
                    <strong>{data.next_milestone.label}</strong> —{" "}
                    {data.next_milestone.due_date} (
                    {data.next_milestone.days_remaining}{" "}
                    {t(locale, "retentionDays")})
                  </Text>
                )}
              </BlockStack>
            </Card>

            <BlockStack gap="300">
              {data.milestones.map((m) => {
                const pct =
                  data.active_event_count > 0
                    ? Math.round(
                        (m.events_reached / m.total_events) * 100,
                      )
                    : 0;
                const tone = STATUS_TONES[m.status];
                const msg =
                  locale === "fr" ? m.message_fr : m.message_en;
                return (
                  <Card key={m.label}>
                    <BlockStack gap="200">
                      <InlineStack gap="300" align="space-between">
                        <Text as="h3" variant="headingSm">
                          {m.label}
                        </Text>
                        <InlineStack gap="200">
                          <Badge tone={tone}>
                            {t(locale, `retentionStatus_${m.status}`)}
                          </Badge>
                          <Text as="span" tone="subdued">
                            {m.due_date}
                          </Text>
                        </InlineStack>
                      </InlineStack>
                      <ProgressBar progress={pct} size="small" />
                      <Text as="p" tone="subdued">
                        {m.events_reached} / {m.total_events}{" "}
                        {t(locale, "retentionEventsReached")} — {msg}
                      </Text>
                      <Box />
                    </BlockStack>
                  </Card>
                );
              })}
            </BlockStack>
          </>
        )}

        <Card>
          <Text as="p" tone="subdued">
            {t(locale, "impactGenerated")}:{" "}
            {data.generated_at.slice(0, 19).replace("T", " ")}
          </Text>
        </Card>
      </BlockStack>
    </Page>
  );
}
