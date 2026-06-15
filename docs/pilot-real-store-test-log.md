# Real-store pilot test log

## 2026-05-15 — Public smoke checks

Tester: Codex

Scope: checks that do not require a Shopify Admin embedded session.

| Check | Command | Result |
|---|---|---|
| Remix app health | `curl -fsS https://pilot.leoniedelacroixfrance.com/healthz` | `ok` |
| Python backend health | `curl -fsS https://leonie-seo-pilot-api.onrender.com/health` | `{"status":"ok","missing_env":[]}` |
| Privacy page | `curl -fsS -o /dev/null -w '%{http_code}\n' https://leonie-seo-pilot-api.onrender.com/privacy` | `200` |
| CLI smoke command | `python -m scripts.cli pilot smoke-public --timeout 90` | all 3 checks OK |

Notes:

- The first public checks took several seconds, consistent with Render Free cold starts.
- The Python smoke command needs a patient timeout for Render Free cold starts; default is now 90 seconds.
- `HEAD /privacy` returned `405` with `allow: GET`; the endpoint is valid through GET and returned `200`.
- Embedded Shopify Admin workflow checks remain to be executed from a logged-in merchant session using `docs/pilot-real-store-test-plan.md`.

Decision: pass for public smoke checks; task 79 remains in progress until embedded Admin workflows are executed and evidence is recorded.

## 2026-05-16 — Embedded Shopify Admin workflow

Tester: Adrien

Scope: logged-in Shopify Admin embedded app session on the real store.

| Check | Result |
|---|---|
| Install/session | Pass |
| Navigation | Pass; no issue reported |
| Settings / pilot-safe state | Pass; the user sees the expected state, even though the exact wording `Mode pilot-safe actif` was not visible |
| Audit job ID | Pass; ID created, exact value not recorded |
| Products / collections crawled | Pass |
| Niche clusters | Pass |
| Meta generation job ID | Pass; exact value not recorded |
| Suggestions generated | Pass |
| Approve / reject | Pass |
| Dry-run job ID | Pass; exact value not recorded |
| Dry-run preview | Pass |
| Billing blocked | Pass |
| Privacy | Pass |
| Bugs or friction | Pass; no blocking issue reported |

Notes:

- The pilot-safe Settings wording can be reviewed during task 80 as a UX clarity follow-up.
- Job IDs were validated in the Admin flow but not copied into this log.

Decision: pass for the embedded Shopify Admin workflow; task 79 can be closed.
