import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import {
  useActionData,
  useLoaderData,
  useNavigation,
  useSubmit,
} from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Box,
  Button,
  Card,
  Divider,
  IndexTable,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface DiffSuggestion {
  suggestion_id: number;
  product_id: string;
  product_title: string;
  generated_title: string;
  generated_description: string;
  title_length: number;
  desc_length: number;
  passes_quality_check: boolean;
  summary: string;
}

interface LoaderData {
  locale: Locale;
  shop: string;
  suggestions: DiffSuggestion[];
  approvedCount: number;
  error?: string;
}

interface ActionData {
  message?: string;
  error?: string;
}

async function readJson<T>(resp: Response): Promise<T> {
  return (await resp.json()) as T;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function normalizeSuggestion(raw: unknown): DiffSuggestion {
  const row = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    suggestion_id: asNumber(row.suggestion_id),
    product_id: asString(row.product_id),
    product_title: asString(row.product_title),
    generated_title: asString(row.generated_title),
    generated_description: asString(row.generated_description),
    title_length: asNumber(row.title_length),
    desc_length: asNumber(row.desc_length),
    passes_quality_check: row.passes_quality_check === true,
    summary: asString(row.summary) || "ok",
  };
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const [resp, approvedResp] = await Promise.all([
      callBackendForShop(shop, `/api/shops/${shop}/generate/meta/diff?limit=50`, {
        accessToken: session.accessToken,
      }),
      callBackendForShop(
        shop,
        `/api/shops/${shop}/generate/meta/results?status=approved&limit=500`,
        {
          accessToken: session.accessToken,
        }
      ),
    ]);
    if (!resp.ok) {
      return json<LoaderData>({
        locale,
        shop,
        suggestions: [],
        approvedCount: 0,
        error: `${resp.status}`,
      });
    }
    const rawSuggestions = await readJson<unknown>(resp);
    const suggestions = Array.isArray(rawSuggestions)
      ? rawSuggestions.map(normalizeSuggestion)
      : [];
    const approved = approvedResp.ok ? await readJson<unknown[]>(approvedResp) : [];
    return json<LoaderData>({
      locale,
      shop,
      suggestions,
      approvedCount: Array.isArray(approved) ? approved.length : 0,
    });
  } catch {
    return json<LoaderData>({
      locale,
      shop,
      suggestions: [],
      approvedCount: 0,
      error: t(locale, "backendOffline"),
    });
  }
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const form = await request.formData();
  const intent = String(form.get("intent") || "");
  const id = Number(form.get("id"));
  const approvedCount = Number(form.get("approvedCount") || 0);

  try {
    if (intent === "generate-meta") {
      const resp = await callBackendForShop(
        shop,
        `/api/shops/${shop}/generate/meta/from-snapshot`,
        {
          method: "POST",
          accessToken: session.accessToken,
          body: JSON.stringify({ limit: 25, max_workers: 5 }),
        }
      );
      if (!resp.ok) {
        return json<ActionData>({ error: `${resp.status}` });
      }
      const data = await readJson<{ job_id: string; queued: number }>(resp);
      return json<ActionData>({
        message: `${t(locale, "jobQueued")} ${data.job_id.slice(0, 8)} (${data.queued})`,
      });
    }

    if (intent === "approve" || intent === "reject") {
      const body =
        intent === "approve" ? { approve: [id], reject: [] } : { approve: [], reject: [id] };
      const resp = await callBackendForShop(shop, `/api/shops/${shop}/generate/meta/review`, {
        method: "POST",
        accessToken: session.accessToken,
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        return json<ActionData>({ error: `${resp.status}` });
      }
      return json<ActionData>({
        message: intent === "approve" ? t(locale, "approved") : t(locale, "rejected"),
      });
    }

    if (intent === "auto-approve") {
      const resp = await callBackendForShop(
        shop,
        `/api/shops/${shop}/generate/meta/auto-approve`,
        { method: "POST", accessToken: session.accessToken }
      );
      if (!resp.ok) {
        return json<ActionData>({ error: `${resp.status}` });
      }
      const data = await readJson<{ message: string }>(resp);
      return json<ActionData>({ message: data.message });
    }

    if (intent === "apply-dry-run") {
      if (approvedCount <= 0) {
        return json<ActionData>({ error: t(locale, "noApprovedSuggestions") });
      }
      const resp = await callBackendForShop(shop, `/api/shops/${shop}/generate/meta/apply`, {
        method: "POST",
        accessToken: session.accessToken,
        body: JSON.stringify({ dry_run: true, max_per_run: approvedCount, delay: 0.5 }),
      });
      if (!resp.ok) {
        return json<ActionData>({ error: `${resp.status}` });
      }
      const data = await readJson<{ job_id: string }>(resp);
      return json<ActionData>({
        message: `${t(locale, "previewQueued")} ${data.job_id.slice(0, 8)} - ${t(locale, "noShopifyWrite")}`,
      });
    }
  } catch {
    return json<ActionData>({ error: t(locale, "backendOffline") });
  }

  return json<ActionData>({ error: "unknown intent" });
};

function qualityTone(ok: boolean): "success" | "critical" {
  return ok ? "success" : "critical";
}

function averageLength(values: number[]): string {
  const validValues = values.filter((value) => Number.isFinite(value));
  if (validValues.length === 0) {
    return "0";
  }
  const total = validValues.reduce((sum, value) => sum + value, 0);
  return Math.round(total / validValues.length).toString();
}

function collectQualityIssues(suggestions: DiffSuggestion[]): Array<[string, number]> {
  const counts = new Map<string, number>();
  for (const suggestion of suggestions) {
    const summary = suggestion.summary || "ok";
    if (suggestion.passes_quality_check || summary === "ok") {
      continue;
    }
    for (const issue of summary.split("; ").filter(Boolean)) {
      counts.set(issue, (counts.get(issue) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
}

function QualityAudit({
  locale,
  suggestions,
}: {
  locale: Locale;
  suggestions: DiffSuggestion[];
}) {
  const passed = suggestions.filter((suggestion) => suggestion.passes_quality_check).length;
  const needsReview = suggestions.length - passed;
  const averageTitle = averageLength(suggestions.map((suggestion) => suggestion.title_length));
  const averageDescription = averageLength(
    suggestions.map((suggestion) => suggestion.desc_length)
  );
  const issues = collectQualityIssues(suggestions).slice(0, 4);

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack gap="300" align="space-between">
          <Text as="h2" variant="headingMd">
            {t(locale, "qualityAudit")}
          </Text>
          <Text as="span" tone="subdued">
            {suggestions.length} {t(locale, "visibleSuggestions")}
          </Text>
        </InlineStack>

        <InlineStack gap="200">
          <Badge tone="success">{`${passed} ${t(locale, "qualityPassed")}`}</Badge>
          <Badge tone={needsReview > 0 ? "warning" : "success"}>
            {`${needsReview} ${t(locale, "qualityNeedsReview")}`}
          </Badge>
          <Badge tone="info">
            {`${t(locale, "averageLengths")} ${averageTitle}/${averageDescription}`}
          </Badge>
        </InlineStack>

        <Divider />

        <BlockStack gap="100">
          <Text as="p" variant="bodyMd" fontWeight="bold">
            {t(locale, "mainIssues")}
          </Text>
          {issues.length === 0 ? (
            <Text as="p" tone="subdued">
              {t(locale, "noQualityIssues")}
            </Text>
          ) : (
            issues.map(([issue, count]) => (
              <InlineStack gap="200" key={issue} align="start">
                <Badge tone="warning">{String(count)}</Badge>
                <Text as="span" tone="subdued">
                  {issue}
                </Text>
              </InlineStack>
            ))
          )}
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

const PRODUCT_CELL_STYLE = {
  maxWidth: "220px",
  minWidth: "180px",
  whiteSpace: "normal",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
} as const;

const TITLE_CELL_STYLE = {
  maxWidth: "280px",
  whiteSpace: "normal",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
} as const;

const DESCRIPTION_CELL_STYLE = {
  maxWidth: "360px",
  whiteSpace: "normal",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
} as const;

export default function Review() {
  const { locale, suggestions, approvedCount, error } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();
  const submit = useSubmit();
  const busy = navigation.state !== "idle";

  const rows = suggestions.map((suggestion, index) => (
    <IndexTable.Row id={String(suggestion.suggestion_id)} key={suggestion.suggestion_id} position={index}>
      <IndexTable.Cell>
        <div style={PRODUCT_CELL_STYLE}>
          <BlockStack gap="100">
            <Text as="span" variant="bodyMd" fontWeight="bold">
              {suggestion.product_title}
            </Text>
            <Text as="span" variant="bodySm" tone="subdued">
              {suggestion.product_id.replace("gid://shopify/Product/", "#") || "#"}
            </Text>
          </BlockStack>
        </div>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <div style={TITLE_CELL_STYLE}>
          <Text as="span" variant="bodySm">
            {suggestion.generated_title}
          </Text>
        </div>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <div style={DESCRIPTION_CELL_STYLE}>
          <Text as="span" variant="bodySm" tone="subdued">
            {suggestion.generated_description}
          </Text>
        </div>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <BlockStack gap="100">
          <Badge tone={qualityTone(suggestion.passes_quality_check)}>
            {suggestion.passes_quality_check ? "OK" : suggestion.summary}
          </Badge>
          <Text as="span" variant="bodySm" tone="subdued">
            {suggestion.title_length}/{suggestion.desc_length}
          </Text>
        </BlockStack>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <InlineStack gap="200" wrap={false}>
          <Button
            size="slim"
            disabled={busy}
            onClick={() =>
              submit(
                { intent: "approve", id: String(suggestion.suggestion_id) },
                { method: "post" }
              )
            }
          >
            {t(locale, "approve")}
          </Button>
          <Button
            size="slim"
            tone="critical"
            disabled={busy}
            onClick={() =>
              submit(
                { intent: "reject", id: String(suggestion.suggestion_id) },
                { method: "post" }
              )
            }
          >
            {t(locale, "reject")}
          </Button>
        </InlineStack>
      </IndexTable.Cell>
    </IndexTable.Row>
  ));

  return (
    <Page title={t(locale, "review")} backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}>
      <BlockStack gap="400">
        <Card>
          <InlineStack gap="300" align="space-between">
            <Text as="h2" variant="headingMd">
              {t(locale, "pendingSuggestions")}
            </Text>
            <Badge tone={approvedCount > 0 ? "success" : "info"}>
              {`${approvedCount} ${t(locale, "approvedReady")}`}
            </Badge>
            <InlineStack gap="200">
              <Button
                disabled={busy}
                onClick={() => submit({ intent: "generate-meta" }, { method: "post" })}
              >
                {t(locale, "generateMeta")}
              </Button>
              <Button
                disabled={busy || suggestions.length === 0}
                onClick={() => submit({ intent: "auto-approve" }, { method: "post" })}
              >
                {t(locale, "autoApprove")}
              </Button>
              <Button
                variant="primary"
                disabled={busy || approvedCount === 0}
                onClick={() =>
                  submit(
                    { intent: "apply-dry-run", approvedCount: String(approvedCount) },
                    { method: "post" }
                  )
                }
              >
                {t(locale, "dryRunApply")}
              </Button>
            </InlineStack>
          </InlineStack>
        </Card>

        {(actionData?.message || actionData?.error || error) && (
          <Card>
            <Text as="p" tone={actionData?.error || error ? "critical" : "success"}>
              {actionData?.message || actionData?.error || error}
            </Text>
          </Card>
        )}

        {suggestions.length > 0 && <QualityAudit locale={locale} suggestions={suggestions} />}

        <Card>
          {suggestions.length === 0 ? (
            <Box padding="400">
              <Text as="p" tone="subdued">
                {t(locale, "noData")}
              </Text>
            </Box>
          ) : (
            <IndexTable
              resourceName={{ singular: "suggestion", plural: "suggestions" }}
              itemCount={suggestions.length}
              headings={[
                { title: t(locale, "product") },
                { title: t(locale, "title") },
                { title: t(locale, "description") },
                { title: t(locale, "quality") },
                { title: t(locale, "action") },
              ]}
              selectable={false}
            >
              {rows}
            </IndexTable>
          )}
        </Card>
      </BlockStack>
    </Page>
  );
}
