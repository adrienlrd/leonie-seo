import { json, type LoaderFunctionArgs, type ActionFunctionArgs } from "@remix-run/node";
import { useLoaderData, useFetcher } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  Text,
  Badge,
  Button,
  DataTable,
  EmptyState,
  InlineStack,
  BlockStack,
  Banner,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { t, getLocale } from "../lib/i18n";

const API_BASE = process.env.LEONIE_API_BASE ?? "http://localhost:8000";

interface ChangeRow {
  id: number;
  applied_at: string;
  resource_type: string;
  resource_id: string;
  field: string;
  old_value: string | null;
  new_value: string;
  status: string;
  revertible: boolean;
}

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);

  const res = await fetch(`${API_BASE}/api/shops/${shop}/rollback/history?limit=50`).catch(() => null);
  const data = res?.ok ? await res.json().catch(() => ({ changes: [] })) : { changes: [] };

  return json({ shop, changes: (data.changes ?? []) as ChangeRow[], locale });
}

export async function action({ request }: ActionFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const form = await request.formData();
  const changeId = form.get("change_id") as string;
  const dryRun = form.get("dry_run") === "true";

  const res = await fetch(
    `${API_BASE}/api/shops/${shop}/safe-apply/revert?change_id=${changeId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dry_run: dryRun,
        confirm_live_write: !dryRun,
      }),
    },
  ).catch(() => null);

  if (!res?.ok) {
    const err = await res?.json().catch(() => ({}));
    return json({ ok: false, error: err?.detail ?? "Revert failed." });
  }

  return json({ ok: true, result: await res.json() });
}

function StatusBadge({ status }: { status: string }) {
  const tone = status === "applied" ? "success" : status === "reverted" ? "info" : "warning";
  return <Badge tone={tone as "success" | "info" | "warning"}>{status}</Badge>;
}

export default function RollbackHistoryPage() {
  const { changes, locale } = useLoaderData<typeof loader>();
  const fetcher = useFetcher();
  const submitting = fetcher.state !== "idle";
  const result = fetcher.data as { ok?: boolean; result?: { status: string }; error?: string } | undefined;

  const rows = changes.map((row) => [
    <Text key={`date-${row.id}`} as="span" variant="bodySm">
      {new Date(row.applied_at).toLocaleDateString()}
    </Text>,
    <Text key={`field-${row.id}`} as="span" variant="bodySm">
      {row.field}
    </Text>,
    <Text key={`rid-${row.id}`} as="span" variant="bodySm" tone="subdued">
      {row.resource_id.slice(-8)}
    </Text>,
    <Text key={`new-${row.id}`} as="span" variant="bodySm">
      {(row.new_value ?? "").slice(0, 60)}…
    </Text>,
    <StatusBadge key={`status-${row.id}`} status={row.status} />,
    row.revertible ? (
      <fetcher.Form key={`revert-${row.id}`} method="post">
        <input type="hidden" name="change_id" value={String(row.id)} />
        <input type="hidden" name="dry_run" value="false" />
        <Button submit size="slim" tone="critical" loading={submitting}>
          {t(locale, "revertAction")}
        </Button>
      </fetcher.Form>
    ) : (
      <Text key={`no-revert-${row.id}`} as="span" tone="subdued" variant="bodySm">
        —
      </Text>
    ),
  ]);

  return (
    <Page
      title={t(locale, "rollbackHistory")}
      subtitle={t(locale, "rollbackHistorySubtitle")}
    >
      <Layout>
        <Layout.Section>
          {result && !result.ok && (
            <Banner tone="critical" title="Erreur">
              <p>{result.error}</p>
            </Banner>
          )}
          {result?.ok && result.result?.status === "reverted" && (
            <Banner tone="success" title="Modification annulée">
              <p>La valeur précédente a été restaurée dans Shopify.</p>
            </Banner>
          )}

          {changes.length === 0 ? (
            <EmptyState
              heading={t(locale, "rollbackHistory")}
              image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
            >
              <p>Aucune modification enregistrée.</p>
            </EmptyState>
          ) : (
            <Card>
              <DataTable
                columnContentTypes={["text", "text", "text", "text", "text", "text"]}
                headings={["Date", "Champ", "Ressource", "Nouveau contenu", "Statut", "Action"]}
                rows={rows}
              />
            </Card>
          )}
        </Layout.Section>
      </Layout>
    </Page>
  );
}
