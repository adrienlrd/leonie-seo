import { useEffect, useRef, useState } from "react";
import { BlockStack, Button, Collapsible, Icon, InlineStack, ProgressBar, Text } from "@shopify/polaris";
import { CheckIcon } from "@shopify/polaris-icons";
import { t, type Locale } from "../lib/i18n";

const PHRASE_INTERVAL_MS = 4_000;
const FADE_MS = 350;
// Time-based ramp: asymptotic so the bar never reaches the end while waiting.
const RAMP_TICK_MS = 400;
const RAMP_CEILING = 92;
const REAL_PROGRESS_CAP = 97;
const VISIBLE_EVENTS = 3;

export interface ResearchJobEvent {
  at: string;
  code: string;
  params: Record<string, unknown>;
}

export type ResearchStepState = "done" | "active" | "pending";

export interface ResearchStep {
  id: string;
  label: string;
  state: ResearchStepState;
}

export interface ResearchCounter {
  label: string;
  value: string;
}

export interface ResearchConsoleProps {
  locale: Locale;
  /** Rotating expert status phrases (from loaderPhrases() in lib/i18n). */
  phrases: string[];
  /** Real progress 0-100 when the job reports it; omit for a time-based ramp. */
  progress?: number;
  /** Expected duration of the wait, used by the time-based ramp. */
  estimateMs?: number;
  /** Bold line above the bar (e.g. "Analyse en cours"). */
  title?: string;
  /** Named expert steps checked off live. */
  steps?: ResearchStep[];
  /** Honest activity feed — only events the backend actually emitted. */
  events?: ResearchJobEvent[];
  /** Effort counters (products analyzed, real keywords evaluated…). */
  counters?: ResearchCounter[];
}

/** Translate a backend event code + params into a display line, or null to skip. */
export function formatResearchEvent(locale: Locale, event: ResearchJobEvent): string | null {
  const p = event.params ?? {};
  const str = (key: string) => String(p[key] ?? "");
  switch (event.code) {
    case "sources_connected": {
      const names: string[] = [t(locale, "researchSourceCatalog")];
      if (p.gsc) names.push("Search Console");
      if (p.ga4) names.push("GA4");
      if (p.dataforseo) names.push("DataForSEO");
      if (p.competitor_crawl) names.push(t(locale, "researchSourceCompetitorPages"));
      return t(locale, "researchEventSourcesConnected").replace("{sources}", names.join(" · "));
    }
    case "product_targeted":
      return t(locale, "researchEventProductTargeted")
        .replace("{title}", str("title"))
        .replace("{real}", str("real_keywords"))
        .replace("{keywords}", str("keywords"));
    case "product_content_ready":
      return t(locale, "researchEventProductContent")
        .replace("{title}", str("title"))
        .replace("{geo}", str("geo_questions"));
    case "analysis_completed":
      return t(locale, "researchEventAnalysisCompleted")
        .replace("{products}", str("products"))
        .replace("{keywords}", str("keywords_evaluated"))
        .replace("{sources}", str("sources"));
    case "crawl_started":
      return t(locale, "researchEventCrawlStarted");
    case "serp_analysis":
      return t(locale, "researchEventSerpAnalysis").replace("{competitors}", str("competitors"));
    case "competitor_pages_fetching":
      return t(locale, "researchEventCompetitorPages").replace("{pages}", str("pages"));
    case "synthesis_writing":
      return t(locale, "researchEventSynthesis").replace("{domain}", str("domain"));
    case "crawl_completed":
      return t(locale, "researchEventCrawlCompleted")
        .replace("{pages}", str("pages"))
        .replace("{competitors}", str("competitors"));
    case "identification_chunk":
      return t(locale, "researchEventIdentificationChunk")
        .replace("{done}", str("done"))
        .replace("{total}", str("total"));
    case "identification_completed":
      return t(locale, "researchEventIdentificationCompleted").replace("{count}", str("count"));
    default:
      return null;
  }
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function eventTime(at: string): string {
  const date = new Date(at);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function PulsingDot() {
  return (
    <span
      style={{
        display: "inline-block",
        width: "0.5rem",
        height: "0.5rem",
        borderRadius: "50%",
        background: "var(--p-color-bg-fill-info, #0094d5)",
        animation: "leonie-pulse 1.2s ease-in-out infinite",
        flexShrink: 0,
      }}
    />
  );
}

function StepRow({ step }: { step: ResearchStep }) {
  return (
    <InlineStack gap="200" blockAlign="center" wrap={false}>
      <span style={{ width: "1.25rem", display: "inline-flex", justifyContent: "center" }}>
        {step.state === "done" ? (
          <Icon source={CheckIcon} tone="success" />
        ) : step.state === "active" ? (
          <PulsingDot />
        ) : (
          <span
            style={{
              display: "inline-block",
              width: "0.5rem",
              height: "0.5rem",
              borderRadius: "50%",
              background: "var(--p-color-border, #d5d9de)",
            }}
          />
        )}
      </span>
      <Text
        as="span"
        variant="bodySm"
        tone={step.state === "pending" ? "subdued" : undefined}
        fontWeight={step.state === "active" ? "semibold" : undefined}
      >
        {step.label}
      </Text>
    </InlineStack>
  );
}

/**
 * Deep-research style console for long analyses: named expert steps checked
 * off live, an honest activity feed (backend events only), effort counters and
 * a rotating expert phrase — operational transparency, never invented work.
 */
export function ResearchConsole({
  locale,
  phrases,
  progress,
  estimateMs = 120_000,
  title,
  steps,
  events,
  counters,
}: ResearchConsoleProps) {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [visible, setVisible] = useState(true);
  const [rampProgress, setRampProgress] = useState(5);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [feedOpen, setFeedOpen] = useState(false);
  const startRef = useRef(Date.now());

  useEffect(() => {
    const id = setInterval(() => setElapsedMs(Date.now() - startRef.current), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (phrases.length < 2) return;
    const id = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setPhraseIndex((i) => (i + 1) % phrases.length);
        setVisible(true);
      }, FADE_MS);
    }, PHRASE_INTERVAL_MS);
    return () => clearInterval(id);
  }, [phrases.length]);

  useEffect(() => {
    if (progress !== undefined) return;
    startRef.current = Date.now();
    setRampProgress(5);
    const id = setInterval(() => {
      const elapsed = Date.now() - startRef.current;
      // 1 - exp(-t/τ) ramp: fast start, slows down, never hits the ceiling.
      const ratio = 1 - Math.exp(-elapsed / (estimateMs * 0.62));
      setRampProgress(Math.min(Math.round(5 + ratio * (RAMP_CEILING - 5)), RAMP_CEILING));
    }, RAMP_TICK_MS);
    return () => clearInterval(id);
  }, [progress === undefined, estimateMs]); // eslint-disable-line react-hooks/exhaustive-deps

  const barProgress =
    progress !== undefined ? Math.min(Math.max(Math.round(progress), 2), REAL_PROGRESS_CAP) : rampProgress;

  const feed = (events ?? [])
    .map((event) => ({ event, text: formatResearchEvent(locale, event) }))
    .filter((item): item is { event: ResearchJobEvent; text: string } => item.text !== null)
    .reverse();
  const visibleFeed = feed.slice(0, VISIBLE_EVENTS);
  const hiddenFeed = feed.slice(VISIBLE_EVENTS);

  return (
    <BlockStack gap="300">
      <style>{`@keyframes leonie-pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.35; transform: scale(0.75); } }`}</style>
      <InlineStack align="space-between" blockAlign="center">
        {title ? (
          <Text as="p" fontWeight="semibold">
            {title}
          </Text>
        ) : (
          <span />
        )}
        <Text as="span" tone="subdued" variant="bodySm">
          {formatElapsed(elapsedMs)}
        </Text>
      </InlineStack>
      <ProgressBar progress={barProgress} size="small" tone="highlight" />

      {steps && steps.length > 0 && (
        <BlockStack gap="100">
          {steps.map((step) => (
            <StepRow key={step.id} step={step} />
          ))}
        </BlockStack>
      )}

      {counters && counters.length > 0 && (
        <InlineStack gap="400" wrap>
          {counters.map((counter) => (
            <BlockStack key={counter.label} gap="0">
              <Text as="span" fontWeight="semibold" variant="bodyMd">
                {counter.value}
              </Text>
              <Text as="span" tone="subdued" variant="bodySm">
                {counter.label}
              </Text>
            </BlockStack>
          ))}
        </InlineStack>
      )}

      <div
        style={{
          opacity: visible ? 1 : 0,
          transition: `opacity ${FADE_MS}ms ease`,
          minHeight: "1.25rem",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <PulsingDot />
        <Text as="p" tone="subdued" variant="bodySm">
          {phrases[phraseIndex] ?? ""}
        </Text>
      </div>

      {visibleFeed.length > 0 && (
        <BlockStack gap="100">
          {visibleFeed.map(({ event, text }) => (
            <InlineStack key={`${event.at}-${event.code}`} gap="200" blockAlign="start" wrap={false}>
              <Text as="span" tone="subdued" variant="bodySm">
                {eventTime(event.at)}
              </Text>
              <Text as="span" variant="bodySm">
                {text}
              </Text>
            </InlineStack>
          ))}
          {hiddenFeed.length > 0 && (
            <>
              <Collapsible open={feedOpen} id="research-activity-feed">
                <BlockStack gap="100">
                  {hiddenFeed.map(({ event, text }) => (
                    <InlineStack key={`${event.at}-${event.code}`} gap="200" blockAlign="start" wrap={false}>
                      <Text as="span" tone="subdued" variant="bodySm">
                        {eventTime(event.at)}
                      </Text>
                      <Text as="span" variant="bodySm">
                        {text}
                      </Text>
                    </InlineStack>
                  ))}
                </BlockStack>
              </Collapsible>
              <Button
                variant="plain"
                size="micro"
                onClick={() => setFeedOpen((open) => !open)}
                disclosure={feedOpen ? "up" : "down"}
              >
                {t(locale, feedOpen ? "researchFeedHide" : "researchFeedShowAll").replace(
                  "{n}",
                  String(hiddenFeed.length),
                )}
              </Button>
            </>
          )}
        </BlockStack>
      )}
    </BlockStack>
  );
}
