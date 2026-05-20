import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useSubmit } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  InlineStack,
  Page,
  ProgressBar,
  Select,
  Text,
  TextField,
} from "@shopify/polaris";
import { useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

type ContentStatus =
  | "draft"
  | "needs_review"
  | "approved"
  | "rejected"
  | "exported"
  | "applied"
  | "reverted";

interface ContentOutput {
  primary_text: string;
  structured: Record<string, unknown> | null;
}

interface ConstraintsCheck {
  length_ok: boolean;
  language_ok: boolean;
  forbidden_promise_violations: string[];
  do_not_say_violations: string[];
}

interface QualityResult {
  score: number;
  label: string;
}

interface LLMMeta {
  tier: string;
  provider: string;
  model: string;
  prompt_version: string;
  cache_hit: boolean;
}

interface ContentActionResult {
  action_id: string;
  content_type: string;
  resource_id: string;
  generated_at: string;
  output: ContentOutput;
  facts_used: { key: string; value: string }[];
  queries_targeted: string[];
  constraints_check: ConstraintsCheck;
  quality: QualityResult;
  status: ContentStatus;
  llm_meta: LLMMeta;
}

interface LoaderData {
  locale: Locale;
  shop: string;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  return json({ locale: getLocale(request), shop: session.shop });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const formData = await request.formData();
  const intent = formData.get("intent") as string;

  if (intent === "run") {
    const contentType = formData.get("content_type") as string;
    const resourceId = formData.get("resource_id") as string;
    const resourceTitle = formData.get("resource_title") as string;
    const plan = formData.get("plan") as string ?? "free";

    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/content-actions/run?plan=${plan}`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify({
            content_type: contentType,
            resource: { id: resourceId, title: resourceTitle, type: "product" },
          }),
        },
      );
      if (!resp.ok) {
        const err = await resp.text();
        return json({ result: null, error: `Backend error ${resp.status}: ${err}` });
      }
      const result: ContentActionResult = await resp.json();
      return json({ result, error: null });
    } catch (err) {
      return json({ result: null, error: String(err) });
    }
  }

  if (intent === "export") {
    const actionId = formData.get("action_id") as string;
    try {
      const resp = await callBackendForShop(
        session.shop,
        `/api/shops/${session.shop}/content-actions/${actionId}/export`,
        {
          accessToken: session.accessToken,
          method: "POST",
          body: JSON.stringify({ format: "json" }),
        },
      );
      const data = await resp.json();
      return json({ exported: data, error: null });
    } catch (err) {
      return json({ exported: null, error: String(err) });
    }
  }

  return json({ error: "Unknown intent" });
};

function statusTone(status: ContentStatus): "success" | "warning" | "critical" | "info" {
  if (status === "approved" || status === "applied") return "success";
  if (status === "needs_review") return "warning";
  if (status === "rejected" || status === "reverted") return "critical";
  return "info";
}

function qualityTone(score: number): "success" | "critical" | "highlight" {
  if (score >= 75) return "success";
  if (score >= 45) return "highlight";
  return "critical";
}

export default function ContentActionsPage() {
  const { locale, shop } = useLoaderData<LoaderData>();
  const submit = useSubmit();

  const [contentType, setContentType] = useState("meta_title");
  const [resourceId, setResourceId] = useState("");
  const [resourceTitle, setResourceTitle] = useState("");
  const [result, setResult] = useState<ContentActionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const contentTypeOptions = [
    { label: "Meta title", value: "meta_title" },
    { label: "Meta description", value: "meta_description" },
    { label: "Description produit", value: "product_description" },
    { label: "Alt text image", value: "alt_text" },
    { label: "FAQ produit", value: "faq_block" },
    { label: "Bloc de réponse", value: "answer_block" },
    { label: "Guide d'achat", value: "buying_guide" },
    { label: "JSON-LD FAQPage", value: "jsonld_faqpage" },
  ];

  const handleRun = () => {
    if (!resourceId || !resourceTitle) return;
    setLoading(true);
    setError(null);
    const fd = new FormData();
    fd.set("intent", "run");
    fd.set("content_type", contentType);
    fd.set("resource_id", resourceId);
    fd.set("resource_title", resourceTitle);
    fd.set("plan", "free");
    submit(fd, { method: "post", replace: true });
    setLoading(false);
  };

  return (
    <Page
      title={t(locale, "contentActions")}
      subtitle={t(locale, "contentActionsSubtitle")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/audit-hub", locale) }}
    >
      <BlockStack gap="400">
        {/* Generation form */}
        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingSm">{t(locale, "contentActionsGenerate")}</Text>
            <Select
              label={t(locale, "contentType")}
              options={contentTypeOptions}
              value={contentType}
              onChange={setContentType}
            />
            <TextField
              label={t(locale, "resourceId")}
              value={resourceId}
              onChange={setResourceId}
              placeholder="gid://shopify/Product/123"
              autoComplete="off"
            />
            <TextField
              label={t(locale, "resourceTitle")}
              value={resourceTitle}
              onChange={setResourceTitle}
              placeholder="Harnais nylon chien"
              autoComplete="off"
            />
            <Button onClick={handleRun} loading={loading} variant="primary">
              {t(locale, "contentActionsRun")}
            </Button>
          </BlockStack>
        </Card>

        {/* Error */}
        {error && (
          <Banner tone="critical">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        {/* Result */}
        {result && (
          <Card>
            <BlockStack gap="300">
              <InlineStack gap="300" align="start">
                <Text as="h3" variant="headingSm">{result.content_type}</Text>
                <Badge tone={statusTone(result.status)}>{result.status}</Badge>
                {result.llm_meta.cache_hit && <Badge tone="info">cache</Badge>}
              </InlineStack>

              {/* Quality */}
              <InlineStack gap="200" align="start">
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "qualityScore")}: {result.quality.score}/100 ({result.quality.label})
                </Text>
              </InlineStack>
              <ProgressBar
                progress={result.quality.score}
                tone={qualityTone(result.quality.score)}
                size="small"
              />

              {/* Violations */}
              {(result.constraints_check.forbidden_promise_violations.length > 0 ||
                result.constraints_check.do_not_say_violations.length > 0) && (
                <Banner tone="warning">
                  <BlockStack gap="100">
                    {result.constraints_check.forbidden_promise_violations.length > 0 && (
                      <Text as="p" variant="bodySm">
                        {t(locale, "forbiddenPromiseViolations")}:{" "}
                        {result.constraints_check.forbidden_promise_violations.join(", ")}
                      </Text>
                    )}
                    {result.constraints_check.do_not_say_violations.length > 0 && (
                      <Text as="p" variant="bodySm">
                        {t(locale, "doNotSayViolations")}:{" "}
                        {result.constraints_check.do_not_say_violations.join(", ")}
                      </Text>
                    )}
                  </BlockStack>
                </Banner>
              )}

              {/* Output */}
              <Box
                padding="300"
                borderWidth="025"
                borderRadius="200"
                borderColor="border"
                background="bg-surface-secondary"
              >
                <Text as="p" variant="bodySm">{result.output.primary_text}</Text>
              </Box>

              {/* Facts used */}
              {result.facts_used.length > 0 && (
                <Text as="p" variant="bodySm" tone="subdued">
                  {t(locale, "factsUsed")}: {result.facts_used.map((f) => f.key).join(", ")}
                </Text>
              )}

              {/* LLM meta */}
              <Text as="p" variant="bodySm" tone="subdued">
                {result.llm_meta.provider} / {result.llm_meta.model} (v{result.llm_meta.prompt_version})
              </Text>
            </BlockStack>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
