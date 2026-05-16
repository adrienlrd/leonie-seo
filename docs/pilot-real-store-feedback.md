# Real-store pilot feedback

## Purpose

Task 80 turns the real-store pilot pass into a product feedback backlog before any priority fixes are started in task 81.

This document records both issues and meaningful non-issues:

- bugs that blocked or slowed the merchant workflow;
- wording that weakened trust or understanding;
- missing evidence that made the pass harder to audit later;
- product gaps that should stay deferred to Phase 10 instead of becoming pilot fixes.

## 2026-05-16 feedback summary

Source:

- `docs/pilot-real-store-test-log.md`, embedded Shopify Admin workflow pass.
- Tester: Adrien.
- Store: `287c4a-bb.myshopify.com`.
- Decision: pass.

Overall result:

- No blocking bug was reported.
- Core trust path passed: audit, crawl, niche clusters, AI suggestions, approve/reject, dry-run preview, Billing blocked, Privacy.
- No live Shopify catalog write was observed or requested during the pilot pass.

## Feedback items

| ID | Area | Severity | Type | Observation | Objective | Proposed task |
|---|---|---:|---|---|---|---|
| P80-001 | Settings | P2 | UX wording | The Settings page state was understood, but the exact expected wording `Mode pilot-safe actif` was not visible. | Make the safety posture immediately recognizable to a merchant before any apply workflow. | Task 81 |
| P80-002 | Test evidence | P3 | Process | Audit, meta generation and dry-run job IDs were validated but not copied into the log. | Make future pilot passes easier to audit and compare. | Keep in the test plan; no app fix required unless repeated. |
| P80-003 | Test evidence | P3 | Process | Product/collection counts and suggestion counts were confirmed as OK but not copied into the log. | Preserve measurable evidence for task 82. | Task 82 measurement pass. |
| P80-004 | Niche / data coverage | P3 | Product gap | GSC-dependent niche areas can remain limited until GSC is connected inside the app. | Avoid treating deferred Phase 10 capabilities as pilot bugs. | Task 83 and 84. |
| P80-005 | Billing | P3 | Trust | Billing was blocked as expected during the pilot. | Preserve this behavior until production billing is intentionally enabled. | No task 81 fix; revalidate before App Store submission. |
| P80-006 | Privacy | P3 | Trust | Privacy passed and stayed available during the embedded workflow. | Preserve GDPR confidence and shop scoping. | No task 81 fix; revalidate before App Store submission. |

## Task 81 resolution

Resolved on 2026-05-16:

- P80-001 fixed in `shopify-app/app/routes/app.settings.tsx`.
- Settings now shows `Mode pilot-safe actif` as the card title when pilot-safe is enabled.
- The badge now says `Écritures live bloquées`.
- Supporting copy states that dry-runs remain allowed and live Shopify writes cannot be sent.
- Verification: `npm run typecheck` and `npm run build` passed in `shopify-app/`.

## Task 81 candidate fix list

Only one direct UX fix was justified from the current feedback:

1. Make the pilot-safe state copy in Settings explicit and stable:
   - show `Mode pilot-safe actif`;
   - explain in one compact line that live Shopify writes are blocked and dry-runs are allowed;
   - keep the real shop identity visible nearby.

No additional task 81 fixes were added based on absent issues. The pilot pass was intentionally clean.

## Deferred to Phase 10

These are not pilot bugs:

- GSC connection inside the app.
- GSC opportunity scoring.
- PageSpeed / Core Web Vitals embedded workflow.
- GA4 revenue attribution.
- Exportable reports.

They remain tracked in Phase 10.

## Decision

Task 80 can be closed: feedback was captured, one UX wording fix was identified for task 81, and non-blocking evidence gaps were separated from product bugs.

Task 81 can be closed: the only direct UX wording fix from the pilot feedback was implemented and verified.
