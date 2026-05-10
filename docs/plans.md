# Plans & Pricing — Léonie SEO

## Comparison / Comparatif

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
| SQLite rollback | ❌ | ✅ | ✅ |
| Stores / Boutiques | 1 | 1 | Unlimited |
| Multi-tenant config | ❌ | ❌ | ✅ |

---

## Plan resolution / Résolution du plan

Le plan actif est lu depuis la clé `LEONIE_API_KEY` dans votre `.env`.

| Situation | Plan actif |
|---|---|
| Aucune clé configurée | **Pro** (usage personnel, sans restriction) |
| Clé valide avec `plan=free` | **Free** |
| Clé valide avec `plan=pro` | **Pro** |
| Clé valide avec `plan=agency` | **Agency** |
| Clé expirée ou invalide | **Free** |

---

## Generate a key / Générer une clé

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

---

## API response / Réponse API

The `/api/shops/{shop}/status` endpoint includes the active plan:

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
