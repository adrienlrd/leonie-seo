# Real-store pilot test plan

## Purpose

Task 79 validates the merchant workflows on the real Léonie Delacroix Shopify store before any public App Store submission.

The goal is not only to prove that pages load. The pilot must answer three product questions:

- Can a merchant understand what the app is doing?
- Can the app produce useful SEO recommendations from the real catalog?
- Can the merchant trust that no Shopify write happens unless explicitly intended?

## Scope

Target store:

- Storefront: `https://www.leoniedelacroix.com`
- Shopify shop: `287c4a-bb.myshopify.com`
- Pilot app origin: `https://pilot.leoniedelacroix.com`
- Backend: `https://leonie-seo-pilot-api.onrender.com`

Required backend posture:

- `LEONIE_REQUIRE_SESSION_TOKEN=true`
- `LEONIE_BILLING_MODE=disabled`
- `LEONIE_PILOT_SAFE_MODE=true`
- `INTERNAL_API_SECRET` shared between Remix and Python
- `LEONIE_MASTER_KEY` set so Shopify tokens are encrypted at rest

## Public smoke checks

These checks do not require Shopify Admin access.

```bash
leonie-seo pilot smoke-public
```

Expected:

- web health returns `ok`;
- API health returns JSON with `status: ok`;
- privacy page returns HTTP 200;
- API `missing_env` is empty or only lists optional provider credentials not used in the current pilot pass.

## Embedded app test checklist

Run these checks from the Shopify Admin for `287c4a-bb.myshopify.com`.

| Area | Steps | Expected result | Notes to capture |
|---|---|---|---|
| Install/session | Open the Léonie SEO Pilot app from Shopify Admin. Refresh once. Navigate away and back. | App loads embedded without OAuth loop; session persists. | Load time, any Shopify frame/session warning. |
| Navigation | Click Dashboard, Review IA, Niche, Onboarding, Jobs SEO, Facturation, Réglages, Confidentialité. | Each route loads on the first click and keeps the Shopify embedded context. | Broken route, route needing multiple clicks, blank page. |
| Settings | Open Réglages. Check backend, shop, snapshot, budget and mode pilote cards. | Backend OK; shop is the real shop; mode pilote shows `Pilot-safe actif`. | Missing env vars, wrong shop, stale snapshot. |
| Onboarding | Open Onboarding. Launch an audit SEO. | Audit job is created; page shows Shopify OK and crawl status updates after completion. | Job ID, duration, product/collection counts. |
| Jobs SEO | Open Jobs SEO during and after the audit. | Job appears as pending/running/completed or failed with a clear error. | Any stuck running job, unclear error, missing result. |
| Niche | Open Niche after a completed audit. | Product clusters appear from the real catalog; empty GSC-dependent areas are explained. | Irrelevant clusters, confusing empty states. |
| Review IA | Click `Générer suggestions IA`. Wait for job completion, then reload Review IA. | Suggestions appear; product/title/description columns stay readable. | Number generated, bad suggestions, layout overflow. |
| Review actions | Approve one suggestion and reject one suggestion. | Approved/rejected rows leave the pending table; approved counter updates. | Any delayed UI feedback or confusing status. |
| Quality audit | Review the quality panel and `À relire` badges. | Reasons are visible enough for a merchant to decide. | Missing or vague quality reason. |
| Dry-run preview | With approved suggestions, click `Prévisualiser l'application`. | A `bulk_apply` dry-run job completes; Jobs SEO shows before/after preview; no Shopify write occurs. | Products shown, source of current SEO, clarity of preview. |
| Pilot-safe write block | Attempt any live write only through a controlled backend/API test, not through UI. | Backend rejects live write with 403 while `LEONIE_PILOT_SAFE_MODE=true`. | Error body and endpoint tested. |
| Billing | Open Facturation. Try Subscribe/Cancel only if visible and safe. | Billing creation is blocked because pilot billing is disabled/pilot-safe. | Button wording, error clarity. |
| Privacy | Open Confidentialité and the public privacy policy link. Trigger GDPR export display. | Privacy page loads; export payload is scoped to the shop; no customer personal data is exposed. | Missing policy link, confusing privacy copy. |

## Pass/fail criteria

Task 79 can be marked complete when all of these are true:

- Every embedded route loads reliably inside Shopify Admin.
- A real audit can be launched and observed through Jobs SEO.
- Review IA can generate, display, approve, reject and dry-run suggestions.
- Niche Intelligence shows real product clusters or clear empty states.
- Settings confirms `Pilot-safe actif`.
- Billing live mutations are blocked in the pilot.
- Privacy/GDPR surfaces load and remain scoped to the shop.
- No live Shopify catalog write is observed during the test.
- Any remaining issue is documented for task 80 or task 81.

## Evidence to record

For each pilot pass, record:

- date and tester;
- browser and Shopify Admin URL;
- audit job ID;
- meta generation job ID;
- dry-run job ID;
- number of products and collections crawled;
- number of IA suggestions generated;
- number approved/rejected;
- any stuck job or failed job result;
- screenshots of unclear UX or risky wording;
- final decision: pass, pass with notes, or fail.

## Known constraints

- GSC, GA4 and PageSpeed workflows are not yet first-class embedded workflows. They are tracked in Phase 10.
- Some Niche views can remain empty until GSC data is connected through the app.
- Render Free services may cold-start; record cold-start delays separately from app bugs.
