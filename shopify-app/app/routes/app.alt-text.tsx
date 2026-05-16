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
  Thumbnail,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AltRow {
  product_id: string;
  product_name: string;
  image_id: string;
  image_url: string;
  old_alt: string | null;
  suggested_alt: string;
  char_count: number;
  quality_ok: boolean;
}

interface AltData {
  available: boolean;
  total: number;
  quality_issues: number;
  rows: AltRow[];
}

interface LoaderData {
  locale: Locale;
  data: AltData | null;
  error: string | null;
}

interface ApplyResult {
  image_id: string;
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

  let data: AltData | null = null;
  let error: string | null = null;

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/audit/alt-text`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) {
      data = (await resp.json()) as AltData;
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
// Action (dry-run preview + live apply)
// ---------------------------------------------------------------------------

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const body = await request.json();

  const resp = await callBackendForShop(
    shop,
    `/api/shops/${shop}/audit/alt-text/apply`,
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
// Component
// ---------------------------------------------------------------------------

export default function AltText() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const fetcher = useFetcher<ApplyResponse>();

  // Local edits: {[image_id]: string}
  const [edits, setEdits] = useState<Record<string, string>>({});
  // Approved set
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const [showConfirm, setShowConfirm] = useState(false);

  const rows = data?.rows ?? [];

  useEffect(() => {
    if (rows.length > 0) {
      const initial: Record<string, string> = {};
      const allApproved = new Set<string>();
      for (const r of rows) {
        initial[r.image_id] = r.suggested_alt;
        allApproved.add(r.image_id);
      }
      setEdits(initial);
      setApproved(allApproved);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const buildPayload = (dryRun: boolean, confirmLive = false) => ({
    dry_run: dryRun,
    confirm_live_write: confirmLive,
    items: [...approved].map((imageId) => {
      const row = rows.find((r) => r.image_id === imageId)!;
      return {
        product_id: row.product_id,
        image_id: imageId,
        alt_text: edits[imageId] ?? row.suggested_alt,
      };
    }),
  });

  const handlePreview = () => {
    fetcher.submit(buildPayload(true), { method: "POST", encType: "application/json" });
  };

  const handleApply = () => {
    fetcher.submit(buildPayload(false, true), { method: "POST", encType: "application/json" });
    setShowConfirm(false);
  };

  const toggleApprove = (imageId: string) => {
    setApproved((prev) => {
      const next = new Set(prev);
      if (next.has(imageId)) next.delete(imageId);
      else next.add(imageId);
      return next;
    });
  };

  const resultMap = Object.fromEntries(
    (fetcher.data?.results ?? []).map((r) => [r.image_id, r])
  );

  const approvedCount = approved.size;
  const isSubmitting = fetcher.state !== "idle";

  return (
    <Page
      title="Alt text images"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        {/* Summary */}
        {data?.available && (
          <Card>
            <BlockStack gap="200">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">Images sans alt text</Text>
                <Badge tone={data.total === 0 ? "success" : "warning"}>
                  {`${data.total} à compléter`}
                </Badge>
              </InlineStack>
              {data.total === 0 && (
                <Text as="p" tone="subdued">
                  Toutes vos images ont déjà un texte alternatif. Rien à faire.
                </Text>
              )}
            </BlockStack>
          </Card>
        )}

        {/* Error */}
        {error && (
          <Card>
            <Text as="p" tone="subdued">{error}</Text>
          </Card>
        )}

        {/* Apply result banner */}
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
              ? `Prévisualisation : ${fetcher.data.total} alt text(s) seraient mis à jour.`
              : `Appliqué : ${fetcher.data.applied ?? 0} succès · ${fetcher.data.errors ?? 0} erreur(s).`}
          </Banner>
        )}

        {/* List */}
        {data && rows.length > 0 && (
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">
                  {`Suggestions (${approvedCount} approuvée(s) sur ${rows.length})`}
                </Text>
                <InlineStack gap="200">
                  <Button size="slim" onClick={() => setApproved(new Set(rows.map((r) => r.image_id)))}>
                    Tout approuver
                  </Button>
                  <Button size="slim" onClick={() => setApproved(new Set())}>
                    Tout rejeter
                  </Button>
                </InlineStack>
              </InlineStack>

              <BlockStack gap="400">
                {rows.map((row, idx) => {
                  const isApproved = approved.has(row.image_id);
                  const currentAlt = edits[row.image_id] ?? row.suggested_alt;
                  const charCount = currentAlt.length;
                  const result = resultMap[row.image_id];

                  return (
                    <BlockStack key={row.image_id} gap="200">
                      <InlineStack align="space-between" wrap>
                        <InlineStack gap="300" wrap>
                          {row.image_url && (
                            <Thumbnail
                              source={row.image_url}
                              alt={row.old_alt ?? ""}
                              size="small"
                            />
                          )}
                          <BlockStack gap="050">
                            <Text as="p" fontWeight="semibold">{row.product_name}</Text>
                            {row.old_alt ? (
                              <Text as="p" tone="subdued" variant="bodySm">
                                {`Actuel : "${row.old_alt}"`}
                              </Text>
                            ) : (
                              <Text as="p" tone="critical" variant="bodySm">Aucun alt text</Text>
                            )}
                          </BlockStack>
                        </InlineStack>
                        <Button
                          size="slim"
                          pressed={isApproved}
                          tone={isApproved ? "success" : undefined}
                          onClick={() => toggleApprove(row.image_id)}
                        >
                          {isApproved ? "Approuvé" : "Rejeter"}
                        </Button>
                      </InlineStack>

                      {isApproved && (
                        <BlockStack gap="100">
                          <TextField
                            label="Alt text suggéré (modifiable)"
                            value={currentAlt}
                            onChange={(v) => setEdits((prev) => ({ ...prev, [row.image_id]: v }))}
                            maxLength={125}
                            showCharacterCount
                            autoComplete="off"
                            error={
                              charCount > 125
                                ? "Trop long (max 125 caractères)"
                                : !row.quality_ok && currentAlt === row.suggested_alt
                                ? "Vérifiez : ne pas commencer par « image », « photo »…"
                                : undefined
                            }
                          />
                          {result && (
                            <Text
                              as="p"
                              tone={result.status === "error" ? "critical" : "success"}
                              variant="bodySm"
                            >
                              {result.status === "preview"
                                ? `✓ ${result.detail}`
                                : result.status === "applied"
                                ? "✓ Appliqué sur Shopify"
                                : `✗ Erreur : ${result.detail}`}
                            </Text>
                          )}
                        </BlockStack>
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
                  loading={isSubmitting && fetcher.formData !== undefined}
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
