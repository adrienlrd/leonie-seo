import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Box,
  Card,
  IndexTable,
  InlineGrid,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface ProductCluster {
  name: string;
  size: number;
  keywords: string[];
  product_titles: string[];
}

interface KeywordGap {
  query: string;
  impressions: number;
  clicks: number;
  position: number;
  cluster_name: string | null;
  saturation: string;
  opportunity_score: number;
}

interface IntentCluster {
  name: string;
  intent: string;
  total_impressions: number;
  avg_position: number;
  top_keywords: string[];
}

interface SignalKeyword {
  keyword: string;
  source: string;
  context: string;
  relevance_score: number;
}

interface NicheReport {
  clusters: ProductCluster[];
  keyword_gaps: KeywordGap[];
  intent_clusters: IntentCluster[];
  entity_summary: Record<string, Record<string, number>>;
  total_products: number;
  total_queries: number;
}

interface LoaderData {
  locale: Locale;
  report: NicheReport | null;
  signals: SignalKeyword[];
  error?: string;
}

async function safeBackendJson<T>(
  shop: string,
  path: string,
  fallback: T,
  options?: RequestInit
): Promise<T> {
  const resp = await callBackendForShop(shop, path, options);
  if (!resp.ok) {
    return fallback;
  }
  return (await resp.json()) as T;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const report = await safeBackendJson<NicheReport | null>(
      shop,
      `/api/shops/${shop}/niche/report`,
      null
    );
    const seeds = [
      ...(report?.keyword_gaps ?? []).slice(0, 3).map((gap) => gap.query),
      ...(report?.clusters ?? []).slice(0, 2).map((cluster) => cluster.name),
    ].filter(Boolean);
    const signals =
      seeds.length > 0
        ? await safeBackendJson<SignalKeyword[]>(
            shop,
            `/api/shops/${shop}/niche/signals`,
            [],
            {
              method: "POST",
              body: JSON.stringify({ seeds, sources: ["google_suggest"], geo: "FR" }),
            }
          )
        : [];
    return json<LoaderData>({ locale, report, signals });
  } catch {
    return json<LoaderData>({
      locale,
      report: null,
      signals: [],
      error: t(locale, "backendOffline"),
    });
  }
};

function scoreTone(score: number): "success" | "warning" | "critical" {
  if (score >= 0.7) return "success";
  if (score >= 0.4) return "warning";
  return "critical";
}

function topEntity(summary: Record<string, Record<string, number>>): string {
  const entries = Object.entries(summary).flatMap(([group, values]) =>
    Object.entries(values).map(([term, count]) => ({ group, term, count }))
  );
  entries.sort((a, b) => b.count - a.count);
  return entries[0] ? `${entries[0].term} (${entries[0].group})` : "—";
}

export default function Niche() {
  const { locale, report, signals, error } = useLoaderData<typeof loader>();

  const clusterRows = (report?.clusters ?? []).slice(0, 8).map((cluster, index) => (
    <IndexTable.Row id={cluster.name} key={cluster.name} position={index}>
      <IndexTable.Cell>
        <Text as="span" fontWeight="bold">
          {cluster.name}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>{cluster.size}</IndexTable.Cell>
      <IndexTable.Cell>{cluster.keywords.slice(0, 6).join(", ")}</IndexTable.Cell>
    </IndexTable.Row>
  ));

  const gapRows = (report?.keyword_gaps ?? []).slice(0, 8).map((gap, index) => (
    <IndexTable.Row id={gap.query} key={gap.query} position={index}>
      <IndexTable.Cell>
        <Text as="span" fontWeight="bold">
          {gap.query}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>{gap.impressions}</IndexTable.Cell>
      <IndexTable.Cell>{gap.position.toFixed(1)}</IndexTable.Cell>
      <IndexTable.Cell>
        <Badge tone={scoreTone(gap.opportunity_score)}>{gap.opportunity_score.toFixed(2)}</Badge>
      </IndexTable.Cell>
    </IndexTable.Row>
  ));

  const intentRows = (report?.intent_clusters ?? []).slice(0, 6).map((intent, index) => (
    <IndexTable.Row id={intent.name} key={intent.name} position={index}>
      <IndexTable.Cell>
        <Badge tone="info">{intent.intent}</Badge>
      </IndexTable.Cell>
      <IndexTable.Cell>{intent.total_impressions}</IndexTable.Cell>
      <IndexTable.Cell>{intent.avg_position.toFixed(1)}</IndexTable.Cell>
      <IndexTable.Cell>{intent.top_keywords.slice(0, 5).join(", ")}</IndexTable.Cell>
    </IndexTable.Row>
  ));

  return (
    <Page title={t(locale, "niche")} backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}>
      <BlockStack gap="400">
        {error && (
          <Card>
            <Text as="p" tone="critical">
              {error}
            </Text>
          </Card>
        )}

        <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="400">
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {t(locale, "products")}
              </Text>
              <Text as="p" variant="headingLg">
                {report?.total_products ?? 0}
              </Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {t(locale, "query")}
              </Text>
              <Text as="p" variant="headingLg">
                {report?.total_queries ?? 0}
              </Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                NER
              </Text>
              <Text as="p">{topEntity(report?.entity_summary ?? {})}</Text>
            </BlockStack>
          </Card>
        </InlineGrid>

        <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                {t(locale, "clusters")}
              </Text>
              {clusterRows.length === 0 ? (
                <Box padding="200">
                  <Text as="p" tone="subdued">
                    {t(locale, "noData")}
                  </Text>
                </Box>
              ) : (
                <IndexTable
                  resourceName={{ singular: "cluster", plural: "clusters" }}
                  itemCount={clusterRows.length}
                  headings={[
                    { title: t(locale, "clusters") },
                    { title: t(locale, "size") },
                    { title: t(locale, "keywords") },
                  ]}
                  selectable={false}
                >
                  {clusterRows}
                </IndexTable>
              )}
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                {t(locale, "gaps")}
              </Text>
              {gapRows.length === 0 ? (
                <Box padding="200">
                  <Text as="p" tone="subdued">
                    {t(locale, "noData")}
                  </Text>
                </Box>
              ) : (
                <IndexTable
                  resourceName={{ singular: "gap", plural: "gaps" }}
                  itemCount={gapRows.length}
                  headings={[
                    { title: t(locale, "query") },
                    { title: t(locale, "impressions") },
                    { title: t(locale, "position") },
                    { title: t(locale, "opportunity") },
                  ]}
                  selectable={false}
                >
                  {gapRows}
                </IndexTable>
              )}
            </BlockStack>
          </Card>
        </InlineGrid>

        <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                {t(locale, "intents")}
              </Text>
              {intentRows.length === 0 ? (
                <Text as="p" tone="subdued">
                  {t(locale, "noData")}
                </Text>
              ) : (
                <IndexTable
                  resourceName={{ singular: "intent", plural: "intents" }}
                  itemCount={intentRows.length}
                  headings={[
                    { title: "Intent" },
                    { title: t(locale, "impressions") },
                    { title: t(locale, "position") },
                    { title: t(locale, "keywords") },
                  ]}
                  selectable={false}
                >
                  {intentRows}
                </IndexTable>
              )}
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">
                  {t(locale, "signals")}
                </Text>
                <Badge tone="info">Google Suggest</Badge>
              </InlineStack>
              <BlockStack gap="200">
                {signals.length === 0 ? (
                  <Text as="p" tone="subdued">
                    {t(locale, "noData")}
                  </Text>
                ) : (
                  signals.slice(0, 10).map((signal) => (
                    <InlineStack key={`${signal.source}-${signal.keyword}`} align="space-between">
                      <Text as="span">{signal.keyword}</Text>
                      <Badge tone="success">{signal.relevance_score.toFixed(2)}</Badge>
                    </InlineStack>
                  ))
                )}
              </BlockStack>
            </BlockStack>
          </Card>
        </InlineGrid>
      </BlockStack>
    </Page>
  );
}
