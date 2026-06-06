# Crawl Strategy — Giulio Geo

> Référence canonique de la stratégie de découverte / vérification des URLs Shopify. Définit le **Crawl Level 3** comme socle V1 public et déclasse Screaming Frog en option avancée.
>
> Statut : décisions produit/architecture figées au 2026-05-19 (tâche 128, Phase 11.7). Runtime backend/API partiellement implémenté le 2026-05-20 (tâche 140, Phase 11.8).

---

## 1. Pourquoi ce cadrage

Aujourd'hui, les détecteurs de problèmes techniques majeurs (404, chaînes de redirections, titres/descriptions dupliqués côté HTML rendu, canonical incohérents) reposent **exclusivement** sur l'import d'un CSV Screaming Frog (`app/crawl/client.py`, `app/api/crawl.py:21`). Un marchand non technique :

- ne sait pas installer Screaming Frog ;
- ne sait pas configurer un crawl propre ;
- n'a pas envie d'exporter un CSV puis de l'uploader dans l'app pour obtenir un audit.

Le snapshot Shopify (`scripts/audit/crawl_shopify.py`) couvre produits + collections, mais **ne récupère ni pages CMS, ni blog articles, ni redirects, ni sitemap**, et ne vérifie pas l'état HTTP réel des URLs.

La tâche 128 définit **Crawl Level 3** comme stratégie de découverte par défaut, sans dépendance manuelle à un outil tiers, tout en gardant l'import CSV Screaming Frog accessible en mode avancé pour les agences SEO.

---

## 2. Définition Crawl Level 3

Trois sources combinées, déclenchées par un seul job `crawl_l3` :

| Niveau | Source | Couverture | Effort marchand |
|---|---|---|---|
| **1. Shopify API snapshot** | Shopify Admin GraphQL (`scripts/audit/crawl_shopify.py`) | Produits, collections, pages CMS, articles de blog, redirects URL | Aucun (OAuth déjà en place) |
| **2. Sitemap scan automatique** | `https://{shop}.myshopify.com/sitemap.xml` (ou domaine custom) | Toutes URLs publiques que Shopify expose | Aucun |
| **3. Mini-crawl interne des URLs prioritaires** | HTTP fetch côté backend, limité à N URLs/job | Statut HTTP, canonical balise, hreflang, JSON-LD côté HTML rendu | Aucun |

> Le marchand ne fait **rien** d'autre que d'installer l'app et de lancer un audit. Aucun crawl externe, aucun outil tiers requis.

---

## 3. Périmètre de chaque niveau

### Niveau 1 — Shopify API snapshot (à étendre)

Le snapshot actuel est limité aux produits/collections. À étendre par les tâches consommatrices avec :

- **Pages CMS** (`pages` GraphQL connection) : titre, handle, body HTML, SEO title/description.
- **Articles de blog** (`articles` connection) : titre, handle, blog associé, SEO.
- **Redirects** (`urlRedirects` connection) : path source → target, type.
- **Métadonnées de boutique** : `primaryDomain`, `myshopifyDomain`, locales actives, `publishedPublication` pour Online Store.

Stockage : même table `snapshots` (`app/db.py`), même JSON enrichi. Pas de nouvelle table.

### Niveau 2 — Sitemap scan automatique

- Récupération de `robots.txt` (cf. section 6).
- Extraction des URLs `Sitemap:` déclarées.
- Téléchargement et parsing récursif des sitemaps (sitemap index → sitemaps enfants).
- Sortie : liste de toutes les URLs publiques avec `<lastmod>` quand disponible.
- Volumétrie typique boutique Shopify : 500-5 000 URLs.

Comparaison avec le snapshot Shopify : toute URL présente dans le sitemap mais absente du snapshot, ou inversement, déclenche une alerte (page orpheline, redirect non déclaré).

### Niveau 3 — Mini-crawl interne des URLs prioritaires

Mini-crawler HTTP côté backend Python, **pas un crawler généraliste**. Critères :

- **Volumétrie plafonnée** : N URLs par job, configurable (proposé : 50 par défaut, 200 max Pro, 1 000 max Agency).
- **Sélection des URLs prioritaires** :
  1. produits Active avec impressions GSC > 0 ;
  2. collections Active visibles Online Store ;
  3. pages CMS et articles de blog avec impressions GSC ;
  4. homepage.
- **Vérifications par URL** :
  - statut HTTP final (`200`, `301→200`, `404`, `5xx`) ;
  - chaîne de redirections (max 5 hops) ;
  - balise `<link rel="canonical">` ;
  - balises `<link rel="alternate" hreflang="...">` ;
  - présence et validité minimale du JSON-LD (`Product`, `BreadcrumbList`, `Organization`, `FAQPage`) ;
  - `<title>`, `<meta name="description">` côté HTML rendu (peut différer du SEO Shopify).
- **Respect du robots.txt** obligatoire (cf. section 6).
- **Throttling** : 1 req/s par shop par défaut, headers `User-Agent: Leonie-SEO/1.0 (+https://leonie-seo.app)`.
- **Aucun rendu JS lourd** : `httpx`/`requests` suffisent. Pas de Chromium headless.

---

## 4. Mapping détecteurs → source de données cible

| Détecteur | Source actuelle | Source cible V1 (Crawl L3) | Source avancée (CSV optionnel) |
|---|---|---|---|
| Meta titles manquants / dupliqués | Snapshot Shopify | Snapshot + niveau 3 (HTML rendu) | CSV Screaming Frog |
| Meta descriptions manquantes / dupliquées | Snapshot Shopify | Snapshot + niveau 3 | CSV Screaming Frog |
| Alt text manquants | Snapshot Shopify (produits) | Inchangé | — |
| Duplicate content `/collections/*/products/*` | Snapshot Shopify | Inchangé | CSV en complément |
| 404 publiques | CSV Screaming Frog **uniquement** | **Niveau 2 + 3** (URL sitemap + statut HTTP) | CSV en complément si gros catalogue |
| Chaînes de redirections | CSV Screaming Frog **uniquement** | **Niveau 1 (urlRedirects)** + niveau 3 (chaîne réelle) | CSV en complément |
| Canonical incohérent | CSV Screaming Frog **uniquement** | **Niveau 3** (balise canonical HTML vs URL canonique) | CSV en complément |
| JSON-LD présent et valide | Rien | **Niveau 3** | — |
| Pages orphelines (sitemap vs snapshot) | Rien | **Niveau 2** (diff sitemap ↔ snapshot) | — |
| Hreflang | Rien | **Niveau 3** | — |

> Conséquence : la totalité des détecteurs aujourd'hui CSV-only deviennent natifs Crawl L3. Le CSV reste utile pour les gros catalogues (10 000+ URLs) où le mini-crawl plafonné ne couvre pas tout.

---

## 5. Comportement du job `crawl_l3`

Un seul job async (réutilise la queue existante de la tâche 55) :

```
crawl_l3 (
  shop,
  scope="active",        # cf. docs/product-scope.md
  max_urls=50,           # plafond du niveau 3
  follow_redirects=True,
)
→ étapes :
   1. Extend Shopify snapshot (pages, articles, redirects, metafields).
   2. Fetch robots.txt + sitemap.xml.
   3. Compute prioritized URL list (GSC + scope active + caps par plan).
   4. Mini-crawl HTTP (throttle 1 req/s, max_urls plafonné).
   5. Aggregate findings → table `crawl_findings` (à créer par la tâche d'implémentation).
   6. Update audit issues feed (réutilise `detect_issues.py`).
```

Fréquence recommandée : à la demande + cron hebdomadaire (réutilise la tâche 28).

---

## 6. robots.txt

- **Lecture obligatoire** avant tout mini-crawl.
- Respect strict des règles `User-agent: *` et `User-agent: Leonie-SEO`.
- Extraction des `Sitemap:` déclarés pour alimenter le niveau 2.
- Si robots.txt absent → fallback `/sitemap.xml` à la racine.
- Cache 24h par shop.

---

## 7. Import Screaming Frog CSV — option avancée

L'import CSV (`POST /api/shops/{shop}/crawl/upload`, `app/api/crawl.py:21`) reste en place mais **n'est plus une étape obligatoire du parcours marchand standard**.

Positionnement V1 :

- accessible depuis l'écran "Audit → Mode avancé" ;
- réservé aux agences ou marchands techniques ;
- les findings CSV **complètent** les findings Crawl L3 (pas de remplacement), avec une colonne de provenance (`source=crawl_l3` ou `source=screaming_frog`) ;
- aucun message d'erreur ou de message marketing ne suggère que ce CSV est requis pour un audit complet.

---

## 8. Limites et garde-fous

- **Volumétrie mini-crawl plafonnée par plan** : Free 50, Pro 200, Agency 1 000 URLs/job. Cohérent avec quotas LLM (`docs/llm-strategy.md`).
- **Throttling** : 1 req/s par shop, 5 connexions parallèles max. Pas de mode burst.
- **Respect robots.txt strict** : aucune URL `Disallow:` n'est crawlée.
- **Domaine personnalisé** : utiliser `primaryDomain` si disponible, sinon `{shop}.myshopify.com`. Toujours vérifier que le domaine répond avant de lancer le mini-crawl.
- **Pas de scraping concurrents** dans ce crawl L3. Le module Competitor Monitor (tâche 132) a un budget de crawl séparé.
- **Pas de stockage de HTML brut** : seules les valeurs extraites (canonical, hreflang, statut, JSON-LD parsé) sont persistées.
- **GDPR** : aucune donnée personnelle n'est traitée par le crawl L3 ; seules les pages publiques Shopify sont visitées.
- **Cleanup** : les findings `crawl_findings` ont un TTL 90 jours (purge automatique).

---

## 9. Mapping module par module

### Fichiers existants étendus ou restant à étendre

| Module | Fichier | Évolution attendue |
|---|---|---|
| Shopify crawl GraphQL | `scripts/audit/crawl_shopify.py:24` | ✅ Pages, articles, redirects et métadonnées shop ajoutés ; metafields/locales restent à compléter si nécessaires |
| Job audit | `app/jobs/audit_snapshot.py` | ✅ Snapshot enrichi pages/articles/redirects ; l'orchestration Crawl L3 complète passe par `app/api/crawl.py` |
| Détecteurs issues | `scripts/audit/detect_issues.py` | Consommer la nouvelle source `crawl_findings` |
| API audit | `app/api/audit.py:53` | Inchangé en signature, source enrichie en interne |
| API crawl | `app/api/crawl.py:21` | ✅ Route native `POST /crawl/l3` ajoutée ; upload CSV conservé, UI avancée à porter |
| UI audit | `shopify-app/app/routes/app.audit.tsx:158` | Mettre en avant le bouton "Lancer l'audit" (Crawl L3 auto), reléguer "Importer CSV" en lien secondaire |

### Modules créés en tâche 140

| Module | Rôle |
|---|---|
| `app/crawl/sitemap.py` | ✅ Parser sitemap.xml + index sitemaps + diff avec snapshot |
| `app/crawl/robots.py` | ✅ Parsing robots.txt, sitemaps déclarés, vérification d'autorisation par URL |
| `app/crawl/mini.py` | ✅ Mini-crawler HTTP plafonné, throttling, vérifications par URL |
| `app/crawl/findings.py` | ✅ Aggregation des findings sitemap/mini-crawl, persistence `crawl_findings` |

---

## 10. Critères d'acceptation de l'implémentation future

À cocher quand une tâche concrétise le Crawl L3 :

- [x] Un audit backend peut être lancé **sans installer Screaming Frog** via `POST /api/shops/{shop}/crawl/l3`.
- [ ] L'extension du snapshot Shopify couvre pages CMS + articles de blog + redirects + metafields.
- [x] `robots.txt` est lu et respecté avant tout mini-crawl.
- [x] Le sitemap est parsé automatiquement et son diff avec le snapshot est exposé.
- [x] Le mini-crawl HTTP plafonné détecte 404, redirect chains, canonical, hreflang, JSON-LD.
- [x] Aucune URL `Disallow:` n'est requêtée.
- [x] Throttling 1 req/s + user-agent identifiable.
- [ ] Plafonds Free/Pro/Agency appliqués.
- [x] Findings persistés avec colonne `source` (`crawl_l3`).
- [ ] CSV Screaming Frog accessible en "Mode avancé", aucun message indiquant qu'il est requis.
- [ ] TTL 90 jours sur `crawl_findings`.

---

## 11. Garde-fous transversaux

- **Pas de Chromium headless en V1.** Si JS rendering devient nécessaire (Web Components, hydration tardive), le porter dans une tâche d'infra dédiée, pas dans le Crawl L3 standard.
- **Pas de crawl externe agressif.** Toutes les URLs requêtées appartiennent au shop du marchand.
- **Pas de log de HTML brut** côté serveur (taille, RGPD, dette).
- **Pas de mélange Competitor Monitor / Crawl L3.** Le monitoring concurrent a son propre budget et ses propres règles.
- **Compatibilité ascendante.** L'endpoint d'upload CSV existant reste fonctionnel.

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Définition Crawl L3 (3 niveaux) | ✅ Documenté ici | Section 2 |
| Mapping détecteurs → source cible | ✅ Documenté ici | Section 4 |
| Comportement du job `crawl_l3` | ✅ Spécifié ici | Section 5 |
| Respect robots.txt | ✅ Spécifié ici | Section 6 |
| Screaming Frog en option avancée | ✅ Documenté ici | Section 7 |
| Plafonds Free/Pro/Agency | ✅ Documenté ici | Section 8 |
| Extension du snapshot Shopify (pages, articles, redirects) | ✅ Implémenté en tâche 140 | Section 9 |
| `app/crawl/sitemap.py`, `robots.py`, `mini.py`, `findings.py` | ✅ Créés en tâche 140 | Section 9 |
| Mini-crawl HTTP avec throttling + JSON-LD parsing | ✅ Implémenté en tâche 140 | Section 3 |
| UI : bouton "Audit Crawl L3" mis en avant, CSV en avancé | ⏳ À porter par la tâche UI dédiée | Section 9 |

> Les éléments ⏳ restants après la tâche 140 concernent surtout l'UI Audit, les plafonds par plan, les champs Shopify avancés non indispensables au runtime V1 et la purge TTL des findings.
