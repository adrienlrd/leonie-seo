import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Form, useLoaderData } from "@remix-run/react";
import { useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  InlineStack,
  List,
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface CompetitorCandidate {
  domain: string;
  visible_url: string;
  visibility_source: string;
  likely_strengths: string[];
  review_checklist: string[];
}

interface MatchingProduct {
  product_id: string;
  title: string;
  handle: string;
  readiness_score: number;
}

interface MonitoredQuery {
  query: string;
  page: string;
  clicks: number;
  impressions: number;
  position: number;
  intent: string;
  matching_products: MatchingProduct[];
  competitors: CompetitorCandidate[];
  recommended_action: {
    action_type: string;
    label: string;
    reason: string;
  };
  copy_policy: string;
}

interface CompetitorData {
  shop: string;
  available: boolean;
  gsc_query_page_connected: boolean;
  total: number;
  summary: {
    queries_monitored: number;
    competitor_domains: number;
    gsc_query_rows: number;
    dry_run: boolean;
    note: string;
  };
  competitor_domains: string[];
  queries: MonitoredQuery[];
}

interface LoaderData {
  locale: Locale;
  competitors: string;
  data: CompetitorData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const url = new URL(request.url);
  const competitors = url.searchParams.get("competitors") || "";

  try {
    const params = new URLSearchParams({ competitors, top: "10" });
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/competitors?${params.toString()}`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, competitors, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, competitors, data: (await resp.json()) as CompetitorData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, competitors, data: null, error: String(err) });
  }
};

function QueryCard({ query }: { query: MonitoredQuery }) {
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{query.query}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{`${query.impressions} impressions · position ${query.position || "n/a"} · ${query.intent}`}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge tone="info">{query.recommended_action.label}</Badge>
            <Badge tone="attention">Dry-run</Badge>
          </InlineStack>
        </InlineStack>

        <Text as="p" variant="bodySm">{query.recommended_action.reason}</Text>
        <Text as="p" variant="bodySm" tone="subdued">{query.copy_policy}</Text>

        {query.matching_products.length > 0 && (
          <BlockStack gap="100">
            <Text as="h3" variant="headingSm">Pages Léonie candidates</Text>
            <InlineStack gap="100" wrap>
              {query.matching_products.map((product) => (
                <Badge key={product.product_id || product.handle} tone={product.readiness_score >= 60 ? "success" : "warning"}>
                  {`${product.title} · ${product.readiness_score}/100`}
                </Badge>
              ))}
            </InlineStack>
          </BlockStack>
        )}

        {query.competitors.length > 0 && (
          <BlockStack gap="200">
            <Text as="h3" variant="headingSm">Concurrents à auditer</Text>
            {query.competitors.map((competitor) => (
              <BlockStack key={`${query.query}-${competitor.domain}`} gap="100">
                <InlineStack gap="100" blockAlign="center" wrap>
                  <Badge tone="critical">{competitor.domain}</Badge>
                  <Text as="p" variant="bodySm" tone="subdued">{competitor.visible_url}</Text>
                </InlineStack>
                <List type="bullet">
                  {competitor.likely_strengths.map((strength) => (
                    <List.Item key={strength}>{strength}</List.Item>
                  ))}
                </List>
              </BlockStack>
            ))}
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}

export default function GeoCompetitors() {
  const { locale, competitors, data, error } = useLoaderData<typeof loader>();
  const [value, setValue] = useState(competitors);

  return (
    <Page
      title={t(locale, "geoCompetitors")}
      subtitle={locale === "fr" ? "Monitoring léger des concurrents visibles sur les requêtes conversationnelles" : "Light competitor monitoring for conversational queries"}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/content-hub", locale) }}
    >
      <BlockStack gap="400">
        <Card>
          <Form method="get">
            <BlockStack gap="300">
              <TextField
                label="Domaines concurrents"
                name="competitors"
                value={value}
                onChange={setValue}
                autoComplete="off"
                placeholder="miacara.com,zara.com"
              />
              <InlineStack align="end">
                <Button submit variant="primary">Analyser</Button>
              </InlineStack>
            </BlockStack>
          </Form>
        </Card>

        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {data && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
              {[
                { label: "Requêtes", value: String(data.summary.queries_monitored) },
                { label: "Concurrents", value: String(data.summary.competitor_domains) },
                { label: "Lignes GSC", value: String(data.summary.gsc_query_rows) },
                { label: "Mode", value: data.summary.dry_run ? "Dry-run" : "Live" },
              ].map((item) => (
                <Card key={item.label}>
                  <BlockStack gap="050">
                    <Text as="p" variant="headingLg">{item.value}</Text>
                    <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
                  </BlockStack>
                </Card>
              ))}
            </div>

            <Banner tone="info">
              <Text as="p">{data.summary.note}</Text>
            </Banner>

            <BlockStack gap="300">
              {data.queries.map((query) => (
                <QueryCard key={query.query} query={query} />
              ))}
            </BlockStack>

            {!data.queries.length && (
              <Banner tone="warning">
                <Text as="p">{t(locale, "noData")}</Text>
              </Banner>
            )}
          </>
        )}
      </BlockStack>
    </Page>
  );
}
