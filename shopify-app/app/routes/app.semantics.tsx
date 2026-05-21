import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Card,
  InlineStack,
  Page,
  ProgressBar,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProductScore {
  id: string;
  handle: string;
  title: string;
  word_count: number;
  desc_grade: "missing" | "too_short" | "short" | "ok";
  content_score: number;
  eeat_global: number;
  experience_score: number;
  expertise_score: number;
  authority_score: number;
  trust_score: number;
  global_score: number;
  seo_issues: string[];
  missing_experience: string[];
  missing_expertise: string[];
  missing_authority: string[];
  missing_trust: string[];
  recommendations: string[];
}

interface Summary {
  avg_global_score: number;
  avg_eeat_score: number;
  products_needing_description: number;
  products_with_seo_issues: number;
  signal_note: string;
}

interface SemanticsData {
  shop: string;
  available: boolean;
  total: number;
  summary: Summary;
  products: ProductScore[];
}

interface LoaderData {
  locale: Locale;
  data: SemanticsData | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(
      shop,
      `/api/shops/${shop}/audit/semantics?top=100`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, data: (await resp.json()) as SemanticsData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type SortKey = "global_score" | "eeat_global" | "word_count";

function pct(n: number): string {
  return `${Math.round(n * 100)} %`;
}

function scoreTone(n: number): "success" | "primary" | "critical" {
  if (n >= 0.6) return "success";
  if (n >= 0.35) return "primary";
  return "critical";
}

function ScoreBar({ value, label }: { value: number; label: string }) {
  return (
    <BlockStack gap="050">
      <InlineStack align="space-between">
        <Text as="span" variant="bodySm" tone="subdued">{label}</Text>
        <Text as="span" variant="bodySm" fontWeight="semibold" tone={value >= 0.6 ? "success" : value >= 0.35 ? undefined : "critical"}>
          {pct(value)}
        </Text>
      </InlineStack>
      <ProgressBar
        progress={Math.min(value * 100, 100)}
        size="small"
        tone={scoreTone(value)}
      />
    </BlockStack>
  );
}

function descGradeBadge(grade: ProductScore["desc_grade"]) {
  const map: Record<string, { tone: "critical" | "warning" | "success" | "info"; label: string }> = {
    missing: { tone: "critical", label: "Description absente" },
    too_short: { tone: "warning", label: "Trop courte" },
    short: { tone: "info", label: "Courte" },
    ok: { tone: "success", label: "OK" },
  };
  const { tone, label } = map[grade] ?? { tone: "info", label: grade };
  return <Badge tone={tone}>{label}</Badge>;
}

function ProductRow({ p, expanded, onToggle }: { p: ProductScore; expanded: boolean; onToggle: () => void }) {
  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="p" variant="bodyMd" fontWeight="semibold">{p.title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">/{p.handle} · {p.word_count} mots</Text>
          </BlockStack>
          <InlineStack gap="200">
            {descGradeBadge(p.desc_grade)}
            <Badge tone={p.global_score >= 0.6 ? "success" : p.global_score >= 0.35 ? "warning" : "critical"}>
              {`Score : ${pct(p.global_score)}`}
            </Badge>
          </InlineStack>
        </InlineStack>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
          <ScoreBar value={p.eeat_global} label="E-E-A-T global" />
          <ScoreBar value={p.content_score} label="Richesse contenu" />
          <ScoreBar value={p.expertise_score} label="Expertise" />
          <ScoreBar value={p.trust_score} label="Confiance" />
        </div>

        {p.recommendations.length > 0 && (
          <BlockStack gap="050">
            {p.recommendations.map((r, i) => (
              <Text key={i} as="p" variant="bodySm" tone="caution">{`→ ${r}`}</Text>
            ))}
          </BlockStack>
        )}

        {expanded && (
          <BlockStack gap="200">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
              <ScoreBar value={p.experience_score} label="Expérience" />
              <ScoreBar value={p.authority_score} label="Autorité" />
            </div>
            {p.seo_issues.length > 0 && (
              <InlineStack gap="100" wrap>
                {p.seo_issues.map((issue) => (
                  <Badge key={issue} tone="critical">{issue.replace(/_/g, " ")}</Badge>
                ))}
              </InlineStack>
            )}
            {(p.missing_trust.length > 0 || p.missing_expertise.length > 0) && (
              <BlockStack gap="050">
                {p.missing_trust.length > 0 && (
                  <Text as="p" variant="bodySm" tone="subdued">
                    {`Signaux confiance manquants : ${p.missing_trust.join(", ")}`}
                  </Text>
                )}
                {p.missing_expertise.length > 0 && (
                  <Text as="p" variant="bodySm" tone="subdued">
                    {`Signaux expertise manquants : ${p.missing_expertise.join(", ")}`}
                  </Text>
                )}
              </BlockStack>
            )}
          </BlockStack>
        )}

        <button
          onClick={onToggle}
          style={{ background: "none", border: "none", cursor: "pointer", padding: 0, textAlign: "left" }}
        >
          <Text as="span" variant="bodySm" tone="subdued">
            {expanded ? "▲ Masquer le détail" : "▼ Voir le détail E-E-A-T"}
          </Text>
        </button>
      </BlockStack>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Semantics() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const [sortKey, setSortKey] = useState<SortKey>("global_score");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const sorted = [...(data?.products ?? [])].sort((a, b) =>
    sortKey === "word_count" ? a[sortKey] - b[sortKey] : a[sortKey] - b[sortKey],
  );

  const sortButtons: { key: SortKey; label: string }[] = [
    { key: "global_score", label: "Score global" },
    { key: "eeat_global", label: "E-E-A-T" },
    { key: "word_count", label: "Longueur desc." },
  ];

  return (
    <Page
      title="Analyse sémantique & E-E-A-T"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">Score contenu & E-E-A-T par produit</Text>
            <Text as="p" tone="subdued" variant="bodySm">
              Chaque produit est scoré sur la richesse de sa description, ses signaux E-E-A-T
              (Expérience, Expertise, Autorité, Confiance) et la qualité de ses balises SEO.
              Les produits les moins bien scorés apparaissent en premier.
            </Text>
          </BlockStack>
        </Card>

        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {/* Summary */}
        {data && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">Synthèse</Text>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
                {[
                  { label: "Score moyen", value: pct(data.summary.avg_global_score) },
                  { label: "E-E-A-T moyen", value: pct(data.summary.avg_eeat_score) },
                  { label: "Descriptions à enrichir", value: String(data.summary.products_needing_description) },
                  { label: "Problèmes SEO", value: String(data.summary.products_with_seo_issues) },
                ].map(({ label, value }) => (
                  <Card key={label}>
                    <BlockStack gap="050">
                      <Text as="p" variant="headingMd">{value}</Text>
                      <Text as="p" variant="bodySm" tone="subdued">{label}</Text>
                    </BlockStack>
                  </Card>
                ))}
              </div>
              <Text as="p" variant="bodySm" tone="subdued">{data.summary.signal_note}</Text>
            </BlockStack>
          </Card>
        )}

        {/* Sort controls + product list */}
        {data && sorted.length > 0 && (
          <BlockStack gap="300">
            <InlineStack gap="200">
              <Text as="p" variant="bodySm" tone="subdued">Trier par :</Text>
              {sortButtons.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setSortKey(key)}
                  style={{
                    background: sortKey === key ? "var(--p-color-bg-surface-secondary)" : "none",
                    border: "1px solid var(--p-color-border)",
                    borderRadius: 4,
                    cursor: "pointer",
                    padding: "4px 10px",
                    fontSize: 13,
                    fontWeight: sortKey === key ? "bold" : "normal",
                  }}
                >
                  {label}
                </button>
              ))}
            </InlineStack>

            {sorted.map((p) => (
              <ProductRow
                key={p.id}
                p={p}
                expanded={expandedId === p.id}
                onToggle={() => setExpandedId(expandedId === p.id ? null : p.id)}
              />
            ))}
          </BlockStack>
        )}

        {data && data.total === 0 && (
          <Card>
            <Text as="p" tone="subdued">{t(locale, "noData")}</Text>
          </Card>
        )}

        {!data && !error && (
          <Card>
            <Text as="p" tone="subdued">Chargement…</Text>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
