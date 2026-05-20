# Unified Priority Engine — Léonie SEO

> Référence canonique du moteur qui transforme la liste des opportunités (tâche 132) en **exactement 3 actions prioritaires** consommables par un marchand non technique. Fusionne ICE, Revenue-Aware Prioritization, Weekly Actions et Risk Guard sans réécrire ce qui marche.
>
> Statut : décisions produit/architecture figées au 2026-05-20 (tâche 133, Phase 11.7). Aucun code applicatif n'est modifié dans cette tâche.

---

## 1. Pourquoi ce cadrage

Quatre logiques de priorisation tournent aujourd'hui en parallèle :

| Logique | Fichier | Output |
|---|---|---|
| ICE matrix | `scripts/report/ice_matrix.py:112` | Liste triée `ice_score = (impact × confidence) / effort` |
| Revenue-Aware Prioritization | `app/geo/prioritization.py:102` | Score `0.35 × readiness_gap + 0.25 × traffic + 0.25 × revenue + 0.15 × gap × stock` |
| Weekly Actions | `app/geo/weekly.py:68` | Sélection top-N avec déduplication de type, step-by-step |
| Risk Guard | `app/geo/risk_guard.py:10` | Statut `protected / review_required / safe`, raisons |

Et trois pages Remix qui chevauchent : `app.geo-priorities`, `app.geo-risk-guard`, `app.next-best-actions`.

**Problème marchand** : un produit peut apparaître dans 3 pages avec 3 scores différents et un statut Risk Guard contradictoire. Les step-by-step Weekly sont noyés au milieu.

La tâche 133 fixe les règles pour produire **exactement 3 actions prioritaires** à la fois, chacune avec un dossier d'action complet (impact, confiance, effort, risque, pourquoi maintenant, métrique de succès), filtrées par Risk Guard, et préparées pour le workflow Review & Safe Apply (135).

C'est le **deuxième vrai consommateur LLM** (tier `advanced`) après 130, mais l'usage LLM est **limité à l'arbitrage final** sur 3 actions — pas au scoring brut, qui reste déterministe.

---

## 2. Position dans le workflow

```
Audit (131) → Opportunities (132) → [Priority Engine 133] → Review & Apply (135) → Mesure (136)
                                          ↑
                                          consomme aussi :
                                          - Risk Guard (existant)
                                          - niche_hypothesis (130)
                                          - product_scope (127)
```

Le Priority Engine **ne crée pas** de nouvelles opportunités — il les **sélectionne** et les **emballe** pour exécution.

---

## 3. Question produit unique

> **Quelles sont les 3 actions à exécuter maintenant qui ont le meilleur ratio impact × confiance / (effort × risque), sur des pages produits ACTIVE Online Store non protégées par Risk Guard ?**

Pourquoi exactement 3 :

- Étude usabilité produit : un marchand non technique sature au-delà de 3 décisions concurrentes par session.
- Cohérent avec l'objectif Phase 11.7 : *« afficher 3 actions prioritaires maximum »* (critère §138).
- Limite l'usage LLM `advanced` à un arbitrage final déterministe et plafonné.

Cas particuliers :

- **< 3 opportunités disponibles** : retourner ce qui est disponible + état explicite `"sparse_signal"`.
- **Aucune opportunité** : retourner un message d'attente (« en attente d'imports GSC / snapshot frais »).
- **Risk Guard exclut tout** : retourner les opportunités en mode "preview only" (pas d'action exécutable, juste de la lecture).

---

## 4. Pipeline en 4 étapes

```
Étape 1 — Pull opportunities
  GET /opportunities?scope=active&top=50 (cf. docs/opportunity-finder.md §4)

Étape 2 — Risk Guard filter
  Pour chaque opportunité, appeler risk_guard.classify(product)
  → exclure protected (sauf si confirmation_override marchand)
  → marquer review_required (visible mais flag)
  → laisser safe

Étape 3 — Pre-score deterministic
  Pour chaque opportunité survivante :
    priority_score = (
      0.40 × opportunity_score / 100              # signal externe (132)
    + 0.25 × business_value                       # revenue_estimate normalisé
    + 0.15 × confidence                           # confidence niveau 132 + freshness audit 131
    + 0.10 × niche_priority_boost                 # priority_products / intents
    - 0.05 × effort_normalized                    # effort 1-3 normalisé
    - 0.05 × risk_normalized                      # risk score normalisé (Risk Guard)
    )
  Trier desc → garder top-10 candidats

Étape 4 — LLM arbitrage final (tier advanced, plafonné)
  Input : top-10 candidats + niche_hypothesis + summary boutique
  Output : 3 actions sélectionnées avec dossier d'action (cf. §5)
  Garde-fou : si LLM échoue / budget dépassé / plan Free → fallback déterministe top-3 du pre-score
```

### Notes sur le LLM en étape 4

- **Tier `advanced`** (cf. `docs/llm-strategy.md` §2-4) — justifié par : arbitrage multi-signaux, valeur business haute, sortie consommée par décision marchand.
- **Plafond** : 1 appel par cycle de priorisation (= 1 par semaine en mode planifié, 1 par run manuel).
- **Cache** : clé `(shop, "priority_arbitrage", prompt_version, top10_hash)` avec TTL 24 h.
- **Plan Free** : pas d'arbitrage LLM, fallback déterministe top-3 du pre-score uniquement.
- **Budget dépassé** : fallback déterministe (cf. `docs/llm-strategy.md` §6).
- **`forbidden_promises`** : exclut toute action qui pousserait à générer un contenu enfreignant la liste.

---

## 5. Schéma du dossier d'action

Chaque action sélectionnée porte un dossier complet et auto-suffisant pour le marchand :

```json
{
  "rank": 1,
  "action_id": "string unique",
  "product_id": "string",
  "product_handle": "string",
  "product_title": "string",
  "action_type": "enrich_product_facts|improve_schema|add_answer_blocks|add_trust_proofs|improve_seo_copy|review_commerce_data|fix_cannibalization|add_internal_link",
  "action_label": "string lisible non-technique",
  "priority_score": 0-100,

  "why_now": "string court — pourquoi cette action vaut le coup MAINTENANT",
  "evidence": [
    {"source": "gsc|audit|niche|crawl_l3|competitors|niche_hypothesis",
     "metric": "string",
     "value": "number|string"}
  ],

  "estimates": {
    "impact": "low|medium|high",
    "confidence": "low|medium|high",
    "effort": "low|medium|high",
    "risk": "low|medium|high",
    "click_gain_estimate": number|null,
    "revenue_estimate_eur": number|null,
    "estimate_basis": "gsc_only|gsc+ga4|gsc+fallback"
  },

  "success_metric": {
    "name": "string",
    "current_value": "number",
    "target_value": "number",
    "measurement_window_days": 30|60|90,
    "source": "gsc|ga4|audit_readiness|jsonld_validity"
  },

  "preview": {
    "depends_on": ["niche_hypothesis", "product_facts_layer", "..."],
    "expected_output_type": "text|jsonld|faq|meta|internal_link",
    "human_review_required": true
  },

  "risk_guard": {
    "status": "safe|review_required",
    "reasons": ["string"],
    "override_required": false
  },

  "niche_alerts": [
    {"type": "forbidden_promise|do_not_say", "message": "string"}
  ]
}
```

### Règles sur le schéma

- **`why_now`** : phrase courte, lisible, basée sur les signaux. Ex : *« Cette page reçoit 800 impressions Google mais aucun fait produit n'est confirmé. »* Pas de jargon SEO.
- **`evidence`** : preuve sourcée, jamais inventée.
- **`estimate_basis`** : transparent — `gsc_only`, `gsc+ga4`, `gsc+fallback` (conversion_rate=0.02, AOV=50€). Le marchand sait sur quoi le revenue estimate repose.
- **`success_metric`** : **obligatoire**. Sans métrique de succès, on ne mesure pas → on ne propose pas l'action. C'est la clé du couplage avec Impact Tracker (136).
- **`measurement_window_days`** : aligné sur les jalons 119 (J+7/J+30/J+60/J+90).
- **`human_review_required: true`** par défaut. Aucune action n'est appliquée sans passer par 135.
- **`override_required`** quand `risk_guard.status = review_required` et que le marchand veut quand même exécuter.

---

## 6. Définition des estimations

Pour rester transparent et éviter les fausses précisions :

### Impact (`low | medium | high`)

| Signal | Impact |
|---|---|
| Quick-win GSC (positions 11-20, impressions > 500) | high |
| Quick-win GSC (positions 11-20, impressions 100-500) | medium |
| Long-term GSC (positions 21-50) | low ou medium selon impressions |
| Cannibalisation entre 2 produits qui convertissent | high |
| `low_facts` sur produit avec impressions > 300 | medium |
| `weak_schema` sur produit isolé | low |

### Confidence (`low | medium | high`)

Reprend la `confidence` du 132 + freshness audit 131 + freshness snapshot Shopify :

| Critères | Confidence |
|---|---|
| ≥ 3 signaux convergents + audit < 7 j + snapshot < 7 j | high |
| 1-2 signaux + données fraîches | medium |
| Données > 14 jours OU 1 seul signal | low |

### Effort (`low | medium | high`)

Mapping fixe par `action_type` (déjà défini dans `app/geo/prioritization.py:85`) :

| Action | Effort |
|---|---|
| `improve_seo_copy` | low |
| `improve_schema`, `add_answer_blocks`, `add_trust_proofs`, `review_commerce_data` | medium |
| `enrich_product_facts`, `fix_cannibalization` | high |

### Risk (`low | medium | high`)

Issu de `app/geo/risk_guard.py:10`. Repris tel quel sans recalcul.

| Statut Risk Guard | Risk |
|---|---|
| `safe` | low |
| `review_required` | medium |
| `protected` (exclu sauf override) | high |

---

## 7. Action types — alignement existant

Le module `app/geo/prioritization.py:85` et `app/geo/weekly.py:10` définissent déjà 6 action types avec libellés FR et step-by-step. Le Priority Engine 133 les **réutilise tels quels** + ajoute deux types alignés avec Opportunity Finder :

| Action type | Libellé | Source step-by-step | Statut |
|---|---|---|---|
| `enrich_product_facts` | Enrichir faits produit | `app/geo/weekly.py:21` | ✅ existant |
| `improve_schema` | Améliorer données structurées | `weekly.py:25` | ✅ existant |
| `add_answer_blocks` | Ajouter FAQ et réponses IA | `weekly.py:29` | ✅ existant |
| `add_trust_proofs` | Ajouter preuves de confiance | `weekly.py:35` | ✅ existant |
| `improve_seo_copy` | Améliorer title/meta/description | `weekly.py:41` | ✅ existant |
| `review_commerce_data` | Compléter prix/stock/statut | `weekly.py:48` | ✅ existant |
| `fix_cannibalization` | Résoudre une cannibalisation | À ajouter | ⏳ nouveau (depuis 132 signal) |
| `add_internal_link` | Ajouter un lien interne pertinent | À ajouter | ⏳ nouveau (depuis 132 signal) |

Pas de prolifération de types — le Finder peut générer 8 signaux, mais ils mappent vers 8 action types stables. Tout nouveau type passe par une décision produit explicite, pas par une simple PR.

---

## 8. Comportement UI cible

### Vue principale `app.priorities.tsx` (à créer ou réutiliser `app.next-best-actions.tsx`)

- **Exactement 3 cartes** côte à côte (Polaris `InlineStack` ou `Grid`) — pas une liste paginée.
- Chaque carte : `rank` (1/2/3), `product_title`, `action_label`, `why_now`, badges `impact / confidence / effort / risk`, `success_metric` en bas.
- Bouton principal "Préparer cette action" → ouvre le workflow Review & Safe Apply (135).
- Lien "Voir les autres opportunités" → ouvre `app.opportunities` (132).
- Bandeau "Recalculé le {date} — prochain rafraîchissement {date+7j}" pour la fréquence hebdomadaire.

### Vue avancée (mode "Tous les candidats")

- Liste top-10 candidats du pre-score, accessible par bouton "Mode avancé".
- Affichage tabulaire avec colonnes : produit, action, priority_score, estimations, risk_guard status.
- Ne montre **jamais** les 50 opportunités brutes du Finder — pour ça, on bascule sur `app.opportunities`.

### Pages existantes — repositionnement

| Page actuelle | Statut post-133 |
|---|---|
| `app.next-best-actions` | Fusionnée dans `app.priorities` (ou renommée). |
| `app.geo-priorities` | Dépréciée. Top-N brut sans Risk Guard ni LLM = redondance. |
| `app.geo-risk-guard` | Conservée comme drill-down. Accessible via lien depuis carte avec `risk_guard.status != safe`. |
| `app.geo-weekly-actions` (si existe) | Dépréciée — la sortie weekly devient la sortie standard du Priority Engine. |

---

## 9. Endpoints — fusion / dépréciation

| Endpoint actuel | Statut post-133 |
|---|---|
| `GET /api/shops/{shop}/geo/priorities` (top-N brut) | Déprécié |
| `GET /api/shops/{shop}/geo/weekly-actions` | Conservé en interne, alimente le Priority Engine |
| `GET /api/shops/{shop}/geo/risk-guard` | Conservé pour drill-down |
| **`GET /api/shops/{shop}/priorities`** | **À créer** — canonique, 3 actions max |

Schéma de réponse simplifié :

```
GET /api/shops/{shop}/priorities?scope=active
→ {
  "shop": "string",
  "generated_at": "ISO date",
  "scope": "active",
  "actions": [...],          # exactement 3 (ou moins si sparse_signal)
  "candidates_evaluated": int,
  "llm_used": true|false,
  "fallback_reason": "string|null",
  "next_refresh_at": "ISO date"
}
```

---

## 10. Cohérence avec `docs/llm-strategy.md`

| Règle LLM | Application 133 |
|---|---|
| Tier `advanced` (cf. §2 strategy) | ✅ Étape 4 d'arbitrage uniquement |
| 1 appel par cycle, cache 24 h | ✅ Plafonné explicitement §4 |
| `check_budget` avant `router.complete` | ✅ Obligatoire, fallback déterministe sinon |
| Mode `low-cost only` global → dégradation | ✅ Fallback déterministe top-3 |
| Plan Free → pas d'`advanced` | ✅ Free reçoit le pre-score top-3 sans LLM |
| Outputs JSON structurés | ✅ Schéma §5 contractuel |
| Prompt versionné dans `config/prompts/` | ✅ `priority_arbitrage.yaml` (à créer post-133) |
| Aucun appel HTTP direct hors `LLMRouter` | ✅ Toujours via router |

---

## 11. Mapping fichiers

### Existant à réutiliser

| Fichier | Rôle |
|---|---|
| `scripts/report/ice_matrix.py:112` | Référence formule ICE (signal historique, peut alimenter le pre-score si on veut un ICE-style explicable) |
| `app/geo/prioritization.py:102` (`prioritize_catalog`) | Réutilisé pour pre-score étape 3 |
| `app/geo/weekly.py:68` (`build_weekly_actions`) | Réutilisé pour step-by-step par action_type |
| `app/geo/risk_guard.py:10` (`classify`) | Réutilisé en étape 2 |
| `app/geo/readiness.py:75` (`score_product_readiness`) | Alimente `audit_action_pressure` côté 132 |
| `app/shop_config_store.py:1` | Lecture `niche_hypothesis` |
| `app/llm/router.py:70` | Étape 4 LLM arbitrage |
| `app/observability/metrics.py:113` (`check_budget`) | Budget guard avant LLM |

### À créer par la tâche d'implémentation (post-133)

| Fichier | Rôle |
|---|---|
| `app/priorities/engine.py` | Orchestrateur 4 étapes |
| `config/prompts/priority_arbitrage.yaml` | Prompt LLM tier `advanced` + schéma JSON §5 |
| `app/api/priorities.py` | Route `GET /api/shops/{shop}/priorities` |
| `shopify-app/app/routes/app.priorities.tsx` | UI 3 cartes |
| `tests/test_priorities/test_engine.py` | Tests : pre-score, fallback déterministe, Risk Guard exclusion, LLM mock |

---

## 12. Garde-fous

- **Exactement 3 actions** — pas plus, pas moins (sauf `sparse_signal`).
- **`success_metric` obligatoire** sur chaque action — sans elle, on ne propose pas (couplage 136).
- **`human_review_required: true` par défaut** — aucune écriture sans 135.
- **Risk Guard prioritaire** — un produit `protected` n'est jamais proposé sans override explicite marchand.
- **Plan Free sans LLM** — pas d'`advanced` sur Free. Fallback déterministe transparent (`llm_used: false`).
- **Fallback déterministe systématique** — si LLM échoue / budget dépassé / mode low-cost only : retourner top-3 du pre-score.
- **Pas de double comptage avec 131/132.** Les poids du pre-score sont publiés, basés sur des signaux déjà calculés.
- **Pas de boucle interne LLM.** 1 seul appel par cycle.
- **Cycle hebdomadaire par défaut**, déclenchable à la demande. Cache 24h sur l'arbitrage LLM, jamais sur le pre-score (qui dépend du snapshot fresh).
- **Aucune dépendance directe à GA4.** Le `revenue_estimate` est calculé avec fallback transparent (`estimate_basis: gsc+fallback` quand GA4 manque).
- **`forbidden_promises` exclut les actions à risque.** Si une action proposée déclencherait une promesse interdite, elle est filtrée à l'étape 4.

---

## 13. Critères d'acceptation de l'implémentation future

À cocher quand une tâche concrétise le Priority Engine :

- [ ] `GET /api/shops/{shop}/priorities` retourne **3 actions max** (ou `sparse_signal` si < 3).
- [ ] Chaque action porte le dossier complet (§5).
- [ ] `success_metric` est présente et alignée sur la fenêtre J+7/J+30/J+60/J+90.
- [ ] Risk Guard exclut les `protected` par défaut, marque les `review_required`.
- [ ] Pre-score déterministe est calculé avec les 6 poids publiés (§4).
- [ ] LLM `advanced` n'est appelé qu'à l'étape 4 sur 10 candidats max.
- [ ] `check_budget` est appelé avant `router.complete`.
- [ ] Plan Free et mode `low-cost only` → fallback déterministe avec `llm_used: false`.
- [ ] Cache 24 h sur l'arbitrage LLM.
- [ ] `forbidden_promises` filtre à l'étape 4.
- [ ] UI affiche exactement 3 cartes côte à côte, pas une liste.
- [ ] Bouton "Préparer cette action" ouvre le workflow 135.
- [ ] Tests : pre-score, Risk Guard exclusion, fallback LLM, niche_alerts propagés.
- [ ] La checklist `docs/llm-strategy.md` §12 est cochée.

---

## 14. Limites V1 explicites

- **Pas de scoring par segment client.** Une action vaut pareil pour tous les segments en V1. Une priorisation par persona viendra plus tard si pertinent.
- **Pas de prise en compte calendrier marketing.** Pas de boost saisonnier explicite en V1 (ex : Noël, Black Friday). À traiter dans `priority_arbitrage.yaml` v0.2.
- **Pas de batch d'actions liées.** Une action est indépendante en V1. Si deux actions partagent une dépendance (ex : même refonte de fiche produit), elles restent séparées dans la sortie. À optimiser plus tard.
- **`measurement_window_days` est statique par action_type**, pas calculé dynamiquement selon le volume.

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Question produit unique (3 actions max) | ✅ Cadrée | Section 3 |
| Pipeline 4 étapes (pull → risk → pre-score → LLM arbitrage) | ✅ Spécifié | Section 4 |
| Schéma JSON du dossier d'action | ✅ Spécifié | Section 5 |
| Définition des estimations (impact/confidence/effort/risk) | ✅ Documentée | Section 6 |
| Action types alignés avec existant + 2 nouveaux | ✅ Mappés | Section 7 |
| UI 3 cartes + drill-down | ✅ Documentée | Section 8 |
| Endpoints (fusion / dépréciation) | ✅ Documentés | Section 9 |
| Cohérence stratégie LLM | ✅ Vérifiée | Section 10 |
| Garde-fous (Risk Guard prioritaire, fallback déterministe, plan Free, forbidden_promises) | ✅ Documentés | Section 12 |
| `app/priorities/engine.py` (orchestrateur 4 étapes) | ⏳ À porter | Section 11 |
| `config/prompts/priority_arbitrage.yaml` | ⏳ À créer | Section 11 |
| Route `GET /api/shops/{shop}/priorities` | ⏳ À créer | Section 11 |
| UI `app.priorities.tsx` 3 cartes | ⏳ À créer | Section 11 |
| Dépréciation `app.geo-priorities` / `app.next-best-actions` | ⏳ Migration UI | Section 8 |

> Les éléments ⏳ ne sont pas le périmètre de la tâche 133. Ils seront pris en charge par la tâche d'implémentation Priority Engine ultérieure et par 137 (Dashboard simplification).
