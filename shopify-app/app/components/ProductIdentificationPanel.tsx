import { useState } from "react";
import { BlockStack, Card, Text, TextField } from "@shopify/polaris";
import type { Locale } from "../lib/i18n";
import { t } from "../lib/i18n";

export interface ProductLabels {
  labels?: Record<string, string>;
  product_titles?: Record<string, string>;
}

function ProductLabelField({ productId, title, label }: { productId: string; title: string; label: string }) {
  const [value, setValue] = useState(label);
  return <TextField label={title || productId} name={`label_${productId}`} value={value} onChange={setValue} autoComplete="off" />;
}

export function ProductIdentificationPanel({ identification, locale }: { identification: ProductLabels | null; locale: Locale }) {
  const labels = identification?.labels ?? {};
  const titles = identification?.product_titles ?? {};
  const entries = Object.entries(labels);

  return (
    <Card>
      <BlockStack gap="300">
        <Text as="h2" variant="headingMd">{t(locale, "onboardingProductLabelsTitle")}</Text>
        <Text as="p" tone="subdued">{t(locale, "onboardingProductLabelsBody")}</Text>
        {entries.length === 0 ? (
          <Text as="p" tone="subdued">{t(locale, "noData")}</Text>
        ) : (
          entries.map(([productId, label]) => <ProductLabelField key={productId} productId={productId} title={titles[productId] || productId} label={label} />)
        )}
      </BlockStack>
    </Card>
  );
}
