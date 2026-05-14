import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Box,
  Card,
  IndexTable,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";

interface Job {
  id: string;
  queue: string;
  status: string;
  shop: string;
  retries: number;
  result?: Record<string, unknown> | string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

interface LoaderData {
  shop: string;
  jobs: Job[];
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;

  let jobs: Job[] = [];
  try {
    const resp = await callBackendForShop(shop, `/api/shops/${shop}/jobs?limit=50`, {
      accessToken: session.accessToken,
    });
    if (resp.ok) {
      const data = (await resp.json()) as { jobs: Job[] };
      jobs = data.jobs;
    }
  } catch {
    // Python backend unavailable
  }

  return json<LoaderData>({ shop, jobs });
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

function summarizeResult(result: Job["result"]): string {
  if (!result) {
    return "—";
  }
  if (typeof result === "string") {
    return result;
  }

  const error = result.error;
  if (typeof error === "string" && error.length > 0) {
    return error;
  }

  const generated = result.generated;
  const total = result.total;
  const errors = result.errors;
  if (typeof generated === "number" && typeof total === "number") {
    const suffix = typeof errors === "number" && errors > 0 ? `, ${errors} erreurs` : "";
    return `${generated}/${total} générés${suffix}`;
  }

  const products = result.products;
  const collections = result.collections;
  if (typeof products === "number" || typeof collections === "number") {
    return `${products ?? 0} produits, ${collections ?? 0} collections`;
  }

  return JSON.stringify(result).slice(0, 120);
}

export default function Jobs() {
  const { jobs } = useLoaderData<typeof loader>();

  const resourceName = { singular: "job", plural: "jobs" };
  const rowMarkup = jobs.map((job, index) => (
    <IndexTable.Row id={job.id} key={job.id} position={index}>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" fontWeight="bold">
          {job.queue}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Badge tone={STATUS_TONE[job.status] ?? "info"}>{job.status}</Badge>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodySm" tone="subdued">
          {job.retries}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodySm" tone="subdued">
          {summarizeResult(job.result)}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodySm" tone="subdued">
          {job.created_at?.slice(0, 16).replace("T", " ")}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodySm" tone="subdued">
          {job.id.slice(0, 8)}…
        </Text>
      </IndexTable.Cell>
    </IndexTable.Row>
  ));

  return (
    <Page title="Jobs SEO" backAction={{ content: "Dashboard", url: "/app" }}>
      <BlockStack gap="400">
        <Card>
          {jobs.length === 0 ? (
            <Box padding="400">
              <Text as="p" tone="subdued">
                Aucun job. Lancez un audit depuis le dashboard.
              </Text>
            </Box>
          ) : (
            <IndexTable
              resourceName={resourceName}
              itemCount={jobs.length}
              headings={[
                { title: "Queue" },
                { title: "Statut" },
                { title: "Tentatives" },
                { title: "Résultat" },
                { title: "Créé le" },
                { title: "ID" },
              ]}
              selectable={false}
            >
              {rowMarkup}
            </IndexTable>
          )}
        </Card>
      </BlockStack>
    </Page>
  );
}
