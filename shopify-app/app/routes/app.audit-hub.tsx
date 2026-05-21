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

export default function AuditHub() {
  const { locale } = useLoaderData<typeof loader>() as { locale: Locale };

  const primaryItems: HubItem[] = [
    {
      titleKey: "auditReadiness",
      href: "/app/audit-readiness",
      description:
        locale === "fr"
          ? "Comprenez rapidement l'état de la boutique et les points à corriger."
          : "Quickly understand store health and what needs attention.",
    },
    {
      titleKey: "opportunities",
      href: "/app/opportunities",
      description:
        locale === "fr"
          ? "Repérez les pages actives qui méritent une optimisation en premier."
          : "Find active pages that deserve optimization first.",
    },
    {
      titleKey: "audit",
      href: "/app/audit",
      description:
        locale === "fr"
          ? "Relancez l'analyse de votre boutique quand les données doivent être actualisées."
          : "Refresh the store analysis when data needs to be updated.",
    },
  ];

  const advancedItems: HubItem[] = [
    {
      titleKey: "priorities",
      href: "/app/priorities",
      description:
        locale === "fr"
          ? "Écran canonique aussi disponible depuis Actions."
          : "Canonical screen also available from Actions.",
    },
    {
      titleKey: "longtail",
      href: "/app/longtail",
      description:
        locale === "fr"
          ? "Mots-clés longue traîne à forte intention sous-exploités."
          : "High-intent long-tail keywords currently under-leveraged.",
    },
    {
      titleKey: "cannibalization",
      href: "/app/cannibalization",
      description:
        locale === "fr"
          ? "Pages qui se concurrencent sur les mêmes requêtes — à fusionner ou différencier."
          : "Pages competing on the same queries — merge or differentiate.",
    },
    {
      titleKey: "alerts",
      href: "/app/alerts",
      description:
        locale === "fr"
          ? "Régressions CWV, 404, chutes de CTR, budget LLM, tâches échouées."
          : "CWV regressions, 404s, CTR drops, LLM budget, failed jobs.",
    },
  ];

  return (
    <Page
      title={t(locale, "hubAudit")}
      subtitle={t(locale, "hubAuditSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">
        <HubGrid items={primaryItems} locale={locale} />
        <AdvancedToolList
          title={locale === "fr" ? "Diagnostics avancés" : "Advanced diagnostics"}
          items={advancedItems}
          locale={locale}
        />
      </BlockStack>
    </Page>
  );
}
