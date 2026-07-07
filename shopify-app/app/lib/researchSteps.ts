import { t, type Locale } from "./i18n";
import type { ResearchCounter, ResearchJobEvent, ResearchStep } from "../components/ResearchConsole";

type StepState = ResearchStep["state"];

function step(id: string, label: string, state: StepState): ResearchStep {
  return { id, label, state };
}

/** Steps for the full market analysis, derived from job status + engine phase. */
export function buildAnalysisSteps(
  locale: Locale,
  status: string | undefined,
  phase: string | undefined,
): ResearchStep[] {
  const running = status === "running";
  const completed = status === "completed";
  const targeting = running && (phase === undefined || phase === "targeting");
  const content = running && phase === "content";
  return [
    step(
      "collect",
      t(locale, "researchStepDataCollection"),
      running || completed ? "done" : "pending",
    ),
    step(
      "demand",
      t(locale, "researchStepDemand"),
      content || completed ? "done" : targeting ? "active" : "pending",
    ),
    step(
      "competitors",
      t(locale, "researchStepCompetitors"),
      content || completed ? "done" : targeting ? "active" : "pending",
    ),
    step(
      "writing",
      t(locale, "researchStepWriting"),
      completed ? "done" : content ? "active" : "pending",
    ),
    step("quality", t(locale, "researchStepQuality"), completed ? "done" : "pending"),
  ];
}

/** Steps for the competitor crawl, derived from the emitted events. */
export function buildCrawlSteps(
  locale: Locale,
  status: string | undefined,
  events: ResearchJobEvent[] | undefined,
): ResearchStep[] {
  const codes = new Set((events ?? []).map((e) => e.code));
  const completed = status === "completed";
  const fetching = codes.has("competitor_pages_fetching");
  const synthesizing = codes.has("synthesis_writing");
  return [
    step(
      "serp",
      t(locale, "researchStepSerp"),
      fetching || synthesizing || completed ? "done" : "active",
    ),
    step(
      "pages",
      t(locale, "researchStepCompetitorPages"),
      synthesizing || completed ? "done" : fetching ? "active" : "pending",
    ),
    step(
      "synthesis",
      t(locale, "researchStepSynthesis"),
      completed ? "done" : synthesizing ? "active" : "pending",
    ),
  ];
}

/** Steps for the product identification job. */
export function buildIdentificationSteps(
  locale: Locale,
  status: string | undefined,
  events: ResearchJobEvent[] | undefined,
): ResearchStep[] {
  const completed = status === "completed";
  const labeling = (events ?? []).some((e) => e.code === "identification_chunk");
  return [
    step(
      "catalog",
      t(locale, "researchStepCatalogRead"),
      labeling || completed ? "done" : "active",
    ),
    step(
      "labeling",
      t(locale, "researchStepLabeling"),
      completed ? "done" : labeling ? "active" : "pending",
    ),
  ];
}

interface AnalysisJobLike {
  products?: { seo_keywords?: { data_source?: string }[]; geo_questions?: unknown[] }[];
  provider_status?: object;
}

const AI_ESTIMATED_SOURCES = new Set(["llm_estimated", "llm_proposed", "market_seed"]);

/** Effort counters computed from the partial products the job already streamed. */
export function buildAnalysisCounters(locale: Locale, job: AnalysisJobLike): ResearchCounter[] {
  const products = job.products ?? [];
  if (products.length === 0) return [];
  let keywords = 0;
  let realKeywords = 0;
  let geoQuestions = 0;
  for (const product of products) {
    const kws = product.seo_keywords ?? [];
    keywords += kws.length;
    realKeywords += kws.filter(
      (kw) => kw.data_source !== undefined && !AI_ESTIMATED_SOURCES.has(kw.data_source),
    ).length;
    geoQuestions += (product.geo_questions ?? []).length;
  }
  const sources = Object.values(job.provider_status ?? {}).filter(Boolean).length;
  const counters: ResearchCounter[] = [
    { label: t(locale, "researchCounterProducts"), value: String(products.length) },
    { label: t(locale, "researchCounterKeywords"), value: `${realKeywords}/${keywords}` },
    { label: t(locale, "researchCounterGeoQuestions"), value: String(geoQuestions) },
  ];
  if (sources > 0) {
    counters.push({ label: t(locale, "researchCounterSources"), value: String(sources) });
  }
  return counters;
}
