# Plans & Pricing — Giulio Geo

> Giulio Geo se distribue selon **deux modes** complémentaires. Chacun a son propre système d'authentification et de facturation. Les fonctionnalités offertes par plan (Free/Pro/Agency) sont identiques entre les deux modes.

---

## Deux modes de distribution / Two distribution modes

| Mode | Cible / Audience | Auth | Facturation / Billing |
|---|---|---|---|
| **🛍️ Shopify App Store** | Marchands Shopify (multi-tenant, install 1 clic) | OAuth Shopify | **Shopify Billing API** (`appSubscriptionCreate`) — obligatoire pour App Store |
| **⚙️ Self-hosted / CLI** | Usage interne, agences, devs, environnements custom | Token Custom App | **Licence HMAC** `LEONIE_API_KEY` |

> Règle App Store : toute monétisation in-app **doit** passer par Shopify Billing API. Le système HMAC reste valide pour les usages hors App Store (CLI agence, déploiements internes).

---

## Feature comparison / Comparatif des fonctionnalités

| Feature / Fonctionnalité | Free | Pro | Agency |
|---|:---:|:---:|:---:|
| Shopify catalog crawl | ✅ | ✅ | ✅ |
| Google Search Console data | ✅ | ✅ | ✅ |
| PageSpeed / Core Web Vitals | ✅ | ✅ | ✅ |
| SEO issue detection | ✅ | ✅ | ✅ |
| SEO score (global + per component) | ✅ | ✅ | ✅ |
| Weekly Markdown report | ❌ | ✅ | ✅ |
| Meta title/description updates | ❌ | ✅ | ✅ |
| Image alt text updates | ❌ | ✅ | ✅ |
| 301 redirect bulk import | ❌ | ✅ | ✅ |
| JSON-LD structured data | ❌ | ✅ | ✅ |
| Hreflang (FR/BE/CH) | ❌ | ✅ | ✅ |
| Email alerts (CWV, positions) | ❌ | ✅ | ✅ |
| Rollback (SQLite/Postgres) | ❌ | ✅ | ✅ |
| LLM content generation (meta, FAQ, blog briefs) | ❌ | ✅ | ✅ |
| Niche Intelligence engine | ❌ | ✅ | ✅ |
| Multilingual generation (EN/DE/NL) | ❌ | ❌ | ✅ |
| GA4 revenue attribution | ❌ | ❌ | ✅ |
| Stores / Boutiques | 1 | 1 | Unlimited |
| Multi-tenant config | ❌ | ❌ | ✅ |

---

## 🛍️ Mode Shopify App Store

### Comment ça marche

1. Le marchand installe l'app depuis le Shopify App Store (1 clic).
2. Au premier lancement, l'app propose les plans Free/Pro/Agency.
3. Le marchand choisit un plan → redirection vers Shopify Billing :
   - **Free** : aucune charge, accès aux fonctions d'audit seul.
   - **Pro / Agency** : confirmation Shopify Billing → `appSubscriptionCreate` → l'abonnement apparaît dans la facture Shopify mensuelle du marchand.
4. Shopify reverse les paiements au compte Partner.

### Endpoints API impliqués

| Endpoint | Rôle |
|---|---|
| `GET /api/shops/{shop}/billing/plans` | Retourne les plans disponibles |
| `POST /api/shops/{shop}/billing/subscribe?plan=pro` | Crée la `appSubscriptionCreate` mutation |
| `GET /api/billing/confirm` | Callback de confirmation Shopify |

Voir `app/billing/` pour le code, et `AGENTS.md` règle 12 pour la règle non-négociable.

---

## ⚙️ Mode Self-hosted / CLI

### Comment ça marche

1. L'utilisateur (agence, dev, déploiement interne) génère une clé HMAC via le CLI :

```bash
# FR: Générer une clé Pro pour un client, valide 1 an
# EN: Generate a Pro key for a client, valid 1 year
leonie-seo license issue --tenant client-name --plan pro --days 365

# FR: Générer une clé Agency
# EN: Generate an Agency key
leonie-seo license issue --tenant agency-name --plan agency --days 365

# FR: Vérifier la licence active
# EN: Check the active license
leonie-seo license check
```

2. La clé est ajoutée au `.env` :

```env
LEONIE_API_KEY=LEO-<clé générée>
LICENSE_SECRET=<secret de signature>
```

3. Les scripts CLI vérifient la clé au démarrage. Une clé expirée ou absente bascule l'utilisateur sur le plan Free.

### Résolution du plan (mode self-hosted uniquement)

| Situation | Plan actif |
|---|---|
| Aucune clé configurée | **Pro** (usage personnel, sans restriction) |
| Clé valide avec `plan=free` | **Free** |
| Clé valide avec `plan=pro` | **Pro** |
| Clé valide avec `plan=agency` | **Agency** |
| Clé expirée ou invalide | **Free** |

> En mode Shopify App Store, ces règles **ne s'appliquent pas** : le plan est résolu par Shopify Billing.

---

## API response / Réponse API

L'endpoint `/api/shops/{shop}/status` indique le plan actif **quel que soit le mode** :

```json
{
  "shop": "xxx.myshopify.com",
  "plan": "pro",
  "can_apply": true,
  "can_report": true,
  "can_hreflang": true,
  "can_alerts": true,
  "max_shops": 1
}
```

Le champ `plan` est résolu par Shopify Billing en mode App Store, et par la clé HMAC en mode self-hosted.
