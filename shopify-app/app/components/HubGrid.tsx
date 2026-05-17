import { BlockStack, Box, Card, InlineGrid, InlineStack, Link, Text } from "@shopify/polaris";
import { localizedPath, t, type Locale } from "../lib/i18n";

export interface HubItem {
  /** i18n key for the card title (resolved via t()). */
  titleKey: string;
  /** Free-form descriptive text shown under the title (already localized). */
  description: string;
  /** Path within the embedded app (e.g. "/app/audit"). Will be locale-suffixed. */
  href: string;
}

interface HubGridProps {
  items: HubItem[];
  locale: Locale;
  /** Number of columns at lg breakpoint. Defaults to 2. */
  columns?: 1 | 2 | 3;
}

/**
 * Generic responsive grid of feature cards used by every hub page.
 * Keeps each hub page short and visually consistent with Shopify Polaris.
 */
export function HubGrid({ items, locale, columns = 2 }: HubGridProps) {
  const cols =
    columns === 3
      ? { xs: "1", sm: "2", lg: "3" }
      : columns === 1
      ? { xs: "1" }
      : { xs: "1", sm: "2" };
  return (
    <InlineGrid columns={cols} gap="400">
      {items.map((item) => (
        <Card key={item.href}>
          <BlockStack gap="200">
            <Text as="h3" variant="headingMd">
              {t(locale, item.titleKey)}
            </Text>
            <Box minHeight="3em">
              <Text as="p" tone="subdued">
                {item.description}
              </Text>
            </Box>
            <InlineStack align="end">
              <Link url={localizedPath(item.href, locale)} removeUnderline>
                {t(locale, "open")} →
              </Link>
            </InlineStack>
          </BlockStack>
        </Card>
      ))}
    </InlineGrid>
  );
}
