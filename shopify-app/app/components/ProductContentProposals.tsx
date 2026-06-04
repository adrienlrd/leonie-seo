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

import { Form, useFetcher, useNavigation } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Checkbox,
  Collapsible,
  Icon,
  InlineStack,
  Text,
  TextField,
  Thumbnail,
  Tooltip,
} from "@shopify/polaris";
import { AlertTriangleIcon } from "@shopify/polaris-icons";
import { useEffect, useState } from "react";
import { t, type Locale } from "../lib/i18n";
import {
  type ContentTestPack,
  type ProductResult,
  KeywordSourceBadge,
  highlightKeywords,
  keywordCoverage,
  merchantAnswersFromPack,
  qualityWarningText,
} from "../lib/marketAnalysisShared";

export type FieldKey = "meta_title" | "meta_description" | "alt_text" | "description" | "faq" | "blog";

const APPLY_FIELD_KEYS: FieldKey[] = ["meta_title", "meta_description", "alt_text", "description"];

export function ProductContentProposals({
  product,
  locale,
  isAnalyzing,
  onEnrichAndAnalyze,
  analyzeDisabled,
  layout,
  showKeywordSources = true,
  checkedApplyFields,
  onToggleApplyField,
}: {
  product: ProductResult;
  locale: Locale;
  isAnalyzing: boolean;
  onEnrichAndAnalyze: (answers: Record<string, string>) => void;
  analyzeDisabled: boolean;
  layout: "sections" | "buttons";
  showKeywordSources?: boolean;
  checkedApplyFields?: Set<FieldKey>;
  onToggleApplyField?: (field: FieldKey) => void;
}) {
  const pack = product.content_test_pack;
  const seoKeywords = product.seo_keywords ?? [];
  const coverageTargets = (() => {
    const primary = seoKeywords
      .filter((keyword) => (keyword.target_rank ?? 999) <= 5)
      .slice(0, 5);
    return primary.length > 0 ? primary : seoKeywords.slice(0, 5);
  })();
  const kwQueries = coverageTargets.map((keyword) => keyword.query);

  const fieldHasNewProposal = (key: FieldKey): boolean => {
    switch (key) {
      case "meta_title":
        return Boolean(pack.proposed_meta_title) && pack.proposed_meta_title !== pack.current_meta_title;
      case "meta_description":
        return Boolean(pack.proposed_meta_description) && pack.proposed_meta_description !== pack.current_meta_description;
      case "description":
        return Boolean(pack.proposed_product_description);
      case "alt_text":
        return (pack.proposed_image_alts ?? []).some((a) => Boolean(a.proposed_alt));
      default:
        return false;
    }
  };

  // Global edit toggle (sections layout) + per-field edit toggle (buttons layout).
  const [editMode, setEditMode] = useState(false);
  const [editingField, setEditingField] = useState<FieldKey | null>(null);
  const [editedPack, setEditedPack] = useState<ContentTestPack>({ ...pack });
  const [showEnrichmentQuestions, setShowEnrichmentQuestions] = useState(false);
  const [enrichmentAnswers, setEnrichmentAnswers] = useState<Record<string, string>>(
    () => merchantAnswersFromPack(pack),
  );
  const [openField, setOpenField] = useState<FieldKey | null>(null);
  const toggleField = (f: FieldKey) => setOpenField((p) => (p === f ? null : f));
  const [showKeywords, setShowKeywords] = useState(false);

  const saveFetcher = useFetcher<{ type: string; error: string | null }>();
  const isSaving = saveFetcher.state !== "idle";
  const navigation = useNavigation();
  const generateAction = `/app/blog?productId=${encodeURIComponent(product.product_id)}`;
  const isGenerating =
    navigation.state !== "idle" && navigation.formAction === generateAction;

  const packSignature = JSON.stringify(pack);
  useEffect(() => {
    if (!editMode && editingField === null) {
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
      setEditingField(null);
    }
  }, [saveFetcher.data]);

  const updateProp = (key: keyof ContentTestPack, value: string) =>
    setEditedPack((prev) => ({ ...prev, [key]: value }));

  const updateImageAlt = (idx: number, value: string) =>
    setEditedPack((prev) => {
      const images = prev.current_product_images ?? [];
      const alts = [...(prev.proposed_image_alts ?? [])];
      // Pad so an image without an LLM alt can still be edited.
      while (alts.length < images.length) {
        alts.push({ image_id: images[alts.length]?.id ?? "", proposed_alt: "" });
      }
      alts[idx] = { ...alts[idx], proposed_alt: value };
      return { ...prev, proposed_image_alts: alts };
    });

  const updateFaq = (idx: number, field: "q" | "a", value: string) =>
    setEditedPack((prev) => {
      const faq = [...(prev.proposed_faq ?? [])];
      faq[idx] = { ...faq[idx], [field]: value };
      return { ...prev, proposed_faq: faq };
    });

  const addFaqItem = () =>
    setEditedPack((prev) => ({
      ...prev,
      proposed_faq: [...(prev.proposed_faq ?? []), { q: "", a: "" }],
    }));

  const removeFaqItem = (idx: number) =>
    setEditedPack((prev) => ({
      ...prev,
      proposed_faq: (prev.proposed_faq ?? []).filter((_, i) => i !== idx),
    }));

  const handleSaveProposals = () => {
    const proposals = {
      proposed_meta_title: editedPack.proposed_meta_title,
      proposed_meta_description: editedPack.proposed_meta_description,
      proposed_product_description: editedPack.proposed_product_description,
      proposed_faq: editedPack.proposed_faq ?? [],
      proposed_blog_title: editedPack.proposed_blog_title,
      proposed_blog_intro: editedPack.proposed_blog_intro,
      proposed_blog_outline: editedPack.proposed_blog_outline ?? [],
      proposed_blog_ideas: editedPack.proposed_blog_ideas,
      proposed_image_alts: editedPack.proposed_image_alts ?? [],
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
  const renderMetaTitle = (editing: boolean) => (
    <BlockStack gap="100">
      {layout === "sections" && <Text as="h4" variant="headingXs">Meta title</Text>}
      {editing ? (
        <>
          <Text as="p" variant="bodySm" tone="subdued">
            {locale === "fr" ? "Actuel" : "Current"} : {pack.current_meta_title || "—"}
          </Text>
          <TextField
            label=""
            labelHidden
            value={editedPack.proposed_meta_title}
            onChange={(v) => updateProp("proposed_meta_title", v)}
            autoComplete="off"
            maxLength={70}
            showCharacterCount
          />
        </>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div>
            <Text as="p" variant="bodySm" tone="subdued" fontWeight="semibold">
              {locale === "fr" ? "Actuel" : "Current"}
            </Text>
            <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
              <Text as="p" variant="bodySm" tone="subdued">{pack.current_meta_title || "—"}</Text>
            </Box>
          </div>
          <div>
            <Text as="p" variant="bodySm" fontWeight="semibold">
              {locale === "fr" ? "Proposé" : "Proposed"}
            </Text>
            <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
              <Text as="p" variant="bodySm">{highlightKeywords(editedPack.proposed_meta_title, kwQueries)}</Text>
            </Box>
          </div>
        </div>
      )}
    </BlockStack>
  );

  const renderMetaDescription = (editing: boolean) => (
    <BlockStack gap="100">
      {layout === "sections" && <Text as="h4" variant="headingXs">Meta description</Text>}
      {editing ? (
        <>
          <Text as="p" variant="bodySm" tone="subdued">
            {locale === "fr" ? "Actuelle" : "Current"} :{" "}
            {pack.current_meta_description || (locale === "fr" ? "absente" : "missing")}
          </Text>
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
        </>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div>
            <Text as="p" variant="bodySm" tone="subdued" fontWeight="semibold">
              {locale === "fr" ? "Actuelle" : "Current"}
            </Text>
            <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
              <Text as="p" variant="bodySm" tone="subdued">
                {pack.current_meta_description || (locale === "fr" ? "— absente" : "— missing")}
              </Text>
            </Box>
          </div>
          <div>
            <Text as="p" variant="bodySm" fontWeight="semibold">
              {locale === "fr" ? "Proposée" : "Proposed"}
            </Text>
            <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
              <Text as="p" variant="bodySm">{highlightKeywords(editedPack.proposed_meta_description, kwQueries)}</Text>
            </Box>
          </div>
        </div>
      )}
    </BlockStack>
  );

  const renderProductDescription = (editing: boolean) => (
    <BlockStack gap="100">
      {layout === "sections" && (
        <Text as="h4" variant="headingXs">{t(locale, "contentTypeProductDescription")}</Text>
      )}
      {editing ? (
        <>
          {pack.current_product_description_summary && (
            <Text as="p" variant="bodySm" tone="subdued">
              {locale === "fr" ? "Actuelle" : "Current"} : {pack.current_product_description_summary}
            </Text>
          )}
          <TextField
            label=""
            labelHidden
            value={editedPack.proposed_product_description}
            onChange={(v) => updateProp("proposed_product_description", v)}
            multiline={5}
            autoComplete="off"
          />
        </>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div>
            <Text as="p" variant="bodySm" tone="subdued" fontWeight="semibold">
              {locale === "fr" ? "Actuelle" : "Current"}
            </Text>
            <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
              <Text as="p" variant="bodySm" tone="subdued">
                {pack.current_product_description_summary || "—"}
              </Text>
            </Box>
          </div>
          <div>
            <Text as="p" variant="bodySm" fontWeight="semibold">
              {locale === "fr" ? "Proposée" : "Proposed"}
            </Text>
            <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
              <Text as="p" variant="bodySm">{highlightKeywords(editedPack.proposed_product_description, kwQueries)}</Text>
            </Box>
          </div>
        </div>
      )}
    </BlockStack>
  );

  const renderFaq = (editing: boolean) => (
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
      {(editedPack.proposed_faq ?? []).map((item, i) => (
        <Box key={i} padding="200" borderWidth="025" borderRadius="200" borderColor="border">
          <BlockStack gap="150">
            {editing ? (
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
      {editing && (
        <Button size="slim" variant="plain" onClick={addFaqItem}>
          {locale === "fr" ? "+ Ajouter une question" : "+ Add question"}
        </Button>
      )}
    </BlockStack>
  );

  const renderBlog = (editing: boolean) => (
    <BlockStack gap="100">
      {layout === "sections" && (
        <Text as="h4" variant="headingXs">
          {locale === "fr" ? "Idée d'article de blog" : "Blog article idea"}
        </Text>
      )}
      {editing ? (
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
            value={(editedPack.proposed_blog_outline ?? []).join("\n")}
            onChange={(v) =>
              setEditedPack((prev) => ({ ...prev, proposed_blog_outline: v.split("\n") }))
            }
            multiline={4}
            autoComplete="off"
          />
        </BlockStack>
      ) : (
        <>
          {(() => {
            const blogIdeas = (editedPack.proposed_blog_ideas && editedPack.proposed_blog_ideas.length > 0)
              ? editedPack.proposed_blog_ideas.slice(0, 5)
              : editedPack.proposed_blog_title
                ? [{
                    title: editedPack.proposed_blog_title,
                    target_keyword: kwQueries[0] ?? "",
                    intro: editedPack.proposed_blog_intro,
                    outline: editedPack.proposed_blog_outline ?? [],
                  }]
                : [];
            return (
              <BlockStack gap="200">
                {blogIdeas.map((idea, index) => (
                  <Box key={`${idea.title}-${index}`} padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
                    <BlockStack gap="150">
                      <InlineStack gap="200" align="space-between" blockAlign="start">
                        <BlockStack gap="050">
                          <Text as="p" variant="bodySm"><strong>{highlightKeywords(idea.title, kwQueries)}</strong></Text>
                          {idea.target_keyword && (
                            <Badge tone="info" size="small">{idea.target_keyword}</Badge>
                          )}
                        </BlockStack>
                        <Form method="post" action={generateAction}>
                          <input type="hidden" name="intent" value="createFromProduct" />
                          <input type="hidden" name="blogIdeaIndex" value={String(index)} />
                          <Button size="slim" variant="primary" submit loading={isGenerating}>
                            {locale === "fr" ? "Générer l'article" : "Generate article"}
                          </Button>
                        </Form>
                      </InlineStack>
                      {idea.intro && (
                        <Text as="p" variant="bodySm" tone="subdued">{highlightKeywords(idea.intro, kwQueries)}</Text>
                      )}
                      {idea.outline && idea.outline.length > 0 && (
                        <BlockStack gap="050">
                          {idea.outline.map((line, i) => (
                            <Text key={i} as="p" variant="bodySm" tone="subdued">• {highlightKeywords(line, kwQueries)}</Text>
                          ))}
                        </BlockStack>
                      )}
                    </BlockStack>
                  </Box>
                ))}
              </BlockStack>
            );
          })()}
          <BlockStack gap="200">
            <InlineStack gap="200">
              <Button size="slim" variant="plain" url="/app/blog">
                {locale === "fr" ? "Voir tous les blogs" : "View all blogs"}
              </Button>
            </InlineStack>
            {isGenerating && (
              <Text as="p" variant="bodySm" tone="subdued">
                {locale === "fr"
                  ? "Génération en cours — environ 20-40 secondes selon le nombre de sections."
                  : "Generating — about 20-40 seconds depending on the number of sections."}
              </Text>
            )}
          </BlockStack>
        </>
      )}
    </BlockStack>
  );

  const renderAltText = (editing: boolean) => (
    <BlockStack gap="150">
      {layout === "sections" && (
        <Text as="h4" variant="headingXs">{t(locale, "proposalFieldAltText")}</Text>
      )}
      {(editedPack.current_product_images ?? []).map((image, i) => {
        const proposed = editedPack.proposed_image_alts?.[i]?.proposed_alt ?? "";
        return (
          <Box key={image.id || i} padding="200" borderWidth="025" borderRadius="200" borderColor="border">
            <InlineStack gap="300" blockAlign="start" wrap={false}>
              <Thumbnail source={image.url} alt={image.current_alt ?? ""} size="small" />
              <Box width="100%">
                <BlockStack gap="100">
                  <Text as="p" variant="bodySm" tone="subdued">
                    {locale === "fr" ? `Image ${i + 1}` : `Image ${i + 1}`}
                    {image.current_alt
                      ? ` — ${locale === "fr" ? "Actuel" : "Current"} : ${image.current_alt}`
                      : ` — ${locale === "fr" ? "aucun alt actuel" : "no current alt"}`}
                  </Text>
                  {editing ? (
                    <TextField
                      label=""
                      labelHidden
                      value={proposed}
                      onChange={(v) => updateImageAlt(i, v)}
                      autoComplete="off"
                      maxLength={125}
                      showCharacterCount
                    />
                  ) : (
                    <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border" background="bg-surface-secondary">
                      <Text as="p" variant="bodySm">{highlightKeywords(proposed, kwQueries)}</Text>
                    </Box>
                  )}
                </BlockStack>
              </Box>
            </InlineStack>
          </Box>
        );
      })}
    </BlockStack>
  );

  const fields: Array<{ key: FieldKey; labelKey: Parameters<typeof t>[1]; has: boolean; render: (editing: boolean) => JSX.Element }> = [
    { key: "meta_title", labelKey: "proposalFieldMetaTitle", has: Boolean(editedPack.proposed_meta_title), render: renderMetaTitle },
    { key: "meta_description", labelKey: "proposalFieldMetaDescription", has: Boolean(editedPack.proposed_meta_description), render: renderMetaDescription },
    { key: "alt_text", labelKey: "proposalFieldAltText", has: (editedPack.current_product_images?.length ?? 0) > 0, render: renderAltText },
    { key: "description", labelKey: "proposalFieldDescription", has: Boolean(editedPack.proposed_product_description), render: renderProductDescription },
    { key: "faq", labelKey: "proposalFieldFaq", has: (editedPack.proposed_faq?.length ?? 0) > 0 || editMode, render: renderFaq },
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

  // Transparency: where each targeted keyword comes from and where it is used.
  // Directly answers the merchant's "which keywords were actually used?" question.
  const targetedKeywords = [...seoKeywords]
    .sort((a, b) => (a.target_rank ?? 999) - (b.target_rank ?? 999))
    .slice(0, 8);

  const keywordSourcesPanel = showKeywordSources && targetedKeywords.length > 0 ? (
    <Box padding="200" borderWidth="025" borderRadius="200" borderColor="border-secondary">
      <BlockStack gap="200">
        <Text as="h4" variant="headingXs">
          {t(locale, "marketAnalysisKeywordSourcesTitle")}
        </Text>
        <Text as="p" variant="bodySm" tone="subdued">
          {t(locale, "marketAnalysisKeywordSourcesHelp")}
        </Text>
        <BlockStack gap="150">
          {targetedKeywords.map((kw) => {
            const used = keywordCoverage(kw.query, editedPack);
            const volume =
              kw.search_volume != null
                ? `${kw.search_volume.toLocaleString()} ${t(locale, "marketAnalysisVolume")}`
                : kw.gsc_impressions != null
                ? `${kw.gsc_impressions} impr. GSC`
                : null;
            return (
              <Box key={kw.query} paddingBlockEnd="100">
                <BlockStack gap="050">
                  <InlineStack gap="150" blockAlign="center" wrap>
                    <Text as="span" variant="bodySm" fontWeight="semibold">{kw.query}</Text>
                    <KeywordSourceBadge source={kw.data_source} locale={locale} />
                    {volume && (
                      <Text as="span" variant="bodySm" tone="subdued">{volume}</Text>
                    )}
                  </InlineStack>
                  <Text as="p" variant="bodySm" tone={used.length ? "subdued" : "critical"}>
                    {used.length
                      ? `${t(locale, "marketAnalysisKeywordUsedIn")} : ${used.join(", ")}`
                      : t(locale, "marketAnalysisKeywordUsedNowhere")}
                  </Text>
                </BlockStack>
              </Box>
            );
          })}
        </BlockStack>
      </BlockStack>
    </Box>
  ) : null;

  const fieldButtons = fields.filter((f) => f.has).map((f) => {
    const isApplyable = APPLY_FIELD_KEYS.includes(f.key);
    const isChecked = isApplyable && (checkedApplyFields?.has(f.key) ?? false);
    const showYellow = isApplyable && fieldHasNewProposal(f.key) && isChecked;
    return (
      <InlineStack key={f.key} gap="050" blockAlign="center">
        {isApplyable && onToggleApplyField && (
          <Checkbox
            label=""
            labelHidden
            checked={isChecked}
            onChange={() => onToggleApplyField(f.key)}
          />
        )}
        <div style={showYellow ? { outline: "2px solid #F4C430", borderRadius: 6 } : {}}>
          <Button size="slim" pressed={openField === f.key} onClick={() => toggleField(f.key)}>
            {t(locale, f.labelKey)}
          </Button>
        </div>
      </InlineStack>
    );
  });

  if (layout === "buttons") {
    const available = fields.filter((f) => f.has);
    return (
      <BlockStack gap="200">
        {saveError}
        {successBanner}
        {enrichmentBlock}
        <InlineStack gap="150" wrap>
          {keywordSourcesPanel && (
            <Button
              size="slim"
              pressed={showKeywords}
              onClick={() => setShowKeywords((v) => !v)}
            >
              {t(locale, "marketAnalysisKeywordSourcesTitle")}
            </Button>
          )}
          {fieldButtons}
        </InlineStack>
        <Collapsible id={`kw-sources-${product.product_id}`} open={showKeywords}>
          <Box paddingBlockStart="100">{keywordSourcesPanel}</Box>
        </Collapsible>
        {available.map((f) => (
          <Collapsible key={f.key} id={`field-${f.key}-${product.product_id}`} open={openField === f.key}>
            <Box paddingBlockStart="100">
              <BlockStack gap="200">
                {f.render(editingField === f.key)}
                {editingField === f.key ? (
                  <InlineStack gap="150">
                    <Button size="slim" loading={isSaving} onClick={handleSaveProposals}>
                      {locale === "fr" ? "Sauvegarder" : "Save"}
                    </Button>
                    <Button
                      size="slim"
                      variant="plain"
                      onClick={() => { setEditingField(null); setEditedPack({ ...pack }); }}
                    >
                      {locale === "fr" ? "Annuler" : "Cancel"}
                    </Button>
                  </InlineStack>
                ) : (
                  <InlineStack>
                    <Button size="slim" variant="plain" onClick={() => setEditingField(f.key)}>
                      {locale === "fr" ? "Modifier" : "Edit"}
                    </Button>
                  </InlineStack>
                )}
              </BlockStack>
            </Box>
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
      {keywordSourcesPanel}
      {enrichmentBlock}
      {fields.filter((f) => f.has).map((f) => (
        <div key={f.key}>{f.render(editMode)}</div>
      ))}
    </BlockStack>
  );
}
