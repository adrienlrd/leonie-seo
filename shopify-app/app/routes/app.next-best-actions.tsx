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

interface SuggestedResource {
  resource_id: string;
  resource_title: string;
  resource_type: string;
  similarity_reason: string;
}

interface NextAction {
  source_event_id: number;
  source_resource_id: string;
  source_resource_title: string;
  source_action_type: string;
  verdict: string;
  action_type: string;
  priority: string;
  rationale: string;
  suggested_resources: SuggestedResource[];
  dry_run: boolean;
}

interface NbaSummary {
  total_actions: number;
  high_priority: number;
  by_action: Record<string, number>;
}

interface NbaData {
  actions: NextAction[];
  summary: NbaSummary;
  dry_run: boolean;
  generated_at: string;
}

interface LoaderData {
  shop: string;
  locale: Locale;
  data: NbaData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/next-best-actions`,
      { accessToken: session.accessToken },
    );

    if (!resp.ok) {
      return json<LoaderData>({ shop, locale, data: null, error: `HTTP ${resp.status}` });
    }

    const data = (await resp.json()) as NbaData;
    return json<LoaderData>({ shop, locale, data, error: null });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    return json<LoaderData>({ shop, locale, data: null, error: message });
  }
};

const PRIORITY_TONES: Record<string, "critical" | "warning" | undefined> = {
  high: "critical",
  medium: "warning",
  low: undefined,
};

const ACTION_TONES: Record<string, "success" | "warning" | "critical" | undefined> = {
  répliquer: "success",
  ajuster: "warning",
  rollback: "critical",
  attendre: undefined,
};

export default function NextBestActionsPage() {
  const { locale, data, error } = useLoaderData<typeof loader>() as LoaderData;

  if (error || !data) {
    return (
      <Page
        title={t(locale, "nbaTitle")}
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

  const rows = data.actions.map((a) => {
    const priorityTone = PRIORITY_TONES[a.priority];
    const actionTone = ACTION_TONES[a.action_type];
    const suggestions =
      a.suggested_resources.length > 0
        ? a.suggested_resources.map((s) => s.resource_title).join(", ")
        : "—";
    return [
      a.source_resource_title || a.source_resource_id,
      a.source_action_type,
      <Badge key={`verdict-${a.source_event_id}`} tone={actionTone}>
        {t(locale, `nbaAction_${a.action_type}`)}
      </Badge>,
      <Badge key={`prio-${a.source_event_id}`} tone={priorityTone}>
        {t(locale, `nbaPriority_${a.priority}`)}
      </Badge>,
      suggestions,
      a.rationale,
    ];
  });

  return (
    <Page
      title={t(locale, "nbaTitle")}
      subtitle={t(locale, "nbaSubtitle")}
      backAction={{
        content: t(locale, "impactTitle"),
        url: localizedPath("/app/impact", locale),
      }}
    >
      <BlockStack gap="400">
        <Banner tone="info" title={t(locale, "nbaDryRunTitle")}>
          <p>{t(locale, "nbaDryRunMessage")}</p>
        </Banner>

        <Card>
          <BlockStack gap="200">
            <InlineStack gap="300">
              <Badge tone="info">
                {`${data.summary.total_actions} ${t(locale, "nbaTotal")}`}
              </Badge>
              {data.summary.high_priority > 0 && (
                <Badge tone="critical">
                  {`${data.summary.high_priority} ${t(locale, "nbaHighPriority")}`}
                </Badge>
              )}
            </InlineStack>
            <InlineStack gap="200">
              {Object.entries(data.summary.by_action)
                .filter(([, count]) => count > 0)
                .map(([action, count]) => (
                  <Badge key={action} tone={ACTION_TONES[action]}>
                    {`${t(locale, `nbaAction_${action}`)}: ${count}`}
                  </Badge>
                ))}
            </InlineStack>
          </BlockStack>
        </Card>

        {data.actions.length === 0 ? (
          <Card>
            <Text as="p" tone="subdued">
              {t(locale, "nbaEmpty")}
            </Text>
          </Card>
        ) : (
          <Card>
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
                t(locale, "nbaColAction"),
                t(locale, "nbaColPriority"),
                t(locale, "nbaColSuggestions"),
                t(locale, "nbaColRationale"),
              ]}
              rows={rows}
            />
          </Card>
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
