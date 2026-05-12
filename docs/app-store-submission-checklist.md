# Shopify App Store Submission Checklist

## Repository readiness completed

- Embedded Shopify app routes are available under `shopify-app/app/routes/`.
- The embedded auth catch-all route exists at `auth.$.tsx`.
- Local development has a dedicated `shopify.app.local.toml` configuration.
- Local dev starts the Remix frontend through `shopify.web.toml`.
- Session storage falls back to Shopify memory storage when `DATABASE_URL` is absent.
- Webhook registration is skipped automatically for localhost development, where Shopify does not support inbound app callbacks.

## Real dev-store test flow

1. Start the Python backend from the repository root:
   `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
2. Start the Shopify app from `shopify-app/`:
   `npm run dev -- --config local --use-localhost`
3. Open the Shopify CLI preview URL inside the development store admin.
4. Verify the embedded app loads and the main navigation works:
   Dashboard, Review, Niche, Onboarding, Jobs, Billing, Settings, Privacy.
5. Verify actions that depend on the Python backend degrade gracefully when data is absent and work when the backend is running.

## Production / Partner Dashboard checks still manual

- Replace localhost with a public production URL or approved tunnel before final review.
- Keep production webhook subscriptions enabled in `shopify.app.toml`.
- Run Shopify automated App Store review checks.
- Complete the App Store listing, primary language, app icon, screenshots, and demo screencast.
- Provide emergency developer contact details in the Partner Dashboard.
- Confirm privacy policy, GDPR export behavior, Billing API flow, and review instructions/test credentials.

## Final submission note

The repository is ready for the next validation stage, but public App Store submission is intentionally deferred until the real-store pilot is complete.

Use `docs/pilot-real-store-setup.md` to prepare the separate pilot app, link the dedicated Shopify CLI configuration, wire a public callback-capable URL, and generate the direct install path for the merchant store. After tasks 76-83 are complete, return to this checklist for the public App Store submission flow.
