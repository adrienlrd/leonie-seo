# Market analysis — data providers

The Market analysis page (`shopify-app/app/routes/app.market-analysis.tsx`)
runs on a layered provider pipeline (`app/market_analysis/providers/`):

1. **Free provider** — always on. Reads from your already-connected sources
   (Shopify snapshot, GSC, GA4, Google Trends) and computes a heuristic
   `free_estimated` difficulty score.
2. **Paid providers** — opt-in. Replace the heuristic scores with real
   monthly volumes, CPC, Ads competition and (later) SERP features.

Every keyword carries the provenance of its data via two fields:

- `data_source` — `gsc`, `ga4`, `trends`, `shopify`, `llm_estimated`,
  `dataforseo`, `google_ads`
- `difficulty_source` — `free_estimated`, `dataforseo`, `google_ads`

These are surfaced as badges on the UI so a merchant can instantly tell a
real number from an estimate.

---

## What works for free, today

| Capability | Source | Notes |
|---|---|---|
| Active product inventory | Shopify | always live |
| Keyword impressions, clicks, position | GSC (if connected) | real per-merchant data |
| Page sessions, conversions, revenue | GA4 (if connected) | real per-merchant data |
| Trending queries proxy | Google Trends (top-5 products) | relative, not absolute volume |
| `demand_score` | GSC impressions bucketed 0–100 | proxy, not search volume |
| `competition_score` | GSC avg position bucketed 0–100 | proxy, not real difficulty |
| Manual competitor list | merchant input via Settings | no SERP automation |
| Content proposals (meta, FAQ, blog, GEO block) | LLM | always generated |

---

## What is estimated (never presented as real)

The following fields stay `None` in free mode and are explicitly rendered
as **"Donnée non disponible en mode gratuit"** on the page — they are
never invented:

- `search_volume`
- `cpc`
- `ads_competition`

For keywords with no GSC overlap, `data_source = "llm_estimated"` and the
UI shows the "IA estimée" badge so the merchant knows the score came
from a model, not a measurement.

---

## What requires a paid provider

| Need | Free mode | Recommended paid mode |
|---|---|---|
| Exact monthly search volume | not available (GSC impressions is a poor proxy) | Google Ads API or DataForSEO |
| CPC | not available | Google Ads API or DataForSEO |
| Google Ads competition index | not available | Google Ads API or DataForSEO |
| 12-month volume history | Google Trends relative only | Google Ads API / DataForSEO |
| Localised Google SERP | not reliable without scraping | DataForSEO SERP Advanced |
| People Also Ask / Featured snippets | not reliable without scraping | DataForSEO SERP Advanced |
| AI Overview detection | not reliable without scraping | DataForSEO SERP Advanced (when supported) |
| Reliable keyword difficulty | heuristic from GSC position | DataForSEO Keyword Difficulty |

**Why no scraping?** A scraper of Google SERPs would breach Google's ToS,
trigger captchas, get the merchant's IP rate-limited, and produce noisy
data. DataForSEO already maintains the proxy/captcha/cache infrastructure
at a marginal cost (~$0.001–0.006 per query) that's hard to beat in-house.

---

## Activating DataForSEO (Keywords Data)

1. Create an account at https://dataforseo.com — get a login + API
   password.
2. Add the following to `.env` (or your hosting platform's env vars):

   ```
   DATAFORSEO_LOGIN=your@email
   DATAFORSEO_PASSWORD=<api password>
   DATAFORSEO_ENABLED=true
   ```
3. Restart the FastAPI backend. The next analysis will:
   - hit `POST /v3/keywords_data/google_ads/search_volume/live` once per
     run, with all unique keywords across all analysed products
   - populate `search_volume`, `cpc`, `ads_competition` on each keyword
   - replace the `free_estimated` difficulty score with a
     `dataforseo`-sourced one

Cost ballpark: ~$0.0005–$0.001 per keyword. For a 50-product analysis
with ~6 keywords each, that's ~$0.15–$0.30 per run.

If the provider call fails for any reason (HTTP error, quota, network),
the analysis continues with free signals only — DataForSEO never blocks
the pipeline.

### What's not yet implemented (TODO paid-provider)

- DataForSEO SERP Advanced → top-10 real competitors per keyword
- DataForSEO SERP → PAA, Featured Snippet, AI Overview detection
- DataForSEO Keyword Difficulty (`/v3/dataforseo_labs/google/bulk_keyword_difficulty/live`)

These are scaffolded in `providers/dataforseo_provider.py` but not yet
exposed. Adding them is a matter of writing a second `_fetch_*` method
and applying the result to `KeywordSignal.difficulty_score` /
`CompetitorSignal`.

---

## Activating the Google Ads Keyword Planner (alternative)

The Google Ads API is *free*, but the activation friction is real: you
need a Google Ads account with active billing or a manager account, and
a developer token approved by Google.

```
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_CUSTOMER_ID=
GOOGLE_ADS_ENABLED=true
```

The provider stub lives at `providers/google_ads_provider.py` — it
reads these env vars, reports `available = False` when anything is
missing, and is a no-op until the real `KeywordPlanIdeaService` call is
plugged in. See the `TODO paid-provider` markers in that file.

---

## Long-term roadmap (TODO future-autopilot)

The V1 stays strictly read-only with merchant validation. Future steps:

1. Human validation gate before any Shopify write (already required by
   AGENTS.md, no exceptions).
2. History of recommendations + before/after comparisons so the merchant
   can audit what changed and why.
3. Semi-automated publication of meta title / meta description / FAQ /
   blog with one-click rollback.
4. Dynamic content rotation (A/B) once trust is established with the
   merchant.
