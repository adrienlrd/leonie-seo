# Unified Opportunity Finder — Léonie SEO

> Référence canonique du module qui répond à **une seule question** : *« quelles pages produits actives méritent une action maintenant ? »*. Fusionne les 7 logiques d'opportunités existantes en une liste unifiée, scorée et explicable, consommée par le Priority Engine (133).
>
> Statut : décisions produit/architecture figées au 2026-05-20 (tâche 132, Phase 11.7). Aucun code applicatif n'est modifié dans cette tâche.

---

## 1. Pourquoi ce cadrage

Aujourd'hui, sept détecteurs d'opportunités fonctionnent indépendamment, exposés sur **4-6 pages Remix distinctes** :

| Logique | Module Python | Page Remix |
|---|---|---|
| GSC Opportunities (positions 11-20, faible CTR, long terme) | `scripts/audit/detect_gsc_opportunities.py:77` | `app.niche` |
| Keyword Gaps / Longue traîne (Jaccard catalog ↔ GSC) | `app/niche/gaps.py:106`, `app/api/longtail.py:39` | `app.longtail`, `app.niche` |
| Intent Clusters (4 intents : info/transac/commercial/navi) | `app/niche/intent.py:390` | `app.niche` |
| Niche Clusters produits (TF-IDF) | `app/niche/clustering.py:142` | `app.niche` |
| Cannibalisation (queries multi-pages, severity) | `scripts/audit/detect_cannibalization.py:49` | `app.cannibalization` |
| Maillage interne (orphans, link opportunities) | `scripts/report/detect_internal_links.py:23` | `app.internal-links` |
| AI Answer Competitor Monitor (light, mock) | `app/geo/competitors.py:62` | `app.geo-competitors` |

Un marchand non technique voit donc **4-6 listes parallèles** sans hiérarchie. Aucune ne répond directement à : *« pour CE produit, faut-il agir ? pourquoi ? quoi faire ? »*

La tâche 132 fixe les règles pour produire **une liste unique scorée au niveau produit** (pas au niveau requête, ni au niveau cluster) avec, pour chaque entrée : raison(s), action(s) recommandée(s), gain estimé, effort, confiance, sources.

---

## 2. Question produit unique

L'Opportunity Finder répond à :

> **Quelles pages produits ACTIVE Online Store ont, MAINTENANT, le meilleur ratio impact / effort pour une optimisation GEO/SEO ?**

Hors scope :
- Suggérer de *créer* un produit ou une collection (c'est le job du **Collection Builder**, tâche 112, et du Pre-launch check, cf. `docs/product-scope.md`).
- Détecter une opportunité hors snapshot Shopify (page CMS, blog) — V1 reste centré produits ; pages CMS sont une extension V1.1.
- Lancer une action automatique — c'est le job du Priority Engine (133) puis du workflow Review & Safe Apply (135).

---

## 3. Sources fusionnées et contribution

Chaque détecteur existant **continue de tourner indépendamment**. L'Opportunity Finder est une couche d'agrégation par produit, pas un remplacement.

| Source | Détecteur | Contribution par produit |
|---|---|---|
| GSC quick wins | `detect_gsc_opportunities.py:77` (positions 11-20) | +Signal `gsc_quick_win` avec gain estimé en clics |
| GSC low CTR | `detect_gsc_opportunities.py:77` (4-10, CTR < benchmark) | +Signal `gsc_low_ctr` |
| GSC long term | `detect_gsc_opportunities.py:77` (21-50, impressions hautes) | +Signal `gsc_long_term` (impact futur) |
| Keyword Gaps | `app/niche/gaps.py:106` (Jaccard ≥ 0.15, score 0-100) | +Signal `keyword_gap` si la requête longue traîne pointe vers ce produit |
| Intent Clusters | `app/niche/intent.py:390` | +Tag `intent: informational/transactional/commercial/navigational` sur chaque opportunité |
| Cannibalisation | `detect_cannibalization.py:49` | +Signal `cannibalization_conflict` si le produit est en compétition avec une autre page |
| Internal Links | `detect_internal_links.py:23` | +Signal `link_opportunity` (orphan ou ancres manquantes) |
| Competitor Monitor (light) | `app/geo/competitors.py:62` | +Signal `competitor_visible` (mock V1, scraping V2) sur les intentions où des concurrents dominent |
| Audit Readiness (131) | `docs/readiness-audit.md` | +Signaux `low_facts`, `weak_schema`, `weak_answerability`, `weak_trust` — pris des `recommended_actions` du score unifié |
| Niche hypothesis (130) | `docs/niche-understanding.md` | Filtre `priority_products` (boost), `forbidden_promises` (alerte sans boost), `conversational_intents` (matching pondéré) |

> Important : aucun nouveau détecteur n'est créé. Le Finder consomme les sorties de l'existant + le score 131 + les hypothèses 130.

---

## 4. Schéma de sortie unifié

Endpoint canonique (à exposer par la tâche d'implémentation) :

```
GET /api/shops/{shop}/opportunities?scope=active&top=20
→ {
  "shop": "string",
  "generated_at": "ISO date",
  "scope": "active",
  "total_products_scanned": int,
  "opportunities": [
    {
      "product_id": "string",
      "handle": "string",
      "title": "string",
      "opportunity_score": 0-100,
      "tier": "high|medium|low",
      "primary_reason": "string court",
      "signals": [
        {
          "type": "gsc_quick_win|gsc_low_ctr|gsc_long_term|keyword_gap|cannibalization_conflict|link_opportunity|competitor_visible|low_facts|weak_schema|weak_answerability|weak_trust",
          "weight": 0-1,
          "evidence": {
            "metric": "string",
            "value": "number|string",
            "source": "gsc|niche|audit|crawl_l3|competitors|niche_hypothesis"
          }
        }
      ],
      "matched_queries": ["string"],
      "matched_intents": ["informational|transactional|commercial|navigational"],
      "recommended_actions": [
        {
          "action": "string",
          "category": "facts|schema|faq|internal_link|meta|content|fix_cannibalization|fix_redirect",
          "expected_metric": "string",
          "impact_estimate": "low|medium|high",
          "effort_estimate": "low|medium|high",
          "depends_on": ["string"]
        }
      ],
      "niche_alerts": [
        {"type": "forbidden_promise|do_not_say", "message": "string"}
      ],
      "confidence": "low|medium|high"
    }
  ],
  "summary": {
    "by_tier": {"high": int, "medium": int, "low": int},
    "by_intent": {"informational": int, "transactional": int, "commercial": int, "navigational": int},
    "average_score": 0-100
  }
}
```

### Règles sur la sortie

- **Une entrée par produit**, pas par requête. Si 5 quick wins GSC pointent vers le même produit, c'est **1 opportunité** avec 5 signaux et 5 `matched_queries`.
- **Tri** : par `opportunity_score` décroissant. `tier=high` ≥ 70, `medium` 40-69, `low` < 40.
- **`top` paramétrable** (défaut 20, max 100). Aucun usage qui demande > 100 opportunités — c'est un signe que la couche niche n'est pas alignée.
- **`primary_reason`** : une seule phrase, lisible non-technique, ex : *« Reçoit déjà des impressions Google mais peu de clics — meta description à retravailler »*.
- **`recommended_actions`** : max 3 par opportunité. Idem que le score 131, mais ici filtrées par signaux trouvés.
- **`confidence`** : `high` si ≥ 3 signaux convergents OU score 131 récent (< 7j) ; `medium` si 1-2 signaux + données fraîches ; `low` sinon.

---

## 5. Formule de scoring

Réutilisation maximale, pas de nouvelle pondération opaque.

```
opportunity_score = 100 × (
    0.30 × gsc_signal_strength       # max(quick_win, low_ctr, long_term×0.5)
  + 0.20 × keyword_gap_score          # déjà 0-1 dans gaps.py
  + 0.15 × audit_action_pressure      # 1 - (readiness_score / 100) depuis 131
  + 0.10 × intent_match_boost         # 1 si conversational_intents niche matched
  + 0.10 × cannibalization_severity   # 0-1 depuis detect_cannibalization
  + 0.10 × link_opportunity_density   # 0-1 depuis detect_internal_links
  + 0.05 × competitor_pressure        # 0-1 depuis competitors monitor (light V1)
)
```

Total des poids = 1.00. Publiés dans la doc et accessibles côté UI ("Comment cette opportunité est calculée").

### Ajustements `niche_hypothesis`

Quand `shop_config.niche_hypothesis.status == "validated_by_merchant"` :

- Produit listé dans `priority_products` → **+10 pts** plafonnés à 100.
- Produit qui couvre une `conversational_intents` à `high confidence` non couverte ailleurs → **+5 pts**.
- Produit dont la fiche contient une `forbidden_promises` → **alerte non-bloquante**, pas de malus sur le score (le malus tombe sur Trust dans le score 131).

---

## 6. Comportement UI cible

### Vue principale `app.opportunities.tsx` (à créer)

- En haut : compteur `x opportunités sur y produits ACTIVE Online Store évalués`.
- Liste paginée triée par `opportunity_score`, max 20 visibles par défaut.
- Chaque ligne : titre produit + `tier` (badge) + `primary_reason` + bouton "Voir le détail".
- Détail (drawer ou page produit) : signaux affichés en chips, `matched_queries`, `recommended_actions`, `niche_alerts`.

### Vue secondaire par intent (filtre)

- Tabs Polaris : `Toutes | Information | Transaction | Commerce | Navigation`.
- Réutilise le même endpoint avec `?intent=...`.

### Pages existantes — repositionnement

| Page actuelle | Statut post-132 |
|---|---|
| `app.niche` | Conservée comme **vue diagnostic niche** (clusters, gaps bruts, intents bruts). N'affiche plus la mini-liste GSC opportunities (déplacée vers `app.opportunities`). |
| `app.longtail` | Conservée comme **drill-down requêtes longue traîne**. Lien depuis `app.opportunities` quand une opportunité a un signal `keyword_gap`. |
| `app.cannibalization` | Conservée comme **drill-down pairs**. Lien depuis `app.opportunities` quand signal `cannibalization_conflict`. |
| `app.internal-links` | Conservée comme **drill-down maillage**. Lien depuis `app.opportunities` quand signal `link_opportunity`. |
| `app.geo-competitors` | Conservée comme **drill-down competitor monitor**. Lien depuis `app.opportunities` quand signal `competitor_visible`. |
| `app.geo-answer-blocks` | Inchangé (workflow content, pas opportunités). |

> Principe identique à 131 : un point d'entrée unifié, les pages spécialisées deviennent des drill-downs accessibles via liens.

---

## 7. Endpoints à fusionner / déprécier

| Endpoint actuel | Statut post-132 |
|---|---|
| `GET /api/shops/{shop}/gsc/opportunities` | Conservé pour drill-down |
| `GET /api/shops/{shop}/longtail` | Conservé pour drill-down |
| `GET /api/shops/{shop}/niche/clusters` | Conservé pour drill-down |
| `GET /api/shops/{shop}/niche/intent-clusters` | Conservé pour drill-down |
| `GET /api/shops/{shop}/audit/cannibalization` | Conservé pour drill-down |
| `GET /api/shops/{shop}/audit/internal-links` | Conservé pour drill-down |
| `GET /api/shops/{shop}/geo/competitors` | Conservé pour drill-down |
| **`GET /api/shops/{shop}/opportunities`** | **À créer** — canonique, agrège tout |

Aucune dépréciation immédiate. Le nouvel endpoint **agrège** les sources existantes sans casser leurs consommateurs.

---

## 8. Mapping fichiers

### Existant à réutiliser (pas réécrire)

| Fichier | Rôle dans la tâche 132 |
|---|---|
| `scripts/audit/detect_gsc_opportunities.py:77` | Source `gsc_quick_win` / `gsc_low_ctr` / `gsc_long_term` |
| `app/niche/gaps.py:106` (`analyze_keyword_gaps`) | Source `keyword_gap` |
| `app/niche/intent.py:390` (`cluster_gsc_queries`) | Tag `matched_intents` |
| `app/niche/clustering.py:142` (`cluster_products`) | Matching produit ↔ requête |
| `scripts/audit/detect_cannibalization.py:49` | Source `cannibalization_conflict` |
| `scripts/report/detect_internal_links.py:23` | Source `link_opportunity` |
| `app/geo/competitors.py:62` (`build_competitor_monitor`) | Source `competitor_visible` |
| `app/geo/readiness.py:137` (`score_product_readiness`) | Source `audit_action_pressure` + `recommended_actions` (post-131) |
| `app/shop_config_store.py:1` | Lecture `niche_hypothesis` |

### À créer par la tâche d'implémentation (post-132)

| Fichier | Rôle |
|---|---|
| `app/opportunities/finder.py` | Orchestrateur : pull des 7 sources, agrégation par produit, scoring, sortie schéma §4 |
| `app/api/opportunities.py` | Route `GET /api/shops/{shop}/opportunities` |
| `shopify-app/app/routes/app.opportunities.tsx` | UI unifiée principale |
| `tests/test_opportunities/test_finder.py` | Tests unitaires : agrégation, scoring, niche ajustements |

---

## 9. Garde-fous

- **Pas de nouveau détecteur dans cette couche.** Si un signal manque, on l'ajoute dans le détecteur existant correspondant, pas dans le Finder.
- **Scope `active` par défaut** (`docs/product-scope.md`). Pas d'opportunités sur DRAFT/ARCHIVED dans la vue principale ; ils ont leur propre vue "Pre-launch check".
- **Pas d'appel LLM dans cette couche.** Tout est déterministe à partir des sources existantes. Le LLM intervient seulement pour générer le **contenu** d'une action (tâche 134), pas pour décider d'en proposer une.
- **Pas d'agrégation cachée.** Les 7 poids du scoring sont publiés et exposables côté UI.
- **`top` plafonné à 100.** Aucun cas d'usage produit ne demande plus. Au-delà, c'est un défaut de signal niche.
- **Cache par snapshot fresh.** Le Finder se recalcule à chaque nouveau snapshot Shopify ou nouvel import GSC. Pas de cron parallèle.
- **Compatibilité ascendante.** Les 7 endpoints existants continuent de fonctionner. `app.niche`, `app.longtail`, `app.cannibalization`, `app.internal-links`, `app.geo-competitors` restent accessibles.
- **Pas de fuite cross-shop.** Le matching concurrent (`competitor_visible`) reste sur la version `mock V1`. Pas de scraping live tant que tâche 115 n'a pas livré une version sûre.
- **`recommended_actions` ne déclenchent rien automatiquement.** Le Priority Engine (133) sélectionne les 3 à exécuter ; Safe Apply (135) gère la confirmation et l'écriture.

---

## 10. Critères d'acceptation de l'implémentation future

À cocher quand une tâche concrétise l'Opportunity Finder :

- [ ] Un seul endpoint `GET /api/shops/{shop}/opportunities` retourne le schéma §4.
- [ ] Une seule entrée par produit (pas par requête, pas par cluster).
- [ ] Scope `active` par défaut.
- [ ] Les 7 sources sont agrégées sans en omettre une.
- [ ] `opportunity_score` calculé selon la formule §5 avec poids publiés.
- [ ] `tier` (high/medium/low) calculé à partir des seuils §4.
- [ ] `confidence` cohérente avec le nombre de signaux + fraîcheur audit 131.
- [ ] Ajustements `niche_hypothesis` appliqués uniquement si `validated_by_merchant`.
- [ ] `niche_alerts` reportées sans baisser le score (le malus tombe sur Trust dans 131).
- [ ] UI `app.opportunities.tsx` remplace les 4-6 listes parallèles comme entrée principale.
- [ ] Les pages existantes (`niche`, `longtail`, `cannibalization`, `internal-links`, `geo-competitors`) sont accessibles en drill-down via liens.
- [ ] Tests : agrégation 1 produit avec 5 signaux = 1 opportunité.
- [ ] Tests : produit hors scope `active` n'apparaît pas.
- [ ] Tests : `forbidden_promise` ajoute une `niche_alerts` mais pas de malus de score.

---

## 11. Lien avec les autres modules Phase 11.7

- **Consomme** : score 131 (`recommended_actions`, `audit_action_pressure`), hypothèses 130 (`priority_products`, `conversational_intents`, `forbidden_promises`), scope 127 (`active` Online Store), crawl L3 128 (signaux SEO fraîs).
- **Alimente** : Priority Engine 133 (sélection des 3 actions prioritaires), Content Actions 134 (le LLM génère le contenu d'une action choisie), Impact Tracker 136 (snapshot + métrique attendue par opportunité).
- **N'interagit pas avec** : Niche raw clusters bruts (132 utilise les hypothèses validées, pas les clusters non corrigés), Crawl L3 raw findings (132 utilise les sous-scores SEO du 131).

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Question produit unique (« quelles pages méritent une action maintenant ? ») | ✅ Cadrée | Section 2 |
| 7 sources fusionnées sans réécriture | ✅ Mappées | Section 3 |
| Schéma JSON `opportunities` | ✅ Spécifié | Section 4 |
| Formule de scoring avec poids publics | ✅ Spécifiée | Section 5 |
| UI `app.opportunities.tsx` + drill-downs | ✅ Documentée | Section 6 |
| Stratégie endpoints (agrégation, pas dépréciation) | ✅ Documentée | Section 7 |
| Garde-fous (pas de nouveau détecteur, scope, pas de LLM) | ✅ Documentés | Section 9 |
| Création `app/opportunities/finder.py`, `app/api/opportunities.py` | ⏳ À porter | Section 8 |
| UI `app.opportunities.tsx` | ⏳ À créer | Section 6 |
| Branchement de la barre de menu principale | ⏳ À faire par 137 (Dashboard) | Section 6 |
| Tests unitaires d'agrégation | ⏳ À écrire | Section 10 |

> Les éléments ⏳ ne sont pas le périmètre de la tâche 132. Ils seront pris en charge par la tâche d'implémentation Opportunity Finder ultérieure et par 133 (Priority Engine consomme `opportunities`) + 137 (Dashboard).
