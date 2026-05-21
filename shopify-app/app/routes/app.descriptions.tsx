import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import { useEffect, useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  InlineStack,
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DescriptionRow {
  product_id: string;
  handle: string;
  title: string;
  category: string;
  old_description: string | null;
  suggested_description: string;
  word_count: number;
  quality_ok: boolean;
}

interface DescriptionData {
  available: boolean;
  total: number;
  quality_issues: number;
  rows: DescriptionRow[];
}

interface LoaderData {
  locale: Locale;
  data: DescriptionData | null;
  error: string | null;
}

interface ApplyResult {
  product_id: string;
  status: "preview" | "applied" | "error";
  detail?: string;
}

interface ApplyResponse {
  dry_run: boolean;
  total: number;
  applied?: number;
  errors?: number;
  results: ApplyResult[];
}

// ---------------------------------------------------------------------------
// Loader
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let data: DescriptionData | null = null;
  let error: string | null = null;

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/audit/descriptions`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) {
      data = (await resp.json()) as DescriptionData;
    } else if (resp.status === 404) {
      error = "Lancez un audit SEO pour générer le snapshot produit.";
    } else {
      error = `Erreur backend : ${resp.status}`;
    }
  } catch {
    error = t(locale, "backendOffline");
  }

  return json<LoaderData>({ locale, data, error });
};

// ---------------------------------------------------------------------------
// Action
// ---------------------------------------------------------------------------

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const body = await request.json();

  const resp = await callBackendForShop(
    shop,
    `/api/shops/${shop}/audit/descriptions/apply`,
    {
      method: "POST",
      accessToken: session.accessToken,
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json" },
    },
  );

  const data = await resp.json();
  return json(data, { status: resp.ok ? 200 : resp.status });
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  vetements_chien: "Vêtements chien",
  vetements_chat: "Vêtements chat",
  fontaines: "Fontaines",
  filtres: "Filtres",
  accessoires: "Accessoires",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Descriptions() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const fetcher = useFetcher<ApplyResponse>();

  const [edits, setEdits] = useState<Record<string, string>>({});
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const [showConfirm, setShowConfirm] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const rows = data?.rows ?? [];

  useEffect(() => {
    if (rows.length > 0) {
      const initial: Record<string, string> = {};
      const allApproved = new Set<string>();
      for (const r of rows) {
        initial[r.product_id] = r.suggested_description;
        allApproved.add(r.product_id);
      }
      setEdits(initial);
      setApproved(allApproved);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const buildPayload = (dryRun: boolean, confirmLive = false) => ({
    dry_run: dryRun,
    confirm_live_write: confirmLive,
    items: [...approved].map((pid) => ({
      product_id: pid,
      description: edits[pid] ?? rows.find((r) => r.product_id === pid)!.suggested_description,
    })),
  });

  const handlePreview = () =>
    fetcher.submit(buildPayload(true), { method: "POST", encType: "application/json" });

  const handleApply = () => {
    fetcher.submit(buildPayload(false, true), { method: "POST", encType: "application/json" });
    setShowConfirm(false);
  };

  const resultMap = Object.fromEntries(
    (fetcher.data?.results ?? []).map((r) => [r.product_id, r])
  );

  const approvedCount = approved.size;
  const isSubmitting = fetcher.state !== "idle";

  return (
    <Page
      title="Descriptions produits"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        {/* Summary */}
        {data?.available && (
          <Card>
            <InlineStack align="space-between">
              <Text as="h2" variant="headingMd">Suggestions de descriptions</Text>
              <Badge tone="info">{`${data.total} produit(s)`}</Badge>
            </InlineStack>
          </Card>
        )}

        {/* Error */}
        {error && (
          <Card>
            <Text as="p" tone="subdued">{error}</Text>
          </Card>
        )}

        {/* Apply result */}
        {fetcher.data && (
          <Banner
            tone={
              fetcher.data.dry_run
                ? "info"
                : (fetcher.data.errors ?? 0) > 0
                ? "warning"
                : "success"
            }
          >
            {fetcher.data.dry_run
              ? `Prévisualisation : ${fetcher.data.total} description(s) seraient mises à jour.`
              : `Appliqué : ${fetcher.data.applied ?? 0} succès · ${fetcher.data.errors ?? 0} erreur(s).`}
          </Banner>
        )}

        {/* List */}
        {data && rows.length > 0 && (
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">
                  {`Produits (${approvedCount} approuvé(s) sur ${rows.length})`}
                </Text>
                <InlineStack gap="200">
                  <Button size="slim" onClick={() => setApproved(new Set(rows.map((r) => r.product_id)))}>
                    Tout approuver
                  </Button>
                  <Button size="slim" onClick={() => setApproved(new Set())}>
                    Tout rejeter
                  </Button>
                </InlineStack>
              </InlineStack>

              <BlockStack gap="400">
                {rows.map((row, idx) => {
                  const isApproved = approved.has(row.product_id);
                  const isExpanded = expandedId === row.product_id;
                  const currentDesc = edits[row.product_id] ?? row.suggested_description;
                  const wordCount = currentDesc.split(/\s+/).filter(Boolean).length;
                  const result = resultMap[row.product_id];

                  return (
                    <BlockStack key={row.product_id} gap="200">
                      <InlineStack align="space-between" wrap>
                        <BlockStack gap="050">
                          <Text as="p" fontWeight="semibold">{row.title}</Text>
                          <InlineStack gap="200">
                            <Badge tone="info">
                              {CATEGORY_LABELS[row.category] ?? row.category}
                            </Badge>
                            <Text as="span" tone="subdued" variant="bodySm">
                              {`${wordCount} mots`}
                            </Text>
                            {!row.quality_ok && (
                              <Badge tone="warning">Hors plage</Badge>
                            )}
                          </InlineStack>
                        </BlockStack>
                        <InlineStack gap="200">
                          <Button
                            size="slim"
                            onClick={() => setExpandedId(isExpanded ? null : row.product_id)}
                          >
                            {isExpanded ? "Masquer" : "Éditer"}
                          </Button>
                          <Button
                            size="slim"
                            pressed={isApproved}
                            tone={isApproved ? "success" : undefined}
                            onClick={() =>
                              setApproved((prev) => {
                                const next = new Set(prev);
                                if (next.has(row.product_id)) next.delete(row.product_id);
                                else next.add(row.product_id);
                                return next;
                              })
                            }
                          >
                            {isApproved ? "Approuvé" : "Rejeter"}
                          </Button>
                        </InlineStack>
                      </InlineStack>

                      {isExpanded && (
                        <BlockStack gap="200">
                          {row.old_description && (
                            <BlockStack gap="100">
                              <Text as="p" variant="bodySm" tone="subdued" fontWeight="semibold">
                                Description actuelle
                              </Text>
                              <div
                                style={{
                                  padding: "8px 12px",
                                  background: "var(--p-color-bg-surface-secondary)",
                                  borderRadius: "var(--p-border-radius-200)",
                                  fontSize: "var(--p-font-size-300)",
                                  color: "var(--p-color-text-secondary)",
                                  whiteSpace: "pre-wrap",
                                }}
                              >
                                {row.old_description}
                              </div>
                            </BlockStack>
                          )}
                          <TextField
                            label="Nouvelle description (modifiable)"
                            value={currentDesc}
                            onChange={(v) =>
                              setEdits((prev) => ({ ...prev, [row.product_id]: v }))
                            }
                            multiline={6}
                            autoComplete="off"
                            helpText={`${wordCount} mots · min 50, max 400`}
                            error={
                              wordCount < 50
                                ? "Trop court (min 50 mots)"
                                : wordCount > 400
                                ? "Trop long (max 400 mots)"
                                : undefined
                            }
                          />
                        </BlockStack>
                      )}

                      {result && (
                        <Text
                          as="p"
                          tone={result.status === "error" ? "critical" : "success"}
                          variant="bodySm"
                        >
                          {result.status === "preview"
                            ? `✓ ${result.detail}`
                            : result.status === "applied"
                            ? "✓ Description mise à jour sur Shopify"
                            : `✗ Erreur : ${result.detail}`}
                        </Text>
                      )}

                      {idx < rows.length - 1 && (
                        <div style={{ borderTop: "1px solid var(--p-color-border)", marginTop: 4 }} />
                      )}
                    </BlockStack>
                  );
                })}
              </BlockStack>

              {/* Actions */}
              <InlineStack gap="300" align="end">
                <Button
                  onClick={handlePreview}
                  disabled={approvedCount === 0 || isSubmitting}
                  loading={isSubmitting}
                >
                  Prévisualiser (dry-run)
                </Button>
                {!showConfirm ? (
                  <Button
                    tone="critical"
                    disabled={approvedCount === 0 || isSubmitting}
                    onClick={() => setShowConfirm(true)}
                  >
                    {`Appliquer (${approvedCount})`}
                  </Button>
                ) : (
                  <InlineStack gap="200">
                    <Text as="span" tone="critical" variant="bodySm">
                      Écriture réelle sur Shopify. Confirmer ?
                    </Text>
                    <Button tone="critical" onClick={handleApply} loading={isSubmitting}>
                      Oui, appliquer
                    </Button>
                    <Button onClick={() => setShowConfirm(false)}>Annuler</Button>
                  </InlineStack>
                )}
              </InlineStack>
            </BlockStack>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
