import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
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

interface ResourceRow {
  resource_type: "organization" | "product" | "collection";
  resource_id: string | number;
  handle?: string;
  title: string;
  valid: boolean;
  missing_fields: string[];
  jsonld: Record<string, unknown>;
}

interface StatusData {
  shop: string;
  available: boolean;
  total: number;
  valid: number;
  invalid: number;
  extension_note: string;
  resources: ResourceRow[];
}

interface LoaderData {
  locale: Locale;
  status: StatusData | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/jsonld/status`, {
      accessToken: session.accessToken,
    });
    if (!resp.ok) {
      const msg = await resp.text();
      return json<LoaderData>({ locale, status: null, error: msg });
    }
    const status = (await resp.json()) as StatusData;
    return json<LoaderData>({ locale, status, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, status: null, error: String(err) });
  }
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type Tab = "organization" | "product" | "collection";

function JsonldPreview({ data }: { data: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  return (
    <Box>
      <Button size="slim" variant="plain" onClick={() => setOpen((v) => !v)}>
        {open ? "Masquer le JSON-LD" : "Voir le JSON-LD"}
      </Button>
      {open && (
        <Box paddingBlockStart="200">
          <pre
            style={{
              background: "#f4f6f8",
              padding: "12px",
              borderRadius: 4,
              fontSize: 12,
              overflowX: "auto",
              whiteSpace: "pre-wrap",
            }}
          >
            {JSON.stringify(data, null, 2)}
          </pre>
        </Box>
      )}
    </Box>
  );
}

function ResourceCard({ row }: { row: ResourceRow }) {
  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack align="space-between" blockAlign="center">
          <BlockStack gap="050">
            <Text as="p" variant="bodyMd" fontWeight="semibold">
              {row.title}
            </Text>
            {row.handle && (
              <Text as="p" variant="bodySm" tone="subdued">
                /{row.resource_type === "product" ? "products" : "collections"}/{row.handle}
              </Text>
            )}
          </BlockStack>
          <Badge tone={row.valid ? "success" : "critical"}>
            {row.valid ? "Valide" : `Invalide (${row.missing_fields.join(", ")})`}
          </Badge>
        </InlineStack>
        <JsonldPreview data={row.jsonld} />
      </BlockStack>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function JsonLd() {
  const { locale, status, error } = useLoaderData<typeof loader>();
  const [tab, setTab] = useState<Tab>("organization");

  const tabs: { key: Tab; label: string }[] = [
    { key: "organization", label: "Organisation" },
    { key: "product", label: "Produits" },
    { key: "collection", label: "Collections" },
  ];

  const filtered = status?.resources.filter((r) => r.resource_type === tab) ?? [];

  return (
    <Page
      title="JSON-LD Structured Data"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        {/* Explainer */}
        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">Données structurées Schema.org</Text>
            <Text as="p" tone="subdued" variant="bodySm">
              Prévisualisez et validez les balises JSON-LD pour chaque ressource de votre boutique.
              Activez le Theme App Extension pour les injecter automatiquement sur votre vitrine.
            </Text>
          </BlockStack>
        </Card>

        {/* Extension activation banner */}
        {status && (
          <Banner tone="info">
            <Text as="p" variant="bodySm">{status.extension_note}</Text>
          </Banner>
        )}

        {/* Error */}
        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {/* Summary */}
        {status && (
          <Card>
            <InlineStack gap="600">
              <BlockStack gap="050">
                <Text as="p" variant="headingLg">{status.total}</Text>
                <Text as="p" tone="subdued" variant="bodySm">Ressources total</Text>
              </BlockStack>
              <BlockStack gap="050">
                <Text as="p" variant="headingLg" tone="success">{status.valid}</Text>
                <Text as="p" tone="subdued" variant="bodySm">Valides</Text>
              </BlockStack>
              <BlockStack gap="050">
                <Text as="p" variant="headingLg" tone="critical">{status.invalid}</Text>
                <Text as="p" tone="subdued" variant="bodySm">Invalides</Text>
              </BlockStack>
            </InlineStack>
          </Card>
        )}

        {/* Tab navigation */}
        {status && (
          <Card>
            <BlockStack gap="400">
              <InlineStack gap="200">
                {tabs.map(({ key, label }) => {
                  const count = status.resources.filter((r) => r.resource_type === key).length;
                  return (
                    <Button
                      key={key}
                      variant={tab === key ? "primary" : "plain"}
                      onClick={() => setTab(key)}
                    >
                      {`${label} (${count})`}
                    </Button>
                  );
                })}
              </InlineStack>

              {filtered.length === 0 ? (
                <Text as="p" tone="subdued">
                  {status.available
                    ? "Aucune ressource dans cette catégorie."
                    : t(locale, "noData")}
                </Text>
              ) : (
                <BlockStack gap="300">
                  {filtered.map((row) => (
                    <ResourceCard key={`${row.resource_type}-${row.resource_id}`} row={row} />
                  ))}
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        )}

        {!status && !error && (
          <Card>
            <Text as="p" tone="subdued">
              Aucun snapshot disponible. Lancez un audit SEO pour générer les données JSON-LD.
            </Text>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
