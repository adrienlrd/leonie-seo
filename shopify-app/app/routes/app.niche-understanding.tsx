import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { Form, useActionData, useLoaderData, useNavigation } from "@remix-run/react";
import { useEffect, useState } from "react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface NicheHypothesis {
  status: string;
  shop_summary: {
    what_you_sell: string;
    primary_niche: string;
    sub_niches: string[];
    languages_detected: string[];
    markets_detected: string[];
  };
  customer_segments: Array<{
    id: string;
    label: string;
    description: string;
    size_estimate: string;
    confidence: string;
  }>;
  buying_motivations: Array<{
    segment_id: string;
    motivation: string;
    evidence: string[];
    confidence: string;
  }>;
  marketing_angles: Array<{
    angle: string;
    for_segment_id: string;
    confidence: string;
  }>;
  conversational_intents: Array<{
    intent: string;
    example_queries: string[];
    confidence: string;
  }>;
  forbidden_promises: Array<{
    promise: string;
    reason: string;
  }>;
  brand_voice: {
    tone: string;
    register: string;
    do_say: string[];
    do_not_say: string[];
    confidence: string;
  };
  global_confidence: string;
  missing_inputs: string[];
}

interface HypothesisResponse {
  available: boolean;
  hypothesis: NicheHypothesis | null;
  history: NicheHypothesis[];
}

interface LoaderData {
  locale: Locale;
  data: HypothesisResponse | null;
  error: string | null;
}

interface ActionData {
  ok: boolean;
  message: string;
}

async function readBackendText(resp: Response): Promise<string> {
  try {
    const data = (await resp.json()) as { detail?: string };
    return data.detail || JSON.stringify(data);
  } catch {
    return resp.text();
  }
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/niche/hypothesis`, {
      accessToken: session.accessToken,
    });
    if (!resp.ok) {
      return json<LoaderData>({ locale, data: null, error: await readBackendText(resp) });
    }
    return json<LoaderData>({
      locale,
      data: (await resp.json()) as HypothesisResponse,
      error: null,
    });
  } catch (err) {
    return json<LoaderData>({ locale, data: null, error: String(err) });
  }
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const form = await request.formData();
  const intent = String(form.get("_action") || "");

  if (intent === "generate") {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/niche/understand`, {
      accessToken: session.accessToken,
      method: "POST",
      body: JSON.stringify({ force_refresh: true, use_llm: true }),
      headers: { "Content-Type": "application/json" },
    });
    if (!resp.ok) {
      return json<ActionData>({ ok: false, message: await readBackendText(resp) });
    }
    return json<ActionData>({ ok: true, message: "Hypothèses générées." });
  }

  const raw = String(form.get("hypothesis_json") || "");
  let hypothesis: NicheHypothesis;
  try {
    hypothesis = JSON.parse(raw) as NicheHypothesis;
  } catch {
    return json<ActionData>({ ok: false, message: "JSON invalide." });
  }
  const status = intent === "validate" ? "validated_by_merchant" : hypothesis.status;
  const resp = await callBackendForShop(shop, `/api/shops/${shop}/niche/hypothesis`, {
    accessToken: session.accessToken,
    method: "PATCH",
    body: JSON.stringify({ hypothesis, status }),
    headers: { "Content-Type": "application/json" },
  });
  if (!resp.ok) {
    return json<ActionData>({ ok: false, message: await readBackendText(resp) });
  }
  return json<ActionData>({
    ok: true,
    message: status === "validated_by_merchant" ? "Hypothèses validées." : "Hypothèses enregistrées.",
  });
};

function confidenceTone(confidence: string): "success" | "warning" | "critical" {
  if (confidence === "high") return "success";
  if (confidence === "medium") return "warning";
  return "critical";
}

function JsonEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <TextField
      label="JSON"
      name="hypothesis_json"
      value={value}
      onChange={onChange}
      multiline={18}
      autoComplete="off"
      monospaced
    />
  );
}

export default function NicheUnderstanding() {
  const { locale, data, error } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();
  const hypothesis = data?.hypothesis;
  const [draftJson, setDraftJson] = useState("");
  const submitting = navigation.state !== "idle";
  const submittingAction = String(navigation.formData?.get("_action") || "");

  useEffect(() => {
    setDraftJson(hypothesis ? JSON.stringify(hypothesis, null, 2) : "");
  }, [hypothesis]);

  return (
    <Page
      title={t(locale, "nicheUnderstanding")}
      backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app/content-hub", locale) }}
    >
      <BlockStack gap="400">
        {actionData && (
          <Banner tone={actionData.ok ? "success" : "warning"}>
            <Text as="p">{actionData.message}</Text>
          </Banner>
        )}
        {error && (
          <Banner tone="warning">
            <Text as="p">{error}</Text>
          </Banner>
        )}

        <Card>
          <BlockStack gap="300">
            <InlineStack align="space-between" blockAlign="center" gap="300" wrap>
              <InlineStack gap="200" blockAlign="center">
                <Badge tone={hypothesis?.status === "validated_by_merchant" ? "success" : "warning"}>
                  {hypothesis?.status ?? "missing"}
                </Badge>
                {hypothesis && (
                  <Badge tone={confidenceTone(hypothesis.global_confidence)}>
                    {hypothesis.global_confidence}
                  </Badge>
                )}
              </InlineStack>
              <InlineStack gap="200">
                <Form method="post">
                  <input type="hidden" name="_action" value="generate" />
                  <Button
                    submit
                    loading={submitting && submittingAction === "generate"}
                    disabled={submitting}
                  >
                    Analyser
                  </Button>
                </Form>
                {hypothesis && (
                  <>
                    <Form method="post">
                      <input type="hidden" name="_action" value="save" />
                      <input type="hidden" name="hypothesis_json" value={draftJson} />
                      <Button
                        submit
                        loading={submitting && submittingAction === "save"}
                        disabled={submitting}
                      >
                        Enregistrer
                      </Button>
                    </Form>
                    <Form method="post">
                      <input type="hidden" name="_action" value="validate" />
                      <input type="hidden" name="hypothesis_json" value={draftJson} />
                      <Button
                        submit
                        variant="primary"
                        loading={submitting && submittingAction === "validate"}
                        disabled={submitting}
                      >
                        Valider
                      </Button>
                    </Form>
                  </>
                )}
              </InlineStack>
            </InlineStack>
            {hypothesis && (
              <JsonEditor value={draftJson} onChange={setDraftJson} />
            )}
          </BlockStack>
        </Card>

        {hypothesis ? (
          <>
            <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
              <Card>
                <BlockStack gap="200">
                  <Text as="h2" variant="headingMd">
                    Boutique
                  </Text>
                  <Text as="p" variant="headingLg">
                    {hypothesis.shop_summary.primary_niche || "-"}
                  </Text>
                  <Text as="p" tone="subdued">
                    {hypothesis.shop_summary.what_you_sell}
                  </Text>
                  <InlineStack gap="100" wrap>
                    {hypothesis.shop_summary.sub_niches.map((item) => (
                      <Badge key={item} tone="info">
                        {item}
                      </Badge>
                    ))}
                  </InlineStack>
                </BlockStack>
              </Card>

              <Card>
                <BlockStack gap="200">
                  <Text as="h2" variant="headingMd">
                    Voix
                  </Text>
                  <Text as="p" variant="headingLg">
                    {hypothesis.brand_voice.register}
                  </Text>
                  <Text as="p" tone="subdued">
                    {hypothesis.brand_voice.tone}
                  </Text>
                  <Badge tone={confidenceTone(hypothesis.brand_voice.confidence)}>
                    {hypothesis.brand_voice.confidence}
                  </Badge>
                </BlockStack>
              </Card>
            </InlineGrid>

            <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="400">
              <Card>
                <BlockStack gap="200">
                  <Text as="h2" variant="headingMd">
                    Clients
                  </Text>
                  {hypothesis.customer_segments.map((segment) => (
                    <BlockStack gap="050" key={segment.id}>
                      <InlineStack align="space-between">
                        <Text as="p" fontWeight="semibold">
                          {segment.label}
                        </Text>
                        <Badge tone={confidenceTone(segment.confidence)}>{segment.confidence}</Badge>
                      </InlineStack>
                      <Text as="p" tone="subdued">
                        {segment.description}
                      </Text>
                    </BlockStack>
                  ))}
                </BlockStack>
              </Card>

              <Card>
                <BlockStack gap="200">
                  <Text as="h2" variant="headingMd">
                    Intentions
                  </Text>
                  {hypothesis.conversational_intents.map((intent) => (
                    <BlockStack gap="050" key={intent.intent}>
                      <InlineStack align="space-between">
                        <Text as="p" fontWeight="semibold">
                          {intent.intent}
                        </Text>
                        <Badge tone={confidenceTone(intent.confidence)}>{intent.confidence}</Badge>
                      </InlineStack>
                      <Text as="p" tone="subdued">
                        {intent.example_queries.join(", ")}
                      </Text>
                    </BlockStack>
                  ))}
                </BlockStack>
              </Card>

              <Card>
                <BlockStack gap="200">
                  <Text as="h2" variant="headingMd">
                    À éviter
                  </Text>
                  {hypothesis.forbidden_promises.length === 0 ? (
                    <Text as="p" tone="subdued">
                      {t(locale, "noData")}
                    </Text>
                  ) : (
                    hypothesis.forbidden_promises.map((item) => (
                      <InlineStack key={item.promise} align="space-between" gap="200">
                        <Text as="span">{item.promise}</Text>
                        <Badge tone="critical">{item.reason}</Badge>
                      </InlineStack>
                    ))
                  )}
                </BlockStack>
              </Card>
            </InlineGrid>
          </>
        ) : (
          <Banner tone="info">
            <Text as="p">{t(locale, "noData")}</Text>
          </Banner>
        )}
      </BlockStack>
    </Page>
  );
}
