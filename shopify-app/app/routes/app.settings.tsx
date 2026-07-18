import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Page,
  Text,
  Select,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { callBackend, callBackendForShop } from "../lib/api.server";
import { localizedPath, t, type Locale } from "../lib/i18n";
import { invalidateLocaleCache } from "../lib/i18n.server";
import { useFetcher } from "@remix-run/react";
import { resolveLocale } from "../lib/i18n.server";

interface LoaderData {
  locale: Locale;
  shop: string;
  backendUrl: string;
  status: Record<string, unknown> | null;
  health: { status: string; missing_env: string[] } | null;
  budget: Record<string, unknown> | null;
  locales: { code: string; name: string }[];
}

async function readIfOk<T>(resp: Response): Promise<T | null> {
  if (!resp.ok) return null;
  return (await resp.json()) as T;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const shop = session.shop;
  const locale = await resolveLocale(request, session.shop, session.accessToken);
  const backendUrl = process.env.PYTHON_BACKEND_URL || "http://localhost:8000";

  let health: LoaderData["health"] = null;
  let status: LoaderData["status"] = null;
  let budget: LoaderData["budget"] = null;
  let locales: LoaderData["locales"] = [];

  try {
    health = await readIfOk(await callBackend("/health"));
    status = await readIfOk(
      await callBackendForShop(shop, `/api/shops/${shop}/status`, {
        accessToken: session.accessToken,
      })
    );
    budget = await readIfOk(
      await callBackendForShop(shop, `/api/shops/${shop}/observability/budget`, {
        accessToken: session.accessToken,
      })
    );
    const localeData = await readIfOk<{ locales: LoaderData["locales"] }>(
      await callBackendForShop(shop, `/api/shops/${shop}/multilingual/locales`, {
        accessToken: session.accessToken,
      })
    );
    locales = localeData?.locales ?? [];
  } catch {
    // Cards render null states.
  }

  return json<LoaderData>({ locale, shop, backendUrl, status, health, budget, locales });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  if (String(form.get("intent")) === "setLanguage") {
    const language = String(form.get("language") ?? "");
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/language`,
      {
        accessToken: session.accessToken,
        method: "PUT",
        body: JSON.stringify({ language }),
        signal: AbortSignal.timeout(10_000),
      },
    );
    if (resp.ok) invalidateLocaleCache(session.shop);
    // Redirect with the new locale so the whole app re-renders in it at once.
    return redirect(localizedPath("/app/settings", language as Locale));
  }
  return json({ ok: false });
};

function LanguageCard({ locale }: { locale: Locale }) {
  const fetcher = useFetcher();
  const options = [
    { label: "Français", value: "fr" },
    { label: "English", value: "en" },
    { label: "Deutsch", value: "de" },
    { label: "Español", value: "es" },
  ];
  return (
    <Card>
      <BlockStack gap="300">
        <Text as="h2" variant="headingMd">
          {t(locale, "languageCardTitle")}
        </Text>
        <Text as="p" tone="subdued">
          {t(locale, "languageCardBody")}
        </Text>
        <Select
          label={t(locale, "languageCardTitle")}
          labelHidden
          options={options}
          value={locale}
          onChange={(value) => {
            const fd = new FormData();
            fd.set("intent", "setLanguage");
            fd.set("language", value);
            fetcher.submit(fd, { method: "post" });
          }}
        />
      </BlockStack>
    </Card>
  );
}

function StateBadge({ ok, locale }: { ok: boolean; locale: Locale }) {
  return (
    <Badge tone={ok ? "success" : "warning"}>
      {ok ? t(locale, "stateReady") : t(locale, "stateToConfigure")}
    </Badge>
  );
}

export default function Settings() {
  const { locale, shop, backendUrl, status, health, budget, locales } =
    useLoaderData<typeof loader>();

  return (
    <Page title={t(locale, "settings")}>
      <BlockStack gap="400">
        <LanguageCard locale={locale} />
        <InlineGrid columns={["oneHalf", "oneHalf"]} gap="400">
          <Card>
            <BlockStack gap="300">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">
                  {t(locale, "shopify")}
                </Text>
                <StateBadge ok={Boolean(status)} locale={locale} />
              </InlineStack>
              <Text as="p">{shop}</Text>
              <Text as="p" tone="subdued">
                {t(locale, "currentPlan")}: {String(status?.plan ?? "free")}
              </Text>
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">
                  {t(locale, "backend")}
                </Text>
                <StateBadge ok={health?.status === "ok"} locale={locale} />
              </InlineStack>
              <Text as="p">{backendUrl}</Text>
              <Text as="p" tone="subdued">
                {health?.missing_env?.length ? health.missing_env.join(", ") : "ok"}
              </Text>
            </BlockStack>
          </Card>
        </InlineGrid>

        <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="400">
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {t(locale, "snapshot")}
              </Text>
              <Badge tone={status?.snapshot_available ? "success" : "warning"}>
                {status?.snapshot_available
                  ? t(locale, "stateReady")
                  : t(locale, "stateToConfigure")}
              </Badge>
              <Text as="p" tone="subdued">
                {String(status?.product_count ?? 0)} {t(locale, "products")} ·{" "}
                {String(status?.collection_count ?? 0)} {t(locale, "collections")}
              </Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {t(locale, "budget")}
              </Text>
              <Text as="p" variant="headingMd">
                {String(budget?.usage_pct ?? 0)}%
              </Text>
              <Text as="p" tone="subdued">
                ${String(budget?.spent_usd ?? 0)} / ${String(budget?.budget_usd ?? 10)}
              </Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                {t(locale, "stgShopifyWrites")}
              </Text>
              <Badge tone="success">
                {t(locale, "stgLiveWritesEnabled")}
              </Badge>
              <Text as="p" tone="subdued">
                {t(locale, "stgLiveWritesDesc")}
              </Text>
              <Text as="p" tone="subdued">
                {t(locale, "locales")}:{" "}
                {locales.map((item) => item.code.toUpperCase()).join(", ") || "-"}
              </Text>
            </BlockStack>
          </Card>
        </InlineGrid>

        <Card>
          <InlineStack align="space-between" blockAlign="center">
            <Text as="h2" variant="headingMd">
              {t(locale, "businessProfileTitle")}
            </Text>
            <Button url={`${localizedPath("/app/onboarding", locale)}&step=2`} size="slim">
              {t(locale, "businessProfileRegenerate")}
            </Button>
          </InlineStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
