import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Badge, BlockStack, Button, Card, Divider, InlineStack, Select, Text, Tooltip } from "@shopify/polaris";
import { useNavigation, useRevalidator, useSubmit, type FetcherWithComponents } from "@remix-run/react";
import { GlobeIcon, RefreshIcon } from "@shopify/polaris-icons";
import { SectionTitle } from "../lib/marketAnalysisShared";
import { t, type Locale } from "../lib/i18n";
import type { GA4Property, GA4Status, GSCStatus, OnboardingActionData } from "./onboarding/types";

interface Props {
  locale: Locale;
  gsc: GSCStatus | null;
  ga4: GA4Status | null;
  /** GA4 properties to choose from, fetched when GA4 is authorized but no property is set. */
  ga4Properties?: GA4Property[];
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
  /** Extra content rendered inside the same card, below the connection controls. */
  footer?: ReactNode;
}

/** GSC + GA4 connection status, connect and disconnect controls. Reused by onboarding and Réglages. */
export function GoogleConnectionsCard({
  locale,
  gsc,
  ga4,
  ga4Properties = [],
  legacyActionData,
  title,
  description,
  actionPath,
  onContinue,
  fetcher,
  footer,
}: Props) {
  const submit = useSubmit();
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  const [selectedProperty, setSelectedProperty] = useState("");
  const busy = fetcher ? fetcher.state !== "idle" : navigation.state !== "idle";
  const submittingAction = String(
    (fetcher ? fetcher.formData?.get("intent") : navigation.formData?.get("intent")) || "",
  );
  const actionData = fetcher ? fetcher.data : legacyActionData;
  const gscConnected = Boolean(gsc?.connected);
  const ga4Ready = Boolean(ga4?.ready);
  const ga4OauthPending = Boolean(ga4?.oauth_connected) && !ga4Ready;

  // The GA4 API can return the same property several times (one per data
  // stream/account link); duplicates make the picker ambiguous.
  const uniqueProperties = useMemo(() => {
    const seen = new Set<string>();
    return ga4Properties.filter((p) => {
      if (seen.has(p.property_id)) return false;
      seen.add(p.property_id);
      return true;
    });
  }, [ga4Properties]);
  const labelCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of uniqueProperties) {
      const label = p.account_name ? `${p.property_name} — ${p.account_name}` : p.property_name;
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    return counts;
  }, [uniqueProperties]);

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

  const submitGa4Property = (propertyId?: string) => {
    const prop = uniqueProperties.find((p) => p.property_id === (propertyId ?? selectedProperty));
    if (!prop) return;
    const payload = {
      intent: "ga4_select_property",
      property_id: prop.property_id,
      property_name: prop.property_name,
    };
    if (fetcher) {
      const fd = new FormData();
      Object.entries(payload).forEach(([k, v]) => fd.set(k, v));
      fetcher.submit(fd, { method: "post", action: actionPath });
      return;
    }
    submit(payload, actionPath ? { method: "post", action: actionPath } : { method: "post" });
  };

  // One single GA4 property → nothing to choose: select it automatically so the
  // connection completes without leaving GA4 half-connected behind the merchant.
  const autoSelectedRef = useRef(false);
  useEffect(() => {
    if (autoSelectedRef.current || !ga4OauthPending || uniqueProperties.length !== 1) return;
    autoSelectedRef.current = true;
    submitGa4Property(uniqueProperties[0].property_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ga4OauthPending, uniqueProperties]);

  // When using a fetcher (no full navigation), re-fetch status after saving the
  // GA4 property so the card flips to "connected" without a manual reload.
  useEffect(() => {
    if (fetcher?.data?.ga4PropertySaved) revalidator.revalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher?.data?.ga4PropertySaved]);

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
            uniqueProperties.length > 1 ? (
              <InlineStack gap="200" blockAlign="end" wrap>
                <Select
                  label={t(locale, "onboardingGA4PropertyPending")}
                  options={[
                    { label: t(locale, "ga4SelectPropertyPlaceholder"), value: "" },
                    ...uniqueProperties.map((p) => {
                      const base = p.account_name
                        ? `${p.property_name} — ${p.account_name}`
                        : p.property_name;
                      // Same display name on several properties → append the id
                      // so the merchant can tell them apart.
                      const label =
                        (labelCounts.get(base) ?? 0) > 1 ? `${base} (${p.property_id})` : base;
                      return { label, value: p.property_id };
                    }),
                  ]}
                  value={selectedProperty}
                  onChange={setSelectedProperty}
                />
                <Button
                  variant="primary"
                  disabled={!selectedProperty}
                  loading={busy && submittingAction === "ga4_select_property"}
                  onClick={() => submitGa4Property()}
                >
                  {t(locale, "ga4SelectPropertyConfirm")}
                </Button>
              </InlineStack>
            ) : (
              <Badge tone="info">{t(locale, "onboardingGA4PropertyPending")}</Badge>
            )
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

        {footer && (
          <>
            <Divider />
            {footer}
          </>
        )}
      </BlockStack>
    </Card>
  );
}
