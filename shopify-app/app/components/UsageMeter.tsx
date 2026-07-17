import { BlockStack, Box, Button, InlineStack, ProgressBar, Text } from "@shopify/polaris";
import type { Locale } from "../lib/i18n";
import { localizedPath } from "../lib/i18n";

export interface UsageInfo {
  analysis: number;
  blog: number;
}

export interface QuotaInfo {
  products: number;
  analysis: number;
  blog: number;
  auto_analysis: boolean;
}

/** ChatGPT-style usage meter: "2/3 used this cycle" with a progress bar that
 * shifts tone as the merchant approaches the limit, and an upgrade CTA at 100%. */
export function UsageMeter({
  label,
  used,
  quota,
  locale,
  showUpgrade = true,
}: {
  label: string;
  used: number;
  quota: number;
  locale: Locale;
  /** Show the upgrade CTA when the limit is reached (hide for paid top tier). */
  showUpgrade?: boolean;
}) {
  const fr = locale === "fr";
  const clamped = Math.min(used, quota);
  const pct = quota > 0 ? Math.round((clamped / quota) * 100) : 0;
  const atLimit = used >= quota;
  const nearLimit = !atLimit && pct >= 80;
  const tone = atLimit ? "critical" : nearLimit ? "primary" : "highlight";

  return (
    <Box background="bg-surface-secondary" padding="300" borderRadius="200">
      <BlockStack gap="150">
        <InlineStack align="space-between" blockAlign="center" gap="200">
          <Text as="p" variant="bodySm" fontWeight="medium">{label}</Text>
          <Text as="p" variant="bodySm" tone={atLimit ? "critical" : "subdued"} fontWeight={atLimit ? "semibold" : undefined}>
            {clamped}/{quota}
          </Text>
        </InlineStack>
        <ProgressBar progress={pct} size="small" tone={tone} />
        <Text as="p" variant="bodySm" tone="subdued">
          {atLimit
            ? fr
              ? "Limite atteinte — se libère au fil des 28 jours."
              : "Limit reached — frees up over the 28-day window."
            : fr
              ? "Sur les 28 derniers jours."
              : "Over the last 28 days."}
        </Text>
        {atLimit && showUpgrade && (
          <Button url={localizedPath("/app/billing", locale)} variant="primary" size="slim">
            {fr ? "Passer à la vitesse supérieure" : "Move up a gear"}
          </Button>
        )}
      </BlockStack>
    </Box>
  );
}

/** Discreet quota indicator for a page's title row (titleMetadata):
 * "Quota 1/10" + a thin progress bar — critical tone at the limit, no CTA. */
export function QuotaPill({
  used,
  quota,
}: {
  used: number;
  quota: number;
}) {
  const clamped = Math.min(used, quota);
  const pct = quota > 0 ? Math.round((clamped / quota) * 100) : 0;
  const atLimit = used >= quota;
  return (
    <InlineStack gap="150" blockAlign="center" wrap={false}>
      <Text
        as="span"
        variant="bodySm"
        tone={atLimit ? "critical" : "subdued"}
        fontWeight={atLimit ? "semibold" : undefined}
      >
        Quota {clamped}/{quota}
      </Text>
      <div style={{ width: 72 }}>
        <ProgressBar
          progress={pct}
          size="small"
          tone={atLimit ? "critical" : "highlight"}
        />
      </div>
    </InlineStack>
  );
}
