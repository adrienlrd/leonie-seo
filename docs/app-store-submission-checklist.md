# Shopify App Store Submission Checklist

> Last updated: 2026-05-17
> Status snapshot: **pilot live on `pilot.leoniedelacroixfrance.com`**, public App Store submission deferred until checklist below is 100 %.

This document is the single source of truth for the App Store submission. Every
item is classified as **✅ Done**, **🔄 In progress**, **⚠️ Blocker**, or
**📋 Manual (Partner Dashboard)**. Code-side items reference the file that
proves the status.

---

## 1. Code & infrastructure (✅ done in repo)

| Item | Status | Evidence |
|---|---|---|
| Embedded Shopify app (App Bridge + Polaris) | ✅ | `shopify-app/app/routes/app.tsx` |
| OAuth install flow + session cookie | ✅ | `@shopify/shopify-app-remix` config in `shopify-app/app/shopify.server.ts` |
| Auth catch-all route | ✅ | `shopify-app/app/routes/auth.$.tsx` |
| Persistent session storage (Postgres) | ✅ | `PostgreSQLSessionStorage` activated when `DATABASE_URL` is present |
| `app/uninstalled` webhook | ✅ | `shopify-app/app/routes/webhooks.tsx` + `app/oauth/webhooks.py` |
| Mandatory GDPR webhooks (`customers/data_request`, `customers/redact`, `shop/redact`) | ✅ | `app/oauth/gdpr.py` (HMAC verified, audit-logged) |
| Webhook HMAC signature verification | ✅ | `app/oauth/hmac_validator.py` |
| OAuth tokens encrypted at rest (Fernet) | ✅ | `app/oauth/crypto.py` — uses `LEONIE_MASTER_KEY` |
| Multi-tenant data isolation | ✅ | All routes resolve shop via `get_shop_context` / `_assert_safe_shop` |
| Shop domain validation (defense-in-depth path traversal) | ✅ | `app/api/deps.py` `_SHOP_DOMAIN_RE` |
| Session token validation in production | ✅ | `LEONIE_REQUIRE_SESSION_TOKEN=true` by default |
| Required env vars validated at startup | ✅ | `app/main.py` `_REQUIRED_ENV` (incl. `INTERNAL_API_SECRET`, `LEONIE_MASTER_KEY`) |
| CORS — credentials false + restricted headers/methods | ✅ | `app/main.py` |
| Privacy policy endpoint (public HTML) | ✅ | `GET /privacy` in `app/api/privacy.py` |
| GDPR data export endpoint | ✅ | `GET /api/gdpr/export` |
| Billing API integration (Shopify subscription) | ✅ | `app/billing/router.py` + `app.billing.tsx` |
| Three pricing tiers (Free / Pro / Agency) defined | ✅ | `app/api/plans.py`, `docs/plans.md` |
| Feature gates per plan | ✅ | `require_feature()` in `app/api/deps.py` |
| Theme App Extension (JSON-LD snippet) | ✅ | `shopify-app/extensions/leonie-seo-jsonld/` |
| Health check endpoint | ✅ | `GET /health` (FastAPI) + `/healthz` (Remix) |
| Pilot deployment on Render | ✅ | `render.yaml` — `leonie-seo-pilot-web` + `leonie-seo-pilot-api` |
| Production webhook subscriptions in `shopify.app.toml` | ✅ | `shopify-app/shopify.app.toml` |
| 6-entry hub navigation (vs 23-flat previously) | ✅ | `shopify-app/app/routes/app.tsx` + 5 hub routes |
| Dashboard with setup progress + alerts + CTAs | ✅ | `shopify-app/app/routes/app._index.tsx` |
| Paginated issue table | ✅ | `shopify-app/app/routes/app.audit.tsx` IndexTable |

## 2. Partner Dashboard configuration (📋 to verify by hand)

The repo cannot manage these — they live in the Shopify Partner Dashboard.
Verify each one before submitting.

| Item | Where | Notes |
|---|---|---|
| **App name** ("Giulio Geo") unique on the App Store | Partner Dashboard → App setup → Name | Must not collide with another app |
| **App URL** = `https://pilot.leoniedelacroixfrance.com` (will change for production app) | App setup → URLs | Use a non-pilot URL when going GA |
| **Allowed redirection URLs** | App setup → URLs | Currently in `shopify.app.pilot.toml` |
| **Access scopes** = `read_products,write_products,write_content,read_themes,write_themes` | App setup → Access scopes | Matches `shopify.app.toml`. `read_orders` removed (unused). `write_themes` is tightly scoped, consented, reversible and audited — see `docs/shopify-write-themes-review-justification.md` (paste its summary into the review notes) |
| **API version** ≥ `2025-01` | App setup → Webhooks | Already set |
| **Embedded** = true | App setup | Already set |
| **App Bridge ≥ 4.x** | Auto via `@shopify/app-bridge-react` | Verify console.log in browser shows "AppBridge 4.x" |
| **GDPR webhooks subscribed** | App setup → Compliance webhooks | URLs declared in `shopify.app.toml` |
| **Webhook delivery** (mandatory webhooks succeed in test) | Apps → Test webhooks | Send all 4 mandatory events, verify 200 OK in API logs |
| **Billing API enabled** | App setup → Distribution | Required for App Store distribution |
| **Distribution = Public (App Store)** | App setup → Distribution | Switch from "Custom distribution" pilot mode |

## 3. App Store listing assets (⚠️ MISSING — blockers)

Required to submit. None are in the repo yet.

| Asset | Spec | Where to place |
|---|---|---|
| **App icon** | 1200×1200 PNG, transparent background, no rounded corners (Shopify rounds them) | `shopify-app/public/icon.png` + upload in Partner Dashboard |
| **App banner** | 1920×1080 JPG/PNG, key visual + tagline | Partner Dashboard → Listing |
| **Feature image** (large banner shown on listing top) | 1600×900 | Partner Dashboard |
| **Screenshots** (3 minimum, 5 recommended) | 1600×900 PNG, embedded admin view | Capture: Dashboard, Hub Audit, Audit IndexTable, Hub Contenu (FAQ), Hub Insights (GA4 funnel) |
| **Demo video** (optional but strongly recommended) | YouTube link, 30-60 s, voice-over OK | Hosted on YouTube |
| **App tagline** (short pitch) | 100 chars max | "SEO Shopify pilote par l'IA : audits, contenu, suivi." |
| **App description** (long) | ~500-2000 words, markdown supported | Cover: problem, audience, key features, integrations, pricing |
| **Categories** | Pick 1-2 from Shopify taxonomy | Suggestion: "Marketing and conversion → SEO" |
| **Keywords** (search) | 5-10 keywords | seo, audit, meta, schema, hreflang, ga4, gsc, pagespeed |

## 4. Required text content (⚠️ to write)

| Text | Length | Status | Source draft |
|---|---|---|---|
| Tagline (FR) | ≤70 chars | 🔄 Drafts ready | `docs/app-store-listing-copy.md` §1 |
| Tagline (EN) | ≤70 chars | 🔄 Drafts ready | `docs/app-store-listing-copy.md` §1 |
| Description courte (FR) | ≤120 chars | 🔄 Drafts ready | `docs/app-store-listing-copy.md` §2 |
| Short description (EN) | ≤120 chars | 🔄 Drafts ready | `docs/app-store-listing-copy.md` §2 |
| Description longue (FR) | ≤2000 chars | 🔄 Draft ready | `docs/app-store-listing-copy.md` §3 |
| Long description (EN) | ≤2000 chars | 🔄 Draft ready | `docs/app-store-listing-copy.md` §3 |
| Key benefits (3-5 bullets) | — | 🔄 Drafts ready | `docs/app-store-listing-copy.md` §4 |
| Categories + keywords | — | 🔄 Drafts ready | `docs/app-store-listing-copy.md` §5 |
| Demo screencast storyboard | 60 s | 🔄 Storyboard ready | `docs/app-store-listing-copy.md` §6 |
| What's new / changelog | ~200 mots | ❌ | À écrire (après la 1ʳᵉ release) |
| Test instructions for the App Store reviewer | ~1500 mots | ✅ Done | `docs/app-store-test-instructions.md` |

## 5. Legal & support (⚠️ partly missing)

| Item | Status | Action |
|---|---|---|
| **Privacy policy URL** (publicly accessible) | ✅ | `https://leonie-seo-pilot-api.onrender.com/privacy` — confirm content covers GDPR + cookies + data retention |
| **Terms of service URL** | ✅ | `GET /terms` (HTML bilingue FR/EN, `app/api/privacy.py`) — clause explicite « aucune garantie de ranking » |
| **Support email** (replied within 24-48 h) | ❌ | À créer (suggestion `support@leoniedelacroix.com`) |
| **Support URL** (FAQ or help center) | 🔄 | `docs/guide-utilisateur.fr.md` existe — à publier publiquement |
| **Emergency developer contact** (Partner Dashboard) | 📋 | À renseigner |
| **Company name / address** (for invoicing) | 📋 | À renseigner dans Partner Dashboard |

## 6. App Store reviewer test plan ✅ Done

Full 11-section reviewer walk-through in `docs/app-store-test-instructions.md`
(install, run audit, browse results, content, billing, GDPR webhooks, uninstall,
privacy/support, known limitations, feedback channel). Copy this verbatim into
the "Test instructions" field of the Partner Dashboard submission form.

## 7. Pre-submission technical validation (🔄 to run)

| Check | Tool | Frequency |
|---|---|---|
| Shopify automated app review checks | Partner Dashboard → "Run checks" | Before each submission |
| Lighthouse perf on `/app` (in iframe) | Chrome DevTools | Once before submission, target Performance ≥ 70 |
| Accessibility audit | axe DevTools | Once before submission, no critical issues |
| Embedded app loads in < 3 s | Network tab | Render free tier has cold starts — consider upgrading |
| Session token validation works | API logs | `LEONIE_REQUIRE_SESSION_TOKEN=true` |
| All 4 mandatory webhooks return 200 | Partner Dashboard → Test webhooks | Send each and check |
| Billing flow end-to-end | Test store with dev billing | Subscribe → cancel → reinstall → resubscribe |
| Demo screencast records cleanly | OBS/Loom | Final asset |

## 8. App Store policies (📋 verify compliance)

Read each at https://shopify.dev/docs/apps/launch/app-requirements-checklist and confirm:

- [ ] No misleading claims ("guaranteed #1 on Google", etc.)
- [ ] No external payments (all monetization via Shopify Billing API)
- [ ] No requests for sensitive PII not needed for the app's function
- [ ] No persistent storage of customer PII outside Shopify Admin (we only store shop-level tokens — confirm)
- [ ] App icon is original, not a generic stock image
- [ ] App functions without leaving the embedded admin (we do open Google OAuth popups — that's allowed)
- [ ] App degrades gracefully when scopes are revoked or backend is down (✅ banners in place)
- [ ] App supports both light and dark Shopify Admin themes (untested — to verify)
- [ ] Translations exist for declared languages (FR + EN ✅)

## 9. Go / no-go decision (Phase 12 task 104)

Before submitting:

- [ ] Sections 1, 2, 3, 4, 5, 6 are all ✅
- [ ] Pilot has been running ≥ 4 weeks without P0 incidents
- [ ] Real merchant feedback collected (already done — see `docs/pilot-real-store-feedback.md`)
- [ ] Pricing strategy locked
- [ ] Support email monitored
- [ ] Submitted to legal review (terms, privacy, billing) — optional but recommended

## 10. Submission workflow (Phase 12 task 105)

1. Switch app distribution to **Public** in Partner Dashboard
2. Upload all assets (§3) + texts (§4)
3. Provide test instructions (§6) + reviewer credentials
4. Click **"Submit for review"**
5. Review delay: typically 5-10 business days. Address feedback iteratively.
6. After approval: app goes live on the App Store. Monitor first 48 h for installs + errors.

---

## Summary

| Section | Status |
|---|---|
| Code & infrastructure | ✅ Ready |
| Partner Dashboard config | 📋 Manual verification |
| **App Store listing assets** | ⚠️ **MISSING — blocker** (icon + 5 screenshots) |
| Required text content | 🔄 Drafts in `docs/app-store-listing-copy.md` |
| Legal & support | ⚠️ Privacy ✅, ToS ✅ (`/terms`), support email ❌ |
| Reviewer test plan | ✅ `docs/app-store-test-instructions.md` |
| Technical validation | 🔄 To run before submission |
| App Store policies | 📋 Self-check |

**Immediate next steps (in order):**
1. Create app icon (1200×1200 PNG) and 5 screenshots — referenced in
   `docs/app-store-listing-copy.md` §6 storyboard
2. Pick one tagline / short / long description from
   `docs/app-store-listing-copy.md` and personalize
3. Set up `support@leoniedelacroix.com` and ensure inbox is monitored
4. Publish a Terms of Service page (route HTML or Notion)
5. Record the 60-second demo screencast following the storyboard
6. Run Shopify automated review checks; fix any failures
7. Switch distribution to Public and submit
