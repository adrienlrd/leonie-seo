/**
 * Onboarding step 1 — zero-click discovery: on mount, kicks the catalog crawl
 * (seo_audit job), then the business-profile analysis, narrated live in the
 * ResearchConsole. Ends with a "mirror" card ("here is what I understood")
 * the merchant confirms to move on. The wow moment comes before any ask.
 */

import { useEffect, useRef, useState } from "react";
import { useFetcher } from "@remix-run/react";
import { Badge, Banner, BlockStack, Box, Button, Card, InlineStack, Text } from "@shopify/polaris";
import { CompassIcon } from "@shopify/polaris-icons";
import { loaderPhrases, t, type Locale } from "../lib/i18n";
import { SectionTitle, type BusinessProfile } from "../lib/marketAnalysisShared";
import { ResearchConsole, type ResearchStep } from "./ResearchConsole";

type DiscoveryResponse = { type: "startDiscovery"; crawlJobId: string | null; error: string | null };
type CrawlPollResponse = { type: "pollCrawlJob"; status: string; error: string | null };
type BizStartResponse = { type: "startBusinessAnalysis"; jobId: string | null; error: string | null };
type BizPollResponse = {
  type: "pollBusinessAnalysis";
  status: string;
  profile: BusinessProfile | null;
  error: string | null;
};

// The crawl is best-effort for the wow moment: past this delay we analyze with
// whatever snapshot exists rather than keeping the merchant waiting.
const CRAWL_TIMEOUT_MS = 90_000;

type Stage = "crawling" | "analyzing" | "done";

interface OnboardingDiscoveryPanelProps {
  locale: Locale;
  /** A previously generated (non-validated) profile — skips straight to the mirror card. */
  existingProfile: BusinessProfile | null;
  onConfirm: (profile: BusinessProfile) => void;
}

export function OnboardingDiscoveryPanel({
  locale,
  existingProfile,
  onConfirm,
}: OnboardingDiscoveryPanelProps) {
  const discoveryFetcher = useFetcher<DiscoveryResponse>();
  const crawlPollFetcher = useFetcher<CrawlPollResponse>();
  const bizStartFetcher = useFetcher<BizStartResponse>();
  const bizPollFetcher = useFetcher<BizPollResponse>();

  const resumable = existingProfile && existingProfile.status !== "validated" ? existingProfile : null;
  const [stage, setStage] = useState<Stage>(resumable ? "done" : "crawling");
  const [profile, setProfile] = useState<BusinessProfile | null>(resumable);
  const [error, setError] = useState<string | null>(null);

  const startedRef = useRef(false);
  const crawlJobIdRef = useRef<string | null>(null);
  const bizJobIdRef = useRef<string | null>(null);
  const crawlStartRef = useRef(Date.now());
  const stageRef = useRef<Stage>(stage);
  stageRef.current = stage;

  // Kick everything off once, with no merchant action.
  useEffect(() => {
    if (startedRef.current || stage !== "crawling") return;
    startedRef.current = true;
    crawlStartRef.current = Date.now();
    const fd = new FormData();
    fd.set("intent", "startDiscovery");
    discoveryFetcher.submit(fd, { method: "post" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const data = discoveryFetcher.data;
    if (!data || data.type !== "startDiscovery") return;
    if (data.crawlJobId) {
      crawlJobIdRef.current = data.crawlJobId;
    } else {
      // Crawl could not start (e.g. already ran) — analyze with what we have.
      startAnalysis();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [discoveryFetcher.data]);

  const startAnalysis = () => {
    if (stageRef.current !== "crawling") return;
    setStage("analyzing");
    const fd = new FormData();
    fd.set("intent", "startBusinessAnalysis");
    bizStartFetcher.submit(fd, { method: "post" });
  };

  // Poll the crawl until it lands (or times out), then chain the analysis.
  useEffect(() => {
    if (stage !== "crawling") return;
    const id = setInterval(() => {
      if (stageRef.current !== "crawling") return;
      if (Date.now() - crawlStartRef.current > CRAWL_TIMEOUT_MS) {
        startAnalysis();
        return;
      }
      if (!crawlJobIdRef.current) return;
      const fd = new FormData();
      fd.set("intent", "pollCrawlJob");
      fd.set("crawlJobId", crawlJobIdRef.current);
      crawlPollFetcher.submit(fd, { method: "post" });
    }, 4_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  useEffect(() => {
    const data = crawlPollFetcher.data;
    if (!data || data.type !== "pollCrawlJob") return;
    if (data.status === "completed" || data.status === "failed") {
      startAnalysis();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [crawlPollFetcher.data]);

  useEffect(() => {
    const data = bizStartFetcher.data;
    if (!data || data.type !== "startBusinessAnalysis") return;
    if (data.jobId) {
      bizJobIdRef.current = data.jobId;
    } else if (data.error) {
      setError(data.error);
    }
  }, [bizStartFetcher.data]);

  useEffect(() => {
    if (stage !== "analyzing") return;
    const id = setInterval(() => {
      if (stageRef.current !== "analyzing" || !bizJobIdRef.current) return;
      const fd = new FormData();
      fd.set("intent", "pollBusinessAnalysis");
      fd.set("bizJobId", bizJobIdRef.current);
      bizPollFetcher.submit(fd, { method: "post" });
    }, 5_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  useEffect(() => {
    const data = bizPollFetcher.data;
    if (!data || data.type !== "pollBusinessAnalysis") return;
    if (data.status === "completed" && data.profile && data.profile.status !== "error") {
      setProfile(data.profile);
      setStage("done");
    } else if (data.status === "failed" || data.status === "unknown") {
      setError(data.error ?? "Analysis failed");
    }
  }, [bizPollFetcher.data]);

  const steps: ResearchStep[] = [
    {
      id: "catalog",
      label: t(locale, "onboardingDiscoveryStepCatalog"),
      state: stage === "crawling" ? "active" : "done",
    },
    {
      id: "market",
      label: t(locale, "onboardingDiscoveryStepMarket"),
      state: stage === "analyzing" ? "active" : stage === "done" ? "done" : "pending",
    },
  ];

  return (
    <Card>
      <BlockStack gap="300">
        <SectionTitle source={CompassIcon}>{t(locale, "onboardingStepDiscoveryTitle")}</SectionTitle>
        <Text as="p" tone="subdued">
          {t(locale, "onboardingStepDiscoveryBody")}
        </Text>

        {error && (
          <Banner tone="critical">
            <Text as="p">{error.split("\n")[0]}</Text>
          </Banner>
        )}

        {stage !== "done" && !error && (
          <Box padding="300" background="bg-surface-secondary" borderRadius="200" width="100%">
            <ResearchConsole
              locale={locale}
              phrases={loaderPhrases(locale, "profile")}
              estimateMs={150_000}
              steps={steps}
            />
          </Box>
        )}

        {stage === "done" && profile && (
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="300">
              <Text as="h3" variant="headingSm">
                {t(locale, "onboardingDiscoveryResultTitle")}
              </Text>
              {profile.brand_name && (
                <Text as="p" fontWeight="semibold">
                  {profile.brand_name}
                </Text>
              )}
              {profile.niche_summary && <Text as="p">{profile.niche_summary}</Text>}
              {(profile.competitor_domains ?? []).length > 0 && (
                <BlockStack gap="100">
                  <Text as="p" variant="bodySm" tone="subdued">
                    {t(locale, "onboardingDiscoveryCompetitors")}
                  </Text>
                  <InlineStack gap="100" wrap>
                    {(profile.competitor_domains ?? []).slice(0, 3).map((domain) => (
                      <Badge key={domain}>{domain}</Badge>
                    ))}
                  </InlineStack>
                </BlockStack>
              )}
              {(profile.key_themes ?? []).length > 0 && (
                <BlockStack gap="100">
                  <Text as="p" variant="bodySm" tone="subdued">
                    {t(locale, "onboardingDiscoveryThemes")}
                  </Text>
                  <InlineStack gap="100" wrap>
                    {(profile.key_themes ?? []).slice(0, 3).map((theme) => (
                      <Badge key={theme} tone="info">
                        {theme}
                      </Badge>
                    ))}
                  </InlineStack>
                </BlockStack>
              )}
              <InlineStack align="end">
                <Button variant="primary" onClick={() => onConfirm(profile)}>
                  {t(locale, "onboardingDiscoveryConfirm")}
                </Button>
              </InlineStack>
            </BlockStack>
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}
