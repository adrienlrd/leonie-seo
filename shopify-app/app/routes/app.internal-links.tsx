import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { useState } from "react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
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

interface OpportunityRow {
  source_keyword: string;
  source_category: string;
  target_type: "product" | "collection";
  target_title: string;
  target_url: string;
  anchor_text: string;
  relevance_score: number;
}

interface OrphanRow {
  title: string;
  url: string;
  handle: string;
  recommendation: string;
}

interface InternalLinksData {
  available: boolean;
  total_opportunities: number;
  total_orphans: number;
  gsc_connected: boolean;
  summary: { product_links: number; collection_links: number; orphans: number };
  opportunities: OpportunityRow[];
  orphans: OrphanRow[];
}

interface LoaderData {
  locale: Locale;
  data: InternalLinksData | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let data: InternalLinksData | null = null;
  let error: string | null = null;

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/audit/internal-links?top=100`,
      { accessToken: session.accessToken },
    );
    if (resp.ok) {
      data = (await resp.json()) as InternalLinksData;
    } else if (resp.status === 404) {
      error = "Données manquantes. Lancez un audit SEO et configurez keywords.yaml.";
    } else {
      error = `Erreur backend : ${resp.status}`;
    }
  } catch {
    error = t(locale, "backendOffline");
  }

  return json<LoaderData>({ locale, data, error });
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function shortUrl(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

const TYPE_TONE: Record<string, "info" | "success"> = {
  product: "success",
  collection: "info",
};

const TYPE_LABEL: Record<string, string> = {
  product: "Produit",
  collection: "Collection",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function InternalLinks() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const [activeTab, setActiveTab] = useState<"opportunities" | "orphans">("opportunities");
  const [activeType, setActiveType] = useState<"product" | "collection" | null>(null);

  const opportunities = data?.opportunities ?? [];
  const orphans = data?.orphans ?? [];

  const filteredOpportunities = opportunities.filter((r) => {
    if (activeType && r.target_type !== activeType) return false;
    return true;
  });

  return (
    <Page
      title="Maillage interne"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        {/* Summary */}
        {data?.available && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">Vue d&apos;ensemble</Text>
              <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="300">
                <BlockStack gap="100">
                  <Text as="p" variant="headingLg" alignment="center">
                    {`${data.total_opportunities}`}
                  </Text>
                  <Text as="p" tone="subdued" alignment="center">Opportunités de liens</Text>
                </BlockStack>
                <BlockStack gap="100">
                  <Text as="p" variant="headingLg" alignment="center">
                    {`${data.summary.orphans}`}
                  </Text>
                  <Text as="p" tone="subdued" alignment="center">Pages orphelines</Text>
                </BlockStack>
                <BlockStack gap="100">
                  <Text as="p" variant="headingLg" alignment="center" tone={data.gsc_connected ? "success" : "subdued"}>
                    {data.gsc_connected ? "Connectée" : "—"}
                  </Text>
                  <Text as="p" tone="subdued" alignment="center">Google Search Console</Text>
                </BlockStack>
              </InlineGrid>
              {!data.gsc_connected && (
                <Text as="p" tone="subdued" variant="bodySm">
                  Sans GSC, les pages orphelines ne peuvent pas être détectées. Connectez Google Search Console dans l&apos;Onboarding.
                </Text>
              )}
            </BlockStack>
          </Card>
        )}

        {/* Error */}
        {error && (
          <Card>
            <Text as="p" tone="subdued">{error}</Text>
          </Card>
        )}

        {/* Tabs */}
        {data?.available && (
          <>
            <InlineStack gap="200">
              <Button
                pressed={activeTab === "opportunities"}
                onClick={() => setActiveTab("opportunities")}
              >
                {`Opportunités (${data.total_opportunities})`}
              </Button>
              <Button
                pressed={activeTab === "orphans"}
                onClick={() => setActiveTab("orphans")}
                tone={data.total_orphans > 0 ? "critical" : undefined}
              >
                {`Pages orphelines (${data.total_orphans})`}
              </Button>
            </InlineStack>

            {/* Opportunities */}
            {activeTab === "opportunities" && (
              <Card>
                <BlockStack gap="400">
                  <Text as="h2" variant="headingMd">
                    {`Liens suggérés (${filteredOpportunities.length}${filteredOpportunities.length !== opportunities.length ? ` / ${opportunities.length}` : ""})`}
                  </Text>

                  {/* Type filters */}
                  <InlineStack gap="200" wrap>
                    <Button size="slim" pressed={activeType === null} onClick={() => setActiveType(null)}>
                      {`Tous (${opportunities.length})`}
                    </Button>
                    {data.summary.product_links > 0 && (
                      <Button
                        size="slim"
                        pressed={activeType === "product"}
                        onClick={() => setActiveType(activeType === "product" ? null : "product")}
                      >
                        {`Produits (${data.summary.product_links})`}
                      </Button>
                    )}
                    {data.summary.collection_links > 0 && (
                      <Button
                        size="slim"
                        pressed={activeType === "collection"}
                        onClick={() => setActiveType(activeType === "collection" ? null : "collection")}
                      >
                        {`Collections (${data.summary.collection_links})`}
                      </Button>
                    )}
                  </InlineStack>

                  {filteredOpportunities.length === 0 ? (
                    <Text as="p" tone="subdued">Aucune opportunité correspondant aux filtres.</Text>
                  ) : (
                    <BlockStack gap="300">
                      {filteredOpportunities.map((row, idx) => (
                        <BlockStack key={`${row.source_keyword}-${row.target_url}`} gap="100">
                          <InlineStack align="space-between" wrap>
                            <InlineStack gap="200" wrap>
                              <Badge tone={TYPE_TONE[row.target_type]}>
                                {TYPE_LABEL[row.target_type]}
                              </Badge>
                              <Text as="span" fontWeight="semibold">{row.source_keyword}</Text>
                            </InlineStack>
                            <Text as="span" tone="subdued" variant="bodySm">
                              {`score ${row.relevance_score}`}
                            </Text>
                          </InlineStack>
                          <InlineStack gap="100" wrap>
                            <Text as="span" tone="subdued" variant="bodySm">→</Text>
                            <Text as="span" variant="bodySm">{row.target_title}</Text>
                            <Text as="span" tone="subdued" variant="bodySm">
                              {shortUrl(row.target_url)}
                            </Text>
                          </InlineStack>
                          <Text as="p" tone="subdued" variant="bodySm">
                            {`Ancre suggérée : "${row.anchor_text}"`}
                          </Text>
                          {idx < filteredOpportunities.length - 1 && (
                            <div style={{ borderTop: "1px solid var(--p-color-border)", marginTop: 4 }} />
                          )}
                        </BlockStack>
                      ))}
                    </BlockStack>
                  )}
                </BlockStack>
              </Card>
            )}

            {/* Orphans */}
            {activeTab === "orphans" && (
              <Card>
                <BlockStack gap="400">
                  <Text as="h2" variant="headingMd">Pages orphelines</Text>
                  {orphans.length === 0 ? (
                    <Text as="p" tone="subdued">
                      {data.gsc_connected
                        ? "Aucune page orpheline détectée."
                        : "Connectez Google Search Console pour détecter les pages sans trafic."}
                    </Text>
                  ) : (
                    <BlockStack gap="300">
                      {orphans.map((orphan, idx) => (
                        <BlockStack key={orphan.handle} gap="100">
                          <Text as="p" fontWeight="semibold">{orphan.title}</Text>
                          <Text as="p" tone="subdued" variant="bodySm">{shortUrl(orphan.url)}</Text>
                          <Text as="p" tone="subdued" variant="bodySm">{orphan.recommendation}</Text>
                          {idx < orphans.length - 1 && (
                            <div style={{ borderTop: "1px solid var(--p-color-border)", marginTop: 4 }} />
                          )}
                        </BlockStack>
                      ))}
                    </BlockStack>
                  )}
                </BlockStack>
              </Card>
            )}
          </>
        )}
      </BlockStack>
    </Page>
  );
}
