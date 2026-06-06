# Public Launch Readiness Criteria — Giulio Geo

> Checklist canonique d'entrée en **Phase 12 (Soumission publique Shopify App Store)**. Distille les décisions produit/architecture des Phases 11.7–11.9 en critères go/no-go opérationnels. La tâche 150 (décision go/no-go) coche cette liste avant que la tâche 151 (soumission App Store) ne démarre.
>
> Statut : mis à jour au 2026-05-21 (tâche 163, Phase 11.9). **La Phase 11.9 complète (tâches 152-163) est un prérequis non négociable avant de cocher §3.**

---

## 0. Prérequis Phase 11.9 (gate obligatoire)

Avant de démarrer la vérification §3, les conditions suivantes doivent être satisfaites :

| Prérequis | Statut | Preuve attendue |
|---|---|---|
| Tâches 152-163 toutes ✅ | ⏳ | ROADMAP.md — Phase 11.9 10/12 → 12/12 |
| Test utilisateur : 3 marchands pilotes ont compris l'app en < 5 min | ⏳ | `docs/pilot-merchant-test-script.md` — grilles de friction remplies |
| Vocabulaire marchand appliqué : 0 terme interdit au premier niveau | ⏳ | `docs/merchant-language-glossary.md` — vérification manuelle i18n.ts |
| Un seul CTA primaire par écran principal | ⏳ | `docs/cta-matrix.md` — revue UI sur chaque écran |
| Dashboard compris sans explication externe | ⏳ | Session test marchand — 0 question "c'est quoi X ?" |

Un ❌ ou ⏳ dans ce tableau = NO-GO Phase 12, indépendamment des critères §3.

---

## 1. Pourquoi ce cadrage

Sans critère explicite, le go/no-go App Store devient une décision opaque, souvent prise sous pression marketing. La tâche 138 fixe une **checklist publique** que tout reviewer interne (et tout futur agent Claude) peut cocher mécaniquement.

Les critères ne sont **pas négociables** : un seul critère ❌ = no-go. Le go/no-go n'est pas une moyenne pondérée.

Ces critères condensent les engagements stratégiques de la Phase 11.7 :

- *« un marchand non expert comprend l'app en moins de 5 minutes »* — `docs/dashboard-simplification.md`
- *« l'app affiche 3 actions prioritaires maximum »* — `docs/priority-engine.md`
- *« chaque action est applicable avec review humaine »* — `docs/safe-apply.md`
- *« coût LLM maîtrisé »* — `docs/llm-strategy.md`
- *« métriques Google et IA séparées »* — `docs/impact-tracker.md`
- *« pas de promesse non prouvée de ranking ChatGPT »* — `docs/impact-tracker.md` §12

---

## 2. Architecture de la checklist

13 catégories, chacune avec :

- **Critère** (une phrase courte, vérifiable).
- **Doc de référence** (lien vers la décision produit).
- **Test acceptance** (preuve à fournir : test automatisé, capture, métrique mesurée, ou revue manuelle documentée).
- **Statut** (✅ / ❌ / ⏳ en cours).

Tout critère ⏳ ou ❌ bloque l'entrée en Phase 12.

---

## 3. Critères de readiness

### 3.1 — Compréhension marchand non-expert

| Critère | Référence | Preuve attendue |
|---|---|---|
| Un marchand non expert comprend l'app en moins de 5 minutes (test utilisateur sur 3 marchands pilotes) | `docs/dashboard-simplification.md` §2 | Capture du test utilisateur, temps mesuré, retranscription des 3 sessions |
| Le dashboard d'accueil affiche 6 zones dans l'ordre spécifié | `docs/dashboard-simplification.md` §3 | Capture d'écran annotée |
| Zéro mot du vocabulaire interdit en Zone 1-3 | `docs/dashboard-simplification.md` §6 | Script de lint sur les chaînes i18n FR/EN |
| Internationalisation complète FR/EN (toutes chaînes Zone 1-6) | `docs/dashboard-simplification.md` §7 | Diff i18n.ts vs textes affichés |
| Coût LLM visible en Header (pas seulement dans Settings) | `docs/dashboard-simplification.md` §4, `docs/llm-strategy.md` §6 | Capture dashboard |

### 3.2 — Limite à 3 actions prioritaires

| Critère | Référence | Preuve attendue |
|---|---|---|
| L'app affiche **exactement 3 actions prioritaires** par cycle (ou `sparse_signal` si < 3) | `docs/priority-engine.md` §3 | Test e2e sur un shop avec 50 opportunités → 3 cartes |
| Chaque action porte un dossier complet (`why_now`, `evidence`, `estimates`, `success_metric`, `risk_guard`, `niche_alerts`) | `docs/priority-engine.md` §5 | Schéma JSON validé par tests Pydantic |
| `success_metric` est **obligatoire** sur chaque action — pas d'action sans métrique de succès | `docs/priority-engine.md` §5 | Test : action sans métrique = 422 |
| Risk Guard exclut systématiquement les pages `protected` sauf override marchand explicite | `docs/priority-engine.md` §4 + `app/geo/risk_guard.py:10` | Test : produit `protected` jamais dans le top 3 par défaut |
| Plan Free et mode `low-cost only` : fallback déterministe sans LLM | `docs/priority-engine.md` §4 | Test : `LEONIE_LLM_LOW_COST_ONLY=true` → `llm_used: false` |

### 3.3 — IA assistante, jamais autonome

| Critère | Référence | Preuve attendue |
|---|---|---|
| Chaque action est **générée ou assistée par LLM** (tier `low-cost` / `medium` / `advanced` selon mapping) | `docs/llm-strategy.md` §3, `docs/ai-content-actions.md` §4 | Mapping documenté dans le code (test : tier déclaré par content_type) |
| Chaque action est **applicable avec review humaine** | `docs/safe-apply.md` §4 + §6 | Test : aucun endpoint n'écrit sans `confirm_live_write=true` |
| `human_review_required: true` est **strict** — pas d'auto-approve dans le code | `docs/ai-content-actions.md` §7 + §13 | Grep négatif sur `auto-approve` dans le code post-migration |
| `confirmed_facts_only` : aucune affirmation factuelle sans `facts_used` sourcé | `docs/ai-content-actions.md` §8.1 | Test : génération avec faits manquants → `needs_review` |
| `forbidden_promises` et `do_not_say` propagés vers tous les content_types | `docs/ai-content-actions.md` §8.2 + §8.3 | Test : promesse interdite dans output → `needs_review` |

### 3.4 — Mesure d'impact obligatoire

| Critère | Référence | Preuve attendue |
|---|---|---|
| **Chaque action appliquée crée un événement mesurable** dans `geo_impact_events` | `docs/safe-apply.md` §7 + `docs/impact-tracker.md` §5 | Test : `apply` réussi → 1 ligne `geo_impact_events` créée |
| Aucun `apply` Shopify ne termine sans event créé (couplage strict) | `docs/safe-apply.md` §7 | Test : exception levée si `create_geo_event()` échoue |
| Validation Timeline J+7 / J+30 / J+60 / J+90 planifiée automatiquement | `docs/impact-tracker.md` §6 | Test : cron déclenche les mesures aux jalons |
| Confidence Score retourné sur tout verdict | `docs/impact-tracker.md` §7 | Test : aucune réponse `/impact-report` sans `confidence` |
| Stabilité commerce détectée : changement prix/stock pendant fenêtre baisse `stability_score` | `docs/impact-tracker.md` §7 | Test unitaire `confidence.py` |
| 4 verdicts standardisés (`Win` / `Neutral` / `Risk` / `Inconclusive`) | `docs/impact-tracker.md` §8 | Schéma validé |
| Next Best Action propose `répliquer` / `ajuster` / `attendre` / `rollback` selon verdict | `docs/impact-tracker.md` §9 | Test : verdict `négatif_possible` → action `rollback` |

### 3.5 — Scope produit V1 verrouillé

| Critère | Référence | Preuve attendue |
|---|---|---|
| Les **produits actifs Online Store sont le scope principal** | `docs/product-scope.md` §3 | Test : `score_catalog_readiness(scope=active)` exclut `DRAFT`, `ARCHIVED`, `UNLISTED` |
| 4 vues séparées exposées : Active / Pre-launch Drafts / Hidden-Unlisted / Cleanup-Archived | `docs/product-scope.md` §4 | Capture UI : sélecteur de vue présent |
| Helper canonique `filter_products_by_scope` utilisé partout (pas de filtrage ad hoc) | `docs/product-scope.md` §6 | Grep : aucun re-filtrage par statut dans les modules consommateurs |
| Bouton "Apply" désactivé sur produits hors scope `active` | `docs/product-scope.md` §5 + `docs/safe-apply.md` | Capture UI : bouton grisé sur DRAFT |

### 3.6 — Pas de dépendance obligatoire à Screaming Frog

| Critère | Référence | Preuve attendue |
|---|---|---|
| Un marchand peut lancer un audit complet **sans installer Screaming Frog** | `docs/crawl-strategy.md` §2 | Test e2e : nouveau shop → audit complet sans upload CSV |
| Crawl Level 3 actif : Shopify snapshot étendu + sitemap auto + mini-crawl HTTP plafonné | `docs/crawl-strategy.md` §2-3 | Logs job `crawl_l3` |
| `robots.txt` lu et respecté avant tout mini-crawl | `docs/crawl-strategy.md` §6 | Test : URL `Disallow:` jamais requêtée |
| Throttling 1 req/s, user-agent identifiable, plafonds Free/Pro/Agency appliqués | `docs/crawl-strategy.md` §3 + §8 | Test : > 50 URLs en Free → arrêt |
| Screaming Frog CSV accessible en "Mode avancé" sans message indiquant qu'il est requis | `docs/crawl-strategy.md` §7 | Audit textuel UI |

### 3.7 — Aucune promesse non prouvée

| Critère | Référence | Preuve attendue |
|---|---|---|
| **Aucune promesse d'apparition** dans ChatGPT / Perplexity / Gemini / Google AI Overviews | `docs/impact-tracker.md` §12 + §15 | Audit textuel : copy app, marketing, ToS |
| AI Visibility cadrée comme **signal mesurable mais imparfait**, branche V2 opt-in | `docs/impact-tracker.md` §12 | Encart Zone 6 du dashboard désactivé V1 avec wording exact |
| Aucun message UI ne suggère que l'app pousse une marque dans les moteurs IA | `docs/impact-tracker.md` §4 + §15 | Audit textuel UI |
| L'encart Zone 6 contient le texte exact "*La présence dans ces moteurs n'est jamais garantie ; il s'agit d'un signal mesuré, pas d'une promesse.*" | `docs/dashboard-simplification.md` §4 (Zone 6) | Capture UI |

### 3.8 — Métriques Google et IA séparées

| Critère | Référence | Preuve attendue |
|---|---|---|
| **Search Performance (GSC/GA4/Shopify) et AI Visibility sont deux axes distincts** | `docs/impact-tracker.md` §4 | Capture UI : deux dashboards séparés |
| Aucune agrégation d'un score Search avec un score AI | `docs/impact-tracker.md` §4 + §15 | Audit code : pas de calcul combiné |
| AI Visibility hors verdict d'optimisation V1 | `docs/impact-tracker.md` §4 | Test : verdict ne dépend que de Search Performance |

### 3.9 — Coût LLM maîtrisé

| Critère | Référence | Preuve attendue |
|---|---|---|
| **3 tiers LLM** (`low-cost` / `medium` / `advanced`) avec routing par tâche | `docs/llm-strategy.md` §2 + §3 | Mapping documenté et testé |
| Cache LLM `(shop, task_name, prompt_version, content_hash)` avec TTL par tâche | `docs/llm-strategy.md` §4 | Test : 2 appels identiques → 1 seul appel provider |
| `check_budget()` appelé **avant** chaque `router.complete()` dans tout consommateur | `docs/llm-strategy.md` §6 | Grep : pas de `router.complete` sans `check_budget` |
| Quotas par plan Free / Pro / Agency appliqués | `docs/llm-strategy.md` §5 | Test : dépassement Free → blocage doux |
| Mode `LEONIE_LLM_LOW_COST_ONLY=true` opérationnel | `docs/llm-strategy.md` §7 | Test : env var → tier forcé low-cost |
| Outputs JSON structurés sur tout `content_type` qui consomme du code | `docs/llm-strategy.md` §11 + `docs/ai-content-actions.md` §6 | Schéma Pydantic validé par les tests |
| Prompts externalisés YAML versionnés (`config/prompts/*.yaml`) | `docs/llm-strategy.md` §10 | Grep : aucun prompt en dur dans le code |
| Tous les prompts ont migré v1 → v2.0 (élimination du hardcode "premium animaux") | `docs/ai-content-actions.md` §9 | Diff prompts avant/après |
| Coût LLM logué par appel (`record_llm_call`) | `docs/llm-strategy.md` §8 | Table `llm_metrics` non vide |
| Aucun appel HTTP direct à un provider hors `LLMRouter` | `docs/llm-strategy.md` §8 | Grep : aucun import direct `openai`/`anthropic`/`groq` hors `app/llm/` |

### 3.10 — Rollback documenté et opérationnel

| Critère | Référence | Preuve attendue |
|---|---|---|
| **Rollback per-item** opérationnel sur les 10 content_types | `docs/safe-apply.md` §8 | Test : `revert` sur chaque content_type → état initial restauré |
| Table `seo_changes` capture `old_value` / `new_value` pour chaque mutation | `docs/safe-apply.md` §6 + `app/db.py:39` | Schéma DB |
| Rollback TTL 90 jours avec avertissement au-delà | `docs/safe-apply.md` §8 | Test : revert > 90 j → confirmation forte demandée |
| Rollback batch possible avec confirmation `confirm_live_write=true` | `docs/safe-apply.md` §8 | Test : batch revert sans confirm → 409 |

### 3.11 — Dry-run par défaut

| Critère | Référence | Preuve attendue |
|---|---|---|
| **Dry-run par défaut** sur toute écriture Shopify | `docs/safe-apply.md` §5 + §6 + `app/apply/bulk_orchestrator.py:84` | `dry_run=True` par défaut dans `BulkApplyRequest` |
| Dry-run obligatoire **avant** live (étape 4 du workflow Safe Apply) | `docs/safe-apply.md` §2 + §5 | Test : live sans dry-run préalable → 409 |
| `LEONIE_PILOT_SAFE_MODE=true` bloque toute écriture live | `app/safety.py:14` (référence existante) | Test : pilot-safe + live → 403 |
| `confirm_live_write=true` vient d'une action UI explicite, jamais d'un défaut | `docs/safe-apply.md` §6 | Audit code : pas de valeur par défaut `confirm=True` |
| `before_drift_detected` force re-génération si état Shopify a changé | `docs/safe-apply.md` §5 | Test : modification admin pendant fenêtre → blocage live |

### 3.12 — Dashboard impact lisible

| Critère | Référence | Preuve attendue |
|---|---|---|
| Le **dashboard impact est compréhensible** par un non-technique | `docs/impact-tracker.md` §11 + `docs/dashboard-simplification.md` §4 | Test utilisateur sur 3 marchands pilotes |
| Aucun chiffre sans phrase de contexte | `docs/dashboard-simplification.md` §6 | Audit UI |
| Mini-courbe Search Performance + prochain jalon + compteur d'optimisations actives | `docs/dashboard-simplification.md` §4 (Zone 3) | Capture UI |
| Anti-dark-pattern strict sur Retention Milestones | `docs/impact-tracker.md` §10 | Audit textuel : pas d'urgency artificielle |

### 3.13 — Niche Understanding gating

| Critère | Référence | Preuve attendue |
|---|---|---|
| `niche_hypothesis.status == "validated_by_merchant"` requis pour les content_types à charge factuelle | `docs/niche-understanding.md` §6 + `docs/ai-content-actions.md` §5 | Test : `product_description` refusée si non validée |
| Plan Free dégradé en tier `medium` (pas d'`advanced` pour la niche) | `docs/niche-understanding.md` §4 | Test : Free → `medium`, Pro/Agency → `advanced` |
| `forbidden_promises` propagé vers tous les modules aval (131-134) | `docs/niche-understanding.md` §7 | Test : promesse interdite ajoutée dans niche → bloque génération sur l'angle correspondant |
| Workflow de correction marchand opérationnel (UI éditable section par section + persistance `shop_config.niche_hypothesis`) | `docs/niche-understanding.md` §6 | Capture UI + schéma DB |

---

## 4. Critères secondaires (recommandés mais non bloquants)

Ces critères améliorent la qualité produit mais ne bloquent pas l'entrée en Phase 12. Ils peuvent être livrés en post-launch.

| Critère | Référence | Impact si manquant |
|---|---|---|
| Tests Playwright e2e sur les 6 zones du dashboard | `docs/dashboard-simplification.md` §11 | Risque de régression UI, mais pas bloquant fonctionnellement |
| Endpoint canonique `GET /dashboard` agrégé (au lieu de 6 appels parallèles) | `docs/dashboard-simplification.md` §9 | Performance dégradée, FCP > 1.5 s acceptable temporairement |
| Migration complète des 5 pages UI génération vers `app.content-actions.tsx` unique | `docs/ai-content-actions.md` §12 | Marchand peut utiliser les pages séparées le temps de la migration |
| Tests unitaires d'agrégation Opportunity Finder | `docs/opportunity-finder.md` §10 | Régression silencieuse possible |
| Encart "AI Visibility" avec opt-in newsletter pour V2 | `docs/dashboard-simplification.md` §4 (Zone 6) | Pas de capture de leads V2 — acceptable V1 |

---

## 5. Critères opérationnels Shopify App Store (rappel — couverts par tâche 75)

Ces critères sont déjà validés depuis la tâche 75 (Phase 8). La tâche 138 vérifie qu'aucune régression Phase 11.7 ne les a cassés.

| Critère | Référence | Vérification |
|---|---|---|
| OAuth Shopify embedded fonctionnel | tâche 45 | smoke test installation pilote |
| Billing API GraphQL + plans (`appSubscriptionCreate` / `Cancel`) | tâche 52 + `app/api/plans.py:10` | Test paiement sandbox |
| Mandatory GDPR webhooks (`customers/data_request`, `customers/redact`, `shop/redact`) | tâche 51 | Webhook endpoints répondent 200 |
| App Bridge v4 + Polaris | tâche 56 | Pas de regression UI |
| API Shopify 2025-01 minimum | AGENTS.md | `shopify.app.toml` |
| Submission checklist | `docs/app-store-submission-checklist.md` | Existante, cf. tâche 75 |

---

## 6. Processus go/no-go (tâche 139)

La tâche 139 (décision go/no-go App Store) suit ce processus :

1. **Lecture exhaustive** des sections 3.1 → 3.13 ci-dessus.
2. **Cocher chaque ligne** avec ✅ / ❌ / ⏳.
3. **Aucune ligne ❌ ou ⏳** dans les critères §3 = **GO**.
4. Sinon = **NO-GO** avec liste des manquants et plan de remédiation.
5. **Documenter la décision** dans `DECISIONS.md` avec date, agent, et état détaillé.
6. Critères §4 (secondaires) listés en *known limitations* du go.

Aucun critère §3 ne peut être contourné par "ça marchera quand même". L'objectif est d'éviter une soumission App Store avec une dette qui se révélerait après publication.

---

## 7. Garde-fous transversaux

- **La checklist est immuable une fois en revue Phase 12.** Toute modification de critère après le démarrage de 139 demande une PR explicite et une nouvelle revue.
- **Aucun critère n'est validé par auto-évaluation Claude.** Chaque ✅ exige une preuve listée (test, capture, métrique, audit textuel).
- **Test utilisateur sur 3 marchands pilotes** est exigé pour §3.1 et §3.12 — pas négociable, pas remplaçable par "test interne".
- **Audit textuel** des copies UI/marketing pour §3.7 — un seul "garantissons l'apparition dans ChatGPT" suffit à bloquer.
- **Multi-tenant strict** vérifié : aucune fuite cross-shop sur events, embeddings, niche_hypothesis, cache LLM, snapshots.
- **Rollback testé end-to-end** sur chaque content_type, pas juste sur meta.
- **Sécurité écriture Shopify** : pilot-safe + confirm_live_write + plan-based gates → 3 verrous indépendants vérifiés.
- **Conformité Polaris** : pas de composant custom non standard pour le marchand habitué à Shopify Admin.

---

## 8. État final attendu à la fin de la Phase 12

À l'issue de la tâche 140 (soumission App Store finale), Giulio Geo doit présenter aux reviewers Shopify :

- ✅ Une **app installable** depuis l'App Store.
- ✅ Un **workflow complet** Connecter → Comprendre → Proposer → Valider → Appliquer → Mesurer démontrable en moins de 5 minutes.
- ✅ Un **dashboard d'accueil unique** synthétisant les 6 modules en 6 zones lisibles.
- ✅ **3 actions prioritaires** maximum visibles à tout moment.
- ✅ **Aucune écriture Shopify** sans review humaine + dry-run + confirm_live_write.
- ✅ **Rollback opérationnel** sur les 10 content_types.
- ✅ **Mesure d'impact** automatique avec verdicts à J+7 / J+30 / J+60 / J+90.
- ✅ **Coût LLM** affiché et plafonné par plan.
- ✅ **AI Visibility désactivée V1** avec encart explicite sans promesse.
- ✅ **Test utilisateur** documenté sur 3 marchands pilotes (compréhension < 5 min validée).
- ✅ **Conformité GDPR / Billing / OAuth** maintenue depuis tâche 75.

---

## 9. Limites du cadrage

- **138 ne mesure pas la qualité du contenu LLM généré** dans l'absolu. Il vérifie que les garde-fous sont en place, pas que toutes les FAQ produites sont parfaites. La qualité fine vient post-launch via feedback marchand.
- **138 ne couvre pas la stratégie marketing / pricing** au-delà du plan technique. Ces décisions sortent du périmètre produit.
- **138 ne traite pas la roadmap V2** (AI Visibility complète, blog massif, multilingue avancé, etc.). Ces extensions sont explicitement repoussées dans les docs amont.
- **138 ne juge pas du timing** de la soumission. Le go/no-go est une décision technique, le timing est une décision business.

---

## 10. Récapitulatif des 11 docs amont consolidés

Les critères §3 sont la consolidation de ces 11 documents :

| Doc | Tâche | Couverture |
|---|---|---|
| `docs/llm-strategy.md` | 129 | §3.9 (Coût LLM maîtrisé) |
| `docs/product-scope.md` | 127 | §3.5 (Scope produit V1) |
| `docs/crawl-strategy.md` | 128 | §3.6 (Pas de Screaming Frog obligatoire) |
| `docs/niche-understanding.md` | 130 | §3.13 (Niche gating) |
| `docs/readiness-audit.md` | 131 | §3.1 (Compréhension), §3.12 (Dashboard impact) |
| `docs/opportunity-finder.md` | 132 | §3.2 (3 actions, en amont) |
| `docs/priority-engine.md` | 133 | §3.2 (3 actions prioritaires), §3.3 (IA assistante) |
| `docs/ai-content-actions.md` | 134 | §3.3 (Content actions), §3.9 (prompts v2.0) |
| `docs/safe-apply.md` | 135 | §3.4 (Event), §3.10 (Rollback), §3.11 (Dry-run) |
| `docs/impact-tracker.md` | 136 | §3.4 (Mesure), §3.7 (Pas de promesse), §3.8 (Google/IA séparés), §3.12 (Dashboard impact) |
| `docs/dashboard-simplification.md` | 137 | §3.1 (Compréhension), §3.8 (Séparation Google/IA visible) |

Aucune décision produit n'est introduite dans 138 — uniquement de la consolidation et de la mise en checklist opérationnelle.

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Architecture de la checklist (13 catégories × critère + preuve + statut) | ✅ Documentée | Section 2 |
| Critères 3.1 — Compréhension marchand | ✅ Listés | Section 3.1 |
| Critères 3.2 — 3 actions prioritaires | ✅ Listés | Section 3.2 |
| Critères 3.3 — IA assistante avec review humaine | ✅ Listés | Section 3.3 |
| Critères 3.4 — Mesure d'impact obligatoire | ✅ Listés | Section 3.4 |
| Critères 3.5 — Scope produit Active | ✅ Listés | Section 3.5 |
| Critères 3.6 — Pas de Screaming Frog obligatoire | ✅ Listés | Section 3.6 |
| Critères 3.7 — Pas de promesse non prouvée | ✅ Listés | Section 3.7 |
| Critères 3.8 — Google / IA séparés | ✅ Listés | Section 3.8 |
| Critères 3.9 — Coût LLM maîtrisé | ✅ Listés | Section 3.9 |
| Critères 3.10 — Rollback opérationnel | ✅ Listés | Section 3.10 |
| Critères 3.11 — Dry-run par défaut | ✅ Listés | Section 3.11 |
| Critères 3.12 — Dashboard impact lisible | ✅ Listés | Section 3.12 |
| Critères 3.13 — Niche Understanding gating | ✅ Listés | Section 3.13 |
| Processus go/no-go formalisé | ✅ Documenté | Section 6 |
| Cohérence avec les 11 docs amont | ✅ Vérifiée | Section 10 |
| Exécution de la checklist (cocher chaque ligne) | ⏳ Phase 12 — tâche 139 | Section 6 |

> Cette tâche **clôture la Phase 11.7** côté documentation stratégique. La Phase 12 (tâche 139 décision + tâche 140 soumission) reprend cette checklist pour exécuter le go/no-go App Store.
