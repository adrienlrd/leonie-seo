import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useActionData, useLoaderData, useNavigation, useSubmit } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackend, callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface ShopStatus {
  installed: boolean;
  snapshot_available: boolean;
  product_count: number;
  collection_count: number;
  plan: string;
  can_apply: boolean;
}

interface Health {
  status: string;
  missing_env: string[];
}

interface LoaderData {
  locale: Locale;
  shop: string;
  health: Health | null;
  status: ShopStatus | null;
  recentJobs: number;
}

interface ActionData {
  jobId?: string;
  error?: string;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  let health: Health | null = null;
  let status: ShopStatus | null = null;
  let recentJobs = 0;

  try {
    const resp = await callBackend("/health");
    if (resp.ok) health = (await resp.json()) as Health;
  } catch {
    health = null;
  }

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/status`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) status = (await resp.json()) as ShopStatus;
  } catch {
    status = null;
  }

  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/jobs?limit=10`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) {
      const data = (await resp.json()) as { count: number };
      recentJobs = data.count;
    }
  } catch {
    recentJobs = 0;
  }

  return json<LoaderData>({ locale, shop, health, status, recentJobs });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  try {
    const resp = await callBackendForShop(shop, "/api/jobs", {
      method: "POST",
      accessToken: session.accessToken,
      body: JSON.stringify({ queue: "seo_audit" }),
    });
    if (!resp.ok) return json<ActionData>({ error: `${resp.status}` });
    const data = (await resp.json()) as { job_id: string };
    return json<ActionData>({ jobId: data.job_id });
  } catch {
    return json<ActionData>({ error: t(locale, "backendOffline") });
  }
};

function Step({
  label,
  done,
  detail,
}: {
  label: string;
  done: boolean;
  detail?: string;
}) {
  return (
    <InlineStack align="space-between" gap="300">
      <BlockStack gap="050">
        <Text as="span" fontWeight="bold">
          {label}
        </Text>
        {detail && (
          <Text as="span" tone="subdued" variant="bodySm">
            {detail}
          </Text>
        )}
      </BlockStack>
      <Badge tone={done ? "success" : "warning"}>{done ? "OK" : "TODO"}</Badge>
    </InlineStack>
  );
}

export default function Onboarding() {
  const { locale, shop, health, status, recentJobs } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();
  const submit = useSubmit();

  return (
    <Page title={t(locale, "onboarding")} backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}>
      <BlockStack gap="400">
        <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                {t(locale, "installation")}
              </Text>
              <Step label={t(locale, "shopify")} done={Boolean(status?.installed)} detail={shop} />
              <Step
                label={t(locale, "backend")}
                done={health?.status === "ok"}
                detail={health?.missing_env?.length ? health.missing_env.join(", ") : "ok"}
              />
              <Step
                label={t(locale, "crawl")}
                done={Boolean(status?.snapshot_available)}
                detail={`${status?.product_count ?? 0} ${t(locale, "products")}`}
              />
              <Step
                label={t(locale, "billing")}
                done={Boolean(status?.plan)}
                detail={status?.plan ?? "free"}
              />
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                {t(locale, "jobs")}
              </Text>
              <Text as="p" variant="headingLg">
                {recentJobs}
              </Text>
              <Button
                variant="primary"
                loading={navigation.state !== "idle"}
                onClick={() => submit({}, { method: "post" })}
              >
                {t(locale, "launchAudit")}
              </Button>
              {actionData?.jobId && (
                <Text as="p" tone="success">
                  {t(locale, "jobQueued")} {actionData.jobId.slice(0, 8)}
                </Text>
              )}
              {actionData?.error && (
                <Text as="p" tone="critical">
                  {actionData.error}
                </Text>
              )}
            </BlockStack>
          </Card>
        </InlineGrid>
      </BlockStack>
    </Page>
  );
}
