/**
 * Onboarding "choose your products" step: the merchant picks which products
 * the app will manage, capped by the plan (free 3 / pro 15 / agency 35).
 * The selection is the source of truth for every surface (analysis, dashboard,
 * GEO, llms.txt) — nothing is analyzed until it is saved.
 */

import { useEffect, useState } from "react";
import { useFetcher } from "@remix-run/react";
import {
  Banner,
  BlockStack,
  Button,
  Card,
  Checkbox,
  InlineStack,
  Spinner,
  Text,
  Thumbnail,
} from "@shopify/polaris";
import { ProductIcon } from "@shopify/polaris-icons";
import { t, type Locale } from "../lib/i18n";
import { SectionTitle } from "../lib/marketAnalysisShared";

export interface ManagedProductsState {
  selected_ids: string[] | null;
  cap: number;
  plan: string;
  available_products: Array<{
    id: string;
    title: string;
    handle: string;
    image_url: string | null;
  }>;
}

type LoadResponse = {
  type: "loadManagedProducts";
  managed: ManagedProductsState | null;
  error: string | null;
};
type SaveResponse = {
  type: "saveManagedProducts";
  saved: boolean;
  error: string | null;
};

interface ProductSelectionPanelProps {
  locale: Locale;
  onSaved: () => void;
}

export function ProductSelectionPanel({ locale, onSaved }: ProductSelectionPanelProps) {
  const loadFetcher = useFetcher<LoadResponse>();
  const saveFetcher = useFetcher<SaveResponse>();

  const [managed, setManaged] = useState<ManagedProductsState | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (loadFetcher.state === "idle" && !loadFetcher.data && !managed) {
      const fd = new FormData();
      fd.set("intent", "loadManagedProducts");
      loadFetcher.submit(fd, { method: "post" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const data = loadFetcher.data;
    if (!data || data.type !== "loadManagedProducts") return;
    if (data.managed) {
      setManaged(data.managed);
      const initial = data.managed.selected_ids ?? [];
      setSelected(new Set(initial));
    } else if (data.error) {
      setError(data.error);
    }
  }, [loadFetcher.data]);

  useEffect(() => {
    const data = saveFetcher.data;
    if (!data || data.type !== "saveManagedProducts") return;
    if (data.saved) {
      onSaved();
    } else if (data.error) {
      setError(data.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveFetcher.data]);

  const cap = managed?.cap ?? 0;
  const atCap = selected.size >= cap;

  const toggle = (id: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked && next.size < cap) next.add(id);
      if (!checked) next.delete(id);
      return next;
    });
  };

  const handleSave = () => {
    setError(null);
    const fd = new FormData();
    fd.set("intent", "saveManagedProducts");
    fd.set("productIds", JSON.stringify([...selected]));
    saveFetcher.submit(fd, { method: "post" });
  };

  return (
    <Card>
      <BlockStack gap="400">
        <SectionTitle source={ProductIcon}>{t(locale, "productSelectionTitle")}</SectionTitle>
        <Text as="p" tone="subdued">
          {t(locale, "productSelectionSubtitle")}
        </Text>

        {error && (
          <Banner tone="critical">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {!managed && !error && (
          <InlineStack gap="200" blockAlign="center">
            <Spinner size="small" />
            <Text as="p" tone="subdued">
              {t(locale, "productSelectionLoading")}
            </Text>
          </InlineStack>
        )}

        {managed && (
          <BlockStack gap="300">
            <Text as="p" fontWeight="semibold">
              {t(locale, "productSelectionCount")
                .replace("{selected}", String(selected.size))
                .replace("{cap}", String(cap))}
            </Text>
            {atCap && (
              <Banner tone="warning">
                <Text as="p">{t(locale, "productSelectionCapReached")}</Text>
              </Banner>
            )}
            <BlockStack gap="200">
              {managed.available_products.map((p) => {
                const checked = selected.has(p.id);
                return (
                  <InlineStack key={p.id} gap="300" blockAlign="center" wrap={false}>
                    <Checkbox
                      label=""
                      labelHidden
                      checked={checked}
                      disabled={!checked && atCap}
                      onChange={(value) => toggle(p.id, value)}
                    />
                    <Thumbnail
                      source={p.image_url || ProductIcon}
                      alt={p.title}
                      size="small"
                    />
                    <Text as="span">{p.title}</Text>
                  </InlineStack>
                );
              })}
              {managed.available_products.length === 0 && (
                <Text as="p" tone="subdued">
                  {t(locale, "productSelectionEmptyCatalog")}
                </Text>
              )}
            </BlockStack>
            <InlineStack align="end">
              <Button
                variant="primary"
                disabled={selected.size === 0}
                loading={saveFetcher.state !== "idle"}
                onClick={handleSave}
              >
                {t(locale, "productSelectionSave")}
              </Button>
            </InlineStack>
          </BlockStack>
        )}
      </BlockStack>
    </Card>
  );
}
