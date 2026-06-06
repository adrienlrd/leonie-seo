import { useEffect } from "react";
import { useFetcher } from "@remix-run/react";
import {
  Badge,
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

/**
 * Compact dashboard panel showing the AI files (llms.txt + llms-full.txt)
 * publication status. Publishing itself happens on the /app/geo-llms-txt page,
 * where the merchant sees exactly which files are written and confirms — so
 * this panel only links there and never writes to the theme directly.
 */
export function LlmsTxtPanel({ locale }: { locale: Locale }) {
  const statusFetcher = useFetcher<{ status: LlmsTxtStatus | null }>();

  useEffect(() => {
    if (statusFetcher.state === "idle" && !statusFetcher.data) {
      statusFetcher.load("/app/geo-llms-txt");
    }
  }, [statusFetcher]);

  const status = statusFetcher.data?.status ?? null;
  const published = Boolean(status?.is_published);
  const divergent = Boolean(status?.divergent);

  const badge = published ? (
    divergent ? (
      <Badge tone="attention">{t(locale, "llmsTxtStatusDivergent")}</Badge>
    ) : (
      <Badge tone="success">{t(locale, "llmsTxtStatusPublished")}</Badge>
    )
  ) : (
    <Badge>{t(locale, "llmsTxtStatusNotPublished")}</Badge>
  );

  const buttonLabel = published
    ? t(locale, "llmsTxtManage")
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

        <InlineStack gap="300" blockAlign="center">
          <Button variant="primary" url="/app/geo-llms-txt">
            {buttonLabel}
          </Button>
          {published && status?.public_url && (
            <Button url={status.public_url} target="_blank" variant="plain">
              {t(locale, "llmsTxtOpenFile")}
            </Button>
          )}
        </InlineStack>

        <Text as="p" variant="bodySm" tone="subdued">
          {t(locale, "llmsTxtAutoUpdate")}
        </Text>
      </BlockStack>
    </Card>
  );
}
