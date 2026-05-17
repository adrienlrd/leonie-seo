import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Text,
} from "@shopify/polaris";
import { Form, useNavigation } from "@remix-run/react";
import type { Locale } from "../../lib/i18n";
import type { CrawlStatus, OnboardingActionData } from "./types";

interface Props {
  locale: Locale;
  crawl: CrawlStatus | null;
  actionData: OnboardingActionData | undefined;
}

/** Screaming Frog CSV upload + technical crawl summary. */
export function CrawlCard({ locale, crawl, actionData }: Props) {
  const navigation = useNavigation();
  const fr = locale === "fr";

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between">
          <Text as="h2" variant="headingMd">
            {fr ? "Crawl technique" : "Technical crawl"}
          </Text>
          <Badge tone={crawl?.available ? "success" : "warning"}>
            {crawl?.available
              ? `${crawl.url_count} URLs`
              : fr ? "À importer" : "Not imported"}
          </Badge>
        </InlineStack>
        <Text as="p" tone="subdued">
          {fr
            ? "Importez un export CSV Screaming Frog (vue « Internal ») pour détecter les 404, chaînes de redirection, canonicals et titres dupliqués."
            : "Import a Screaming Frog CSV export (Internal view) to detect 404s, redirect chains, canonicals, and duplicate titles."}
        </Text>
        {crawl?.available && (
          <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="300">
            <Text as="p" tone="subdued">
              {fr ? "Problèmes" : "Issues"}: {crawl.issue_count}
            </Text>
            <Text as="p" tone="subdued">
              {fr ? "Critiques" : "Critical"}: {crawl.by_severity?.critical ?? 0}
            </Text>
            <Text as="p" tone="subdued">
              {fr ? "Élevés" : "High"}: {crawl.by_severity?.high ?? 0}
            </Text>
          </InlineGrid>
        )}
        {(crawl?.issues ?? [])
          .filter((i) => i.severity === "critical")
          .slice(0, 3)
          .map((issue) => (
            <BlockStack gap="100" key={issue.url + issue.issue_type}>
              <InlineStack gap="200">
                <Badge tone="critical">{issue.issue_type.replace(/_/g, " ")}</Badge>
                <Text as="span" tone="subdued">
                  {issue.url}
                </Text>
              </InlineStack>
              <Text as="p" tone="subdued">
                {issue.detail}
              </Text>
            </BlockStack>
          ))}
        <Form method="post" encType="multipart/form-data">
          <input type="hidden" name="intent" value="crawl_upload" />
          <BlockStack gap="200">
            <Text as="p" variant="bodySm">
              {fr
                ? "Overview CSV (obligatoire — export « Internal » Screaming Frog)"
                : "Overview CSV (required — Screaming Frog \"Internal\" export)"}
            </Text>
            <input type="file" name="overview" accept=".csv" />
            <Text as="p" variant="bodySm">
              {fr
                ? "CSV codes réponse (optionnel — export « Response Codes » Screaming Frog)"
                : "Response codes CSV (optional — Screaming Frog \"Response Codes\" export)"}
            </Text>
            <input type="file" name="redirects" accept=".csv" />
            <Button submit variant="primary" loading={navigation.state !== "idle"}>
              {fr ? "Analyser le crawl" : "Analyze crawl"}
            </Button>
          </BlockStack>
        </Form>
        {actionData?.error && (
          <Text as="p" tone="critical">
            {actionData.error}
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}
