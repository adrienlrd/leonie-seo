# Unified AI Search Readiness Audit — GEO by Organically

> Référence canonique du score d'audit unique exposé au marchand. Définit comment GEO by Organically fusionne facts, SEO issues, JSON-LD, Crawl L3, PageSpeed, status produit et signaux niche en **un seul score lisible** par produit, avec sous-scores explicatifs et actions recommandées.
>
> Statut : décisions produit/architecture figées au 2026-05-19 (tâche 131, Phase 11.7). Aucun code applicatif n'est modifié dans cette tâche.

---

## 1. Pourquoi ce cadrage

Trois scores parallèles sont affichés aujourd'hui dans l'UI :

| Score | Source | Page Remix |
|---|---|---|
| `readiness_score` (0-100, 6 composants) | `app/geo/readiness.py:137` | `app.geo-readiness.tsx` |
| `seo_score` (composants meta/alt/CWV/redirects/duplicates) | `scripts/report/generate_report.py:42`, `app/api/audit.py:53` | `app.audit.tsx` |
| `completeness_score` facts (0-1) | `app/geo/facts.py:122` | `app.geo-facts.tsx` |

Un marchand non technique voit trois chiffres différents pour le même produit. **22+ pages Remix** consomment au moins un score. La tâche 131 fixe les règles pour réduire ça à **un seul score canonique** (`AI Search Readiness`), 6 sous-scores explicatifs, et une liste d'actions priorisées — sans casser les détecteurs existants.

---

## 2. Le score unifié : `AI Search Readiness`

### Définition

Un seul score `0–100` par produit, par collection, par boutique. Affiché en grand dans toutes les vues. Pondération réutilisée et étendue depuis `app/geo/readiness.py:137`.

### Six sous-scores explicatifs (poids V1)

| Sous-score | Poids | Sources | Couvre |
|---|---|---|---|
| **Facts** | 25 % | `app/geo/facts.py:122` (confirmed + missing) | Faits produits confirmés (matières, dimensions, certifications, origines, usages, garanties). Pénalité si faits sensibles manquants (cf. `docs/niche-understanding.md` §5). |
| **Schema** | 20 % | `app/api/jsonld.py:179`, builders `app/jsonld/builders.py:20` | JSON-LD `Product` valide + `BreadcrumbList` + `FAQPage` quand pertinent + `Organization` au niveau boutique. |
| **Answerability** | 20 % | FAQ items, Answer Blocks, `app/geo/faq_generator.py` (read-only) | Couverture des intentions conversationnelles (cf. `docs/niche-understanding.md` §3 `conversational_intents`). |
| **Trust** | 15 % | NER `app/niche/ner.py`, signaux marchand (avis, garanties, retours, livraison) | Preuves de confiance présentes sur la page produit. |
| **SEO** | 10 % | `scripts/audit/detect_issues.py:19` + Crawl L3 (`docs/crawl-strategy.md`) | Meta titles/descriptions, alt text, duplicates, canonical, hreflang, statut HTTP, redirect chains. |
| **Commerce** | 10 % | `app/geo/readiness.py:123` (existant) + Shopify status | Statut `ACTIVE` + visible Online Store (cf. `docs/product-scope.md`), stock, prix. |

Total : 100 %. Les poids peuvent être réajustés post-pilote, mais ils restent **publics dans la doc** — pas de pondération magique cachée.

### Niveaux lisibles

| Score | Niveau | Affichage marchand |
|---|---|---|
| ≥ 80 | `Excellent` | Vert, badge "Prêt pour les moteurs IA" |
| 65–79 | `Bon` | Vert clair, "Quelques améliorations possibles" |
| 45–64 | `Partiel` | Orange, "Plusieurs lacunes à corriger" |
| < 45 | `Faible` | Rouge, "Page à reprendre" |

Pas de pourcentage brut isolé : toujours le couple `score + niveau` côté UI.

---

## 3. Mapping détecteurs → sous-score

Tous les détecteurs existants restent en place, ils alimentent un sous-score précis. Aucune duplication d'algorithme.

### Sous-score **Facts**

- `analyze_product_facts()` `app/geo/facts.py:122` → ratio `confirmed / (confirmed + missing)` × 100.
- Bonus si faits sensibles (`materials`, `origins`, `certifications`) tous confirmés.
- Malus si faits sensibles manquants.

### Sous-score **Schema**

- `validate_jsonld()` `app/api/jsonld.py:179` → présence + champs requis Product.
- +20 pts si `FAQPage` valide associé.
- +10 pts si `BreadcrumbList` valide.
- −20 pts par erreur de schéma critique.

### Sous-score **Answerability**

- `niche_hypothesis.conversational_intents` × FAQ items couvrant ces intents = ratio de couverture.
- Bonus si Answer Block présent et conforme au schéma.
- Malus si une intention `high confidence` n'est couverte par aucune Q/R.

### Sous-score **Trust**

- Signaux NER (`app/niche/ner.py`) : nombre d'entités `target`, `property`, `certification` extraites.
- Signaux marchand : avis, livraison, retours, garantie présents dans la description.
- Bonus si JSON-LD `AggregateRating` valide.

### Sous-score **SEO**

- Détecteurs existants `scripts/audit/detect_issues.py:19` : meta title (présence, longueur, dup), meta description (idem), alt text manquants, duplicate content.
- Findings Crawl L3 (`docs/crawl-strategy.md` §3) : statut HTTP final, redirect chains, canonical, hreflang.

### Sous-score **Commerce**

- `_commerce_score()` existant `app/geo/readiness.py:123` : `status=ACTIVE`, visibilité Online Store, stock variants.
- Cohérent avec `docs/product-scope.md` : seuls les produits Active Online Store ont un score affiché en vue principale. Drafts ont un sous-score Commerce nul, ce qui les tire vers `Faible` et les pousse hors de la vue principale.

---

## 4. Intégration des hypothèses niche

Quand `shop_config.niche_hypothesis.status == "validated_by_merchant"` (cf. `docs/niche-understanding.md` §6) :

- `forbidden_promises` : si la fiche produit contient une promesse listée → malus −10 sur `Trust` + alerte `"Promesse à éviter : ..."` dans les actions recommandées.
- `brand_voice.do_not_say` : signalé comme alerte (sans malus), à corriger au prochain passage AI Content Action.
- `conversational_intents` : alimente le sous-score `Answerability`.
- `priority_products` : pas d'effet sur le score brut, mais influence l'ordre d'affichage dans la liste.

Tant que `niche_hypothesis` n'est pas validée, le score est calculé sur les heuristiques par défaut, sans ces ajustements.

---

## 5. Schéma de sortie unifié

Un seul endpoint canonique (à exposer par la tâche d'implémentation) :

```
GET /api/shops/{shop}/audit/readiness?scope=active
→ {
  "shop": "string",
  "generated_at": "ISO date",
  "scope": "active",                 # cf. docs/product-scope.md
  "global_score": 0-100,
  "global_level": "excellent|bon|partiel|faible",
  "products": [
    {
      "product_id": "string",
      "title": "string",
      "handle": "string",
      "score": 0-100,
      "level": "excellent|bon|partiel|faible",
      "components": {
        "facts": {"score": 0-100, "weight": 0.25},
        "schema": {"score": 0-100, "weight": 0.20},
        "answerability": {"score": 0-100, "weight": 0.20},
        "trust": {"score": 0-100, "weight": 0.15},
        "seo": {"score": 0-100, "weight": 0.10},
        "commerce": {"score": 0-100, "weight": 0.10}
      },
      "reasons": [
        {"category": "facts|schema|answerability|trust|seo|commerce",
         "label": "string",
         "severity": "info|warning|critical"}
      ],
      "recommended_actions": [
        {"action": "string",
         "category": "facts|schema|answerability|trust|seo|commerce",
         "impact_estimate": "low|medium|high",
         "effort_estimate": "low|medium|high"}
      ],
      "niche_alerts": [
        {"type": "forbidden_promise|do_not_say",
         "message": "string"}
      ]
    }
  ],
  "summary": {
    "by_level": {"excellent": int, "bon": int, "partiel": int, "faible": int},
    "average_score": 0-100,
    "products_in_scope": int
  }
}
```

### Règles sur la sortie

- **Toujours retourner les 6 sous-scores**, jamais en omettre un. Si une donnée manque (ex : Crawl L3 pas encore exécuté), le sous-score affiche un `null` côté API et un message `"En attente de [source]"` côté UI.
- **`reasons`** est ordonnée par sévérité décroissante, max 6 items.
- **`recommended_actions`** est ordonnée par `impact × (1/effort)` décroissant, max 3 items. Sert directement au Priority Engine (tâche 133).
- **`niche_alerts`** ne fait pas baisser le score directement (sauf `forbidden_promise` qui pénalise via `Trust`), mais alerte le marchand.

---

## 6. Endpoints à fusionner / déprécier

| Endpoint actuel | Statut post-131 | Action |
|---|---|---|
| `GET /api/shops/{shop}/geo/readiness` (`app/api/geo.py:127`) | Remplacé | Redirection 301 vers `/audit/readiness` |
| `GET /api/shops/{shop}/audit/issues` (`app/api/audit.py:53`) | Conservé | Reste utile pour le drill-down par catégorie SEO |
| `GET /api/shops/{shop}/audit/score` (`app/api/audit.py:71`) | Déprécié | Marqué `deprecated` dans la doc, à supprimer après migration UI |
| `GET /api/shops/{shop}/geo/facts` (`app/api/geo.py:105`) | Conservé | Vue détaillée facts par produit, indépendante |
| `GET /api/shops/{shop}/geo/crawlability` (`app/api/geo.py:558`) | Conservé | Alimente `Schema` + `SEO` mais reste consultable |
| `GET /api/shops/{shop}/jsonld/status` | Conservé | Drill-down schéma |

**Principe** : un endpoint canonique pour le score global, des endpoints existants pour le drill-down détaillé. Pas de suppression brutale ; dépréciation graduelle.

---

## 7. Comportement UI cible

### Vue principale (vue marchand non technique)

Page unique `app.audit-readiness.tsx` (à créer, fusion de `app.geo-readiness.tsx`, `app.geo-facts.tsx`, `app.audit.tsx`) :

- En haut : **score global** boutique (gros chiffre + niveau coloré).
- Bandeau "x produits Active Online Store évalués" (cf. `docs/product-scope.md`).
- Liste paginée par produit : score + niveau + 3 actions recommandées + niche alerts visibles.
- Drill-down par produit : 6 sous-scores en barres + `reasons` détaillées + liens vers `app.geo-facts.tsx`, `app.audit.tsx`, `app.jsonld.tsx` pour le détail.

### Pages secondaires conservées

- `app.geo-facts.tsx` : drill-down facts par produit.
- `app.audit.tsx` : drill-down issues SEO par catégorie.
- `app.jsonld.tsx` : drill-down JSON-LD.

Elles ne sont **plus des entrées dans le menu principal**. Elles sont accessibles via les liens du drill-down de la vue principale uniquement.

### Pages à déprécier UI

- `app.geo-readiness.tsx` : fusionnée dans `app.audit-readiness.tsx`.
- Les 22+ pages Remix qui réimplémentent un mini-score doivent se brancher sur le nouveau endpoint canonique ou retirer leur score.

---

## 8. Mapping fichiers

### Existant à réutiliser (pas réécrire)

| Fichier | Rôle dans la tâche 131 |
|---|---|
| `app/geo/readiness.py:137` (`score_product_readiness`) | Cœur du calcul, structure quasi-prête, à étendre |
| `app/geo/readiness.py:199` (`score_catalog_readiness`) | Agrégation boutique |
| `app/geo/facts.py:122` (`analyze_product_facts`) | Sous-score Facts |
| `app/api/jsonld.py:179` (`validate_jsonld`) | Sous-score Schema |
| `app/jsonld/builders.py:20` | Builders Product/Collection/Organization |
| `scripts/audit/detect_issues.py:19` | Sous-score SEO (meta, alt, duplicates) |
| `app/niche/ner.py` | Sous-score Trust (entités confiance) |
| `app/api/pagespeed.py:36` | Optionnel — pas dans V1 du score (CWV reste un signal séparé pour ne pas pénaliser un produit dont la lenteur vient du thème global) |
| `app/geo/crawlability.py:57` | Sous-score Schema (llms.txt + crawl status) |
| `app/shop_config_store.py:1` | Lecture `niche_hypothesis` pour ajustements |

### À créer par la tâche d'implémentation (post-131)

| Fichier | Rôle |
|---|---|
| `app/geo/readiness.py` (étendre) | Ajouter sous-score `Answerability`, ajustements `niche_hypothesis`, intégration findings Crawl L3 |
| `app/api/audit.py` (étendre) | Route `GET /api/shops/{shop}/audit/readiness` (canonique) |
| `shopify-app/app/routes/app.audit-readiness.tsx` | Vue unifiée principale |
| Migration `app.geo-readiness.tsx` → `app.audit-readiness.tsx` | Lien Redirect Remix |

---

## 9. Note explicite sur PageSpeed / CWV

Le score CWV (`app/api/pagespeed.py:36`) **n'est pas inclus dans le score unifié V1**. Raisons :

- CWV est largement déterminé par le thème Shopify, pas par les optimisations GEO by Organically.
- Inclure CWV pénaliserait des marchands qui ne peuvent pas y agir depuis l'app.
- CWV reste visible comme **signal séparé** sur la page audit, avec ses propres alertes.

À reconsidérer post-pilote si les marchands demandent un score global incluant la performance.

---

## 10. Garde-fous

- **Pas de pondération secrète.** Les poids des 6 sous-scores sont publiés dans cette doc et lisibles côté UI ("Comment ce score est calculé").
- **Pas de double comptage.** Un détecteur alimente un seul sous-score. Si un signal est pertinent pour deux sous-scores, on choisit le plus représentatif.
- **Pas de score affiché si scope ≠ active sans annotation.** Cohérent avec `docs/product-scope.md` : Drafts et Archived ont un score séparé, annoté.
- **Pas de score pour les produits hors snapshot frais.** Si le snapshot a > 7 jours, afficher un avertissement "Données catalogue obsolètes — relancer le snapshot".
- **`recommended_actions` ne déclenchent rien automatiquement.** Elles sont consommées par le Priority Engine (133), pas appliquées sans validation marchand (cf. `docs/AGENTS.md` règles dry-run).
- **Compatibilité ascendante.** Tous les endpoints existants restent fonctionnels pendant la migration. Pas de breaking change immédiat.
- **Pas de re-calcul à la volée.** Le score est calculé par job async (réutilise la queue existante) et persisté. Lecture rapide côté UI.

---

## 11. Critères d'acceptation de l'implémentation future

À cocher quand une tâche concrétise l'audit unifié :

- [ ] Un seul score `AI Search Readiness` est exposé par `GET /api/shops/{shop}/audit/readiness`.
- [ ] Les 6 sous-scores (facts/schema/answerability/trust/seo/commerce) sont toujours retournés.
- [ ] Le scope par défaut est `active` (`docs/product-scope.md`).
- [ ] Les findings Crawl L3 alimentent les sous-scores SEO et Schema (`docs/crawl-strategy.md`).
- [ ] Les ajustements niche (`forbidden_promises`, `do_not_say`) sont appliqués si `niche_hypothesis.status == "validated_by_merchant"` (`docs/niche-understanding.md`).
- [ ] Les 4 niveaux lisibles (`excellent`, `bon`, `partiel`, `faible`) sont affichés en plus du score brut.
- [ ] `reasons` (max 6) + `recommended_actions` (max 3) sont retournées par produit.
- [ ] CWV n'est pas inclus dans le score V1, mais reste visible comme signal séparé.
- [ ] L'UI principale `app.audit-readiness.tsx` remplace les 3 pages parallèles dans le menu.
- [ ] Les pages drill-down (`app.geo-facts`, `app.audit`, `app.jsonld`) sont accessibles via liens uniquement.
- [ ] La doc "Comment ce score est calculé" est accessible en 1 clic depuis le score.
- [ ] Snapshot > 7 jours = bandeau d'avertissement.

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Score unifié + 6 sous-scores pondérés | ✅ Documenté | Section 2 |
| Mapping détecteurs → sous-score | ✅ Documenté | Section 3 |
| Intégration `niche_hypothesis` | ✅ Spécifié | Section 4 |
| Schéma JSON de sortie | ✅ Spécifié | Section 5 |
| Stratégie endpoints (fusion / dépréciation) | ✅ Documenté | Section 6 |
| Vue UI unifiée + dépréciation pages parallèles | ✅ Documenté | Section 7 |
| CWV hors V1 du score, signal séparé conservé | ✅ Décidé | Section 9 |
| Garde-fous (pondération publique, scope, freshness) | ✅ Documentés | Section 10 |
| Extension `app/geo/readiness.py` (Answerability, niche, Crawl L3) | ⏳ À porter | Section 8 |
| Route `GET /audit/readiness` canonique | ⏳ À créer | Section 8 |
| UI `app.audit-readiness.tsx` | ⏳ À créer | Section 7 |
| Branchement des 22+ pages Remix au score unifié | ⏳ À porter incrémentalement | Section 7 |

> Les éléments ⏳ ne sont pas le périmètre de la tâche 131. Ils seront pris en charge par la tâche d'implémentation Audit Unifié ultérieure et par les tâches consommatrices 133 (Priority Engine) et 137 (Dashboard simplification).
