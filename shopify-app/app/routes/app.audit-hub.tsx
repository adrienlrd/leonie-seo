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

export default function AuditHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };

  const items: HubItem[] = [
    {
      titleKey: "nicheUnderstanding",
      href: "/app/niche-understanding",
      description:
        locale === "fr"
          ? "Définissez et validez votre niche pour que l'IA génère du contenu adapté."
          : "Define and validate your niche so the AI generates relevant content.",
    },
    {
      titleKey: "auditReadiness",
      href: "/app/audit-readiness",
      description:
        locale === "fr"
          ? "Score de préparation IA par produit actif — faits, structure, crawl."
          : "AI readiness score per active product — facts, structure, crawl.",
    },
    {
      titleKey: "opportunities",
      href: "/app/opportunities",
      description:
        locale === "fr"
          ? "Pages ACTIVE classées par ratio impact/effort — sans IA, 7 signaux."
          : "ACTIVE pages ranked by impact/effort — no AI, 7 signals.",
    },
    {
      titleKey: "priorities",
      href: "/app/priorities",
      description:
        locale === "fr"
          ? "Vos 3 actions prioritaires du moment — avec pourquoi maintenant."
          : "Your 3 priority actions right now — with why it matters.",
    },
    {
      titleKey: "alerts",
      href: "/app/alerts",
      description:
        locale === "fr"
          ? "Régressions, 404, chutes de CTR et budget LLM dépassé."
          : "Regressions, 404s, CTR drops and LLM budget exceeded.",
    },
  ];

  return (
    <Page
      title={t(locale, "hubAudit")}
      subtitle={t(locale, "hubAuditSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        <HubGrid items={items} locale={locale} />
      </BlockStack>
    </Page>
  );
}
