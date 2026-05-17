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
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChangeRow {
  id: number;
  applied_at: string;
  resource_type: string;
  resource_id: string;
  field: string;
  old_value: string | null;
  new_value: string;
  status: string;
  revertible: boolean;
}

interface HistoryData {
  shop: string;
  total: number;
  limit: number;
  offset: number;
  changes: ChangeRow[];
}

interface RevertResult {
  change_id: number;
  dry_run: boolean;
  status: "preview" | "reverted" | "error";
  detail?: string;
}

interface LoaderData {
  locale: Locale;
  history: HistoryData | null;
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
      `/api/shops/${shop}/rollback/history?limit=50`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, history: null, error: await resp.text() });
    }
    return json<LoaderData>({ locale, history: (await resp.json()) as HistoryData, error: null });
  } catch (err) {
    return json<LoaderData>({ locale, history: null, error: String(err) });
  }
};

// ---------------------------------------------------------------------------
// Action
// ---------------------------------------------------------------------------

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const body = await request.json();
  const { change_id, dry_run, confirm_live_write } = body as {
    change_id: number;
    dry_run: boolean;
    confirm_live_write: boolean;
  };

  const resp = await callBackendForShop(
    shop,
    `/api/shops/${shop}/rollback/${change_id}/revert`,
    {
      method: "POST",
      accessToken: session.accessToken,
      body: JSON.stringify({ dry_run, confirm_live_write }),
      headers: { "Content-Type": "application/json" },
    },
  );
  const data = await resp.json();
  return json(data, { status: resp.ok ? 200 : resp.status });
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fieldLabel(field: string): string {
  const labels: Record<string, string> = {
    "seo.title": "Méta title",
    "seo.description": "Méta description",
    "image.alt_text": "Alt text image",
    "description.body_html": "Description produit",
  };
  return labels[field] ?? field;
}

function statusBadge(status: string) {
  const tones: Record<string, "success" | "info" | "critical" | "warning"> = {
    applied: "success",
    reverted: "info",
    error: "critical",
  };
  return (
    <Badge tone={tones[status] ?? "warning"}>
      {status === "applied" ? "Appliqué" : status === "reverted" ? "Annulé" : status}
    </Badge>
  );
}

function truncate(s: string | null, max = 60): string {
  if (!s) return "—";
  return s.length > max ? s.slice(0, max) + "…" : s;
}

// ---------------------------------------------------------------------------
// Row component
// ---------------------------------------------------------------------------

function ChangeRowItem({ row }: { row: ChangeRow }) {
  const fetcher = useFetcher<RevertResult>();
  const [showConfirm, setShowConfirm] = useState(false);
  const isSubmitting = fetcher.state !== "idle";
  const result = fetcher.data;

  const handleRevert = (dryRun: boolean) => {
    fetcher.submit(
      { change_id: row.id, dry_run: dryRun, confirm_live_write: !dryRun },
      { method: "POST", encType: "application/json" },
    );
    setShowConfirm(false);
  };

  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack align="space-between" blockAlign="start" wrap>
          <BlockStack gap="050">
            <Text as="p" variant="bodyMd" fontWeight="semibold">
              {fieldLabel(row.field)}
            </Text>
            <Text as="p" variant="bodySm" tone="subdued">
              {row.resource_type} · {row.resource_id.split("/").pop()} ·{" "}
              {new Date(row.applied_at).toLocaleString("fr-FR")}
            </Text>
          </BlockStack>
          {statusBadge(row.status)}
        </InlineStack>

        <InlineStack gap="400">
          <BlockStack gap="050">
            <Text as="p" variant="bodySm" tone="subdued">Avant</Text>
            <Text as="p" variant="bodySm">{truncate(row.old_value)}</Text>
          </BlockStack>
          <Text as="span" tone="subdued">→</Text>
          <BlockStack gap="050">
            <Text as="p" variant="bodySm" tone="subdued">Après</Text>
            <Text as="p" variant="bodySm">{truncate(row.new_value)}</Text>
          </BlockStack>
        </InlineStack>

        {result && (
          <Banner tone={result.status === "reverted" ? "success" : result.status === "preview" ? "info" : "critical"}>
            <Text as="p" variant="bodySm">
              {result.status === "reverted"
                ? "Annulation appliquée avec succès."
                : result.status === "preview"
                ? `Prévisualisation : ${result.detail}`
                : `Erreur : ${result.detail}`}
            </Text>
          </Banner>
        )}

        {row.revertible && row.status === "applied" && !result && (
          <InlineStack gap="200">
            <Button size="slim" onClick={() => handleRevert(true)} loading={isSubmitting}>
              Prévisualiser l'annulation
            </Button>
            {!showConfirm ? (
              <Button size="slim" tone="critical" onClick={() => setShowConfirm(true)}>
                Annuler cette modification
              </Button>
            ) : (
              <InlineStack gap="200">
                <Text as="span" variant="bodySm" tone="critical">
                  Restaurera l'ancienne valeur sur Shopify. Confirmer ?
                </Text>
                <Button size="slim" tone="critical" onClick={() => handleRevert(false)} loading={isSubmitting}>
                  Oui, annuler
                </Button>
                <Button size="slim" onClick={() => setShowConfirm(false)}>Non</Button>
              </InlineStack>
            )}
          </InlineStack>
        )}
      </BlockStack>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Rollback() {
  const { locale, history, error } = useLoaderData<typeof loader>();

  return (
    <Page
      title="Historique & Rollback"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        <Card>
          <BlockStack gap="200">
            <Text as="h2" variant="headingMd">Historique des modifications Shopify</Text>
            <Text as="p" tone="subdued" variant="bodySm">
              Toutes les écritures appliquées via Léonie SEO. Les modifications annulables
              disposent d'un bouton de rollback avec confirmation.
            </Text>
          </BlockStack>
        </Card>

        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {history && history.total === 0 && (
          <Card>
            <Text as="p" tone="subdued">
              Aucune modification enregistrée. Les écritures Shopify apparaîtront ici après leur application.
            </Text>
          </Card>
        )}

        {history && history.changes.length > 0 && (
          <BlockStack gap="300">
            <Text as="p" tone="subdued" variant="bodySm">
              {`${history.total} modification(s) enregistrée(s)`}
            </Text>
            {history.changes.map((row) => (
              <ChangeRowItem key={row.id} row={row} />
            ))}
          </BlockStack>
        )}

        {!history && !error && (
          <Card>
            <Text as="p" tone="subdued">Chargement…</Text>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
