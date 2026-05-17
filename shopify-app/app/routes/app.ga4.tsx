import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
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

interface GA4Status {
  ga4_property_id_set: boolean;
  credentials_file_set: boolean;
  ready: boolean;
}

interface FunnelSummary {
  urls_total: number;
  urls_with_ga4_data: number;
  total_impressions: number;
  total_clicks: number;
  total_sessions: number;
  total_conversions: number;
  total_revenue: number;
  avg_position: number;
  overall_conversion_rate: number;
  overall_session_rate: number;
}

interface FunnelRow {
  url: string;
  path: string;
  impressions: number;
  clicks: number;
  ctr: number;
  position: number;
  sessions: number;
  conversions: number;
  revenue: number;
  has_ga4_data: boolean;
}

interface FunnelData {
  shop: string;
  days: number;
  summary: FunnelSummary;
  by_url: FunnelRow[];
}

interface ImpactRow {
  url: string;
  title: string;
  resource_type: string;
  impressions: number;
  position_before: number;
  position_after: number;
  clicks_gained: number;
  revenue_estimate: number;
  changes: { field: string; applied_at: string }[];
}

interface ImpactData {
  urls: ImpactRow[];
  total_clicks_gained: number;
  total_revenue_estimate: number;
  meta: { shop: string; days: number; gsc_data_available: boolean };
}

interface LoaderData {
  locale: Locale;
  status: GA4Status | null;
  funnel: FunnelData | null;
  funnelError: string | null;
  impact: ImpactData | null;
}

// ---------------------------------------------------------------------------
// Loader — parallel fetches
// ---------------------------------------------------------------------------

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const fetch = (path: string) =>
    callBackendForShop(shop, path, { accessToken: session.accessToken });

  const [statusResp, funnelResp, impactResp] = await Promise.allSettled([
    fetch(`/api/shops/${shop}/ga4/status`),
    fetch(`/api/shops/${shop}/ga4/funnel?days=30`),
    fetch(`/api/shops/${shop}/impact?days=30`),
  ]);

  const status =
    statusResp.status === "fulfilled" && statusResp.value.ok
      ? ((await statusResp.value.json()) as GA4Status)
      : null;

  let funnel: FunnelData | null = null;
  let funnelError: string | null = null;
  if (funnelResp.status === "fulfilled") {
    if (funnelResp.value.ok) {
      funnel = (await funnelResp.value.json()) as FunnelData;
    } else {
      funnelError = `${funnelResp.value.status}`;
    }
  } else {
    funnelError = funnelResp.reason?.message ?? "Erreur réseau";
  }

  const impact =
    impactResp.status === "fulfilled" && impactResp.value.ok
      ? ((await impactResp.value.json()) as ImpactData)
      : null;

  return json<LoaderData>({ locale, status, funnel, funnelError, impact });
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: number, decimals = 0): string {
  return n.toLocaleString("fr-FR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function pct(n: number): string {
  return `${(n * 100).toFixed(1)} %`;
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card>
      <BlockStack gap="100">
        <Text as="p" variant="headingLg">{value}</Text>
        <Text as="p" variant="bodySm" tone="subdued">{label}</Text>
        {sub && <Text as="p" variant="bodySm" tone="subdued">{sub}</Text>}
      </BlockStack>
    </Card>
  );
}

function ConfigGuide({ status }: { status: GA4Status }) {
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <Text as="h2" variant="headingMd">Configuration GA4</Text>
          <Badge tone="warning">Non connecté</Badge>
        </InlineStack>
        <BlockStack gap="100">
          {!status.ga4_property_id_set && (
            <Text as="p" variant="bodySm" tone="critical">
              ✗ Variable <code>GA4_PROPERTY_ID</code> manquante (ex : <code>123456789</code>)
            </Text>
          )}
          {status.ga4_property_id_set && (
            <Text as="p" variant="bodySm" tone="success">✓ GA4_PROPERTY_ID configuré</Text>
          )}
          {!status.credentials_file_set && (
            <Text as="p" variant="bodySm" tone="critical">
              ✗ Variable <code>GOOGLE_APPLICATION_CREDENTIALS</code> manquante (chemin vers le fichier JSON du compte de service)
            </Text>
          )}
          {status.credentials_file_set && (
            <Text as="p" variant="bodySm" tone="success">✓ Credentials fichier configuré</Text>
          )}
        </BlockStack>
        <Button size="slim" variant="plain" onClick={() => setOpen((v) => !v)}>
          {open ? "Masquer les instructions" : "Voir les instructions de configuration"}
        </Button>
        {open && (
          <Box background="bg-surface-secondary" padding="300" borderRadius="200">
            <BlockStack gap="200">
              <Text as="p" variant="bodyMd" fontWeight="semibold">Étapes de configuration</Text>
              <Text as="p" variant="bodySm">
                1. Dans Google Cloud Console, créez un compte de service avec le rôle{" "}
                <strong>Viewer</strong> sur la propriété GA4.
              </Text>
              <Text as="p" variant="bodySm">
                2. Téléchargez le fichier JSON de clé du compte de service.
              </Text>
              <Text as="p" variant="bodySm">
                3. Définissez les variables d'environnement dans votre fichier <code>.env</code> :
              </Text>
              <pre style={{ background: "#f4f6f8", padding: "8px", borderRadius: 4, fontSize: 12 }}>
                {`GA4_PROPERTY_ID=123456789\nGOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`}
              </pre>
              <Text as="p" variant="bodySm">
                4. Redémarrez le backend. Le statut passera à « Connecté » automatiquement.
              </Text>
            </BlockStack>
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function GA4Dashboard() {
  const { locale, status, funnel, funnelError, impact } = useLoaderData<typeof loader>();

  const topUrls = (funnel?.by_url ?? [])
    .sort((a, b) => b.revenue - a.revenue || b.sessions - a.sessions)
    .slice(0, 20);

  const topImpact = (impact?.urls ?? [])
    .sort((a, b) => b.revenue_estimate - a.revenue_estimate)
    .slice(0, 15);

  return (
    <Page
      title="Dashboard GA4 & Impact"
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
    >
      <BlockStack gap="400">

        {/* Status / config guide */}
        {status && !status.ready && <ConfigGuide status={status} />}
        {status?.ready && (
          <Banner tone="success">
            <Text as="p" variant="bodySm">GA4 connecté — données des 30 derniers jours.</Text>
          </Banner>
        )}
        {!status && (
          <Banner tone="warning">
            <Text as="p">Impossible de vérifier le statut GA4.</Text>
          </Banner>
        )}

        {/* Funnel error */}
        {funnelError && status?.ready && (
          <Banner tone="info">
            <Text as="p" variant="bodySm">
              {funnelError === "404"
                ? "Pas de données GSC disponibles. Lancez « leonie-seo audit gsc » d'abord."
                : `Funnel GA4 indisponible (${funnelError}).`}
            </Text>
          </Banner>
        )}

        {/* KPI summary */}
        {funnel && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">Funnel organique — 30 jours</Text>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 12 }}>
                <KpiCard label="Impressions" value={fmt(funnel.summary.total_impressions)} />
                <KpiCard label="Clics" value={fmt(funnel.summary.total_clicks)} />
                <KpiCard label="Sessions" value={fmt(funnel.summary.total_sessions)}
                  sub={`Taux : ${pct(funnel.summary.overall_session_rate)}`} />
                <KpiCard label="Conversions" value={fmt(funnel.summary.total_conversions)}
                  sub={`Taux : ${pct(funnel.summary.overall_conversion_rate)}`} />
                <KpiCard label="Revenu organique" value={`${fmt(funnel.summary.total_revenue, 2)} €`} />
                <KpiCard label="Position moy." value={String(funnel.summary.avg_position)} />
              </div>
            </BlockStack>
          </Card>
        )}

        {/* Top URLs table */}
        {topUrls.length > 0 && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">Top URLs par revenu organique</Text>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #e1e3e5", textAlign: "left" }}>
                      <th style={{ padding: "8px 12px" }}>URL</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Impr.</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Clics</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Sessions</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Conv.</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Revenu</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Pos.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topUrls.map((row) => (
                      <tr key={row.url} style={{ borderBottom: "1px solid #f1f2f3" }}>
                        <td style={{ padding: "8px 12px", maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          <Text as="span" variant="bodySm">{row.path}</Text>
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>{fmt(row.impressions)}</td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>{fmt(row.clicks)}</td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>
                          {row.has_ga4_data ? fmt(row.sessions) : <Text as="span" tone="subdued">—</Text>}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>
                          {row.has_ga4_data ? fmt(row.conversions) : <Text as="span" tone="subdued">—</Text>}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>
                          {row.has_ga4_data ? `${fmt(row.revenue, 2)} €` : <Text as="span" tone="subdued">—</Text>}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>{row.position.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </BlockStack>
          </Card>
        )}

        {/* ROI by modified URL */}
        {topImpact.length > 0 && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">ROI estimé par URL modifiée</Text>
              <Text as="p" variant="bodySm" tone="subdued">
                Estimation basée sur le gain de position supposé (+2 pos.) appliqué aux impressions GSC.
                {!impact?.meta.gsc_data_available && " GSC non disponible — estimations non affichées."}
              </Text>
              {impact?.meta.gsc_data_available && (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid #e1e3e5", textAlign: "left" }}>
                        <th style={{ padding: "8px 12px" }}>Ressource</th>
                        <th style={{ padding: "8px 12px", textAlign: "right" }}>Impr. GSC</th>
                        <th style={{ padding: "8px 12px", textAlign: "right" }}>Pos. avant</th>
                        <th style={{ padding: "8px 12px", textAlign: "right" }}>Pos. après</th>
                        <th style={{ padding: "8px 12px", textAlign: "right" }}>Clics gagnés</th>
                        <th style={{ padding: "8px 12px", textAlign: "right" }}>Revenu estimé</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topImpact.map((row, i) => (
                        <tr key={i} style={{ borderBottom: "1px solid #f1f2f3" }}>
                          <td style={{ padding: "8px 12px" }}>
                            <Text as="span" variant="bodySm" fontWeight="semibold">{row.title}</Text>
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>{fmt(row.impressions)}</td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>{row.position_before.toFixed(1)}</td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>{row.position_after.toFixed(1)}</td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>{fmt(row.clicks_gained, 1)}</td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>{fmt(row.revenue_estimate, 2)} €</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <InlineStack gap="600">
                <BlockStack gap="050">
                  <Text as="p" variant="headingMd">{fmt(impact?.total_clicks_gained ?? 0, 1)}</Text>
                  <Text as="p" variant="bodySm" tone="subdued">Clics estimés gagnés</Text>
                </BlockStack>
                <BlockStack gap="050">
                  <Text as="p" variant="headingMd">{fmt(impact?.total_revenue_estimate ?? 0, 2)} €</Text>
                  <Text as="p" variant="bodySm" tone="subdued">Revenu estimé total</Text>
                </BlockStack>
              </InlineStack>
            </BlockStack>
          </Card>
        )}

        {!funnel && !impact && status?.ready && (
          <Card>
            <Text as="p" tone="subdued">
              Aucune donnée disponible. Lancez un audit SEO pour obtenir les données GSC et GA4.
            </Text>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
