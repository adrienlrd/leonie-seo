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
      titleKey: "safeApply",
      href: "/app/safe-apply",
      description:
        locale === "fr"
          ? "Revue humaine, dry-run, application Shopify et rollback — accept/edit/reject/retry."
          : "Human review, dry-run, Shopify apply and rollback — accept/edit/reject/retry.",
    },
    {
      titleKey: "contentActions",
      href: "/app/content-actions",
      description:
        locale === "fr"
          ? "Workflow unifié : meta, descriptions, FAQ, guides — faits confirmés + hypothèse niche."
          : "Unified workflow: meta, descriptions, FAQ, guides — confirmed facts + niche hypothesis.",
    },
    {
      titleKey: "priorities",
      href: "/app/priorities",
      description:
        locale === "fr"
          ? "Top 3 actions sélectionnées par score déterministe — LLM arbitrage sur plans Pro/Agency."
          : "Top 3 actions selected by deterministic score — LLM arbitrage on Pro/Agency plans.",
    },
    {
      titleKey: "opportunities",
      href: "/app/opportunities",
      description:
        locale === "fr"
          ? "Pages ACTIVE classées par ratio impact/effort — 7 signaux déterministes sans IA."
          : "ACTIVE pages ranked by impact/effort ratio — 7 deterministic signals, no AI.",
    },
    {
      titleKey: "auditReadiness",
      href: "/app/audit-readiness",
      description:
        locale === "fr"
          ? "Score AI Search Readiness unifié : faits produits, crawl L3, hypothèse niche."
          : "Unified AI Search Readiness score: product facts, crawl L3, niche hypothesis.",
    },
    {
      titleKey: "audit",
      href: "/app/audit",
      description:
        locale === "fr"
          ? "Crawl SEO complet : titres, descriptions, JSON-LD, redirections, problèmes techniques."
          : "Full SEO crawl: titles, descriptions, JSON-LD, redirects, technical issues.",
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
        <HubGrid items={items} locale={locale} />
      </BlockStack>
    </Page>
  );
}
