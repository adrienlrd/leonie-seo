# Real-store pilot measurement

## Purpose

Task 82 measures the real-store pilot before the project moves into Phase 10.

The goal is to decide whether the pilot proved the core workflow and what still needs better instrumentation. This report does not invent missing values; unrecorded values are marked as such.

## Data sources

- `docs/pilot-real-store-test-log.md`
- `docs/pilot-real-store-feedback.md`
- `PROGRESS.md`
- Local verification commands recorded during tasks 78-81

Production Render database access was not used for this report, so job-level metrics are limited to what was captured during the pilot pass and retest notes.

## Scorecard

| Dimension | Result | Evidence | Confidence |
|---|---|---|---|
| Install/session stability | Pass | Embedded Shopify Admin workflow passed on 2026-05-16. | High |
| Navigation stability | Pass | Dashboard, Review IA, Niche, Onboarding, Jobs SEO, Billing, Settings and Privacy passed. | High |
| Audit job stability | Pass | Audit job created, crawl completed, products/collections crawled. Exact job ID not recorded. | Medium |
| Niche Intelligence usefulness | Pass | Product clusters appeared from the real catalog. GSC-dependent areas remain deferred. | Medium |
| AI suggestion generation | Pass | Retest note recorded one completed `meta_generation` job with 21 suggestions. 2026-05-16 pass confirmed suggestions generated. | Medium |
| Review workflow | Pass | Approve/reject passed and pending rows updated. | High |
| Dry-run apply workflow | Pass | `bulk_apply` dry-run completed and preview was visible. Exact dry-run job ID not recorded. | Medium |
| Live write safety | Pass | `LEONIE_PILOT_SAFE_MODE=true`, live apply blocked by code and tests, no live write observed in pilot. | High |
| Billing safety | Pass | Billing was blocked during the embedded workflow and protected by pilot-safe tests. | High |
| Privacy/GDPR surface | Pass | Privacy page and embedded Privacy route passed. | High |
| LLM cost | Not fully measured | Budget card exists; local metrics are not the Render pilot metrics. No production cost value was copied into the log. | Low |
| Job IDs and durations | Not fully measured | Jobs were validated visually, but IDs/durations were not recorded. | Low |

## Measured values

| Metric | Value |
|---|---:|
| Public smoke checks passed | 3/3 |
| Embedded workflow areas passed | 13/13 |
| Blocking bugs reported in final pass | 0 |
| Direct UX fixes identified | 1 |
| Direct UX fixes completed | 1 |
| Suggestions generated in recorded retest | 21 |
| Live Shopify writes observed | 0 |
| Billing mutations allowed during pilot | 0 |

## Quality read

The pilot validated the core V1 trust promise:

- the app can run inside the real Shopify Admin;
- it can crawl real catalog data;
- it can generate AI meta suggestions;
- it lets the merchant review and approve/reject;
- it can preview application in dry-run mode;
- it blocks live writes and Billing while pilot-safe is active.

The only product gap directly observed in the pilot pass was wording clarity around pilot-safe mode. That was fixed in task 81.

## Measurement gaps

These values must be captured in the next pilot pass or before go/no-go:

- audit job ID and duration;
- meta generation job ID and duration;
- dry-run job ID and duration;
- exact product and collection counts crawled;
- exact generated / approved / rejected suggestion counts;
- LLM provider, token totals and cost for the pilot shop;
- number of jobs recovered from stale `running` state after the recovery fix.

## Decision

Task 82 can be closed with a pass-with-measurement-gaps decision:

- the pilot is strong enough to move into Phase 10;
- no Phase 9 blocker remains;
- Phase 10 should prioritize real data connectors and app parity, while future pilot passes must record the missing quantitative evidence.
