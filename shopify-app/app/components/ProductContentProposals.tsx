/**
 * Per-product content proposals (meta title, meta description, description,
 * FAQ, blog) with edit / save / enrichment. Shared by the market-analysis
 * route and the dashboard active-products panel so both render identically.
 *
 * Self-contained: owns edit state and posts saves to the *current* route's
 * action with intent "saveProposals" — every route that renders this component
 * must handle that intent.
 *
 * `layout`:
 *  - "sections": all fields stacked (market-analysis proposals collapsible)
 *  - "buttons":  one toggle button per field, each revealing its section
 *    (dashboard active-products panel)
 */

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
  Text,
  TextField,
  Tooltip,
} from "@shopify/polaris";
import { AlertTriangleIcon } from "@shopify/polaris-icons";
import { useEffect, useState } from "react";
import { t, type Locale } from "../lib/i18n";
import {
  type ContentTestPack,
  type ProductResult,
  highlightKeywords,
  merchantAnswersFromPack,
  qualityWarningText,
} from "../lib/marketAnalysisShared";

type FieldKey = "meta_title" | "meta_description" | "description" | "faq" | "blog";

export function ProductContentProposals({
  product,
  locale,
  isAnalyzing,
  onEnrichAndAnalyze,
  analyzeDisabled,
  layout,
}: {
  product: ProductResult;
  locale: Locale;
  isAnalyzing: boolean;
  onEnrichAndAnalyze: (answers: Record<string, string>) => void;
  analyzeDisabled: boolean;
  layout: "sections" | "buttons";
}) {
  const pack = product.content_test_pack;
  const coverageTargets = (() => {
    const primary = product.seo_keywords
      .filter((keyword) => (keyword.target_rank ?? 999) <= 5)
      .slice(0, 5);
    return primary.length > 0 ? primary : product.seo_keywords.slice(0, 5);
  })();
  const kwQueries = coverageTargets.map((keyword) => keyword.query);

  const [editMode, setEditMode] = useState(false);
  const [editedPack, setEditedPack] = useState<ContentTestPack>({ ...pack });
  const [showEnrichmentQuestions, setShowEnrichmentQuestions] = useState(false);
  const [enrichmentAnswers, setEnrichmentAnswers] = useState<Record<string, string>>(
    () => merchantAnswersFromPack(pack),
  );
  const [openField, setOpenField] = useState<FieldKey | null>(null);
  const toggleField = (f: FieldKey) => setOpenField((p) => (p === f ? null : f));

  const saveFetcher = useFetcher<{ type: string; error: string | null }>();
  const isSaving = saveFetcher.state !== "idle";

  const packSignature = JSON.stringify(pack);
  useEffect(() => {
    if (!editMode) {
      setEditedPack({ ...pack });
      setShowEnrichmentQuestions(false);
      setEnrichmentAnswers(merchantAnswersFromPack(pack));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packSignature]);

  useEffect(() => {
    if (saveFetcher.data?.type === "saveProposals" && !saveFetcher.data.error) {
      setEditedPack((previous) => ({
        ...previous,
        content_quality: {
          publish_ready: false,
          issues: ["merchant_edit_requires_revalidation"],
        },
      }));
      setEditMode(false);
    }
  }, [saveFetcher.data]);

  const updateProp = (key: keyof ContentTestPack, value: string) =>
    setEditedPack((prev) => ({ ...prev, [key]: value }));

  const updateFaq = (idx: number, field: "q" | "a", value: string) =>
    setEditedPack((prev) => {
      const faq = [...prev.proposed_faq];
      faq[idx] = { ...faq[idx], [field]: value };
      return { ...prev, proposed_faq: faq };
    });

  const addFaqItem = () =>
    setEditedPack((prev) => ({
      ...prev,
      proposed_faq: [...prev.proposed_faq, { q: "", a: "" }],
    }));

  const removeFaqItem = (idx: number) =>
    setEditedPack((prev) => ({
      ...prev,
      proposed_faq: prev.proposed_faq.filter((_, i) => i !== idx),
    }));

  const handleSaveProposals = () => {
    const proposals = {
      proposed_meta_title: editedPack.proposed_meta_title,
      proposed_meta_description: editedPack.proposed_meta_description,
      proposed_product_description: editedPack.proposed_product_description,
      proposed_faq: editedPack.proposed_faq,
      proposed_blog_title: editedPack.proposed_blog_title,
      proposed_blog_intro: editedPack.proposed_blog_intro,
      proposed_blog_outline: editedPack.proposed_blog_outline,
    };
    saveFetcher.submit(
      { intent: "saveProposals", productId: product.product_id, proposals: JSON.stringify(proposals) },
      { method: "POST" },
    );
  };

  const enrichmentQuestions = editedPack.enrichment_questions ?? [];
  const canSubmitEnrichment = enrichmentQuestions.some(
    (question) => (enrichmentAnswers[question.key] ?? "").trim().length > 0,
  );

  // Compact quality warning shown behind a warning icon (sections layout only;
  // the buttons layout renders it next to the product title in the parent).
  const qualityWarningTooltip = qualityWarningText(editedPack, locale);

  // ── Field renderers ────────────────────────────────────────────────────────
  const renderMetaTitle = () => (
    <BlockStack gap="100">
      {layout === "sections" && <Text as="h4" variant="headingXs">Meta title</Text>}
      <Text as="p" variant="bodySm" tone="subdued">
        {locale === "fr" ? "Actuel" : "Current"} : {pack.current_meta_title}
      </Text>
      {editMode ? (
        <TextField
          label=""
          labelHidden
          value={editedPack.proposed_meta_title}
          onChange={(v) => updateProp("proposed_meta_title", v)}
          autoComplete="off"
          maxLength={70}
          showCharacterCount
        />
      ) : (
        <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
          <Text as="p" variant="bodySm">{highlightKeywords(editedPack.proposed_meta_title, kwQueries)}</Text>
        </Box>
      )}
    </BlockStack>
  );

  const renderMetaDescription = () => (
    <BlockStack gap="100">
      {layout === "sections" && <Text as="h4" variant="headingXs">Meta description</Text>}
      <Text as="p" variant="bodySm" tone="subdued">
        {locale === "fr" ? "Actuelle" : "Current"} :{" "}
        {pack.current_meta_description || (locale === "fr" ? "absente" : "missing")}
      </Text>
      {editMode ? (
        <TextField
          label=""
          labelHidden
          value={editedPack.proposed_meta_description}
          onChange={(v) => updateProp("proposed_meta_description", v)}
          multiline={3}
          autoComplete="off"
          maxLength={160}
          showCharacterCount
        />
      ) : (
        <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
          <Text as="p" variant="bodySm">{highlightKeywords(editedPack.proposed_meta_description, kwQueries)}</Text>
        </Box>
      )}
    </BlockStack>
  );

  const renderProductDescription = () => (
    <BlockStack gap="100">
      {layout === "sections" && (
        <Text as="h4" variant="headingXs">{t(locale, "contentTypeProductDescription")}</Text>
      )}
      {editMode ? (
        <TextField
          label=""
          labelHidden
          value={editedPack.proposed_product_description}
          onChange={(v) => updateProp("proposed_product_description", v)}
          multiline={5}
          autoComplete="off"
        />
      ) : (
        <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
          <Text as="p" variant="bodySm">{highlightKeywords(editedPack.proposed_product_description, kwQueries)}</Text>
        </Box>
      )}
    </BlockStack>
  );

  const renderFaq = () => (
    <BlockStack gap="100">
      <InlineStack gap="200" blockAlign="center">
        {layout === "sections" && <Text as="h4" variant="headingXs">FAQ</Text>}
        {editedPack.faq_sync?.applied && editedPack.faq_sync.applied_at && (
          <Badge tone="success" size="small">
            {locale === "fr"
              ? `Synchronisée sur Shopify le ${new Date(editedPack.faq_sync.applied_at).toLocaleDateString("fr-FR")}`
              : `Synced to Shopify on ${new Date(editedPack.faq_sync.applied_at).toLocaleDateString("en-US")}`}
          </Badge>
        )}
        {editedPack.faq_sync?.applied === false && editedPack.faq_sync.error && (
          <Badge tone="attention" size="small">
            {locale === "fr" ? "Synchro Shopify en attente" : "Shopify sync pending"}
          </Badge>
        )}
      </InlineStack>
      {editedPack.proposed_faq.map((item, i) => (
        <Box key={i} padding="200" borderWidth="025" borderRadius="200" borderColor="border">
          <BlockStack gap="150">
            {editMode ? (
              <>
                <InlineStack gap="200" align="space-between" blockAlign="start">
                  <Box width="100%">
                    <TextField
                      label={locale === "fr" ? "Question" : "Question"}
                      value={item.q}
                      onChange={(v) => updateFaq(i, "q", v)}
                      autoComplete="off"
                    />
                  </Box>
                  <Button size="slim" variant="plain" tone="critical" onClick={() => removeFaqItem(i)}>
                    ×
                  </Button>
                </InlineStack>
                <TextField
                  label={locale === "fr" ? "Réponse" : "Answer"}
                  value={item.a}
                  onChange={(v) => updateFaq(i, "a", v)}
                  multiline={3}
                  autoComplete="off"
                />
              </>
            ) : (
              <>
                <Text as="p" variant="headingXs">{highlightKeywords(item.q, kwQueries)}</Text>
                <Text as="p" variant="bodySm">{highlightKeywords(item.a, kwQueries)}</Text>
              </>
            )}
          </BlockStack>
        </Box>
      ))}
      {editMode && (
        <Button size="slim" variant="plain" onClick={addFaqItem}>
          {locale === "fr" ? "+ Ajouter une question" : "+ Add question"}
        </Button>
      )}
    </BlockStack>
  );

  const renderBlog = () => (
    <BlockStack gap="100">
      {layout === "sections" && (
        <Text as="h4" variant="headingXs">
          {locale === "fr" ? "Idée d'article de blog" : "Blog article idea"}
        </Text>
      )}
      {editMode ? (
        <BlockStack gap="200">
          <TextField
            label={locale === "fr" ? "Titre" : "Title"}
            value={editedPack.proposed_blog_title}
            onChange={(v) => updateProp("proposed_blog_title", v)}
            autoComplete="off"
          />
          <TextField
            label="Intro"
            value={editedPack.proposed_blog_intro}
            onChange={(v) => updateProp("proposed_blog_intro", v)}
            multiline={3}
            autoComplete="off"
          />
          <TextField
            label={locale === "fr" ? "Plan (une section par ligne)" : "Outline (one section per line)"}
            value={editedPack.proposed_blog_outline.join("\n")}
            onChange={(v) =>
              setEditedPack((prev) => ({ ...prev, proposed_blog_outline: v.split("\n") }))
            }
            multiline={4}
            autoComplete="off"
          />
        </BlockStack>
      ) : (
        <>
          <Text as="p" variant="bodySm"><strong>{highlightKeywords(editedPack.proposed_blog_title, kwQueries)}</strong></Text>
          {editedPack.proposed_blog_intro && (
            <Text as="p" variant="bodySm" tone="subdued">{highlightKeywords(editedPack.proposed_blog_intro, kwQueries)}</Text>
          )}
          {editedPack.proposed_blog_outline.length > 0 && (
            <BlockStack gap="050">
              {editedPack.proposed_blog_outline.map((line, i) => (
                <Text key={i} as="p" variant="bodySm" tone="subdued">• {highlightKeywords(line, kwQueries)}</Text>
              ))}
            </BlockStack>
          )}
        </>
      )}
    </BlockStack>
  );

  const fields: Array<{ key: FieldKey; labelKey: Parameters<typeof t>[1]; has: boolean; render: () => JSX.Element }> = [
    { key: "meta_title", labelKey: "proposalFieldMetaTitle", has: Boolean(editedPack.proposed_meta_title), render: renderMetaTitle },
    { key: "meta_description", labelKey: "proposalFieldMetaDescription", has: Boolean(editedPack.proposed_meta_description), render: renderMetaDescription },
    { key: "description", labelKey: "proposalFieldDescription", has: Boolean(editedPack.proposed_product_description), render: renderProductDescription },
    { key: "faq", labelKey: "proposalFieldFaq", has: editedPack.proposed_faq.length > 0 || editMode, render: renderFaq },
    { key: "blog", labelKey: "proposalFieldBlog", has: Boolean(editedPack.proposed_blog_title), render: renderBlog },
  ];

  // ── Reusable chrome pieces ─────────────────────────────────────────────────
  const editButtons = editMode ? (
    <>
      <Button size="slim" loading={isSaving} onClick={handleSaveProposals}>
        {locale === "fr" ? "Sauvegarder" : "Save"}
      </Button>
      <Button size="slim" variant="plain" onClick={() => { setEditMode(false); setEditedPack({ ...pack }); }}>
        {locale === "fr" ? "Annuler" : "Cancel"}
      </Button>
    </>
  ) : (
    <Button size="slim" variant="plain" onClick={() => setEditMode(true)}>
      {locale === "fr" ? "Modifier" : "Edit"}
    </Button>
  );

  const saveError = saveFetcher.data?.type === "saveProposals" && saveFetcher.data.error ? (
    <Banner tone="critical">
      <Text as="p" variant="bodySm">{saveFetcher.data.error}</Text>
    </Banner>
  ) : null;

  const successBanner = !editMode && editedPack.content_quality?.publish_ready ? (
    <Banner tone="success">
      <BlockStack gap="050">
        <Text as="p" variant="bodySm">
          {locale === "fr"
            ? "Validation SEO/GEO réussie : cette proposition est éligible à une publication automatisée."
            : "SEO/GEO validation passed: this proposal is eligible for automated publishing."}
        </Text>
        {(editedPack.content_quality.evidence_ledger?.length ?? 0) > 0 && (
          <Text as="p" variant="bodySm">
            {locale === "fr"
              ? `${editedPack.content_quality.evidence_ledger?.length} affirmation(s) reliée(s) à des faits Shopify confirmés.`
              : `${editedPack.content_quality.evidence_ledger?.length} claim(s) linked to confirmed Shopify facts.`}
          </Text>
        )}
      </BlockStack>
    </Banner>
  ) : null;

  const warningIcon = !editMode && qualityWarningTooltip ? (
    <Tooltip content={qualityWarningTooltip}>
      <span style={{ display: "inline-flex", cursor: "help" }}>
        <Icon source={AlertTriangleIcon} tone="warning" />
      </span>
    </Tooltip>
  ) : null;

  const enrichmentBlock = !editMode && enrichmentQuestions.length > 0 ? (
    <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border-secondary">
      <BlockStack gap="200">
        <InlineStack gap="200" blockAlign="center" wrap>
          <Text as="p" variant="bodySm" fontWeight="semibold">
            {locale === "fr" ? "Améliorer le contenu" : "Improve content"}
          </Text>
          <Button size="slim" variant="plain" onClick={() => setShowEnrichmentQuestions((open) => !open)}>
            {showEnrichmentQuestions
              ? (locale === "fr" ? "Réduire" : "Collapse")
              : (locale === "fr" ? "Compléter" : "Complete")}
          </Button>
        </InlineStack>
        <Collapsible id={`enrichment-${product.product_id}`} open={showEnrichmentQuestions}>
          <BlockStack gap="300">
            <Text as="p" variant="bodySm" tone="subdued">
              {locale === "fr"
                ? "Répondez seulement avec des informations exactes. Vos réponses sont injectées dans le prompt pour produire un contenu plus précis et ancré dans votre produit."
                : "Answer only with accurate information. Your answers are injected into the prompt to produce more precise, product-grounded content."}
            </Text>
            {enrichmentQuestions.map((question) => (
              <TextField
                key={question.key}
                label={question.question}
                helpText={question.why_it_matters}
                placeholder={question.placeholder}
                value={enrichmentAnswers[question.key] ?? ""}
                onChange={(value) => setEnrichmentAnswers((answers) => ({ ...answers, [question.key]: value }))}
                autoComplete="off"
                multiline={2}
              />
            ))}
            <InlineStack gap="200">
              <Button
                variant="primary"
                loading={isAnalyzing}
                disabled={!canSubmitEnrichment || analyzeDisabled}
                onClick={() => onEnrichAndAnalyze(enrichmentAnswers)}
              >
                {locale === "fr" ? "Régénérer avec mes réponses" : "Regenerate with my answers"}
              </Button>
            </InlineStack>
          </BlockStack>
        </Collapsible>
      </BlockStack>
    </Box>
  ) : null;

  const fieldButtons = fields.filter((f) => f.has).map((f) => (
    <Button
      key={f.key}
      size="slim"
      pressed={openField === f.key}
      onClick={() => toggleField(f.key)}
    >
      {t(locale, f.labelKey)}
    </Button>
  ));

  if (layout === "buttons") {
    const available = fields.filter((f) => f.has);
    return (
      <BlockStack gap="200">
        {saveError}
        {successBanner}
        {enrichmentBlock}
        {/* Field buttons with the edit control on the same row. */}
        <InlineStack gap="150" align="space-between" blockAlign="center" wrap>
          <InlineStack gap="150" wrap>{fieldButtons}</InlineStack>
          <InlineStack gap="150">{editButtons}</InlineStack>
        </InlineStack>
        {available.map((f) => (
          <Collapsible key={f.key} id={`field-${f.key}-${product.product_id}`} open={openField === f.key}>
            <Box paddingBlockStart="100">{f.render()}</Box>
          </Collapsible>
        ))}
      </BlockStack>
    );
  }

  // layout === "sections"
  return (
    <BlockStack gap="300">
      <InlineStack gap="200" align="end">{editButtons}</InlineStack>
      {saveError}
      {successBanner}
      {warningIcon}
      {enrichmentBlock}
      {fields.filter((f) => f.has).map((f) => (
        <div key={f.key}>{f.render()}</div>
      ))}
    </BlockStack>
  );
}
