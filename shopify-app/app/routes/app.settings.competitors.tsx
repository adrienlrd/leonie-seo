import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import {
  Banner,
  BlockStack,
  Button,
  Card,
  InlineStack,
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import { useEffect, useState } from "react";
import { authenticate } from "../shopify.server";
import { callBackendForShop } from "../lib/api.server";
import { localizedPath, t, type Locale } from "../lib/i18n";
import { resolveLocale } from "../lib/i18n.server";

interface Competitor {
  domain: string;
  url?: string | null;
  note?: string | null;
}

interface LoaderData {
  locale: Locale;
  shop: string;
  competitors: Competitor[];
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const locale = await resolveLocale(request, session.shop, session.accessToken);
  let competitors: Competitor[] = [];
  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/competitors`,
      { accessToken: session.accessToken, method: "GET", signal: AbortSignal.timeout(5_000) },
    );
    if (resp.ok) {
      const data = await resp.json() as { competitors?: Competitor[] };
      competitors = data.competitors ?? [];
    }
  } catch {
    // empty list on error
  }
  return json<LoaderData>({ locale, shop: session.shop, competitors });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const formData = await request.formData();
  const raw = formData.get("competitors") as string;
  let parsed: Competitor[] = [];
  try {
    parsed = JSON.parse(raw) as Competitor[];
  } catch {
    return json({ ok: false, error: "Invalid payload" }, { status: 400 });
  }
  try {
    const resp = await callBackendForShop(
      session.shop,
      `/api/shops/${session.shop}/market-analysis/competitors`,
      {
        accessToken: session.accessToken,
        method: "PUT",
        body: JSON.stringify({ competitors: parsed }),
        signal: AbortSignal.timeout(10_000),
      },
    );
    if (!resp.ok) {
      return json({ ok: false, error: `Backend ${resp.status}` }, { status: 500 });
    }
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: String(err) }, { status: 500 });
  }
};

export default function CompetitorsSettings() {
  const { locale, competitors } = useLoaderData<typeof loader>();
  const fetcher = useFetcher<typeof action>();
  const [items, setItems] = useState<Competitor[]>(competitors);
  const [domain, setDomain] = useState("");
  const [note, setNote] = useState("");
  const [savedBanner, setSavedBanner] = useState(false);

  useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data?.ok) {
      setSavedBanner(true);
      const timer = setTimeout(() => setSavedBanner(false), 2_500);
      return () => clearTimeout(timer);
    }
  }, [fetcher.state, fetcher.data]);

  const persist = (next: Competitor[]) => {
    setItems(next);
    const fd = new FormData();
    fd.append("competitors", JSON.stringify(next));
    fetcher.submit(fd, { method: "POST" });
  };

  const handleAdd = () => {
    const clean = domain.trim();
    if (!clean) return;
    const next = [...items, { domain: clean, note: note.trim() || null }];
    setDomain("");
    setNote("");
    persist(next);
  };

  const handleRemove = (target: string) => {
    persist(items.filter((c) => c.domain !== target));
  };

  return (
    <Page
      title={t(locale, "marketAnalysisCompetitorsTitle")}
    >
      <BlockStack gap="400">
        {savedBanner && (
          <Banner tone="success">
            {t(locale, "marketAnalysisCompetitorsSaved")}
          </Banner>
        )}

        <Card>
          <BlockStack gap="200">
            <Text as="p" variant="bodyMd" tone="subdued">
              {t(locale, "marketAnalysisCompetitorsSubtitle")}
            </Text>
            <TextField
              label={t(locale, "marketAnalysisCompetitorDomain")}
              autoComplete="off"
              value={domain}
              onChange={setDomain}
            />
            <TextField
              label={t(locale, "marketAnalysisCompetitorNote")}
              autoComplete="off"
              value={note}
              onChange={setNote}
            />
            <InlineStack align="end">
              <Button variant="primary" onClick={handleAdd} disabled={!domain.trim()}>
                {t(locale, "marketAnalysisAddCompetitor")}
              </Button>
            </InlineStack>
          </BlockStack>
        </Card>

        {items.length > 0 && (
          <Card>
            <BlockStack gap="200">
              {items.map((c) => (
                <InlineStack key={c.domain} align="space-between" blockAlign="center">
                  <BlockStack gap="050">
                    <Text as="p" variant="bodyMd">{c.domain}</Text>
                    {c.note && (
                      <Text as="p" variant="bodySm" tone="subdued">{c.note}</Text>
                    )}
                  </BlockStack>
                  <Button variant="plain" tone="critical" onClick={() => handleRemove(c.domain)}>
                    {t(locale, "marketAnalysisCompetitorRemove")}
                  </Button>
                </InlineStack>
              ))}
            </BlockStack>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
