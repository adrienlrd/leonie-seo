import { BlockStack, Button, Card, Text } from "@shopify/polaris";
import { useSubmit, useNavigation } from "@remix-run/react";
import { t, type Locale } from "../../lib/i18n";
import type { OnboardingActionData } from "./types";

interface Props {
  locale: Locale;
  recentJobs: number;
  actionData: OnboardingActionData | undefined;
}

/** Right card: quick job stats + "run audit now" CTA. */
export function AuditLauncherCard({ locale, recentJobs, actionData }: Props) {
  const submit = useSubmit();
  const navigation = useNavigation();

  return (
    <Card>
      <BlockStack gap="300">
        <Text as="h2" variant="headingMd">
          {t(locale, "jobs")}
        </Text>
        <Text as="p" variant="headingLg">
          {recentJobs}
        </Text>
        <Button
          variant="primary"
          loading={navigation.state !== "idle"}
          onClick={() => submit({}, { method: "post" })}
        >
          {t(locale, "launchAudit")}
        </Button>
        {actionData?.jobId && (
          <Text as="p" tone="success">
            {t(locale, "jobQueued")} {actionData.jobId.slice(0, 8)}
          </Text>
        )}
        {actionData?.error && (
          <Text as="p" tone="critical">
            {actionData.error}
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}
