import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Card,
  InlineStack,
  Page,
  ProgressBar,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface Recommendation {
  key: string;
  label: string;
  instruction: string;
}

interface ReadinessProduct {
  id: string;
  handle: string;
  title: string;
  readiness_score: number;
  level: "ready" | "partial" | "weak";
  components: {
    facts: number;
    schema: number;
    answerability: number;
    trust: number;
    seo: number;
    commerce: number;
  };
  confirmed_fact_count: number;
  missing_fact_count: number;
  recommendations: Recommendation[];
  note: string;
}

interface ReadinessData {
  shop: string;
  available: boolean;
  total: number;
  summary: {
    avg_readiness_score: number;
    ready_products: number;
    partial_products: number;
    weak_products: number;
    score_note: string;
  };
  products: ReadinessProduct[];
}

interface LoaderData {
  locale: Locale;
  data: ReadinessData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/readiness?top=100`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as ReadinessData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function scoreTone(score: number): "success" | "primary" | "critical" {
  if (score >= 75) return "success";
  if (score >= 50) return "primary";
  return "critical";
}

function levelBadge(level: ReadinessProduct["level"]) {
  if (level === "ready") return <Badge tone="success">Ready</Badge>;
  if (level === "partial") return <Badge tone="warning">Partiel</Badge>;
  return <Badge tone="critical">Faible</Badge>;
}

function ComponentBar({ label, value }: { label: string; value: number }) {
  return (
    <BlockStack gap="050">
      <InlineStack align="space-between">
        <Text as="span" variant="bodySm" tone="subdued">{label}</Text>
        <Text as="span" variant="bodySm" fontWeight="semibold">{`${value} %`}</Text>
      </InlineStack>
      <ProgressBar progress={value} size="small" tone={scoreTone(value)} />
    </BlockStack>
  );
}

function ProductRow({ product }: { product: ReadinessProduct }) {
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{product.title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">/{product.handle}</Text>
          </BlockStack>
          <InlineStack gap="200" blockAlign="center">
            {levelBadge(product.level)}
            <Badge tone={product.readiness_score >= 75 ? "success" : product.readiness_score >= 50 ? "warning" : "critical"}>
              {`${product.readiness_score} / 100`}
            </Badge>
          </InlineStack>
        </InlineStack>

        <ProgressBar
          progress={product.readiness_score}
          size="small"
          tone={scoreTone(product.readiness_score)}
        />

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
          <ComponentBar label="Faits" value={product.components.facts} />
          <ComponentBar label="Schema" value={product.components.schema} />
          <ComponentBar label="Réponses IA" value={product.components.answerability} />
          <ComponentBar label="Confiance" value={product.components.trust} />
          <ComponentBar label="SEO" value={product.components.seo} />
          <ComponentBar label="Commerce" value={product.components.commerce} />
        </div>

        {product.recommendations.length > 0 && (
          <BlockStack gap="100">
            {product.recommendations.slice(0, 3).map((rec) => (
              <Text key={`${product.id}-${rec.key}-${rec.instruction}`} as="p" variant="bodySm" tone="caution">
                {`${rec.label}: ${rec.instruction}`}
              </Text>
            ))}
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}

export default function GeoReadiness() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoReadiness")}
      subtitle={locale === "fr" ? "Score interne de préparation aux moteurs IA" : "Internal readiness score for AI search engines"}
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
                { label: "Score moyen", value: `${data.summary.avg_readiness_score} / 100` },
                { label: "Ready", value: String(data.summary.ready_products) },
                { label: "Partiels", value: String(data.summary.partial_products) },
                { label: "Faibles", value: String(data.summary.weak_products) },
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
              <Text as="p">{data.summary.score_note}</Text>
            </Banner>

            <BlockStack gap="300">
              {data.products.map((product) => (
                <ProductRow key={product.id || product.handle} product={product} />
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
