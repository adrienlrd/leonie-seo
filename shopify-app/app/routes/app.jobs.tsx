import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Box,
  Card,
  Divider,
  IndexTable,
  InlineStack,
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

interface BulkApplyDetail {
  suggestion_id?: number;
  product_id?: string;
  product_title?: string;
  current_title?: string;
  current_description?: string;
  current_seo_read?: boolean;
  generated_title?: string;
  generated_description?: string;
  dry_run?: boolean;
  action?: string;
  note?: string;
}

interface BulkApplyResult {
  dry_run?: boolean;
  applied?: number;
  skipped?: number;
  errors?: number;
  details?: BulkApplyDetail[];
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

  if (result.dry_run === true && Array.isArray(result.details)) {
    return `Prévisualisation: ${result.details.length} suggestion(s), aucune écriture Shopify`;
  }

  const rows = result.rows;
  const urls = result.urls;
  if (typeof rows === "number" && typeof urls === "number") {
    const regressions = Array.isArray(result.regression_alerts) ? result.regression_alerts.length : 0;
    return `PageSpeed: ${urls} URL(s), ${rows} score(s), ${regressions} régression(s)`;
  }

  const products = result.products;
  const collections = result.collections;
  if (typeof products === "number" || typeof collections === "number") {
    return `${products ?? 0} produits, ${collections ?? 0} collections`;
  }

  return JSON.stringify(result).slice(0, 120);
}

function asBulkPreview(job: Job): BulkApplyResult | null {
  if (job.queue !== "bulk_apply" || typeof job.result !== "object" || job.result === null) {
    return null;
  }
  if (job.result.dry_run !== true || !Array.isArray(job.result.details)) {
    return null;
  }
  return job.result as BulkApplyResult;
}

const PREVIEW_TEXT_STYLE = {
  maxWidth: "560px",
  whiteSpace: "normal",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
} as const;

function PreviewDetails({ job }: { job: Job }) {
  const preview = asBulkPreview(job);
  if (!preview || !preview.details || preview.details.length === 0) {
    return null;
  }

  const details = preview.details.slice(0, 10);
  const remaining = preview.details.length - details.length;

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack gap="200" align="space-between">
          <BlockStack gap="100">
            <Text as="h2" variant="headingMd">
              Prévisualisation d'application
            </Text>
            <Text as="p" tone="subdued">
              Job {job.id.slice(0, 8)} - aucune modification Shopify n'a été faite.
            </Text>
          </BlockStack>
          <Badge tone="info">{`${preview.details.length} suggestion(s)`}</Badge>
        </InlineStack>

        {details.map((detail, index) => (
          <BlockStack gap="200" key={`${job.id}-${detail.suggestion_id ?? index}`}>
            {index > 0 && <Divider />}
            <BlockStack gap="100">
              <Text as="p" variant="bodyMd" fontWeight="bold">
                {detail.product_title || detail.product_id || "Produit"}
              </Text>
              <Badge tone={detail.current_seo_read ? "success" : "warning"}>
                {detail.current_seo_read ? "Avant lu depuis Shopify" : "Avant estimé depuis le crawl"}
              </Badge>
              <div style={PREVIEW_TEXT_STYLE}>
                <Text as="p" tone="subdued">
                  Avant titre: {detail.current_title || "Non renseigné"}
                </Text>
                <Text as="p">Après titre: {detail.generated_title || "Non renseigné"}</Text>
                <Text as="p" tone="subdued">
                  Avant meta description: {detail.current_description || "Non renseignée"}
                </Text>
                <Text as="p">
                  Après meta description: {detail.generated_description || "Non renseignée"}
                </Text>
              </div>
            </BlockStack>
          </BlockStack>
        ))}

        {remaining > 0 && (
          <Text as="p" tone="subdued">
            +{remaining} autre(s) suggestion(s) dans ce dry-run.
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}

export default function Jobs() {
  const { jobs } = useLoaderData<typeof loader>();
  const previewJobs = jobs.filter((job) => asBulkPreview(job) !== null);

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
        {previewJobs.map((job) => (
          <PreviewDetails job={job} key={`preview-${job.id}`} />
        ))}
      </BlockStack>
    </Page>
  );
}
