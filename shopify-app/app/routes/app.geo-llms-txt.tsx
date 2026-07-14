import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  Checkbox,
  InlineGrid,
  InlineStack,
  List,
  Page,
  Text,
} from "@shopify/polaris";
import { PlanBadge } from "../components/PlanBadge";
import { useEffect, useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, t, type Locale } from "../lib/i18n";

interface LlmsTxtStatus {
  is_published: boolean;
  divergent: boolean;
  public_url: string;
  public_full_url: string;
  public_agents_url: string;
  last_published_at: string | null;
  theme_write_mode?: string;
  allowed_files?: string[];
  crawler_prefs?: CrawlerPrefs;
  known_agents?: string[];
}

interface CrawlerPrefs {
  include_products: boolean;
  include_collections: boolean;
  include_pages: boolean;
  welcomed_agents: string[];
}

interface ActionResult {
  ok: boolean;
  intent: string;
  status?: number;
  error?: string;
  result?: {
    llms_txt?: string;
    public_url?: string;
    public_full_url?: string;
    public_agents_url?: string;
    warnings?: string[];
    unpublished?: boolean;
  };
}

const INTENT_SEGMENTS: Record<string, string> = {
  generate: "generate",
  publish: "publish",
  unpublish: "unpublish",
};

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  let status: LlmsTxtStatus | null = null;
  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/llms-txt/status`,
      { accessToken: session.accessToken },
    );
    if (resp.ok) status = (await resp.json()) as LlmsTxtStatus;
  } catch (err) {
    console.error("[llms-txt] status load failed:", err);
  }
  return json({ locale, status });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const intent = String(form.get("intent") ?? "");

  // Save AI crawler preferences (content filters + welcomed agents).
  if (intent === "save-prefs") {
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/llms-txt/crawler-prefs`,
        {
          method: "PUT",
          accessToken: session.accessToken,
          body: String(form.get("prefs_json") ?? "{}"),
        },
      );
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        return json<ActionResult>({ ok: false, intent, status: resp.status, error: "error" });
      }
      return json<ActionResult>({ ok: true, intent, result: data });
    } catch (err) {
      console.error("[llms-txt] save-prefs failed:", err);
      return json<ActionResult>({ ok: false, intent, error: String(err) });
    }
  }

  const segment = INTENT_SEGMENTS[intent];
  if (!segment) {
    return json<ActionResult>({ ok: false, intent, error: "unknown_intent" }, { status: 400 });
  }

  // Publishing requires explicit merchant confirmation (the UI gates this
  // behind a checkbox). Forward confirm=true only for the publish intent.
  const confirmed = intent === "publish" && String(form.get("confirm") ?? "") === "true";
  const query = intent === "publish" ? `?confirm=${confirmed}` : "";

  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/llms-txt/${segment}${query}`,
      { method: "POST", accessToken: session.accessToken },
    );
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      return json<ActionResult>({
        ok: false,
        intent,
        status: resp.status,
        error: (data as { detail?: string }).detail ?? "error",
      });
    }
    return json<ActionResult>({ ok: true, intent, result: data });
  } catch (err) {
    console.error(`[llms-txt] ${intent} failed:`, err);
    return json<ActionResult>({ ok: false, intent, error: String(err) });
  }
};

export default function LlmsTxtPage() {
  const { locale, status } = useLoaderData<typeof loader>() as {
    locale: Locale;
    status: LlmsTxtStatus | null;
  };
  const fetcher = useFetcher<ActionResult>();
  const prefsFetcher = useFetcher<ActionResult>();
  const [preview, setPreview] = useState<string | null>(null);
  const [confirmChecked, setConfirmChecked] = useState(Boolean(status?.is_published));

  const knownAgents = status?.known_agents ?? [];
  const [prefs, setPrefs] = useState<CrawlerPrefs>(
    status?.crawler_prefs ?? {
      include_products: true,
      include_collections: true,
      include_pages: true,
      welcomed_agents: knownAgents,
    },
  );
  const savePrefs = () => {
    const fd = new FormData();
    fd.set("intent", "save-prefs");
    fd.set("prefs_json", JSON.stringify(prefs));
    prefsFetcher.submit(fd, { method: "post" });
  };
  const toggleAgent = (agent: string, checked: boolean) => {
    setPrefs((p) => ({
      ...p,
      welcomed_agents: checked
        ? [...p.welcomed_agents, agent]
        : p.welcomed_agents.filter((a) => a !== agent),
    }));
  };

  const busy = fetcher.state !== "idle";
  const data = fetcher.data;

  const themeWriteMode = status?.theme_write_mode ?? "review_safe";
  const writesDisabled = themeWriteMode === "disabled";
  const allowedFiles = status?.allowed_files ?? [
    "templates/agents.md.liquid",
    "templates/llms.txt.liquid",
    "templates/llms-full.txt.liquid",
  ];

  useEffect(() => {
    if (data?.ok && data.intent === "generate" && data.result?.llms_txt) {
      setPreview(data.result.llms_txt);
    }
  }, [data]);

  const published = data?.ok && data.intent === "publish" ? true : Boolean(status?.is_published);
  const divergent = Boolean(status?.divergent);
  const publicUrl =
    data?.result?.public_url ?? status?.public_url ?? "";
  const warnings = data?.result?.warnings ?? [];

  const submit = (intent: string) => {
    const fd = new FormData();
    fd.set("intent", intent);
    fetcher.submit(fd, { method: "post" });
  };

  const submitPublish = () => {
    const fd = new FormData();
    fd.set("intent", "publish");
    fd.set("confirm", "true");
    fetcher.submit(fd, { method: "post" });
  };

  const statusBadge = published ? (
    divergent ? (
      <Badge tone="attention">{t(locale, "llmsTxtStatusDivergent")}</Badge>
    ) : (
      <Badge tone="success">{t(locale, "llmsTxtStatusPublished")}</Badge>
    )
  ) : (
    <Badge>{t(locale, "llmsTxtStatusNotPublished")}</Badge>
  );

  const publishLabel =
    busy && fetcher.formData?.get("intent") === "publish"
      ? t(locale, "llmsTxtPublishing")
      : t(locale, "llmsTxtPublishCta");

  return (
    <Page title={t(locale, "llmsTxtTitle")} titleMetadata={<PlanBadge />}>
      <BlockStack gap="400">
        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center">
              <Text as="h2" variant="headingMd">
                {t(locale, "llmsTxtTitle")}
              </Text>
              {statusBadge}
            </InlineStack>

            <Text as="p" tone="subdued">
              {t(locale, "llmsTxtIntro")}
            </Text>

            {data && !data.ok && (
              <Banner tone="critical">
                <p>{data.error ?? t(locale, "llmsTxtError")}</p>
              </Banner>
            )}

            {data?.ok && data.intent === "publish" && (
              <Banner tone="success">
                <p>{t(locale, "llmsTxtPublished")}</p>
              </Banner>
            )}

            {warnings.length > 0 && (
              <Banner tone="warning" title={t(locale, "llmsTxtWarnings")}>
                <List type="bullet">
                  {warnings.map((w) => (
                    <List.Item key={w}>{w}</List.Item>
                  ))}
                </List>
              </Banner>
            )}

            {writesDisabled && (
              <Banner tone="info" title={t(locale, "llmsTxtDisabledTitle")}>
                <p>{t(locale, "llmsTxtDisabledBody")}</p>
              </Banner>
            )}

            <Box
              background="bg-surface-secondary"
              padding="300"
              borderRadius="200"
            >
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">
                  {t(locale, "llmsTxtConfirmTitle")}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "llmsTxtConfirmFilesIntro")}
                </Text>
                <List type="bullet">
                  {allowedFiles.map((f) => (
                    <List.Item key={f}>{f}</List.Item>
                  ))}
                </List>
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "llmsTxtConfirmNoOther")}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "llmsTxtConfirmRemovable")}
                </Text>
                <Checkbox
                  label={t(locale, "llmsTxtConfirmCheckbox")}
                  checked={confirmChecked}
                  disabled={writesDisabled || busy}
                  onChange={setConfirmChecked}
                />
                <InlineStack gap="300">
                  <Button
                    variant="primary"
                    loading={busy && fetcher.formData?.get("intent") === "publish"}
                    disabled={busy || writesDisabled || !confirmChecked}
                    onClick={submitPublish}
                  >
                    {publishLabel}
                  </Button>
                </InlineStack>
              </BlockStack>
            </Box>

            <InlineStack gap="300">
              <Button
                loading={busy && fetcher.formData?.get("intent") === "generate"}
                disabled={busy}
                onClick={() => submit("generate")}
              >
                {t(locale, "llmsTxtGenerate")}
              </Button>
              {published && (
                <Button
                  tone="critical"
                  loading={busy && fetcher.formData?.get("intent") === "unpublish"}
                  disabled={busy}
                  onClick={() => submit("unpublish")}
                >
                  {t(locale, "llmsTxtUnpublish")}
                </Button>
              )}
            </InlineStack>

            {published && publicUrl && (
              <InlineStack gap="300">
                <Button url={publicUrl} target="_blank" variant="plain">
                  {t(locale, "llmsTxtOpenFile")}
                </Button>
                <Button
                  url={status?.public_full_url ?? publicUrl.replace("/llms.txt", "/llms-full.txt")}
                  target="_blank"
                  variant="plain"
                >
                  {t(locale, "llmsTxtOpenFullFile")}
                </Button>
                <Button
                  url={status?.public_agents_url ?? publicUrl.replace("/llms.txt", "/agents.md")}
                  target="_blank"
                  variant="plain"
                >
                  {t(locale, "llmsTxtOpenAgents")}
                </Button>
              </InlineStack>
            )}

            <Text as="p" variant="bodySm" tone="subdued">
              {t(locale, "llmsTxtAutoUpdate")}
            </Text>
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">
              {t(locale, "llmsTxtPrefsTitle")}
            </Text>
            <Text as="p" tone="subdued">
              {t(locale, "llmsTxtPrefsIntro")}
            </Text>

            {prefsFetcher.data?.ok && prefsFetcher.data.intent === "save-prefs" && (
              <Banner tone="success">
                <p>{t(locale, "llmsTxtPrefsSaved")}</p>
              </Banner>
            )}

            <BlockStack gap="100">
              <Checkbox
                label={t(locale, "llmsTxtPrefsProducts")}
                checked={prefs.include_products}
                onChange={(v) => setPrefs((p) => ({ ...p, include_products: v }))}
              />
              <Checkbox
                label={t(locale, "llmsTxtPrefsCollections")}
                checked={prefs.include_collections}
                onChange={(v) => setPrefs((p) => ({ ...p, include_collections: v }))}
              />
              <Checkbox
                label={t(locale, "llmsTxtPrefsPages")}
                checked={prefs.include_pages}
                onChange={(v) => setPrefs((p) => ({ ...p, include_pages: v }))}
              />
            </BlockStack>

            {knownAgents.length > 0 && (
              <BlockStack gap="100">
                <Text as="p" variant="bodySm" fontWeight="semibold">
                  {t(locale, "llmsTxtPrefsAgents")}
                </Text>
                <InlineGrid columns={3} gap="100">
                  {knownAgents.map((agent) => (
                    <Checkbox
                      key={agent}
                      label={agent}
                      checked={prefs.welcomed_agents.includes(agent)}
                      onChange={(v) => toggleAgent(agent, v)}
                    />
                  ))}
                </InlineGrid>
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "llmsTxtPrefsAgentsNote")}
                </Text>
              </BlockStack>
            )}

            <InlineStack>
              <Button
                loading={prefsFetcher.state !== "idle"}
                disabled={prefsFetcher.state !== "idle"}
                onClick={savePrefs}
              >
                {t(locale, "llmsTxtPrefsSave")}
              </Button>
            </InlineStack>
          </BlockStack>
        </Card>

        {preview && (
          <Card>
            <BlockStack gap="200">
              <Text as="h3" variant="headingSm">
                {t(locale, "llmsTxtPreviewTitle")}
              </Text>
              <Box
                background="bg-surface-secondary"
                padding="300"
                borderRadius="200"
                overflowX="scroll"
              >
                <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>
                  {preview}
                </pre>
              </Box>
            </BlockStack>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
