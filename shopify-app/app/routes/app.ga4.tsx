import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useActionData, useFetcher, useLoaderData } from "@remix-run/react";
import { useEffect, useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  InlineStack,
  Page,
  Select,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GA4Status {
  oauth_connected: boolean;
  oauth_configured: boolean;
  email: string | null;
  property_id: string | null;
  property_name: string | null;
  ready: boolean;
  // legacy fields
  ga4_property_id_set: boolean;
  credentials_file_set: boolean;
}

interface GA4Property {
  property_id: string;
  property_name: string;
  account_name: string;
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
  shop: string;
  locale: Locale;
  status: GA4Status | null;
  funnel: FunnelData | null;
  funnelError: string | null;
  impact: ImpactData | null;
}

interface ActionData {
  authorization_url?: string;
  properties?: GA4Property[];
  saved?: boolean;
  disconnected?: boolean;
  error?: string;
  intent?: string;
}

// ---------------------------------------------------------------------------
// Loader
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

  return json<LoaderData>({ shop, locale, status, funnel, funnelError, impact });
};

// ---------------------------------------------------------------------------
// Action — OAuth connect / property selection / disconnect
// ---------------------------------------------------------------------------

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const formData = await request.formData();
  const intent = formData.get("intent") as string;

  if (intent === "connect") {
    const resp = await fetch(`${BACKEND}/api/shops/${shop}/ga4/authorize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: "Erreur réseau" }));
      return json<ActionData>({ error: err.detail ?? "Connexion impossible", intent });
    }
    const data = (await resp.json()) as { authorization_url: string };
    return json<ActionData>({ authorization_url: data.authorization_url, intent });
  }

  if (intent === "list_properties") {
    const resp = await fetch(`${BACKEND}/api/shops/${shop}/ga4/properties`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: "Erreur réseau" }));
      return json<ActionData>({ error: err.detail ?? "Impossible de lister les propriétés", intent });
    }
    const data = (await resp.json()) as { properties: GA4Property[] };
    return json<ActionData>({ properties: data.properties, intent });
  }

  if (intent === "save_property") {
    const property_id = formData.get("property_id") as string;
    const property_name = formData.get("property_name") as string;
    const resp = await fetch(`${BACKEND}/api/shops/${shop}/ga4/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ property_id, property_name }),
    });
    if (!resp.ok) {
      return json<ActionData>({ error: "Sauvegarde échouée", intent });
    }
    return json<ActionData>({ saved: true, intent });
  }

  if (intent === "disconnect") {
    await fetch(`${BACKEND}/api/shops/${shop}/ga4/disconnect`, { method: "DELETE" });
    return json<ActionData>({ disconnected: true, intent });
  }

  return json<ActionData>({ error: "Action inconnue", intent });
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: number, decimals = 0): string {
  return n.toLocaleString("fr-FR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function pct(n: number): string {
  return `${(n * 100).toFixed(1)} %`;
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card>
      <BlockStack gap="100">
        <Text as="p" variant="headingLg">
          {value}
        </Text>
        <Text as="p" variant="bodySm" tone="subdued">
          {label}
        </Text>
        {sub && (
          <Text as="p" variant="bodySm" tone="subdued">
            {sub}
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// OAuth connect panel
// ---------------------------------------------------------------------------

function ConnectPanel({
  status,
  actionData,
}: {
  status: GA4Status | null;
  actionData: ActionData | null;
}) {
  const fetcher = useFetcher<ActionData>();
  const [properties, setProperties] = useState<GA4Property[]>([]);
  const [selectedPropId, setSelectedPropId] = useState("");
  const [selectedPropName, setSelectedPropName] = useState("");

  const isConnected = status?.oauth_connected;
  const hasProperty = Boolean(status?.property_id);

  // When the authorization URL arrives, redirect the parent window to Google consent
  useEffect(() => {
    const url =
      (fetcher.data as ActionData | null)?.authorization_url ??
      actionData?.authorization_url;
    if (url) {
      (window.top ?? window).location.href = url;
    }
  }, [fetcher.data, actionData]);

  // When property list arrives, update state
  useEffect(() => {
    const props = (fetcher.data as ActionData | null)?.properties;
    if (props) {
      setProperties(props);
      if (props.length > 0) {
        setSelectedPropId(props[0].property_id);
        setSelectedPropName(props[0].property_name);
      }
    }
  }, [fetcher.data]);

  // Reload page after save/disconnect
  useEffect(() => {
    const data = fetcher.data as ActionData | null;
    if (data?.saved || data?.disconnected) {
      window.location.reload();
    }
  }, [fetcher.data]);

  if (!isConnected) {
    return (
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <Text as="h2" variant="headingMd">
              Google Analytics 4
            </Text>
            <Badge tone="warning">Non connecté</Badge>
          </InlineStack>
          <Text as="p" variant="bodySm" tone="subdued">
            Connectez votre compte Google pour accéder aux données de sessions, conversions et
            revenu organique de vos pages.
          </Text>
          {actionData?.error && (
            <Banner tone="critical">
              <Text as="p">{actionData.error}</Text>
            </Banner>
          )}
          {!status?.oauth_configured && (
            <Banner tone="warning">
              <Text as="p">
                Google OAuth non configuré côté serveur (variable{" "}
                <code>GOOGLE_OAUTH_CLIENT_CONFIG</code> manquante).
              </Text>
            </Banner>
          )}
          <fetcher.Form method="post">
            <input type="hidden" name="intent" value="connect" />
            <Button
              variant="primary"
              submit
              loading={fetcher.state !== "idle"}
              disabled={!status?.oauth_configured}
            >
              Connecter Google Analytics
            </Button>
          </fetcher.Form>
        </BlockStack>
      </Card>
    );
  }

  // Connected, but no property selected yet
  if (!hasProperty) {
    const propOptions = properties.map((p) => ({
      label: `${p.property_name} (${p.account_name}) — ID ${p.property_id}`,
      value: p.property_id,
    }));

    return (
      <Card>
        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center">
            <Text as="h2" variant="headingMd">
              Google Analytics 4
            </Text>
            <Badge tone="info">Connecté — propriété non choisie</Badge>
          </InlineStack>
          {status.email && (
            <Text as="p" variant="bodySm" tone="subdued">
              Compte : {status.email}
            </Text>
          )}
          <Text as="p" variant="bodySm">
            Choisissez la propriété GA4 à utiliser pour ce shop.
          </Text>

          {properties.length === 0 && (
            <fetcher.Form method="post">
              <input type="hidden" name="intent" value="list_properties" />
              <Button submit loading={fetcher.state !== "idle"}>
                Charger mes propriétés GA4
              </Button>
            </fetcher.Form>
          )}

          {properties.length > 0 && (
            <fetcher.Form method="post">
              <input type="hidden" name="intent" value="save_property" />
              <BlockStack gap="200">
                <Select
                  label="Propriété GA4"
                  options={propOptions}
                  value={selectedPropId}
                  onChange={(v) => {
                    setSelectedPropId(v);
                    setSelectedPropName(
                      properties.find((p) => p.property_id === v)?.property_name ?? ""
                    );
                  }}
                />
                <input type="hidden" name="property_id" value={selectedPropId} />
                <input type="hidden" name="property_name" value={selectedPropName} />
                <Button variant="primary" submit loading={fetcher.state !== "idle"}>
                  Enregistrer
                </Button>
              </BlockStack>
            </fetcher.Form>
          )}

          {(fetcher.data as ActionData | null)?.error && (
            <Banner tone="critical">
              <Text as="p">{(fetcher.data as ActionData).error}</Text>
            </Banner>
          )}
        </BlockStack>
      </Card>
    );
  }

  // Fully connected
  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack align="space-between" blockAlign="center">
          <Text as="h2" variant="headingMd">
            Google Analytics 4
          </Text>
          <Badge tone="success">Connecté</Badge>
        </InlineStack>
        <Text as="p" variant="bodySm" tone="subdued">
          {status.email && `Compte : ${status.email} — `}
          Propriété : {status.property_name || status.property_id}
        </Text>
        <fetcher.Form method="post">
          <input type="hidden" name="intent" value="disconnect" />
          <Button
            variant="plain"
            tone="critical"
            submit
            loading={fetcher.state !== "idle"}
          >
            Déconnecter
          </Button>
        </fetcher.Form>
      </BlockStack>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function GA4Dashboard() {
  const { locale, status, funnel, funnelError, impact } = useLoaderData<LoaderData>();
  const actionData = useActionData<ActionData>() ?? null;

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
        {/* OAuth connection panel */}
        <ConnectPanel status={status} actionData={actionData} />

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
              <Text as="h2" variant="headingMd">
                Funnel organique — 30 jours
              </Text>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                  gap: 12,
                }}
              >
                <KpiCard label="Impressions" value={fmt(funnel.summary.total_impressions)} />
                <KpiCard label="Clics" value={fmt(funnel.summary.total_clicks)} />
                <KpiCard
                  label="Sessions"
                  value={fmt(funnel.summary.total_sessions)}
                  sub={`Taux : ${pct(funnel.summary.overall_session_rate)}`}
                />
                <KpiCard
                  label="Conversions"
                  value={fmt(funnel.summary.total_conversions)}
                  sub={`Taux : ${pct(funnel.summary.overall_conversion_rate)}`}
                />
                <KpiCard
                  label="Revenu organique"
                  value={`${fmt(funnel.summary.total_revenue, 2)} €`}
                />
                <KpiCard label="Position moy." value={String(funnel.summary.avg_position)} />
              </div>
            </BlockStack>
          </Card>
        )}

        {/* Top URLs table */}
        {topUrls.length > 0 && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                Top URLs par revenu organique
              </Text>
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
                        <td
                          style={{
                            padding: "8px 12px",
                            maxWidth: 260,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          <Text as="span" variant="bodySm">
                            {row.path}
                          </Text>
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>
                          {fmt(row.impressions)}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>
                          {fmt(row.clicks)}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>
                          {row.has_ga4_data ? (
                            fmt(row.sessions)
                          ) : (
                            <Text as="span" tone="subdued">
                              —
                            </Text>
                          )}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>
                          {row.has_ga4_data ? (
                            fmt(row.conversions)
                          ) : (
                            <Text as="span" tone="subdued">
                              —
                            </Text>
                          )}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>
                          {row.has_ga4_data ? (
                            `${fmt(row.revenue, 2)} €`
                          ) : (
                            <Text as="span" tone="subdued">
                              —
                            </Text>
                          )}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>
                          {row.position.toFixed(1)}
                        </td>
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
              <Text as="h2" variant="headingMd">
                ROI estimé par URL modifiée
              </Text>
              <Text as="p" variant="bodySm" tone="subdued">
                Estimation basée sur le gain de position (+2 pos.) appliqué aux impressions GSC.
                {!impact?.meta.gsc_data_available &&
                  " GSC non disponible — estimations non affichées."}
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
                            <Text as="span" variant="bodySm" fontWeight="semibold">
                              {row.title}
                            </Text>
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>
                            {fmt(row.impressions)}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>
                            {row.position_before.toFixed(1)}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>
                            {row.position_after.toFixed(1)}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>
                            {fmt(row.clicks_gained, 1)}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>
                            {fmt(row.revenue_estimate, 2)} €
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <InlineStack gap="600">
                <BlockStack gap="050">
                  <Text as="p" variant="headingMd">
                    {fmt(impact?.total_clicks_gained ?? 0, 1)}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Clics estimés gagnés
                  </Text>
                </BlockStack>
                <BlockStack gap="050">
                  <Text as="p" variant="headingMd">
                    {fmt(impact?.total_revenue_estimate ?? 0, 2)} €
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Revenu estimé total
                  </Text>
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
