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
  InlineStack,
  List,
  Page,
  Text,
} from "@shopify/polaris";
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
  const segment = INTENT_SEGMENTS[intent];
  if (!segment) {
    return json<ActionResult>({ ok: false, intent, error: "unknown_intent" }, { status: 400 });
  }

  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/llms-txt/${segment}`,
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
  const [preview, setPreview] = useState<string | null>(null);

  const busy = fetcher.state !== "idle";
  const data = fetcher.data;

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
      : published
        ? t(locale, "llmsTxtRepublish")
        : t(locale, "llmsTxtPublish");

  return (
    <Page title={t(locale, "llmsTxtTitle")}>
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

            <InlineStack gap="300">
              <Button
                variant="primary"
                loading={busy && fetcher.formData?.get("intent") === "publish"}
                disabled={busy}
                onClick={() => submit("publish")}
              >
                {publishLabel}
              </Button>
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
