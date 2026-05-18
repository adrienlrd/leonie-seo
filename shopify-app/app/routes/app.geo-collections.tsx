import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Card,
  InlineStack,
  List,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface CollectionProduct {
  id: string;
  title: string;
  handle: string;
}

interface CollectionSuggestion {
  suggested_title: string;
  handle: string;
  intent: string;
  cluster_name: string;
  keywords: string[];
  source_queries: string[];
  product_count: number;
  products: CollectionProduct[];
  estimated_impressions: number;
  estimated_clicks: number;
  opportunity_score: number;
  preview: {
    h1: string;
    seo_title: string;
    meta_description: string;
    description: string;
    faq_questions: string[];
  };
  dry_run: boolean;
  warnings: string[];
}

interface CollectionsData {
  shop: string;
  available: boolean;
  gsc_query_page_connected: boolean;
  total: number;
  summary: {
    suggested_collections: number;
    total_estimated_impressions: number;
    gsc_query_rows: number;
    dry_run: boolean;
    note: string;
  };
  suggestions: CollectionSuggestion[];
}

interface LoaderData {
  locale: Locale;
  data: CollectionsData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/collections?top=10&min_products=2`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as CollectionsData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function scoreTone(score: number): "success" | "warning" | "critical" {
  if (score >= 70) return "success";
  if (score >= 40) return "warning";
  return "critical";
}

function SuggestionCard({ suggestion }: { suggestion: CollectionSuggestion }) {
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{suggestion.suggested_title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{`/collections/${suggestion.handle}`}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge tone={scoreTone(suggestion.opportunity_score)}>{`${suggestion.opportunity_score} opportunité`}</Badge>
            <Badge tone="info">{suggestion.intent}</Badge>
            <Badge tone="attention">Dry-run</Badge>
          </InlineStack>
        </InlineStack>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
          {[
            { label: "Produits", value: String(suggestion.product_count) },
            { label: "Impressions", value: String(suggestion.estimated_impressions) },
            { label: "Clics", value: String(suggestion.estimated_clicks) },
            { label: "Cluster", value: suggestion.cluster_name },
          ].map((item) => (
            <BlockStack key={item.label} gap="050">
              <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
              <Text as="p" variant="bodyMd" fontWeight="semibold">{item.value}</Text>
            </BlockStack>
          ))}
        </div>

        {suggestion.source_queries.length > 0 && (
          <InlineStack gap="100" wrap>
            {suggestion.source_queries.map((query) => (
              <Badge key={query}>{query}</Badge>
            ))}
          </InlineStack>
        )}

        {suggestion.warnings.length > 0 && (
          <Banner tone="warning">
            <List type="bullet">
              {suggestion.warnings.map((warning) => (
                <List.Item key={warning}>{warning}</List.Item>
              ))}
            </List>
          </Banner>
        )}

        <BlockStack gap="150">
          <Text as="h3" variant="headingSm">Preview</Text>
          <Text as="p" variant="bodyMd" fontWeight="semibold">{suggestion.preview.h1}</Text>
          <Text as="p" variant="bodySm">{suggestion.preview.seo_title}</Text>
          <Text as="p" variant="bodySm" tone="subdued">{suggestion.preview.meta_description}</Text>
          <Text as="p" variant="bodySm">{suggestion.preview.description}</Text>
        </BlockStack>

        <BlockStack gap="100">
          <Text as="h3" variant="headingSm">Produits inclus</Text>
          <List type="bullet">
            {suggestion.products.map((product) => (
              <List.Item key={product.id || product.handle}>{`${product.title} · /${product.handle}`}</List.Item>
            ))}
          </List>
        </BlockStack>

        <BlockStack gap="100">
          <Text as="h3" variant="headingSm">Questions candidates</Text>
          <List type="bullet">
            {suggestion.preview.faq_questions.map((question) => (
              <List.Item key={question}>{question}</List.Item>
            ))}
          </List>
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

export default function GeoCollections() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoCollections")}
      subtitle={locale === "fr" ? "Suggestions de collections Shopify pour intentions conversationnelles" : "Shopify collection suggestions for conversational intents"}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/content-hub", locale) }}
    >
      <BlockStack gap="400">
        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {data && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
              {[
                { label: "Collections", value: String(data.summary.suggested_collections) },
                { label: "Impressions", value: String(data.summary.total_estimated_impressions) },
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
              {data.suggestions.map((suggestion) => (
                <SuggestionCard key={suggestion.handle} suggestion={suggestion} />
              ))}
            </BlockStack>

            {!data.suggestions.length && (
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
