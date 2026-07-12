# Gemini 3.1 Flash-Lite + Google Search Grounding — Implementation Brief

> **Audience:** Claude Sonnet 5 (or any coding agent) executing this end-to-end.
> **Written:** 2026-07-12, after a read-only exploration of the codebase (findings below are verified with file:line references — re-verify lines before editing, they may have drifted).
> **Language:** talk to Adrien in French; code/commits/comments in English (see AGENTS.md).
> **Read first:** `AGENTS.md`, `docs/AI_HANDOFF.md`, `CLAUDE.md`.

## 0. Goal

Give the **Grande boutique plan** (internal plan id: `agency`, 45 €/month) a real-time edge that the current pipeline cannot provide:

- Detect **live events and rising queries** (e.g. the June/July 2026 canicule in France) and turn them into timely blog ideas ("fontaine pour chat pendant la canicule") and analysis inputs.
- Watch **competitors' current content**.
- Ground keyword/trend claims in **cited, verifiable web sources** — consistent with the project rule "real data > AI estimates, always show sources".

We do NOT replace GPT everywhere. Default model stays `gpt-4o-mini` via the existing router. Gemini-with-grounding is added as a provider and used **only where grounding adds value, only for the `agency` plan**.

## 1. Guide Adrien through Gemini API account + key (do this FIRST, interactively)

Adrien is not a developer. Walk him through, step by step, waiting for his confirmation at each step:

1. Open https://aistudio.google.com/ and sign in with a Google account (his standard Google account works; no Cloud project setup is required for the Gemini Developer API).
2. Click **"Get API key"** (left sidebar) → **"Create API key"**. AI Studio creates the backing project automatically.
3. Copy the key (starts with `AIza…`). It must be pasted into the chat or directly into `.env` — never committed.
4. Free tier notes to tell him: token pricing for `gemini-3.1-flash-lite` is ~$0.25/M input, $1.50/M output; **Google Search grounding: 5,000 grounded prompts/month free**, then $14/1,000 queries (verify current numbers at https://ai.google.dev/gemini-api/docs/pricing). Billing must be enabled in AI Studio for paid tier — but start on free tier.
5. Add to local `.env`: `GEMINI_API_KEY=...` and add the same env var on the **Render API service** (he knows how; it's the same place as `LEONIE_ACCESS_CODE_PRO`).
6. Update `.env.example` with a commented `# GEMINI_API_KEY=` entry (no value).

Reference doc for grounding: https://ai.google.dev/gemini-api/docs/google-search — enable by adding the `google_search` tool; the response carries grounding metadata (queries executed, `url_citation` annotations with source URLs).

## 2. Current architecture — verified facts you must know

### LLM abstraction (`app/llm/`)
- `app/llm/provider.py` — abstract `LLMProvider` (line ~18): class attrs `name`, `model`; single method `complete(prompt, *, system="", max_tokens=512, temperature=0.3, json_mode=False) -> CompletionResult`. `CompletionResult` (line ~9): `text, provider, model, tokens_in, tokens_out`. Errors: `LLMError`, `LLMRateLimitError`, `LLMUnavailableError` — the router falls back on retryable ones.
- `app/llm/__init__.py` — `_build_providers()` (~27-58) builds an ordered provider list from env: `OPENAI_API_KEY` → `OpenAIProvider` (gpt-4o-mini), `GROQ_API_KEY` → Groq, `CF_ACCOUNT_ID`+`CF_API_TOKEN` → Cloudflare. `get_router(*, shop=None)` (~61-79) returns a cached `LLMRouter`. **The cache is a module singleton — mind it when adding tier-based routing.**
- `app/llm/router.py` — `LLMRouter.complete()` (~70-125): ordered fallback + metrics via `record_llm_call`.
- Model provider example to mirror: `app/llm/providers/openai.py` (json_mode via `response_format`, error mapping at ~68-73).

### Where LLM calls happen
- **Blog sections:** `app/blog/section_generator.py:109` → `get_router(shop=shop)`, `.complete(..., json_mode=True)`.
- **Market analysis:** `app/market_analysis/engine.py` — `get_router(shop=shop)` at ~5552, shared helper `_complete_json()` (~5048-5079), two LLM passes per product. Plan gates a USD **budget** and emitted surfaces, NOT the model.
- **Niche understanding:** `app/niche/understanding.py:403-459`. **Only existing plan→tier hook:** line ~417 `plan = get_plan_for_shop(shop)`; line ~418 `tier = "medium" if plan == "free" else "advanced"` — but `tier` is currently **cosmetic** (only stored in `llm_meta`, never passed to the router). This is the pattern to make real.

### Freshness data today (why grounding is needed)
- `app/niche/signals/trends.py` — pytrends `related_queries()` on a **hardcoded 12-month window** (`today 12-m`; also `engine.py:557-558`, `geo="FR"`). Fail-open: errors → `[]`. No `now 1-d`/`now 7-d`, no realtime trending.
- GSC = own-site queries, ~2-3 day lag. DataForSEO = monthly average volumes (opt-in). Google Suggest = completions, no recency signal.
- Blog ideas: `app/blog/idea_generator.py` is **deterministic** (seasonal by calendar month, competitor, advantage, `trend_rising` from the 12-month window — line ~109). `proposed_blog_ideas` flow into `app/blog/auto_draft.py:69-80` and `app/api/blog.py:270`.
- Conclusion (verified): a live event like the canicule is invisible to the current pipeline.

### Plan resolution
- `app/billing/subscription_store.py` → `get_plan_for_shop(shop) -> "free"|"pro"|"agency"` (honors the `plan_override` access-code path). Quotas in `app/billing/quotas.py`.

## 3. Implementation plan (follow in order)

### Step 1 — `GeminiProvider` (`app/llm/providers/gemini.py`)
- Mirror `openai.py`. Use plain `httpx` against the REST endpoint `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=...` (avoid adding the `google-genai` SDK unless Adrien approves a new dependency — AGENTS.md forbids undocumented deps; httpx is already used).
- Model: `gemini-3.1-flash-lite` (constant, overridable via `GEMINI_MODEL` env).
- Constructor flag `grounded: bool` — when True, send `"tools": [{"google_search": {}}]`.
- `json_mode`: use `generationConfig.responseMimeType = "application/json"`. **Caveat:** grounding + forced-JSON can conflict on some model versions; if the API rejects the combination, fall back to prompt-level "answer in JSON" + robust parsing (the codebase already parses LLM JSON defensively in `_complete_json`).
- Map errors: 429 → `LLMRateLimitError`, 5xx/network → `LLMUnavailableError`, else `LLMError`.
- Token counts from `usageMetadata.promptTokenCount` / `candidatesTokenCount`.

### Step 2 — Extend `CompletionResult` with grounding metadata
- Add optional fields (default empty so nothing else breaks): `citations: list[dict]` (each `{url, title, start_index, end_index}`) and `search_queries: list[str]`.
- Populate from Gemini's `groundingMetadata` (`groundingChunks`/`groundingSupports` → url_citations; `webSearchQueries`).
- Do NOT touch other providers — they leave the fields empty.

### Step 3 — Tier-aware routing
- Add parameter `get_router(*, shop=None, tier: str = "default")`. `tier="grounded"` returns a router whose provider list is `[GeminiProvider(grounded=True), <existing default list>]` (fallback preserved: if `GEMINI_API_KEY` is absent or Gemini fails, the call degrades to gpt-4o-mini WITHOUT grounding — analysis must never hard-fail because Gemini is down).
- Cache per tier (`_PROVIDERS_CACHE` → dict keyed by tier).
- Make `app/niche/understanding.py:417-418` real: it stays informational there (no grounding needed for niche hypothesis), but reuse its `get_plan_for_shop` pattern at the new call sites below.

### Step 4 — New realtime-trends signal (the core value)
Create `app/niche/signals/realtime_trends.py`:
- `fetch_realtime_signals(shop, niche_summary, product_titles, competitors, locale="fr") -> RealtimeSignals` where `RealtimeSignals = {events: [...], rising_queries: [...], competitor_moves: [...], citations: [...], fetched_at}`.
- One **single grounded call** per analysis (cost control): prompt asks, in the shop's market/language (geo FR), for (a) current events/seasonal context affecting the niche THIS WEEK (weather, holidays, news), (b) queries/products trending now in the niche, (c) notable recent competitor content — each item with source URLs. `json_mode` with the schema above; keep citations from `CompletionResult.citations`.
- Gate: only call when `get_plan_for_shop(shop) == "agency"` AND `GEMINI_API_KEY` set. Otherwise return `None`.
- Persist the result to `data/raw/{shop}/realtime_signals.json` (same pattern as other artifacts) so the blog page and dashboard can display it with its sources.

### Step 5 — Feed the signal into the pipeline
- **Market analysis pass 1:** in `engine.py`, where `trend_rising`/`trend_top` are injected into `_build_pass1_prompt` (~604+), also inject `realtime_signals` (events + rising queries, with a clear label "REAL-TIME, sourced" so the prompt can prioritize them). Call `fetch_realtime_signals` once per job near the trends fetch (`_fetch_trends_once` ~557).
- **Blog ideas:** in `app/blog/idea_generator.py`, add a `_realtime_ideas()` bucket built from `events × matching products` (e.g. canicule + fontaine à eau chat → "Canicule : garder son chat hydraté avec une fontaine"), placed FIRST in the suggestion order. Deterministic assembly from the signal — no extra LLM call needed.
- **Blog sections (agency only):** in `section_generator.py:109`, resolve plan; for `agency` use `get_router(shop=shop, tier="grounded")` so factual sections can be grounded and their `citations` recorded next to the existing `claims_used` mechanism. Store citations in the draft JSON (`sources` field) and render them in the article footer as "Sources" links (check `app/blog/markdown.py` / draft schema).

### Step 6 — Surface it to the merchant (sell the feature)
- Dashboard (`app._index.tsx`): for agency shops, a small "Tendances temps réel" card (events + rising queries + "il y a X heures" + source links). For pro/free: the same card **locked** 🔒 with "Exclusif Grande boutique — surfez sur les tendances avant vos concurrents" and CTA to `/app/billing`.
- Pricing page (`app.billing.tsx` `planCopy`): add line "Tendances temps réel + veille concurrents (Google Search)" — ✓ agency only, 🔒 others. This differentiates agency from pro (today it's only quotas).
- i18n: FR+EN inline, matching existing dashboard patterns.

### Step 7 — Costs, budget, observability
- Count grounded calls in the existing per-plan USD budget in `engine.py` (~89) — add an estimated cost per grounded call.
- `record_llm_call` already logs provider/model/tokens; verify the Gemini provider flows through it (it will, via the router).
- Rate limit: at most 1 grounded signal fetch per shop per 12h (cache `realtime_signals.json` by `fetched_at`).

### Step 8 — Tests & validation (mandatory before commit)
- `tests/test_llm/`: GeminiProvider — request shape (tools/google_search present when grounded), response parsing incl. groundingMetadata → citations, error mapping (429/5xx), json_mode.
- Router: tier="grounded" ordering; fallback to OpenAI when Gemini raises `LLMUnavailableError`; free/pro shops never trigger a grounded call.
- realtime_trends: agency-gated, cache window, fail-open (Gemini down → None → pipeline unchanged).
- idea_generator: realtime ideas ranked first when signal present.
- Run: `pytest`, `ruff check .`, `cd shopify-app && npm run typecheck && npm run build`.
- Update `docs/AI_HANDOFF.md`. Commit per logical change (Conventional Commits), push on main.

## 4. Non-goals / guardrails
- Do NOT replace gpt-4o-mini for free/pro plans. No behavior change for them at all.
- Do NOT hard-depend on Gemini: every grounded path must degrade gracefully to the current behavior.
- No new pip dependency without asking Adrien (prefer httpx REST).
- Never log or commit the API key. `.env.example` gets the commented var only.
- Grounding output must keep its sources — displaying uncited "web facts" violates the project's data-transparency rule (`feedback_seo_real_data_first`).
