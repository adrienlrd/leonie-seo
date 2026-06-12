import { useEffect, useRef, useState } from "react";
import { BlockStack, ProgressBar, Text } from "@shopify/polaris";

const PHRASE_INTERVAL_MS = 4_000;
const FADE_MS = 350;
// Time-based ramp: asymptotic so the bar never reaches the end while waiting.
const RAMP_TICK_MS = 400;
const RAMP_CEILING = 92;
const REAL_PROGRESS_CAP = 97;

export interface AnalysisLoaderProps {
  /** Rotating vague status phrases (from loaderPhrases() in lib/i18n). */
  phrases: string[];
  /**
   * Real progress 0-100 when the job reports it. Capped at 97 so the bar
   * never looks finished while the job is still running. Omit to use a
   * time-based ramp instead.
   */
  progress?: number;
  /**
   * Expected duration of the wait, used by the time-based ramp: the bar
   * reaches ~80% after estimateMs, then crawls toward 92%.
   */
  estimateMs?: number;
  /** Optional bold line above the bar (e.g. "Analyse en cours"). */
  title?: string;
}

/**
 * Shared loading UI for long generations/analyses: a progress bar with a
 * vague rotating phrase underneath (Claude-thinking / deep-research style).
 */
export function AnalysisLoader({ phrases, progress, estimateMs = 120_000, title }: AnalysisLoaderProps) {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [visible, setVisible] = useState(true);
  const [rampProgress, setRampProgress] = useState(5);
  const startRef = useRef(Date.now());

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

  return (
    <BlockStack gap="200">
      {title && (
        <Text as="p" fontWeight="semibold">
          {title}
        </Text>
      )}
      <ProgressBar progress={barProgress} size="small" tone="highlight" />
      <div
        style={{
          opacity: visible ? 1 : 0,
          transition: `opacity ${FADE_MS}ms ease`,
          minHeight: "1.25rem",
        }}
      >
        <Text as="p" tone="subdued" variant="bodySm">
          {phrases[phraseIndex] ?? ""}
        </Text>
      </div>
    </BlockStack>
  );
}
