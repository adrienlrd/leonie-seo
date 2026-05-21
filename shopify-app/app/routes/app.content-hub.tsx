import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { BlockStack, Page } from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";
import { AdvancedToolList, HubGrid, type HubItem } from "../components/HubGrid";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return json({ locale: getLocale(request) });
};

export default function ContentHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };

  const primaryItems: HubItem[] = [
    {
      titleKey: "contentActions",
      href: "/app/content-actions",
      description:
        locale === "fr"
          ? "Générez un brouillon relisible depuis les faits de la boutique."
          : "Generate a reviewable draft from store facts.",
    },
    {
      titleKey: "nicheUnderstanding",
      href: "/app/niche-understanding",
      description:
        locale === "fr"
          ? "Validez ce que Léonie a compris avant de générer des recommandations."
          : "Validate what Léonie understood before generating recommendations.",
    },
    {
      titleKey: "safeApply",
      href: "/app/safe-apply",
      description:
        locale === "fr"
          ? "Relisez et appliquez les contenus validés depuis le workflow sécurisé."
          : "Review and apply approved content from the safe workflow.",
    },
  ];

  const advancedItems: HubItem[] = [
    {
      titleKey: "faqContentTitle",
      href: "/app/geo-faq-content",
      description:
        locale === "fr"
          ? "FAQ produits, guides d'achat et JSON-LD depuis les faits confirmés."
          : "Product FAQ, buying guides, and JSON-LD from confirmed facts.",
    },
    {
      titleKey: "content",
      href: "/app/content",
      description:
        locale === "fr"
          ? "Ancien écran FAQ et briefs blog depuis les requêtes GSC."
          : "Legacy FAQ and blog brief screen from GSC queries.",
    },
    {
      titleKey: "hreflang",
      href: "/app/hreflang",
      description:
        locale === "fr"
          ? "Configuration multimarché et balises hreflang."
          : "Multi-market configuration and hreflang tags.",
    },
    {
      titleKey: "jsonld",
      href: "/app/jsonld",
      description:
        locale === "fr"
          ? "Données structurées Schema.org pour produits et collections."
          : "Schema.org structured data for products and collections.",
    },
    {
      titleKey: "semantics",
      href: "/app/semantics",
      description:
        locale === "fr"
          ? "Analyse sémantique et signaux E-E-A-T avancés."
          : "Advanced semantic and E-E-A-T analysis.",
    },
    {
      titleKey: "niche",
      href: "/app/niche",
      description:
        locale === "fr"
          ? "Clusters produits, écarts de mots-clés et intentions de recherche."
          : "Product clusters, keyword gaps, and search intents.",
    },
    {
      titleKey: "geoFacts",
      href: "/app/geo-facts",
      description:
        locale === "fr"
          ? "Faits produits confirmés et manques à vérifier."
          : "Confirmed product facts and verification gaps.",
    },
    {
      titleKey: "geoCollections",
      href: "/app/geo-collections",
      description:
        locale === "fr"
          ? "Suggestions de collections Shopify en dry-run."
          : "Shopify collection suggestions in dry-run.",
    },
    {
      titleKey: "geoAnswerBlocks",
      href: "/app/geo-answer-blocks",
      description:
        locale === "fr"
          ? "Blocs réponses IA depuis les faits produits confirmés."
          : "AI answer blocks from confirmed product facts.",
    },
    {
      titleKey: "geoCrawlability",
      href: "/app/geo-crawlability",
      description:
        locale === "fr"
          ? "Prévisualisation llms.txt et lisibilité pour moteurs IA."
          : "llms.txt preview and AI crawler readability.",
    },
  ];

  return (
    <Page
      title={t(locale, "hubContent")}
      subtitle={t(locale, "hubContentSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        <HubGrid items={primaryItems} locale={locale} />
        <AdvancedToolList
          title={locale === "fr" ? "Outils contenu avancés" : "Advanced content tools"}
          items={advancedItems}
          locale={locale}
        />
      </BlockStack>
    </Page>
  );
}
