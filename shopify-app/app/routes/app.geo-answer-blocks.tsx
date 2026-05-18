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

interface AnswerSource {
  key: string;
  label: string;
  source: string;
}

interface AnswerBlock {
  question: string;
  answer: string;
  intent: string;
  confidence: "confirmed";
  sources: AnswerSource[];
  review_required: boolean;
}

interface ReviewPrompt {
  key: string;
  label: string;
  question: string;
  reason: string;
}

interface AnswerProduct {
  product_id: string;
  handle: string;
  title: string;
  answer_block_count: number;
  answer_blocks: AnswerBlock[];
  review_prompt_count: number;
  review_prompts: ReviewPrompt[];
  jsonld: Record<string, unknown>;
  dry_run: boolean;
  safety_note: string;
}

interface AnswerData {
  shop: string;
  available: boolean;
  total: number;
  summary: {
    products_with_answers: number;
    total_answer_blocks: number;
    total_review_prompts: number;
    dry_run: boolean;
    safety_note: string;
  };
  products: AnswerProduct[];
}

interface LoaderData {
  locale: Locale;
  data: AnswerData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/answer-blocks?top=30&max_blocks=6`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as AnswerData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function AnswerProductCard({ product }: { product: AnswerProduct }) {
  const jsonldText = JSON.stringify(product.jsonld, null, 2);
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{product.title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{`/products/${product.handle}`}</Text>
          </BlockStack>
          <InlineStack gap="100" blockAlign="center">
            <Badge tone={product.answer_block_count ? "success" : "warning"}>{`${product.answer_block_count} réponses`}</Badge>
            <Badge tone={product.review_prompt_count ? "warning" : "success"}>{`${product.review_prompt_count} à vérifier`}</Badge>
            <Badge tone="attention">Dry-run</Badge>
          </InlineStack>
        </InlineStack>

        <Banner tone="info">
          <Text as="p">{product.safety_note}</Text>
        </Banner>

        {product.answer_blocks.length > 0 && (
          <BlockStack gap="200">
            <Text as="h3" variant="headingSm">Blocs de réponse confirmés</Text>
            {product.answer_blocks.map((block) => (
              <BlockStack key={block.question} gap="150">
                <InlineStack gap="100" blockAlign="center" wrap>
                  <Badge tone="success">{block.confidence}</Badge>
                  <Badge tone="info">{block.intent}</Badge>
                  {block.sources.map((source) => (
                    <Badge key={`${block.question}-${source.key}`}>{source.label}</Badge>
                  ))}
                </InlineStack>
                <Text as="p" variant="bodyMd" fontWeight="semibold">{block.question}</Text>
                <Text as="p" variant="bodySm">{block.answer}</Text>
              </BlockStack>
            ))}
          </BlockStack>
        )}

        {product.review_prompts.length > 0 && (
          <BlockStack gap="100">
            <Text as="h3" variant="headingSm">À confirmer avant publication</Text>
            <List type="bullet">
              {product.review_prompts.slice(0, 6).map((prompt) => (
                <List.Item key={`${prompt.key}-${prompt.question}`}>{`${prompt.question} — ${prompt.reason}`}</List.Item>
              ))}
            </List>
          </BlockStack>
        )}

        {product.answer_blocks.length > 0 && (
          <BlockStack gap="100">
            <Text as="h3" variant="headingSm">JSON-LD FAQPage preview</Text>
            <pre
              aria-label={`JSON-LD FAQPage pour ${product.title}`}
              style={{ fontSize: 11, overflowX: "auto", margin: 0, whiteSpace: "pre-wrap" }}
            >
              {jsonldText}
            </pre>
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}

export default function GeoAnswerBlocks() {
  const { locale, data, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title={t(locale, "geoAnswerBlocks")}
      subtitle={locale === "fr" ? "FAQ et réponses IA fondées sur les faits produits confirmés" : "FAQ and AI answers grounded in confirmed product facts"}
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
                { label: "Produits avec réponses", value: String(data.summary.products_with_answers) },
                { label: "Blocs confirmés", value: String(data.summary.total_answer_blocks) },
                { label: "À vérifier", value: String(data.summary.total_review_prompts) },
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
              <Text as="p">{data.summary.safety_note}</Text>
            </Banner>

            <BlockStack gap="300">
              {data.products.map((product) => (
                <AnswerProductCard key={product.product_id || product.handle} product={product} />
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
