import { useState } from "react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  InlineStack,
  Text,
  TextField,
} from "@shopify/polaris";
import { Form, useSubmit, useNavigation } from "@remix-run/react";
import type { Locale } from "../../lib/i18n";
import type { PageSpeedStatus } from "./types";

interface Props {
  locale: Locale;
  pagespeed: PageSpeedStatus | null;
}

/** PageSpeed Insights configuration and on-demand analysis. */
export function PageSpeedCard({ locale, pagespeed }: Props) {
  const submit = useSubmit();
  const navigation = useNavigation();
  const [psApiKey, setPsApiKey] = useState("");
  const fr = locale === "fr";

  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between">
          <Text as="h2" variant="headingMd">
            PageSpeed / Core Web Vitals
          </Text>
          <Badge tone={pagespeed?.available ? "success" : "warning"}>
            {pagespeed?.available
              ? `${pagespeed.url_count} URL(s)`
              : fr ? "À analyser" : "Not analyzed"}
          </Badge>
        </InlineStack>

        {pagespeed?.configured ? (
          <Text as="p" tone="subdued" variant="bodySm">
            {fr
              ? `Clé API configurée (source : ${pagespeed.key_source ?? "env"}) — quota élevé actif.`
              : `API key configured (source: ${pagespeed.key_source ?? "env"}) — high quota active.`}
          </Text>
        ) : (
          <BlockStack gap="200">
            <Text as="p" tone="subdued">
              {fr
                ? "L'analyse fonctionne sans clé (quota réduit). Pour un usage régulier, ajoutez une clé gratuite depuis "
                : "Analysis works without a key (reduced quota). For regular use, add a free key from "}
              <a
                href="https://developers.google.com/speed/docs/insights/v5/get-started"
                target="_blank"
                rel="noreferrer"
              >
                Google Cloud Console
              </a>
              {fr ? " (API PageSpeed Insights → Créer une clé)." : " (PageSpeed Insights API → Create a key)."}
            </Text>
            <Form method="post">
              <input type="hidden" name="intent" value="pagespeed_configure" />
              <BlockStack gap="200">
                <TextField
                  label={fr ? "Clé API PageSpeed (optionnelle)" : "PageSpeed API key (optional)"}
                  value={psApiKey}
                  onChange={setPsApiKey}
                  name="pagespeed_api_key"
                  type="password"
                  autoComplete="off"
                  placeholder="AIzaSy…"
                />
                <Button
                  submit
                  disabled={psApiKey.trim().length === 0}
                  loading={navigation.state !== "idle"}
                >
                  {fr ? "Enregistrer la clé" : "Save key"}
                </Button>
              </BlockStack>
            </Form>
          </BlockStack>
        )}

        {pagespeed?.available && (
          <InlineGrid columns={["oneThird", "oneThird", "oneThird"]} gap="300">
            <Text as="p" tone="subdued">
              {`Mobile : ${
                pagespeed.mobile_average !== null && pagespeed.mobile_average !== undefined
                  ? `${Math.round(pagespeed.mobile_average * 100)}%`
                  : "—"
              }`}
            </Text>
            <Text as="p" tone="subdued">
              {`Desktop : ${
                pagespeed.desktop_average !== null && pagespeed.desktop_average !== undefined
                  ? `${Math.round(pagespeed.desktop_average * 100)}%`
                  : "—"
              }`}
            </Text>
            <Text as="p" tone="subdued">
              {`${fr ? "Alertes" : "Alerts"} : ${pagespeed.alerts.length}`}
            </Text>
          </InlineGrid>
        )}

        <Button
          variant="primary"
          loading={navigation.state !== "idle"}
          onClick={() => submit({ intent: "pagespeed_import" }, { method: "post" })}
        >
          {pagespeed?.available
            ? fr ? "Réanalyser les URLs prioritaires" : "Re-analyze priority URLs"
            : fr ? "Analyser les URLs prioritaires" : "Analyze priority URLs"}
        </Button>

        {(pagespeed?.alerts ?? []).slice(0, 3).map((alert) => (
          <BlockStack gap="100" key={`${alert.url}-${alert.strategy}`}>
            <InlineStack gap="200">
              <Badge tone={alert.severity === "critical" ? "critical" : "warning"}>
                {alert.strategy}
              </Badge>
              <Text as="span" fontWeight="bold">
                {`${Math.round((alert.performance_score ?? 0) * 100)}%`}
              </Text>
              <Text as="span" tone="subdued">
                {alert.url}
              </Text>
            </InlineStack>
            <Text as="p" tone="subdued">
              {alert.recommendations[0] ??
                (fr
                  ? "Revoir les éléments les plus lourds de cette page."
                  : "Review the heaviest elements on this page.")}
            </Text>
          </BlockStack>
        ))}

        {!pagespeed?.available && (
          <Text as="p" tone="subdued">
            {fr
              ? "Lancez une analyse pour mesurer mobile/desktop sur les URLs les plus importantes."
              : "Run an analysis to measure mobile/desktop on the most important URLs."}
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}
