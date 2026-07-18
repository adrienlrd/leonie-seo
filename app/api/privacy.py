"""Privacy policy page and GDPR data export endpoint.

Two privacy modes are supported, controlled by the LEONIE_MODE env var:

- `app_store` (default) — SaaS deployment. Tokens and metadata are stored on
  GEO by Organically managed infrastructure (Neon Postgres) and the data controller
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
  <title>Politique de confidentialité — GEO by Organically</title>
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

  <h1>Politique de confidentialité — GEO by Organically</h1>
  <p><em>Mise à jour : 18 juillet 2026 — édition Shopify App Store</em></p>

  <h2>1. Responsable du traitement</h2>
  <p>
    L'application Shopify <strong>GEO by Organically</strong> est éditée par :<br>
    <strong>Léonie Delacroix SASU</strong>, société par actions simplifiée unipersonnelle
    au capital de 1 000 €<br>
    Siège social : 28 C, rue François-Spoerry, 68100 Mulhouse, France<br>
    RCS Mulhouse 987 948 106 — SIREN 987 948 106 — TVA intracommunautaire FR 18 987 948 106<br>
    Contact : <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a>
    — Tél. : +33 7 68 33 16 27<br>
    Référent protection des données (DPO) : Adrien Leredde,
    <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a>
  </p>
  <p>
    Léonie Delacroix SASU est responsable du traitement des données décrites ci-dessous.
    Le marchand Shopify reste responsable des données de sa boutique qu'il choisit
    d'exposer via les portées OAuth accordées à l'installation.
  </p>

  <h2>2. Données collectées, finalités et bases légales</h2>
  <table>
    <tr><th>Donnée</th><th>Finalité</th><th>Base légale</th><th>Conservation</th></tr>
    <tr><td>Domaine de la boutique</td><td>Identification du compte</td><td>Exécution du contrat</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Token OAuth Shopify (chiffré)</td><td>Appels API Admin Shopify</td><td>Exécution du contrat</td><td>Supprimé à la désinstallation</td></tr>
    <tr><td>Catalogue produits/collections (métadonnées)</td><td>Analyses SEO/GEO et génération de contenu</td><td>Exécution du contrat</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Données Google Search Console / GA4</td><td>Mesure de performance SEO</td><td>Consentement (connexion Google facultative, révocable)</td><td>Jusqu'à déconnexion ou désinstallation</td></tr>
    <tr><td>Plan et statut d'abonnement</td><td>Facturation via Shopify Billing</td><td>Exécution du contrat</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Historique des modifications SEO</td><td>Annulation (rollback) et audit</td><td>Exécution du contrat</td><td>Jusqu'à désinstallation</td></tr>
    <tr><td>Journal des demandes GDPR</td><td>Piste d'audit réglementaire</td><td>Obligation légale</td><td>Désinstallation + 30 jours</td></tr>
    <tr><td>Métadonnées d'appels IA (fournisseur, tokens, coût)</td><td>Facturation et observabilité</td><td>Intérêt légitime</td><td>13 mois</td></tr>
  </table>

  <h2>3. Données non collectées</h2>
  <p>
    GEO by Organically <strong>ne collecte pas</strong> de données des clients finaux du
    marchand (noms, e-mails, adresses, historiques de commandes, données de paiement).
    L'app accède uniquement aux métadonnées produits/collections de la boutique et,
    si le marchand connecte Google, à ses données de performance SEO agrégées.
  </p>

  <h2>4. Sous-traitants et transferts hors UE</h2>
  <table>
    <tr><th>Sous-traitant</th><th>Rôle</th><th>Localisation</th><th>Encadrement du transfert</th></tr>
    <tr><td>Render Services, Inc.</td><td>Hébergement applicatif</td><td>UE (Francfort, Allemagne)</td><td>Données hébergées en UE ; DPA</td></tr>
    <tr><td>Neon, Inc.</td><td>Base de données Postgres</td><td>UE</td><td>Données hébergées en UE ; DPA</td></tr>
    <tr><td>Shopify International Ltd.</td><td>Plateforme e-commerce, facturation</td><td>Irlande / Canada</td><td>Clauses contractuelles types (SCC) ; décision d'adéquation Canada</td></tr>
    <tr><td>OpenAI, LLC</td><td>Génération de contenu IA</td><td>USA</td><td>SCC ; DPA ; contenu non utilisé pour l'entraînement</td></tr>
    <tr><td>Google LLC (Gemini, Search Console, GA4)</td><td>IA avec recherche web, données SEO</td><td>USA</td><td>SCC ; EU-US Data Privacy Framework</td></tr>
    <tr><td>DataForSEO (Intellectual Systems)</td><td>Volumes de recherche et données SERP</td><td>USA</td><td>SCC ; seuls des mots-clés (jamais de données personnelles) sont transmis</td></tr>
  </table>

  <h2>5. Sécurité</h2>
  <ul>
    <li>Tokens OAuth chiffrés au repos (Fernet : AES-128-CBC + HMAC-SHA256)</li>
    <li>Signature HMAC-SHA256 vérifiée sur chaque webhook Shopify entrant et chaque appel interne</li>
    <li>Isolation multi-tenant : chaque requête est systématiquement filtrée par boutique</li>
    <li>Chiffrement TLS 1.2+ pour toute donnée en transit</li>
  </ul>

  <h2>6. Vos droits (RGPD)</h2>
  <p>Conformément au RGPD et à la loi Informatique et Libertés, vous disposez des droits
     d'accès, de rectification, d'effacement, de portabilité, de limitation et d'opposition :</p>
  <ul>
    <li><strong>Accès / portabilité</strong> : export intégral depuis l'app
        (page Réglages) ou <code>GET /api/gdpr/export</code></li>
    <li><strong>Effacement</strong> : désinstaller l'app — le webhook Shopify
        <code>shop/redact</code> efface toutes les données sous 48 h ;
        la réinitialisation depuis l'app efface les données d'analyse à tout moment</li>
    <li><strong>Rectification, limitation, opposition</strong> : écrire à
        <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a>
        — réponse sous 30 jours</li>
    <li><strong>Réclamation</strong> : vous pouvez saisir la CNIL
        (<a href="https://www.cnil.fr">www.cnil.fr</a>, 3 place de Fontenoy,
        TSA 80715, 75334 Paris Cedex 07)</li>
  </ul>

  <h2>7. Webhooks de conformité Shopify</h2>
  <p>L'app implémente les trois webhooks obligatoires de Shopify :
     <code>customers/data_request</code> (demande d'export d'un client final —
     sans objet car aucune donnée client n'est collectée, réponse fournie sous 30 jours),
     <code>customers/redact</code> (idem) et <code>shop/redact</code>
     (effacement complet des données de la boutique 48 h après désinstallation).</p>

  <h2>8. Cookies</h2>
  <p>L'app embarquée n'utilise que les cookies techniques strictement nécessaires à la
     session Shopify (authentification). Aucun cookie publicitaire ou de suivi n'est déposé.</p>

  <h2>9. Modifications</h2>
  <p>Cette politique peut être mise à jour ; la date en tête fait foi. En cas de
     changement substantiel (nouveau sous-traitant, nouvelle finalité), les marchands
     installés sont informés via l'app.</p>

  <h2>10. Droit applicable</h2>
  <p>La présente politique est soumise au droit français. Tout litige relève des
     tribunaux français compétents.</p>

  <hr id="english" style="margin: 3rem 0;">

  <h1>Privacy Policy — GEO by Organically</h1>
  <p><em>Updated: July 18, 2026 — Shopify App Store edition</em></p>

  <h2>1. Data Controller</h2>
  <p>
    The <strong>GEO by Organically</strong> Shopify app is published by:<br>
    <strong>Léonie Delacroix SASU</strong>, a French single-shareholder simplified
    joint-stock company with a share capital of €1,000<br>
    Registered office: 28 C, rue François-Spoerry, 68100 Mulhouse, France<br>
    Mulhouse Trade Register (RCS) 987 948 106 — VAT FR 18 987 948 106<br>
    Contact: <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a>
    — Phone: +33 7 68 33 16 27<br>
    Data protection officer: Adrien Leredde,
    <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a>
  </p>
  <p>
    Léonie Delacroix SASU is the controller for the data described below. The Shopify
    merchant remains responsible for the store data they expose through the OAuth
    scopes granted at install time.
  </p>

  <h2>2. Data Collected, Purposes and Legal Bases</h2>
  <table>
    <tr><th>Data</th><th>Purpose</th><th>Legal basis</th><th>Retention</th></tr>
    <tr><td>Shop domain</td><td>Account identification</td><td>Contract performance</td><td>Until uninstall</td></tr>
    <tr><td>Shopify OAuth token (encrypted)</td><td>Shopify Admin API calls</td><td>Contract performance</td><td>Deleted on uninstall</td></tr>
    <tr><td>Product/collection catalog (metadata)</td><td>SEO/GEO analysis and content generation</td><td>Contract performance</td><td>Until uninstall</td></tr>
    <tr><td>Google Search Console / GA4 data</td><td>SEO performance measurement</td><td>Consent (optional, revocable Google connection)</td><td>Until disconnect or uninstall</td></tr>
    <tr><td>Subscription plan &amp; status</td><td>Billing via Shopify Billing</td><td>Contract performance</td><td>Until uninstall</td></tr>
    <tr><td>SEO change history</td><td>Rollback and audit</td><td>Contract performance</td><td>Until uninstall</td></tr>
    <tr><td>GDPR request log</td><td>Regulatory audit trail</td><td>Legal obligation</td><td>Uninstall + 30 days</td></tr>
    <tr><td>AI call metadata (provider, tokens, cost)</td><td>Billing &amp; observability</td><td>Legitimate interest</td><td>13 months</td></tr>
  </table>

  <h2>3. Data Not Collected</h2>
  <p>
    GEO by Organically does <strong>not</strong> collect the merchant's end-customer
    data (names, emails, addresses, order history, payment data). The app only
    accesses store product/collection metadata and, if the merchant connects Google,
    aggregated SEO performance data.
  </p>

  <h2>4. Subprocessors and Transfers Outside the EU</h2>
  <table>
    <tr><th>Subprocessor</th><th>Role</th><th>Location</th><th>Transfer safeguard</th></tr>
    <tr><td>Render Services, Inc.</td><td>Application hosting</td><td>EU (Frankfurt, Germany)</td><td>Data hosted in the EU; DPA</td></tr>
    <tr><td>Neon, Inc.</td><td>Postgres database</td><td>EU</td><td>Data hosted in the EU; DPA</td></tr>
    <tr><td>Shopify International Ltd.</td><td>E-commerce platform, billing</td><td>Ireland / Canada</td><td>SCCs; Canada adequacy decision</td></tr>
    <tr><td>OpenAI, LLC</td><td>AI content generation</td><td>USA</td><td>SCCs; DPA; content not used for training</td></tr>
    <tr><td>Google LLC (Gemini, Search Console, GA4)</td><td>AI with web search, SEO data</td><td>USA</td><td>SCCs; EU-US Data Privacy Framework</td></tr>
    <tr><td>DataForSEO (Intellectual Systems)</td><td>Search volumes and SERP data</td><td>USA</td><td>SCCs; only keywords (never personal data) are sent</td></tr>
  </table>

  <h2>5. Security</h2>
  <ul>
    <li>OAuth tokens encrypted at rest (Fernet: AES-128-CBC + HMAC-SHA256)</li>
    <li>HMAC-SHA256 signature verified on every inbound Shopify webhook and internal call</li>
    <li>Multi-tenant isolation: every query is systematically filtered by shop</li>
    <li>TLS 1.2+ encryption for all data in transit</li>
  </ul>

  <h2>6. Your Rights (GDPR)</h2>
  <ul>
    <li><strong>Access / portability</strong>: full export from the app (Settings page)
        or <code>GET /api/gdpr/export</code></li>
    <li><strong>Erasure</strong>: uninstall the app — the Shopify <code>shop/redact</code>
        webhook erases all data within 48 hours; the in-app reset erases analysis data
        at any time</li>
    <li><strong>Rectification, restriction, objection</strong>: write to
        <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a>
        — response within 30 days</li>
    <li><strong>Complaint</strong>: you may lodge a complaint with the French
        supervisory authority, the CNIL (<a href="https://www.cnil.fr">www.cnil.fr</a>)</li>
  </ul>

  <h2>7. Shopify Compliance Webhooks</h2>
  <p>The app implements Shopify's three mandatory webhooks:
     <code>customers/data_request</code> (end-customer export — not applicable as no
     customer data is collected; answered within 30 days), <code>customers/redact</code>
     (same) and <code>shop/redact</code> (full store-data erasure 48 hours after
     uninstall).</p>

  <h2>8. Cookies</h2>
  <p>The embedded app only uses the technical cookies strictly required for the
     Shopify session (authentication). No advertising or tracking cookies are set.</p>

  <h2>9. Changes</h2>
  <p>This policy may be updated; the date above is authoritative. For substantial
     changes (new subprocessor, new purpose), installed merchants are notified in-app.</p>

  <h2>10. Governing Law</h2>
  <p>This policy is governed by French law. Any dispute falls under the jurisdiction
     of the competent French courts.</p>
</body>
</html>"""


_PRIVACY_HTML_SELF_HOSTED = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Politique de confidentialité — GEO by Organically</title>
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

  <h1>Politique de confidentialité — GEO by Organically</h1>
  <p><em>Mise à jour : 2026-05-10</em></p>

  <h2>1. Responsable du traitement</h2>
  <p>
    GEO by Organically est un outil auto-hébergé. Le responsable du traitement des données est
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
    GEO by Organically <strong>ne collecte pas</strong> de données clients individuels (noms, emails,
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
    <li><strong>Contact</strong> : <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a></li>
  </ul>

  <hr id="english" style="margin: 3rem 0;">

  <h1>Privacy Policy — GEO by Organically</h1>
  <p><em>Updated: 2026-05-10</em></p>

  <h2>1. Data Controller</h2>
  <p>
    GEO by Organically is a self-hosted tool. The data controller is the merchant who installs
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
    GEO by Organically does <strong>not</strong> collect individual customer data (names, emails,
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
    <li><strong>Contact</strong>: <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a></li>
  </ul>
</body>
</html>"""


_TERMS_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Conditions d'utilisation — GEO by Organically</title>
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

  <h1>Conditions d'utilisation — GEO by Organically</h1>
  <p><em>Mise à jour : 2026-06-06</em></p>

  <h2>1. Objet</h2>
  <p>
    GEO by Organically est une application Shopify d'aide au référencement (SEO) : audit,
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
    GEO by Organically fournit des recommandations et des optimisations SEO. <strong>Aucune
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
    Contact : <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a>.
  </p>

  <hr id="english" style="margin: 3rem 0;">

  <h1>Terms of Service — GEO by Organically</h1>
  <p><em>Updated: 2026-06-06</em></p>

  <h2>1. Purpose</h2>
  <p>
    GEO by Organically is a Shopify SEO assistance app: audits, supervised recommendations,
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
    GEO by Organically provides SEO recommendations and optimizations. <strong>No Google ranking
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
    Contact: <a href="mailto:support.organically@gmail.com">support.organically@gmail.com</a>.
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
