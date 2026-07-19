import { Badge, BlockStack, Card, InlineStack, Text } from "@shopify/polaris";
import { t, type Locale } from "../lib/i18n";

type Tone = "success" | "info" | undefined;

/** source code → [i18n label key, badge tone]. Unknown codes are skipped. */
const SOURCE_META: Record<string, [string, Tone]> = {
  gsc: ["srcGsc", "success"],
  dataforseo: ["srcDataforseo", "success"],
  dataforseo_keyword_ideas: ["srcDataforseoIdeas", "success"],
  dataforseo_serp: ["srcDataforseoSerp", "success"],
  ga4: ["srcGa4", "success"],
  google_ads: ["srcGoogleAds", "success"],
  google_suggest: ["srcSuggest", "info"],
  trends: ["srcTrends", "info"],
  realtime_grounding: ["srcRealtime", "info"],
  realtime_market_verification: ["srcRealtimeVerify", "info"],
  shopify_snapshot: ["srcShopify", "info"],
  keyword_candidate_pool: ["srcCandidatePool", undefined],
  optimization_history: ["srcHistory", undefined],
  business_profile: ["srcBusinessProfile", undefined],
  niche_hypothesis: ["srcNiche", undefined],
};

/** Compact per-analysis data-provenance summary (Built for Shopify: the
 * merchant sees at a glance which real sources fed the recommendations). */
export function SourcesUsedCard({
  sources,
  locale,
}: {
  sources: string[];
  locale: Locale;
}) {
  const known = sources.filter((code) => SOURCE_META[code]);
  if (known.length === 0) return null;
  return (
    <Card>
      <BlockStack gap="200">
        <Text as="h3" variant="headingSm">
          {t(locale, "sourcesUsedTitle")}
        </Text>
        <InlineStack gap="150" wrap>
          {known.map((code) => {
            const [labelKey, tone] = SOURCE_META[code];
            return (
              <Badge key={code} tone={tone}>
                {t(locale, labelKey)}
              </Badge>
            );
          })}
        </InlineStack>
      </BlockStack>
    </Card>
  );
}
