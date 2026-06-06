# App Store Reviewer Test Instructions — Giulio Geo

> Audience: Shopify App Store review team
> Estimated test duration: 15–20 minutes
> Last updated: 2026-05-18

Thank you for reviewing **Giulio Geo**. This document walks you through every
flow you need to assess: install, value delivery, billing, GDPR webhooks,
and uninstall. The app is fully embedded in Shopify Admin and requires no
external account creation to evaluate.

---

## 1. Test store & credentials

| Item | Value |
|---|---|
| App listing | (will be provided in the Partner Dashboard submission) |
| Install URL | Provided by Shopify "Test app" link |
| Test store | Use any development store; the app supports any `*.myshopify.com` domain |
| Pre-loaded credentials | **None required** — the app uses only Shopify OAuth |
| Optional Google credentials | Not required for the core walk-through. Skip the GSC/GA4 connection steps if you prefer a faster review |

If you choose to evaluate the GSC/GA4 integrations, contact our support email
(`support@leoniedelacroix.com`) and we'll provide a dedicated sandbox Google
account with read-only scopes on a public test property.

---

## 2. Install & first-run experience (≈ 2 min)

1. From the Partner Dashboard, click **Test app on development store** and
   pick your store.
2. Shopify shows the standard install screen listing scopes:
   `read_products, write_products, write_content, read_themes, write_themes`.
   Click **Install app**.
3. You are redirected into the embedded Giulio Geo **Dashboard** inside the
   Shopify Admin chrome.
4. Confirm the following appears immediately:
   - Page title: **Tableau de bord** (or **Dashboard** with `?locale=en`)
   - Sub-title: your shop domain
   - **Configuration de votre boutique** card with a 4-step setup
     progress bar (Boutique connectée ✓, Premier audit, GSC, Abonnement)
   - **Alertes prioritaires** card (initially empty)
   - **Accès rapide** card with 4 hub buttons
   - **Activité récente** card (initially empty)
   - Primary CTA button **Lancer un audit SEO** at the top-right
5. The left navigation menu shows only 6 entries:
   Dashboard, Audit & diagnostic, Optimisation, Contenu & visibilité,
   Insights & rapports, Compte & configuration.

Expected result: no blank screen, no untranslated keys, no console errors.

---

## 3. Run an audit (≈ 1 min)

1. Click **Lancer un audit SEO** in the top-right of the dashboard.
2. A success banner appears: *"Audit en cours — tâche XXXXXXXX…"*.
3. Open the **Insights & rapports** hub → **Tâches en cours**.
4. The audit job moves from `pending` → `running` → `completed` within
   ~60 seconds on a typical development store.
5. Return to the dashboard — the **Configuration** card now shows
   *Premier audit SEO lancé* as ✓ Fait.

---

## 4. Browse the audit results (≈ 3 min)

1. From the dashboard, click the **Audit & diagnostic** hub button.
2. Open the **Audit SEO** card.
3. You should see:
   - **Score SEO global** card with breakdown per component
   - **Priorités ICE (top 10)** card with a tooltip explaining ICE
   - **Issues** card with severity filters (Toutes, critical, high, …),
     resource-type filters (product, collection, image, page), and a
     **Polaris IndexTable with pagination** (25 rows per page).
4. Click between pages to verify pagination works. Apply a severity filter
   to verify the page resets to 1 and the count updates.

---

## 5. Content suggestions (≈ 2 min)

1. From the dashboard, click **Contenu & visibilité** hub button.
2. Open the **Contenu SEO** card.
3. Two tabs are shown:
   - **FAQ produits** — Schema.org FAQPage suggestions per product, with
     a "Copier JSON-LD" button on each card.
   - **Briefs blog** — informational queries surfaced from Google Search
     Console data (empty if GSC is not connected).
4. Open the **Hreflang / International** card and verify the
   Configuration / Prévisualisation / Problèmes tabs all render.

---

## 6. Billing flow (≈ 3 min)

> Mandatory App Store check: confirm Shopify Billing API is used and that
> the merchant signs the charge inside Shopify's chrome.

1. From the dashboard, click **Compte & configuration** hub → **Abonnement**.
2. You see three plans:
   - **Giulio Geo Free** — $0 / month (active by default after install)
   - **Giulio Geo Pro** — $29 USD / 30 days
   - **Giulio Geo Agency** — $99 USD / 30 days
3. Click **Passer en Pro** (or *Upgrade to Pro*).
4. Shopify redirects you to the **Shopify Billing confirmation screen**
   signed by Shopify itself (URL contains `/admin/charges/...`).
5. Click **Approve charge** (development stores incur no real payment).
6. You are sent back to the app. The Abonnement page now shows
   **Plan actuel : Pro** and the setup checklist marks
   *Abonnement actif* as ✓.

To verify the cancel path, click **Annuler l'abonnement** — the app
calls `appSubscriptionCancel` and the merchant returns to the Free plan.

---

## 7. GDPR mandatory webhooks (≈ 1 min)

All three Shopify mandatory webhooks are implemented and HMAC-verified.
Trigger each from your Partner Dashboard under **Apps → Test webhooks**:

| Topic | Expected backend response |
|---|---|
| `customers/data_request` | `200 OK`, JSON ack with `audit_logged: true` |
| `customers/redact` | `200 OK`, ack with `audit_logged: true` |
| `shop/redact` | `200 OK`, app data deleted for the shop |

You can also send `app/uninstalled` — it cleans up the OAuth token store.

---

## 8. Uninstall (≈ 1 min)

1. From Shopify Admin → Settings → Apps → **Giulio Geo** → click **Delete**.
2. Confirm uninstall in the Shopify modal.
3. Within 30 seconds, the `app/uninstalled` webhook fires.
4. Attempt to navigate back to the app URL — you should be redirected to
   the standard install screen (no stale session).

---

## 9. Privacy & support

- **Privacy policy URL** (publicly accessible HTML page):
  `https://leonie-seo-pilot-api.onrender.com/privacy`
  Covers what data is collected, retention, third parties (Google APIs,
  LLM providers), and GDPR rights.
- **Terms of service URL**: provided in the App Store listing form.
- **Support email**: `support@leoniedelacroix.com` (replies within 24 h on
  business days).

---

## 10. Known limitations during review

These are intentional and documented in `docs/plans.md`:

- The **Free plan** does not allow writing back to Shopify (no `meta`
  updates, no alt-text writes). Upgrade to **Pro** to enable apply flows.
- **PageSpeed analysis** runs at reduced quota without a Google Cloud
  API key. The merchant can paste their own key in **Onboarding → PageSpeed**
  to lift the rate limit; the app degrades gracefully otherwise.
- **Google Search Console** and **GA4** integrations are optional. The
  core audit + content features work without them.
- All Shopify writes are **dry-run by default**. The merchant must
  explicitly toggle live mode in **Optimisation → Review IA** before any
  product fields are modified.

---

## 11. Reviewer feedback

If anything in this walk-through diverges from what you observe, please
contact `support@leoniedelacroix.com` and reference the section number.
We treat reviewer feedback as P0 and typically reply within a few hours.
