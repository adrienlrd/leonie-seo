/**
 * Shared "product identification" step: runs (or resumes) the AI product
 * labeling job, lets the merchant review/edit each label, then saves them
 * and kicks off the deep market analysis.
 *
 * Used by the onboarding wizard (app.onboarding.tsx) and can be reused by
 * the dashboard's "re-run analysis" entry point.
 */

import { useEffect, useRef, useState } from "react";
import { useFetcher } from "@remix-run/react";
import { Banner, BlockStack, Box, Button, Card, InlineStack, Text, TextField } from "@shopify/polaris";
import { ProductIcon, RefreshIcon } from "@shopify/polaris-icons";
import { loaderPhrases, t, type Locale } from "../lib/i18n";
import { ResearchConsole } from "./ResearchConsole";
import { SectionTitle, type MarketJobState } from "../lib/marketAnalysisShared";
import { buildIdentificationSteps } from "../lib/researchSteps";

type StartResponse = { type: "startProductAnalysis"; jobId: string | null; error: string | null };
type PollResponse = { type: "pollProductIdentification"; job: MarketJobState | null; error: string | null };
type SaveResponse = { type: "saveProductIdentificationAndStartAnalysis"; productJobId: string | null; error: string | null };

interface ProductIdentificationPanelProps {
  locale: Locale;
  initialJobId?: string | null;
  onSaved: (productJobId: string) => void;
}

export function ProductIdentificationPanel({ locale, initialJobId, onSaved }: ProductIdentificationPanelProps) {
  const startFetcher = useFetcher<StartResponse>();
  const pollFetcher = useFetcher<PollResponse>();
  const saveFetcher = useFetcher<SaveResponse>();

  const [jobId, setJobId] = useState<string | null>(initialJobId ?? null);
  const [job, setJob] = useState<MarketJobState | null>(null);
  const [labels, setLabels] = useState<Record<string, string> | null>(null);
  const [productTitles, setProductTitles] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const jobStatusRef = useRef<string | undefined>(undefined);
  jobStatusRef.current = job?.status;

  const handleStart = () => {
    setError(null);
    setJob(null);
    setLabels(null);
    const fd = new FormData();
    fd.set("intent", "startProductAnalysis");
    startFetcher.submit(fd, { method: "post" });
  };

  useEffect(() => {
    const data = startFetcher.data;
    if (!data || data.type !== "startProductAnalysis") return;
    if (data.jobId) {
      setJobId(data.jobId);
      setJob(null);
    } else if (data.error) {
      setError(data.error);
    }
  }, [startFetcher.data]);

  useEffect(() => {
    const data = pollFetcher.data;
    if (!data || data.type !== "pollProductIdentification") return;
    if (data.error) {
      setJobId(null);
      setError(data.error);
      return;
    }
    if (data.job) setJob(data.job);
    if (data.job?.status === "failed") {
      setJobId(null);
      setError(data.job.error ?? "Identification produits échouée");
    }
    if (data.job?.status === "completed") {
      setJobId(null);
      setLabels(data.job.labels ?? {});
      setProductTitles(data.job.product_titles ?? {});
    }
  }, [pollFetcher.data]);

  useEffect(() => {
    if (!jobId) return;
    const poll = () => {
      if (jobStatusRef.current === "completed" || jobStatusRef.current === "failed") return;
      const fd = new FormData();
      fd.set("intent", "pollProductIdentification");
      fd.set("identifyJobId", jobId);
      pollFetcher.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  useEffect(() => {
    const data = saveFetcher.data;
    if (!data || data.type !== "saveProductIdentificationAndStartAnalysis") return;
    if (data.productJobId) {
      onSaved(data.productJobId);
    } else if (data.error) {
      setError(data.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveFetcher.data]);

  const handleLabelChange = (productId: string, label: string) => {
    setLabels((prev) => ({ ...(prev ?? {}), [productId]: label }));
  };

  const handleConfirm = () => {
    if (!labels) return;
    setError(null);
    const fd = new FormData();
    fd.set("intent", "saveProductIdentificationAndStartAnalysis");
    fd.set("identifications", JSON.stringify(labels));
    saveFetcher.submit(fd, { method: "post" });
  };

  const identifying = jobId !== null || startFetcher.state !== "idle";
  const saving = saveFetcher.state !== "idle";
  const entries = labels ? Object.entries(labels) : [];

  return (
    <Card>
      <BlockStack gap="300">
        <SectionTitle source={ProductIcon}>{t(locale, "onboardingStepProductsTitle")}</SectionTitle>
        <Text as="p" tone="subdued">
          {t(locale, "onboardingStepProductsBody")}
        </Text>

        {error && (
          <Banner tone="critical">
            <Text as="p">{error.split("\n")[0]}</Text>
          </Banner>
        )}

        {!labels && !identifying && (
          <InlineStack align="start">
            <Button variant="primary" icon={RefreshIcon} onClick={handleStart}>
              {t(locale, "onboardingStartProductIdentification")}
            </Button>
          </InlineStack>
        )}

        {identifying && !labels && (
          <Banner tone="info">
            <ResearchConsole
              locale={locale}
              phrases={loaderPhrases(locale, "profile")}
              estimateMs={120_000}
              title={t(locale, "dashboardProductIdentificationRunning")}
              steps={buildIdentificationSteps(locale, job?.status, job?.events)}
              events={job?.events}
            />
          </Banner>
        )}

        {labels && (
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="300">
              <Text as="p" tone="subdued">
                {t(locale, "dashboardReviewProductsBody")}
              </Text>
              {entries.length > 0 ? (
                <BlockStack gap="200">
                  {entries.map(([productId, label]) => (
                    <TextField
                      key={productId}
                      label={productTitles[productId] || productId.slice(-8)}
                      helpText={t(locale, "dashboardProductConcreteLabel")}
                      value={label}
                      onChange={(value) => handleLabelChange(productId, value)}
                      placeholder={t(locale, "marketAnalysisLabelPlaceholder")}
                      autoComplete="off"
                    />
                  ))}
                </BlockStack>
              ) : (
                <Banner tone="warning">
                  <Text as="p">{t(locale, "dashboardNoProductLabels")}</Text>
                </Banner>
              )}
              <InlineStack align="end">
                <Button
                  variant="primary"
                  onClick={handleConfirm}
                  loading={saving}
                  disabled={saving || entries.length === 0}
                >
                  {t(locale, "dashboardConfirmProductsAndAnalyze")}
                </Button>
              </InlineStack>
            </BlockStack>
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}
