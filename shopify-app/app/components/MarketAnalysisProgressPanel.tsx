/**
 * Shared "deep market analysis" progress step: polls a market-analysis job
 * until completion and reports back via onComplete.
 *
 * Used by the onboarding wizard (app.onboarding.tsx) and can be reused by
 * the dashboard's "re-run analysis" entry point.
 */

import { useEffect, useRef, useState } from "react";
import { useFetcher } from "@remix-run/react";
import { Banner, BlockStack, Card, Text } from "@shopify/polaris";
import { ChartHistogramGrowthIcon } from "@shopify/polaris-icons";
import { loaderPhrases, t, type Locale } from "../lib/i18n";
import { SectionTitle, type MarketJobState } from "../lib/marketAnalysisShared";
import { buildAnalysisCounters, buildAnalysisSteps } from "../lib/researchSteps";
import { ResearchConsole } from "./ResearchConsole";

type PollResponse = { type: "pollProductAnalysis"; job: MarketJobState | null; error: string | null };

interface MarketAnalysisProgressPanelProps {
  locale: Locale;
  jobId: string;
  onComplete: (job: MarketJobState) => void;
}

export function MarketAnalysisProgressPanel({ locale, jobId, onComplete }: MarketAnalysisProgressPanelProps) {
  const pollFetcher = useFetcher<PollResponse>();
  const [job, setJob] = useState<MarketJobState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const statusRef = useRef<string | undefined>(undefined);
  statusRef.current = job?.status;

  useEffect(() => {
    const data = pollFetcher.data;
    if (!data || data.type !== "pollProductAnalysis") return;
    if (data.error) {
      setError(data.error);
      return;
    }
    if (!data.job) return;
    setJob(data.job);
    if (data.job.status === "completed") {
      onComplete(data.job);
    }
    if (data.job.status === "failed") {
      setError(data.job.error ?? "Analyse produits échouée");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollFetcher.data]);

  useEffect(() => {
    const poll = () => {
      if (statusRef.current === "completed" || statusRef.current === "failed") return;
      const fd = new FormData();
      fd.set("intent", "pollProductAnalysis");
      fd.set("productJobId", jobId);
      pollFetcher.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const total = job?.total ?? job?.analyzed_product_count ?? 0;
  const progress = job?.progress ?? job?.analyzed_product_count ?? 0;
  const progressPct = total > 0 ? Math.round((progress / total) * 100) : 15;

  return (
    <Card>
      <BlockStack gap="300">
        <SectionTitle source={ChartHistogramGrowthIcon}>{t(locale, "onboardingStepDeepTitle")}</SectionTitle>
        <Text as="p" tone="subdued">
          {t(locale, "onboardingStepDeepBody")}
        </Text>
        {error && (
          <Banner tone="critical">
            <Text as="p">{error.split("\n")[0]}</Text>
          </Banner>
        )}
        {!error && (
          <Banner tone="info">
            <ResearchConsole
              locale={locale}
              phrases={loaderPhrases(locale, "analysis")}
              progress={total > 0 ? progressPct : undefined}
              estimateMs={420_000}
              title={t(locale, "dashboardProductAnalysisRunning")}
              steps={buildAnalysisSteps(locale, job?.status ?? "running", job?.phase)}
              events={job?.events}
              counters={job ? buildAnalysisCounters(locale, job) : undefined}
            />
          </Banner>
        )}
      </BlockStack>
    </Card>
  );
}
