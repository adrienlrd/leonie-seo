import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  InlineStack,
  Page,
  ProgressBar,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface Fact {
  key: string;
  label: string;
  value: string | string[];
  source: string;
  confidence: "confirmed";
}

interface MissingFact {
  key: string;
  label: string;
}

interface Suggestion {
  key: string;
  label: string;
  instruction: string;
}

interface GeoProduct {
  id: string;
  handle: string;
  title: string;
  confirmed_facts: Fact[];
  missing_facts: MissingFact[];
  suggestions_to_verify: Suggestion[];
  completeness_score: number;
  confirmed_count: number;
  missing_count: number;
  safety_note: string;
}

interface GeoFactsData {
  shop: string;
  available: boolean;
  total: number;
  summary: {
    avg_completeness_score: number;
    products_missing_sensitive_facts: number;
    products_ready_for_geo: number;
    safety_note: string;
  };
  products: GeoProduct[];
}

interface LoaderData {
  locale: Locale;
  data: GeoFactsData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/facts?top=100`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as GeoFactsData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function pct(value: number): string {
  return `${Math.round(value * 100)} %`;
}

function scoreTone(value: number): "success" | "primary" | "critical" {
  if (value >= 0.75) return "success";
  if (value >= 0.4) return "primary";
  return "critical";
}

function factValue(value: string | string[]): string {
  return Array.isArray(value) ? value.join(", ") : value;
}

function FactBadges({ facts }: { facts: Fact[] }) {
  const topFacts = facts.filter((fact) => fact.key !== "description").slice(0, 8);
  if (!topFacts.length) {
    return <Text as="p" variant="bodySm" tone="subdued">Aucun fait confirmé exploitable.</Text>;
  }
  return (
    <InlineStack gap="100" wrap>
      {topFacts.map((fact) => (
        <Badge key={`${fact.key}-${fact.label}`} tone="success">
          {`${fact.label}: ${factValue(fact.value)}`}
        </Badge>
      ))}
    </InlineStack>
  );
}

function ProductFactsRow({ product }: { product: GeoProduct }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{product.title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">/{product.handle}</Text>
          </BlockStack>
          <InlineStack gap="200" blockAlign="center">
            <Badge tone={product.completeness_score >= 0.75 ? "success" : product.completeness_score >= 0.4 ? "warning" : "critical"}>
              {pct(product.completeness_score)}
            </Badge>
            <Badge tone="info">{`${product.confirmed_count} faits`}</Badge>
            <Badge tone={product.missing_count ? "warning" : "success"}>
              {`${product.missing_count} manquants`}
            </Badge>
          </InlineStack>
        </InlineStack>

        <ProgressBar
          progress={Math.min(product.completeness_score * 100, 100)}
          size="small"
          tone={scoreTone(product.completeness_score)}
        />

        <FactBadges facts={product.confirmed_facts} />

        {expanded && (
          <BlockStack gap="200">
            {product.missing_facts.length > 0 && (
              <BlockStack gap="100">
                <Text as="h3" variant="headingSm">Faits à vérifier</Text>
                <InlineStack gap="100" wrap>
                  {product.missing_facts.map((fact) => (
                    <Badge key={fact.key} tone="warning">{fact.label}</Badge>
                  ))}
                </InlineStack>
              </BlockStack>
            )}
            <Text as="p" variant="bodySm" tone="subdued">{product.safety_note}</Text>
          </BlockStack>
        )}

        <Button variant="plain" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Masquer le détail" : "Voir les faits manquants"}
        </Button>
      </BlockStack>
    </Card>
  );
}

export default function GeoFacts() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoFacts")}
      subtitle={locale === "fr" ? "Faits produits confirmés pour le GEO et les moteurs IA" : "Confirmed product facts for GEO and AI search"}
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
                { label: "Complétude moyenne", value: pct(data.summary.avg_completeness_score) },
                { label: "Prêts GEO", value: String(data.summary.products_ready_for_geo) },
                { label: "Faits sensibles manquants", value: String(data.summary.products_missing_sensitive_facts) },
                { label: "Produits analysés", value: String(data.total) },
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
              <Text as="p">{data.summary.safety_note}</Text>
            </Banner>

            <BlockStack gap="300">
              {data.products.map((product) => (
                <ProductFactsRow key={product.id || product.handle} product={product} />
              ))}
            </BlockStack>

            {!data.products.length && (
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
