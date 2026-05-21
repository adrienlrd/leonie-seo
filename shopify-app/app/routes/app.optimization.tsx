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

export default function OptimizationHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };

  const primaryItems: HubItem[] = [
    {
      titleKey: "priorities",
      href: "/app/priorities",
      description:
        locale === "fr"
          ? "Commencez ici : les trois actions les plus utiles à traiter maintenant."
          : "Start here: the three most useful actions to handle now.",
    },
    {
      titleKey: "contentActions",
      href: "/app/content-actions",
      description:
        locale === "fr"
          ? "Générez un contenu prêt à relire : meta, descriptions, FAQ ou guides."
          : "Generate content ready to review: meta, descriptions, FAQ, or guides.",
    },
    {
      titleKey: "safeApply",
      href: "/app/safe-apply",
      description:
        locale === "fr"
          ? "Relisez, modifiez, simulez, puis appliquez seulement après validation humaine."
          : "Review, edit, preview, then apply only after human approval.",
    },
    {
      titleKey: "rollbackHistory",
      href: "/app/rollback-history",
      description:
        locale === "fr"
          ? "Retrouvez les changements appliqués et annulez une modification si nécessaire."
          : "Find applied changes and revert an update if needed.",
    },
  ];

  const advancedItems: HubItem[] = [
    {
      titleKey: "review",
      href: "/app/review",
      description:
        locale === "fr"
          ? "Ancien écran de revue IA, conservé pour compatibilité pilote."
          : "Legacy AI review screen, kept for pilot compatibility.",
    },
    {
      titleKey: "descriptions",
      href: "/app/descriptions",
      description:
        locale === "fr"
          ? "Ancien générateur dédié aux descriptions produits."
          : "Legacy generator dedicated to product descriptions.",
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
          ? "Ancien rollback technique, remplacé par l'historique des modifications."
          : "Legacy technical rollback, replaced by change history.",
    },
  ];

  return (
    <Page
      title={t(locale, "hubOptimization")}
      subtitle={t(locale, "hubOptimizationSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        <HubGrid items={primaryItems} locale={locale} />
        <AdvancedToolList
          title={locale === "fr" ? "Outils avancés" : "Advanced tools"}
          items={advancedItems}
          locale={locale}
        />
      </BlockStack>
    </Page>
  );
}
