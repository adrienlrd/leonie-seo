import { json, type LoaderFunctionArgs, type ActionFunctionArgs } from "@remix-run/node";
import { useLoaderData, useFetcher } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Text,
  Badge,
  Banner,
  Button,
  ButtonGroup,
  InlineStack,
  BlockStack,
  Box,
  Divider,
  ProgressBar,
  EmptyState,
  Spinner,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { t, getLocale, type Locale } from "../lib/i18n";

interface LoaderData {
  shop: string;
  queue: ContentActionRow[];
  locale: Locale;
}

const API_BASE = process.env.LEONIE_API_BASE ?? "http://localhost:8000";

async function apiGet(shop: string, path: string) {
  const res = await fetch(`${API_BASE}/api/shops/${shop}${path}`);
  if (!res.ok) return null;
  return res.json();
}

async function apiPost(shop: string, path: string, body: object) {
  const res = await fetch(`${API_BASE}/api/shops/${shop}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { ok: res.ok, status: res.status, data: await res.json().catch(() => ({})) };
}

// Load all content actions that need review (draft / needs_review / approved)
async function loadReviewQueue(shop: string): Promise<ContentActionRow[]> {
  const res = await fetch(`${API_BASE}/api/shops/${shop}/content-actions?status=draft,needs_review,approved`).catch(() => null);
  if (!res?.ok) return [];
  const data = await res.json().catch(() => ({ items: [] }));
  return data.items ?? [];
}

interface ContentActionRow {
  action_id: string;
  content_type: string;
  resource_id: string;
  status: string;
  quality?: { score: number; label: string };
  output?: { primary_text: string };
  constraints_check?: {
    forbidden_promise_violations: string[];
    do_not_say_violations: string[];
    length_ok: boolean;
    language_ok: boolean;
  };
}

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const queue = await loadReviewQueue(shop);
  return json<LoaderData>({ shop, queue, locale });
}

export async function action({ request }: ActionFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const form = await request.formData();
  const intent = form.get("intent") as string;
  const actionId = form.get("action_id") as string;

  if (intent === "dry_run") {
    const result = await apiPost(shop, "/safe-apply/dry-run", { action_id: actionId });
    return json({ intent, ...result });
  }

  if (intent === "decision") {
    const decision = form.get("decision") as string;
    const editedText = form.get("edited_text") as string | null;
    const rejectedReason = form.get("rejected_reason") as string | null;
    const result = await apiPost(shop, "/safe-apply/decision", {
      action_id: actionId,
      decision,
      edited_text: editedText || undefined,
      rejected_reason: rejectedReason || undefined,
    });
    return json({ intent, ...result });
  }

  if (intent === "live_apply") {
    const result = await apiPost(shop, `/safe-apply/live?plan=pro`, {
      action_id: actionId,
      confirm_live_write: true,
    });
    return json({ intent, ...result });
  }

  return json({ intent, ok: false, error: "Unknown intent" });
}

const STATUS_TONES: Record<string, "info" | "success" | "warning" | "critical" | "attention"> = {
  draft: "info",
  needs_review: "warning",
  approved: "success",
  applied: "success",
  rejected: "critical",
  exported: "attention",
};

const STATUS_I18N_KEYS: Record<string, string> = {
  draft: "statusDraft",
  needs_review: "statusNeedsReview",
  approved: "statusApproved",
  applied: "statusApplied",
  rejected: "statusRejected",
};

const CONTENT_TYPE_I18N_KEYS: Record<string, string> = {
  product_title: "contentTypeProductTitle",
  product_description: "contentTypeProductDescription",
  meta_title: "contentTypeMetaTitle",
  meta_description: "contentTypeMetaDescription",
};

function StatusBadge({ status, locale }: { status: string; locale: Locale }) {
  return (
    <Badge tone={STATUS_TONES[status] ?? "info"}>
      {t(locale, STATUS_I18N_KEYS[status] ?? status)}
    </Badge>
  );
}

function QualityBar({ score }: { score: number }) {
  const tone: "success" | "critical" | "highlight" =
    score >= 75 ? "success" : score >= 45 ? "highlight" : "critical";
  return <ProgressBar progress={score} tone={tone} size="small" />;
}

function ActionCard({ row, locale }: { row: ContentActionRow; locale: Locale }) {
  const fetcher = useFetcher();
  const submitting = fetcher.state !== "idle";
  const check = row.constraints_check;
  const hasViolations =
    (check?.forbidden_promise_violations?.length ?? 0) > 0 ||
    (check?.do_not_say_violations?.length ?? 0) > 0 ||
    !check?.length_ok ||
    !check?.language_ok;

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between" blockAlign="center">
          <Text variant="headingMd" as="h3">
            {t(locale, CONTENT_TYPE_I18N_KEYS[row.content_type] ?? row.content_type)}
          </Text>
          <StatusBadge status={row.status} locale={locale} />
        </InlineStack>

        <InlineStack gap="100">
          <Text as="p" tone="subdued" variant="bodySm">{t(locale, "productReference")} :</Text>
          <Text as="p" tone="subdued">{row.resource_id}</Text>
        </InlineStack>

        {row.output?.primary_text && (
          <Box background="bg-surface-secondary" padding="300" borderRadius="200">
            <Text as="p" variant="bodyMd">
              {row.output.primary_text}
            </Text>
          </Box>
        )}

        {row.quality && (
          <BlockStack gap="100">
            <Text as="p" tone="subdued">
              {t(locale, "qualityScore")}: {row.quality.score}/100 ({row.quality.label})
            </Text>
            <QualityBar score={row.quality.score} />
          </BlockStack>
        )}

        {hasViolations && (
          <Banner tone="warning" title={t(locale, "blockedReasons")}>
            {check?.forbidden_promise_violations?.map((v: string) => (
              <Text key={v} as="p">{t(locale, "forbiddenPromiseViolations")}: {v}</Text>
            ))}
            {!check?.length_ok && <Text as="p">{t(locale, "lengthOutOfBounds")}</Text>}
            {!check?.language_ok && <Text as="p">{t(locale, "languageMismatch")}</Text>}
          </Banner>
        )}

        <Divider />

        <ButtonGroup>
          {row.status === "approved" ? (
            <fetcher.Form method="post">
              <input type="hidden" name="intent" value="live_apply" />
              <input type="hidden" name="action_id" value={row.action_id} />
              <Button submit variant="primary" loading={submitting}>
                {t(locale, "applyLive")}
              </Button>
            </fetcher.Form>
          ) : (
            !hasViolations && (
              <fetcher.Form method="post">
                <input type="hidden" name="intent" value="decision" />
                <input type="hidden" name="action_id" value={row.action_id} />
                <input type="hidden" name="decision" value="accept" />
                <Button submit variant="primary" loading={submitting}>
                  {t(locale, "acceptAction")}
                </Button>
              </fetcher.Form>
            )
          )}

          <fetcher.Form method="post">
            <input type="hidden" name="intent" value="dry_run" />
            <input type="hidden" name="action_id" value={row.action_id} />
            <Button submit variant="secondary" loading={submitting}>
              {t(locale, "dryRunAction")}
            </Button>
          </fetcher.Form>

          <fetcher.Form method="post">
            <input type="hidden" name="intent" value="decision" />
            <input type="hidden" name="action_id" value={row.action_id} />
            <input type="hidden" name="decision" value="reject" />
            <Button submit tone="critical" variant="plain" loading={submitting}>
              {t(locale, "rejectAction")}
            </Button>
          </fetcher.Form>
        </ButtonGroup>
      </BlockStack>
    </Card>
  );
}

export default function SafeApplyPage() {
  const { queue, locale } = useLoaderData<typeof loader>();

  return (
    <Page title={t(locale, "safeApply")} subtitle={t(locale, "safeApplySubtitle")}>
      <Layout>
        <Layout.Section>
          <Banner tone="info">
            <p>{t(locale, "safeApplyNoBadPublish")}</p>
          </Banner>
        </Layout.Section>
        <Layout.Section>
          {queue.length === 0 ? (
            <EmptyState
              heading={t(locale, "safeApplyEmpty")}
              image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
            >
              <p>{t(locale, "safeApplyEmpty")}</p>
            </EmptyState>
          ) : (
            <BlockStack gap="400">
              {queue.map((row) => (
                <ActionCard key={row.action_id} row={row} locale={locale} />
              ))}
            </BlockStack>
          )}
        </Layout.Section>
      </Layout>
    </Page>
  );
}
