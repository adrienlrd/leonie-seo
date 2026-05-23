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

export default function InsightsHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };

  const primaryItems: HubItem[] = [
    {
      titleKey: "marketAnalysis",
      href: "/app/market-analysis",
      description:
        locale === "fr"
          ? "Analysez les produits actifs : mots-clés SEO, questions GEO, propositions de contenu."
          : "Analyze active products: SEO keywords, GEO questions, content proposals.",
    },
    {
      titleKey: "impact",
      href: "/app/impact",
      description:
        locale === "fr"
          ? "Suivez les résultats des optimisations appliquées dans le temps."
          : "Track results from applied optimizations over time.",
    },
    {
      titleKey: "nbaTitle",
      href: "/app/next-best-actions",
      description:
        locale === "fr"
          ? "Décidez quoi faire ensuite à partir des résultats déjà mesurés."
          : "Decide what to do next from already measured results.",
    },
    {
      titleKey: "retentionTitle",
      href: "/app/retention-milestones",
      description:
        locale === "fr"
          ? "Voyez les jalons J+7, J+30, J+60 et J+90 avant de conclure."
          : "See J+7, J+30, J+60, and J+90 milestones before concluding.",
    },
    {
      titleKey: "reports",
      href: "/app/reports",
      description:
        locale === "fr"
          ? "Rapports SEO mensuels et exports prêts à partager."
          : "Monthly SEO reports and shareable exports.",
    },
  ];

  const advancedItems: HubItem[] = [
    {
      titleKey: "impactReportTitle",
      href: "/app/impact-report",
      description:
        locale === "fr"
          ? "Rapport avant/après détaillé par optimisation."
          : "Detailed before/after report per optimization.",
    },
    {
      titleKey: "ga4",
      href: "/app/ga4",
      description:
        locale === "fr"
          ? "Funnel organique : sessions, conversions et revenu."
          : "Organic funnel: sessions, conversions, and revenue.",
    },
    {
      titleKey: "jobs",
      href: "/app/jobs",
      description:
        locale === "fr"
          ? "Suivi des audits, générations IA et imports en arrière-plan."
          : "Track audits, AI generations, and background imports.",
    },
    {
      titleKey: "geoLedger",
      href: "/app/geo-ledger",
      description:
        locale === "fr"
          ? "Historique technique des optimisations et snapshots."
          : "Technical history of optimizations and snapshots.",
    },
    {
      titleKey: "geoValidationTimeline",
      href: "/app/geo-validation-timeline",
      description:
        locale === "fr"
          ? "Timeline détaillée des fenêtres de validation."
          : "Detailed timeline of validation windows.",
    },
    {
      titleKey: "geoSnapshots",
      href: "/app/geo-snapshots",
      description:
        locale === "fr"
          ? "Snapshots avant optimisation pour analyse avancée."
          : "Before-optimization snapshots for advanced analysis.",
    },
    {
      titleKey: "geoControlGroups",
      href: "/app/geo-control-groups",
      description:
        locale === "fr"
          ? "Groupes témoins pour comparer pages modifiées et non modifiées."
          : "Control groups comparing changed and unchanged pages.",
    },
  ];

  return (
    <Page
      title={t(locale, "hubInsights")}
      subtitle={t(locale, "hubInsightsSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        <HubGrid items={primaryItems} locale={locale} />
        <AdvancedToolList
          title={locale === "fr" ? "Mesure avancée" : "Advanced measurement"}
          items={advancedItems}
          locale={locale}
        />
      </BlockStack>
    </Page>
  );
}
