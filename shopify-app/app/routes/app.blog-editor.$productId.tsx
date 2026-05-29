/**
 * Blog editor (Sprint 1) — per-section Auto/Manuel toggle, regenerate, and Shopify
 * draft publication. The merchant always reviews; the article is never published live
 * automatically in Sprint 1.
 */

import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useActionData, useFetcher, useLoaderData, useNavigate } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  ChoiceList,
  InlineStack,
  Modal,
  Page,
  Select,
  Spinner,
  Text,
  TextField,
} from "@shopify/polaris";
import { useEffect, useState } from "react";

import { callBackendForShop } from "../lib/api.server";
import { getLocale, type Locale } from "../lib/i18n";
import { authenticate } from "../shopify.server";

interface ConfirmedFact {
  key: string;
  value?: string | string[];
  source?: string;
  confidence?: string;
}

interface LoaderData {
  locale: Locale;
  shop: string;
  productId: string;
  productTitle: string;
  productSummary: string;
  targetCustomer: string;
  blogTitle: string;
  intro: string;
  outline: string[];
  confirmedFacts: ConfirmedFact[];
  error: string | null;
}

interface Section {
  h2: string;
  direct_answer: string;
  body: string;
  mode: "auto" | "manuel";
}

export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  const productId = params.productId ?? "";
  const res = await callBackendForShop(
    session.shop,
    `/api/shops/${session.shop}/market-analysis/latest`,
    { accessToken: session.accessToken },
  );
  if (!res.ok) {
    return json<LoaderData>({
      locale,
      shop: session.shop,
      productId,
      productTitle: "",
      productSummary: "",
      targetCustomer: "",
      blogTitle: "",
      intro: "",
      outline: [],
      confirmedFacts: [],
      error: `Failed to load analysis (${res.status})`,
    });
  }
  const data = (await res.json()) as { products?: Array<Record<string, unknown>> };
  const product = (data.products ?? []).find(
    (p) => String((p as { product_id?: string }).product_id) === productId,
  ) as Record<string, unknown> | undefined;
  if (!product) {
    return json<LoaderData>({
      locale,
      shop: session.shop,
      productId,
      productTitle: "",
      productSummary: "",
      targetCustomer: "",
      blogTitle: "",
      intro: "",
      outline: [],
      confirmedFacts: [],
      error: "Product not found in the latest analysis.",
    });
  }
  const pack = (product.content_test_pack ?? {}) as Record<string, unknown>;
  return json<LoaderData>({
    locale,
    shop: session.shop,
    productId,
    productTitle: String(product.product_title ?? ""),
    productSummary: String(product.product_summary ?? ""),
    targetCustomer: String(product.target_customer ?? ""),
    blogTitle: String(pack.proposed_blog_title ?? ""),
    intro: String(pack.proposed_blog_intro ?? ""),
    outline: ((pack.proposed_blog_outline as string[]) ?? []).map((s) => String(s)),
    confirmedFacts: ((pack.confirmed_facts as ConfirmedFact[]) ?? []) as ConfirmedFact[],
    error: null,
  });
};

interface ActionResult {
  type: string;
  ok: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any | null;
  error: string | null;
}

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const intent = String(form.get("intent") ?? "");
  const proxy = async (path: string, init?: RequestInit) =>
    callBackendForShop(session.shop, `/api/shops/${session.shop}${path}`, {
      accessToken: session.accessToken,
      ...init,
    });

  const respond = (ok: boolean, data: unknown, error: string | null = null) =>
    json<ActionResult>({ type: intent, ok, data: ok ? (data as ActionResult["data"]) : null, error });

  try {
    if (intent === "listBlogs") {
      const r = await proxy(`/blog/blogs`);
      return respond(r.ok, r.ok ? await r.json() : null, r.ok ? null : `${r.status}`);
    }
    if (intent === "regenerateSection" || intent === "generateAll") {
      const path = intent === "regenerateSection" ? `/blog/section` : `/blog/generate-all`;
      const r = await proxy(path, {
        method: "POST",
        body: String(form.get("payload") ?? "{}"),
      });
      return respond(r.ok, r.ok ? await r.json() : null, r.ok ? null : `${r.status}`);
    }
    if (intent === "publishDraft") {
      const r = await proxy(`/blog/publish-draft`, {
        method: "POST",
        body: String(form.get("payload") ?? "{}"),
      });
      return respond(r.ok, r.ok ? await r.json() : null, r.ok ? null : `${r.status}`);
    }
  } catch (exc) {
    return respond(false, null, String(exc));
  }
  return respond(false, null, "unknown intent");
};

export default function BlogEditorPage() {
  const data = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigate = useNavigate();
  const fr = data.locale === "fr";

  const [blogTitle, setBlogTitle] = useState(data.blogTitle);
  const [intro, setIntro] = useState(data.intro);
  const [sections, setSections] = useState<Section[]>(
    data.outline.map((h2) => ({ h2, direct_answer: "", body: "", mode: "auto" })),
  );
  const [authorType, setAuthorType] = useState<"Organization" | "Person">("Organization");
  const [authorName, setAuthorName] = useState("");
  const [authorUrl, setAuthorUrl] = useState("");
  const [publishOpen, setPublishOpen] = useState(false);
  const [blogs, setBlogs] = useState<Array<{ id: string; handle: string; title: string }>>([]);
  const [selectedBlog, setSelectedBlog] = useState<string>("");

  const fetcher = useFetcher<typeof action>();
  const isBusy = fetcher.state !== "idle";

  // When the action returns a section/full-blog result, splice it into state.
  useEffect(() => {
    const d = fetcher.data;
    if (!d) return;
    if (d.type === "listBlogs" && d.ok && d.data?.blogs) {
      setBlogs(d.data.blogs);
      if (d.data.blogs.length && !selectedBlog) setSelectedBlog(d.data.blogs[0].id);
    }
    if (d.type === "regenerateSection" && d.ok && d.data) {
      setSections((prev) =>
        prev.map((s) =>
          s.h2 === d.data.h2
            ? { ...s, direct_answer: d.data.direct_answer, body: d.data.body }
            : s,
        ),
      );
    }
    if (d.type === "generateAll" && d.ok && d.data?.sections) {
      setSections(
        d.data.sections.map((s: Section) => ({ ...s, mode: "auto" as const })),
      );
    }
    if (d.type === "publishDraft" && d.ok && d.data?.article) {
      // Bounce back to the dashboard once the draft was created.
      setPublishOpen(false);
      navigate("/app");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher.data]);

  const productCtx = {
    product_title: data.productTitle,
    product_summary: data.productSummary,
    target_customer: data.targetCustomer,
    confirmed_facts: data.confirmedFacts.map((f) => ({
      key: f.key,
      value: Array.isArray(f.value) ? f.value.join(", ") : String(f.value ?? ""),
    })),
  };

  const onRegenerate = (h2: string) =>
    fetcher.submit(
      {
        intent: "regenerateSection",
        payload: JSON.stringify({ ...productCtx, blog_title: blogTitle, h2_question: h2 }),
      },
      { method: "post" },
    );

  const onGenerateAll = () =>
    fetcher.submit(
      {
        intent: "generateAll",
        payload: JSON.stringify({
          ...productCtx,
          blog_title: blogTitle,
          h2_questions: sections.map((s) => s.h2),
        }),
      },
      { method: "post" },
    );

  const onOpenPublish = () => {
    setPublishOpen(true);
    fetcher.submit({ intent: "listBlogs" }, { method: "post" });
  };

  const onPublish = () => {
    fetcher.submit(
      {
        intent: "publishDraft",
        payload: JSON.stringify({
          blog_id: selectedBlog,
          title: blogTitle,
          intro,
          summary: intro.slice(0, 200),
          sections: sections.map((s) => ({
            h2: s.h2,
            direct_answer: s.direct_answer,
            body: s.body,
          })),
          author_type: authorType,
          author_name: authorName || data.shop,
          author_url: authorUrl || null,
          publisher_name: data.shop,
        }),
      },
      { method: "post" },
    );
  };

  if (data.error) {
    return (
      <Page title={fr ? "Éditeur de blog" : "Blog editor"}>
        <Banner tone="critical">
          <p>{data.error}</p>
        </Banner>
      </Page>
    );
  }

  const setSectionField = (idx: number, patch: Partial<Section>) =>
    setSections((prev) => prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)));

  return (
    <Page
      title={fr ? "Éditeur de blog" : "Blog editor"}
      subtitle={data.productTitle}
      backAction={{ content: fr ? "Retour" : "Back", onAction: () => navigate("/app") }}
      primaryAction={{
        content: fr ? "Publier en brouillon" : "Publish as draft",
        onAction: onOpenPublish,
        disabled: !blogTitle || sections.every((s) => !s.direct_answer),
      }}
      secondaryActions={[
        {
          content: fr ? "Tout générer (Auto)" : "Generate all (Auto)",
          onAction: onGenerateAll,
          loading: isBusy && fetcher.formData?.get("intent") === "generateAll",
        },
      ]}
    >
      <BlockStack gap="400">
        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">
              {fr ? "Titre + intro" : "Title + intro"}
            </Text>
            <TextField
              label={fr ? "Titre du blog" : "Blog title"}
              value={blogTitle}
              onChange={setBlogTitle}
              autoComplete="off"
            />
            <TextField
              label={fr ? "Introduction" : "Intro"}
              value={intro}
              onChange={setIntro}
              multiline={3}
              autoComplete="off"
            />
          </BlockStack>
        </Card>

        {sections.map((section, idx) => (
          <Card key={`${section.h2}-${idx}`}>
            <BlockStack gap="300">
              <InlineStack gap="200" align="space-between" blockAlign="center" wrap>
                <Text as="h3" variant="headingSm">
                  H{idx + 2} · {fr ? "Section" : "Section"} {idx + 1}
                </Text>
                <InlineStack gap="200">
                  <Badge tone={section.mode === "auto" ? "info" : "attention"}>
                    {section.mode === "auto"
                      ? fr ? "Auto" : "Auto"
                      : fr ? "Manuel" : "Manual"}
                  </Badge>
                  <Button
                    size="slim"
                    variant="plain"
                    onClick={() =>
                      setSectionField(idx, {
                        mode: section.mode === "auto" ? "manuel" : "auto",
                      })
                    }
                  >
                    {fr ? "Basculer" : "Toggle"}
                  </Button>
                  <Button
                    size="slim"
                    onClick={() => onRegenerate(section.h2)}
                    loading={
                      isBusy &&
                      fetcher.formData?.get("intent") === "regenerateSection" &&
                      String(fetcher.formData?.get("payload") ?? "").includes(section.h2)
                    }
                  >
                    {fr ? "Régénérer" : "Regenerate"}
                  </Button>
                </InlineStack>
              </InlineStack>
              <TextField
                label={fr ? "Question (H2)" : "Question (H2)"}
                value={section.h2}
                onChange={(v) => setSectionField(idx, { h2: v })}
                autoComplete="off"
              />
              <TextField
                label={
                  fr
                    ? "Réponse directe (40-60 mots, citable par les LLM)"
                    : "Direct answer (40-60 words, LLM-citable)"
                }
                value={section.direct_answer}
                onChange={(v) => setSectionField(idx, { direct_answer: v })}
                multiline={3}
                autoComplete="off"
                disabled={section.mode === "auto"}
              />
              <TextField
                label={fr ? "Corps de la section" : "Section body"}
                value={section.body}
                onChange={(v) => setSectionField(idx, { body: v })}
                multiline={6}
                autoComplete="off"
                disabled={section.mode === "auto"}
              />
              {section.mode === "auto" && (
                <Box>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {fr
                      ? "En mode Auto, la régénération réécrit la section. Bascule en Manuel pour éditer."
                      : "In Auto mode, Regenerate rewrites the section. Switch to Manual to edit."}
                  </Text>
                </Box>
              )}
            </BlockStack>
          </Card>
        ))}

        {actionData?.type === "publishDraft" && !actionData.ok && (
          <Banner tone="critical">
            <p>{actionData.error ?? "Publication failed."}</p>
          </Banner>
        )}
      </BlockStack>

      <Modal
        open={publishOpen}
        onClose={() => setPublishOpen(false)}
        title={fr ? "Publier le brouillon" : "Publish draft"}
        primaryAction={{
          content: fr ? "Créer le brouillon" : "Create draft",
          onAction: onPublish,
          loading: isBusy && fetcher.formData?.get("intent") === "publishDraft",
          disabled: !selectedBlog || !blogTitle,
        }}
        secondaryActions={[
          { content: fr ? "Annuler" : "Cancel", onAction: () => setPublishOpen(false) },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="300">
            {blogs.length === 0 ? (
              <InlineStack gap="200" blockAlign="center">
                <Spinner size="small" />
                <Text as="span">{fr ? "Chargement des blogs…" : "Loading blogs…"}</Text>
              </InlineStack>
            ) : (
              <Select
                label={fr ? "Blog de destination" : "Target blog"}
                options={blogs.map((b) => ({ label: b.title, value: b.id }))}
                value={selectedBlog}
                onChange={setSelectedBlog}
              />
            )}
            <ChoiceList
              title={fr ? "Auteur" : "Author"}
              choices={[
                {
                  label: fr ? "Organisation (par défaut)" : "Organization (default)",
                  value: "Organization",
                },
                {
                  label: fr ? "Personne réelle (renforce l'E-E-A-T)" : "Real person (boosts E-E-A-T)",
                  value: "Person",
                },
              ]}
              selected={[authorType]}
              onChange={(s) => setAuthorType((s[0] as "Organization" | "Person") ?? "Organization")}
            />
            <TextField
              label={fr ? "Nom de l'auteur" : "Author name"}
              value={authorName}
              onChange={setAuthorName}
              autoComplete="off"
              placeholder={authorType === "Person" ? "Adrien Delacroix" : data.shop}
            />
            {authorType === "Person" && (
              <TextField
                label={fr ? "URL du profil auteur (optionnel)" : "Author profile URL (optional)"}
                value={authorUrl}
                onChange={setAuthorUrl}
                autoComplete="off"
              />
            )}
            <Text as="p" variant="bodySm" tone="subdued">
              {fr
                ? "L'article est créé en brouillon. Vous le publierez depuis Shopify Admin après vérification."
                : "The article is created as a draft. Publish it from Shopify Admin after review."}
            </Text>
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
