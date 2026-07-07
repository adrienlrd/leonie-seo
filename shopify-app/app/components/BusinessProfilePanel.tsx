/**
 * Shared "business profile" step: launches the AI analysis, polls until
 * complete, lets the merchant review/edit the draft, then saves it and
 * kicks off product identification.
 *
 * Used by the onboarding wizard (app.onboarding.tsx) and can be reused by
 * the dashboard's "re-run analysis" entry point.
 */

import { useEffect, useRef, useState } from "react";
import { useFetcher } from "@remix-run/react";
import {
  Banner,
  BlockStack,
  Box,
  Button,
  Card,
  FormLayout,
  InlineStack,
  Text,
  TextField,
} from "@shopify/polaris";
import { CompassIcon, RefreshIcon } from "@shopify/polaris-icons";
import { loaderPhrases, t, type Locale } from "../lib/i18n";
import { ResearchConsole } from "./ResearchConsole";
import { SectionTitle, linesFromText, textFromLines, type BusinessProfile } from "../lib/marketAnalysisShared";

type StartResponse = { type: "startBusinessAnalysis"; jobId: string | null; error: string | null };
type PollResponse = {
  type: "pollBusinessAnalysis";
  status: string;
  profile: BusinessProfile | null;
  error: string | null;
};
type SaveResponse = {
  type: "saveBusinessProfileAndStartIdentification" | "saveBusinessProfileOnly";
  profile: BusinessProfile | null;
  identifyJobId: string | null;
  error: string | null;
};

interface BusinessProfilePanelProps {
  locale: Locale;
  initialProfile: BusinessProfile | null;
  /** Pre-filled draft (e.g. from the onboarding discovery step) — skips the "run analysis" button. */
  initialDraft?: BusinessProfile | null;
  /** Save the profile without kicking product identification (onboarding reordered flow). */
  saveOnly?: boolean;
  onValidated: (profile: BusinessProfile, identifyJobId: string | null) => void;
}

export function BusinessProfilePanel({
  locale,
  initialProfile,
  initialDraft,
  saveOnly = false,
  onValidated,
}: BusinessProfilePanelProps) {
  const startFetcher = useFetcher<StartResponse>();
  const pollFetcher = useFetcher<PollResponse>();
  const saveFetcher = useFetcher<SaveResponse>();

  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [draft, setDraft] = useState<BusinessProfile | null>(
    initialDraft ?? (initialProfile && initialProfile.status !== "validated" ? initialProfile : null),
  );
  const [error, setError] = useState<string | null>(null);

  const statusRef = useRef<string | null>(null);
  statusRef.current = status;

  const handleStart = () => {
    setError(null);
    setDraft(null);
    setStatus(null);
    const fd = new FormData();
    fd.set("intent", "startBusinessAnalysis");
    startFetcher.submit(fd, { method: "post" });
  };

  useEffect(() => {
    const data = startFetcher.data;
    if (!data || data.type !== "startBusinessAnalysis") return;
    if (data.jobId) {
      setJobId(data.jobId);
      setStatus(null);
    } else if (data.error) {
      setError(data.error);
    }
  }, [startFetcher.data]);

  useEffect(() => {
    const data = pollFetcher.data;
    if (!data || data.type !== "pollBusinessAnalysis") return;
    setStatus(data.status);
    if (data.status === "completed") {
      setJobId(null);
      if (data.profile && data.profile.status !== "error") {
        setDraft(data.profile);
      } else if (data.error) {
        setError(data.error);
      }
    }
    if (data.status === "failed" || data.status === "unknown") {
      setJobId(null);
      if (data.error) setError(data.error);
    }
  }, [pollFetcher.data]);

  useEffect(() => {
    if (!jobId) return;
    const poll = () => {
      if (statusRef.current === "completed" || statusRef.current === "failed") return;
      const fd = new FormData();
      fd.set("intent", "pollBusinessAnalysis");
      fd.set("bizJobId", jobId);
      pollFetcher.submit(fd, { method: "post" });
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  useEffect(() => {
    const data = saveFetcher.data;
    if (
      !data ||
      (data.type !== "saveBusinessProfileAndStartIdentification" &&
        data.type !== "saveBusinessProfileOnly")
    )
      return;
    if (data.profile) {
      onValidated(data.profile, data.identifyJobId ?? null);
    } else if (data.error) {
      setError(data.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveFetcher.data]);

  const handleConfirm = () => {
    if (!draft) return;
    setError(null);
    const fd = new FormData();
    fd.set(
      "intent",
      saveOnly ? "saveBusinessProfileOnly" : "saveBusinessProfileAndStartIdentification",
    );
    fd.set("profileJson", JSON.stringify(draft));
    saveFetcher.submit(fd, { method: "post" });
  };

  const updateDraft = (patch: Partial<BusinessProfile>) => {
    setDraft((prev) => (prev ? { ...prev, ...patch } : prev));
  };

  const analyzing = jobId !== null || startFetcher.state !== "idle";
  const saving = saveFetcher.state !== "idle";

  return (
    <Card>
      <BlockStack gap="300">
        <SectionTitle source={CompassIcon}>{t(locale, "onboardingStepProfileTitle")}</SectionTitle>
        <Text as="p" tone="subdued">
          {t(locale, "onboardingStepProfileBody")}
        </Text>

        {error && (
          <Banner tone="critical">
            <Text as="p">{error.split("\n")[0]}</Text>
          </Banner>
        )}

        {!draft && !analyzing && (
          <InlineStack align="start">
            <Button variant="primary" icon={RefreshIcon} onClick={handleStart}>
              {t(locale, "onboardingStartBusinessAnalysis")}
            </Button>
          </InlineStack>
        )}

        {analyzing && !draft && (
          <Banner tone="info">
            <ResearchConsole
              locale={locale}
              phrases={loaderPhrases(locale, "profile")}
              estimateMs={120_000}
              title={t(locale, "dashboardProfileAnalysisRunning")}
            />
          </Banner>
        )}

        {draft && (
          <Box padding="300" borderWidth="025" borderRadius="200" borderColor="border">
            <BlockStack gap="300">
              <Text as="p" tone="subdued">
                {t(locale, "dashboardReviewProfileBody")}
              </Text>
              <FormLayout>
                <TextField
                  label={t(locale, "dashboardProfileBrandName")}
                  value={draft.brand_name ?? ""}
                  onChange={(value) => updateDraft({ brand_name: value })}
                  autoComplete="off"
                />
                <TextField
                  label={t(locale, "dashboardProfileNiche")}
                  value={draft.niche_summary ?? ""}
                  onChange={(value) => updateDraft({ niche_summary: value })}
                  multiline={3}
                  autoComplete="off"
                />
                <TextField
                  label={t(locale, "dashboardProfileVoice")}
                  value={draft.brand_voice ?? ""}
                  onChange={(value) => updateDraft({ brand_voice: value })}
                  multiline={3}
                  autoComplete="off"
                />
                <TextField
                  label={t(locale, "dashboardProfileCompetitors")}
                  value={textFromLines(draft.competitor_domains)}
                  onChange={(value) => updateDraft({ competitor_domains: linesFromText(value) })}
                  multiline={3}
                  autoComplete="off"
                />
                <TextField
                  label={t(locale, "dashboardProfileThemes")}
                  value={textFromLines(draft.key_themes)}
                  onChange={(value) => updateDraft({ key_themes: linesFromText(value) })}
                  multiline={3}
                  autoComplete="off"
                />
                <TextField
                  label={t(locale, "dashboardProfileCompetitorInsights")}
                  value={textFromLines(draft.competitor_insights)}
                  onChange={(value) => updateDraft({ competitor_insights: linesFromText(value) })}
                  multiline={3}
                  autoComplete="off"
                />
                <TextField
                  label={t(locale, "dashboardProfileContentGaps")}
                  value={textFromLines(draft.content_gaps)}
                  onChange={(value) => updateDraft({ content_gaps: linesFromText(value) })}
                  multiline={3}
                  autoComplete="off"
                />
              </FormLayout>
              <InlineStack align="end">
                <Button variant="primary" onClick={handleConfirm} loading={saving} disabled={saving}>
                  {t(locale, "dashboardConfirmProfileAndContinue")}
                </Button>
              </InlineStack>
            </BlockStack>
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}
