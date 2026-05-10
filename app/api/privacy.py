"""Privacy policy page and GDPR data export endpoint."""

from __future__ import annotations

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

_PRIVACY_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Politique de confidentialité — Léonie SEO</title>
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

  <h1>Politique de confidentialité — Léonie SEO</h1>
  <p><em>Mise à jour : 2026-05-10</em></p>

  <h2>1. Responsable du traitement</h2>
  <p>
    Léonie SEO est un outil auto-hébergé. Le responsable du traitement des données est
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
    Léonie SEO <strong>ne collecte pas</strong> de données clients individuels (noms, emails,
    adresses, historiques de commandes). L'outil accède uniquement aux méta-données produits
    et aux données de performance SEO (GSC, PageSpeed).
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

  <h1>Privacy Policy — Léonie SEO</h1>
  <p><em>Updated: 2026-05-10</em></p>

  <h2>1. Data Controller</h2>
  <p>
    Léonie SEO is a self-hosted tool. The data controller is the merchant who installs
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
    Léonie SEO does <strong>not</strong> collect individual customer data (names, emails,
    addresses, order history). The tool only accesses product meta-data and SEO performance
    data (GSC, PageSpeed).
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


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy() -> str:
    """Public privacy policy page — required for Shopify App Store listing."""
    return _PRIVACY_HTML


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
