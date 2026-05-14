import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useActionData, useLoaderData, useSubmit } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Box,
  Button,
  Card,
  InlineGrid,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";

interface Job {
  id: string;
  queue: string;
  status: string;
  created_at: string;
}

interface LoaderData {
  shop: string;
  jobs: Job[];
}

interface ActionData {
  job_id?: string;
  error?: string;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;

  let jobs: Job[] = [];
  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/jobs?limit=5`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) {
      const data = (await resp.json()) as { jobs: Job[] };
      jobs = data.jobs;
    }
  } catch {
    // Python backend unavailable — show empty state
  }

  return json<LoaderData>({ shop, jobs });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;

  try {
    const resp = await callBackendForShop(shop, "/api/jobs", {
      method: "POST",
      accessToken: session.accessToken,
      body: JSON.stringify({ queue: "seo_audit", shop }),
    });
    const data = (await resp.json()) as { job_id: string };
    return json<ActionData>({ job_id: data.job_id });
  } catch {
    return json<ActionData>({ error: "Impossible de contacter le moteur SEO." });
  }
};

const STATUS_TONE: Record<
  string,
  "success" | "warning" | "critical" | "info"
> = {
  completed: "success",
  pending: "warning",
  running: "info",
  failed: "critical",
};

export default function Index() {
  const { shop, jobs } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const submit = useSubmit();

  return (
    <Page title="Léonie SEO — Dashboard">
      <BlockStack gap="500">
        <InlineGrid columns={["twoThirds", "oneThird"]} gap="400">
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                Boutique
              </Text>
              <Text as="p" tone="subdued">
                {shop}
              </Text>
              <Button
                variant="primary"
                onClick={() => submit({}, { method: "post" })}
              >
                Lancer un audit SEO
              </Button>
              {actionData?.job_id && (
                <Text as="p" tone="success">
                  Audit lancé — job {actionData.job_id.slice(0, 8)}…
                </Text>
              )}
              {actionData?.error && (
                <Text as="p" tone="critical">
                  {actionData.error}
                </Text>
              )}
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                Ressources
              </Text>
              <Text as="p">
                <a href="/app/billing">Gérer l&apos;abonnement →</a>
              </Text>
              <Text as="p">
                <a href="/app/jobs">Voir tous les jobs →</a>
              </Text>
            </BlockStack>
          </Card>
        </InlineGrid>

        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">
              Derniers jobs
            </Text>
            {jobs.length === 0 ? (
              <Text as="p" tone="subdued">
                Aucun job récent. Lancez votre premier audit.
              </Text>
            ) : (
              jobs.map((job) => (
                <Box key={job.id} paddingBlockEnd="200">
                  <InlineGrid columns={["oneThird", "oneThird", "oneThird"]}>
                    <Text as="span" variant="bodyMd">
                      {job.queue}
                    </Text>
                    <Badge tone={STATUS_TONE[job.status] ?? "info"}>
                      {job.status}
                    </Badge>
                    <Text as="span" tone="subdued" variant="bodySm">
                      {job.created_at?.slice(0, 16).replace("T", " ")}
                    </Text>
                  </InlineGrid>
                </Box>
              ))
            )}
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
