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
  Checkbox,
  Collapsible,
  Divider,
  EmptyState,
  Icon,
  InlineStack,
  Modal,
  Page,
  Popover,
  Select,
  Spinner,
  Tabs,
  Tag,
  Text,
  TextField,
} from "@shopify/polaris";
import { CheckIcon, EditIcon, ImageIcon, QuestionCircleIcon, XIcon } from "@shopify/polaris-icons";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { callBackendForShop } from "../lib/api.server";
import { handleShopifyFilesIntent } from "../lib/shopifyFiles.server";
import { getLocale, loaderPhrases, type Locale } from "../lib/i18n";
import { AnalysisLoader } from "../components/AnalysisLoader";
import { CoverImageModal, ShopifyImagePicker } from "../components/ShopifyImagePicker";
import { scoreTone } from "../lib/marketAnalysisShared";
import { authenticate } from "../shopify.server";

interface Section { h2: string; direct_answer: string; body: string; image_url?: string; image_alt?: string }
interface FaqItem { q: string; a: string }
interface GeoScoreComponent { score: number; weight: number }
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
  secondary_keywords?: string[];
  keyword_check?: KeywordCheck;
  intro: string;
  summary?: string;
  meta_description?: string;
  sections: Section[];
  internal_links?: InternalLink[];
  faq?: FaqItem[];
  outline?: string[];
  tags?: string[];
  author_type?: "Organization" | "Person";
  author_name?: string;
  author_url?: string | null;
  author_bio?: string;
  image_url?: string;
  image_alt?: string;
  image_style?: "hero" | "banner" | "centered" | "float-left" | "float-right";
  show_toc?: boolean;
  numbered_steps?: boolean;
  cta_enabled?: boolean;
  cta_label?: string;
  cta_url?: string;
  cta_description?: string;
  cta_position?: "mid" | "end";
  geo_score?: number;
  geo_score_components?: Record<string, GeoScoreComponent>;
  word_count?: number;
  confirmed_facts?: Array<{ key: string; value: string }>;
  target_customer?: string;
  product_summary?: string;
  status?: "draft" | "published_to_shopify";
  shopify_visible?: boolean;
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
  angle?: string;
  source_label?: string;
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
  ideaSuggestions: BlogIdeaFlat[];
  keywordSuggestions: string[];
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
  // Only open a draft when one is explicitly requested in the URL — landing on
  // /app/blog shows the inspiration grid, not a pre-opened article.
  const targetId = draftId ?? null;
  if (targetId) {
    const oneRes = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/blog/drafts/${targetId}`,
      { accessToken: session.accessToken },
    );
    if (oneRes.ok) selected = (await oneRes.json()) as Draft;
  }

  // Load blog ideas + keyword suggestions from the latest market analysis
  let blogIdeas: BlogIdeaFlat[] = [];
  let keywordSuggestions: string[] = [];
  try {
    if (analysisRes && analysisRes.ok) {
      const analysis = (await analysisRes.json()) as { products?: Array<{
        product_id: string; product_title: string;
        seo_keywords?: Array<{ query?: string }>;
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
      // De-duplicated keyword queries across all analysed products.
      const seen = new Set<string>();
      for (const p of analysis.products ?? []) {
        for (const k of p.seo_keywords ?? []) {
          const q = (k.query ?? "").trim();
          if (q && !seen.has(q.toLowerCase())) { seen.add(q.toLowerCase()); keywordSuggestions.push(q); }
        }
      }
      keywordSuggestions = keywordSuggestions.slice(0, 40);
    }
  } catch { /* analysis not available yet */ }

  // Suggested ideas: seasonal/trending, competitor alternatives, product advantages.
  let ideaSuggestions: BlogIdeaFlat[] = [];
  try {
    const suggRes = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/blog/idea-suggestions`,
      { accessToken: session.accessToken },
    );
    if (suggRes.ok) {
      const data = (await suggRes.json()) as { suggestions?: Array<{
        title?: string; target_keyword?: string; intro?: string; outline?: string[];
        product_id?: string; product_title?: string; angle?: string; source_label?: string;
      }> };
      ideaSuggestions = (data.suggestions ?? []).map((s) => ({
        title: s.title ?? "",
        target_keyword: s.target_keyword ?? "",
        intro: s.intro ?? "",
        outline: s.outline ?? [],
        product_id: s.product_id ?? "",
        product_title: s.product_title ?? "",
        idea_index: -1,
        angle: s.angle,
        source_label: s.source_label,
      }));
    }
  } catch { /* suggestions are advisory only */ }

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
    ideaSuggestions,
    keywordSuggestions,
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

interface BlogAuthor {
  id: string;
  name: string;
  bio: string;
  url: string;
}

interface ActionResult {
  type: string;
  ok: boolean;
  error: string | null;
  draft?: Draft | null;
  blogs?: Array<{ id: string; handle: string; title: string }>;
  articles?: LinkableArticle[];
  suggestions?: DynamicSuggestion[];
  authors?: BlogAuthor[];
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
      const body: {
        product_id: string;
        auto_generate: boolean;
        blog_idea_index?: number;
        idea?: { title: string; target_keyword: string; secondary_keywords?: string[]; intro: string; outline: string[] };
      } = {
        product_id: productId,
        auto_generate: true,
      };
      const rawIdea = String(form.get("idea") ?? "");
      if (rawIdea) {
        try {
          body.idea = JSON.parse(rawIdea);
        } catch { /* ignore malformed idea */ }
      } else if (blogIdeaIndex !== null && Number.isFinite(blogIdeaIndex)) {
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

    if (intent === "listAuthors" || intent === "createAuthor" || intent === "deleteAuthor") {
      let res: Response;
      if (intent === "createAuthor") {
        res = await proxy("/blog/authors", {
          method: "POST",
          body: JSON.stringify({
            id: String(form.get("id") ?? ""),
            name: String(form.get("name") ?? ""),
            bio: String(form.get("bio") ?? ""),
            url: String(form.get("url") ?? ""),
          }),
        });
      } else if (intent === "deleteAuthor") {
        res = await proxy(`/blog/authors/${String(form.get("id") ?? "")}`, { method: "DELETE" });
      } else {
        res = await proxy("/blog/authors");
      }
      const data = res.ok ? ((await res.json()) as { authors?: BlogAuthor[] }) : null;
      return json<ActionResult>({
        type: intent,
        ok: res.ok,
        error: res.ok ? null : `${res.status}`,
        draft: null,
        authors: data?.authors ?? [],
      });
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

/** Per-pillar breakdown of the blog GEO/SEO score — mirrors the product page
 *  GeoScoreBreakdown: ✓ (done, ≥70) / ✗ (to improve) with weight per pillar. */
function BlogGeoScoreBreakdown({
  components,
  locale,
}: {
  components?: Record<string, GeoScoreComponent>;
  locale: Locale;
}) {
  const fr = locale === "fr";
  const pillars: Array<{ key: string; label: string }> = [
    { key: "content_length", label: fr ? "Longueur du contenu" : "Content length" },
    { key: "keyword", label: fr ? "Mot-clé placé" : "Keyword placement" },
    { key: "structure", label: fr ? "Structure (intro, H2)" : "Structure (intro, H2)" },
    { key: "meta_description", label: fr ? "Meta description" : "Meta description" },
    { key: "faq", label: "FAQ" },
    { key: "internal_links", label: fr ? "Liens internes" : "Internal links" },
    { key: "image", label: fr ? "Image de couverture" : "Cover image" },
  ];
  const has = components && Object.keys(components).length > 0;
  return (
    <BlockStack gap="200">
      <Text as="p" variant="headingSm">
        {fr ? "Détail du Score GEO" : "GEO score breakdown"}
      </Text>
      <Text as="p" variant="bodySm" tone="subdued">
        {fr
          ? "Ce que les moteurs évaluent. ✓ = en place, ✗ = à compléter. Le % est le poids dans le score."
          : "What engines assess. ✓ = in place, ✗ = to complete. The % is its weight in the score."}
      </Text>
      {!has ? (
        <Text as="p" variant="bodySm" tone="subdued">
          {fr ? "Sauvegardez pour voir le détail par critère." : "Save to see the per-criterion breakdown."}
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

/** Minimal Markdown → HTML for the preview, mirroring app/blog/markdown.py.
 *  LLM bodies contain **bold**, bullet lists, links — render them instead of
 *  showing literal asterisks. Input is HTML-escaped first, so it is safe to inject. */
function escapeHtml(s: string): string {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function renderInlineMd(text: string): string {
  let s = escapeHtml(text);
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]*)\)/g, '<a href="$2">$1</a>');
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*([^*\n]+?)\*/g, "<em>$1</em>");
  s = s.replace(/(^|[^A-Za-z0-9_])_([^_\n]+?)_(?![A-Za-z0-9_])/g, "$1<em>$2</em>");
  return s;
}
function renderMd(text: string): string {
  if (!text || !text.trim()) return "";
  const blocks: string[] = [];
  let para: string[] = [];
  let items: string[] = [];
  let listTag = "";
  const flushPara = () => { if (para.length) { blocks.push("<p>" + para.join(" ") + "</p>"); para = []; } };
  const flushList = () => { if (items.length) { blocks.push(`<${listTag}>` + items.map((i) => `<li>${i}</li>`).join("") + `</${listTag}>`); items = []; listTag = ""; } };
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) { flushPara(); flushList(); continue; }
    const heading = line.match(/^\s*(#{2,4})\s+(.*)$/);
    if (heading) { flushPara(); flushList(); const lvl = Math.min(heading[1].length + 1, 4); blocks.push(`<h${lvl}>${renderInlineMd(heading[2])}</h${lvl}>`); continue; }
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || numbered) { flushPara(); const tag = bullet ? "ul" : "ol"; if (listTag && listTag !== tag) flushList(); listTag = tag; items.push(renderInlineMd((bullet || numbered)![1])); continue; }
    flushList(); para.push(renderInlineMd(line));
  }
  flushPara(); flushList();
  return blocks.join("\n");
}

/** Live word count over intro + section answers/bodies (mirrors the backend scorer). */
function countDraftWords(d: Draft): number {
  const parts = [d.intro || ""];
  for (const s of d.sections || []) {
    parts.push(s.direct_answer || "", s.body || "");
  }
  const text = parts.join(" ").replace(/<[^>]+>/g, " ").trim();
  return text ? text.split(/\s+/).length : 0;
}

const READING_WORDS_PER_MIN = 200;
const TARGET_WORDS = 1500;

/** Live blog GEO score, mirroring app/blog/seo_score.py so the badge updates in
 *  real time as the merchant edits (links, image, meta…) without waiting for a save. */
function computeBlogGeoScore(d: Draft): { score: number; components: Record<string, GeoScoreComponent> } {
  const words = countDraftWords(d);
  const lengthScore = Math.min(words / TARGET_WORDS, 1);
  const kw = (d.target_keyword || "").trim().toLowerCase();
  const title = (d.blog_title || "").toLowerCase();
  const intro = (d.intro || "").toLowerCase();
  const h2text = (d.sections || []).map((s) => (s.h2 || "").toLowerCase()).join(" ");
  const keywordScore = kw ? [title.includes(kw), intro.includes(kw), h2text.includes(kw)].filter(Boolean).length / 3 : 0;
  const sections = (d.sections || []).filter((s) => (s.h2 || "").trim());
  const answered = sections.filter((s) => (s.direct_answer || "").trim()).length;
  const hasAnswers = sections.length ? answered >= Math.max(1, Math.floor(sections.length / 2)) : false;
  const structureScore = [!!(d.intro || "").trim(), sections.length >= 3, hasAnswers].filter(Boolean).length / 3;
  const meta = (d.meta_description || "").trim();
  const metaScore = !meta ? 0 : meta.length >= 70 && meta.length <= 155 ? 1 : 0.5;
  const faqLen = (d.faq || []).length;
  const faqScore = faqLen >= 2 ? 1 : faqLen >= 1 ? 0.5 : 0;
  const linksLen = (d.internal_links || []).filter(Boolean).length;
  const linksScore = Math.min(linksLen / 2, 1);
  const imageScore = (d.image_url || "").trim() ? 1 : 0;
  const components: Record<string, GeoScoreComponent> = {
    content_length: { score: Math.round(lengthScore * 100), weight: 0.2 },
    keyword: { score: Math.round(keywordScore * 100), weight: 0.2 },
    structure: { score: Math.round(structureScore * 100), weight: 0.15 },
    meta_description: { score: Math.round(metaScore * 100), weight: 0.15 },
    faq: { score: Math.round(faqScore * 100), weight: 0.1 },
    internal_links: { score: Math.round(linksScore * 100), weight: 0.1 },
    image: { score: Math.round(imageScore * 100), weight: 0.1 },
  };
  const weighted = Object.values(components).reduce((s, c) => s + c.score * c.weight, 0);
  return { score: Math.round(weighted), components };
}

/** Editable fields persisted by saveDraft — single source of truth for both the
 *  manual Save and the debounced auto-save (and dirty detection). */
function buildSavePayload(d: Draft): Record<string, unknown> {
  return {
    blog_title: d.blog_title,
    intro: d.intro,
    summary: d.summary,
    target_keyword: d.target_keyword ?? "",
    secondary_keywords: d.secondary_keywords ?? [],
    meta_description: d.meta_description ?? "",
    sections: d.sections,
    internal_links: d.internal_links ?? [],
    faq: d.faq ?? [],
    tags: d.tags ?? [],
    author_type: d.author_type ?? "Organization",
    author_name: d.author_name ?? "",
    author_url: d.author_url ?? null,
    author_bio: d.author_bio ?? "",
    image_url: d.image_url ?? "",
    image_alt: d.image_alt ?? "",
    image_style: d.image_style ?? "hero",
    show_toc: d.show_toc ?? true,
    numbered_steps: d.numbered_steps ?? false,
    cta_enabled: d.cta_enabled ?? false,
    cta_label: d.cta_label ?? "",
    cta_url: d.cta_url ?? "",
    cta_description: d.cta_description ?? "",
    cta_position: d.cta_position ?? "end",
  };
}

export default function BlogIndexPage() {
  const { locale, shop, drafts, selected, error, prefillTitle, prefillCluster, blogIdeas, ideaSuggestions, keywordSuggestions, pillarIdeaKeys } = useLoaderData<typeof loader>();
  const pillarIdeaKeySet = useMemo(() => new Set(pillarIdeaKeys), [pillarIdeaKeys]);
  const actionData = useActionData<typeof action>();
  const submit = useSubmit();
  const navigate = useNavigate();
  const navigation = useNavigation();
  const fr = locale === "fr";

  // Editable copy of the selected draft.
  const [draft, setDraft] = useState<Draft | null>(selected);
  // 0 = édition, 1 = aperçu. Opening/generating an article lands on the preview
  // (the cover image + format can be edited from there too); the Édition tab keeps
  // the full field-by-field editor.
  const [tabIndex, setTabIndex] = useState(1);
  const [selectedIdea, setSelectedIdea] = useState<BlogIdeaFlat | null>(null);
  // Selecting an idea swaps in the right-hand "generate" panel at the top — scroll
  // back up so the merchant sees it instead of staying at the bottom of the list.
  const selectIdea = (idea: BlogIdeaFlat) => {
    setSelectedIdea(idea);
    setDraft(null);
    setIdeaKeyword(idea.target_keyword ?? "");
    setIdeaSecondary([]);
    setEditingKeyword(false);
    setNewKeyword("");
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  };
  useEffect(() => {
    setDraft(selected);
    // Land on the preview (tab 1) when an article is opened or freshly generated.
    setTabIndex(1);
    // Generating from an idea redirects to ?draft={newId} — switch the panel
    // over to the freshly generated draft instead of staying stuck on the idea card.
    setSelectedIdea(null);
  }, [selected?.id]);

  const fetcher = useFetcher<typeof action>();
  const blogsFetcher = useFetcher<{ ok?: boolean; blogs?: Array<{ id: string; handle: string; title: string }> }>();
  const articlesFetcher = useFetcher<ActionResult>();
  const suggestionsFetcher = useFetcher<ActionResult>();
  const authorsFetcher = useFetcher<ActionResult>();
  const authors = authorsFetcher.data?.authors ?? [];
  const [selectedAuthorId, setSelectedAuthorId] = useState("");
  const [newAuthorOpen, setNewAuthorOpen] = useState(false);
  const [newAuthor, setNewAuthor] = useState({ name: "", bio: "", url: "" });
  const isBusy = fetcher.state !== "idle";
  const isGeneratingArticle = navigation.state !== "idle" && navigation.formData?.get("intent") === "createFromProduct";
  const [showArticlePicker, setShowArticlePicker] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [selectedBlog, setSelectedBlog] = useState("");
  const [showPublished, setShowPublished] = useState(false);
  const [showDrafts, setShowDrafts] = useState(false);
  const [showIdeas, setShowIdeas] = useState(false);
  const [showSuggested, setShowSuggested] = useState(false);
  // Ideas already turned into a draft (generated or published) live in the
  // Brouillons/Publiés lists, so hide them from the idea lists — each item in one place.
  const draftTitleSet = useMemo(
    () => new Set(drafts.map((d) => (d.blog_title || "").trim().toLowerCase()).filter(Boolean)),
    [drafts],
  );
  const isRealised = (idea: BlogIdeaFlat) => draftTitleSet.has((idea.title || "").trim().toLowerCase());
  const visibleBlogIdeas = useMemo(() => blogIdeas.filter((i) => !isRealised(i)), [blogIdeas, draftTitleSet]);
  const visibleSuggestions = useMemo(() => ideaSuggestions.filter((i) => !isRealised(i)), [ideaSuggestions, draftTitleSet]);
  // Up to 6 ideas (suggested first, then analysis blog ideas) for the landing grid.
  const inspirationIdeas = [...visibleSuggestions, ...visibleBlogIdeas].slice(0, 6);
  const [coverOpen, setCoverOpen] = useState(false);
  // Keyword editing for the idea panel (pre-generation): primary keyword + extras
  // chosen from past-analysis suggestions, all fed into the article generation.
  const [ideaKeyword, setIdeaKeyword] = useState("");
  const [ideaSecondary, setIdeaSecondary] = useState<string[]>([]);
  const [editingKeyword, setEditingKeyword] = useState(false);
  const [newKeyword, setNewKeyword] = useState("");
  const addIdeaKeyword = (kw: string) => {
    const v = kw.trim();
    if (!v) return;
    setIdeaSecondary((s) => (v === ideaKeyword || s.includes(v) ? s : [...s, v]));
  };
  const addNewKeyword = () => { addIdeaKeyword(newKeyword); setNewKeyword(""); };

  // Localized format options for the cover-image popup (shared with the preview).
  const coverStyleOptions = [
    { label: fr ? "Couverture pleine largeur" : "Full-width cover", value: "hero" },
    { label: fr ? "Bandeau cinématique (plus court)" : "Cinematic banner (shorter)", value: "banner" },
    { label: fr ? "Image centrée" : "Centered image", value: "centered" },
    { label: fr ? "Flottant à gauche (texte à droite)" : "Float left (text wraps right)", value: "float-left" },
    { label: fr ? "Flottant à droite (texte à gauche)" : "Float right (text wraps left)", value: "float-right" },
  ];
  const [geoHelpOpen, setGeoHelpOpen] = useState(false);

  const wordCount = useMemo(() => (draft ? countDraftWords(draft) : 0), [draft]);
  const readingMinutes = Math.max(1, Math.round(wordCount / READING_WORDS_PER_MIN));
  // GEO score computed live from the current edits (not the last saved value).
  const liveGeo = useMemo(() => (draft ? computeBlogGeoScore(draft) : null), [draft]);
  const geoScore = liveGeo?.score ?? null;

  // ── Debounced auto-save ─────────────────────────────────────────────────────
  const autoSaveFetcher = useFetcher<typeof action>();
  const lastSavedRef = useRef<string>("");
  const pendingPublishRef = useRef(false);
  useEffect(() => {
    // Reset the saved baseline whenever a different draft loads.
    lastSavedRef.current = selected ? JSON.stringify(buildSavePayload(selected)) : "";
  }, [selected?.id]);

  const persistDraft = useCallback((d: Draft) => {
    autoSaveFetcher.submit(
      { intent: "saveDraft", id: d.id, payload: JSON.stringify(buildSavePayload(d)) },
      { method: "post" },
    );
    lastSavedRef.current = JSON.stringify(buildSavePayload(d));
  }, [autoSaveFetcher]);

  useEffect(() => {
    if (!draft?.id) return;
    const snapshot = JSON.stringify(buildSavePayload(draft));
    if (snapshot === lastSavedRef.current) return;
    const timer = setTimeout(() => persistDraft(draft), 900);
    return () => clearTimeout(timer);
  }, [draft, persistDraft]);

  // Chain a forced save → publish so publishing never loses unsaved edits.
  useEffect(() => {
    if (autoSaveFetcher.state === "idle" && pendingPublishRef.current && autoSaveFetcher.data) {
      pendingPublishRef.current = false;
      doPublish();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSaveFetcher.state, autoSaveFetcher.data]);

  useEffect(() => {
    if (blogsFetcher.data?.blogs && blogsFetcher.data.blogs.length && !selectedBlog) {
      setSelectedBlog(blogsFetcher.data.blogs[0].id);
    }
  }, [blogsFetcher.data?.blogs, selectedBlog]);

  useEffect(() => {
    const d = fetcher.data;
    if (!d) return;
    if ((d.type === "regenerateSection" || d.type === "publishDraft") && d.ok && d.draft) {
      // Sync the saved baseline so auto-save doesn't immediately re-fire.
      lastSavedRef.current = JSON.stringify(buildSavePayload(d.draft as Draft));
      setDraft(d.draft as Draft);
      if (d.type === "publishDraft") setPublishOpen(false);
    }
  }, [fetcher.data]);

  // Auto-load internal-link / cluster suggestions when a draft opens so the merchant
  // immediately sees which sibling/pillar articles they should link to (and which
  // are still missing) without an extra click. Cheap: pure matching, no LLM call.
  useEffect(() => {
    if (!selected?.id) return;
    const existingUrls = (selected.internal_links ?? []).map((l) => l.target_url).join("||");
    const keywords = [
      selected.blog_title,
      ...(selected.sections ?? []).map((s) => s.h2),
    ].filter(Boolean).join("||");
    if (!keywords) return;
    suggestionsFetcher.submit(
      { intent: "fetchLinkSuggestions", draftId: selected.id, keywords, excludeUrls: existingUrls },
      { method: "post" },
    );
    setShowSuggestions(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id]);

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

  const setFaqItem = (idx: number, patch: Partial<FaqItem>) =>
    setDraft((prev) => prev ? {
      ...prev,
      faq: (prev.faq ?? []).map((f, i) => i === idx ? { ...f, ...patch } : f),
    } : prev);
  const addFaqItem = () =>
    setDraft((prev) => prev ? { ...prev, faq: [...(prev.faq ?? []), { q: "", a: "" }] } : prev);
  const removeFaqItem = (idx: number) =>
    setDraft((prev) => prev ? { ...prev, faq: (prev.faq ?? []).filter((_, i) => i !== idx) } : prev);

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
    authorsFetcher.submit({ intent: "listAuthors" }, { method: "post" });
  };

  // Apply a saved author to the draft (its name/bio/url feed the published HTML + JSON-LD).
  const applyAuthor = (a: BlogAuthor | null) => {
    setSelectedAuthorId(a?.id ?? "");
    setDraft((p) => p ? {
      ...p,
      author_type: a ? "Person" : "Organization",
      author_name: a?.name ?? "",
      author_bio: a?.bio ?? "",
      author_url: a?.url ?? null,
    } : p);
  };

  const onCreateAuthor = () => {
    if (!newAuthor.name.trim()) return;
    authorsFetcher.submit(
      { intent: "createAuthor", name: newAuthor.name, bio: newAuthor.bio, url: newAuthor.url },
      { method: "post" },
    );
  };

  // After creating an author, auto-select the newest one and apply it.
  useEffect(() => {
    if (authorsFetcher.data?.type === "createAuthor" && authorsFetcher.data.ok) {
      const created = (authorsFetcher.data.authors ?? [])[0];
      if (created) {
        applyAuthor(created);
        setNewAuthorOpen(false);
        setNewAuthor({ name: "", bio: "", url: "" });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authorsFetcher.data]);

  function doPublish() {
    if (!draft) return;
    fetcher.submit(
      {
        intent: "publishDraft",
        id: draft.id,
        // Always publish live (visible) — no draft/hidden state exposed to the merchant.
        payload: JSON.stringify({ blog_id: selectedBlog, publisher_name: shop, published: true }),
      },
      { method: "post" },
    );
  }

  const onPublish = () => {
    if (!draft) return;
    // If there are unsaved edits, force a save first then publish (chained via the
    // auto-save effect) so the published article always reflects the latest state.
    const snapshot = JSON.stringify(buildSavePayload(draft));
    if (snapshot !== lastSavedRef.current) {
      pendingPublishRef.current = true;
      persistDraft(draft);
    } else {
      doPublish();
    }
  };

  const onDelete = () => {
    if (!draft) return;
    if (typeof window !== "undefined" && !window.confirm(fr ? "Supprimer ce brouillon ?" : "Delete this draft?")) return;
    submit({ intent: "deleteDraft", id: draft.id }, { method: "post" });
  };

  return (
    <>
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
                    <Button
                      onClick={() => setShowPublished((p) => !p)}
                      fullWidth
                      textAlign="left"
                      disclosure={showPublished ? "up" : "down"}
                      variant="tertiary"
                    >
                      {fr ? `Publiés (${published.length})` : `Published (${published.length})`}
                    </Button>
                    <Collapsible open={showPublished} id="blog-published">
                      <Box>
                        {published.map((d) => (
                          <DraftListItem key={d.id} draft={d} active={d.id === draft?.id && !selectedIdea} locale={locale} onClick={() => setSelectedIdea(null)} />
                        ))}
                      </Box>
                    </Collapsible>
                    <Divider />
                  </>
                );
              })()}

              {/* ── Brouillons ───────────────────────────────────────── */}
              {(() => {
                const unpublished = drafts.filter((d) => d.status !== "published_to_shopify");
                return (
                  <>
                    <Button
                      onClick={() => setShowDrafts((p) => !p)}
                      fullWidth
                      textAlign="left"
                      disclosure={showDrafts ? "up" : "down"}
                      variant="tertiary"
                    >
                      {fr ? `Brouillons (${unpublished.length})` : `Drafts (${unpublished.length})`}
                    </Button>
                    <Collapsible open={showDrafts} id="blog-drafts">
                      {unpublished.length === 0 ? (
                        <Box padding="200">
                          <Text as="p" tone="subdued" variant="bodySm">
                            {fr ? "Aucun brouillon." : "No drafts yet."}
                          </Text>
                        </Box>
                      ) : (
                        <Box>
                          {unpublished.map((d) => (
                            <DraftListItem key={d.id} draft={d} active={d.id === draft?.id && !selectedIdea} locale={locale} onClick={() => setSelectedIdea(null)} />
                          ))}
                        </Box>
                      )}
                    </Collapsible>
                  </>
                );
              })()}

              {/* ── Idées de blog ────────────────────────────────────── */}
              {visibleBlogIdeas.length > 0 && (
                <>
                  <Divider />
                  <InlineStack gap="150" blockAlign="center" wrap={false}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#D72C0D", flex: "0 0 auto" }} />
                    <div style={{ flex: 1 }}>
                      <Button
                        onClick={() => setShowIdeas((p) => !p)}
                        fullWidth
                        textAlign="left"
                        disclosure={showIdeas ? "up" : "down"}
                        variant="tertiary"
                      >
                        {fr ? `Idées de blog (${visibleBlogIdeas.length})` : `Blog ideas (${visibleBlogIdeas.length})`}
                      </Button>
                    </div>
                  </InlineStack>
                  <Collapsible open={showIdeas} id="blog-ideas">
                    <BlockStack gap="100">
                      {(() => {
                        const byProduct = new Map<string, BlogIdeaFlat[]>();
                        visibleBlogIdeas.forEach((idea) => {
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
                                  onClick={() => selectIdea(idea)}
                                  onKeyDown={(e) => { if (e.key === "Enter") selectIdea(idea); }}
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
                  </Collapsible>
                </>
              )}

              {/* ── Idées suggérées (tendances, concurrents, avantages) ─── */}
              {visibleSuggestions.length > 0 && (
                <>
                  <Divider />
                  <InlineStack gap="150" blockAlign="center" wrap={false}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#D72C0D", flex: "0 0 auto" }} />
                    <div style={{ flex: 1 }}>
                      <Button
                        onClick={() => setShowSuggested((p) => !p)}
                        fullWidth
                        textAlign="left"
                        disclosure={showSuggested ? "up" : "down"}
                        variant="tertiary"
                      >
                        {fr ? `Idées suggérées (${visibleSuggestions.length})` : `Suggested ideas (${visibleSuggestions.length})`}
                      </Button>
                    </div>
                  </InlineStack>
                  <Collapsible open={showSuggested} id="blog-suggested">
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySm" tone="subdued">
                        {fr
                          ? "Tendances saisonnières, alternatives aux concurrents et avantages produit."
                          : "Seasonal trends, competitor alternatives and product advantages."}
                      </Text>
                      <BlockStack gap="050">
                    {visibleSuggestions.map((idea, i) => {
                      const isActive = selectedIdea?.title === idea.title && selectedIdea?.idea_index === -1;
                      const tone = idea.angle === "competitor" ? "warning"
                        : idea.angle === "seasonal" || idea.angle === "trend" ? "info"
                        : "success";
                      return (
                        <div
                          key={`sugg-${i}`}
                          role="button"
                          tabIndex={0}
                          onClick={() => selectIdea(idea)}
                          onKeyDown={(e) => { if (e.key === "Enter") selectIdea(idea); }}
                          style={{
                            padding: "8px 12px",
                            borderRadius: 6,
                            cursor: "pointer",
                            background: isActive ? "var(--p-color-bg-surface-active)" : "transparent",
                            marginBottom: 2,
                          }}
                        >
                          <BlockStack gap="050">
                            <Text as="span" variant="bodySm" fontWeight={isActive ? "semibold" : "regular"}>
                              {idea.title}
                            </Text>
                            {idea.source_label && (
                              <InlineStack>
                                <Badge tone={tone} size="small">{idea.source_label}</Badge>
                              </InlineStack>
                            )}
                          </BlockStack>
                        </div>
                      );
                    })}
                      </BlockStack>
                    </BlockStack>
                  </Collapsible>
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
                <InlineStack align="space-between" blockAlign="center" wrap={false}>
                  <BlockStack gap="050">
                    <Text as="h2" variant="headingLg">{selectedIdea.title || (fr ? "(sans titre)" : "(untitled)")}</Text>
                    <Text as="p" variant="bodySm" tone="subdued">{selectedIdea.product_title}</Text>
                  </BlockStack>
                  <Button variant="plain" onClick={() => setSelectedIdea(null)}>
                    {fr ? "Fermer" : "Close"}
                  </Button>
                </InlineStack>

                {selectedIdea.source_label && (
                  <InlineStack>
                    <Badge tone="info">{selectedIdea.source_label}</Badge>
                  </InlineStack>
                )}

                <BlockStack gap="100">
                  <Text as="span" variant="bodySm" tone="subdued">{fr ? "Mot-clé cible :" : "Target keyword:"}</Text>
                  <InlineStack gap="150" blockAlign="center">
                    {editingKeyword ? (
                      <div style={{ minWidth: 240 }}>
                        <TextField label="" labelHidden value={ideaKeyword} onChange={setIdeaKeyword} autoComplete="off" />
                      </div>
                    ) : (
                      <Badge tone="attention">{ideaKeyword || (fr ? "(non défini)" : "(none)")}</Badge>
                    )}
                    <Button variant="plain" icon={EditIcon} accessibilityLabel={fr ? "Modifier le mot-clé" : "Edit keyword"} onClick={() => setEditingKeyword((e) => !e)} />
                  </InlineStack>
                  {ideaSecondary.length > 0 && (
                    <InlineStack gap="100" wrap>
                      {ideaSecondary.map((kw) => (
                        <Tag key={kw} onRemove={() => setIdeaSecondary((s) => s.filter((k) => k !== kw))}>{kw}</Tag>
                      ))}
                    </InlineStack>
                  )}
                  {keywordSuggestions.length > 0 && (
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySm" tone="subdued">
                        {fr ? "Suggestions (de vos analyses) — cliquez pour ajouter :" : "Suggestions (from your analyses) — click to add:"}
                      </Text>
                      <InlineStack gap="100" wrap>
                        {keywordSuggestions
                          .filter((kw) => kw !== ideaKeyword && !ideaSecondary.includes(kw))
                          .slice(0, 15)
                          .map((kw) => (
                            <Button key={kw} size="slim" variant="tertiary" onClick={() => addIdeaKeyword(kw)}>
                              {`+ ${kw}`}
                            </Button>
                          ))}
                      </InlineStack>
                    </BlockStack>
                  )}
                </BlockStack>

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
                      {/* Always send the (possibly edited) keywords so they steer generation. */}
                      <input
                        type="hidden"
                        name="idea"
                        value={JSON.stringify({
                          title: selectedIdea.title,
                          target_keyword: ideaKeyword,
                          secondary_keywords: ideaSecondary,
                          intro: selectedIdea.intro,
                          outline: selectedIdea.outline,
                        })}
                      />
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
                          ? "Génération en cours… cela peut prendre 1 à 2 minutes."
                          : "Generating… this can take 1-2 minutes."}
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
                  <InlineStack gap="200" blockAlign="center">
                    {geoScore !== null && (
                      <InlineStack gap="100" blockAlign="center">
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
                            <BlogGeoScoreBreakdown components={liveGeo?.components} locale={locale} />
                          </Box>
                        </Popover>
                        <Badge tone={scoreTone(geoScore)}>{`${fr ? "Score GEO" : "GEO score"} ${geoScore}/100`}</Badge>
                      </InlineStack>
                    )}
                    <Text as="span" variant="bodySm" tone="subdued">
                      {autoSaveFetcher.state !== "idle"
                        ? (fr ? "Enregistrement…" : "Saving…")
                        : (fr ? "Enregistré automatiquement" : "Auto-saved")}
                    </Text>
                    <Button variant="primary" onClick={onOpenPublish}
                      disabled={!draft.sections.length || !draft.sections.some((s) => s.direct_answer)}>
                      {fr ? "Publier" : "Publish"}
                    </Button>
                    <Button tone="critical" variant="plain" onClick={onDelete}>
                      {fr ? "Supprimer" : "Delete"}
                    </Button>
                    {/* Close the editor and return to the inspiration grid. Edits are
                        already auto-saved, so navigating away loses nothing. */}
                    <Button variant="plain" onClick={() => navigate("/app/blog")}>
                      {fr ? "Fermer" : "Close"}
                    </Button>
                  </InlineStack>
                </InlineStack>

                {draft.status === "published_to_shopify" && (
                  <Banner tone="success">
                    <p>{fr
                      ? "Cet article est en ligne et visible sur ta boutique Shopify. Tes modifications republiées éditent le même article."
                      : "This article is live and visible on your Shopify store. Re-publishing edits the same article."}</p>
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

                    {/* SEO bar: live word count vs target + reading time */}
                    <Box padding="300" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
                      <InlineStack gap="300" blockAlign="center" wrap>
                        <Badge tone={wordCount >= 1000 ? "success" : wordCount >= 600 ? "warning" : "critical"}>
                          {`${wordCount.toLocaleString(fr ? "fr-FR" : "en-US")} / ${TARGET_WORDS.toLocaleString(fr ? "fr-FR" : "en-US")} ${fr ? "mots min." : "words min."}`}
                        </Badge>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {fr ? `⏱ ${readingMinutes} min de lecture` : `⏱ ${readingMinutes} min read`}
                        </Text>
                        {wordCount < 1000 && (
                          <Text as="span" variant="bodySm" tone="subdued">
                            {fr
                              ? "Sous 1 000 mots, Google peut considérer l'article comme « thin content »."
                              : "Below 1,000 words Google may treat the article as thin content."}
                          </Text>
                        )}
                      </InlineStack>
                    </Box>

                    {/* Meta description — what shows in Google + sent as Shopify SEO description */}
                    <TextField
                      label={fr ? "Meta description (Google)" : "Meta description (Google)"}
                      value={draft.meta_description ?? ""}
                      onChange={(v) => setDraft((p) => p ? { ...p, meta_description: v } : p)}
                      multiline={2}
                      autoComplete="off"
                      maxLength={160}
                      showCharacterCount
                      helpText={(() => {
                        const len = (draft.meta_description ?? "").length;
                        if (len === 0) return fr ? "Résumé affiché dans les résultats Google (70-155 caractères)." : "Summary shown in Google results (70-155 chars).";
                        if (len < 70) return fr ? "Un peu court — visez 70-155 caractères." : "A bit short — aim for 70-155 characters.";
                        if (len > 155) return fr ? "Un peu long — Google tronque au-delà de 155 caractères." : "A bit long — Google truncates beyond 155 characters.";
                        return fr ? "Longueur idéale ✓" : "Ideal length ✓";
                      })()}
                    />

                    <ShopifyImagePicker
                      locale={locale}
                      imageUrl={draft.image_url ?? null}
                      imageAlt={draft.image_alt ?? null}
                      onSelect={(url, alt) => setDraft((p) => p ? { ...p, image_url: url, image_alt: alt || p.image_alt } : p)}
                      onAltChange={(alt) => setDraft((p) => p ? { ...p, image_alt: alt } : p)}
                      onRemove={() => setDraft((p) => p ? { ...p, image_url: "", image_alt: "" } : p)}
                    />

                    {draft.image_url && (
                      <Select
                        label={fr ? "Format et emplacement de l'image" : "Image format & placement"}
                        options={[
                          { label: fr ? "Couverture pleine largeur" : "Full-width cover", value: "hero" },
                          { label: fr ? "Bandeau cinématique (plus court)" : "Cinematic banner (shorter)", value: "banner" },
                          { label: fr ? "Image centrée" : "Centered image", value: "centered" },
                          { label: fr ? "Flottant à gauche (texte à droite)" : "Float left (text wraps right)", value: "float-left" },
                          { label: fr ? "Flottant à droite (texte à gauche)" : "Float right (text wraps left)", value: "float-right" },
                        ]}
                        value={draft.image_style ?? "hero"}
                        onChange={(v) => setDraft((p) => p ? { ...p, image_style: v as Draft["image_style"] } : p)}
                      />
                    )}

                    <Checkbox
                      label={fr ? "Afficher la table des matières" : "Show table of contents"}
                      helpText={fr
                        ? "Génère automatiquement une liste des sections de l'article."
                        : "Automatically generates a list of article sections."}
                      checked={draft.show_toc ?? true}
                      onChange={(v) => setDraft((p) => p ? { ...p, show_toc: v } : p)}
                    />

                    <Checkbox
                      label={fr ? "Format guide numéroté (étape par étape)" : "Numbered guide format (step by step)"}
                      helpText={fr
                        ? "Numérote les sections (1, 2, 3…) et ajoute le schema HowTo pour les tutoriels."
                        : "Numbers the sections (1, 2, 3…) and adds HowTo schema for tutorials."}
                      checked={draft.numbered_steps ?? false}
                      onChange={(v) => setDraft((p) => p ? { ...p, numbered_steps: v } : p)}
                    />

                    {/* Open Graph / social share preview — how the article looks when shared */}
                    <BlockStack gap="150">
                      <Text as="p" variant="headingSm">{fr ? "Aperçu du partage social" : "Social share preview"}</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        {fr
                          ? "Ce que voient vos clients quand l'article est partagé sur WhatsApp, Instagram, LinkedIn ou Facebook."
                          : "What customers see when the article is shared on WhatsApp, Instagram, LinkedIn or Facebook."}
                      </Text>
                      <div style={{ maxWidth: 420, border: "1px solid #E1E3E5", borderRadius: 8, overflow: "hidden", background: "#fff" }}>
                        <div style={{ width: "100%", aspectRatio: "1200 / 630", background: "#F1F2F4", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          {draft.image_url ? (
                            <img src={draft.image_url} alt={draft.image_alt || ""} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                          ) : (
                            <Text as="span" variant="bodySm" tone="subdued">{fr ? "Aucune image" : "No image"}</Text>
                          )}
                        </div>
                        <div style={{ padding: "10px 12px" }}>
                          <div style={{ fontSize: 11, textTransform: "uppercase", color: "#6D7175", letterSpacing: 0.3 }}>{shop}</div>
                          <div style={{ fontSize: 15, fontWeight: 600, color: "#202223", margin: "2px 0", lineHeight: 1.3 }}>
                            {draft.blog_title || (fr ? "(titre de l'article)" : "(article title)")}
                          </div>
                          <div style={{ fontSize: 13, color: "#6D7175", lineHeight: 1.4, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                            {draft.meta_description || draft.intro || (fr ? "Ajoutez une meta description ci-dessus." : "Add a meta description above.")}
                          </div>
                        </div>
                      </div>
                    </BlockStack>

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
                          <ShopifyImagePicker
                            locale={locale}
                            label={fr ? "Image de la section (optionnel)" : "Section image (optional)"}
                            imageUrl={section.image_url ?? null}
                            imageAlt={section.image_alt ?? null}
                            onSelect={(url, alt) => setSection(idx, { image_url: url, image_alt: alt || section.image_alt })}
                            onAltChange={(alt) => setSection(idx, { image_alt: alt })}
                            onRemove={() => setSection(idx, { image_url: "", image_alt: "" })}
                          />
                        </BlockStack>
                      </Card>
                    ))}

                    {/* FAQ block — editable Q/A appended at the end of the article (GEO signal) */}
                    <Box padding="400" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
                      <BlockStack gap="300">
                        <BlockStack gap="050">
                          <Text as="h3" variant="headingSm">{fr ? "Questions fréquentes (FAQ)" : "Frequently asked questions (FAQ)"}</Text>
                          <Text as="p" variant="bodySm" tone="subdued">
                            {fr
                              ? "Affichée en bas de l'article. Signal fort pour ChatGPT, Perplexity et Google AI Overviews."
                              : "Shown at the end of the article. Strong signal for ChatGPT, Perplexity and Google AI Overviews."}
                          </Text>
                        </BlockStack>
                        {(draft.faq ?? []).map((item, idx) => (
                          <BlockStack key={`faq-${idx}`} gap="100">
                            <InlineStack align="space-between" blockAlign="center">
                              <Text as="span" variant="bodySm" fontWeight="semibold">{`FAQ ${idx + 1}`}</Text>
                              <Button size="slim" variant="plain" tone="critical" onClick={() => removeFaqItem(idx)}>
                                {fr ? "Retirer" : "Remove"}
                              </Button>
                            </InlineStack>
                            <TextField
                              label={fr ? "Question" : "Question"}
                              labelHidden
                              placeholder={fr ? "Question" : "Question"}
                              value={item.q}
                              onChange={(v) => setFaqItem(idx, { q: v })}
                              autoComplete="off"
                            />
                            <TextField
                              label={fr ? "Réponse" : "Answer"}
                              labelHidden
                              placeholder={fr ? "Réponse" : "Answer"}
                              value={item.a}
                              onChange={(v) => setFaqItem(idx, { a: v })}
                              multiline={2}
                              autoComplete="off"
                            />
                          </BlockStack>
                        ))}
                        <InlineStack>
                          <Button size="slim" variant="plain" onClick={addFaqItem}>
                            {fr ? "Ajouter une question" : "Add a question"}
                          </Button>
                        </InlineStack>
                      </BlockStack>
                    </Box>

                    {/* CTA conversion block — drives blog traffic to the source product */}
                    <Box padding="400" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
                      <BlockStack gap="300">
                        <Checkbox
                          label={fr ? "Bouton d'appel à l'action (CTA)" : "Call-to-action button (CTA)"}
                          helpText={fr
                            ? "Encart bouton vers le produit. C'est ce qui transforme le trafic du blog en ventes."
                            : "Button box linking to the product. This turns blog traffic into sales."}
                          checked={draft.cta_enabled ?? false}
                          onChange={(v) => setDraft((p) => p ? { ...p, cta_enabled: v } : p)}
                        />
                        {draft.cta_enabled && (
                          <>
                            <TextField
                              label={fr ? "Texte du bouton" : "Button label"}
                              value={draft.cta_label ?? ""}
                              onChange={(v) => setDraft((p) => p ? { ...p, cta_label: v } : p)}
                              autoComplete="off"
                              placeholder={fr ? "Découvrir le produit" : "Discover the product"}
                            />
                            <TextField
                              label={fr ? "Lien du bouton (URL)" : "Button link (URL)"}
                              value={draft.cta_url ?? ""}
                              onChange={(v) => setDraft((p) => p ? { ...p, cta_url: v } : p)}
                              autoComplete="off"
                              placeholder="/products/..."
                              helpText={fr ? "Pré-rempli avec le produit source de l'article." : "Pre-filled with the article's source product."}
                            />
                            <TextField
                              label={fr ? "Phrase d'accroche (optionnel)" : "Tagline (optional)"}
                              value={draft.cta_description ?? ""}
                              onChange={(v) => setDraft((p) => p ? { ...p, cta_description: v } : p)}
                              autoComplete="off"
                              multiline={2}
                              placeholder={fr ? "Ex. Le harnais préféré des petits chiens frileux." : "e.g. The harness small dogs love."}
                            />
                            <Select
                              label={fr ? "Position du bouton" : "Button position"}
                              options={[
                                { label: fr ? "Fin de l'article" : "End of article", value: "end" },
                                { label: fr ? "Milieu (après le contenu, avant la FAQ)" : "Middle (after content, before FAQ)", value: "mid" },
                              ]}
                              value={draft.cta_position ?? "end"}
                              onChange={(v) => setDraft((p) => p ? { ...p, cta_position: v as "mid" | "end" } : p)}
                            />
                          </>
                        )}
                      </BlockStack>
                    </Box>

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
                    <article style={{ maxWidth: 720, margin: "0 auto", lineHeight: 1.65, overflow: "hidden" }}>
                      {/* 1. Title */}
                      <h1 style={{ marginBottom: 8, fontSize: 28 }}>
                        {draft.blog_title || (fr ? "(sans titre)" : "(untitled)")}
                      </h1>
                      {/* 2. Reading time + last updated date */}
                      <p style={{ color: "#6D7175", fontSize: 13, marginBottom: 16 }}>
                        {fr ? `⏱ ${readingMinutes} min de lecture` : `⏱ ${readingMinutes} min read`}
                        {draft.updated_at && (() => {
                          const d = new Date(draft.updated_at);
                          if (Number.isNaN(d.getTime())) return null;
                          const formatted = d.toLocaleDateString(fr ? "fr-FR" : "en-US", { day: "numeric", month: "long", year: "numeric" });
                          return ` · ${fr ? "Mis à jour le" : "Updated"} ${formatted}`;
                        })()}
                      </p>
                      {/* 3. Description (intro) */}
                      {draft.intro && (
                        <p
                          style={{ color: "#374151", fontSize: 17, marginBottom: 24 }}
                          dangerouslySetInnerHTML={{ __html: renderInlineMd(draft.intro) }}
                        />
                      )}
                      {/* 4. Table of contents — below title + description, above text/image */}
                      {draft.show_toc && draft.sections.length > 0 && (
                        <nav style={{ background: "#F9FAFB", border: "1px solid #E5E7EB", borderRadius: 8, padding: "16px 20px", marginBottom: 28 }}>
                          <p style={{ fontWeight: 600, marginBottom: 8, fontSize: 15 }}>
                            {fr ? "Sommaire" : "Table of contents"}
                          </p>
                          <ol style={{ margin: 0, paddingLeft: 20 }}>
                            {draft.sections.map((section, idx) => (
                              <li key={`toc-${idx}`} style={{ marginBottom: 4 }}>
                                <span style={{ color: "#2563EB", fontSize: 14 }}>{section.h2}</span>
                              </li>
                            ))}
                          </ol>
                        </nav>
                      )}
                      {/* No image → a full-width "Add an image" button under the TOC. */}
                      {!draft.image_url && (
                        <div style={{ marginBottom: 24 }}>
                          <Button fullWidth icon={ImageIcon} onClick={() => setCoverOpen(true)}>
                            {fr ? "Ajouter une image" : "Add an image"}
                          </Button>
                        </div>
                      )}
                      {/* 5. Cover image with a pencil overlay (top-left) to edit it. */}
                      {draft.image_url && (() => {
                        const style = draft.image_style ?? "hero";
                        const wrapperStyle: React.CSSProperties =
                          style === "centered"
                            ? { position: "relative", display: "block", margin: "0 auto 24px", maxWidth: 480, width: "100%" }
                            : style === "float-left"
                            ? { position: "relative", float: "left", width: "40%", maxWidth: 280, margin: "0 20px 8px 0" }
                            : style === "float-right"
                            ? { position: "relative", float: "right", width: "40%", maxWidth: 280, margin: "0 0 8px 20px" }
                            : { position: "relative", width: "100%", marginBottom: 24 };
                        const imgStyle: React.CSSProperties =
                          style === "banner"
                            ? { width: "100%", height: 220, objectFit: "cover", borderRadius: 0, display: "block" }
                            : style === "centered" || style === "float-left" || style === "float-right"
                            ? { width: "100%", borderRadius: 8, display: "block" }
                            : { width: "100%", maxHeight: 400, objectFit: "cover", borderRadius: 8, display: "block" };
                        return (
                          <div style={wrapperStyle}>
                            <img src={draft.image_url} alt={draft.image_alt || draft.blog_title || ""} style={imgStyle} />
                            <button
                              type="button"
                              onClick={() => setCoverOpen(true)}
                              aria-label={fr ? "Modifier l'image" : "Edit image"}
                              style={{
                                position: "absolute", top: 8, left: 8, width: 32, height: 32,
                                borderRadius: "50%", border: "none", cursor: "pointer",
                                background: "rgba(255,255,255,0.92)", boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
                                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15,
                              }}
                            >
                              ✎
                            </button>
                          </div>
                        );
                      })()}
                      {/* 6. Sections */}
                      {draft.sections.map((section, idx) => (
                        <section key={`prev-${section.h2}-${idx}`} style={{ marginBottom: 28 }}>
                          <h2 style={{ fontSize: 22, marginBottom: 10 }}>
                            {draft.numbered_steps ? `${idx + 1}. ${section.h2}` : section.h2}
                          </h2>
                          {section.direct_answer && (
                            <p
                              style={{ fontWeight: 600, marginBottom: 12 }}
                              dangerouslySetInnerHTML={{ __html: renderInlineMd(section.direct_answer) }}
                            />
                          )}
                          {section.image_url && (
                            <img
                              src={section.image_url}
                              alt={section.image_alt || section.h2 || ""}
                              style={{ maxWidth: "100%", borderRadius: 8, margin: "12px 0", display: "block" }}
                            />
                          )}
                          {section.body && (
                            <div dangerouslySetInnerHTML={{ __html: renderMd(section.body) }} />
                          )}
                        </section>
                      ))}
                      {/* Clearfix for float variants */}
                      {(draft.image_style === "float-left" || draft.image_style === "float-right") && (
                        <div style={{ clear: "both" }} />
                      )}
                      {/* CTA — mid position (after content, before FAQ) */}
                      {draft.cta_enabled && draft.cta_position === "mid" && draft.cta_label && draft.cta_url && (
                        <div style={{ margin: "32px 0", padding: 24, borderRadius: 12, background: "#F4F6F8", border: "1px solid #E1E3E5", textAlign: "center" }}>
                          {draft.cta_description && <p style={{ margin: "0 0 12px", color: "#374151" }}>{draft.cta_description}</p>}
                          <a href={draft.cta_url} style={{ display: "inline-block", padding: "12px 28px", borderRadius: 8, background: "#202223", color: "#fff", textDecoration: "none", fontWeight: 600 }}>
                            {draft.cta_label}
                          </a>
                        </div>
                      )}
                      {/* 7. FAQ block */}
                      {(draft.faq ?? []).filter((f) => f.q && f.a).length > 0 && (
                        <section style={{ marginTop: 32, borderTop: "1px solid #E5E7EB", paddingTop: 20 }}>
                          <h2 style={{ fontSize: 22, marginBottom: 16 }}>
                            {fr ? "Questions fréquentes" : "Frequently asked questions"}
                          </h2>
                          {(draft.faq ?? []).filter((f) => f.q && f.a).map((item, idx) => (
                            <div key={`prev-faq-${idx}`} style={{ marginBottom: 16 }}>
                              <h3 style={{ fontSize: 17, marginBottom: 4 }} dangerouslySetInnerHTML={{ __html: renderInlineMd(item.q) }} />
                              <p style={{ color: "#374151" }} dangerouslySetInnerHTML={{ __html: renderInlineMd(item.a) }} />
                            </div>
                          ))}
                        </section>
                      )}
                      {/* 8. Author bio */}
                      {(draft.author_bio ?? "").trim() && (
                        <aside style={{ marginTop: 32, background: "#F9FAFB", border: "1px solid #E5E7EB", borderRadius: 8, padding: "16px 20px" }}>
                          <h2 style={{ fontSize: 18, marginBottom: 6 }}>
                            {fr ? "À propos de l'auteur" : "About the author"}
                          </h2>
                          <p style={{ color: "#374151" }}>
                            {draft.author_name && <strong>{draft.author_name}<br /></strong>}
                            {draft.author_bio}
                          </p>
                        </aside>
                      )}
                      {/* CTA — end position (after author bio) */}
                      {draft.cta_enabled && draft.cta_position !== "mid" && draft.cta_label && draft.cta_url && (
                        <div style={{ margin: "32px 0", padding: 24, borderRadius: 12, background: "#F4F6F8", border: "1px solid #E1E3E5", textAlign: "center" }}>
                          {draft.cta_description && <p style={{ margin: "0 0 12px", color: "#374151" }}>{draft.cta_description}</p>}
                          <a href={draft.cta_url} style={{ display: "inline-block", padding: "12px 28px", borderRadius: 8, background: "#202223", color: "#fff", textDecoration: "none", fontWeight: 600 }}>
                            {draft.cta_label}
                          </a>
                        </div>
                      )}
                      {/* 9. Internal links */}
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
                    <CoverImageModal
                      locale={locale}
                      open={coverOpen}
                      imageUrl={draft.image_url ?? null}
                      imageAlt={draft.image_alt ?? null}
                      imageStyle={draft.image_style ?? "hero"}
                      styleOptions={coverStyleOptions}
                      onClose={() => setCoverOpen(false)}
                      onSelect={(url, alt) => setDraft((p) => p ? { ...p, image_url: url, image_alt: alt || p.image_alt } : p)}
                      onAltChange={(alt) => setDraft((p) => p ? { ...p, image_alt: alt } : p)}
                      onStyleChange={(v) => setDraft((p) => p ? { ...p, image_style: v as Draft["image_style"] } : p)}
                      onRemove={() => { setDraft((p) => p ? { ...p, image_url: "", image_alt: "" } : p); setCoverOpen(false); }}
                    />
                  </Box>
                )}
              </BlockStack>
            </Card>
          ) : inspirationIdeas.length > 0 ? (
            <BlockStack gap="400">
              <BlockStack gap="100">
                <Text as="h2" variant="headingLg">
                  {fr ? "Inspiration pour améliorer son référencement organique" : "Inspiration to improve your organic ranking"}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {fr
                    ? "Les meilleures idées d'articles à réaliser. Clique sur « Découvrir » pour voir le plan et générer l'article."
                    : "The best article ideas to create. Click \"Discover\" to see the outline and generate the article."}
                </Text>
              </BlockStack>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 32, alignItems: "stretch", width: "100%" }}>
                {inspirationIdeas.map((idea, i) => (
                  <div
                    key={`insp-${i}`}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      height: "100%",
                      background: "var(--p-color-bg-surface)",
                      border: "1px solid var(--p-color-border)",
                      borderRadius: 12,
                      padding: 16,
                    }}
                  >
                    <BlockStack gap="200">
                      {idea.source_label && (
                        <Badge tone={idea.angle === "competitor" ? "warning" : idea.angle === "seasonal" || idea.angle === "trend" ? "info" : "success"} size="small">
                          {idea.source_label}
                        </Badge>
                      )}
                      <Text as="h3" variant="headingMd">{idea.title || (fr ? "(sans titre)" : "(untitled)")}</Text>
                      {idea.product_title && (
                        <Text as="p" variant="bodySm" tone="subdued">{idea.product_title}</Text>
                      )}
                      {idea.intro && (
                        <BlockStack gap="050">
                          <Text as="p" variant="headingXs" tone="subdued">{fr ? "Introduction" : "Introduction"}</Text>
                          <Text as="p" variant="bodySm">{idea.intro}</Text>
                        </BlockStack>
                      )}
                    </BlockStack>
                    {/* Push the button to the bottom so it lines up across all cards. */}
                    <div style={{ marginTop: "auto", paddingTop: 16 }}>
                      <Button variant="primary" fullWidth onClick={() => selectIdea(idea)}>
                        {fr ? "Découvrir" : "Discover"}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </BlockStack>
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
        title={fr ? "Publier sur Shopify" : "Publish to Shopify"}
        primaryAction={{
          content: fr ? "Publier" : "Publish",
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
            <Divider />
            <Select
              label={fr ? "Auteur" : "Author"}
              options={[
                { label: fr ? "Marque (par défaut)" : "Brand (default)", value: "" },
                ...authors.map((a) => ({ label: a.name, value: a.id })),
              ]}
              value={selectedAuthorId}
              onChange={(id) => applyAuthor(authors.find((a) => a.id === id) ?? null)}
              helpText={fr
                ? "Sélectionne un auteur déjà créé. Sa bio renforce l'E-E-A-T (crédibilité Google)."
                : "Pick an author you already created. Their bio strengthens E-E-A-T."}
            />
            {selectedAuthorId && (() => {
              const a = authors.find((x) => x.id === selectedAuthorId);
              return a?.bio ? (
                <Text as="p" variant="bodySm" tone="subdued">{a.bio}</Text>
              ) : null;
            })()}
            {!newAuthorOpen ? (
              <InlineStack gap="200">
                <Button variant="plain" onClick={() => setNewAuthorOpen(true)}>
                  {fr ? "＋ Nouvel auteur" : "＋ New author"}
                </Button>
                {selectedAuthorId && (
                  <Button
                    variant="plain"
                    tone="critical"
                    onClick={() => authorsFetcher.submit({ intent: "deleteAuthor", id: selectedAuthorId }, { method: "post" })}
                  >
                    {fr ? "Supprimer cet auteur" : "Delete this author"}
                  </Button>
                )}
              </InlineStack>
            ) : (
              <Box padding="300" background="bg-surface-secondary" borderRadius="200" borderColor="border" borderWidth="025">
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm" fontWeight="semibold">{fr ? "Nouvel auteur" : "New author"}</Text>
                  <TextField
                    label={fr ? "Nom" : "Name"}
                    value={newAuthor.name}
                    onChange={(v) => setNewAuthor((p) => ({ ...p, name: v }))}
                    autoComplete="off"
                  />
                  <TextField
                    label={fr ? "Bio (E-E-A-T)" : "Bio (E-E-A-T)"}
                    value={newAuthor.bio}
                    onChange={(v) => setNewAuthor((p) => ({ ...p, bio: v }))}
                    multiline={3}
                    autoComplete="off"
                    helpText={fr ? "2-3 phrases sur l'expertise de l'auteur." : "2-3 sentences on the author's expertise."}
                  />
                  <TextField
                    label={fr ? "URL profil (optionnel)" : "Profile URL (optional)"}
                    value={newAuthor.url}
                    onChange={(v) => setNewAuthor((p) => ({ ...p, url: v }))}
                    autoComplete="off"
                  />
                  <InlineStack gap="200">
                    <Button onClick={onCreateAuthor} loading={authorsFetcher.state !== "idle"} disabled={!newAuthor.name.trim()}>
                      {fr ? "Créer" : "Create"}
                    </Button>
                    <Button variant="plain" onClick={() => setNewAuthorOpen(false)}>
                      {fr ? "Annuler" : "Cancel"}
                    </Button>
                  </InlineStack>
                </BlockStack>
              </Box>
            )}
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
    </>
  );
}
