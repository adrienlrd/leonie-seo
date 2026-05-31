import { useEffect } from "react";
import { useFetcher } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  InlineStack,
  Text,
} from "@shopify/polaris";
import { t, type Locale } from "../lib/i18n";

interface LlmsTxtStatus {
  is_published: boolean;
  divergent: boolean;
  public_url: string;
}

interface ActionResult {
  ok: boolean;
  intent: string;
  error?: string;
  result?: { public_url?: string };
}

/**
 * Compact dashboard panel: lets the merchant publish/update the AI files
 * (llms.txt + llms-full.txt) in one click. The heavy lifting lives in the
 * /app/geo-llms-txt route; this panel reuses its loader + action via fetchers.
 */
export function LlmsTxtPanel({ locale }: { locale: Locale }) {
  const statusFetcher = useFetcher<{ status: LlmsTxtStatus | null }>();
  const actionFetcher = useFetcher<ActionResult>();

  useEffect(() => {
    if (statusFetcher.state === "idle" && !statusFetcher.data) {
      statusFetcher.load("/app/geo-llms-txt");
    }
  }, [statusFetcher]);

  // Refresh status after a successful publish/unpublish.
  useEffect(() => {
    if (actionFetcher.state === "idle" && actionFetcher.data?.ok) {
      statusFetcher.load("/app/geo-llms-txt");
    }
  }, [actionFetcher.state, actionFetcher.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const status = statusFetcher.data?.status ?? null;
  const published = Boolean(status?.is_published);
  const divergent = Boolean(status?.divergent);
  const publishing = actionFetcher.state !== "idle";

  const submitPublish = () => {
    const fd = new FormData();
    fd.set("intent", "publish");
    actionFetcher.submit(fd, { method: "post", action: "/app/geo-llms-txt" });
  };

  const badge = published ? (
    divergent ? (
      <Badge tone="attention">{t(locale, "llmsTxtStatusDivergent")}</Badge>
    ) : (
      <Badge tone="success">{t(locale, "llmsTxtStatusPublished")}</Badge>
    )
  ) : (
    <Badge>{t(locale, "llmsTxtStatusNotPublished")}</Badge>
  );

  const buttonLabel = publishing
    ? t(locale, "llmsTxtPublishing")
    : published
      ? t(locale, "llmsTxtRepublish")
      : t(locale, "llmsTxtPublish");

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <Text as="h2" variant="headingMd">
            {t(locale, "llmsTxtTitle")}
          </Text>
          {badge}
        </InlineStack>

        <Text as="p" tone="subdued">
          {t(locale, "llmsTxtIntro")}
        </Text>

        {actionFetcher.data && !actionFetcher.data.ok && (
          <Banner tone="critical">
            <p>{actionFetcher.data.error ?? t(locale, "llmsTxtError")}</p>
          </Banner>
        )}

        {actionFetcher.data?.ok && actionFetcher.data.intent === "publish" && (
          <Banner tone="success">
            <p>{t(locale, "llmsTxtPublished")}</p>
          </Banner>
        )}

        <InlineStack gap="300" blockAlign="center">
          <Button
            variant="primary"
            loading={publishing}
            disabled={publishing}
            onClick={submitPublish}
          >
            {buttonLabel}
          </Button>
          {published && status?.public_url && (
            <Button url={status.public_url} target="_blank" variant="plain">
              {t(locale, "llmsTxtOpenFile")}
            </Button>
          )}
          <Button url="/app/geo-llms-txt" variant="plain">
            {t(locale, "llmsTxtManage")}
          </Button>
        </InlineStack>

        <Text as="p" variant="bodySm" tone="subdued">
          {t(locale, "llmsTxtAutoUpdate")}
        </Text>
      </BlockStack>
    </Card>
  );
}
