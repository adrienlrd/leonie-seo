"""Privacy policy page and GDPR data export endpoint.

Two privacy modes are supported, controlled by the LEONIE_MODE env var:

- `app_store` (default) — SaaS deployment. Tokens and metadata are stored on
  Giulio Geo managed infrastructure (Neon Postgres) and the data controller
  is the app vendor. This is the canonical mode for App Store distribution.
- `self_hosted` — CLI/agency deployment. The merchant runs the app on their
  own infrastructure; no data leaves their environment. The data controller
  is the merchant.

Lying about which mode is active = App Store review rejection + RGPD risk.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.deps import ShopContext, get_shop_context
from app.billing.subscription_store import get_subscription
from app.db import DB_PATH
from app.db_adapter import get_conn
from app.oauth.token_store import get_token

router = APIRouter(tags=["privacy"])


def _mode() -> str:
    """Return the active deployment mode — 'app_store' (default) or 'self_hosted'."""
    raw = os.getenv("LEONIE_MODE", "app_store").strip().lower()
    return raw if raw in ("app_store", "self_hosted") else "app_store"


_PRIVACY_HTML_APP_STORE = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Politique de confidentialité — Giulio Geo</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 800px; margin: 40px auto; padding: 0 20px; color: #111; line-height: 1.6; }
    h1 { font-size: 1.8rem; border-bottom: 2px solid #111; padding-bottom: 8px; }
    h2 { font-size: 1.2rem; margin-top: 2rem; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
    th { background: #f5f5f5; font-weight: 600; }
    a { color: #3b82f6; }
    .lang { font-size: 0.85rem; color: #666; margin-bottom: 2rem; }
  </style>
</head>
<body>
  <p class="lang"><a href="#english">English version below</a></p>

  <h1>Politique de confidentialité — Giulio Geo</h1>
  <p><em>Mise à jour : 2026-05-12 — édition Shopify App Store</em></p>

  <h2>1. Responsable du traitement</h2>
  <p>
    Giulio Geo est une application Shopify hébergée par son éditeur. Le responsable du
    traitement des données est <strong>l'éditeur de Giulio Geo</strong>. Le marchand
    Shopify reste responsable des données qu'il choisit d'exposer via les portées OAuth
    qu'il accorde lors de l'installation.
  </p>

  <h2>2. Données collectées et hébergement</h2>
  <table>
    <tr><th>Donnée</th><th>Finalité</th><th>Hébergement</th><th>Conservation</th></tr>
    <tr><td>Domaine de la boutique</td><td>Identification du tenant</td><td>Neon Postgres (UE)</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Token OAuth Shopify (chiffré Fernet)</td><td>Appels API Admin Shopify</td><td>Neon Postgres (UE)</td><td>Supprimé à la désinstallation</td></tr>
    <tr><td>Portées OAuth (scopes)</td><td>Contrôle d'accès</td><td>Neon Postgres (UE)</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Plan et statut d'abonnement</td><td>Gestion du niveau de service</td><td>Neon Postgres (UE)</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Journal des demandes GDPR</td><td>Piste d'audit réglementaire</td><td>Neon Postgres (UE)</td><td>Désinstallation + 30 jours</td></tr>
    <tr><td>Historique des modifications SEO</td><td>Rollback et audit</td><td>Neon Postgres (UE)</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Métadonnées d'appels LLM (provider, tokens, coût)</td><td>Facturation et observabilité</td><td>Neon Postgres (UE)</td><td>13 mois</td></tr>
  </table>

  <h2>3. Données non collectées</h2>
  <p>
    Giulio Geo <strong>ne collecte pas</strong> de données clients individuels du marchand
    (noms, emails, adresses, historiques de commandes). L'app accède uniquement aux
    méta-données produits/collections et aux performances SEO (GSC, GA4).
  </p>

  <h2>4. Sous-traitants</h2>
  <ul>
    <li>Neon (Postgres serverless — base de données) — UE</li>
    <li>OpenAI (génération LLM, GPT-4o mini) — USA, DPA signé, contenu non utilisé pour entraînement</li>
    <li>Cloudflare Workers AI (génération LLM, fallback) — USA/UE</li>
    <li>Groq (génération LLM, fallback) — USA</li>
    <li>Google Cloud (GSC, GA4 APIs) — USA</li>
  </ul>

  <h2>5. Sécurité</h2>
  <ul>
    <li>Tokens OAuth chiffrés au repos via Fernet (AES-128-CBC + HMAC-SHA256)</li>
    <li>HMAC-SHA256 validé sur chaque webhook Shopify entrant et chaque appel d'app interne</li>
    <li>Isolation multi-tenant : chaque table contient une colonne <code>shop</code>
        et les requêtes la filtrent systématiquement</li>
    <li>Communication TLS 1.2+ pour toute donnée en transit</li>
  </ul>

  <h2>6. Droits des marchands</h2>
  <ul>
    <li><strong>Accès</strong> : <code>GET /api/gdpr/export?shop=votre-boutique</code></li>
    <li><strong>Suppression</strong> : désinstaller l'app — le webhook <code>shop/redact</code>
        efface toutes les données dans les 48 h conformément aux exigences Shopify</li>
    <li><strong>Contact</strong> : <a href="mailto:support@leonie-seo.com">support@leonie-seo.com</a></li>
  </ul>

  <hr id="english" style="margin: 3rem 0;">

  <h1>Privacy Policy — Giulio Geo</h1>
  <p><em>Updated: 2026-05-12 — Shopify App Store edition</em></p>

  <h2>1. Data Controller</h2>
  <p>
    Giulio Geo is a Shopify-hosted application operated by its publisher. The data
    controller is the <strong>Giulio Geo publisher</strong>. The Shopify merchant
    remains responsible for the data they expose via the OAuth scopes they grant on
    install.
  </p>

  <h2>2. Data Collected and Hosting</h2>
  <table>
    <tr><th>Data</th><th>Purpose</th><th>Hosting</th><th>Retention</th></tr>
    <tr><td>Shop domain</td><td>Tenant identification</td><td>Neon Postgres (EU)</td><td>Until uninstall</td></tr>
    <tr><td>Shopify OAuth token (Fernet-encrypted)</td><td>Shopify Admin API calls</td><td>Neon Postgres (EU)</td><td>Deleted on uninstall</td></tr>
    <tr><td>OAuth scopes</td><td>Access control</td><td>Neon Postgres (EU)</td><td>Until uninstall</td></tr>
    <tr><td>Subscription plan &amp; status</td><td>Service tier management</td><td>Neon Postgres (EU)</td><td>Until uninstall</td></tr>
    <tr><td>GDPR request log</td><td>Regulatory audit trail</td><td>Neon Postgres (EU)</td><td>Until uninstall + 30 days</td></tr>
    <tr><td>SEO change history</td><td>Rollback and audit</td><td>Neon Postgres (EU)</td><td>Until uninstall</td></tr>
    <tr><td>LLM call metadata (provider, tokens, cost)</td><td>Billing &amp; observability</td><td>Neon Postgres (EU)</td><td>13 months</td></tr>
  </table>

  <h2>3. Data Not Collected</h2>
  <p>
    Giulio Geo does <strong>not</strong> collect individual customer data (names,
    emails, addresses, order history). The app only accesses product/collection
    meta-data and SEO performance data (GSC, GA4).
  </p>

  <h2>4. Subprocessors</h2>
  <ul>
    <li>Neon (serverless Postgres database) — EU</li>
    <li>OpenAI (LLM generation, GPT-4o mini) — USA, DPA signed, content not used for training</li>
    <li>Cloudflare Workers AI (LLM generation, fallback) — USA/EU</li>
    <li>Groq (LLM generation, fallback) — USA</li>
    <li>Google Cloud (GSC, GA4 APIs) — USA</li>
  </ul>

  <h2>5. Security</h2>
  <ul>
    <li>OAuth tokens encrypted at rest via Fernet (AES-128-CBC + HMAC-SHA256)</li>
    <li>HMAC-SHA256 validated on every inbound Shopify webhook and internal call</li>
    <li>Multi-tenant isolation: every table carries a <code>shop</code> column and queries always filter on it</li>
    <li>TLS 1.2+ for all data in transit</li>
  </ul>

  <h2>6. Merchant Rights</h2>
  <ul>
    <li><strong>Access</strong>: <code>GET /api/gdpr/export?shop=your-shop</code></li>
    <li><strong>Deletion</strong>: uninstall the app — the <code>shop/redact</code> webhook
        erases all data within 48 hours per Shopify requirements</li>
    <li><strong>Contact</strong>: <a href="mailto:support@leonie-seo.com">support@leonie-seo.com</a></li>
  </ul>
</body>
</html>"""


_PRIVACY_HTML_SELF_HOSTED = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Politique de confidentialité — Giulio Geo</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 800px; margin: 40px auto; padding: 0 20px; color: #111; line-height: 1.6; }
    h1 { font-size: 1.8rem; border-bottom: 2px solid #111; padding-bottom: 8px; }
    h2 { font-size: 1.2rem; margin-top: 2rem; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
    th { background: #f5f5f5; font-weight: 600; }
    a { color: #3b82f6; }
    .lang { font-size: 0.85rem; color: #666; margin-bottom: 2rem; }
  </style>
</head>
<body>
  <p class="lang"><a href="#english">English version below</a></p>

  <h1>Politique de confidentialité — Giulio Geo</h1>
  <p><em>Mise à jour : 2026-05-10</em></p>

  <h2>1. Responsable du traitement</h2>
  <p>
    Giulio Geo est un outil auto-hébergé. Le responsable du traitement des données est
    le marchand qui installe et opère l'application sur ses propres serveurs.
    Anthropic / Claude Code ne collecte aucune donnée marchande.
  </p>

  <h2>2. Données collectées</h2>
  <table>
    <tr><th>Donnée</th><th>Finalité</th><th>Durée de conservation</th></tr>
    <tr><td>Domaine de la boutique</td><td>Identification du tenant</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Token OAuth Shopify (chiffré Fernet)</td><td>Appels API Admin Shopify</td><td>Supprimé à la désinstallation</td></tr>
    <tr><td>Portées OAuth (scopes)</td><td>Contrôle d'accès</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Plan et statut d'abonnement</td><td>Gestion du niveau de service</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Journal des demandes GDPR</td><td>Piste d'audit réglementaire</td><td>Jusqu'à désinstallation + 30 jours</td></tr>
    <tr><td>Historique des modifications SEO</td><td>Rollback et audit</td><td>Jusqu'à désinstallation</td></tr>
  </table>

  <h2>3. Données non collectées</h2>
  <p>
    Giulio Geo <strong>ne collecte pas</strong> de données clients individuels (noms, emails,
    adresses, historiques de commandes). L'outil accède uniquement aux méta-données produits
    et aux données de performance SEO (GSC).
  </p>

  <h2>4. Sécurité</h2>
  <ul>
    <li>Tokens OAuth chiffrés au repos via Fernet (AES-128-CBC + HMAC-SHA256)</li>
    <li>Aucune donnée transmise à des serveurs tiers — l'outil est entièrement auto-hébergé</li>
    <li>HMAC-SHA256 validé sur chaque webhook Shopify entrant</li>
  </ul>

  <h2>5. Droits des marchands</h2>
  <ul>
    <li><strong>Accès</strong> : <code>GET /api/gdpr/export?shop=votre-boutique</code></li>
    <li><strong>Suppression</strong> : désinstaller l'app — le webhook <code>shop/redact</code>
        efface toutes les données dans les 48 h</li>
    <li><strong>Contact</strong> : <a href="mailto:support@leonie-seo.com">support@leonie-seo.com</a></li>
  </ul>

  <hr id="english" style="margin: 3rem 0;">

  <h1>Privacy Policy — Giulio Geo</h1>
  <p><em>Updated: 2026-05-10</em></p>

  <h2>1. Data Controller</h2>
  <p>
    Giulio Geo is a self-hosted tool. The data controller is the merchant who installs
    and operates the application on their own servers.
  </p>

  <h2>2. Data Collected</h2>
  <table>
    <tr><th>Data</th><th>Purpose</th><th>Retention</th></tr>
    <tr><td>Shop domain</td><td>Tenant identification</td><td>Until uninstall</td></tr>
    <tr><td>Shopify OAuth token (Fernet-encrypted)</td><td>Shopify Admin API calls</td><td>Deleted on uninstall</td></tr>
    <tr><td>OAuth scopes</td><td>Access control</td><td>Until uninstall</td></tr>
    <tr><td>Subscription plan &amp; status</td><td>Service tier management</td><td>Until uninstall</td></tr>
    <tr><td>GDPR request log</td><td>Regulatory audit trail</td><td>Until uninstall + 30 days</td></tr>
    <tr><td>SEO change history</td><td>Rollback and audit</td><td>Until uninstall</td></tr>
  </table>

  <h2>3. Data Not Collected</h2>
  <p>
    Giulio Geo does <strong>not</strong> collect individual customer data (names, emails,
    addresses, order history). The tool only accesses product meta-data and SEO performance
    data (GSC).
  </p>

  <h2>4. Security</h2>
  <ul>
    <li>OAuth tokens encrypted at rest via Fernet (AES-128-CBC + HMAC-SHA256)</li>
    <li>No data transmitted to third-party servers — fully self-hosted</li>
    <li>HMAC-SHA256 validated on every inbound Shopify webhook</li>
  </ul>

  <h2>5. Merchant Rights</h2>
  <ul>
    <li><strong>Access</strong>: <code>GET /api/gdpr/export?shop=your-shop</code></li>
    <li><strong>Deletion</strong>: uninstall the app — the <code>shop/redact</code> webhook
        erases all data within 48 hours</li>
    <li><strong>Contact</strong>: <a href="mailto:support@leonie-seo.com">support@leonie-seo.com</a></li>
  </ul>
</body>
</html>"""


_TERMS_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Conditions d'utilisation — Giulio Geo</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 800px; margin: 40px auto; padding: 0 20px; color: #111; line-height: 1.6; }
    h1 { font-size: 1.8rem; border-bottom: 2px solid #111; padding-bottom: 8px; }
    h2 { font-size: 1.2rem; margin-top: 2rem; }
    a { color: #3b82f6; }
    .lang { font-size: 0.85rem; color: #666; margin-bottom: 2rem; }
  </style>
</head>
<body>
  <p class="lang"><a href="#english">English version below</a></p>

  <h1>Conditions d'utilisation — Giulio Geo</h1>
  <p><em>Mise à jour : 2026-06-06</em></p>

  <h2>1. Objet</h2>
  <p>
    Giulio Geo est une application Shopify d'aide au référencement (SEO) : audit,
    recommandations supervisées, génération de contenu assistée et suivi d'impact.
    En installant l'application, le marchand accepte les présentes conditions.
  </p>

  <h2>2. Facturation</h2>
  <p>
    L'abonnement est géré exclusivement via la Shopify Billing API. Aucun paiement
    n'est collecté en dehors de Shopify. Les plans, prix et fonctionnalités sont
    décrits dans l'application. La résiliation s'effectue depuis l'application ou en
    désinstallant l'app ; elle prend effet à la fin de la période de facturation en cours.
  </p>

  <h2>3. Usage acceptable</h2>
  <p>
    Le marchand s'engage à utiliser l'application conformément aux règles de Shopify et
    à la législation applicable. Toute modification appliquée à la boutique passe par une
    validation humaine (revue puis confirmation explicite) ; le mode dry-run est le défaut.
  </p>

  <h2>4. Absence de garantie de résultat</h2>
  <p>
    Giulio Geo fournit des recommandations et des optimisations SEO. <strong>Aucune
    position dans Google ni aucune apparition dans des moteurs de réponse IA (ChatGPT,
    Perplexity, Gemini, Google AI Overviews) n'est garantie.</strong> La visibilité
    constitue un signal mesuré, jamais une promesse. Les estimations d'impact sont
    indicatives et dépendent de facteurs externes hors du contrôle de l'éditeur.
  </p>

  <h2>5. Contenu généré par IA</h2>
  <p>
    Les contenus produits avec assistance d'un modèle de langage doivent être relus et
    validés par le marchand avant publication. Le marchand reste responsable du contenu
    publié sur sa boutique.
  </p>

  <h2>6. Limitation de responsabilité</h2>
  <p>
    L'application est fournie « en l'état ». Dans les limites permises par la loi,
    l'éditeur ne saurait être tenu responsable des pertes indirectes (perte de chiffre
    d'affaires, de classement ou de données) résultant de l'utilisation de l'application.
  </p>

  <h2>7. Données personnelles</h2>
  <p>
    Le traitement des données est décrit dans la
    <a href="/privacy">politique de confidentialité</a>. La suppression des données
    intervient à la désinstallation via le webhook <code>shop/redact</code>.
  </p>

  <h2>8. Évolution et contact</h2>
  <p>
    Ces conditions peuvent évoluer ; la version en vigueur est celle publiée sur cette page.
    Contact : <a href="mailto:support@leonie-seo.com">support@leonie-seo.com</a>.
  </p>

  <hr id="english" style="margin: 3rem 0;">

  <h1>Terms of Service — Giulio Geo</h1>
  <p><em>Updated: 2026-06-06</em></p>

  <h2>1. Purpose</h2>
  <p>
    Giulio Geo is a Shopify SEO assistance app: audits, supervised recommendations,
    AI-assisted content generation and impact tracking. By installing the app, the
    merchant agrees to these terms.
  </p>

  <h2>2. Billing</h2>
  <p>
    Subscriptions are managed exclusively through the Shopify Billing API. No payment is
    collected outside Shopify. Plans, prices and features are described in the app.
    Cancellation is done from the app or by uninstalling it, and takes effect at the end
    of the current billing period.
  </p>

  <h2>3. Acceptable use</h2>
  <p>
    The merchant agrees to use the app in compliance with Shopify rules and applicable law.
    Any change applied to the store goes through human validation (review then explicit
    confirmation); dry-run is the default.
  </p>

  <h2>4. No guarantee of results</h2>
  <p>
    Giulio Geo provides SEO recommendations and optimizations. <strong>No Google ranking
    and no appearance in AI answer engines (ChatGPT, Perplexity, Gemini, Google AI
    Overviews) is guaranteed.</strong> Visibility is a measured signal, never a promise.
    Impact estimates are indicative and depend on external factors beyond the publisher's
    control.
  </p>

  <h2>5. AI-generated content</h2>
  <p>
    Content produced with language-model assistance must be reviewed and approved by the
    merchant before publication. The merchant remains responsible for the content published
    on their store.
  </p>

  <h2>6. Limitation of liability</h2>
  <p>
    The app is provided "as is". To the extent permitted by law, the publisher shall not be
    liable for indirect losses (loss of revenue, ranking or data) arising from use of the app.
  </p>

  <h2>7. Personal data</h2>
  <p>
    Data processing is described in the <a href="/privacy">privacy policy</a>. Data is
    erased on uninstall via the <code>shop/redact</code> webhook.
  </p>

  <h2>8. Changes and contact</h2>
  <p>
    These terms may change; the version in force is the one published on this page.
    Contact: <a href="mailto:support@leonie-seo.com">support@leonie-seo.com</a>.
  </p>
</body>
</html>"""


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy() -> str:
    """Public privacy policy page — required for Shopify App Store listing.

    Returns the variant matching the active deployment mode (LEONIE_MODE):
    - 'app_store' (default): SaaS — vendor is data controller, Neon Postgres host.
    - 'self_hosted': merchant is data controller, no third-party hosting.
    """
    return _PRIVACY_HTML_APP_STORE if _mode() == "app_store" else _PRIVACY_HTML_SELF_HOSTED


@router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms_of_service() -> str:
    """Public terms of service page — required for the Shopify App Store listing.

    Bilingual (FR/EN). Explicitly states no ranking / AI-visibility guarantee to
    stay within App Store policy on misleading claims (launch-readiness §3.7).
    """
    return _TERMS_HTML


@router.get("/api/gdpr/export")
async def gdpr_export(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Export all data stored for a shop — GDPR Article 15 right of access.

    Does not expose the OAuth access token (security boundary).
    """
    exported_at = datetime.now(UTC).isoformat()
    shop = ctx.shop

    # Token metadata — no access_token in export
    token_record = get_token(shop)
    token_meta = (
        {
            "scope": token_record.get("scope"),
            "installed_at": token_record.get("installed_at"),
            "updated_at": token_record.get("updated_at"),
        }
        if token_record
        else None
    )

    # Subscription
    sub = get_subscription(shop)
    subscription = (
        {
            "plan": sub["plan"],
            "status": sub["status"],
            "subscription_id": sub["subscription_id"],
            "created_at": sub["created_at"],
            "updated_at": sub["updated_at"],
        }
        if sub
        else None
    )

    # GDPR request log for this shop
    # DB_PATH may be monkeypatched by tests — get_conn detects the patched path.
    with get_conn(DB_PATH) as conn:
        gdpr_requests = conn.execute(
            "SELECT received_at, topic FROM gdpr_requests WHERE shop = ? ORDER BY received_at",
            (shop,),
        ).fetchall()

    return {
        "shop": shop,
        "exported_at": exported_at,
        "data": {
            "installation": token_meta,
            "subscription": subscription,
            "gdpr_requests": gdpr_requests,
        },
    }
