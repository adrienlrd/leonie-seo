/**
 * Blog — master-detail page.
 * Left: list of every draft generated for the shop. Right: full editor for the
 * selected draft with regenerate/edit/publish actions. Drafts persist between
 * sessions on the merchant's data directory (Render disk).
 */

import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import {
  Form,
  Link as RemixLink,
  useActionData,
  useFetcher,
  useLoaderData,
  useNavigate,
  useNavigation,
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
  Divider,
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
import { SaveBar } from "@shopify/app-bridge-react";
import { useEffect, useMemo, useState } from "react";

import { callBackendForShop } from "../lib/api.server";
import { handleShopifyFilesIntent } from "../lib/shopifyFiles.server";
import { getLocale, loaderPhrases, type Locale } from "../lib/i18n";
import { AnalysisLoader } from "../components/AnalysisLoader";
import { ShopifyImagePicker } from "../components/ShopifyImagePicker";
import { scoreTone } from "../lib/marketAnalysisShared";
import { authenticate } from "../shopify.server";

interface Section { h2: string; direct_answer: string; body: string }
interface InternalLink {
  target_url: string;
  anchor: string;
  target_title?: string;
  reason?: string;
}
interface KeywordCheck {
  ok: boolean;
  score: number;
  label: string;
  issues: string[];
}
interface Draft {
  id: string;
  product_id?: string;
  product_title: string;
  blog_title: string;
  target_keyword?: string;
  keyword_check?: KeywordCheck;
  intro: string;
  summary?: string;
  sections: Section[];
  internal_links?: InternalLink[];
  outline?: string[];
  tags?: string[];
  author_type?: "Organization" | "Person";
  author_name?: string;
  author_url?: string | null;
  image_url?: string;
  image_alt?: string;
  confirmed_facts?: Array<{ key: string; value: string }>;
  target_customer?: string;
  product_summary?: string;
  status?: "draft" | "published_to_shopify";
  shopify_article_id?: string;
  shopify_article_handle?: string;
  updated_at?: string;
}

interface BlogIdeaFlat {
  title: string;
  target_keyword: string;
  intro: string;
  outline: string[];
  product_id: string;
  product_title: string;
  idea_index: number;
}

interface LoaderData {
  locale: Locale;
  shop: string;
  drafts: Draft[];
  selected: Draft | null;
  error: string | null;
  prefillTitle: string | null;
  prefillCluster: string | null;
  blogIdeas: BlogIdeaFlat[];
  pillarIdeaKeys: string[];
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  const url = new URL(request.url);
  const draftId = url.searchParams.get("draft");
  const prefillTitle = url.searchParams.get("title");
  const prefillCluster = url.searchParams.get("cluster");

  // Drafts list and market analysis are independent — fetch them in parallel.
  const [listRes, analysisRes] = await Promise.all([
    callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/blog/drafts`,
      { accessToken: session.accessToken },
    ),
    callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/latest`,
      { accessToken: session.accessToken },
    ).catch(() => null),
  ]);
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

  // Load blog ideas from the latest market analysis
  let blogIdeas: BlogIdeaFlat[] = [];
  try {
    if (analysisRes && analysisRes.ok) {
      const analysis = (await analysisRes.json()) as { products?: Array<{
        product_id: string; product_title: string;
        content_test_pack?: { proposed_blog_ideas?: Array<{ title?: string; target_keyword?: string; intro?: string; outline?: string[] }> };
      }> };
      blogIdeas = (analysis.products ?? []).flatMap((p) =>
        ((p.content_test_pack?.proposed_blog_ideas) ?? []).map((idea, idx) => ({
          title: idea.title ?? "",
          target_keyword: idea.target_keyword ?? "",
          intro: idea.intro ?? "",
          outline: idea.outline ?? [],
          product_id: p.product_id,
          product_title: p.product_title,
          idea_index: idx,
        })),
      );
    }
  } catch { /* analysis not available yet */ }

  // Group ideas sharing a similar target keyword and flag a suggested pillar
  let pillarIdeaKeys: string[] = [];
  if (blogIdeas.length > 1) {
    try {
      const clustersRes = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/blog/idea-clusters`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify({
            items: blogIdeas.map((idea) => ({
              key: `${idea.product_id}:${idea.idea_index}`,
              target_keyword: idea.target_keyword,
              outline: idea.outline,
            })),
          }),
        },
      );
      if (clustersRes.ok) {
        const data = (await clustersRes.json()) as { clusters?: Array<{ pillar_key?: string }> };
        pillarIdeaKeys = (data.clusters ?? []).map((c) => c.pillar_key ?? "").filter(Boolean);
      }
    } catch { /* clustering is advisory only */ }
  }

  return json<LoaderData>({
    locale,
    shop: session.shop,
    drafts,
    selected,
    error: null,
    prefillTitle,
    prefillCluster,
    blogIdeas,
    pillarIdeaKeys,
  });
};

interface LinkableArticle {
  id: string;
  blog_title: string;
  shopify_article_handle: string | null;
  status: string;
  tags: string[];
}

interface DynamicSuggestion {
  target_url: string;
  anchor: string;
  target_title: string;
  reason: string;
}

interface ActionResult {
  type: string;
  ok: boolean;
  error: string | null;
  draft?: Draft | null;
  blogs?: Array<{ id: string; handle: string; title: string }>;
  articles?: LinkableArticle[];
  suggestions?: DynamicSuggestion[];
}

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);
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
      const rawBlogIdeaIndex = String(form.get("blogIdeaIndex") ?? "");
      const blogIdeaIndex = rawBlogIdeaIndex === "" ? null : Number(rawBlogIdeaIndex);
      const body: { product_id: string; auto_generate: boolean; blog_idea_index?: number } = {
        product_id: productId,
        auto_generate: true,
      };
      if (blogIdeaIndex !== null && Number.isFinite(blogIdeaIndex)) {
        body.blog_idea_index = blogIdeaIndex;
      }
      const res = await proxy("/blog/drafts", {
        method: "POST",
        body: JSON.stringify(body),
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

    if (intent === "createBlank") {
      const blogTitle = String(form.get("blogTitle") ?? "");
      const res = await proxy("/blog/drafts", {
        method: "POST",
        body: JSON.stringify({ blog_title: blogTitle, auto_generate: false }),
      });
      if (!res.ok) return respond(false, null, `${res.status}`);
      const draft = (await res.json()) as Draft;
      return redirect(`/app/blog?draft=${draft.id}`);
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

    if (intent === "listLinkableArticles") {
      const draftId = String(form.get("draftId") ?? "");
      if (!draftId) return json<ActionResult>({ type: "listLinkableArticles", ok: false, error: "Missing draftId", draft: null });
      const res = await proxy(`/blog/drafts/${draftId}/linkable-articles`);
      const data = res.ok ? ((await res.json()) as { articles?: LinkableArticle[] }) : null;
      return json<ActionResult>({
        type: "listLinkableArticles",
        ok: res.ok,
        error: res.ok ? null : `${res.status}`,
        draft: null,
        articles: data?.articles ?? [],
      });
    }

    if (intent === "fetchLinkSuggestions") {
      const draftId = String(form.get("draftId") ?? "");
      const rawKeywords = String(form.get("keywords") ?? "");
      const rawExclude = String(form.get("excludeUrls") ?? "");
      const keywords = rawKeywords ? rawKeywords.split("||").filter(Boolean) : [];
      const excludeUrls = rawExclude ? rawExclude.split("||").filter(Boolean) : [];
      const res = await proxy(`/blog/drafts/${draftId}/link-suggestions`, {
        method: "POST",
        body: JSON.stringify({ keywords, exclude_urls: excludeUrls }),
      });
      const data = res.ok ? ((await res.json()) as { suggestions?: DynamicSuggestion[] }) : null;
      return json<ActionResult>({
        type: "fetchLinkSuggestions",
        ok: res.ok,
        error: res.ok ? null : `${res.status}`,
        draft: null,
        suggestions: data?.suggestions ?? [],
      });
    }
    // Shopify Files API intents (browse, upload)
    const filesResponse = await handleShopifyFilesIntent(intent, form, admin);
    if (filesResponse) return filesResponse;
  } catch (exc) {
    return respond(false, null, String(exc));
  }
  return respond(false, null, "unknown intent");
};

function DraftListItem({
  draft,
  active,
  locale,
  onClick,
}: { draft: Draft; active: boolean; locale: Locale; onClick?: () => void }) {
  const fr = locale === "fr";
  // Use the Remix Link (client-side navigation) so we never leave the embedded
  // Shopify session — a plain anchor would trigger the OAuth login path.
  return (
    <RemixLink
      to={`/app/blog?draft=${draft.id}`}
      onClick={onClick}
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

// Only the fields persisted by the `saveDraft` action, serialized in a fixed key
// order so the contextual Save Bar can reliably detect unsaved changes regardless
// of object key ordering.
function serializeEditableDraft(d: Draft | null): string {
  if (!d) return "";
  return JSON.stringify({
    blog_title: d.blog_title,
    intro: d.intro,
    summary: d.summary,
    sections: d.sections,
    internal_links: d.internal_links ?? [],
    tags: d.tags ?? [],
    author_type: d.author_type ?? "Organization",
    author_name: d.author_name ?? "",
    author_url: d.author_url ?? null,
    image_url: d.image_url ?? "",
    image_alt: d.image_alt ?? "",
  });
}

function linkReasonBadge(reason: string, fr: boolean): { tone: "info" | "success" | "attention"; label: string } {
  switch (reason) {
    case "related_article":
      return { tone: "info", label: fr ? "Article" : "Article" };
    case "collection_parent":
      return { tone: "success", label: fr ? "Collection" : "Collection" };
    case "cluster_pillar":
      return { tone: "success", label: fr ? "Article pilier" : "Pillar article" };
    case "cluster_sibling":
      return { tone: "info", label: fr ? "Article satellite" : "Cluster article" };
    default:
      return { tone: "attention", label: fr ? "Produit" : "Product" };
  }
}

export default function BlogIndexPage() {
  const { locale, shop, drafts, selected, error, prefillTitle, prefillCluster, blogIdeas, pillarIdeaKeys } = useLoaderData<typeof loader>();
  const pillarIdeaKeySet = useMemo(() => new Set(pillarIdeaKeys), [pillarIdeaKeys]);
  const actionData = useActionData<typeof action>();
  const submit = useSubmit();
  const navigate = useNavigate();
  const navigation = useNavigation();
  const fr = locale === "fr";

  // Editable copy of the selected draft.
  const [draft, setDraft] = useState<Draft | null>(selected);
  // 0 = édition, 1 = aperçu — saving auto-switches to preview so the merchant
  // immediately sees the cleanly-rendered article; switching drafts goes back
  // to édition so every editable field (incl. cover image) is reachable.
  const [tabIndex, setTabIndex] = useState(0);
  const [selectedIdea, setSelectedIdea] = useState<BlogIdeaFlat | null>(null);
  useEffect(() => {
    setDraft(selected);
    setTabIndex(0);
    // Generating from an idea redirects to ?draft={newId} — switch the panel
    // over to the freshly generated draft instead of staying stuck on the idea card.
    setSelectedIdea(null);
  }, [selected?.id]);

  const fetcher = useFetcher<typeof action>();
  const blogsFetcher = useFetcher<{ ok?: boolean; blogs?: Array<{ id: string; handle: string; title: string }> }>();
  const articlesFetcher = useFetcher<ActionResult>();
  const suggestionsFetcher = useFetcher<ActionResult>();
  const isBusy = fetcher.state !== "idle";
  const isGeneratingArticle = navigation.state !== "idle" && navigation.formData?.get("intent") === "createFromProduct";
  const [showArticlePicker, setShowArticlePicker] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [selectedBlog, setSelectedBlog] = useState("");
  const [showPublished, setShowPublished] = useState(true);
  const [showIdeas, setShowIdeas] = useState(true);

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
          internal_links: draft.internal_links ?? [],
          tags: draft.tags ?? [],
          author_type: draft.author_type ?? "Organization",
          author_name: draft.author_name ?? "",
          author_url: draft.author_url ?? null,
          image_url: draft.image_url ?? "",
          image_alt: draft.image_alt ?? "",
        }),
      },
      { method: "post" },
    );
  };

  // Drives the App Bridge contextual Save Bar (Built for Shopify requirement for
  // forms with editable inputs). Dirty = the editable draft differs from the
  // last saved version returned by the loader.
  const dirty = draft != null && serializeEditableDraft(draft) !== serializeEditableDraft(selected);
  const onDiscard = () => setDraft(selected);

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

  const setInternalLink = (idx: number, patch: Partial<InternalLink>) =>
    setDraft((prev) => prev ? {
      ...prev,
      internal_links: (prev.internal_links ?? []).map((link, i) =>
        i === idx ? { ...link, ...patch } : link,
      ),
    } : prev);

  const addArticleLink = (article: LinkableArticle) => {
    const target_url = article.shopify_article_handle
      ? `/blogs/blog/${article.shopify_article_handle}`
      : `#draft-${article.id}`;
    const newLink: InternalLink = {
      target_url,
      anchor: article.blog_title,
      target_title: article.blog_title,
      reason: "related_article",
    };
    setDraft((prev) => prev ? {
      ...prev,
      internal_links: [...(prev.internal_links ?? []), newLink],
    } : prev);
    setShowArticlePicker(false);
  };

  const onLoadArticles = () => {
    if (!draft) return;
    articlesFetcher.submit(
      { intent: "listLinkableArticles", draftId: draft.id },
      { method: "post" },
    );
    setShowArticlePicker(true);
  };

  const onFetchSuggestions = () => {
    if (!draft) return;
    const existingUrls = (draft.internal_links ?? []).map((l) => l.target_url).join("||");
    const keywords = [
      draft.blog_title,
      ...(draft.sections ?? []).map((s) => s.h2),
    ].filter(Boolean).join("||");
    suggestionsFetcher.submit(
      { intent: "fetchLinkSuggestions", draftId: draft.id, keywords, excludeUrls: existingUrls },
      { method: "post" },
    );
    setShowSuggestions(true);
  };

  const addSuggestedLink = (suggestion: DynamicSuggestion) => {
    const newLink: InternalLink = {
      target_url: suggestion.target_url,
      anchor: suggestion.anchor,
      target_title: suggestion.target_title,
      reason: suggestion.reason,
    };
    setDraft((prev) => prev ? {
      ...prev,
      internal_links: [...(prev.internal_links ?? []), newLink],
    } : prev);
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
    <>
      {/*
        App Bridge contextual Save Bar — shows in the admin chrome whenever the
        draft has unsaved edits. The button with variant="primary" is Save, the
        other is Discard (per the ui-save-bar contract).
      */}
      <SaveBar id="blog-draft-save-bar" open={dirty} discardConfirmation>
        <button
          {...({ variant: "primary" } as Record<string, unknown>)}
          onClick={onSave}
          disabled={isBusy}
        >
          {fr ? "Enregistrer" : "Save"}
        </button>
        <button onClick={onDiscard} disabled={isBusy}>
          {fr ? "Annuler" : "Discard"}
        </button>
      </SaveBar>
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
        {prefillTitle && (
          <Banner
            tone="info"
            title={fr ? "Sujet détecté depuis Produits" : "Topic detected from Products"}
          >
            <BlockStack gap="200">
              <Text as="p" variant="bodySm">
                {fr
                  ? `Crée un article sur : "${prefillTitle}"`
                  : `Create an article about: "${prefillTitle}"`}
              </Text>
              <Form method="post">
                <input type="hidden" name="intent" value="createBlank" />
                <input type="hidden" name="blogTitle" value={prefillTitle} />
                <Button
                  variant="primary"
                  size="slim"
                  submit
                  loading={navigation.state !== "idle" && navigation.formData?.get("intent") === "createBlank"}
                >
                  {fr ? "Créer le brouillon" : "Create draft"}
                </Button>
              </Form>
            </BlockStack>
          </Banner>
        )}
        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16, alignItems: "start" }}>
          <Card padding="200">
            <BlockStack gap="200">
              {/* ── Publiés ──────────────────────────────────────────── */}
              {(() => {
                const published = drafts.filter((d) => d.status === "published_to_shopify");
                if (published.length === 0) return null;
                return (
                  <>
                    <InlineStack align="space-between" blockAlign="center">
                      <Text as="h2" variant="headingSm">
                        {fr ? `Publiés (${published.length})` : `Published (${published.length})`}
                      </Text>
                      <Button size="slim" variant="plain" onClick={() => setShowPublished((p) => !p)}>
                        {showPublished ? "▲" : "▼"}
                      </Button>
                    </InlineStack>
                    {showPublished && (
                      <Box>
                        {published.map((d) => (
                          <DraftListItem key={d.id} draft={d} active={d.id === draft?.id && !selectedIdea} locale={locale} onClick={() => setSelectedIdea(null)} />
                        ))}
                      </Box>
                    )}
                    <Divider />
                  </>
                );
              })()}

              {/* ── Brouillons ───────────────────────────────────────── */}
              {(() => {
                const unpublished = drafts.filter((d) => d.status !== "published_to_shopify");
                return (
                  <>
                    <Text as="h2" variant="headingSm">
                      {fr ? `Brouillons (${unpublished.length})` : `Drafts (${unpublished.length})`}
                    </Text>
                    {unpublished.length === 0 ? (
                      <Text as="p" tone="subdued" variant="bodySm">
                        {fr ? "Aucun brouillon." : "No drafts yet."}
                      </Text>
                    ) : (
                      <Box>
                        {unpublished.map((d) => (
                          <DraftListItem key={d.id} draft={d} active={d.id === draft?.id && !selectedIdea} locale={locale} onClick={() => setSelectedIdea(null)} />
                        ))}
                      </Box>
                    )}
                  </>
                );
              })()}

              {/* ── Idées de blog ────────────────────────────────────── */}
              {blogIdeas.length > 0 && (
                <>
                  <Divider />
                  <InlineStack align="space-between" blockAlign="center">
                    <Text as="h2" variant="headingSm">
                      {fr ? `Idées de blog (${blogIdeas.length})` : `Blog ideas (${blogIdeas.length})`}
                    </Text>
                    <Button size="slim" variant="plain" onClick={() => setShowIdeas((p) => !p)}>
                      {showIdeas ? "▲" : "▼"}
                    </Button>
                  </InlineStack>
                  {showIdeas && (
                    <BlockStack gap="100">
                      {(() => {
                        const byProduct = new Map<string, BlogIdeaFlat[]>();
                        blogIdeas.forEach((idea) => {
                          const arr = byProduct.get(idea.product_id) ?? [];
                          arr.push(idea);
                          byProduct.set(idea.product_id, arr);
                        });
                        return [...byProduct.entries()].map(([pid, ideas]) => (
                          <BlockStack key={pid} gap="050">
                            <Text as="p" variant="bodySm" fontWeight="semibold" tone="subdued">
                              {ideas[0].product_title}
                            </Text>
                            {ideas.map((idea) => {
                              const isActive = selectedIdea?.product_id === idea.product_id && selectedIdea?.idea_index === idea.idea_index;
                              const isPillar = pillarIdeaKeySet.has(`${idea.product_id}:${idea.idea_index}`);
                              return (
                                <div
                                  key={`${pid}-${idea.idea_index}`}
                                  role="button"
                                  tabIndex={0}
                                  onClick={() => { setSelectedIdea(idea); setDraft(null); }}
                                  onKeyDown={(e) => { if (e.key === "Enter") { setSelectedIdea(idea); setDraft(null); } }}
                                  style={{
                                    padding: "6px 12px",
                                    borderRadius: 6,
                                    cursor: "pointer",
                                    background: isActive ? "var(--p-color-bg-surface-active)" : "transparent",
                                    marginBottom: 2,
                                  }}
                                >
                                  <InlineStack gap="150" blockAlign="center">
                                    <Text as="span" variant="bodySm" fontWeight={isActive ? "semibold" : "regular"}>
                                      {idea.title || (fr ? "(sans titre)" : "(untitled)")}
                                    </Text>
                                    {isPillar && (
                                      <Badge tone="success" size="small">
                                        {fr ? "Pilier suggéré" : "Suggested pillar"}
                                      </Badge>
                                    )}
                                  </InlineStack>
                                </div>
                              );
                            })}
                          </BlockStack>
                        ));
                      })()}
                    </BlockStack>
                  )}
                </>
              )}

              <Button url="/app/products" variant="plain">
                {fr ? "Aller à Produits →" : "Go to Products →"}
              </Button>
            </BlockStack>
          </Card>

          {selectedIdea ? (
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between" blockAlign="start" wrap>
                  <BlockStack gap="100">
                    <Text as="h2" variant="headingLg">{selectedIdea.title || (fr ? "(sans titre)" : "(untitled)")}</Text>
                    <Text as="p" variant="bodySm" tone="subdued">{selectedIdea.product_title}</Text>
                    {selectedIdea.target_keyword && (
                      <InlineStack gap="100" blockAlign="center">
                        <Text as="span" variant="bodySm" tone="subdued">{fr ? "Mot-clé cible :" : "Target keyword:"}</Text>
                        <Badge tone="attention">{selectedIdea.target_keyword}</Badge>
                      </InlineStack>
                    )}
                  </BlockStack>
                  <Button variant="plain" onClick={() => setSelectedIdea(null)}>
                    {fr ? "Fermer" : "Close"}
                  </Button>
                </InlineStack>

                {selectedIdea.intro && (
                  <BlockStack gap="100">
                    <Text as="p" variant="headingXs" tone="subdued">{fr ? "Introduction" : "Introduction"}</Text>
                    <Text as="p" variant="bodySm">{selectedIdea.intro}</Text>
                  </BlockStack>
                )}

                {selectedIdea.outline.length > 0 && (
                  <BlockStack gap="100">
                    <Text as="p" variant="headingXs" tone="subdued">{fr ? "Plan de l'article" : "Article outline"}</Text>
                    <BlockStack gap="050">
                      {selectedIdea.outline.map((h2, i) => (
                        <Text key={i} as="p" variant="bodySm">
                          {i + 1}. {h2}
                        </Text>
                      ))}
                    </BlockStack>
                  </BlockStack>
                )}

                <Box paddingBlockStart="200">
                  <BlockStack gap="150">
                    <Form method="post">
                      <input type="hidden" name="intent" value="createFromProduct" />
                      <input type="hidden" name="productId" value={selectedIdea.product_id} />
                      <input type="hidden" name="blogIdeaIndex" value={String(selectedIdea.idea_index)} />
                      <Button
                        variant="primary"
                        submit
                        disabled={isGeneratingArticle}
                        loading={isGeneratingArticle}
                      >
                        {fr ? "Générer l'article" : "Generate article"}
                      </Button>
                    </Form>
                    {isGeneratingArticle && (
                      <AnalysisLoader
                        phrases={loaderPhrases(locale, "writing")}
                        estimateMs={90_000}
                        title={fr
                          ? "Génération en cours… cela peut prendre 1 à 2 minutes. Inutile de cliquer à nouveau."
                          : "Generating… this can take 1-2 minutes. No need to click again."}
                      />
                    )}
                  </BlockStack>
                </Box>
              </BlockStack>
            </Card>
          ) : draft ? (
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

                {draft.keyword_check && (
                  <Box padding="300" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
                    <BlockStack gap="150">
                      <InlineStack gap="200" blockAlign="center">
                        <Text as="h3" variant="headingSm">
                          {fr ? "Vérification mot-clé" : "Keyword check"}
                        </Text>
                        {draft.target_keyword && <Badge tone="info">{draft.target_keyword}</Badge>}
                        <Badge tone={scoreTone(draft.keyword_check.score)}>
                          {`${draft.keyword_check.score}/100`}
                        </Badge>
                      </InlineStack>
                      {draft.keyword_check.issues.length > 0 ? (
                        <BlockStack gap="050">
                          {draft.keyword_check.issues.map((issue) => (
                            <Text as="p" variant="bodySm" tone="subdued" key={issue}>
                              {`• ${issue}`}
                            </Text>
                          ))}
                        </BlockStack>
                      ) : (
                        <Text as="p" variant="bodySm" tone="subdued">
                          {fr
                            ? "Le mot-clé cible est bien placé (titre, sous-titres, début d'article, densité)."
                            : "The target keyword is well placed (title, subheadings, opening, density)."}
                        </Text>
                      )}
                    </BlockStack>
                  </Box>
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

                    <ShopifyImagePicker
                      locale={locale}
                      imageUrl={draft.image_url ?? null}
                      imageAlt={draft.image_alt ?? null}
                      onSelect={(url, alt) => setDraft((p) => p ? { ...p, image_url: url, image_alt: alt || p.image_alt } : p)}
                      onAltChange={(alt) => setDraft((p) => p ? { ...p, image_alt: alt } : p)}
                      onRemove={() => setDraft((p) => p ? { ...p, image_url: "", image_alt: "" } : p)}
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

                    <Box
                      padding="400"
                      background="bg-surface-secondary"
                      borderRadius="200"
                      borderColor="border"
                      borderWidth="025"
                    >
                      <BlockStack gap="300">
                        <BlockStack gap="050">
                          <Text as="h3" variant="headingSm">
                            {fr ? "Liens internes" : "Internal links"}
                          </Text>
                          <Text as="p" variant="bodySm" tone="subdued">
                            {fr
                              ? "Liens vers produits, collections ou autres articles. Ajuste l'ancre avant publication."
                              : "Links to products, collections, or other articles. Adjust anchors before publishing."}
                          </Text>
                        </BlockStack>
                        {(draft.internal_links ?? []).map((link, idx) => (
                          <div
                            key={`${link.target_url}-${idx}`}
                            style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}
                          >
                            <TextField
                              label={fr ? "Ancre" : "Anchor"}
                              value={link.anchor}
                              onChange={(v) => setInternalLink(idx, { anchor: v })}
                              autoComplete="off"
                            />
                            <TextField
                              label="URL"
                              value={link.target_url}
                              onChange={(v) => setInternalLink(idx, { target_url: v })}
                              autoComplete="off"
                              suffix={link.reason === "related_article"
                                ? <Badge tone="info" size="small">Article</Badge>
                                : undefined}
                            />
                          </div>
                        ))}
                        <InlineStack gap="200">
                          <Button size="slim" variant="plain" onClick={onLoadArticles}>
                            {fr ? "Ajouter un lien vers un autre article" : "Add link to another article"}
                          </Button>
                        </InlineStack>
                        {showArticlePicker && (
                          <Box
                            padding="300"
                            background="bg-surface-secondary"
                            borderRadius="200"
                            borderColor="border"
                            borderWidth="025"
                          >
                            <BlockStack gap="200">
                              <InlineStack align="space-between" blockAlign="center">
                                <Text as="p" variant="bodySm" fontWeight="semibold">
                                  {fr ? "Choisir un article" : "Choose an article"}
                                </Text>
                                <Button size="slim" variant="plain" onClick={() => setShowArticlePicker(false)}>
                                  {fr ? "Fermer" : "Close"}
                                </Button>
                              </InlineStack>
                              {articlesFetcher.state !== "idle" ? (
                                <InlineStack gap="200" blockAlign="center">
                                  <Spinner size="small" />
                                  <Text as="span" variant="bodySm">{fr ? "Chargement…" : "Loading…"}</Text>
                                </InlineStack>
                              ) : (articlesFetcher.data?.articles ?? []).length === 0 ? (
                                <Text as="p" variant="bodySm" tone="subdued">
                                  {fr ? "Aucun autre article disponible." : "No other articles available."}
                                </Text>
                              ) : (
                                <BlockStack gap="150">
                                  {(articlesFetcher.data?.articles ?? []).map((article) => (
                                    <InlineStack key={article.id} align="space-between" blockAlign="center">
                                      <BlockStack gap="025">
                                        <Text as="span" variant="bodySm">{article.blog_title}</Text>
                                        <Badge
                                          tone={article.status === "published_to_shopify" ? "success" : "info"}
                                          size="small"
                                        >
                                          {article.status === "published_to_shopify"
                                            ? (fr ? "Publié" : "Published")
                                            : (fr ? "Brouillon" : "Draft")}
                                        </Badge>
                                      </BlockStack>
                                      <Button size="slim" onClick={() => addArticleLink(article)}>
                                        {fr ? "Ajouter" : "Add"}
                                      </Button>
                                    </InlineStack>
                                  ))}
                                </BlockStack>
                              )}
                            </BlockStack>
                          </Box>
                        )}
                        <InlineStack gap="200">
                          <Button size="slim" variant="plain" onClick={onFetchSuggestions} loading={suggestionsFetcher.state !== "idle"}>
                            {fr ? "Rafraîchir les suggestions" : "Refresh suggestions"}
                          </Button>
                        </InlineStack>
                        {showSuggestions && (
                          <Box
                            padding="300"
                            background="bg-surface-secondary"
                            borderRadius="200"
                            borderColor="border"
                            borderWidth="025"
                          >
                            <BlockStack gap="200">
                              <InlineStack align="space-between" blockAlign="center">
                                <Text as="p" variant="bodySm" fontWeight="semibold">
                                  {fr ? "Suggestions de liens" : "Link suggestions"}
                                </Text>
                                <Button size="slim" variant="plain" onClick={() => setShowSuggestions(false)}>
                                  {fr ? "Fermer" : "Close"}
                                </Button>
                              </InlineStack>
                              {suggestionsFetcher.state !== "idle" ? (
                                <InlineStack gap="200" blockAlign="center">
                                  <Spinner size="small" />
                                  <Text as="span" variant="bodySm">{fr ? "Analyse en cours…" : "Analyzing…"}</Text>
                                </InlineStack>
                              ) : (suggestionsFetcher.data?.suggestions ?? []).length === 0 ? (
                                <Text as="p" variant="bodySm" tone="subdued">
                                  {fr ? "Aucune suggestion trouvée pour ces mots-clés." : "No suggestions found for these keywords."}
                                </Text>
                              ) : (
                                <BlockStack gap="150">
                                  {(suggestionsFetcher.data?.suggestions ?? []).map((s, i) => {
                                    const badge = linkReasonBadge(s.reason, fr);
                                    return (
                                      <InlineStack key={`${s.target_url}-${i}`} align="space-between" blockAlign="center">
                                        <BlockStack gap="025">
                                          <Text as="span" variant="bodySm">{s.target_title || s.anchor}</Text>
                                          <Badge tone={badge.tone} size="small">{badge.label}</Badge>
                                        </BlockStack>
                                        <Button size="slim" onClick={() => addSuggestedLink(s)}>
                                          {fr ? "Ajouter" : "Add"}
                                        </Button>
                                      </InlineStack>
                                    );
                                  })}
                                </BlockStack>
                              )}
                            </BlockStack>
                          </Box>
                        )}
                      </BlockStack>
                    </Box>
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
                      {(draft.internal_links ?? []).length > 0 && (
                        <aside style={{ marginTop: 32, borderTop: "1px solid #E5E7EB", paddingTop: 20 }}>
                          <h2 style={{ fontSize: 20, marginBottom: 10 }}>
                            {fr ? "À lire aussi" : "Related reading"}
                          </h2>
                          <ul>
                            {(draft.internal_links ?? []).map((link, idx) => (
                              <li key={`${link.target_url}-${idx}`}>
                                <a href={link.target_url}>{link.anchor || link.target_title || link.target_url}</a>
                              </li>
                            ))}
                          </ul>
                        </aside>
                      )}
                    </article>
                  </Box>
                )}
              </BlockStack>
            </Card>
          ) : (
            <Card>
              <EmptyState
                heading={fr ? "Aucun brouillon sélectionné" : "No draft selected"}
                action={{ content: fr ? "Aller à Produits" : "Go to Products", url: "/app/products" }}
                image=""
              >
                <p>
                  {fr
                    ? "Génère un brouillon depuis Produits pour le retrouver ici."
                    : "Generate a draft from Products to see it here."}
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
    </>
  );
}
