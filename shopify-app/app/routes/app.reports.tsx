import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import { useEffect } from "react";
import {
  Badge,
  Banner,
  BlockStack,
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

interface ReportMeta {
  type: string;
  label: string;
  description: string;
  format: string;
  available: boolean;
}

interface ListData {
  shop: string;
  reports: ReportMeta[];
}

interface LoaderData {
  locale: Locale;
  list: ListData | null;
  error: string | null;
}

interface ActionData {
  content: string;
  filename: string;
  report_type: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/reports/list`, {
      accessToken: session.accessToken,
    });
    if (!resp.ok) {
      return json<LoaderData>({ locale, list: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, list: (await resp.json()) as ListData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, list: null, error: String(err) });
  }
};

// ---------------------------------------------------------------------------
// Action — fetch report content server-side, return to client for download
// ---------------------------------------------------------------------------

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const body = await request.json();
  const { report_type } = body as { report_type: string };

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/reports/${report_type}`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<ActionData>(
        { content: "", filename: "", report_type, error: await resp.text() },
        { status: resp.status },
      );
    }
    const content = await resp.text();
    const date = new Date().toISOString().slice(0, 10);
    const filename = `leonie-seo-${report_type}-${date}.md`;
    return json<ActionData>({ content, filename, report_type });
  } catch (err) {
    return json<ActionData>(
      { content: "", filename: "", report_type, error: String(err) },
      { status: 500 },
    );
  }
};

// ---------------------------------------------------------------------------
// Report card with download
// ---------------------------------------------------------------------------

function ReportCard({ meta }: { meta: ReportMeta }) {
  const fetcher = useFetcher<ActionData>();
  const isLoading = fetcher.state !== "idle";
  const result = fetcher.data;

  // Trigger browser download when content arrives
  useEffect(() => {
    if (!result?.content || result.error) return;
    const blob = new Blob([result.content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [result]);

  const handleGenerate = () => {
    fetcher.submit(
      { report_type: meta.type },
      { method: "POST", encType: "application/json" },
    );
  };

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{meta.label}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{meta.description}</Text>
          </BlockStack>
          <Badge tone={meta.available ? "success" : "warning"}>
            {meta.available ? "Disponible" : "Données manquantes"}
          </Badge>
        </InlineStack>

        {result?.error && (
          <Banner tone="critical">
            <Text as="p" variant="bodySm">{result.error}</Text>
          </Banner>
        )}

        {result?.content && !result.error && (
          <Banner tone="success">
            <Text as="p" variant="bodySm">
              {`Téléchargement lancé : ${result.filename}`}
            </Text>
          </Banner>
        )}

        <InlineStack>
          <Button
            onClick={handleGenerate}
            loading={isLoading}
            disabled={!meta.available || isLoading}
          >
            {`Générer & Télécharger (.${meta.format})`}
          </Button>
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Reports() {
  const { locale, list, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title="Rapports exportables"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">Rapports SEO</Text>
            <Text as="p" tone="subdued" variant="bodySm">
              Générez et téléchargez les rapports SEO de votre boutique au format Markdown.
              Chaque rapport est généré à la demande depuis les données actuelles.
            </Text>
          </BlockStack>
        </Card>

        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {list && (
          <BlockStack gap="300">
            {list.reports.map((meta) => (
              <ReportCard key={meta.type} meta={meta} />
            ))}
          </BlockStack>
        )}

        {!list && !error && (
          <Card>
            <Text as="p" tone="subdued">Chargement…</Text>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
