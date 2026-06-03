import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import { Banner, BlockStack, Box, Button, Card, Divider, InlineStack, Page, Text } from "@shopify/polaris";
import { useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { HubGrid, type HubItem } from "../components/HubGrid";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return json({ locale: getLocale(request) });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const intent = String(form.get("intent") ?? "");

  if (intent === "resetTags") {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/tags/reset`,
      { accessToken: session.accessToken, method: "DELETE" },
    );
    const data = resp.ok ? (await resp.json()) as { reset: number } : null;
    return json({ type: "resetTags", ok: resp.ok, reset: data?.reset ?? 0 });
  }

  return json({ type: "unknown", ok: false, reset: 0 });
};

export default function AccountHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };
  const fr = locale === "fr";
  const resetFetcher = useFetcher<{ type: string; ok: boolean; reset: number }>();
  const [confirmReset, setConfirmReset] = useState(false);

  const items: HubItem[] = [
    {
      titleKey: "onboarding",
      href: "/app/onboarding",
      description: fr
        ? "Configurez votre boutique étape par étape : Google, audit, performance."
        : "Set up your store step by step: Google, audit, performance.",
    },
    {
      titleKey: "billing",
      href: "/app/billing",
      description: fr
        ? "Plan actuel, facturation et passage Pro ou Agency."
        : "Current plan, billing, and upgrade to Pro or Agency.",
    },
    {
      titleKey: "settings",
      href: "/app/settings",
      description: fr
        ? "Préférences, budget IA, locales multilingues."
        : "Preferences, AI budget, multilingual locales.",
    },
    {
      titleKey: "jobs",
      href: "/app/jobs",
      description: fr
        ? "Suivi des tâches en arrière-plan : analyses, imports, applications."
        : "Monitor background tasks: analyses, imports, apply runs.",
    },
    {
      titleKey: "privacy",
      href: "/app/privacy",
      description: fr
        ? "Confidentialité, export et suppression de vos données (RGPD)."
        : "Privacy, data export, and deletion (GDPR).",
    },
  ];

  const onResetConfirm = () => {
    const fd = new FormData();
    fd.set("intent", "resetTags");
    resetFetcher.submit(fd, { method: "post" });
    setConfirmReset(false);
  };

  return (
    <Page
      title={t(locale, "hubSettings")}
      subtitle={t(locale, "hubSettingsSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="600">
        <HubGrid items={items} locale={locale} />

        <Divider />

        <Card>
          <BlockStack gap="300">
            <BlockStack gap="100">
              <Text as="h2" variant="headingMd">
                {fr ? "Zone de danger" : "Danger zone"}
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                {fr
                  ? "Ces actions sont irréversibles."
                  : "These actions are irreversible."}
              </Text>
            </BlockStack>

            <Box
              padding="400"
              background="bg-surface-critical"
              borderRadius="200"
              borderColor="border-critical"
              borderWidth="025"
            >
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="050">
                  <Text as="p" variant="bodyMd" fontWeight="semibold">
                    {fr ? "Réinitialiser les tags" : "Reset tags"}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {fr
                      ? "Supprime tous les tags ajoutés et retirés pour tous les produits."
                      : "Deletes all added and retired tags for all products."}
                  </Text>
                </BlockStack>
                {!confirmReset ? (
                  <Button tone="critical" onClick={() => setConfirmReset(true)}>
                    {fr ? "Réinitialiser" : "Reset"}
                  </Button>
                ) : (
                  <InlineStack gap="200">
                    <Button variant="plain" onClick={() => setConfirmReset(false)}>
                      {fr ? "Annuler" : "Cancel"}
                    </Button>
                    <Button
                      tone="critical"
                      loading={resetFetcher.state !== "idle"}
                      onClick={onResetConfirm}
                    >
                      {fr ? "Confirmer la réinitialisation" : "Confirm reset"}
                    </Button>
                  </InlineStack>
                )}
              </InlineStack>
            </Box>

            {resetFetcher.data?.ok && (
              <Banner tone="success">
                <Text as="p" variant="bodySm">
                  {fr
                    ? `${resetFetcher.data.reset} tag(s) supprimé(s).`
                    : `${resetFetcher.data.reset} tag(s) deleted.`}
                </Text>
              </Banner>
            )}
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
