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

interface LongtailRow {
  keyword: string;
  category: string;
  status: "ranking" | "on_site" | "gap";
  position: number | null;
  impressions: number;
  clicks: number;
  site_page: string | null;
  opportunity_score: number;
  recommendation: string;
}

interface LongtailData {
  available: boolean;
  total: number;
  gsc_connected: boolean;
  summary: { ranking: number; on_site: number; gap: number };
  rows: LongtailRow[];
}

interface LoaderData {
  locale: Locale;
  data: LongtailData | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let data: LongtailData | null = null;
  let error: string | null = null;

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/audit/longtail?top=100`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) {
      data = (await resp.json()) as LongtailData;
    } else if (resp.status === 404) {
      error = "Données manquantes. Lancez un audit SEO et connectez Google Search Console.";
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

const STATUS_TONE: Record<string, "success" | "warning" | "critical"> = {
  ranking: "success",
  on_site: "warning",
  gap: "critical",
};

const STATUS_LABEL: Record<string, string> = {
  ranking: "Ranking",
  on_site: "Sur site",
  gap: "Gap",
};

const STATUSES = ["ranking", "on_site", "gap"] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Longtail() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const [activeStatus, setActiveStatus] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const rows = data?.rows ?? [];
  const categories = [...new Set(rows.map((r) => r.category))].sort();

  const filtered = rows.filter((r) => {
    if (activeStatus && r.status !== activeStatus) return false;
    if (activeCategory && r.category !== activeCategory) return false;
    return true;
  });

  return (
    <Page
      title="Longue traîne"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        {/* Summary */}
        {data && (
          <Card>
            <BlockStack gap="300">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">Couverture mots-clés</Text>
                <Text as="span" tone="subdued" variant="bodySm">
                  {data.gsc_connected ? "GSC connectée" : "Sans données GSC"}
                </Text>
              </InlineStack>
              <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="300">
                <BlockStack gap="100">
                  <Text as="p" variant="headingLg" alignment="center">
                    {`${data.summary.ranking}`}
                  </Text>
                  <Text as="p" tone="subdued" alignment="center">Ranking</Text>
                </BlockStack>
                <BlockStack gap="100">
                  <Text as="p" variant="headingLg" alignment="center">
                    {`${data.summary.on_site}`}
                  </Text>
                  <Text as="p" tone="subdued" alignment="center">Sur site sans trafic</Text>
                </BlockStack>
                <BlockStack gap="100">
                  <Text as="p" variant="headingLg" alignment="center">
                    {`${data.summary.gap}`}
                  </Text>
                  <Text as="p" tone="subdued" alignment="center">Gaps (contenu manquant)</Text>
                </BlockStack>
              </InlineGrid>
              {!data.gsc_connected && (
                <Text as="p" tone="subdued" variant="bodySm">
                  Connectez Google Search Console dans l&apos;Onboarding pour enrichir l&apos;analyse avec les positions et impressions réelles.
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

        {/* Filters + list */}
        {data && (
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                {`Mots-clés (${filtered.length}${filtered.length !== rows.length ? ` / ${rows.length}` : ""})`}
              </Text>

              {/* Status filters */}
              <BlockStack gap="200">
                <Text as="p" variant="bodySm" tone="subdued">Statut</Text>
                <InlineStack gap="200" wrap>
                  <Button size="slim" pressed={activeStatus === null} onClick={() => setActiveStatus(null)}>
                    {`Tous (${rows.length})`}
                  </Button>
                  {STATUSES.map((s) =>
                    (data.summary[s] ?? 0) > 0 ? (
                      <Button
                        key={s}
                        size="slim"
                        pressed={activeStatus === s}
                        tone={s === "gap" ? "critical" : undefined}
                        onClick={() => setActiveStatus(activeStatus === s ? null : s)}
                      >
                        {`${STATUS_LABEL[s]} (${data.summary[s]})`}
                      </Button>
                    ) : null
                  )}
                </InlineStack>
              </BlockStack>

              {/* Category filters */}
              {categories.length > 1 && (
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm" tone="subdued">Catégorie</Text>
                  <InlineStack gap="200" wrap>
                    <Button size="slim" pressed={activeCategory === null} onClick={() => setActiveCategory(null)}>
                      Toutes
                    </Button>
                    {categories.map((cat) => (
                      <Button
                        key={cat}
                        size="slim"
                        pressed={activeCategory === cat}
                        onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                      >
                        {cat.replace(/_/g, " ")}
                      </Button>
                    ))}
                  </InlineStack>
                </BlockStack>
              )}

              {/* Rows */}
              {filtered.length === 0 ? (
                <Text as="p" tone="subdued">Aucun mot-clé correspondant aux filtres.</Text>
              ) : (
                <BlockStack gap="300">
                  {filtered.map((row, idx) => (
                    <BlockStack key={`${row.keyword}-${idx}`} gap="100">
                      <InlineStack align="space-between" wrap>
                        <InlineStack gap="200" wrap>
                          <Badge tone={STATUS_TONE[row.status]}>
                            {STATUS_LABEL[row.status]}
                          </Badge>
                          <Text as="span" fontWeight="semibold">{row.keyword}</Text>
                          <Text as="span" tone="subdued" variant="bodySm">
                            {row.category.replace(/_/g, " ")}
                          </Text>
                        </InlineStack>
                        <InlineStack gap="300">
                          {row.position !== null && (
                            <Text as="span" tone="subdued" variant="bodySm">
                              {`pos. ${row.position}`}
                            </Text>
                          )}
                          {row.impressions > 0 && (
                            <Text as="span" tone="subdued" variant="bodySm">
                              {`${row.impressions} imp.`}
                            </Text>
                          )}
                          {row.clicks > 0 && (
                            <Text as="span" tone="subdued" variant="bodySm">
                              {`${row.clicks} clics`}
                            </Text>
                          )}
                        </InlineStack>
                      </InlineStack>
                      <Text as="p" tone="subdued" variant="bodySm">
                        {row.recommendation}
                      </Text>
                      {row.site_page && (
                        <Text as="p" tone="subdued" variant="bodySm">
                          {row.site_page}
                        </Text>
                      )}
                      {idx < filtered.length - 1 && (
                        <div style={{ borderTop: "1px solid var(--p-color-border)", marginTop: 4 }} />
                      )}
                    </BlockStack>
                  ))}
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
