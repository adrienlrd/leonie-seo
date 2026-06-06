# `write_themes` scope — App Store review justification

> Purpose: give the Shopify App Store reviewer everything needed to approve the
> `write_themes` scope quickly, by proving the app uses it for a single, narrow,
> consented, reversible, audited purpose and can never modify a merchant's
> existing theme.

## 1. Why the app requests `write_themes`

The app publishes three **AI discovery files** so that AI crawlers and answer
engines can read a structured summary of the store:

- `/llms.txt`
- `/llms-full.txt`
- `/agents.md`

Shopify serves these root paths from theme template files: dropping a file at
`templates/<name>.liquid` makes Shopify render it in place of its default output
for every request to that path. Customising them is therefore only possible by
writing those template files on the **published** theme via the Admin GraphQL
API (`themeFilesUpsert` / `themeFilesDelete`), which requires `read_themes` +
`write_themes`.

## 2. Exactly which files are written

Only these three files, ever — enforced by a strict allowlist in code:

```
templates/llms.txt.liquid
templates/llms-full.txt.liquid
templates/agents.md.liquid
```

Source of truth: `ALLOWED_THEME_FILES` in `app/apply/shopify_theme_files.py`.
Both `upsert_templates()` and `delete_templates()` validate every filename
against this allowlist **before any network call** and raise a blocking error
otherwise.

## 3. Why a Theme App Extension is not sufficient

Theme App Extensions can only add app blocks/embeds into existing template
surfaces; they **cannot create root-path responses** like `/llms.txt`,
`/llms-full.txt` or `/agents.md`. Those paths are served by Shopify from the
theme's `templates/*.liquid` files, so producing/overriding them requires
writing those specific template files — there is no extension-only path.

## 4. No modification of the merchant's existing theme

The app **never** writes to any other theme file. The following are impossible
by construction (any attempt raises before a request is sent):

- `layout/*` (incl. `theme.liquid`), `sections/*`, `snippets/*`, `assets/*`,
  `config/*`, `templates/product*`, `templates/collection*`, `templates/index*`, …

No design, layout, section, snippet, asset, settings or existing merchant code is
read-for-write or modified. The three AI files are additive and independent of
the theme's visual design.

## 5. Explicit merchant consent (no automatic writes)

- Nothing is published at install. There is **no auto-publish**.
- Publishing happens only from the **AI files** page (`/app/geo-llms-txt`) where
  the merchant sees the exact list of files, a statement that no other theme
  file is touched, and how to remove them — then ticks a confirmation checkbox
  and clicks **"Publish the AI files to my theme"**.
- The backend `POST /api/shops/{shop}/llms-txt/publish` requires `confirm=true`
  (HTTP 409 otherwise) and a theme-write mode other than `disabled` (HTTP 403
  otherwise). See `require_theme_write_allowed()` in `app/safety.py`.
- Catalogue webhooks (`products/*`, `collections/*`) can refresh the files
  **only if the merchant already published them** (`is_published`) and the mode
  is not `disabled`; otherwise the intent is recorded as `regeneration_pending`
  and nothing is written. A debounce (5 min) prevents bursts.

## 6. Review-safe mode

`LEONIE_THEME_WRITE_MODE` (see `app/safety.py`) gates the whole feature:

| Mode | Behaviour |
|---|---|
| `disabled` | No theme write at all — preview/export only. Default in local/test. |
| `review_safe` | Writes allowed, restricted to the 3 allowlisted files, explicit merchant confirmation + full audit log. **Production default.** |
| `live` | Same strict allowlist, for production after validation. |

This lets the app ship with theme writes **off** if needed, while keeping the
preview/export experience fully functional.

## 7. How the merchant disables / removes the files

The same page exposes **"Unpublish"**, which calls `themeFilesDelete` for the
three allowlisted files only, reverting to Shopify's default output. Unpublish
never touches any other file and works as a best-effort off-switch.

## 8. Audit trail

Every theme write is recorded in the `theme_write_log` table (see
`app/db.py` + `app/llms_txt/store.py::log_theme_write`): shop, theme_id,
action (`publish` / `unpublish` / `regeneration_pending`), filenames, content
hash before/after, `user_action`, timestamp.

## 9. Tests that prove the guarantees

- `tests/apply/test_shopify_theme_files.py`
  - upsert/delete on `layout/theme.liquid`, `sections/*`, `snippets/*`,
    `assets/*`, `templates/product*`, `templates/collection*`, `config/*` are
    **refused before any network call**;
  - allowlisted files succeed;
  - a global scan asserts **no code path outside the writer** issues
    `themeFilesUpsert` / `themeFilesDelete`.
- `tests/test_llms_txt/test_publisher.py`
  - `disabled` mode → no write even on an allowlisted file;
  - publish/unpublish write the audit log;
  - webhook does not regenerate when never published.
- `tests/test_api/test_llms_txt_api.py`
  - publish without `confirm` → 409; `disabled` → 403;
  - webhook in `disabled` → `regeneration_pending`, no write.

## 10. REVIEW_NOTE — verify before submission

Confirm on a real store, with the production Admin API version, that after
publishing:

- `GET https://<shop>/llms.txt`, `/llms-full.txt`, `/agents.md` each return 200
  with the generated content;
- the published theme shows only the three new `templates/*.liquid` files added,
  with no diff to any other file.

If Shopify ever stops serving these paths from theme templates, do **not** force
it: set `LEONIE_THEME_WRITE_MODE=disabled` (preview/export only) and drop
`write_themes` from the requested scopes.
