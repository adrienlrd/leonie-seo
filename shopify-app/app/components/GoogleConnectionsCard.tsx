import { Badge, BlockStack, Button, Card, InlineStack, Text, Tooltip } from "@shopify/polaris";
import { useNavigation, useRevalidator, useSubmit, type FetcherWithComponents } from "@remix-run/react";
import { GlobeIcon, RefreshIcon } from "@shopify/polaris-icons";
import { SectionTitle } from "../lib/marketAnalysisShared";
import { t, type Locale } from "../lib/i18n";
import type { GA4Status, GSCStatus, OnboardingActionData } from "./onboarding/types";

interface Props {
  locale: Locale;
  gsc: GSCStatus | null;
  ga4: GA4Status | null;
  legacyActionData?: OnboardingActionData;
  title: string;
  description: string;
  /** Route the connect/disconnect intents are submitted to (defaults to the current route). */
  actionPath?: string;
  /** Shown only when provided (used by the onboarding wizard to advance to the next step). */
  onContinue?: () => void;
  /**
   * When provided, intents are submitted via this fetcher (no full navigation) — used when this
   * card is rendered on a route other than the one owning the GSC/GA4 connect action intents.
   */
  fetcher?: FetcherWithComponents<OnboardingActionData>;
}

/** GSC + GA4 connection status, connect and disconnect controls. Reused by onboarding and Réglages. */
export function GoogleConnectionsCard({
  locale,
  gsc,
  ga4,
  legacyActionData,
  title,
  description,
  actionPath,
  onContinue,
  fetcher,
}: Props) {
  const submit = useSubmit();
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  const busy = fetcher ? fetcher.state !== "idle" : navigation.state !== "idle";
  const submittingAction = String(
    (fetcher ? fetcher.formData?.get("intent") : navigation.formData?.get("intent")) || "",
  );
  const actionData = fetcher ? fetcher.data : legacyActionData;
  const gscConnected = Boolean(gsc?.connected);
  const ga4Ready = Boolean(ga4?.ready);
  const ga4OauthPending = Boolean(ga4?.oauth_connected) && !ga4Ready;

  const submitIntent = (intent: string) => {
    if (fetcher) {
      const fd = new FormData();
      fd.set("intent", intent);
      fetcher.submit(fd, { method: "post", action: actionPath });
      return;
    }
    submit(
      { intent },
      actionPath ? { method: "post", action: actionPath } : { method: "post" },
    );
  };

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap={false}>
          <SectionTitle source={GlobeIcon}>{title}</SectionTitle>
          <Tooltip content={t(locale, "dashboardRefresh")}>
            <Button
              icon={RefreshIcon}
              variant="tertiary"
              loading={revalidator.state === "loading"}
              onClick={() => revalidator.revalidate()}
              accessibilityLabel={t(locale, "dashboardRefresh")}
            />
          </Tooltip>
        </InlineStack>
        <Text as="p" tone="subdued">
          {description}
        </Text>

        <InlineStack gap="300" wrap blockAlign="center">
          {gscConnected ? (
            <InlineStack gap="200" blockAlign="center">
              <Badge tone="success">{t(locale, "onboardingGSCConnected")}</Badge>
              <Button
                variant="plain"
                tone="critical"
                loading={busy && submittingAction === "gsc_disconnect"}
                onClick={() => submitIntent("gsc_disconnect")}
              >
                {t(locale, "onboardingDisconnectGSC")}
              </Button>
            </InlineStack>
          ) : (
            <Button
              variant="primary"
              disabled={!gsc?.configured}
              loading={busy && submittingAction === "gsc_connect"}
              onClick={() => submitIntent("gsc_connect")}
            >
              {t(locale, "onboardingConnectGSC")}
            </Button>
          )}

          {ga4Ready ? (
            <InlineStack gap="200" blockAlign="center">
              <Badge tone="success">{t(locale, "onboardingGA4Connected")}</Badge>
              <Button
                variant="plain"
                tone="critical"
                loading={busy && submittingAction === "ga4_disconnect"}
                onClick={() => submitIntent("ga4_disconnect")}
              >
                {t(locale, "onboardingDisconnectGA4")}
              </Button>
            </InlineStack>
          ) : ga4OauthPending ? (
            <Badge tone="info">{t(locale, "onboardingGA4PropertyPending")}</Badge>
          ) : (
            <Button
              loading={busy && submittingAction === "ga4_connect"}
              onClick={() => submitIntent("ga4_connect")}
            >
              {t(locale, "onboardingConnectGA4")}
            </Button>
          )}
        </InlineStack>

        {actionData?.error && (
          <Text as="p" tone="critical">
            {actionData.error}
          </Text>
        )}

        {onContinue && gscConnected && (
          <InlineStack align="end">
            <Button variant="primary" onClick={onContinue}>
              {t(locale, "onboardingGoogleContinue")}
            </Button>
          </InlineStack>
        )}
      </BlockStack>
    </Card>
  );
}
