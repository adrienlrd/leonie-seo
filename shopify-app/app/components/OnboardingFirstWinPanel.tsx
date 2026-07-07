/**
 * Onboarding step 5 — the "first win": pick the strongest low-risk proposal
 * (a meta title) from the completed analysis and let the merchant apply it in
 * one click. The merchant leaves onboarding with a real change live on their
 * store and a measurement promise — not just a list of proposals.
 */

import { useEffect, useMemo } from "react";
import { useFetcher } from "@remix-run/react";
import { Badge, Banner, BlockStack, Box, Button, Card, InlineStack, Text } from "@shopify/polaris";
import { CheckCircleIcon } from "@shopify/polaris-icons";
import { t, type Locale } from "../lib/i18n";
import { SectionTitle, type MarketJobState, type ProductResult } from "../lib/marketAnalysisShared";

type ApplyResponse = { type: "applyFirstWin"; ok: boolean; error: string | null };

interface OnboardingFirstWinPanelProps {
  locale: Locale;
  job: MarketJobState;
  onDone: () => void;
}

function pickCandidate(products: ProductResult[]): ProductResult | null {
  const eligible = products.filter((product) => {
    const pack = product.content_test_pack;
    const proposed = (pack?.proposed_meta_title ?? "").trim();
    return proposed !== "" && proposed !== (pack?.current_meta_title ?? "").trim();
  });
  if (eligible.length === 0) return null;
  return [...eligible].sort((a, b) => (b.opportunity_score ?? 0) - (a.opportunity_score ?? 0))[0];
}

export function OnboardingFirstWinPanel({ locale, job, onDone }: OnboardingFirstWinPanelProps) {
  const applyFetcher = useFetcher<ApplyResponse>();

  const candidate = useMemo(() => pickCandidate(job.products ?? []), [job.products]);

  // No eligible proposal → nothing to sell here, go straight to the dashboard.
  useEffect(() => {
    if (!candidate) onDone();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidate]);

  if (!candidate) return null;

  const pack = candidate.content_test_pack;
  const keyword = candidate.seo_keywords?.[0];
  const applied = applyFetcher.data?.type === "applyFirstWin" && applyFetcher.data.ok;
  const applyError =
    applyFetcher.data?.type === "applyFirstWin" ? applyFetcher.data.error : null;
  const applying = applyFetcher.state !== "idle";

  const handleApply = () => {
    const fd = new FormData();
    fd.set("intent", "applyFirstWin");
    fd.set("productId", candidate.product_id);
    applyFetcher.submit(fd, { method: "post" });
  };

  return (
    <Card>
      <BlockStack gap="300">
        <SectionTitle source={CheckCircleIcon}>
          {t(locale, "onboardingStepFirstWinTitle")}
        </SectionTitle>
        <Text as="p" tone="subdued">
          {t(locale, "onboardingStepFirstWinBody")}
        </Text>

        <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
          <BlockStack gap="300">
            <InlineStack gap="200" blockAlign="center" wrap>
              <Text as="p" fontWeight="semibold">
                {candidate.product_title}
              </Text>
              {keyword?.query && (
                <Badge tone="info">
                  {t(locale, "onboardingFirstWinKeyword").replace("{query}", keyword.query)}
                </Badge>
              )}
              {keyword?.search_volume ? (
                <Badge>
                  {t(locale, "onboardingFirstWinKeywordVolume").replace(
                    "{volume}",
                    String(keyword.search_volume),
                  )}
                </Badge>
              ) : null}
            </InlineStack>

            <BlockStack gap="100">
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "onboardingFirstWinCurrent")}
              </Text>
              <Box padding="200" background="bg-surface-secondary" borderRadius="100">
                <Text as="p" tone="subdued">
                  {pack.current_meta_title || "—"}
                </Text>
              </Box>
              <Text as="p" variant="bodySm" tone="subdued">
                {t(locale, "onboardingFirstWinProposed")}
              </Text>
              <Box padding="200" background="bg-surface-success" borderRadius="100">
                <Text as="p" fontWeight="medium">
                  {pack.proposed_meta_title}
                </Text>
              </Box>
            </BlockStack>

            {applyError && (
              <Banner tone="critical">
                <Text as="p">{applyError.split("\n")[0]}</Text>
              </Banner>
            )}

            {applied ? (
              <BlockStack gap="200">
                <Banner tone="success">
                  <Text as="p">{t(locale, "onboardingFirstWinApplied")}</Text>
                </Banner>
                <InlineStack align="end">
                  <Button variant="primary" onClick={onDone}>
                    {t(locale, "onboardingFirstWinDone")}
                  </Button>
                </InlineStack>
              </BlockStack>
            ) : (
              <InlineStack align="end" gap="200">
                <Button variant="tertiary" onClick={onDone} disabled={applying}>
                  {t(locale, "onboardingFirstWinLater")}
                </Button>
                <Button variant="primary" onClick={handleApply} loading={applying}>
                  {t(locale, "onboardingFirstWinApply")}
                </Button>
              </InlineStack>
            )}
          </BlockStack>
        </Box>
      </BlockStack>
    </Card>
  );
}
