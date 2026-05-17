import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  InlineStack,
  Badge,
  Tabs,
  DataTable,
  Banner,
  Collapsible,
  Button,
  Divider,
  Box,
  EmptyState,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, t, type Locale } from "../lib/i18n";
import { useState, useCallback } from "react";

interface FaqEntry {
  q: string;
  a: string;
}

interface FaqItem {
  product_id: string;
  handle: string;
  title: string;
  faq_count: number;
  faq: FaqEntry[];
  jsonld: Record<string, unknown>;
}

interface FaqData {
  shop: string;
  total: number;
  note: string;
  items: FaqItem[];
}

interface InternalLink {
  title: string;
  path: string;
}

interface Brief {
  target_keyword: string;
  impressions: number;
  suggested_title: string;
  word_count_target: number;
  h2_sections: string[];
  internal_links: InternalLink[];
  call_to_action: string;
}

interface BriefsData {
  shop: string;
  gsc_connected: boolean;
  total: number;
  note: string;
  briefs: Brief[];
}

interface LoaderData {
  shop: string;
  locale: Locale;
  faq: FaqData | null;
  briefs: BriefsData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const be = (path: string) =>
    callBackendForShop(shop, path, { accessToken: session.accessToken });

  const [faqResult, briefsResult] = await Promise.allSettled([
    be(`/api/shops/${shop}/content/faq`).then((r) => r.json()),
    be(`/api/shops/${shop}/content/briefs`).then((r) => r.json()),
  ]);

  return json<LoaderData>({
    shop,
    locale,
    faq: faqResult.status === "fulfilled" ? (faqResult.value as FaqData) : null,
    briefs: briefsResult.status === "fulfilled" ? (briefsResult.value as BriefsData) : null,
    error: null,
  });
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [text]);
  return (
    <Button size="slim" onClick={handleCopy}>
      {copied ? "Copié !" : "Copier JSON-LD"}
    </Button>
  );
}

function FaqProductCard({ item }: { item: FaqItem }) {
  const [open, setOpen] = useState(false);
  const jsonldText = JSON.stringify(item.jsonld, null, 2);

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <BlockStack gap="100">
            <Text variant="headingSm" as="h3">
              {item.title}
            </Text>
            <Text variant="bodySm" as="p" tone="subdued">
              /products/{item.handle}
            </Text>
          </BlockStack>
          <InlineStack gap="200">
            <Badge tone="info">{`${item.faq_count} FAQ`}</Badge>
            <Button
              size="slim"
              onClick={() => setOpen(!open)}
            >
              {open ? "Masquer" : "Voir détails"}
            </Button>
          </InlineStack>
        </InlineStack>

        <Collapsible open={open} id={`faq-${item.handle}`} transition={{ duration: "200ms" }}>
          <BlockStack gap="300">
            {item.faq.map((entry, idx) => (
              <Box key={idx} padding="300" background="bg-surface-secondary" borderRadius="200">
                <BlockStack gap="100">
                  <Text variant="bodyMd" as="p" fontWeight="bold">
                    {entry.q}
                  </Text>
                  <Text variant="bodySm" as="p" tone="subdued">
                    {entry.a}
                  </Text>
                </BlockStack>
              </Box>
            ))}
            <Divider />
            <InlineStack align="space-between" blockAlign="center">
              <Text variant="bodySm" as="p" tone="subdued">
                JSON-LD Schema.org FAQPage
              </Text>
              <CopyButton text={jsonldText} />
            </InlineStack>
            <Box
              padding="200"
              background="bg-surface-secondary"
              borderRadius="200"
            >
              <pre style={{ fontSize: "11px", overflowX: "auto", margin: 0, whiteSpace: "pre-wrap" }}>
                {jsonldText}
              </pre>
            </Box>
          </BlockStack>
        </Collapsible>
      </BlockStack>
    </Card>
  );
}

function FaqTab({ data }: { data: FaqData | null }) {
  if (!data) {
    return (
      <Banner tone="critical">
        <Text as="p">Impossible de charger les FAQ. Vérifiez que le backend est disponible.</Text>
      </Banner>
    );
  }

  if (data.total === 0) {
    return (
      <EmptyState
        heading="Aucun produit trouvé"
        image=""
      >
        <Text as="p">Lancez un audit SEO pour générer un snapshot de vos produits.</Text>
      </EmptyState>
    );
  }

  return (
    <BlockStack gap="400">
      <Banner tone="info">
        <Text as="p">{data.note}</Text>
      </Banner>
      <Text variant="headingSm" as="h2">
        {data.total} produit{data.total > 1 ? "s" : ""}
      </Text>
      {data.items.map((item) => (
        <FaqProductCard key={item.handle} item={item} />
      ))}
    </BlockStack>
  );
}

function BriefCard({ brief }: { brief: Brief }) {
  const [open, setOpen] = useState(false);

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <BlockStack gap="100">
            <Text variant="headingSm" as="h3">
              {brief.suggested_title}
            </Text>
            <Text variant="bodySm" as="p" tone="subdued">
              Mot-clé cible : <strong>{brief.target_keyword}</strong>
            </Text>
          </BlockStack>
          <InlineStack gap="200">
            <Badge>{`${brief.impressions} impressions`}</Badge>
            <Badge tone="attention">{`${brief.word_count_target} mots`}</Badge>
            <Button size="slim" onClick={() => setOpen(!open)}>
              {open ? "Masquer" : "Voir brief"}
            </Button>
          </InlineStack>
        </InlineStack>

        <Collapsible open={open} id={`brief-${brief.target_keyword}`} transition={{ duration: "200ms" }}>
          <BlockStack gap="300">
            <BlockStack gap="200">
              <Text variant="bodyMd" as="p" fontWeight="semibold">
                Structure H2 suggérée
              </Text>
              {brief.h2_sections.map((h2, idx) => (
                <Box key={idx} padding="200" background="bg-surface-secondary" borderRadius="200">
                  <Text variant="bodySm" as="p">
                    H2 {idx + 1} — {h2}
                  </Text>
                </Box>
              ))}
            </BlockStack>

            {brief.internal_links.length > 0 && (
              <BlockStack gap="200">
                <Text variant="bodyMd" as="p" fontWeight="semibold">
                  Liens internes suggérés
                </Text>
                {brief.internal_links.map((lk, idx) => (
                  <InlineStack key={idx} gap="200" blockAlign="center">
                    <Badge tone="success">Produit</Badge>
                    <Text variant="bodySm" as="p">
                      {lk.title} → <code>{lk.path}</code>
                    </Text>
                  </InlineStack>
                ))}
              </BlockStack>
            )}

            <InlineStack gap="200" blockAlign="center">
              <Text variant="bodySm" as="p" tone="subdued">
                CTA suggéré :
              </Text>
              <Text variant="bodySm" as="p">
                {brief.call_to_action}
              </Text>
            </InlineStack>
          </BlockStack>
        </Collapsible>
      </BlockStack>
    </Card>
  );
}

function BriefsTab({ data }: { data: BriefsData | null }) {
  if (!data) {
    return (
      <Banner tone="critical">
        <Text as="p">Impossible de charger les briefs. Vérifiez que le backend est disponible.</Text>
      </Banner>
    );
  }

  if (!data.gsc_connected) {
    return (
      <EmptyState
        heading="Google Search Console non connectée"
        image=""
      >
        <BlockStack gap="200">
          <Text as="p">
            Connectez Google Search Console pour générer des briefs basés sur vos vraies requêtes.
          </Text>
          <Text as="p" tone="subdued">
            Les briefs seront triés par volume d&apos;impressions et filtrés sur les requêtes informationnelles.
          </Text>
        </BlockStack>
      </EmptyState>
    );
  }

  return (
    <BlockStack gap="400">
      <Banner tone="info">
        <Text as="p">{data.note}</Text>
      </Banner>
      <Text variant="headingSm" as="h2">
        {data.total} brief{data.total > 1 ? "s" : ""} identifié{data.total > 1 ? "s" : ""}
      </Text>
      {data.briefs.map((brief, idx) => (
        <BriefCard key={idx} brief={brief} />
      ))}
    </BlockStack>
  );
}

export default function ContentPage() {
  const { locale, faq, briefs } = useLoaderData<LoaderData>();
  const [selectedTab, setSelectedTab] = useState(0);

  const tabs = [
    { id: "faq", content: t(locale, "contentFaq"), panelID: "faq-panel" },
    { id: "briefs", content: t(locale, "contentBriefs"), panelID: "briefs-panel" },
  ];

  return (
    <Page
      title={t(locale, "content")}
      subtitle={t(locale, "contentSubtitle")}
    >
      <Layout>
        <Layout.Section>
          <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
            <Box paddingBlockStart="400">
              {selectedTab === 0 && <FaqTab data={faq} />}
              {selectedTab === 1 && <BriefsTab data={briefs} />}
            </Box>
          </Tabs>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
