# Real-store pilot setup before App Store submission

## Purpose

Task 76 prepares a merchant-facing pilot that can run on the real Léonie store before the public Shopify App Store launch.

The pilot must:
- use a separate Shopify Partner app from the future public App Store app;
- use Shopify custom distribution with a direct install link for the merchant store;
- run behind a stable public HTTPS URL, not localhost-only preview URLs;
- keep Remix sessions persistent and Shopify callbacks/webhooks reachable;
- leave the codebase ready for task 77, where the app is actually installed and validated on the real store.

## Target store and distribution choice

- Merchant storefront: `https://www.leoniedelacroix.com`
- Shopify store identity: `287c4a-bb.myshopify.com`
- Pilot distribution type: **Custom distribution**
- Future public release: **separate public App Store app**

Do not reuse the future public App Store app for the pilot. The pilot is a controlled merchant environment, not the final public listing path.

## Target runtime topology

```text
Merchant Shopify Admin
        |
        v
Public pilot app URL
  - Remix embedded app
  - /auth/*
  - /webhooks
        |
        v
Python backend
  - internal HTTP from Remix
  - shared INTERNAL_API_SECRET
        |
        v
Neon Postgres
  - OAuth sessions
  - app data
  - async jobs
```

## Partner Dashboard setup

1. Create a new Shopify Partner app dedicated to the pilot, for example `Léonie SEO Pilot`.
2. Select **Custom distribution** for that app.
3. Restrict the install target to `287c4a-bb.myshopify.com`.
4. Generate the install link for the store owner.
5. Keep the future public App Store app separate for the later task 84 flow.

## Link a dedicated CLI config

From `shopify-app/`:

```bash
shopify app config link --config pilot
```

This generates `shopify.app.pilot.toml` for the real pilot environment. Once the app is linked, keep this file versioned so later deploys use the same Shopify app identity, URLs, scopes, and webhook configuration.

After linking, edit the generated config so the pilot app points to the real public origin:

```toml
application_url = "https://pilot.leoniedelacroix.com"

[auth]
redirect_urls = [
  "https://pilot.leoniedelacroix.com/auth/callback",
  "https://pilot.leoniedelacroix.com/auth/shopify/callback",
]
```

Keep the webhook subscriptions active in the pilot config:
- `app/uninstalled`
- `customers/data_request`
- `customers/redact`
- `shop/redact`

Once the configuration is ready:

```bash
shopify app deploy --config pilot
```

## Required environment values

### Remix app service (`shopify-app/.env`)

```env
SHOPIFY_API_KEY=...
SHOPIFY_API_SECRET=...
SCOPES=read_products,write_products,read_orders
SHOPIFY_APP_URL=https://pilot.leoniedelacroix.com
DATABASE_URL=postgresql://...
PYTHON_BACKEND_URL=https://python-backend.example.com
INTERNAL_API_SECRET=...
```

### Python backend (`.env`)

```env
DATABASE_URL=postgresql://...
INTERNAL_API_SECRET=...
LEONIE_MASTER_KEY=...
LEONIE_REQUIRE_SESSION_TOKEN=true
```

Add the SEO provider credentials that the pilot actually needs for real workflows:
- Google Search Console;
- PageSpeed Insights;
- GA4, if those journeys are validated during the pilot.

## Render deployment plan

The repository includes a `render.yaml` Blueprint for the pilot:
- `leonie-seo-pilot-web` — Remix embedded app, attached to `pilot.leoniedelacroix.com`;
- `leonie-seo-pilot-api` — FastAPI backend, public Render URL used by `PYTHON_BACKEND_URL`.

The Blueprint uses the Free Render instance type for both services to keep the pilot inexpensive. Free web services can spin down after idle periods and take about a minute to wake back up, so upgrade later if pilot sessions need faster always-on responsiveness.

### Render setup sequence

1. In Render, create a new Blueprint from this Git repository.
2. Let Render detect `render.yaml`.
3. Create both services from the Blueprint.
4. Fill the secret environment variables marked `sync: false`.
5. Copy the public Render URL of `leonie-seo-pilot-api` into the web service variable `PYTHON_BACKEND_URL`.
6. Add and verify the custom domain `pilot.leoniedelacroix.com` on the web service.
7. Configure the required DNS records at the domain provider, then wait for Render TLS verification.

Render automatically manages TLS for custom domains after DNS verification, and web services must bind to the platform port over `0.0.0.0`. The Blueprint follows that requirement for both services.

## Ready-for-task-77 checklist

- Public HTTPS origin `https://pilot.leoniedelacroix.com` is live and stable.
- Render Blueprint services are created from `render.yaml`.
- `PYTHON_BACKEND_URL` points to the deployed Render API service.
- Redirect URLs in `shopify.app.pilot.toml` match that origin exactly.
- `DATABASE_URL` is set for both services that need persistent state.
- `INTERNAL_API_SECRET` matches between Remix and Python.
- The public app can reach the Python backend.
- `/webhooks` is reachable from the public origin.
- Custom distribution install link has been generated for the real merchant store.
- The pilot app is separate from the future public App Store app.

## What task 77 will validate next

Task 77 starts only after this setup exists. It will validate:
- installation on the real merchant store;
- OAuth and embedded session persistence;
- GDPR and uninstall webhook delivery;
- the pilot billing posture;
- that the app works against the live Léonie catalog without relying on dev-store shortcuts.
