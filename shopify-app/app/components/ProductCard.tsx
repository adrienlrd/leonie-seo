import { useFetcher } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Collapsible,
  Icon,
  InlineStack,
  Popover,
  Spinner,
  Text,
  TextField,
  Tooltip,
} from "@shopify/polaris";
import { AlertTriangleIcon, CheckIcon, QuestionCircleIcon, XIcon } from "@shopify/polaris-icons";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { t, type Locale } from "../lib/i18n";
import { ProductContentProposals, type FieldKey } from "./ProductContentProposals";
import {
  keywordCoverage,
  scoreTone,
  type ImprovementTag,
  type ImprovementTagStatus,
  type InternalLinkSuggestion,
  type ProductResult,
} from "../lib/marketAnalysisShared";

function tagToneInAdded(tag: ImprovementTag): "success" | "critical" | "attention" | "warning" | "info" {
  if (tag.tag_type === "keyword") return "attention";
  if (tag.tag_type === "risk") return "critical";
  if (tag.tag_type === "merchant" || tag.status === "forced") return "warning";
  if (tag.status === "positive") return "success";
  return "info";
}

function ImprovementTags({
  addedTags,
  retiredTags,
  openBucket,
  onToggle,
  onRetire,
  onRestore,
  newLabel,
  onNewLabelChange,
  onAdd,
  locale,
  leading,
  trailing,
}: {
  addedTags: ImprovementTag[];
  retiredTags: ImprovementTag[];
  openBucket: "added" | "retired" | null;
  onToggle: (b: "added" | "retired") => void;
  onRetire: (tag: ImprovementTag) => void;
  onRestore: (tag: ImprovementTag) => void;
  newLabel: string;
  onNewLabelChange: (v: string) => void;
  onAdd: () => void;
  locale: Locale;
  leading?: ReactNode;
  trailing?: ReactNode;
}) {
  const fr = locale === "fr";
  return (
    <BlockStack gap="200">
      <InlineStack gap="150">
        {leading}
        <Button
          size="slim"
          pressed={openBucket === "added"}
          onClick={() => onToggle("added")}
        >
          {fr ? `Tags ajoutés (${addedTags.length})` : `Added tags (${addedTags.length})`}
        </Button>
        {retiredTags.length > 0 && (
          <Button
            size="slim"
            pressed={openBucket === "retired"}
            onClick={() => onToggle("retired")}
          >
            {fr ? `Tags retirés (${retiredTags.length})` : `Retired tags (${retiredTags.length})`}
          </Button>
        )}
        {trailing}
      </InlineStack>

      {openBucket === "added" && (
        <Box padding="300" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
          <BlockStack gap="200">
            {addedTags.length === 0 ? (
              <Text as="p" variant="bodySm" tone="subdued">
                {fr ? "Aucun tag actif." : "No active tags."}
              </Text>
            ) : (
              <BlockStack gap="100">
                {addedTags.map((tag) => (
                  <InlineStack key={tag.tag_id} align="space-between" blockAlign="center">
                    <Badge tone={tagToneInAdded(tag)}>{tag.label}</Badge>
                    <Button size="slim" variant="plain" tone="critical" onClick={() => onRetire(tag)}>
                      {fr ? "Retirer" : "Retire"}
                    </Button>
                  </InlineStack>
                ))}
              </BlockStack>
            )}
            <InlineStack gap="150" blockAlign="center">
              <div style={{ flex: 1 }}>
                <TextField
                  label=""
                  labelHidden
                  placeholder={fr ? "Nouveau tag…" : "New tag…"}
                  value={newLabel}
                  onChange={onNewLabelChange}
                  autoComplete="off"
                />
              </div>
              <Button size="slim" onClick={onAdd} disabled={!newLabel.trim()}>
                {fr ? "Ajouter" : "Add"}
              </Button>
            </InlineStack>
          </BlockStack>
        </Box>
      )}

      {openBucket === "retired" && retiredTags.length > 0 && (
        <Box padding="300" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
          <BlockStack gap="100">
            <Text as="p" variant="bodySm" tone="subdued">
              {fr
                ? "Ces sujets sont exclus des prochaines analyses."
                : "These topics are excluded from future analyses."}
            </Text>
            {retiredTags.map((tag) => (
              <InlineStack key={tag.tag_id} align="space-between" blockAlign="center">
                <Badge tone="critical">{tag.label}</Badge>
                <Button size="slim" variant="plain" onClick={() => onRestore(tag)}>
                  {fr ? "Restaurer" : "Restore"}
                </Button>
              </InlineStack>
            ))}
          </BlockStack>
        </Box>
      )}
    </BlockStack>
  );
}

/** Per-pillar breakdown of the GEO readiness score: shows ✓ (done) / ✗ (to improve)
 * for each weighted component so the merchant understands why the score is what it is. */
function GeoScoreBreakdown({
  components,
  locale,
}: {
  components?: Record<string, { score: number; weight: number }>;
  locale: Locale;
}) {
  const fr = locale === "fr";
  // Order by weight (biggest lever first). Labels mirror the readiness scorer.
  const pillars: Array<{ key: string; label: string }> = [
    { key: "facts", label: fr ? "Faits produit" : "Product facts" },
    { key: "schema", label: fr ? "Données structurées" : "Structured data" },
    { key: "answerability", label: fr ? "Répondabilité IA" : "AI answerability" },
    { key: "trust", label: fr ? "Confiance" : "Trust" },
    { key: "seo", label: fr ? "GEO (méta)" : "GEO (meta)" },
    { key: "commerce", label: fr ? "Commerce" : "Commerce" },
  ];
  const has = components && Object.keys(components).length > 0;

  return (
    <BlockStack gap="200">
      <Text as="p" variant="headingSm">
        {fr ? "Détail du Score GEO" : "GEO score breakdown"}
      </Text>
      <Text as="p" variant="bodySm" tone="subdued">
        {fr
          ? "Ce que les moteurs IA évaluent. ✓ = en place, ✗ = à compléter. Le % est le poids dans le score."
          : "What AI engines assess. ✓ = in place, ✗ = to complete. The % is its weight in the score."}
      </Text>
      {!has ? (
        <Text as="p" variant="bodySm" tone="subdued">
          {fr
            ? "Relancez une analyse pour voir le détail par critère."
            : "Re-run an analysis to see the per-criterion breakdown."}
        </Text>
      ) : (
        pillars.map(({ key, label }) => {
          const comp = components![key];
          if (!comp) return null;
          const done = comp.score >= 70;
          const weight = Math.round((comp.weight ?? 0) * 100);
          return (
            <InlineStack key={key} gap="150" blockAlign="center" wrap={false}>
              <span style={{ display: "inline-flex", flex: "0 0 auto", width: "1rem", height: "1rem" }}>
                <Icon source={done ? CheckIcon : XIcon} tone={done ? "success" : "critical"} />
              </span>
              <Text as="span" variant="bodySm">
                {`${label} — ${comp.score}/100 (${weight}%)`}
              </Text>
            </InlineStack>
          );
        })
      )}
    </BlockStack>
  );
}

export function ProductCard({
  product,
  locale,
  shop,
  isAnalyzing,
  onEnrichAndAnalyze,
  analyzeDisabled,
}: {
  product: ProductResult;
  locale: Locale;
  shop: string;
  isAnalyzing: boolean;
  onEnrichAndAnalyze: (answers: Record<string, string>) => void;
  analyzeDisabled: boolean;
}) {
  const fr = locale === "fr";
  const [openSection, setOpenSection] = useState<string | null>(null);
  const toggle = (s: string) => setOpenSection((p) => (p === s ? null : s));
  const [enrichmentOpen, setEnrichmentOpen] = useState(false);
  const [geoHelpOpen, setGeoHelpOpen] = useState(false);

  // ── Question retire/restore ───────────────────────────────────────────────
  const questionFetcher = useFetcher<{ type: string; ok: boolean }>();
  const onRetireQuestion = (key: string) =>
    questionFetcher.submit(
      { intent: "retireQuestion", productId: product.product_id, key },
      { method: "post" },
    );
  const onRestoreQuestion = (key: string) =>
    questionFetcher.submit(
      { intent: "restoreQuestion", productId: product.product_id, key },
      { method: "post" },
    );
  const onValidateQuestion = (key: string, answer: string) =>
    questionFetcher.submit(
      { intent: "validateQuestion", productId: product.product_id, key, answer },
      { method: "post" },
    );

  // ── Apply-to-Shopify state ─────────────────────────────────────────────────
  const applyFetcher = useFetcher<{ type: string; ok: boolean; results?: Record<string, { applied: boolean; error: string | null }>; applied_fields?: Record<string, string>; error?: string | null }>();
  const applyLoading = applyFetcher.state !== "idle";

  const pack = product.content_test_pack;

  // Applied fields (field → ISO date): seeded from the persisted pack, updated
  // immediately after a successful apply so badge + countdown show without reload.
  const [appliedFields, setAppliedFields] = useState<Record<string, string>>(
    () => pack?.applied_fields ?? {},
  );
  useEffect(() => {
    setAppliedFields(pack?.applied_fields ?? {});
  }, [product.product_id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const d = applyFetcher.data;
    if (d?.type === "applyToShopify" && d.applied_fields && Object.keys(d.applied_fields).length > 0) {
      setAppliedFields((prev) => ({ ...prev, ...d.applied_fields }));
      // Uncheck just-applied fields: re-applying must be a deliberate re-check.
      setCheckedApplyFields((prev) => {
        const next = new Set(prev);
        for (const key of Object.keys(d.applied_fields ?? {})) {
          next.delete((key === "image_alts" ? "alt_text" : key) as FieldKey);
        }
        return next;
      });
    }
  }, [applyFetcher.data]);
  const APPLY_FIELDS: FieldKey[] = ["meta_title", "meta_description", "alt_text", "description"];

  const fieldHasProposal = (key: FieldKey): boolean => {
    switch (key) {
      case "meta_title": return Boolean(pack?.proposed_meta_title) && pack?.proposed_meta_title !== pack?.current_meta_title;
      case "meta_description": return Boolean(pack?.proposed_meta_description) && pack?.proposed_meta_description !== pack?.current_meta_description;
      case "description": return Boolean(pack?.proposed_product_description);
      case "alt_text": return (pack?.proposed_image_alts ?? []).some((a) => Boolean(a.proposed_alt));
      default: return false;
    }
  };

  // Default-checked: fields with a proposal that were NOT already applied —
  // applied fields must be re-checked deliberately to re-apply (and restart
  // their countdown).
  const isFieldApplied = (key: FieldKey): boolean =>
    Boolean((pack?.applied_fields ?? {})[key === "alt_text" ? "image_alts" : key]);
  const FIELD_TO_BACKEND: Record<FieldKey, string> = {
    meta_title: "meta_title",
    meta_description: "meta_description",
    description: "description",
    alt_text: "image_alts",
  } as unknown as Record<FieldKey, string>;
  const defaultChecked = () => {
    // Persisted per-product selection wins (an empty array means the merchant
    // unchecked everything); otherwise default to every field that has a
    // proposal and is not already applied.
    const persisted = pack?.auto_publish_fields;
    if (persisted) {
      return new Set(APPLY_FIELDS.filter((f) => persisted.includes(FIELD_TO_BACKEND[f] ?? f)));
    }
    return new Set(APPLY_FIELDS.filter((f) => fieldHasProposal(f) && !isFieldApplied(f)));
  };

  const [checkedApplyFields, setCheckedApplyFields] = useState<Set<FieldKey>>(defaultChecked);
  const autoPublishFetcher = useFetcher();

  const packSig = JSON.stringify(pack);
  useEffect(() => {
    setCheckedApplyFields(defaultChecked());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product.product_id, packSig]);

  const onToggleApplyField = (field: FieldKey) =>
    setCheckedApplyFields((prev) => {
      const next = new Set(prev);
      if (next.has(field)) next.delete(field); else next.add(field);
      // Persist the per-product auto-publish selection (best-effort).
      const backendFields = [...next].map((f) => FIELD_TO_BACKEND[f] ?? f);
      autoPublishFetcher.submit(
        {
          intent: "setAutoPublishFields",
          productId: product.product_id,
          autoPublishFields: JSON.stringify(backendFields),
        },
        { method: "post" },
      );
      return next;
    });

  const handleApplyProposals = () => {
    const fields = [...checkedApplyFields].map((f) => (f === "alt_text" ? "image_alts" : f));
    applyFetcher.submit(
      { intent: "applyToShopify", productId: product.product_id, fields: JSON.stringify(fields) },
      { method: "post" },
    );
  };

  // GEO score shown on the card: starts at the product's current readiness
  // (geo_score) and rises toward its potential (geo_score_potential) as proposed
  // fields get applied. Uses the live appliedFields state so it climbs the moment
  // a field is validated (manually or via auto-publish). Falls back to the legacy
  // inverted opportunity score when the backend score is absent (older results).
  const geoCurrent = product.geo_score ?? Math.max(0, 100 - product.opportunity_score);
  const geoPotential = product.geo_score_potential ?? geoCurrent;
  // Each applied field lifts the score by its real readiness contribution
  // (geo_score_field_deltas), so validating one field moves the score by its
  // true value instead of a diluted count fraction. Capped at the potential.
  const fieldDeltas = product.geo_score_field_deltas ?? {};
  const appliedDelta = APPLY_FIELDS.reduce((sum, f) => {
    const key = FIELD_TO_BACKEND[f] ?? f;
    return appliedFields[key] ? sum + (fieldDeltas[key] ?? 0) : sum;
  }, 0);
  const geoDisplayed = Math.round(Math.min(geoPotential, geoCurrent + appliedDelta));

  const applyResult = applyFetcher.data?.type === "applyToShopify" ? applyFetcher.data : null;

  // ── Tag state managed at ProductCard level ─────────────────────────────────
  const [localTags, setLocalTags] = useState<ImprovementTag[]>(product.improvement_tags ?? []);
  useEffect(() => {
    const serverTags = product.improvement_tags ?? [];
    setLocalTags((prev) => {
      // Preserve pending optimistic tags (tmp- prefix) not yet confirmed by server
      const pending = prev.filter(
        (p) =>
          p.tag_id.startsWith("tmp-") &&
          !serverTags.some(
            (s) => s.label.toLowerCase() === p.label.toLowerCase() && s.tag_type === p.tag_type,
          ),
      );
      return [...serverTags, ...pending];
    });
  }, [product.product_id, product.improvement_tags]);
  const tagFetcher = useFetcher<{ ok?: boolean }>();
  const [openBucket, setOpenBucket] = useState<"added" | "retired" | null>(null);
  const [newTagLabel, setNewTagLabel] = useState("");

  const addedTags = localTags.filter((t) => t.status !== "negative");
  const retiredTags = localTags.filter((t) => t.status === "negative");
  const keywordTagLabels = new Set(
    localTags.filter((t) => t.tag_type === "keyword").map((t) => t.label.toLowerCase()),
  );
  const addedKeywordLabels = new Set(
    localTags
      .filter((t) => t.tag_type === "keyword" && t.status !== "negative")
      .map((t) => t.label.toLowerCase()),
  );
  const retiredKeywordLabels = new Set(
    localTags
      .filter((t) => t.tag_type === "keyword" && t.status === "negative")
      .map((t) => t.label.toLowerCase()),
  );

  const onToggleBucket = (b: "added" | "retired") =>
    setOpenBucket((p) => (p === b ? null : b));

  const retireTag = (tag: ImprovementTag) => {
    setLocalTags((prev) =>
      prev.map((t) =>
        t.tag_id === tag.tag_id
          ? { ...t, status: "negative" as ImprovementTagStatus, locked_by_merchant: true }
          : t,
      ),
    );
    tagFetcher.submit(
      { intent: "retireTag", productId: product.product_id, tagId: tag.tag_id },
      { method: "post" },
    );
  };

  const restoreTag = (tag: ImprovementTag) => {
    setLocalTags((prev) =>
      prev.map((t) =>
        t.tag_id === tag.tag_id ? { ...t, status: "positive" as ImprovementTagStatus } : t,
      ),
    );
    tagFetcher.submit(
      { intent: "restoreTag", productId: product.product_id, tagId: tag.tag_id },
      { method: "post" },
    );
  };

  const addManualTag = () => {
    const label = newTagLabel.trim();
    if (!label) return;
    const tempTag: ImprovementTag = {
      tag_id: `tmp-${Date.now()}`,
      label,
      tag_type: "merchant",
      status: "forced",
      score: 100,
      source: "merchant",
      locked_by_merchant: true,
    };
    setLocalTags((prev) => [...prev, tempTag]);
    setNewTagLabel("");
    tagFetcher.submit(
      { intent: "addTag", productId: product.product_id, label, tagType: "merchant" },
      { method: "post" },
    );
  };

  const addKeywordTag = (query: string) => {
    const tempTag: ImprovementTag = {
      tag_id: `tmp-${Date.now()}`,
      label: query,
      tag_type: "keyword",
      status: "forced",
      score: 100,
      source: "merchant",
      locked_by_merchant: true,
    };
    // Replace any existing keyword tag with the same label (e.g. a retired
    // one being re-added) — otherwise the label sits in both the added and
    // retired sets and both buttons disappear.
    setLocalTags((prev) => [
      ...prev.filter(
        (t) => !(t.tag_type === "keyword" && t.label.toLowerCase() === query.toLowerCase()),
      ),
      tempTag,
    ]);
    tagFetcher.submit(
      { intent: "addTag", productId: product.product_id, label: query, tagType: "keyword" },
      { method: "post" },
    );
  };

  const retireKeywordTag = (query: string) => {
    const existing = localTags.find(
      (t) => t.tag_type === "keyword" && t.label.toLowerCase() === query.toLowerCase(),
    );
    if (existing) {
      retireTag(existing);
    } else {
      const tempTag: ImprovementTag = {
        tag_id: `tmp-${Date.now()}`,
        label: query,
        tag_type: "keyword",
        status: "negative",
        score: 0,
        source: "merchant",
        locked_by_merchant: true,
      };
      setLocalTags((prev) => [...prev, tempTag]);
      tagFetcher.submit(
        { intent: "retireKeyword", productId: product.product_id, label: query, tagType: "keyword" },
        { method: "post" },
      );
    }
  };
  // Hide keywords with zero product fit — they are noise for the merchant.
  const displayedKeywords = product.seo_keywords.filter(
    (keyword) => (keyword.product_fit_score ?? 0) > 0,
  );
  // Coverage badge reflects the saved pack; live edits revalidate on save.
  // Memoized because keywordCoverage() runs regex-based substring matching over
  // every proposal field for each target keyword — wasteful to recompute on each
  // render (e.g. while typing or polling). Recomputes only when keywords/pack change.
  const { coverageByKeyword, usedKeywords } = useMemo(() => {
    const selectedTargets = product.seo_keywords
      .filter((keyword) => (keyword.target_rank ?? 999) <= 5)
      .slice(0, 5);
    const coverageTargets = selectedTargets.length > 0
      ? selectedTargets
      : product.seo_keywords.slice(0, 5);

    const byKeyword = new Map(
      coverageTargets.map((keyword) => [
        keyword.query.toLowerCase(),
        keywordCoverage(keyword.query, pack),
      ]),
    );
    const used = new Set(
      [...byKeyword.entries()]
        .filter(([, fields]) => fields.length > 0)
        .map(([query]) => query),
    );
    return { coverageByKeyword: byKeyword, usedKeywords: used };
  }, [product.seo_keywords, pack]);


  const productImageUrl = pack.current_product_images?.[0]?.url ?? null;

  return (
    <Box padding={productImageUrl ? "0" : "300"} borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface">
      <div style={{ display: "flex", alignItems: "stretch", borderRadius: "inherit", overflow: "hidden" }}>
        {productImageUrl && (
          <div
            style={{
              flex: "0 0 26%",
              maxWidth: 300,
              minWidth: 170,
              borderRight: "1px solid var(--p-color-border)",
            }}
          >
            <img
              src={productImageUrl}
              alt={pack.current_product_images?.[0]?.current_alt ?? product.product_title}
              style={{
                width: "100%",
                aspectRatio: "3 / 4",
                objectFit: "cover",
                display: "block",
              }}
            />
          </div>
        )}
        <div style={{ flex: 1, minWidth: 0, padding: productImageUrl ? "var(--p-space-300)" : 0 }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "var(--p-space-300)",
          justifyContent: "space-between",
          height: "100%",
        }}
      >
        <InlineStack gap="200" align="space-between" wrap>
          <BlockStack gap="100">
            <InlineStack gap="150" blockAlign="center">
              <Text as="p" variant="bodyMd" fontWeight="semibold">{product.product_title}</Text>
              {(() => {
                const parts: string[] = [];
                if ((pack.facts_missing?.length ?? 0) > 0) {
                  parts.push(`${t(locale, "marketAnalysisFactsMissing")} : ${(pack.facts_missing ?? []).join(" · ")}`);
                }
                const notImproved = (product.improvement_elements ?? []).filter((e) => !e.improved);
                if (notImproved.length > 0) {
                  parts.push(`${fr ? "Non amélioré" : "Not improved"} : ${notImproved.map((e) => e.label).join(", ")}`);
                }
                return parts.length > 0 ? (
                  <Tooltip content={parts.join(" — ")}>
                    <span style={{ display: "inline-flex", cursor: "help" }}>
                      <Icon source={AlertTriangleIcon} tone="warning" />
                    </span>
                  </Tooltip>
                ) : null;
              })()}
            </InlineStack>
          </BlockStack>
          <InlineStack gap="200" blockAlign="center">
            <Popover
              active={geoHelpOpen}
              onClose={() => setGeoHelpOpen(false)}
              preferredAlignment="left"
              activator={
                <Button
                  variant="tertiary"
                  icon={QuestionCircleIcon}
                  onClick={() => setGeoHelpOpen((o) => !o)}
                  accessibilityLabel={fr ? "Détail du Score GEO" : "GEO score breakdown"}
                />
              }
            >
              <Box padding="300" maxWidth="340px">
                <GeoScoreBreakdown components={product.geo_score_components} locale={locale} />
              </Box>
            </Popover>
            <Badge tone={scoreTone(geoDisplayed)}>
              {`${t(locale, "productGeoScore")} ${geoDisplayed}/100`}
            </Badge>
            {product.business_profile_context_status === "stale" && (
              <Badge tone="attention">{t(locale, "marketAnalysisProfileContextStaleBadge")}</Badge>
            )}
            {product.business_profile_context_status === "unknown" && (
              <Badge tone="attention">{t(locale, "marketAnalysisProfileContextUnknownBadge")}</Badge>
            )}
            {isAnalyzing && <Spinner size="small" />}
          </InlineStack>
        </InlineStack>

        {product.product_summary && (
          <Text as="p" variant="bodySm">{product.product_summary}</Text>
        )}
        {product.target_customer && (
          <Text as="p" variant="bodySm" tone="subdued">
            {locale === "fr" ? "Client cible" : "Target customer"} :{" "}
            {typeof product.target_customer === "string"
              ? product.target_customer
              : Object.values(product.target_customer as Record<string, string>).join(" — ")}
          </Text>
        )}

        <ImprovementTags
          addedTags={addedTags}
          retiredTags={retiredTags}
          openBucket={openBucket}
          onToggle={onToggleBucket}
          onRetire={retireTag}
          onRestore={restoreTag}
          newLabel={newTagLabel}
          onNewLabelChange={setNewTagLabel}
          onAdd={addManualTag}
          locale={locale}
          leading={
            displayedKeywords.length > 0 ? (
              <Button size="slim" pressed={openSection === "keywords"} onClick={() => toggle("keywords")}>
                {fr
                  ? `Mots-clés (${displayedKeywords.filter((k) => !keywordTagLabels.has(k.query.toLowerCase())).length})`
                  : `Keywords (${displayedKeywords.filter((k) => !keywordTagLabels.has(k.query.toLowerCase())).length})`}
              </Button>
            ) : null
          }
          trailing={(() => {
            const completedKeys = new Set((pack.completed_questions ?? []).map((q) => q.key));
            const retiredKeys = new Set(pack.retired_question_keys ?? []);
            const activeCount = (pack.enrichment_questions ?? []).filter(
              (q) => !completedKeys.has(q.key) && !retiredKeys.has(q.key),
            ).length;
            // Nothing left to enrich → show an "optimized" badge instead of an
            // open Improve button (objective reached for this product).
            if (activeCount === 0) {
              return completedKeys.size > 0 || retiredKeys.size > 0 ? (
                <Badge tone="success">{t(locale, "productOptimizedBadge")}</Badge>
              ) : null;
            }
            return (
              <Button size="slim" variant="primary" pressed={enrichmentOpen} onClick={() => setEnrichmentOpen((v) => !v)}>
                {(fr ? "Améliorer" : "Improve") + ` (${activeCount})`}
              </Button>
            );
          })()}
        />

        {applyResult && (
          <Banner tone={applyResult.ok ? "success" : "critical"}>
            {applyResult.ok ? (
              <BlockStack gap="100">
                {Object.entries(applyResult.results ?? {}).map(([field, res]) => (
                  <Text key={field} as="p" variant="bodySm">
                    {field} : {res.applied ? (fr ? "✓ appliqué" : "✓ applied") : `✗ ${res.error ?? (fr ? "échec" : "failed")}`}
                  </Text>
                ))}
                {Object.values(applyResult.results ?? {}).some((r) => r.applied) && (
                  <Text as="p" variant="bodySm" tone="subdued">
                    {fr ? "Résultats dans 28 j" : "Results in 28d"}
                  </Text>
                )}
              </BlockStack>
            ) : (
              <Text as="p" variant="bodySm">{applyResult.error}</Text>
            )}
          </Banner>
        )}

        <ProductContentProposals
          product={
            pack
              ? { ...product, content_test_pack: { ...pack, applied_fields: appliedFields } }
              : product
          }
          locale={locale}
          isAnalyzing={isAnalyzing}
          onEnrichAndAnalyze={onEnrichAndAnalyze}
          analyzeDisabled={analyzeDisabled}
          layout="buttons"
          showKeywordSources={false}
          checkedApplyFields={checkedApplyFields}
          onToggleApplyField={onToggleApplyField}
          onRetireQuestion={onRetireQuestion}
          onRestoreQuestion={onRestoreQuestion}
          onValidateQuestion={onValidateQuestion}
          enrichmentOpen={enrichmentOpen}
          applyAction={
            checkedApplyFields.size > 0 ? (
              <Button size="slim" variant="primary" loading={applyLoading} onClick={handleApplyProposals}>
                {fr ? "Valider" : "Apply"}
              </Button>
            ) : null
          }
        />

        {pack.recommended_internal_links && pack.recommended_internal_links.length > 0 && (
          <InlineStack gap="150" wrap>
            <Button size="slim" pressed={openSection === "links"} onClick={() => toggle("links")}>
              {`${t(locale, "marketAnalysisInternalLinks")} (${pack.recommended_internal_links.length})`}
            </Button>
          </InlineStack>
        )}

        {displayedKeywords.length > 0 && (
          <Collapsible id={`kw-${product.product_id}`} open={openSection === "keywords"}>
              <Box paddingBlockStart="200">
                <BlockStack gap="200">
                  {[...displayedKeywords]
                    .sort((a, b) => {
                      const rank = (q: string) =>
                        retiredKeywordLabels.has(q.toLowerCase())
                          ? 2
                          : addedKeywordLabels.has(q.toLowerCase()) || usedKeywords.has(q.toLowerCase())
                          ? 0
                          : 1;
                      return rank(a.query) - rank(b.query);
                    })
                    .map((k, idx) => {
                      const isRetired = retiredKeywordLabels.has(k.query.toLowerCase());
                      const isAdded =
                        !isRetired &&
                        (addedKeywordLabels.has(k.query.toLowerCase()) ||
                          usedKeywords.has(k.query.toLowerCase()));
                      return (
                    <div
                      key={`${k.query}-${idx}`}
                      style={
                        isRetired
                          ? { outline: "2px solid var(--p-color-border-critical)", borderRadius: 8 }
                          : isAdded
                          ? { outline: "2px solid #F4C430", borderRadius: 8 }
                          : {}
                      }
                    >
                    <Box
                      padding="200"
                      borderWidth="025"
                      borderRadius="200"
                      borderColor="border"
                      background="bg-surface-secondary"
                    >
                      <BlockStack gap="100">
                        <InlineStack gap="200" align="space-between" wrap blockAlign="center">
                          <InlineStack gap="200" blockAlign="center" wrap>
                            <Text as="span" variant="bodySm" fontWeight="semibold">{k.query}</Text>
                            <Badge>{k.intent_type || "—"}</Badge>
                          </InlineStack>
                          <InlineStack gap="100" blockAlign="center">
                            {k.priority_score != null && (
                              <Badge tone={scoreTone(k.priority_score)}>
                                {`${fr ? "Priorité" : "Priority"} ${k.priority_score}`}
                              </Badge>
                            )}
                            <Badge
                              tone={
                                k.data_source === "llm_estimated" || k.data_source === "shopify" || k.data_source === "parent_estimated"
                                  ? undefined
                                  : scoreTone(k.demand_score)
                              }
                            >
                              {`${fr ? "Demande" : "Demand"} ${k.demand_score}${
                                k.data_source === "llm_estimated" || k.data_source === "shopify" || k.data_source === "parent_estimated"
                                  ? " (estimé)"
                                  : ""
                              }`}
                            </Badge>
                            <Badge tone="info">
                              {`${t(locale, "marketAnalysisDifficulty")} ${k.competition_score}`}
                            </Badge>
                            <Badge tone={scoreTone(k.product_fit_score)}>
                              {`Fit ${k.product_fit_score}`}
                            </Badge>
                            {!addedKeywordLabels.has(k.query.toLowerCase()) &&
                              (retiredKeywordLabels.has(k.query.toLowerCase()) ||
                                !usedKeywords.has(k.query.toLowerCase())) && (
                              <Button size="slim" onClick={() => addKeywordTag(k.query)}>
                                {fr ? "Ajouter" : "Add"}
                              </Button>
                            )}
                            {!retiredKeywordLabels.has(k.query.toLowerCase()) && (
                              <Button size="slim" variant="plain" tone="critical" onClick={() => retireKeywordTag(k.query)}>
                                {fr ? "Retirer" : "Retire"}
                              </Button>
                            )}
                          </InlineStack>
                        </InlineStack>
                        {k.gsc_impressions != null && (
                          <Text as="p" variant="bodySm" tone="subdued">
                            GSC: <strong>{k.gsc_impressions}</strong> impr., pos {k.gsc_position}
                          </Text>
                        )}
                        {(() => {
                          const notes = (k.notes ?? []).filter(
                            (n) => !/^seed (ajouté|added)/i.test(n) && !/aucune donnée gsc|no gsc data/i.test(n),
                          );
                          return notes.length > 0 ? (
                            <Text as="p" variant="bodySm" tone="subdued">
                              {notes.join(" · ")}
                            </Text>
                          ) : null;
                        })()}
                      </BlockStack>
                    </Box>
                    </div>
                      );
                    })}
                </BlockStack>
              </Box>
            </Collapsible>
        )}

        {pack.recommended_internal_links && pack.recommended_internal_links.length > 0 && (
          <Collapsible id={`links-${product.product_id}`} open={openSection === "links"}>
            <Box paddingBlockStart="200">
              <InternalLinksSection
                links={pack.recommended_internal_links}
                locale={locale}
              />
            </Box>
          </Collapsible>
        )}
      </div>
        </div>
      </div>
    </Box>
  );
}

function InternalLinksSection({
  links,
  locale,
}: {
  links: InternalLinkSuggestion[];
  locale: Locale;
}) {
  const reasonLabel = (reason: InternalLinkSuggestion["reason"]) => {
    if (reason === "sibling_product") return t(locale, "marketAnalysisInternalLinksReasonSibling");
    if (reason === "collection_parent") return t(locale, "marketAnalysisInternalLinksReasonCollection");
    return t(locale, "marketAnalysisInternalLinksReasonArticle");
  };
  return (
    <BlockStack gap="200">
      {links.map((link, i) => (
        <Box
          key={`${link.target_url}-${i}`}
          paddingBlock="200"
          paddingInline="300"
          background="bg-surface-secondary"
          borderRadius="200"
        >
          <BlockStack gap="100">
            <InlineStack gap="200" blockAlign="center">
              <Text as="span" variant="bodySm">
                <strong>{link.target_title || link.target_url}</strong>
              </Text>
              <Badge tone={link.confidence === "high" ? "success" : "info"}>
                {reasonLabel(link.reason)}
              </Badge>
            </InlineStack>
            <Text as="p" variant="bodySm" tone="subdued">
              {link.target_url}
            </Text>
            {link.anchors.length > 0 ? (
              <InlineStack gap="100" wrap>
                {link.anchors.map((anchor, j) => (
                  <Badge key={j}>{anchor}</Badge>
                ))}
              </InlineStack>
            ) : null}
          </BlockStack>
        </Box>
      ))}
    </BlockStack>
  );
}
