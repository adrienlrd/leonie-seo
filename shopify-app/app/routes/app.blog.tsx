/**
 * Blog — master-detail page.
 * Left: list of every draft generated for the shop. Right: full editor for the
 * selected draft with regenerate/edit/publish actions. Drafts persist between
 * sessions on the merchant's data directory (Render disk).
 */

import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import {
  Link as RemixLink,
  useActionData,
  useFetcher,
  useLoaderData,
  useNavigate,
  useSubmit,
} from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  ChoiceList,
  EmptyState,
  InlineStack,
  Modal,
  Page,
  Select,
  Spinner,
  Tabs,
  Text,
  TextField,
} from "@shopify/polaris";
import { useEffect, useState } from "react";

import { callBackendForShop } from "../lib/api.server";
import { getLocale, type Locale } from "../lib/i18n";
import { authenticate } from "../shopify.server";

interface Section { h2: string; direct_answer: string; body: string }
interface Draft {
  id: string;
  product_id?: string;
  product_title: string;
  blog_title: string;
  intro: string;
  summary?: string;
  sections: Section[];
  outline?: string[];
  tags?: string[];
  author_type?: "Organization" | "Person";
  author_name?: string;
  author_url?: string | null;
  confirmed_facts?: Array<{ key: string; value: string }>;
  target_customer?: string;
  product_summary?: string;
  status?: "draft" | "published_to_shopify";
  shopify_article_id?: string;
  shopify_article_handle?: string;
  updated_at?: string;
}

interface LoaderData {
  locale: Locale;
  shop: string;
  drafts: Draft[];
  selected: Draft | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  const url = new URL(request.url);
  const draftId = url.searchParams.get("draft");

  const listRes = await callBackendForShop(
    session.shop,
    `/api/shops/${session.shop}/blog/drafts`,
    { accessToken: session.accessToken },
  );
  const listData = listRes.ok ? ((await listRes.json()) as { drafts: Draft[] }) : { drafts: [] };
  const drafts = listData.drafts ?? [];

  let selected: Draft | null = null;
  const targetId = draftId ?? drafts[0]?.id ?? null;
  if (targetId) {
    const oneRes = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/blog/drafts/${targetId}`,
      { accessToken: session.accessToken },
    );
    if (oneRes.ok) selected = (await oneRes.json()) as Draft;
  }

  return json<LoaderData>({
    locale,
    shop: session.shop,
    drafts,
    selected,
    error: null,
  });
};

interface ActionResult {
  type: string;
  ok: boolean;
  error: string | null;
  draft?: Draft | null;
  blogs?: Array<{ id: string; handle: string; title: string }>;
}

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const intent = String(form.get("intent") ?? "");
  const proxy = (path: string, init?: RequestInit) =>
    callBackendForShop(session.shop, `/api/shops/${session.shop}${path}`, {
      accessToken: session.accessToken,
      ...init,
    });
  const respond = (ok: boolean, draft: Draft | null = null, error: string | null = null) =>
    json<ActionResult>({ type: intent, ok, draft, error });

  try {
    if (intent === "createFromProduct") {
      const url = new URL(request.url);
      const productId = url.searchParams.get("productId") || String(form.get("productId") || "");
      if (!productId) return respond(false, null, "Missing productId");
      const res = await proxy("/blog/drafts", {
        method: "POST",
        body: JSON.stringify({ product_id: productId, auto_generate: true }),
      });
      if (!res.ok) return respond(false, null, `${res.status}`);
      const draft = (await res.json()) as Draft;
      return redirect(`/app/blog?draft=${draft.id}`);
    }

    if (intent === "saveDraft") {
      const id = String(form.get("id") ?? "");
      const patch = JSON.parse(String(form.get("payload") ?? "{}"));
      const res = await proxy(`/blog/drafts/${id}`, {
        method: "PUT",
        body: JSON.stringify(patch),
      });
      return respond(res.ok, res.ok ? ((await res.json()) as Draft) : null, res.ok ? null : `${res.status}`);
    }

    if (intent === "regenerateSection") {
      const id = String(form.get("id") ?? "");
      const payload = JSON.parse(String(form.get("payload") ?? "{}"));
      const res = await proxy(`/blog/drafts/${id}/regenerate-section`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      return respond(res.ok, res.ok ? ((await res.json()) as Draft) : null, res.ok ? null : `${res.status}`);
    }

    if (intent === "publishDraft") {
      const id = String(form.get("id") ?? "");
      const payload = JSON.parse(String(form.get("payload") ?? "{}"));
      const res = await proxy(`/blog/drafts/${id}/publish`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        // Surface the FastAPI HTTPException detail so the merchant sees the real
        // reason (scope issue, Shopify userError, GraphQL field rejected…).
        const raw = await res.text();
        let detail = `HTTP ${res.status}`;
        try {
          const j = JSON.parse(raw) as { detail?: string };
          if (j.detail) detail = j.detail;
        } catch { /* keep raw status */ }
        return respond(false, null, detail);
      }
      const data = (await res.json()) as { draft: Draft };
      return respond(true, data.draft);
    }

    if (intent === "deleteDraft") {
      const id = String(form.get("id") ?? "");
      const res = await proxy(`/blog/drafts/${id}`, { method: "DELETE" });
      if (res.ok) return redirect(`/app/blog`);
      return respond(false, null, `${res.status}`);
    }

    if (intent === "listBlogs") {
      const res = await proxy("/blog/blogs");
      const data = res.ok ? ((await res.json()) as { blogs?: ActionResult["blogs"] }) : null;
      return json<ActionResult>({
        type: "listBlogs",
        ok: res.ok,
        error: res.ok ? null : `${res.status}`,
        draft: null,
        blogs: data?.blogs ?? [],
      });
    }
  } catch (exc) {
    return respond(false, null, String(exc));
  }
  return respond(false, null, "unknown intent");
};

function DraftListItem({
  draft,
  active,
  locale,
}: { draft: Draft; active: boolean; locale: Locale }) {
  const fr = locale === "fr";
  // Use the Remix Link (client-side navigation) so we never leave the embedded
  // Shopify session — a plain anchor would trigger the OAuth login path.
  return (
    <RemixLink
      to={`/app/blog?draft=${draft.id}`}
      style={{
        display: "block",
        textDecoration: "none",
        color: "inherit",
        padding: "8px 12px",
        borderRadius: 6,
        background: active ? "var(--p-color-bg-surface-active)" : "transparent",
        marginBottom: 4,
      }}
    >
      <BlockStack gap="050">
        <Text as="span" variant="bodyMd" fontWeight={active ? "semibold" : "regular"}>
          {draft.blog_title || (fr ? "(sans titre)" : "(untitled)")}
        </Text>
        <Text as="span" variant="bodySm" tone="subdued">{draft.product_title}</Text>
        <InlineStack gap="100">
          <Badge tone={draft.status === "published_to_shopify" ? "success" : "info"}>
            {draft.status === "published_to_shopify"
              ? fr ? "Sur Shopify" : "On Shopify"
              : fr ? "Brouillon" : "Draft"}
          </Badge>
        </InlineStack>
      </BlockStack>
    </RemixLink>
  );
}

export default function BlogIndexPage() {
  const { locale, shop, drafts, selected, error } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const submit = useSubmit();
  const navigate = useNavigate();
  const fr = locale === "fr";

  // Editable copy of the selected draft.
  const [draft, setDraft] = useState<Draft | null>(selected);
  useEffect(() => { setDraft(selected); }, [selected?.id]);

  const fetcher = useFetcher<typeof action>();
  const blogsFetcher = useFetcher<{ ok?: boolean; blogs?: Array<{ id: string; handle: string; title: string }> }>();
  const isBusy = fetcher.state !== "idle";
  const [publishOpen, setPublishOpen] = useState(false);
  const [selectedBlog, setSelectedBlog] = useState("");
  // 0 = édition, 1 = aperçu — saving auto-switches to preview so the merchant
  // immediately sees the cleanly-rendered article.
  const [tabIndex, setTabIndex] = useState(0);

  useEffect(() => {
    if (blogsFetcher.data?.blogs && blogsFetcher.data.blogs.length && !selectedBlog) {
      setSelectedBlog(blogsFetcher.data.blogs[0].id);
    }
  }, [blogsFetcher.data?.blogs, selectedBlog]);

  useEffect(() => {
    const d = fetcher.data;
    if (!d) return;
    if ((d.type === "saveDraft" || d.type === "regenerateSection" || d.type === "publishDraft") && d.ok && d.draft) {
      setDraft(d.draft as Draft);
      if (d.type === "publishDraft") setPublishOpen(false);
      // After a save, switch to preview so the merchant sees the final article.
      if (d.type === "saveDraft") setTabIndex(1);
    }
  }, [fetcher.data]);

  const productCtx = draft ? {
    product_title: draft.product_title,
    product_summary: draft.product_summary ?? "",
    target_customer: draft.target_customer ?? "",
    confirmed_facts: (draft.confirmed_facts ?? []).map((f) => ({
      key: f.key,
      value: Array.isArray(f.value) ? f.value.join(", ") : String(f.value ?? ""),
    })),
  } : null;

  const setSection = (idx: number, patch: Partial<Section>) =>
    setDraft((prev) => prev ? {
      ...prev,
      sections: prev.sections.map((s, i) => i === idx ? { ...s, ...patch } : s),
    } : prev);

  const onSave = () => {
    if (!draft) return;
    submit(
      {
        intent: "saveDraft",
        id: draft.id,
        payload: JSON.stringify({
          blog_title: draft.blog_title,
          intro: draft.intro,
          summary: draft.summary,
          sections: draft.sections,
          tags: draft.tags ?? [],
          author_type: draft.author_type ?? "Organization",
          author_name: draft.author_name ?? "",
          author_url: draft.author_url ?? null,
        }),
      },
      { method: "post" },
    );
  };

  const onRegenerate = (h2: string) => {
    if (!draft || !productCtx) return;
    fetcher.submit(
      {
        intent: "regenerateSection",
        id: draft.id,
        payload: JSON.stringify({
          ...productCtx,
          blog_title: draft.blog_title,
          h2_question: h2,
        }),
      },
      { method: "post" },
    );
  };

  const onOpenPublish = () => {
    setPublishOpen(true);
    blogsFetcher.submit({ intent: "listBlogs" }, { method: "post" });
  };

  const onPublish = () => {
    if (!draft) return;
    fetcher.submit(
      {
        intent: "publishDraft",
        id: draft.id,
        payload: JSON.stringify({ blog_id: selectedBlog, publisher_name: shop }),
      },
      { method: "post" },
    );
  };

  const onDelete = () => {
    if (!draft) return;
    if (typeof window !== "undefined" && !window.confirm(fr ? "Supprimer ce brouillon ?" : "Delete this draft?")) return;
    submit({ intent: "deleteDraft", id: draft.id }, { method: "post" });
  };

  return (
    <Page title="Blog" fullWidth>
      <BlockStack gap="400">
        {error && (
          <Banner tone="critical"><p>{error}</p></Banner>
        )}
        {actionData?.error && (
          <Banner tone="critical"><p>{actionData.error}</p></Banner>
        )}
        {fetcher.data?.error && !fetcher.data.ok && (
          <Banner tone="critical" title={fr ? "Publication échouée" : "Publish failed"}>
            <p style={{ whiteSpace: "pre-wrap" }}>{fetcher.data.error}</p>
          </Banner>
        )}
        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16, alignItems: "start" }}>
          <Card padding="200">
            <BlockStack gap="200">
              <InlineStack align="space-between" blockAlign="center">
                <Text as="h2" variant="headingSm">
                  {fr ? `Brouillons (${drafts.length})` : `Drafts (${drafts.length})`}
                </Text>
              </InlineStack>
              {drafts.length === 0 ? (
                <Text as="p" tone="subdued" variant="bodySm">
                  {fr
                    ? "Aucun brouillon. Génère-en un depuis Analyse marché."
                    : "No drafts yet. Generate one from Market analysis."}
                </Text>
              ) : (
                <Box>
                  {drafts.map((d) => (
                    <DraftListItem key={d.id} draft={d} active={d.id === draft?.id} locale={locale} />
                  ))}
                </Box>
              )}
              <Button url="/app/market-analysis" variant="plain">
                {fr ? "Aller à Analyse marché →" : "Go to Market analysis →"}
              </Button>
            </BlockStack>
          </Card>

          {draft ? (
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between" blockAlign="center" wrap>
                  <BlockStack gap="050">
                    <Text as="h2" variant="headingLg">{draft.blog_title || (fr ? "(sans titre)" : "(untitled)")}</Text>
                    <Text as="p" variant="bodySm" tone="subdued">{draft.product_title}</Text>
                  </BlockStack>
                  <InlineStack gap="200">
                    <Button onClick={onSave} loading={isBusy && fetcher.formData?.get("intent") === "saveDraft"}>
                      {fr ? "Sauvegarder" : "Save"}
                    </Button>
                    <Button variant="primary" onClick={onOpenPublish}
                      disabled={!draft.sections.length || !draft.sections.some((s) => s.direct_answer)}>
                      {fr ? "Publier en brouillon" : "Publish as draft"}
                    </Button>
                    <Button tone="critical" variant="plain" onClick={onDelete}>
                      {fr ? "Supprimer" : "Delete"}
                    </Button>
                  </InlineStack>
                </InlineStack>

                {draft.status === "published_to_shopify" && (
                  <Banner tone="success">
                    <p>{fr ? "Cet article a été créé sur Shopify (en brouillon). Publiez-le depuis Shopify Admin." : "This article was created on Shopify (as draft). Publish it from Shopify Admin."}</p>
                  </Banner>
                )}

                <Tabs
                  tabs={[
                    { id: "edit", content: fr ? "Édition" : "Edit" },
                    { id: "preview", content: fr ? "Aperçu" : "Preview" },
                  ]}
                  selected={tabIndex}
                  onSelect={setTabIndex}
                />

                {tabIndex === 0 ? (
                  <>
                    <TextField
                      label={fr ? "Titre" : "Title"}
                      value={draft.blog_title}
                      onChange={(v) => setDraft((p) => p ? { ...p, blog_title: v } : p)}
                      autoComplete="off"
                    />
                    <TextField
                      label="Intro"
                      value={draft.intro}
                      onChange={(v) => setDraft((p) => p ? { ...p, intro: v } : p)}
                      multiline={3}
                      autoComplete="off"
                    />

                    {draft.sections.map((section, idx) => (
                      <Card key={`${section.h2}-${idx}`} padding="300">
                        <BlockStack gap="200">
                          <InlineStack align="space-between" blockAlign="center" wrap>
                            <Text as="h3" variant="headingSm">H{idx + 2} · Section {idx + 1}</Text>
                            <Button size="slim" onClick={() => onRegenerate(section.h2)}
                              loading={isBusy && fetcher.formData?.get("intent") === "regenerateSection" && String(fetcher.formData?.get("payload") ?? "").includes(section.h2)}>
                              {fr ? "Régénérer" : "Regenerate"}
                            </Button>
                          </InlineStack>
                          <TextField label={fr ? "Question (H2)" : "Question (H2)"} value={section.h2}
                            onChange={(v) => setSection(idx, { h2: v })} autoComplete="off" />
                          <TextField label={fr ? "Réponse directe (40-60 mots)" : "Direct answer (40-60 words)"}
                            value={section.direct_answer} onChange={(v) => setSection(idx, { direct_answer: v })}
                            multiline={3} autoComplete="off" />
                          <TextField label={fr ? "Corps" : "Body"} value={section.body}
                            onChange={(v) => setSection(idx, { body: v })} multiline={6} autoComplete="off" />
                        </BlockStack>
                      </Card>
                    ))}
                  </>
                ) : (
                  <Box
                    padding="500"
                    background="bg-surface"
                    borderRadius="200"
                    borderColor="border"
                    borderWidth="025"
                  >
                    <article style={{ maxWidth: 720, margin: "0 auto", lineHeight: 1.65 }}>
                      <h1 style={{ marginBottom: 16, fontSize: 28 }}>
                        {draft.blog_title || (fr ? "(sans titre)" : "(untitled)")}
                      </h1>
                      {draft.intro && (
                        <p style={{ color: "#374151", fontSize: 17, marginBottom: 24 }}>
                          {draft.intro}
                        </p>
                      )}
                      {draft.sections.map((section, idx) => (
                        <section key={`prev-${section.h2}-${idx}`} style={{ marginBottom: 28 }}>
                          <h2 style={{ fontSize: 22, marginBottom: 10 }}>{section.h2}</h2>
                          {section.direct_answer && (
                            <p style={{ fontWeight: 600, marginBottom: 12 }}>
                              {section.direct_answer}
                            </p>
                          )}
                          {section.body && (
                            <div style={{ whiteSpace: "pre-wrap" }}>{section.body}</div>
                          )}
                        </section>
                      ))}
                    </article>
                  </Box>
                )}
              </BlockStack>
            </Card>
          ) : (
            <Card>
              <EmptyState
                heading={fr ? "Aucun brouillon sélectionné" : "No draft selected"}
                action={{ content: fr ? "Aller à Analyse marché" : "Go to Market analysis", url: "/app/market-analysis" }}
                image=""
              >
                <p>
                  {fr
                    ? "Génère un brouillon depuis Analyse marché pour le retrouver ici."
                    : "Generate a draft from Market analysis to see it here."}
                </p>
              </EmptyState>
            </Card>
          )}
        </div>
      </BlockStack>

      <Modal
        open={publishOpen}
        onClose={() => setPublishOpen(false)}
        title={fr ? "Publier le brouillon sur Shopify" : "Publish draft to Shopify"}
        primaryAction={{
          content: fr ? "Créer le brouillon" : "Create draft",
          onAction: onPublish,
          loading: isBusy && fetcher.formData?.get("intent") === "publishDraft",
        }}
        secondaryActions={[{ content: fr ? "Annuler" : "Cancel", onAction: () => setPublishOpen(false) }]}
      >
        <Modal.Section>
          <BlockStack gap="300">
            {!blogsFetcher.data ? (
              <InlineStack gap="200" blockAlign="center">
                <Spinner size="small" />
                <Text as="span">{fr ? "Chargement des blogs…" : "Loading blogs…"}</Text>
              </InlineStack>
            ) : (blogsFetcher.data.blogs ?? []).length === 0 ? (
              <Banner tone="info">
                <p>
                  {fr
                    ? "Aucun blog Shopify détecté — un blog « Blog » sera créé automatiquement."
                    : "No Shopify blog detected — a default \"Blog\" container will be created automatically."}
                </p>
              </Banner>
            ) : (
              <Select
                label={fr ? "Blog de destination" : "Target blog"}
                options={(blogsFetcher.data.blogs ?? []).map((b) => ({ label: b.title, value: b.id }))}
                value={selectedBlog}
                onChange={setSelectedBlog}
              />
            )}
            <ChoiceList
              title={fr ? "Auteur" : "Author"}
              choices={[
                { label: fr ? "Organisation (par défaut)" : "Organization (default)", value: "Organization" },
                { label: fr ? "Personne réelle (E-E-A-T)" : "Real person (E-E-A-T)", value: "Person" },
              ]}
              selected={[draft?.author_type ?? "Organization"]}
              onChange={(s) => setDraft((p) => p ? { ...p, author_type: (s[0] as "Organization" | "Person") } : p)}
            />
            <TextField
              label={fr ? "Nom de l'auteur" : "Author name"}
              value={draft?.author_name ?? ""}
              onChange={(v) => setDraft((p) => p ? { ...p, author_name: v } : p)}
              autoComplete="off"
            />
            {draft?.author_type === "Person" && (
              <TextField
                label={fr ? "URL profil auteur (optionnel)" : "Author URL (optional)"}
                value={draft?.author_url ?? ""}
                onChange={(v) => setDraft((p) => p ? { ...p, author_url: v } : p)}
                autoComplete="off"
              />
            )}
            <Text as="p" variant="bodySm" tone="subdued">
              {fr ? "Brouillon créé sur Shopify, publiez-le depuis Shopify Admin après vérif."
                  : "Created as a draft on Shopify. Publish from Shopify Admin after review."}
            </Text>
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
