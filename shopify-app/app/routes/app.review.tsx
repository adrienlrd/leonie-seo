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
  error?: string;
}

interface ActionData {
  message?: string;
  error?: string;
}

async function readJson<T>(resp: Response): Promise<T> {
  return (await resp.json()) as T;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/generate/meta/diff?limit=50`, {
      accessToken: session.accessToken,
    });
    if (!resp.ok) {
      return json<LoaderData>({
        locale,
        shop,
        suggestions: [],
        error: `${resp.status}`,
      });
    }
    const suggestions = await readJson<DiffSuggestion[]>(resp);
    return json<LoaderData>({ locale, shop, suggestions });
  } catch {
    return json<LoaderData>({
      locale,
      shop,
      suggestions: [],
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

  try {
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
      const resp = await callBackendForShop(shop, `/api/shops/${shop}/generate/meta/apply`, {
        method: "POST",
        accessToken: session.accessToken,
        body: JSON.stringify({ dry_run: true, max_per_run: 50, delay: 0.5 }),
      });
      if (!resp.ok) {
        return json<ActionData>({ error: `${resp.status}` });
      }
      const data = await readJson<{ job_id: string }>(resp);
      return json<ActionData>({ message: `${t(locale, "jobQueued")} ${data.job_id.slice(0, 8)}` });
    }
  } catch {
    return json<ActionData>({ error: t(locale, "backendOffline") });
  }

  return json<ActionData>({ error: "unknown intent" });
};

function qualityTone(ok: boolean): "success" | "critical" {
  return ok ? "success" : "critical";
}

export default function Review() {
  const { locale, suggestions, error } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();
  const submit = useSubmit();
  const busy = navigation.state !== "idle";

  const rows = suggestions.map((suggestion, index) => (
    <IndexTable.Row id={String(suggestion.suggestion_id)} key={suggestion.suggestion_id} position={index}>
      <IndexTable.Cell>
        <BlockStack gap="100">
          <Text as="span" variant="bodyMd" fontWeight="bold">
            {suggestion.product_title}
          </Text>
          <Text as="span" variant="bodySm" tone="subdued">
            {suggestion.product_id.replace("gid://shopify/Product/", "#")}
          </Text>
        </BlockStack>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodySm">
          {suggestion.generated_title}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodySm" tone="subdued">
          {suggestion.generated_description}
        </Text>
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
            <InlineStack gap="200">
              <Button
                disabled={busy || suggestions.length === 0}
                onClick={() => submit({ intent: "auto-approve" }, { method: "post" })}
              >
                {t(locale, "autoApprove")}
              </Button>
              <Button
                variant="primary"
                disabled={busy}
                onClick={() => submit({ intent: "apply-dry-run" }, { method: "post" })}
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
