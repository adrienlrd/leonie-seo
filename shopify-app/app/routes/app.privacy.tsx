import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  BlockStack,
  Button,
  Card,
  InlineGrid,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { getLocale, localizedPath, t, type Locale } from "../lib/i18n";

interface ExportPayload {
  shop: string;
  exported_at: string;
  data: {
    installation: Record<string, unknown> | null;
    subscription: Record<string, unknown> | null;
    gdpr_requests: Array<Record<string, unknown>>;
  };
}

interface LoaderData {
  locale: Locale;
  privacyUrl: string;
  exportPayload: ExportPayload | null;
  error?: string;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = getLocale(request);
  const backendUrl = process.env.PYTHON_BACKEND_URL || "http://localhost:8000";
  const privacyUrl = `${backendUrl}/privacy`;

  try {
    const resp = await callBackendForShop(shop, `/api/gdpr/export?shop=${shop}`, {
      accessToken: session.accessToken,
    });
    const exportPayload = resp.ok ? ((await resp.json()) as ExportPayload) : null;
    return json<LoaderData>({ locale, privacyUrl, exportPayload });
  } catch {
    return json<LoaderData>({
      locale,
      privacyUrl,
      exportPayload: null,
      error: t(locale, "backendOffline"),
    });
  }
};

export default function Privacy() {
  const { locale, privacyUrl, exportPayload, error } = useLoaderData<typeof loader>();
  const installation = exportPayload?.data.installation;
  const subscription = exportPayload?.data.subscription;

  return (
    <Page title={t(locale, "privacy")} backAction={{ content: t(locale, "backDashboard"), url: localizedPath("/app", locale) }}>
      <BlockStack gap="400">
        {error && (
          <Card>
            <Text as="p" tone="critical">
              {error}
            </Text>
          </Card>
        )}

        <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                {t(locale, "privacyPolicy")}
              </Text>
              <Button url={privacyUrl} target="_blank">
                {t(locale, "openPolicy")}
              </Button>
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                {t(locale, "exportData")}
              </Text>
              <Text as="p" tone="subdued">
                {exportPayload?.exported_at ?? t(locale, "noData")}
              </Text>
            </BlockStack>
          </Card>
        </InlineGrid>

        <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {t(locale, "installation")}
              </Text>
              <Text as="p">Scope: {String(installation?.scope ?? "—")}</Text>
              <Text as="p" tone="subdued">
                {String(installation?.installed_at ?? "—")}
              </Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {t(locale, "billing")}
              </Text>
              <Text as="p">{String(subscription?.plan ?? "free")}</Text>
              <Text as="p" tone="subdued">
                {String(subscription?.status ?? "—")}
              </Text>
            </BlockStack>
          </Card>
        </InlineGrid>
      </BlockStack>
    </Page>
  );
}
