import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import { useState } from "react";
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

interface RedirectRow {
  from_path: string;
  to_path: string;
}

interface ApplyResultRow {
  from_path: string;
  to_path: string;
  status: "preview" | "applied" | "error";
  detail?: string;
}

interface ApplyResponse {
  dry_run: boolean;
  total_submitted: number;
  total_valid: number;
  warnings: string[];
  results: ApplyResultRow[];
  applied: number;
  errors: number;
}

interface LoaderData {
  locale: Locale;
}

// ---------------------------------------------------------------------------
// Loader (minimal — page is fully interactive)
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return json<LoaderData>({ locale: getLocale(request) });
};

// ---------------------------------------------------------------------------
// Action
// ---------------------------------------------------------------------------

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const body = await request.json();
  const endpoint = body._validate
    ? `/api/shops/${shop}/audit/redirects/validate`
    : `/api/shops/${shop}/audit/redirects/apply`;

  const { _validate, ...payload } = body;

  const resp = await callBackendForShop(shop, endpoint, {
    method: "POST",
    accessToken: session.accessToken,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });

  const data = await resp.json();
  return json(data, { status: resp.ok ? 200 : resp.status });
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const EMPTY_ROW: RedirectRow = { from_path: "", to_path: "" };

function isValidPath(p: string) {
  return p.startsWith("/") || p.startsWith("https://");
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Redirects() {
  const { locale } = useLoaderData<typeof loader>();
  const fetcher = useFetcher<ApplyResponse>();

  const [rows, setRows] = useState<RedirectRow[]>([{ ...EMPTY_ROW }]);
  const [showConfirm, setShowConfirm] = useState(false);

  const addRow = () => setRows((prev) => [...prev, { ...EMPTY_ROW }]);
  const removeRow = (idx: number) =>
    setRows((prev) => prev.filter((_, i) => i !== idx));
  const updateRow = (idx: number, field: keyof RedirectRow, value: string) =>
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));

  const validItems = rows.filter((r) => r.from_path.startsWith("/") && isValidPath(r.to_path));
  const isSubmitting = fetcher.state !== "idle";

  const buildPayload = (dryRun: boolean, validate = false, confirmLive = false) => ({
    _validate: validate,
    items: rows
      .filter((r) => r.from_path && r.to_path)
      .map((r) => ({ from_path: r.from_path, to_path: r.to_path })),
    dry_run: dryRun,
    confirm_live_write: confirmLive,
  });

  const handleValidate = () =>
    fetcher.submit(buildPayload(true, true), { method: "POST", encType: "application/json" });
  const handlePreview = () =>
    fetcher.submit(buildPayload(true), { method: "POST", encType: "application/json" });
  const handleApply = () => {
    fetcher.submit(buildPayload(false, false, true), { method: "POST", encType: "application/json" });
    setShowConfirm(false);
  };

  const resp = fetcher.data;
  const resultMap = Object.fromEntries(
    (resp?.results ?? []).map((r) => [r.from_path, r])
  );

  return (
    <Page
      title="Redirections 301"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        {/* Explainer */}
        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">Créer des redirections</Text>
            <Text as="p" tone="subdued" variant="bodySm">
              Saisissez les chemins source (chemin existant à rediriger) et destination. Les redirections
              sont validées avant toute écriture. Utilisez « Prévisualiser » pour vérifier sans risque.
            </Text>
          </BlockStack>
        </Card>

        {/* Result banner */}
        {resp && (
          <Banner
            tone={
              resp.errors > 0 ? "warning" : resp.dry_run ? "info" : "success"
            }
          >
            <BlockStack gap="100">
              <Text as="p">
                {resp.dry_run
                  ? `Prévisualisation : ${resp.total_valid}/${resp.total_submitted} redirections valides.`
                  : `Appliqué : ${resp.applied} succès · ${resp.errors} erreur(s).`}
              </Text>
              {resp.warnings.length > 0 && (
                <BlockStack gap="050">
                  {resp.warnings.map((w, i) => (
                    <Text key={i} as="p" variant="bodySm" tone="caution">
                      {`⚠ ${w}`}
                    </Text>
                  ))}
                </BlockStack>
              )}
            </BlockStack>
          </Banner>
        )}

        {/* Redirect editor */}
        <Card>
          <BlockStack gap="400">
            <InlineStack align="space-between">
              <Text as="h2" variant="headingMd">
                {`Redirections (${rows.length})`}
              </Text>
              <Button size="slim" onClick={addRow}>
                + Ajouter une ligne
              </Button>
            </InlineStack>

            <BlockStack gap="300">
              {rows.map((row, idx) => {
                const result = resultMap[row.from_path];
                const fromError =
                  row.from_path && !row.from_path.startsWith("/")
                    ? "Doit commencer par /"
                    : undefined;
                const toError =
                  row.to_path && !isValidPath(row.to_path)
                    ? "Doit commencer par / ou https://"
                    : undefined;

                return (
                  <BlockStack key={idx} gap="100">
                    <InlineStack gap="200" blockAlign="start" wrap>
                      <div style={{ flex: 1, minWidth: 180 }}>
                        <TextField
                          label={idx === 0 ? "Chemin source (from)" : ""}
                          labelHidden={idx > 0}
                          value={row.from_path}
                          onChange={(v) => updateRow(idx, "from_path", v)}
                          placeholder="/ancien-produit"
                          autoComplete="off"
                          error={fromError}
                          connectedRight={
                            <Text as="span" tone="subdued">→</Text>
                          }
                        />
                      </div>
                      <div style={{ flex: 1, minWidth: 180 }}>
                        <TextField
                          label={idx === 0 ? "Destination (to)" : ""}
                          labelHidden={idx > 0}
                          value={row.to_path}
                          onChange={(v) => updateRow(idx, "to_path", v)}
                          placeholder="/products/nouveau-produit"
                          autoComplete="off"
                          error={toError}
                        />
                      </div>
                      <div style={{ paddingTop: idx === 0 ? 24 : 0 }}>
                        <Button
                          size="slim"
                          tone="critical"
                          onClick={() => removeRow(idx)}
                          disabled={rows.length === 1}
                        >
                          ✕
                        </Button>
                      </div>
                    </InlineStack>

                    {result && (
                      <InlineStack gap="100">
                        <Badge
                          tone={
                            result.status === "applied"
                              ? "success"
                              : result.status === "error"
                              ? "critical"
                              : "info"
                          }
                        >
                          {result.status === "preview"
                            ? "À créer"
                            : result.status === "applied"
                            ? "Créé"
                            : "Erreur"}
                        </Badge>
                        {result.status === "error" && (
                          <Text as="span" tone="critical" variant="bodySm">
                            {result.detail}
                          </Text>
                        )}
                      </InlineStack>
                    )}
                  </BlockStack>
                );
              })}
            </BlockStack>

            {/* Actions */}
            <InlineStack gap="300" align="end">
              <Button
                onClick={handleValidate}
                disabled={validItems.length === 0 || isSubmitting}
                loading={isSubmitting}
              >
                Valider
              </Button>
              <Button
                onClick={handlePreview}
                disabled={validItems.length === 0 || isSubmitting}
              >
                Prévisualiser
              </Button>
              {!showConfirm ? (
                <Button
                  tone="critical"
                  disabled={validItems.length === 0 || isSubmitting}
                  onClick={() => setShowConfirm(true)}
                >
                  {`Appliquer (${validItems.length})`}
                </Button>
              ) : (
                <InlineStack gap="200">
                  <Text as="span" tone="critical" variant="bodySm">
                    Créera des redirections sur Shopify. Confirmer ?
                  </Text>
                  <Button tone="critical" onClick={handleApply} loading={isSubmitting}>
                    Oui, créer
                  </Button>
                  <Button onClick={() => setShowConfirm(false)}>Annuler</Button>
                </InlineStack>
              )}
            </InlineStack>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
