import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
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

type TagStatus = "positive" | "neutral" | "negative" | "forced";

interface ImprovementTag {
  tag_id: string;
  label: string;
  tag_type: string;
  status: TagStatus;
  score: number;
  source: string;
  locked_by_merchant: boolean;
}

interface ImprovementElement {
  key: string;
  label: string;
  improved: boolean;
  status: "improved" | "not_improved";
}

interface ProductRow {
  product_id: string;
  product_title: string;
  product_handle: string;
  opportunity_score: number;
  tags: ImprovementTag[];
  elements: ImprovementElement[];
}

interface AgentEvent {
  id: number;
  created_at: string;
  event_type: string;
  resource_title: string;
  action_type: string;
  status: string;
  measurement_status: string;
  score_before: number | null;
  score_after: number | null;
  estimated_impact: Record<string, unknown>;
  observed_impact: Record<string, unknown> | null;
  notes: string | null;
}

interface AgentRun {
  id: number;
  created_at: string;
  mode: string;
  status: string;
  summary: Record<string, number | string | boolean>;
  proposals: Array<Record<string, unknown>>;
  errors: Array<Record<string, unknown>>;
}

interface TagHistoryItem {
  product_id: string;
  tag_id: string;
  label: string;
  status_before: string;
  status_after: string;
  window: string;
  reason: string;
  decided_at: string;
}

interface ContinuousImprovementData {
  shop: string;
  available: boolean;
  summary: {
    total_events: number;
    estimated_revenue: number;
    observed_revenue: number;
    products_tracked: number;
    tags_total: number;
    positive_tags: number;
    negative_tags: number;
    improved_elements: number;
    total_elements: number;
    measurement_note: string;
  };
  tag_breakdown: Array<{ tag_type: string; status: string; count: number }>;
  products: ProductRow[];
  events: AgentEvent[];
  agent_runs: AgentRun[];
  tag_history: TagHistoryItem[];
}

interface LoaderData {
  locale: Locale;
  data: ContinuousImprovementData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/geo/continuous-improvement?limit=100`,
      { accessToken: session.accessToken },
    );
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await resp.text() });
    }
    return json<LoaderData>({
      locale,
      data: (await resp.json()) as ContinuousImprovementData,
      error: null,
    });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

interface ActionResult {
  ok: boolean;
  error: string | null;
  result?: {
    run_id: number;
    summary: Record<string, unknown>;
    proposals: Array<Record<string, unknown>>;
    errors: Array<Record<string, unknown>>;
  };
}

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const autoApply = String(form.get("auto_apply") ?? "false") === "true";
  const confirmLiveWrite = String(form.get("confirm_live_write") ?? "false") === "true";
  const plan = String(form.get("plan") ?? "free");
  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/geo/continuous-improvement/run`,
      {
        method: "POST",
        accessToken: session.accessToken,
        body: JSON.stringify({
          auto_apply: autoApply,
          confirm_live_write: confirmLiveWrite,
          plan,
          max_actions: 5,
        }),
      },
    );
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      return json<ActionResult>({
        ok: false,
        error: (data as { detail?: string }).detail ?? `Backend ${resp.status}`,
      });
    }
    return json<ActionResult>({ ok: true, error: null, result: data as ActionResult["result"] });
  } catch (err) {
    return json<ActionResult>({ ok: false, error: String(err) });
  }
};

function money(value: number): string {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(value);
}

function tagTone(status: TagStatus): "success" | "critical" | "attention" | "info" {
  if (status === "positive") return "success";
  if (status === "negative") return "critical";
  if (status === "forced") return "attention";
  return "info";
}

function statusTone(status: string): "success" | "critical" | "attention" | "info" {
  if (status === "measured") return "success";
  if (status === "failed" || status === "rejected") return "critical";
  if (status === "planned") return "attention";
  return "info";
}

function ProductCard({ product, locale }: { product: ProductRow; locale: Locale }) {
  const improved = product.elements.filter((element) => element.improved).length;
  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{product.product_title}</Text>
            <Text as="p" variant="bodySm" tone="subdued">/{product.product_handle}</Text>
          </BlockStack>
          <Badge tone="info">{`${improved}/${product.elements.length} ${locale === "fr" ? "éléments améliorés" : "elements improved"}`}</Badge>
        </InlineStack>
        <InlineStack gap="100" wrap>
          {product.tags.slice(0, 12).map((tag) => (
            <Badge key={tag.tag_id} tone={tagTone(tag.status)}>
              {tag.locked_by_merchant ? `${tag.label} · ${locale === "fr" ? "marchand" : "merchant"}` : tag.label}
            </Badge>
          ))}
          {product.tags.length === 0 && <Badge>{locale === "fr" ? "Aucun tag" : "No tag"}</Badge>}
        </InlineStack>
        <InlineStack gap="100" wrap>
          {product.elements.map((element) => (
            <Badge key={element.key} tone={element.improved ? "success" : "info"}>
              {`${element.label}: ${element.improved
                ? (locale === "fr" ? "amélioré" : "improved")
                : (locale === "fr" ? "non amélioré" : "not improved")}`}
            </Badge>
          ))}
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

function EventCard({ event, locale }: { event: AgentEvent; locale: Locale }) {
  const estimatedRevenue = Number(event.estimated_impact.revenue_estimate ?? 0);
  const observedRevenue = event.observed_impact ? Number(event.observed_impact.revenue ?? 0) : null;
  return (
    <Card>
      <BlockStack gap="200">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h2" variant="headingMd">{event.resource_title || event.action_type}</Text>
            <Text as="p" variant="bodySm" tone="subdued">{`${event.action_type} · ${event.created_at}`}</Text>
          </BlockStack>
          <InlineStack gap="100">
            <Badge tone={statusTone(event.status)}>{event.status}</Badge>
            <Badge tone="info">{event.measurement_status}</Badge>
          </InlineStack>
        </InlineStack>
        <InlineStack gap="300" wrap>
          <Text as="p" variant="bodySm">
            <strong>{locale === "fr" ? "Score avant" : "Before score"}:</strong>{" "}
            {event.score_before ?? "n/a"}
          </Text>
          <Text as="p" variant="bodySm">
            <strong>{locale === "fr" ? "Score après" : "After score"}:</strong>{" "}
            {event.score_after ?? (locale === "fr" ? "En attente" : "Pending")}
          </Text>
          <Text as="p" variant="bodySm">
            <strong>{locale === "fr" ? "Revenu estimé" : "Estimated revenue"}:</strong>{" "}
            {money(estimatedRevenue)}
          </Text>
          <Text as="p" variant="bodySm">
            <strong>{locale === "fr" ? "Revenu observé" : "Observed revenue"}:</strong>{" "}
            {observedRevenue === null ? (locale === "fr" ? "En attente" : "Pending") : money(observedRevenue)}
          </Text>
        </InlineStack>
        {event.notes && <Text as="p" variant="bodySm">{event.notes}</Text>}
      </BlockStack>
    </Card>
  );
}

export default function ContinuousImprovement() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const fetcher = useFetcher<ActionResult>();
  const busy = fetcher.state !== "idle";

  const runAgent = (autoApply: boolean) => {
    const fd = new FormData();
    fd.set("auto_apply", autoApply ? "true" : "false");
    fd.set("confirm_live_write", autoApply ? "true" : "false");
    fd.set("plan", autoApply ? "pro" : "free");
    fetcher.submit(fd, { method: "post" });
  };

  return (
    <Page
      title={t(locale, "continuousImprovementTitle")}
      subtitle={t(locale, "continuousImprovementSubtitle")}
      backAction={{ content: t(locale, "hubInsights"), url: localizedPath("/app/insights", locale) }}
    >
      <BlockStack gap="400">
        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center" wrap>
              <BlockStack gap="050">
                <Text as="h2" variant="headingMd">
                  {locale === "fr" ? "Agent de correction GEO" : "GEO correction agent"}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {locale === "fr"
                    ? "Analyse les retours J+7/J+30/J+60, classe les tags, génère les corrections et enregistre le score avant/après."
                    : "Analyzes J+7/J+30/J+60 feedback, classifies tags, generates corrections and records before/after scores."}
                </Text>
              </BlockStack>
              <InlineStack gap="200">
                <Button loading={busy} onClick={() => runAgent(false)}>
                  {locale === "fr" ? "Générer les propositions" : "Generate proposals"}
                </Button>
                <Button variant="primary" tone="critical" loading={busy} onClick={() => runAgent(true)}>
                  {locale === "fr" ? "Auto-apply sécurisé" : "Safe auto-apply"}
                </Button>
              </InlineStack>
            </InlineStack>
            {fetcher.data?.ok && (
              <Banner tone="success">
                <Text as="p">
                  {locale === "fr"
                    ? `Run #${fetcher.data.result?.run_id} terminé. Propositions : ${fetcher.data.result?.proposals.length ?? 0}.`
                    : `Run #${fetcher.data.result?.run_id} completed. Proposals: ${fetcher.data.result?.proposals.length ?? 0}.`}
                </Text>
              </Banner>
            )}
            {fetcher.data && !fetcher.data.ok && (
              <Banner tone="warning">
                <Text as="p">{fetcher.data.error}</Text>
              </Banner>
            )}
          </BlockStack>
        </Card>

        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {data ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
              {[
                { label: locale === "fr" ? "Produits suivis" : "Products tracked", value: String(data.summary.products_tracked) },
                { label: locale === "fr" ? "Éléments améliorés" : "Elements improved", value: `${data.summary.improved_elements}/${data.summary.total_elements}` },
                { label: locale === "fr" ? "Tags positifs" : "Positive tags", value: String(data.summary.positive_tags) },
                { label: locale === "fr" ? "Tags négatifs" : "Negative tags", value: String(data.summary.negative_tags) },
                { label: locale === "fr" ? "Modifications agent" : "Agent changes", value: String(data.summary.total_events) },
                { label: locale === "fr" ? "Impact observé" : "Observed impact", value: money(data.summary.observed_revenue) },
              ].map((item) => (
                <Card key={item.label}>
                  <BlockStack gap="050">
                    <Text as="p" variant="headingLg">{item.value}</Text>
                    <Text as="p" variant="bodySm" tone="subdued">{item.label}</Text>
                  </BlockStack>
                </Card>
              ))}
            </div>

            <Banner tone="info">
              <Text as="p">{data.summary.measurement_note}</Text>
            </Banner>

            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">
                  {locale === "fr" ? "Répartition des tags" : "Tag breakdown"}
                </Text>
                <InlineStack gap="100" wrap>
                  {data.tag_breakdown.map((row) => (
                    <Badge key={`${row.tag_type}-${row.status}`} tone={tagTone(row.status as TagStatus)}>
                      {`${row.tag_type} · ${row.status}: ${row.count}`}
                    </Badge>
                  ))}
                  {data.tag_breakdown.length === 0 && (
                    <Badge>{locale === "fr" ? "Aucun tag enregistré" : "No stored tag"}</Badge>
                  )}
                </InlineStack>
              </BlockStack>
            </Card>

            <BlockStack gap="300">
              <Text as="h2" variant="headingLg">
                {locale === "fr" ? "Runs de l'agent" : "Agent runs"}
              </Text>
              {data.agent_runs.map((run) => (
                <Card key={run.id}>
                  <BlockStack gap="150">
                    <InlineStack align="space-between" blockAlign="center" wrap>
                      <Text as="h3" variant="headingMd">{`#${run.id} · ${run.created_at}`}</Text>
                      <InlineStack gap="100">
                        <Badge tone={run.status === "completed" ? "success" : "attention"}>{run.status}</Badge>
                        <Badge tone="info">{run.mode}</Badge>
                      </InlineStack>
                    </InlineStack>
                    <InlineStack gap="200" wrap>
                      {Object.entries(run.summary).map(([key, value]) => (
                        <Badge key={key}>{`${key}: ${String(value)}`}</Badge>
                      ))}
                    </InlineStack>
                    {run.errors.length > 0 && (
                      <Banner tone="warning">
                        <Text as="p">{`${run.errors.length} ${locale === "fr" ? "erreur(s) pendant le run" : "error(s) during the run"}`}</Text>
                      </Banner>
                    )}
                  </BlockStack>
                </Card>
              ))}
              {data.agent_runs.length === 0 && (
                <Banner tone="info">
                  <Text as="p">{locale === "fr" ? "Aucun run agent enregistré." : "No agent run recorded."}</Text>
                </Banner>
              )}
            </BlockStack>

            <BlockStack gap="300">
              <Text as="h2" variant="headingLg">
                {locale === "fr" ? "Décisions sur les tags" : "Tag decisions"}
              </Text>
              <InlineStack gap="100" wrap>
                {data.tag_history.slice(0, 30).map((item) => (
                  <Badge key={`${item.tag_id}-${item.decided_at}`} tone={tagTone(item.status_after as TagStatus)}>
                    {`${item.window} · ${item.label}: ${item.status_before} → ${item.status_after}`}
                  </Badge>
                ))}
                {data.tag_history.length === 0 && (
                  <Badge>{locale === "fr" ? "Aucune décision tag" : "No tag decision"}</Badge>
                )}
              </InlineStack>
            </BlockStack>

            <BlockStack gap="300">
              <Text as="h2" variant="headingLg">
                {locale === "fr" ? "Produits et axes de contenu" : "Products and content axes"}
              </Text>
              {data.products.map((product) => (
                <ProductCard key={product.product_id} product={product} locale={locale} />
              ))}
              {data.products.length === 0 && (
                <Banner tone="warning">
                  <Text as="p">{locale === "fr" ? "Lancez une Analyse marché pour créer les premiers tags." : "Run a Market analysis to create the first tags."}</Text>
                </Banner>
              )}
            </BlockStack>

            <BlockStack gap="300">
              <Text as="h2" variant="headingLg">
                {locale === "fr" ? "Modifications de l'agent" : "Agent changes"}
              </Text>
              {data.events.map((event) => (
                <EventCard key={event.id} event={event} locale={locale} />
              ))}
              {data.events.length === 0 && (
                <Banner tone="info">
                  <Text as="p">{locale === "fr" ? "Aucune modification agent enregistrée pour le moment." : "No agent change recorded yet."}</Text>
                </Banner>
              )}
            </BlockStack>
          </>
        ) : null}
      </BlockStack>
    </Page>
  );
}
