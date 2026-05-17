import { Badge, BlockStack, Button, Card, InlineStack, Text } from "@shopify/polaris";
import { useSubmit, useNavigation } from "@remix-run/react";
import type { Locale } from "../../lib/i18n";
import type { GSCStatus, OnboardingActionData } from "./types";

interface Props {
  locale: Locale;
  gsc: GSCStatus | null;
  actionData: OnboardingActionData | undefined;
}

/** Google Search Console connection and historical import. */
export function GoogleSearchConsoleCard({ locale, gsc, actionData }: Props) {
  const submit = useSubmit();
  const navigation = useNavigation();
  const fr = locale === "fr";

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between">
          <Text as="h2" variant="headingMd">
            Google Search Console
          </Text>
          <Badge tone={gsc?.connected ? "success" : "warning"}>
            {gsc?.connected
              ? fr ? "Connectée" : "Connected"
              : fr ? "À connecter" : "Not connected"}
          </Badge>
        </InlineStack>

        {gsc?.connected ? (
          <BlockStack gap="100">
            <Text as="p" tone="subdued">
              {`${fr ? "Compte" : "Account"} : ${gsc.email ?? "—"}`}
            </Text>
            <Text as="p" tone="subdued">
              {`${fr ? "Propriété" : "Property"} : ${gsc.site_url ?? "—"}`}
            </Text>
            {gsc.latest_import.available && (
              <Text as="p" tone="subdued">
                {`${fr ? "Dernier import" : "Last import"} : ${
                  gsc.latest_import.row_count
                } ${fr ? "lignes" : "rows"}`}
              </Text>
            )}
          </BlockStack>
        ) : (
          <BlockStack gap="100">
            <Text as="p" tone="subdued">
              {fr
                ? "Connectez votre compte Google pour importer vos données de recherche (requêtes, impressions, positions)."
                : "Connect your Google account to import your search data (queries, impressions, positions)."}
            </Text>
            {!gsc?.configured && (
              <Text as="p" tone="critical" variant="bodySm">
                {fr
                  ? "Connexion Google indisponible — contactez le support."
                  : "Google connection unavailable — please contact support."}
              </Text>
            )}
          </BlockStack>
        )}

        <InlineStack gap="300" wrap>
          {!gsc?.connected && (
            <Button
              variant="primary"
              disabled={!gsc?.configured}
              loading={navigation.state !== "idle"}
              onClick={() => submit({ intent: "gsc_connect" }, { method: "post" })}
            >
              {fr ? "Connecter Google Search Console" : "Connect Google Search Console"}
            </Button>
          )}
          <Button
            disabled={!gsc?.connected}
            loading={navigation.state !== "idle"}
            onClick={() => submit({ intent: "gsc_import" }, { method: "post" })}
          >
            {gsc?.latest_import.available
              ? fr ? "Réimporter 90 jours" : "Reimport 90 days"
              : fr ? "Importer 90 jours" : "Import 90 days"}
          </Button>
        </InlineStack>

        {actionData?.authorizationUrl && (
          <Text as="p" tone="subdued" variant="bodySm">
            {fr
              ? "Une fenêtre Google s'est ouverte. Si elle est bloquée, "
              : "A Google window has opened. If it's blocked, "}
            <a href={actionData.authorizationUrl} target="_blank" rel="noreferrer">
              {fr ? "cliquez ici" : "click here"}
            </a>
            .
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}
