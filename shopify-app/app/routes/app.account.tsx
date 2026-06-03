import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { BlockStack, Page } from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { HubGrid, type HubItem } from "../components/HubGrid";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return json({ locale: getLocale(request) });
};

export default function AccountHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };

  const items: HubItem[] = [
    {
      titleKey: "onboarding",
      href: "/app/onboarding",
      description:
        locale === "fr"
          ? "Configurez votre boutique étape par étape : Google, audit, performance."
          : "Set up your store step by step: Google, audit, performance.",
    },
    {
      titleKey: "billing",
      href: "/app/billing",
      description:
        locale === "fr"
          ? "Plan actuel, facturation et passage Pro ou Agency."
          : "Current plan, billing, and upgrade to Pro or Agency.",
    },
    {
      titleKey: "settings",
      href: "/app/settings",
      description:
        locale === "fr"
          ? "Préférences, budget IA, locales multilingues."
          : "Preferences, AI budget, multilingual locales.",
    },
    {
      titleKey: "jobs",
      href: "/app/jobs",
      description:
        locale === "fr"
          ? "Suivi des tâches en arrière-plan : analyses, imports, applications."
          : "Monitor background tasks: analyses, imports, apply runs.",
    },
    {
      titleKey: "privacy",
      href: "/app/privacy",
      description:
        locale === "fr"
          ? "Confidentialité, export et suppression de vos données (RGPD)."
          : "Privacy, data export, and deletion (GDPR).",
    },
  ];

  return (
    <Page
      title={t(locale, "hubSettings")}
      subtitle={t(locale, "hubSettingsSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        <HubGrid items={items} locale={locale} />
      </BlockStack>
    </Page>
  );
}
