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

interface CannibalRow {
  query: string;
  primary_url: string;
  primary_position: number;
  primary_type: string;
  cannibal_url: string;
  cannibal_position: number;
  cannibal_type: string;
  position_gap: number;
  severity: number;
  recommendation: string;
}

interface CannibalData {
  available: boolean;
  total: number;
  summary: { high: number; medium: number; low: number };
  rows: CannibalRow[];
  message?: string;
}

interface LoaderData {
  locale: Locale;
  data: CannibalData | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let data: CannibalData | null = null;
  let error: string | null = null;

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/audit/cannibalization?top=100`,
      { accessToken: session.accessToken },
    );
    if (resp.ok) {
      data = (await resp.json()) as CannibalData;
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

function severityTone(severity: number): "critical" | "warning" | "success" {
  if (severity >= 0.6) return "critical";
  if (severity >= 0.3) return "warning";
  return "success";
}

function severityLabel(severity: number): string {
  if (severity >= 0.6) return "Haute";
  if (severity >= 0.3) return "Moyenne";
  return "Faible";
}

function shortUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.pathname;
  } catch {
    return url;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Cannibalization() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const [activeSeverity, setActiveSeverity] = useState<"high" | "medium" | "low" | null>(null);

  const rows = data?.rows ?? [];

  const filtered = rows.filter((r) => {
    if (activeSeverity === "high" && r.severity < 0.6) return false;
    if (activeSeverity === "medium" && (r.severity < 0.3 || r.severity >= 0.6)) return false;
    if (activeSeverity === "low" && r.severity >= 0.3) return false;
    return true;
  });

  return (
    <Page
      title="Cannibalisation"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        {/* Summary */}
        {data?.available && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">Requêtes cannibalisées</Text>
              <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="300">
                <BlockStack gap="100">
                  <Text as="p" variant="headingLg" alignment="center" tone="critical">
                    {`${data.summary.high}`}
                  </Text>
                  <Text as="p" tone="subdued" alignment="center">Haute sévérité</Text>
                </BlockStack>
                <BlockStack gap="100">
                  <Text as="p" variant="headingLg" alignment="center">
                    {`${data.summary.medium}`}
                  </Text>
                  <Text as="p" tone="subdued" alignment="center">Sévérité moyenne</Text>
                </BlockStack>
                <BlockStack gap="100">
                  <Text as="p" variant="headingLg" alignment="center">
                    {`${data.summary.low}`}
                  </Text>
                  <Text as="p" tone="subdued" alignment="center">Faible sévérité</Text>
                </BlockStack>
              </InlineGrid>
            </BlockStack>
          </Card>
        )}

        {/* Not available */}
        {data && !data.available && (
          <Card>
            <Text as="p" tone="subdued">{data.message}</Text>
          </Card>
        )}

        {/* Error */}
        {error && (
          <Card>
            <Text as="p" tone="subdued">{error}</Text>
          </Card>
        )}

        {/* Filters + list */}
        {data?.available && rows.length > 0 && (
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                {`Paires cannibalisées (${filtered.length}${filtered.length !== rows.length ? ` / ${rows.length}` : ""})`}
              </Text>

              {/* Severity filters */}
              <InlineStack gap="200" wrap>
                <Button size="slim" pressed={activeSeverity === null} onClick={() => setActiveSeverity(null)}>
                  {`Toutes (${rows.length})`}
                </Button>
                {data.summary.high > 0 && (
                  <Button
                    size="slim"
                    pressed={activeSeverity === "high"}
                    tone="critical"
                    onClick={() => setActiveSeverity(activeSeverity === "high" ? null : "high")}
                  >
                    {`Haute (${data.summary.high})`}
                  </Button>
                )}
                {data.summary.medium > 0 && (
                  <Button
                    size="slim"
                    pressed={activeSeverity === "medium"}
                    onClick={() => setActiveSeverity(activeSeverity === "medium" ? null : "medium")}
                  >
                    {`Moyenne (${data.summary.medium})`}
                  </Button>
                )}
                {data.summary.low > 0 && (
                  <Button
                    size="slim"
                    pressed={activeSeverity === "low"}
                    onClick={() => setActiveSeverity(activeSeverity === "low" ? null : "low")}
                  >
                    {`Faible (${data.summary.low})`}
                  </Button>
                )}
              </InlineStack>

              {/* Rows */}
              {filtered.length === 0 ? (
                <Text as="p" tone="subdued">Aucune paire correspondant aux filtres.</Text>
              ) : (
                <BlockStack gap="400">
                  {filtered.map((row, idx) => (
                    <BlockStack key={`${row.query}-${idx}`} gap="200">
                      <InlineStack align="space-between" wrap>
                        <InlineStack gap="200" wrap>
                          <Badge tone={severityTone(row.severity)}>
                            {severityLabel(row.severity)}
                          </Badge>
                          <Text as="span" fontWeight="semibold">{row.query}</Text>
                        </InlineStack>
                        <Text as="span" tone="subdued" variant="bodySm">
                          {`Écart : ${row.position_gap} positions`}
                        </Text>
                      </InlineStack>

                      <InlineGrid columns={["oneHalf", "oneHalf"]} gap="200">
                        <BlockStack gap="050">
                          <Text as="p" variant="bodySm" fontWeight="semibold">Principale</Text>
                          <Text as="p" variant="bodySm">{shortUrl(row.primary_url)}</Text>
                          <Text as="p" variant="bodySm" tone="subdued">
                            {`pos. ${row.primary_position} · ${row.primary_type}`}
                          </Text>
                        </BlockStack>
                        <BlockStack gap="050">
                          <Text as="p" variant="bodySm" fontWeight="semibold">Cannibale</Text>
                          <Text as="p" variant="bodySm">{shortUrl(row.cannibal_url)}</Text>
                          <Text as="p" variant="bodySm" tone="subdued">
                            {`pos. ${row.cannibal_position} · ${row.cannibal_type}`}
                          </Text>
                        </BlockStack>
                      </InlineGrid>

                      <Text as="p" tone="subdued" variant="bodySm">
                        {row.recommendation}
                      </Text>

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
