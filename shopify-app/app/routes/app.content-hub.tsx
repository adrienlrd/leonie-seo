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

export default function ContentHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };

  const items: HubItem[] = [
    {
      titleKey: "content",
      href: "/app/content",
      description:
        locale === "fr"
          ? "FAQ produits prêtes à publier et briefs blog basés sur vos requêtes GSC."
          : "Ready-to-publish product FAQs and blog briefs from your GSC queries.",
    },
    {
      titleKey: "hreflang",
      href: "/app/hreflang",
      description:
        locale === "fr"
          ? "Configuration multimarché et balises hreflang pour vendre à l'international."
          : "Multi-market configuration and hreflang tags for international selling.",
    },
    {
      titleKey: "jsonld",
      href: "/app/jsonld",
      description:
        locale === "fr"
          ? "Données structurées Schema.org pour produits, collections et organisation."
          : "Schema.org structured data for products, collections, and organization.",
    },
    {
      titleKey: "semantics",
      href: "/app/semantics",
      description:
        locale === "fr"
          ? "Analyse sémantique et signaux E-E-A-T pour renforcer votre autorité."
          : "Semantic analysis and E-E-A-T signals to strengthen authority.",
    },
    {
      titleKey: "niche",
      href: "/app/niche",
      description:
        locale === "fr"
          ? "Clusters produits, écarts de mots-clés et intentions de recherche par niche."
          : "Product clusters, keyword gaps, and search intents per niche.",
    },
  ];

  return (
    <Page
      title={t(locale, "hubContent")}
      subtitle={t(locale, "hubContentSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        <HubGrid items={items} locale={locale} />
      </BlockStack>
    </Page>
  );
}
