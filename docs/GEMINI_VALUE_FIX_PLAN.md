# Gemini Grounding — Value Fix Plan

> **Audience:** Claude Sonnet 5 executing this end-to-end.
> **Written:** 2026-07-15 by Fable 5, after analyzing `Ananlyse_json/Comparaison de plan, 15 juil 2026.json`.
> **Language:** talk to Adrien in French; code/commits/comments in English (AGENTS.md).
> **Read first:** `AGENTS.md`, `docs/AI_HANDOFF.md` (sections Gemini + live smoke test), `docs/GEMINI_GROUNDING_IMPLEMENTATION.md` (original brief).

## 0. Problem statement (verified from the comparison export)

The Pro vs Grande boutique comparison (button « Analyse test ») produced **identical results** for both plans (modulo the product cap 2 vs 3). `agency.realtime_grounding_used = False` — the grounding never ran. Even if it had run, its only effect today is one context line in the pass-1 prompt: it verifies nothing, boosts nothing, and leaves no trace in the output.

Adrien's goal, restated: **the Gemini layer must (a) verify keyword/content data against the real market, (b) add a real-world/trend layer, (c) measurably improve SEO and GEO output — and its contribution must be visible in the result.**

## 1. Fix the silent no-op (root cause first)

### 1a. Render env var (Adrien does this, guide him FIRST)
`GEMINI_API_KEY` exists only in local `.env`. The test ran on the Render backend where the key is absent → `fetch_realtime_signals` returned `None` silently. Walk Adrien through adding `GEMINI_API_KEY` on the **Render API service** env vars (same place as `LEONIE_ACCESS_CODE_PRO`), value from his local `.env` line 45. Redeploy.

### 1b. Make the fail-open diagnosable (code)
In `app/niche/signals/realtime_trends.py::fetch_realtime_signals`, every `return None` path must record a reason. Add a `status_out: dict | None = None` param (same pattern as `trends.py::fetch_related_queries`, lines 47-50): `no_gemini_key`, `plan_not_agency`, `llm_error: <msg>`, `parse_error`, `ok`. In `engine.py::_fetch_realtime_signals_once`, thread a `realtime_status` dict and store it in the result: add `"realtime_status": {...}` next to `provider_status` in `run_market_analysis`'s return dict (~line 6140). The comparison JSON and the dashboard can then show *why* grounding did or didn't run. Test: status is `no_gemini_key` when env is empty, `ok` when the mocked call succeeds.

## 2. Make grounding VERIFY market data (the core ask)

Today `realtime_signals` only feeds one prompt line. Add a **keyword-verification step**, deterministic, after pass 1 selects keywords:

- New function in `realtime_trends.py`: `verify_keywords_against_market(shop, keywords: list[str], niche_summary) -> dict | None` — ONE additional grounded call per full-catalog job (not per product). Prompt (FR, geo FR): given this list of target keywords, search the current French web/market and return for each: `{"query", "market_evidence": "confirmed|rising|declining|no_signal", "evidence_note", "source_url"}`. Same fail-open + `status_out` + `max_tokens=4096` + JSON-in-schema-sources pattern as `fetch_realtime_signals` (groundingMetadata is absent with json_mode — verified live, see AI_HANDOFF).
- Gate: agency plan (or `force`) + `GEMINI_API_KEY`, called from `run_market_analysis` right after the pass-1 loop, with the deduplicated primary+secondary keywords of all analyzed products (cap the list at ~30 to control tokens).
- **Write the verdict onto each keyword**: in each product's `seo_keywords`, add `market_verification: {evidence, note, source_url}` when the keyword was verified. This is the visible, comparable trace that was missing.
- **Use the verdict**: bump `priority_score` (+10 capped at 100) for `rising`, −10 for `declining`, and add `"verified_by_market"` to the keyword's `notes`. Deterministic, no extra LLM cost. This makes the agency output *rank differently* — a real, measurable SEO effect.

## 3. Make the trend layer visible in output (GEO)

- In `run_market_analysis`'s return dict, include the full `realtime_signals` payload under `"realtime_signals"` (events, rising_queries, competitor_moves, citations, fetched_at) — today it's only persisted to disk, invisible in exports and in the comparison JSON.
- Pass-1 prompt: keep the existing injected line, but ALSO instruct explicitly (only when `realtime_text` is non-empty): "Si une requête TEMPS RÉEL correspond à ce produit, inclus-la dans seo_keywords avec data_source='realtime_grounding'." Then pass-1 output can carry realtime-sourced keywords, traceable via `data_source`.
- GEO side: in pass 2, when `realtime_signals.events` is non-empty, append to the prompt a short instruction to angle ONE `geo_question`/answer on the current event when relevant (e.g. canicule → hydration question). Trace it: the engine already stores `geo_questions`; no schema change needed, the event angle is verifiable by content.

## 4. Comparison tool: surface the diff

In `plan_comparison.py`, add to the returned dict a computed `"diff_summary"`: for each plan `{keywords_with_market_verification: n, keywords_realtime_sourced: n, realtime_status, events_used: n}`. So the next comparison JSON answers "did Gemini add value?" at a glance without diffing 1.3 MB by hand.

## 5. Tests & validation (mandatory)

- `tests/test_niche/test_realtime_trends.py`: status_out reasons (no key / not agency / ok), `verify_keywords_against_market` (parse, fail-open, cap 30, sources).
- `tests/market_analysis/test_two_pass_engine.py`: keyword gets `market_verification` + priority bump when verifier returns `rising`; `realtime_status` present in result; `realtime_signals` included in the return dict.
- `tests/market_analysis/test_plan_comparison.py`: `diff_summary` present and correct.
- Run: `ruff check .`, full `pytest`, `cd shopify-app && npm run typecheck && npm run build` (frontend only if you touch it — not required by this plan).
- **Live re-test:** after Render has the key, Adrien re-clicks « Analyse test » and hands over the new JSON; verify `agency.realtime_grounding_used = True`, `realtime_status.status = "ok"`, and ≥1 keyword with `market_verification`.
- Update `docs/AI_HANDOFF.md`. Conventional commits, push on main, one commit per logical step.

## 6. Guardrails (unchanged from the original brief)

- Zero behavior change for free/pro (all new paths gated agency-or-force).
- Every grounded path fails open — an analysis must never break because Gemini is down.
- Max +1 grounded call per full-catalog job (signals + verification = 2 total). Never per-product, never on targeted re-analyses.
- Sources must be kept and surfaced (data-transparency rule). Never fabricate URLs — instruct the model to return empty when unsure.
- No new pip dependency.
