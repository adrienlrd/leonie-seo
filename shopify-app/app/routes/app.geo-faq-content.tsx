import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  DataTable,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface FaqItem {
  question: string;
  answer: string;
  source: string;
}

interface BuyingGuideSection {
  heading: string;
  content: string;
}

interface ContentItem {
  id: string;
  content_type: "product_faq" | "collection_faq";
  resource_type: string;
  resource_id: string;
  resource_title: string;
  resource_handle: string;
  faq_items: FaqItem[];
  buying_guide: { title: string; sections: BuyingGuideSection[] } | null;
  answer_block: string;
  faq_jsonld_str: string;
  quality_score: number;
  quality_label: string;
  status: "draft" | "needs_review";
  facts_used: string[];
  facts_missing: string[];
  source_queries: string[];
}

interface FaqData {
  content_items: ContentItem[];
  summary: {
    total: number;
    by_status: Record<string, number>;
    by_quality: Record<string, number>;
    avg_quality_score: number;
  };
  generated_at: string;
}

interface LoaderData {
  locale: Locale;
  data: FaqData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/geo/faq-content`, {
      accessToken: session.accessToken,
    });
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: `HTTP ${resp.status}` });
    }
    const data = (await resp.json()) as FaqData;
    return json<LoaderData>({ locale, data, error: null });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    return json<LoaderData>({ locale, data: null, error: message });
  }
};

const QUALITY_TONES: Record<string, "success" | "warning" | "critical" | undefined> = {
  excellent: "success",
  bon: "success",
  à_compléter: "warning",
  incomplet: "critical",
};

const STATUS_TONES: Record<string, "warning" | undefined> = {
  needs_review: "warning",
  draft: undefined,
};

function ContentCard({ item, locale }: { item: ContentItem; locale: Locale }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack gap="200" align="space-between">
          <BlockStack gap="100">
            <Text as="h3" variant="headingSm">
              {item.resource_title}
            </Text>
            <Text as="p" tone="subdued" variant="bodySm">
              {item.content_type === "product_faq"
                ? t(locale, "faqTypeProduct")
                : t(locale, "faqTypeCollection")}
            </Text>
          </BlockStack>
          <InlineStack gap="200">
            <Badge tone={QUALITY_TONES[item.quality_label]}>
              {`${item.quality_score}/100`}
            </Badge>
            <Badge tone={STATUS_TONES[item.status]}>
              {item.status === "needs_review"
                ? t(locale, "faqStatusReview")
                : t(locale, "faqStatusDraft")}
            </Badge>
            <Button
              variant="plain"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? t(locale, "faqCollapse") : t(locale, "faqExpand")}
            </Button>
          </InlineStack>
        </InlineStack>

        {!expanded && (
          <Text as="p" tone="subdued">
            {item.faq_items.length} {t(locale, "faqItemsCount")}
            {item.source_queries.length > 0
              ? ` · ${item.source_queries.length} ${t(locale, "faqQueriesCount")}`
              : ""}
          </Text>
        )}

        {expanded && (
          <BlockStack gap="400">
            {/* Answer block */}
            <Card>
              <BlockStack gap="100">
                <Text as="h4" variant="headingXs" tone="subdued">
                  {t(locale, "faqAnswerBlock")}
                </Text>
                <Text as="p">{item.answer_block}</Text>
              </BlockStack>
            </Card>

            {/* FAQ items */}
            {item.faq_items.length > 0 && (
              <BlockStack gap="200">
                <Text as="h4" variant="headingXs">
                  {t(locale, "faqItemsTitle")}
                </Text>
                <DataTable
                  columnContentTypes={["text", "text"]}
                  headings={[t(locale, "faqQuestion"), t(locale, "faqAnswer")]}
                  rows={item.faq_items.map((f) => [f.question, f.answer])}
                />
              </BlockStack>
            )}

            {/* Buying guide */}
            {item.buying_guide && item.buying_guide.sections.length > 0 && (
              <BlockStack gap="200">
                <Text as="h4" variant="headingXs">
                  {item.buying_guide.title}
                </Text>
                {item.buying_guide.sections.map((s, i) => (
                  <Card key={i}>
                    <BlockStack gap="100">
                      <Text as="p" fontWeight="semibold">
                        {s.heading}
                      </Text>
                      <Text as="p" tone="subdued">
                        {s.content}
                      </Text>
                    </BlockStack>
                  </Card>
                ))}
              </BlockStack>
            )}

            {/* JSON-LD preview */}
            <BlockStack gap="100">
              <Text as="h4" variant="headingXs">
                JSON-LD FAQPage
              </Text>
              <pre
                style={{
                  background: "#f4f6f8",
                  padding: "12px",
                  borderRadius: "8px",
                  fontSize: "11px",
                  overflow: "auto",
                  maxHeight: "200px",
                  whiteSpace: "pre-wrap",
                }}
              >
                {item.faq_jsonld_str}
              </pre>
            </BlockStack>

            {/* Missing facts warning */}
            {item.facts_missing.length > 0 && (
              <Banner tone="warning" title={t(locale, "faqMissingTitle")}>
                <p>
                  {t(locale, "faqMissingDesc")}: {item.facts_missing.join(", ")}
                </p>
              </Banner>
            )}
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}

export default function GeoFaqContentPage() {
  const { locale, data, error } = useLoaderData<typeof loader>() as LoaderData;

  if (error || !data) {
    return (
      <Page
        title={t(locale, "faqContentTitle")}
        backAction={{
          content: t(locale, "backDashboard"),
          url: localizedPath("/app/insights", locale),
        }}
      >
        <Banner tone="critical" title={t(locale, "impactError")}>
          <p>{error ?? "Unknown error"}</p>
        </Banner>
      </Page>
    );
  }

  return (
    <Page
      title={t(locale, "faqContentTitle")}
      subtitle={t(locale, "faqContentSubtitle")}
      backAction={{
        content: t(locale, "backDashboard"),
        url: localizedPath("/app/insights", locale),
      }}
    >
      <BlockStack gap="400">
        <Banner tone="info" title={t(locale, "faqDryRunTitle")}>
          <p>{t(locale, "faqDryRunMessage")}</p>
        </Banner>

        <Card>
          <BlockStack gap="200">
            <InlineStack gap="300">
              <Badge tone="info">
                {`${data.summary.total} ${t(locale, "faqTotal")}`}
              </Badge>
              <Badge>
                {`${t(locale, "faqAvgScore")}: ${data.summary.avg_quality_score}/100`}
              </Badge>
              {(data.summary.by_status["needs_review"] ?? 0) > 0 && (
                <Badge tone="warning">
                  {`${data.summary.by_status["needs_review"]} ${t(locale, "faqNeedsReview")}`}
                </Badge>
              )}
            </InlineStack>
            <Text as="p" tone="subdued">
              {t(locale, "impactGenerated")}:{" "}
              {data.generated_at.slice(0, 19).replace("T", " ")}
            </Text>
          </BlockStack>
        </Card>

        {data.content_items.length === 0 ? (
          <Card>
            <Text as="p" tone="subdued">
              {t(locale, "faqEmpty")}
            </Text>
          </Card>
        ) : (
          <BlockStack gap="300">
            {data.content_items.map((item) => (
              <ContentCard key={item.id} item={item} locale={locale} />
            ))}
          </BlockStack>
        )}
      </BlockStack>
    </Page>
  );
}
