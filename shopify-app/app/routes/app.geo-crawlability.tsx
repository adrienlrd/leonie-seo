import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
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
} from "@shopify/polaris";
import { useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface CrawlabilityPage {
  resource_type: "product" | "collection" | "policy";
  title: string;
  path: string;
  reason: string;
  priority: "high" | "medium" | "review" | "exclude";
}

interface CrawlabilityData {
  shop: string;
  available: boolean;
  domain: string;
  summary: {
    included_pages: number;
    excluded_or_review_pages: number;
    product_pages: number;
    collection_pages: number;
    policy_pages: number;
    dry_run: boolean;
    note: string;
  };
  included_pages: CrawlabilityPage[];
  excluded_pages: CrawlabilityPage[];
  warnings: string[];
  llms_txt: string;
  robots_txt_liquid: string;
  robots_install_steps: string[];
}

interface LoaderData {
  locale: Locale;
  data: CrawlabilityData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/geo/crawlability?top_products=30&top_collections=20`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as CrawlabilityData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

function priorityTone(priority: CrawlabilityPage["priority"]): "success" | "info" | "warning" | "critical" {
  if (priority === "high") return "success";
  if (priority === "medium") return "info";
  if (priority === "review") return "warning";
  return "critical";
}

function PageList({ title, pages, locale }: { title: string; pages: CrawlabilityPage[]; locale: Locale }) {
  return (
    <Card>
      <BlockStack gap="300">
        <Text as="h2" variant="headingMd">{title}</Text>
        {pages.length > 0 ? (
          <BlockStack gap="200">
            {pages.map((page) => (
              <BlockStack key={`${page.resource_type}-${page.path}-${page.title}`} gap="100">
                <InlineStack gap="100" blockAlign="center" wrap>
                  <Badge tone={priorityTone(page.priority)}>{page.priority}</Badge>
                  <Badge>{page.resource_type}</Badge>
                  <Text as="p" variant="bodyMd" fontWeight="semibold">{page.title}</Text>
                </InlineStack>
                <Text as="p" variant="bodySm" tone="subdued">{page.path || "URL manquante"}</Text>
                <Text as="p" variant="bodySm">{page.reason}</Text>
              </BlockStack>
            ))}
          </BlockStack>
        ) : (
          <Text as="p" tone="subdued">{t(locale, "noData")}</Text>
        )}
      </BlockStack>
    </Card>
  );
}

export default function GeoCrawlability() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const [robotsCopied, setRobotsCopied] = useState(false);

  const copyRobotsTemplate = async () => {
    if (!data?.robots_txt_liquid || typeof navigator === "undefined") return;
    await navigator.clipboard.writeText(data.robots_txt_liquid);
    setRobotsCopied(true);
  };

  return (
    <Page
      title={t(locale, "geoCrawlability")}
      subtitle={locale === "fr" ? "Preview llms.txt et recommandations de lisibilité IA" : "llms.txt preview and AI crawlability recommendations"}
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
                { label: "Pages incluses", value: String(data.summary.included_pages) },
                { label: "À revoir/exclure", value: String(data.summary.excluded_or_review_pages) },
                { label: "Produits", value: String(data.summary.product_pages) },
                { label: "Collections", value: String(data.summary.collection_pages) },
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

            {data.warnings.length > 0 && (
              <Banner tone="warning">
                <List type="bullet">
                  {data.warnings.map((warning) => (
                    <List.Item key={warning}>{warning}</List.Item>
                  ))}
                </List>
              </Banner>
            )}

            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center" wrap>
                  <BlockStack gap="050">
                    <Text as="h2" variant="headingMd">
                      {locale === "fr" ? "Template robots.txt.liquid" : "robots.txt.liquid template"}
                    </Text>
                    <Text as="p" tone="subdued">
                      {locale === "fr"
                        ? "À coller dans le thème uniquement si le marchand veut personnaliser robots.txt."
                        : "Paste into the theme only if the merchant wants to customize robots.txt."}
                    </Text>
                  </BlockStack>
                  <Button onClick={copyRobotsTemplate}>
                    {robotsCopied
                      ? locale === "fr" ? "Copié" : "Copied"
                      : locale === "fr" ? "Copier" : "Copy"}
                  </Button>
                </InlineStack>
                <List type="number">
                  {(data.robots_install_steps ?? []).map((step) => (
                    <List.Item key={step}>{step}</List.Item>
                  ))}
                </List>
                <pre
                  aria-label="robots.txt.liquid template"
                  style={{ fontSize: 12, overflowX: "auto", margin: 0, whiteSpace: "pre-wrap" }}
                >
                  {data.robots_txt_liquid}
                </pre>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <InlineStack align="space-between" blockAlign="center" wrap>
                  <Text as="h2" variant="headingMd">llms.txt preview</Text>
                  <InlineStack gap="100">
                    <Badge tone="attention">Dry-run</Badge>
                    <Badge>{data.domain}</Badge>
                  </InlineStack>
                </InlineStack>
                <pre
                  aria-label="llms.txt preview"
                  style={{ fontSize: 12, overflowX: "auto", margin: 0, whiteSpace: "pre-wrap" }}
                >
                  {data.llms_txt}
                </pre>
              </BlockStack>
            </Card>

            <PageList title="Pages recommandées" pages={data.included_pages} locale={locale} />
            <PageList title="Pages à revoir ou exclure" pages={data.excluded_pages} locale={locale} />
          </>
        )}
      </BlockStack>
    </Page>
  );
}
