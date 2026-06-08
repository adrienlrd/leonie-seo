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
  Select,
  Text,
  TextField,
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

interface LearningApproval {
  id: number;
  resource_type: string;
  resource_id: string;
  action_type: string;
  field: string;
  old_value: string | null;
  proposed_value: string;
  confidence_score: number;
  risk_level: string;
  expected_impact: Record<string, unknown>;
  explanation: Record<string, unknown>;
  status: string;
  created_at: string;
  applied_at: string | null;
}

interface LearningStatusData {
  shop: string;
  settings: {
    enabled: boolean;
    mode: "semi_auto" | "auto_apply";
    allow_bulk_approval: boolean;
    max_auto_actions_per_cycle: number;
    min_confidence_to_auto_apply: number;
    min_confidence_to_suggest: number;
  };
  last_run: Record<string, unknown> | null;
  observation_count: number;
  pending_approval_count: number;
  weights_up: Array<Record<string, unknown>>;
  weights_down: Array<Record<string, unknown>>;
  top_actions: Array<Record<string, unknown>>;
  recent_decisions: Array<Record<string, unknown>>;
  recent_runs: Array<Record<string, unknown>>;
}

interface LearningApprovalsData {
  approvals: LearningApproval[];
}

interface AgentScheduleData {
  enabled: boolean;
  mode: "semi_auto" | "auto_apply";
  next_run_at: string | null;
  last_run_at: string | null;
  last_run_id: number | null;
  test_run_at: string | null;
  schedule: {
    frequency: string;
    local_time: string;
    timezone: string;
  };
}

type EffectivenessVerdict = "improving" | "regressing" | "no_effect" | "inconclusive";

interface EffectivenessRecommendation {
  code: string;
  severity: "critical" | "warning" | "info" | "success";
  fr: string;
  en: string;
}

interface AgentEffectivenessData {
  overall_verdict: string;
  sample_size: number;
  avg_confidence: number;
  seo: { verdict: EffectivenessVerdict; score: number; sample: number };
  geo: { verdict: EffectivenessVerdict; score: number; sample: number };
  by_field: Array<{
    field: string;
    sample: number;
    seo_score: number;
    geo_score: number;
    avg_outcome: number;
  }>;
  recommendations: EffectivenessRecommendation[];
}

interface LoaderData {
  locale: Locale;
  shop: string;
  data: ContinuousImprovementData | null;
  learning: LearningStatusData | null;
  approvals: LearningApproval[];
  schedule: AgentScheduleData | null;
  effectiveness: AgentEffectivenessData | null;
  error: string | null;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = getLocale(request);
  try {
    const [resp, learningResp, approvalsResp, scheduleResp, effectivenessResp] =
      await Promise.all([
        callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/geo/continuous-improvement?limit=100`,
          { accessToken: session.accessToken },
        ),
        callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/learning/status`,
          { accessToken: session.accessToken },
        ),
        callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/learning/pending-approvals?limit=100`,
          { accessToken: session.accessToken },
        ),
        callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/agent-schedule/status`,
          { accessToken: session.accessToken },
        ),
        callBackendForShop(
          session.shop,
          `/api/shops/${session.shop}/agent-schedule/effectiveness`,
          { accessToken: session.accessToken },
        ),
      ]);
    if (!resp.ok) {
      return json<LoaderData>({
        locale,
        shop: session.shop,
        data: null,
        learning: null,
        approvals: [],
        schedule: null,
        effectiveness: null,
        error: await resp.text(),
      });
    }
    return json<LoaderData>({
      locale,
      shop: session.shop,
      data: (await resp.json()) as ContinuousImprovementData,
      learning: learningResp.ok ? ((await learningResp.json()) as LearningStatusData) : null,
      approvals: approvalsResp.ok
        ? ((await approvalsResp.json()) as LearningApprovalsData).approvals
        : [],
      schedule: scheduleResp.ok ? ((await scheduleResp.json()) as AgentScheduleData) : null,
      effectiveness: effectivenessResp.ok
        ? ((await effectivenessResp.json()) as AgentEffectivenessData)
        : null,
      error: null,
    });
  } catch (err) {
    return json<LoaderData>({
      locale,
      shop: session.shop,
      data: null,
      learning: null,
      approvals: [],
      schedule: null,
      effectiveness: null,
      error: String(err),
    });
  }
};

interface CycleDiagnostics {
  reason: string;
  proposals: number;
  fr: string;
  en: string;
}

interface ActionResult {
  ok: boolean;
  error: string | null;
  result?: {
    run_id?: number;
    status?: string;
    summary?: Record<string, unknown>;
    proposals?: Array<Record<string, unknown>>;
    errors?: Array<Record<string, unknown>>;
    diagnostics?: CycleDiagnostics;
    continuous_agent?: {
      summary?: Record<string, unknown>;
      proposals?: Array<Record<string, unknown>>;
      errors?: Array<Record<string, unknown>>;
    } | null;
  };
  exportData?: unknown;
}

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const intent = String(form.get("intent") ?? "runContinuousAgent");
  const confirmLiveWrite = String(form.get("confirm_live_write") ?? "false") === "true";
  try {
    if (intent === "saveLearningSettings") {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/learning/settings`,
        {
          method: "PUT",
          accessToken: session.accessToken,
          body: JSON.stringify({
            enabled: String(form.get("enabled") ?? "false") === "true",
            mode: String(form.get("mode") ?? "semi_auto"),
            allow_bulk_approval: String(form.get("allow_bulk_approval") ?? "false") === "true",
            max_auto_actions_per_cycle: Number(form.get("max_auto_actions_per_cycle") ?? 3),
            min_confidence_to_auto_apply: Number(form.get("min_confidence_to_auto_apply") ?? 80),
            min_confidence_to_suggest: Number(form.get("min_confidence_to_suggest") ?? 45),
          }),
        },
      );
      const data = await resp.json().catch(() => ({}));
      return json<ActionResult>({
        ok: resp.ok,
        error: resp.ok ? null : ((data as { detail?: string }).detail ?? `Backend ${resp.status}`),
        result: data as ActionResult["result"],
      });
    }

    if (intent === "runLearningCycle") {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/learning/run`,
        {
          method: "POST",
          accessToken: session.accessToken,
          body: JSON.stringify({ confirm_live_write: confirmLiveWrite, max_actions: 5 }),
        },
      );
      const data = await resp.json().catch(() => ({}));
      return json<ActionResult>({
        ok: resp.ok,
        error: resp.ok ? null : ((data as { detail?: string }).detail ?? `Backend ${resp.status}`),
        result: data as ActionResult["result"],
      });
    }

    if (intent === "approveLearning" || intent === "rejectLearning" || intent === "editLearning") {
      const approvalId = String(form.get("approval_id") ?? "");
      const endpoint = intent === "approveLearning"
        ? "approve"
        : intent === "rejectLearning"
          ? "reject"
          : "edit";
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/learning/approvals/${approvalId}/${endpoint}`,
        {
          method: intent === "editLearning" ? "PATCH" : "POST",
          accessToken: session.accessToken,
          body: JSON.stringify(
            intent === "editLearning"
              ? { proposed_value: String(form.get("proposed_value") ?? "") }
              : { confirm_live_write: true, max_actions: 1 },
          ),
        },
      );
      const data = await resp.json().catch(() => ({}));
      return json<ActionResult>({
        ok: resp.ok,
        error: resp.ok ? null : ((data as { detail?: string }).detail ?? `Backend ${resp.status}`),
        result: data as ActionResult["result"],
      });
    }

    if (intent === "saveAgentSchedule") {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/agent-schedule/settings`,
        {
          method: "PUT",
          accessToken: session.accessToken,
          body: JSON.stringify({
            enabled: String(form.get("enabled") ?? "true") === "true",
            mode: String(form.get("mode") ?? "semi_auto"),
            frequency: "daily",
            local_time: String(form.get("local_time") ?? "08:00"),
          }),
        },
      );
      const data = await resp.json().catch(() => ({}));
      return json<ActionResult>({
        ok: resp.ok,
        error: resp.ok ? null : ((data as { detail?: string }).detail ?? `Backend ${resp.status}`),
      });
    }

    if (intent === "disableAgentSchedule" || intent === "testAgentIn5Min") {
      const endpoint = intent === "disableAgentSchedule" ? "disable" : "test-in-5-min";
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/agent-schedule/${endpoint}`,
        { method: "POST", accessToken: session.accessToken },
      );
      const data = await resp.json().catch(() => ({}));
      return json<ActionResult>({
        ok: resp.ok,
        error: resp.ok ? null : ((data as { detail?: string }).detail ?? `Backend ${resp.status}`),
      });
    }

    if (intent === "exportAgentSchedule") {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/agent-schedule/export`,
        { accessToken: session.accessToken },
      );
      const data = await resp.json().catch(() => ({}));
      return json<ActionResult>({
        ok: resp.ok,
        error: resp.ok ? null : `Backend ${resp.status}`,
        exportData: resp.ok ? data : undefined,
      });
    }

    if (intent === "bulkApproveSafe") {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/learning/approvals/bulk-approve-safe`,
        {
          method: "POST",
          accessToken: session.accessToken,
          body: JSON.stringify({ confirm_live_write: true, max_actions: 20 }),
        },
      );
      const data = await resp.json().catch(() => ({}));
      return json<ActionResult>({
        ok: resp.ok,
        error: resp.ok ? null : ((data as { detail?: string }).detail ?? `Backend ${resp.status}`),
        result: data as ActionResult["result"],
      });
    }

    const autoApply = String(form.get("auto_apply") ?? "false") === "true";
    const plan = String(form.get("plan") ?? "free");
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

function verdictTone(verdict: string): "success" | "critical" | "attention" | "info" {
  if (verdict === "improving") return "success";
  if (verdict === "regressing") return "critical";
  if (verdict === "no_effect") return "attention";
  return "info";
}

function verdictLabel(verdict: string, locale: Locale): string {
  const fr: Record<string, string> = {
    improving: "En amélioration",
    regressing: "En régression",
    no_effect: "Sans effet",
    inconclusive: "Non concluant",
    partially_improving: "Partiellement en amélioration",
  };
  const en: Record<string, string> = {
    improving: "Improving",
    regressing: "Regressing",
    no_effect: "No effect",
    inconclusive: "Inconclusive",
    partially_improving: "Partially improving",
  };
  return (locale === "fr" ? fr : en)[verdict] ?? verdict;
}

function recommendationTone(severity: string): "success" | "critical" | "warning" | "info" {
  if (severity === "success") return "success";
  if (severity === "critical") return "critical";
  if (severity === "warning") return "warning";
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

function ApprovalCard({
  approval,
  locale,
  busy,
}: {
  approval: LearningApproval;
  locale: Locale;
  busy: boolean;
}) {
  const fetcher = useFetcher<ActionResult>();
  const [value, setValue] = useState(approval.proposed_value);
  const pending = busy || fetcher.state !== "idle";
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center" wrap>
          <BlockStack gap="050">
            <Text as="h3" variant="headingMd">
              {String(approval.explanation.product_title ?? approval.resource_id)}
            </Text>
            <Text as="p" variant="bodySm" tone="subdued">
              {`${approval.field} · ${approval.created_at}`}
            </Text>
          </BlockStack>
          <InlineStack gap="100">
            <Badge tone={approval.risk_level === "low" ? "success" : approval.risk_level === "medium" ? "attention" : "critical"}>
              {approval.risk_level}
            </Badge>
            <Badge tone="info">{`${approval.confidence_score}/100`}</Badge>
          </InlineStack>
        </InlineStack>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
          <div style={{ border: "1px solid #dfe3e8", borderRadius: 8, padding: 12 }}>
            <BlockStack gap="100">
              <Text as="p" variant="headingSm">{locale === "fr" ? "Avant" : "Before"}</Text>
              <Text as="p" variant="bodySm">{approval.old_value || "n/a"}</Text>
            </BlockStack>
          </div>
          <div style={{ border: "1px solid #dfe3e8", borderRadius: 8, padding: 12 }}>
            <BlockStack gap="100">
              <Text as="p" variant="headingSm">{locale === "fr" ? "Après" : "After"}</Text>
              <TextField
                label={locale === "fr" ? "Proposition" : "Proposal"}
                labelHidden
                value={value}
                onChange={setValue}
                multiline={4}
                autoComplete="off"
              />
            </BlockStack>
          </div>
        </div>
        <Text as="p" variant="bodySm" tone="subdued">
          {String(
            approval.expected_impact.summary
              ?? approval.explanation.reason
              ?? (locale === "fr" ? "Impact attendu calculé par le moteur." : "Expected impact calculated by the engine."),
          )}
        </Text>
        <InlineStack gap="200">
          <fetcher.Form method="post">
            <input type="hidden" name="intent" value="approveLearning" />
            <input type="hidden" name="approval_id" value={approval.id} />
            <Button submit variant="primary" loading={pending}>
              {locale === "fr" ? "Appliquer" : "Apply"}
            </Button>
          </fetcher.Form>
          <fetcher.Form method="post">
            <input type="hidden" name="intent" value="rejectLearning" />
            <input type="hidden" name="approval_id" value={approval.id} />
            <Button submit loading={pending}>
              {locale === "fr" ? "Ignorer" : "Skip"}
            </Button>
          </fetcher.Form>
          <fetcher.Form method="post">
            <input type="hidden" name="intent" value="editLearning" />
            <input type="hidden" name="approval_id" value={approval.id} />
            <input type="hidden" name="proposed_value" value={value} />
            <Button submit loading={pending}>
              {locale === "fr" ? "Modifier" : "Edit"}
            </Button>
          </fetcher.Form>
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

function formatDateTime(value: string | null, locale: Locale): string {
  if (!value) return locale === "fr" ? "—" : "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale === "fr" ? "fr-FR" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function ContinuousImprovement() {
  const { locale, shop, data, learning, approvals, schedule, effectiveness, error } =
    useLoaderData<typeof loader>();
  const fetcher = useFetcher<ActionResult>();
  const busy = fetcher.state !== "idle";

  const scheduleFetcher = useFetcher<ActionResult>();
  const exportFetcher = useFetcher<ActionResult>();
  const cycleFetcher = useFetcher<ActionResult>();
  const scheduleBusy = scheduleFetcher.state !== "idle";
  const exportBusy = exportFetcher.state !== "idle";
  const cycleBusy = cycleFetcher.state !== "idle";

  const downloadJson = (payload: unknown, filename: string) => {
    if (typeof document === "undefined") return;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  const [scheduleMode, setScheduleMode] = useState<"semi_auto" | "auto_apply">(
    schedule?.mode ?? "semi_auto",
  );
  const [scheduleTime, setScheduleTime] = useState(schedule?.schedule.local_time ?? "08:00");

  // Trigger a client-side download once the export payload comes back.
  useEffect(() => {
    if (!exportFetcher.data?.ok || exportFetcher.data.exportData === undefined) return;
    downloadJson(
      exportFetcher.data.exportData,
      `leonie-agent-results-${shop}-${new Date().toISOString().slice(0, 10)}.json`,
    );
  }, [exportFetcher.data, shop]);

  const enableDailyAgent = () => {
    const fd = new FormData();
    fd.set("intent", "saveAgentSchedule");
    fd.set("enabled", "true");
    fd.set("mode", scheduleMode);
    fd.set("local_time", scheduleTime);
    scheduleFetcher.submit(fd, { method: "post" });
  };

  const disableDailyAgent = () => {
    const fd = new FormData();
    fd.set("intent", "disableAgentSchedule");
    scheduleFetcher.submit(fd, { method: "post" });
  };

  const testAgentIn5Min = () => {
    const fd = new FormData();
    fd.set("intent", "testAgentIn5Min");
    scheduleFetcher.submit(fd, { method: "post" });
  };

  const exportResults = () => {
    const fd = new FormData();
    fd.set("intent", "exportAgentSchedule");
    exportFetcher.submit(fd, { method: "post" });
  };

  const [learningMode, setLearningMode] = useState<"semi_auto" | "auto_apply">(
    learning?.settings.mode ?? "semi_auto",
  );
  const [enabled, setEnabled] = useState(String(Boolean(learning?.settings.enabled ?? true)));
  const [bulkApproval, setBulkApproval] = useState(
    String(Boolean(learning?.settings.allow_bulk_approval ?? true)),
  );
  const [minAutoConfidence, setMinAutoConfidence] = useState(
    String(learning?.settings.min_confidence_to_auto_apply ?? 80),
  );
  const [maxAutoActions, setMaxAutoActions] = useState(
    String(learning?.settings.max_auto_actions_per_cycle ?? 3),
  );

  const runAgent = (autoApply: boolean) => {
    const fd = new FormData();
    fd.set("intent", "runContinuousAgent");
    fd.set("auto_apply", autoApply ? "true" : "false");
    fd.set("confirm_live_write", autoApply ? "true" : "false");
    fd.set("plan", autoApply ? "pro" : "free");
    fetcher.submit(fd, { method: "post" });
  };

  const runLearningCycle = () => {
    const fd = new FormData();
    fd.set("intent", "runLearningCycle");
    fd.set("confirm_live_write", learningMode === "auto_apply" ? "true" : "false");
    cycleFetcher.submit(fd, { method: "post" });
  };

  const downloadCycleResult = () => {
    if (!cycleFetcher.data?.result) return;
    downloadJson(
      cycleFetcher.data.result,
      `leonie-cycle-${shop}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`,
    );
  };

  const downloadAgentResult = () => {
    if (!fetcher.data?.result) return;
    downloadJson(
      fetcher.data.result,
      `leonie-agent-run-${shop}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`,
    );
  };

  const saveLearningSettings = () => {
    const fd = new FormData();
    fd.set("intent", "saveLearningSettings");
    fd.set("enabled", enabled);
    fd.set("mode", learningMode);
    fd.set("allow_bulk_approval", bulkApproval);
    fd.set("min_confidence_to_auto_apply", minAutoConfidence);
    fd.set("min_confidence_to_suggest", "45");
    fd.set("max_auto_actions_per_cycle", maxAutoActions);
    fetcher.submit(fd, { method: "post" });
  };

  const bulkApproveSafe = () => {
    const fd = new FormData();
    fd.set("intent", "bulkApproveSafe");
    fetcher.submit(fd, { method: "post" });
  };

  return (
    <Page
      title={t(locale, "continuousImprovementTitle")}
      subtitle={t(locale, "continuousImprovementSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}
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
                    ? "Analyse les retours J+14/J+28, classe les tags, génère les corrections et enregistre le score avant/après."
                    : "Analyzes J+14/J+28 feedback, classifies tags, generates corrections and records before/after scores."}
                </Text>
              </BlockStack>
              <InlineStack gap="200">
                <Button loading={busy} onClick={() => runAgent(false)}>
                  {locale === "fr" ? "Semi-automatique — recommandé" : "Semi-automatic — recommended"}
                </Button>
                <Button variant="primary" tone="critical" loading={busy} onClick={() => runAgent(true)}>
                  {locale === "fr" ? "Auto-apply — avancé" : "Auto-apply — advanced"}
                </Button>
              </InlineStack>
            </InlineStack>
            {fetcher.data?.ok && fetcher.data.result?.diagnostics && (
              <Banner tone="success">
                <Text as="p">
                  {locale === "fr"
                    ? `Run #${fetcher.data.result?.run_id} terminé. Propositions : ${fetcher.data.result?.proposals?.length ?? 0}.`
                    : `Run #${fetcher.data.result?.run_id} completed. Proposals: ${fetcher.data.result?.proposals?.length ?? 0}.`}
                </Text>
              </Banner>
            )}
            {fetcher.data?.ok
              && fetcher.data.result?.diagnostics
              && (fetcher.data.result.proposals?.length ?? 0) === 0 && (
              <Banner tone="info">
                <Text as="p">
                  {locale === "fr"
                    ? fetcher.data.result.diagnostics.fr
                    : fetcher.data.result.diagnostics.en}
                </Text>
              </Banner>
            )}
            {fetcher.data?.ok && fetcher.data.result?.diagnostics && (
              <InlineStack gap="200">
                <Button onClick={downloadAgentResult}>
                  {locale === "fr"
                    ? "Télécharger le JSON (raisonnement + résultat)"
                    : "Download JSON (reasoning + result)"}
                </Button>
              </InlineStack>
            )}
            {fetcher.data && !fetcher.data.ok && (
              <Banner tone="warning">
                <Text as="p">{fetcher.data.error}</Text>
              </Banner>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center" wrap>
              <BlockStack gap="050">
                <Text as="h2" variant="headingMd">
                  {locale === "fr" ? "Automatisation de l'agent" : "Agent automation"}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {locale === "fr"
                    ? "Laissez l'agent tourner automatiquement chaque jour. Le test ne fait qu'un seul passage et n'active pas le quotidien."
                    : "Let the agent run automatically every day. The test runs once and does not enable the daily schedule."}
                </Text>
              </BlockStack>
              <Badge tone={schedule?.enabled ? "success" : "info"}>
                {schedule?.enabled
                  ? (locale === "fr" ? "Activé" : "Enabled")
                  : (locale === "fr" ? "Désactivé" : "Disabled")}
              </Badge>
            </InlineStack>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
              <Select
                label={locale === "fr" ? "Mode" : "Mode"}
                options={[
                  {
                    label: locale === "fr"
                      ? "Semi-automatique — recommandé"
                      : "Semi-automatic — recommended",
                    value: "semi_auto",
                  },
                  {
                    label: locale === "fr" ? "Auto-apply — avancé" : "Auto-apply — advanced",
                    value: "auto_apply",
                  },
                ]}
                value={scheduleMode}
                onChange={(value) => setScheduleMode(value as "semi_auto" | "auto_apply")}
              />
              <Select
                label={locale === "fr" ? "Fréquence" : "Frequency"}
                options={[
                  { label: locale === "fr" ? "Tous les jours" : "Every day", value: "daily" },
                ]}
                value="daily"
                disabled
                onChange={() => {}}
              />
              <TextField
                label={locale === "fr" ? "Heure locale" : "Local time"}
                value={scheduleTime}
                onChange={setScheduleTime}
                type="time"
                autoComplete="off"
              />
            </div>

            {scheduleMode === "auto_apply" && (
              <Banner tone="warning">
                <Text as="p">
                  {locale === "fr"
                    ? "Mode auto-apply : l'agent peut appliquer des modifications Shopify automatiquement, dans la limite des garde-fous existants (faible risque + confiance élevée). Le mode semi-automatique reste recommandé."
                    : "Auto-apply mode: the agent may apply Shopify changes automatically, within existing guardrails (low risk + high confidence). Semi-automatic mode remains recommended."}
                </Text>
              </Banner>
            )}

            <InlineStack gap="200" wrap>
              <Button variant="primary" loading={scheduleBusy} onClick={enableDailyAgent}>
                {locale === "fr" ? "Activer l'agent quotidien" : "Enable daily agent"}
              </Button>
              <Button tone="critical" loading={scheduleBusy} onClick={disableDailyAgent}>
                {locale === "fr" ? "Désactiver l'agent" : "Disable agent"}
              </Button>
              <Button loading={scheduleBusy} onClick={testAgentIn5Min}>
                {locale === "fr" ? "Lancer un test dans 5 minutes" : "Run a test in 5 minutes"}
              </Button>
              <Button loading={exportBusy} onClick={exportResults}>
                {locale === "fr" ? "Exporter les résultats" : "Export results"}
              </Button>
            </InlineStack>

            <InlineStack gap="300" wrap>
              <Text as="p" variant="bodySm">
                <strong>{locale === "fr" ? "Prochain lancement" : "Next run"}:</strong>{" "}
                {schedule?.enabled
                  ? formatDateTime(schedule?.next_run_at ?? null, locale)
                  : (locale === "fr" ? "Désactivé" : "Disabled")}
              </Text>
              <Text as="p" variant="bodySm">
                <strong>{locale === "fr" ? "Dernier lancement" : "Last run"}:</strong>{" "}
                {formatDateTime(schedule?.last_run_at ?? null, locale)}
              </Text>
              {schedule?.test_run_at && (
                <Text as="p" variant="bodySm">
                  <strong>{locale === "fr" ? "Test prévu" : "Test scheduled"}:</strong>{" "}
                  {formatDateTime(schedule.test_run_at, locale)}
                </Text>
              )}
            </InlineStack>

            <div style={{ borderTop: "1px solid #e1e3e5", paddingTop: 12 }}>
              <BlockStack gap="200">
                <InlineStack align="space-between" blockAlign="center" wrap>
                  <Text as="h3" variant="headingSm">
                    {locale === "fr"
                      ? "L'agent améliore-t-il le SEO et le GEO ?"
                      : "Is the agent improving SEO and GEO?"}
                  </Text>
                  <InlineStack gap="100">
                    <Badge tone={verdictTone(effectiveness?.seo.verdict ?? "inconclusive")}>
                      {`SEO: ${verdictLabel(effectiveness?.seo.verdict ?? "inconclusive", locale)}`}
                    </Badge>
                    <Badge tone={verdictTone(effectiveness?.geo.verdict ?? "inconclusive")}>
                      {`GEO: ${verdictLabel(effectiveness?.geo.verdict ?? "inconclusive", locale)}`}
                    </Badge>
                  </InlineStack>
                </InlineStack>
                <Text as="p" variant="bodySm" tone="subdued">
                  {locale === "fr"
                    ? `Basé sur ${effectiveness?.sample_size ?? 0} mesure(s) mûre(s) (J+14/J+28), confiance moyenne ${effectiveness?.avg_confidence ?? 0}/100.`
                    : `Based on ${effectiveness?.sample_size ?? 0} matured measurement(s) (J+14/J+28), average confidence ${effectiveness?.avg_confidence ?? 0}/100.`}
                </Text>
                {(effectiveness?.recommendations ?? []).slice(0, 4).map((rec) => (
                  <Banner key={rec.code} tone={recommendationTone(rec.severity)}>
                    <Text as="p" variant="bodySm">{locale === "fr" ? rec.fr : rec.en}</Text>
                  </Banner>
                ))}
                {(effectiveness?.by_field?.length ?? 0) > 0 && (
                  <InlineStack gap="100" wrap>
                    {effectiveness?.by_field.slice(0, 6).map((field) => (
                      <Badge key={field.field} tone={field.avg_outcome >= 0 ? "success" : "critical"}>
                        {`${field.field}: ${field.avg_outcome >= 0 ? "+" : ""}${field.avg_outcome} (${field.sample})`}
                      </Badge>
                    ))}
                  </InlineStack>
                )}
              </BlockStack>
            </div>

            {scheduleFetcher.data?.ok && (
              <Banner tone="success">
                <Text as="p">
                  {locale === "fr" ? "Automatisation mise à jour." : "Automation updated."}
                </Text>
              </Banner>
            )}
            {scheduleFetcher.data && !scheduleFetcher.data.ok && (
              <Banner tone="warning">
                <Text as="p">{scheduleFetcher.data.error}</Text>
              </Banner>
            )}
            {exportFetcher.data && !exportFetcher.data.ok && (
              <Banner tone="warning">
                <Text as="p">{exportFetcher.data.error}</Text>
              </Banner>
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center" wrap>
              <BlockStack gap="050">
                <Text as="h2" variant="headingMd">Learning / Algorithme</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  {locale === "fr"
                    ? "Le moteur apprend des résultats J+14/J+28, prépare les meilleures optimisations et garde les changements risqués en validation."
                    : "The engine learns from J+14/J+28 outcomes, prepares the best optimizations and keeps riskier changes in review."}
                </Text>
              </BlockStack>
              <InlineStack gap="200">
                <Button loading={busy} onClick={saveLearningSettings}>
                  {locale === "fr" ? "Enregistrer" : "Save"}
                </Button>
                <Button variant="primary" loading={cycleBusy} onClick={runLearningCycle}>
                  {locale === "fr" ? "Lancer un cycle maintenant" : "Run cycle now"}
                </Button>
              </InlineStack>
            </InlineStack>
            {cycleFetcher.data?.result?.diagnostics && (
              <Banner
                tone={
                  cycleFetcher.data.result.diagnostics.reason === "ok" ? "success" : "info"
                }
              >
                <Text as="p">
                  {locale === "fr"
                    ? cycleFetcher.data.result.diagnostics.fr
                    : cycleFetcher.data.result.diagnostics.en}
                </Text>
              </Banner>
            )}
            {cycleFetcher.data && !cycleFetcher.data.ok && (
              <Banner tone="warning">
                <Text as="p">{cycleFetcher.data.error}</Text>
              </Banner>
            )}
            {cycleFetcher.data?.result && (
              <InlineStack gap="200">
                <Button onClick={downloadCycleResult}>
                  {locale === "fr"
                    ? "Télécharger le JSON de ce cycle (raisonnement + résultat)"
                    : "Download this cycle's JSON (reasoning + result)"}
                </Button>
              </InlineStack>
            )}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
              <Select
                label={locale === "fr" ? "Statut" : "Status"}
                options={[
                  { label: locale === "fr" ? "Activé" : "Enabled", value: "true" },
                  { label: locale === "fr" ? "Désactivé" : "Disabled", value: "false" },
                ]}
                value={enabled}
                onChange={setEnabled}
              />
              <Select
                label={locale === "fr" ? "Mode" : "Mode"}
                options={[
                  {
                    label: locale === "fr"
                      ? "Semi-automatique — recommandé"
                      : "Semi-automatic — recommended",
                    value: "semi_auto",
                  },
                  {
                    label: locale === "fr"
                      ? "Auto-apply — avancé"
                      : "Auto-apply — advanced",
                    value: "auto_apply",
                  },
                ]}
                value={learningMode}
                onChange={(value) => setLearningMode(value as "semi_auto" | "auto_apply")}
              />
              <TextField
                label={locale === "fr" ? "Confiance minimum auto-apply" : "Auto-apply minimum confidence"}
                value={minAutoConfidence}
                onChange={setMinAutoConfidence}
                type="number"
                autoComplete="off"
              />
              <TextField
                label={locale === "fr" ? "Limite auto par cycle" : "Auto limit per cycle"}
                value={maxAutoActions}
                onChange={setMaxAutoActions}
                type="number"
                autoComplete="off"
              />
              <Select
                label={locale === "fr" ? "Validation groupée" : "Bulk approval"}
                options={[
                  { label: locale === "fr" ? "Autorisée" : "Allowed", value: "true" },
                  { label: locale === "fr" ? "Désactivée" : "Disabled", value: "false" },
                ]}
                value={bulkApproval}
                onChange={setBulkApproval}
              />
            </div>
            <InlineStack gap="200" wrap>
              <Badge tone={learning?.settings.mode === "auto_apply" ? "attention" : "success"}>
                {learning?.settings.mode ?? "semi_auto"}
              </Badge>
              <Badge tone="info">{`${learning?.observation_count ?? 0} observations`}</Badge>
              <Badge tone="info">{`${learning?.pending_approval_count ?? approvals.length} actions à valider`}</Badge>
              {learning?.last_run && <Badge>{`Dernier run #${String(learning.last_run.id ?? "")}`}</Badge>}
            </InlineStack>
            <InlineStack gap="100" wrap>
              {(learning?.top_actions ?? []).slice(0, 8).map((weight) => (
                <Badge key={`${String(weight.feature_value)}-${String(weight.updated_at)}`} tone="success">
                  {`${String(weight.feature_value)} ${Number(weight.weight ?? 0).toFixed(2)}`}
                </Badge>
              ))}
              {(learning?.weights_down ?? []).slice(0, 5).map((weight) => (
                <Badge key={`${String(weight.feature_value)}-${String(weight.updated_at)}`} tone="critical">
                  {`${String(weight.feature_value)} ${Number(weight.weight ?? 0).toFixed(2)}`}
                </Badge>
              ))}
            </InlineStack>
          </BlockStack>
        </Card>

        <BlockStack gap="300">
          <InlineStack align="space-between" blockAlign="center" wrap>
            <Text as="h2" variant="headingLg">
              {locale === "fr" ? "Actions à valider" : "Actions to review"}
            </Text>
            <Button loading={busy} onClick={bulkApproveSafe}>
              {locale === "fr" ? "Appliquer toutes les actions sûres" : "Apply all safe actions"}
            </Button>
          </InlineStack>
          {approvals.map((approval) => (
            <ApprovalCard key={approval.id} approval={approval} locale={locale} busy={busy} />
          ))}
          {approvals.length === 0 && (
            <Banner tone="info">
              <Text as="p">
                {locale === "fr"
                  ? "Aucune action en attente. Lance un cycle learning pour préparer les prochaines optimisations."
                  : "No pending action. Run a learning cycle to prepare the next optimizations."}
              </Text>
            </Banner>
          )}
        </BlockStack>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {locale === "fr" ? "Actions appliquées automatiquement" : "Automatically applied actions"}
              </Text>
              {(learning?.recent_decisions ?? [])
                .filter((decision) => decision.merchant_decision === "auto_applied")
                .slice(0, 8)
                .map((decision) => (
                  <Badge key={String(decision.id)} tone="success">
                    {`${String(decision.action_type)} · ${Number(decision.final_score ?? 0).toFixed(0)}/100`}
                  </Badge>
                ))}
              {(learning?.recent_decisions ?? []).filter((decision) => decision.merchant_decision === "auto_applied").length === 0 && (
                <Text as="p" variant="bodySm" tone="subdued">
                  {locale === "fr" ? "Aucune action auto-appliquée récemment." : "No recent automatic apply."}
                </Text>
              )}
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {locale === "fr" ? "Suivi J+14 / J+28" : "J+14 / J+28 follow-up"}
              </Text>
              {(learning?.recent_runs ?? []).slice(0, 5).map((run) => (
                <InlineStack key={String(run.id)} align="space-between" wrap>
                  <Text as="p" variant="bodySm">{`#${String(run.id)} · ${String(run.created_at ?? "")}`}</Text>
                  <Badge tone={run.status === "completed" ? "success" : "attention"}>
                    {String(run.status)}
                  </Badge>
                </InlineStack>
              ))}
              {(learning?.recent_runs ?? []).length === 0 && (
                <Text as="p" variant="bodySm" tone="subdued">
                  {locale === "fr" ? "Aucun cycle learning enregistré." : "No learning cycle recorded."}
                </Text>
              )}
            </BlockStack>
          </Card>
        </div>

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
