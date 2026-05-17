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

export default function InsightsHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };

  const items: HubItem[] = [
    {
      titleKey: "ga4",
      href: "/app/ga4",
      description:
        locale === "fr"
          ? "Funnel organique : impressions, clics, sessions, conversions et revenu."
          : "Organic funnel: impressions, clicks, sessions, conversions, revenue.",
    },
    {
      titleKey: "reports",
      href: "/app/reports",
      description:
        locale === "fr"
          ? "Rapports SEO mensuels et exports prêts à partager."
          : "Monthly SEO reports and shareable exports.",
    },
    {
      titleKey: "jobs",
      href: "/app/jobs",
      description:
        locale === "fr"
          ? "Suivi des audits, générations IA et imports en arrière-plan."
          : "Track audits, AI generations, and background imports.",
    },
  ];

  return (
    <Page
      title={t(locale, "hubInsights")}
      subtitle={t(locale, "hubInsightsSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        <HubGrid items={items} locale={locale} columns={3} />
      </BlockStack>
    </Page>
  );
}
