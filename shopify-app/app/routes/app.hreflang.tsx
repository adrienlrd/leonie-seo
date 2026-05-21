import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useActionData, useLoaderData, useSubmit } from "@remix-run/react";
import { useCallback, useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  Checkbox,
  DataTable,
  InlineStack,
  Page,
  Tabs,
  Text,
  TextField,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HreflangMarket {
  locale: string;
  url_prefix: string;
  primary: boolean;
}

interface HreflangIssue {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
}

interface HreflangStatus {
  configured: boolean;
  markets_count: number;
  markets: HreflangMarket[];
  issues_count: number;
  error_count: number;
  ready: boolean;
}

interface HreflangTag {
  hreflang: string;
  href: string;
}

interface HreflangPage {
  type: string;
  path: string;
  url: string;
  tags: HreflangTag[];
  html: string;
}

interface HreflangPreview {
  available: boolean;
  base_url?: string;
  markets_count?: number;
  pages: HreflangPage[];
  issues: HreflangIssue[];
  message?: string;
}

interface LoaderData {
  status: HreflangStatus;
  preview: HreflangPreview;
  locale: Locale;
  shop: string;
}

interface ActionData {
  saved?: boolean;
  deleted?: boolean;
  issues?: HreflangIssue[];
  error?: string;
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const be = (path: string) =>
    callBackendForShop(shop, path, { accessToken: session.accessToken });

  const [statusRes, previewRes] = await Promise.all([
    be(`/api/shops/${shop}/hreflang/status`),
    be(`/api/shops/${shop}/hreflang/preview?max_pages=5`),
  ]);

  const status: HreflangStatus = statusRes.ok
    ? await statusRes.json()
    : { configured: false, markets_count: 0, markets: [], issues_count: 0, error_count: 0, ready: false };

  const preview: HreflangPreview = previewRes.ok
    ? await previewRes.json()
    : { available: false, pages: [], issues: [] };

  return json<LoaderData>({ status, preview, locale, shop });
}

// ---------------------------------------------------------------------------
// Action
// ---------------------------------------------------------------------------

export async function action({ request }: ActionFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const form = await request.formData();
  const intent = form.get("intent") as string;

  const be = (path: string, init: RequestInit = {}) =>
    callBackendForShop(shop, path, { accessToken: session.accessToken, ...init });

  try {
    if (intent === "save") {
      const marketsJson = form.get("markets") as string;
      const markets: HreflangMarket[] = JSON.parse(marketsJson);
      const res = await be(`/api/shops/${shop}/hreflang/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markets }),
      });
      const data = await res.json();
      if (!res.ok) {
        return json<ActionData>({ error: data.detail ?? "Erreur lors de l'enregistrement" });
      }
      return json<ActionData>({ saved: true, issues: data.issues });
    }

    if (intent === "delete") {
      await be(`/api/shops/${shop}/hreflang/settings`, { method: "DELETE" });
      return json<ActionData>({ deleted: true });
    }
  } catch (err) {
    return json<ActionData>({ error: err instanceof Error ? err.message : "Erreur réseau" });
  }

  return json<ActionData>({});
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SEVERITY_TONE = {
  error: "critical",
  warning: "warning",
  info: "info",
} as const;

function issueBadge(severity: HreflangIssue["severity"]) {
  const labels = { error: "Erreur", warning: "Attention", info: "Info" };
  return <Badge tone={SEVERITY_TONE[severity]}>{labels[severity]}</Badge>;
}

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function MarketRow({
  market,
  index,
  onChange,
  onRemove,
  locale,
}: {
  market: HreflangMarket;
  index: number;
  onChange: (i: number, m: HreflangMarket) => void;
  onRemove: (i: number) => void;
  locale: Locale;
}) {
  return (
    <Box paddingBlockEnd="300">
      <InlineStack gap="300" wrap={false} blockAlign="center">
        <Box minWidth="120px">
          <TextField
            label={index === 0 ? t(locale, "hreflangLocale") : ""}
            labelHidden={index !== 0}
            value={market.locale}
            placeholder="fr-FR"
            onChange={(v) => onChange(index, { ...market, locale: v })}
            autoComplete="off"
          />
        </Box>
        <Box minWidth="140px">
          <TextField
            label={index === 0 ? t(locale, "hreflangPrefix") : ""}
            labelHidden={index !== 0}
            value={market.url_prefix}
            placeholder="/fr-be"
            onChange={(v) => onChange(index, { ...market, url_prefix: v })}
            autoComplete="off"
          />
        </Box>
        <Box paddingBlockStart={index === 0 ? "500" : "0"}>
          <Checkbox
            label={t(locale, "hreflangPrimary")}
            checked={market.primary}
            onChange={(v) => onChange(index, { ...market, primary: v })}
          />
        </Box>
        <Box paddingBlockStart={index === 0 ? "500" : "0"}>
          <Button variant="plain" tone="critical" onClick={() => onRemove(index)}>
            {t(locale, "hreflangRemove")}
          </Button>
        </Box>
      </InlineStack>
    </Box>
  );
}

function ConfigTab({ status, locale, submit }: {
  status: HreflangStatus;
  locale: Locale;
  submit: ReturnType<typeof useSubmit>;
}) {
  const [markets, setMarkets] = useState<HreflangMarket[]>(
    status.markets.length > 0
      ? status.markets
      : [{ locale: "", url_prefix: "", primary: true }]
  );

  const updateMarket = useCallback((i: number, m: HreflangMarket) => {
    setMarkets((prev) => prev.map((item, idx) => (idx === i ? m : item)));
  }, []);

  const addMarket = useCallback(() => {
    setMarkets((prev) => [...prev, { locale: "", url_prefix: "", primary: false }]);
  }, []);

  const removeMarket = useCallback((i: number) => {
    setMarkets((prev) => prev.filter((_, idx) => idx !== i));
  }, []);

  const handleSave = useCallback(() => {
    const fd = new FormData();
    fd.set("intent", "save");
    fd.set("markets", JSON.stringify(markets));
    submit(fd, { method: "post" });
  }, [markets, submit]);

  const handleDelete = useCallback(() => {
    const fd = new FormData();
    fd.set("intent", "delete");
    submit(fd, { method: "post" });
  }, [submit]);

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="center">
          <Text variant="headingMd" as="h2">{t(locale, "hreflangConfig")}</Text>
          <Badge tone={status.ready ? "success" : "attention"}>
            {status.ready ? t(locale, "hreflangReady") : t(locale, "hreflangNotReady")}
          </Badge>
        </InlineStack>

        {markets.length === 0 ? (
          <Text as="p" tone="subdued">{t(locale, "hreflangNoMarkets")}</Text>
        ) : (
          <BlockStack gap="0">
            {markets.map((m, i) => (
              <MarketRow
                key={i}
                market={m}
                index={i}
                onChange={updateMarket}
                onRemove={removeMarket}
                locale={locale}
              />
            ))}
          </BlockStack>
        )}

        <InlineStack gap="300">
          <Button onClick={addMarket}>{t(locale, "hreflangAddMarket")}</Button>
          <Button variant="primary" onClick={handleSave}>{t(locale, "hreflangSave")}</Button>
          {status.configured && (
            <Button variant="plain" tone="critical" onClick={handleDelete}>
              Supprimer la configuration
            </Button>
          )}
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

function PreviewTab({ preview, locale }: { preview: HreflangPreview; locale: Locale }) {
  if (!preview.available) {
    return (
      <Card>
        <Banner tone="info">
          <Text as="p">{preview.message ?? t(locale, "hreflangNoMarkets")}</Text>
        </Banner>
      </Card>
    );
  }

  return (
    <BlockStack gap="400">
      {preview.pages.map((page) => (
        <Card key={page.path}>
          <BlockStack gap="300">
            <InlineStack gap="200" blockAlign="center">
              <Badge>{page.type}</Badge>
              <Text variant="bodyMd" as="span" fontWeight="medium">{page.path}</Text>
            </InlineStack>
            <Text as="h3" variant="headingXs">
              {locale === "fr" ? "Balises HTML générées" : "Generated HTML tags"}
            </Text>
            <Box background="bg-surface-secondary" padding="300" borderRadius="200">
              <pre
                aria-label={
                  locale === "fr"
                    ? `Balises hreflang HTML pour ${page.path}`
                    : `Hreflang HTML tags for ${page.path}`
                }
                style={{ margin: 0, fontSize: "12px", whiteSpace: "pre-wrap", wordBreak: "break-all" }}
              >
                {page.html}
              </pre>
            </Box>
          </BlockStack>
        </Card>
      ))}
    </BlockStack>
  );
}

function IssuesTab({ issues, locale }: { issues: HreflangIssue[]; locale: Locale }) {
  if (issues.length === 0) {
    return (
      <Card>
        <Banner tone="success">
          <Text as="p">Aucun problème hreflang détecté.</Text>
        </Banner>
      </Card>
    );
  }

  const rows = issues.map((issue) => [
    issueBadge(issue.severity),
    issue.code,
    issue.message,
  ]);

  return (
    <Card>
      <DataTable
        columnContentTypes={["text", "text", "text"]}
        headings={[t(locale, "status"), "Code", "Message"]}
        rows={rows}
      />
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HreflangPage() {
  const { status, preview, locale, shop } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const submit = useSubmit();
  const [selectedTab, setSelectedTab] = useState(0);

  const allIssues = preview.issues.length > 0 ? preview.issues : [];

  const tabs = [
    { id: "config", content: t(locale, "hreflangConfig"), panelID: "config-panel" },
    { id: "preview", content: t(locale, "hreflangPreview"), panelID: "preview-panel" },
    { id: "issues", content: `${t(locale, "hreflangIssues")} (${allIssues.length})`, panelID: "issues-panel" },
  ];

  return (
    <Page
      title={t(locale, "hreflang")}
      subtitle={t(locale, "hreflangSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        {actionData?.error && (
          <Banner tone="critical">
            <Text as="p">{actionData.error}</Text>
          </Banner>
        )}
        {actionData?.saved && (
          <Banner tone="success">
            <Text as="p">Marchés enregistrés avec succès.</Text>
          </Banner>
        )}
        {actionData?.deleted && (
          <Banner tone="info">
            <Text as="p">Configuration hreflang supprimée.</Text>
          </Banner>
        )}

        <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
          <Box paddingBlockStart="400">
            {selectedTab === 0 && (
              <ConfigTab status={status} locale={locale} submit={submit} />
            )}
            {selectedTab === 1 && (
              <PreviewTab preview={preview} locale={locale} />
            )}
            {selectedTab === 2 && (
              <IssuesTab issues={allIssues} locale={locale} />
            )}
          </Box>
        </Tabs>
      </BlockStack>
    </Page>
  );
}
