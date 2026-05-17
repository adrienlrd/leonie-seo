import { Badge, BlockStack, Card, InlineStack, Text } from "@shopify/polaris";
import { t, type Locale } from "../../lib/i18n";
import type { CrawlStatus, GSCStatus, Health, PageSpeedStatus, ShopStatus } from "./types";

function Step({
  label,
  done,
  detail,
}: {
  label: string;
  done: boolean;
  detail?: string;
}) {
  return (
    <InlineStack align="space-between" gap="300">
      <BlockStack gap="050">
        <Text as="span" fontWeight="bold">
          {label}
        </Text>
        {detail && (
          <Text as="span" tone="subdued" variant="bodySm">
            {detail}
          </Text>
        )}
      </BlockStack>
      <Badge tone={done ? "success" : "warning"}>{done ? "✓" : "—"}</Badge>
    </InlineStack>
  );
}

interface Props {
  locale: Locale;
  shop: string;
  status: ShopStatus | null;
  health: Health | null;
  gsc: GSCStatus | null;
  pagespeed: PageSpeedStatus | null;
  crawl: CrawlStatus | null;
}

/** Left card: at-a-glance checklist of every integration. */
export function InstallationChecklistCard({
  locale,
  shop,
  status,
  health,
  gsc,
  pagespeed,
  crawl,
}: Props) {
  return (
    <Card>
      <BlockStack gap="300">
        <Text as="h2" variant="headingMd">
          {t(locale, "installation")}
        </Text>
        <Step label={t(locale, "shopify")} done={Boolean(status?.installed)} detail={shop} />
        <Step
          label={t(locale, "backend")}
          done={health?.status === "ok"}
          detail={
            health?.missing_env?.length
              ? `${t(locale, "missing")}: ${health.missing_env.join(", ")}`
              : "ok"
          }
        />
        <Step
          label={t(locale, "crawl")}
          done={Boolean(status?.snapshot_available)}
          detail={`${status?.product_count ?? 0} ${t(locale, "products")}`}
        />
        <Step
          label={t(locale, "billing")}
          done={Boolean(status?.plan)}
          detail={status?.plan ?? "free"}
        />
        <Step
          label={t(locale, "gsc")}
          done={Boolean(gsc?.connected && gsc.latest_import.available)}
          detail={
            gsc?.connected
              ? `${gsc.site_url} · ${gsc.latest_import.row_count ?? 0} ${
                  locale === "fr" ? "lignes" : "rows"
                }`
              : gsc?.action_required ??
                (locale === "fr" ? "Connexion requise" : "Connection required")
          }
        />
        <Step
          label="PageSpeed / Core Web Vitals"
          done={Boolean(pagespeed?.available)}
          detail={
            pagespeed?.available
              ? `${pagespeed.url_count} URL(s) · mobile ${Math.round(
                  (pagespeed.mobile_average ?? 0) * 100
                )}%`
              : locale === "fr"
              ? "Analyse performance à lancer"
              : "Performance analysis to run"
          }
        />
        <Step
          label={locale === "fr" ? "Crawl technique" : "Technical crawl"}
          done={Boolean(crawl?.available)}
          detail={
            crawl?.available
              ? `${crawl.url_count} URLs · ${crawl.issue_count} ${
                  locale === "fr" ? "problèmes" : "issues"
                }`
              : locale === "fr"
              ? "Exporter un CSV Screaming Frog et l'importer"
              : "Export a Screaming Frog CSV and import it"
          }
        />
      </BlockStack>
    </Card>
  );
}
