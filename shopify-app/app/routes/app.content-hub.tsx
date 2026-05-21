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
      titleKey: "geoWeekly",
      href: "/app/geo-weekly",
      description:
        locale === "fr"
          ? "Les 3 actions GEO les plus utiles à traiter cette semaine."
          : "The 3 most useful GEO actions to handle this week.",
    },
    {
      titleKey: "geoLedger",
      href: "/app/geo-ledger",
      description:
        locale === "fr"
          ? "Historique des optimisations GEO, snapshots avant/après et impact estimé vs observé."
          : "GEO optimization history, before/after snapshots, and estimated vs observed impact.",
    },
    {
      titleKey: "geoRiskGuard",
      href: "/app/geo-risk-guard",
      description:
        locale === "fr"
          ? "Protège les pages déjà performantes ou business-critiques avant optimisation."
          : "Protects already performing or business-critical pages before optimization.",
    },
    {
      titleKey: "geoCollections",
      href: "/app/geo-collections",
      description:
        locale === "fr"
          ? "Propose des collections Shopify adaptées aux intentions conversationnelles, en dry-run."
          : "Suggests Shopify collections for conversational intents, in dry-run.",
    },
    {
      titleKey: "geoAnswerBlocks",
      href: "/app/geo-answer-blocks",
      description:
        locale === "fr"
          ? "Génère des FAQ et réponses IA uniquement depuis les faits produits confirmés."
          : "Generates FAQ and AI answers only from confirmed product facts.",
    },
    {
      titleKey: "geoCrawlability",
      href: "/app/geo-crawlability",
      description:
        locale === "fr"
          ? "Prévisualise un llms.txt et les pages à rendre lisibles pour les moteurs IA."
          : "Previews llms.txt and pages to make readable for AI crawlers.",
    },
    {
      titleKey: "geoCompetitors",
      href: "/app/geo-competitors",
      description:
        locale === "fr"
          ? "Compare les concurrents visibles sur les requêtes conversationnelles prioritaires."
          : "Compares competitors visible on priority conversational queries.",
    },
    {
      titleKey: "geoSnapshots",
      href: "/app/geo-snapshots",
      description:
        locale === "fr"
          ? "Capture l'état avant optimisation pour mesurer l'impact plus tard."
          : "Captures the before state so optimization impact can be measured later.",
    },
    {
      titleKey: "geoControlGroups",
      href: "/app/geo-control-groups",
      description:
        locale === "fr"
          ? "Compare les pages optimisées à des pages témoins similaires non modifiées."
          : "Compares optimized pages with similar unchanged control pages.",
    },
    {
      titleKey: "geoValidationTimeline",
      href: "/app/geo-validation-timeline",
      description:
        locale === "fr"
          ? "Planifie les fenêtres J+7, J+30, J+60 et J+90 avant de conclure."
          : "Schedules J+7, J+30, J+60, and J+90 windows before conclusions.",
    },
    {
      titleKey: "geoFacts",
      href: "/app/geo-facts",
      description:
        locale === "fr"
          ? "Faits produits confirmés, manques à vérifier et score de complétude GEO."
          : "Confirmed product facts, verification gaps, and GEO completeness score.",
    },
    {
      titleKey: "geoReadiness",
      href: "/app/geo-readiness",
      description:
        locale === "fr"
          ? "Score GEO par produit : faits, schema, réponses IA, confiance, SEO et signaux commerce."
          : "Product GEO score across facts, schema, AI answers, trust, SEO, and commerce signals.",
    },
    {
      titleKey: "geoPriorities",
      href: "/app/geo-priorities",
      description:
        locale === "fr"
          ? "Classe les actions GEO selon le potentiel business, le trafic, le stock et l'effort."
          : "Ranks GEO actions by business upside, traffic, stock, and effort.",
    },
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
      titleKey: "nicheUnderstanding",
      href: "/app/niche-understanding",
      description:
        locale === "fr"
          ? "Hypothèses marchand validées avant les recommandations et contenus IA."
          : "Merchant-validated hypotheses before AI recommendations and content.",
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
