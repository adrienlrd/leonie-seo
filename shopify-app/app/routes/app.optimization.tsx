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

export default function OptimizationHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };

  const items: HubItem[] = [
    {
      titleKey: "review",
      href: "/app/review",
      description:
        locale === "fr"
          ? "Suggestions IA générées : à approuver, rejeter ou ajuster avant publication."
          : "AI-generated suggestions to approve, reject, or adjust before publishing.",
    },
    {
      titleKey: "descriptions",
      href: "/app/descriptions",
      description:
        locale === "fr"
          ? "Réécriture des descriptions produits pour plus de clarté et de conversion."
          : "Rewrite product descriptions for clarity and conversion.",
    },
    {
      titleKey: "altText",
      href: "/app/alt-text",
      description:
        locale === "fr"
          ? "Génération de textes alternatifs accessibles pour vos images produits."
          : "Generate accessible alternative text for your product images.",
    },
    {
      titleKey: "internalLinks",
      href: "/app/internal-links",
      description:
        locale === "fr"
          ? "Suggestions de maillage interne entre produits et collections."
          : "Internal link suggestions across products and collections.",
    },
    {
      titleKey: "redirects",
      href: "/app/redirects",
      description:
        locale === "fr"
          ? "Gestion des redirections 301 pour préserver le SEO lors des changements d'URL."
          : "301 redirect management to preserve SEO when URLs change.",
    },
    {
      titleKey: "rollback",
      href: "/app/rollback",
      description:
        locale === "fr"
          ? "Annuler une modification appliquée si le résultat ne correspond pas."
          : "Roll back an applied change if the result is not what you expected.",
    },
  ];

  return (
    <Page
      title={t(locale, "hubOptimization")}
      subtitle={t(locale, "hubOptimizationSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        <HubGrid items={items} locale={locale} />
      </BlockStack>
    </Page>
  );
}
