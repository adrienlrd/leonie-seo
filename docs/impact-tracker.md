# Impact Tracker as Core Product Value — Léonie SEO

> Référence canonique du module central de mesure d'impact. Positionne les 8 briques de la Phase 11.5 (déjà codées) comme **le cœur différenciant** de Léonie SEO : la preuve que chaque optimisation a aidé, ou non. Sépare strictement Search Performance (GSC/GA4) et AI Visibility (signal mesurable mais imparfait, branche opt-in V2).
>
> Statut : décisions produit/architecture figées au 2026-05-20 (tâche 136, Phase 11.7). Aucun code applicatif n'est modifié dans cette tâche.

---

## 1. Pourquoi ce cadrage

Léonie SEO n'est pas un générateur de contenu — c'est un **moteur de preuve d'impact**. Cette posture est ce qui différencie l'app des dizaines d'outils SEO génératifs disponibles sur l'App Store.

L'infrastructure existante est déjà **complète et opérationnelle** (Phase 11.5 tâches 116-125) :

| Brique | Fichier | Statut |
|---|---|---|
| Optimization Snapshot | `app/geo/optimization_snapshots.py:103` | ✅ codé |
| GEO Impact Ledger (events) | `app/geo/ledger.py:48`, table `geo_impact_events` | ✅ codé |
| Validation Timeline J+7/J+30/J+60/J+90 | `app/geo/validation_timeline.py:100` | ✅ codé |
| Progress Curve | `app/geo/progress_curve.py:1` | ✅ codé |
| Confidence Score | `app/geo/confidence.py:139` | ✅ codé |
| Before/After Report | `app/geo/impact_report.py:137` | ✅ codé |
| Win/Neutral/Risk + Next Best Action Loop | `app/geo/next_best_actions.py:85` | ✅ codé |
| Retention Milestones | `app/geo/retention_milestones.py:54` | ✅ codé |

Mais ces 8 briques sont aujourd'hui **présentées comme 5 outils séparés** dans l'UI (`app.impact`, `app.impact-report`, `app.retention-milestones`, `app.next-best-actions`, `app.reports` — 1 358 lignes Remix au total). Le marchand ne voit pas le cycle complet.

La tâche 136 ne réécrit rien. Elle :

1. **Repositionne** les 8 briques comme un seul module conceptuel — *Impact Tracker*.
2. **Standardise le branchement** strict avec 135 (chaque apply crée un event).
3. **Sépare explicitement** Search Performance et AI Visibility en deux axes distincts.
4. **Cadre l'AI Visibility** comme branche future opt-in, sans promesse non tenable.
5. **Consolide l'UI** en une vue principale Impact + drill-downs.
6. **Verrouille le couplage** avec 133 (`success_metric` obligatoire) et 134 (event créé après apply).

---

## 2. Le cycle de mesure unifié

```
1. Plan         ← Priority Engine 133 émet une action avec success_metric obligatoire
2. Snapshot     ← Optimization Snapshot capture l'état AVANT (scores, content, facts, GSC, GA4, commerce)
3. Apply        ← Safe Apply 135 écrit Shopify, capture rollback
4. Event        ← Ledger crée un geo_impact_event lié à l'action_id (135 §7)
5. Wait         ← Validation Timeline planifie J+7 / J+30 / J+60 / J+90
6. Re-measure   ← À chaque jalon, capture metrics_after depuis GSC/GA4/Shopify
7. Confidence   ← Confidence Score note la fiabilité du signal (volume, délai, stabilité)
8. Verdict      ← Before/After Report classe en Win / Neutral / Risk / Inconclusive
9. Next Action  ← Next Best Action Loop propose répliquer / ajuster / attendre / rollback
10. Retention   ← Milestones expliquent au marchand pourquoi rester pendant la mesure
```

Le cycle est **fermé** : il n'y a pas d'optimisation sans mesure, et pas de mesure sans hypothèse explicite et `success_metric` documentée.

Position dans le workflow GEO Autopilot :

```
Connecter → Comprendre → Proposer → Valider → Appliquer → [Mesurer (136)]
                                                              ↻ alimente Priority Engine 133
```

L'Impact Tracker **boucle** sur le Priority Engine : un Win se réplique, un Risk se rollback, un Neutral se réajuste.

---

## 3. Question produit unique

> **Pour chaque optimisation appliquée, quelle est son contribution mesurable, dans quelle fenêtre de temps, avec quelle confiance, et que faire ensuite ?**

Cette question structure l'ensemble du module. Aucune brique ne fait sens isolée — toutes existent **pour répondre à cette question pour une page produit donnée**.

---

## 4. Deux axes de mesure séparés

### Search Performance (cœur V1, fiable)

| Source | Métriques | Fenêtre |
|---|---|---|
| Google Search Console | impressions, clics, CTR, position moyenne, requêtes gagnées, nouvelles requêtes longues | 28 jours rolling |
| Google Analytics 4 (si configuré) | sessions organiques, conversions, revenu, taux conversion, panier moyen | 28 jours rolling |
| Shopify | statut produit, stock, prix, changements pendant période de mesure | snapshot à chaque jalon |
| Score AI Search Readiness | score `before` / `after` (cf. `docs/readiness-audit.md`) | recalcul à chaque jalon |

### AI Visibility (signal séparé, branche opt-in V2)

| Source | Métriques | Statut V1 |
|---|---|---|
| ChatGPT / Perplexity / Gemini prompts suivis | mention de la marque, citation du site, position dans la réponse, concurrents visibles, sources citées | **Non implémenté en V1**, hors scope code actuel |
| AI Answer Competitor Monitor | données déjà partielles côté `app/geo/competitors.py:62` (mock) | V1 = light, V2 = scraping live opt-in |

### Règle de séparation stricte

- **Jamais d'agrégation** d'un score Search Performance avec un score AI Visibility.
- **Deux dashboards distincts** côté UI, deux jeux de courbes, deux séries de verdicts.
- **AI Visibility n'est jamais présenté comme garanti.** Aucun message marketing ou UI ne suggère que l'app pousse une marque dans ChatGPT. La visibilité IA est **un signal mesurable mais imparfait**.
- **Le verdict global d'une optimisation reste basé sur Search Performance** en V1. AI Visibility complète, ne décide pas.

---

## 5. Structure de données canonique

Réutilise l'existant sans modification de schéma.

### Snapshot (table `geo_optimization_snapshots`)

Capturé à T0 et à chaque jalon (J+7, J+30, J+60, J+90). Champs (existants `app/geo/optimization_snapshots.py:103`) :

- `resource_type`, `resource_id`, `resource_title`, `path`, `action_type`, `source`, `hypothesis`, `captured_at`
- `scores` : `readiness_score`, `seo_score`, `readiness_components`
- `content` : `title`, `handle`, `description`, `description_word_count`, `seo`
- `facts` : `confirmed_count`, `missing_count`, `missing_facts`
- `commerce` : `price`, `sku`, `inventory_quantity`, `status`
- `recommendations`, `metrics` (GSC : clicks, impressions, ctr, position)

### Event (table `geo_impact_events`)

Lien unique entre action 134, apply 135 et mesure 136. Champs (existants `app/geo/ledger.py:48`) :

- `shop`, `created_at`, `event_type`, `status` ∈ `{planned, applied, measured, rolled_back}`
- `resource_type`, `resource_id`, `resource_title`, `action_type`, `action_id`, `content_type`
- `source` (action recommandée), `job_id`, `snapshot_id`, `hypothesis`
- `score_before`, `score_after`, `measurement_status`
- `status_history` JSON, `before_snapshot`, `after_snapshot`, `metrics_before`, `metrics_after`
- `estimated_impact` (issu de `success_metric` du Priority Engine), `observed_impact` (mesuré)
- `notes`

### Couplage strict avec 135

Aucun event n'existe sans :

- un `action_id` venu du Content Action 134 ;
- un `success_metric` venu du Priority Engine 133 ;
- un `applied_at` validé par le workflow Safe Apply 135 (cf. `docs/safe-apply.md` §7).

Inversement : **aucun apply 135 n'est terminé sans event créé**. Ce couplage est strict côté code par la séquence `create_geo_event()` appelée dans le post-apply.

---

## 6. Fenêtres de mesure

Reprises de `app/geo/validation_timeline.py:100` sans modification.

| Jalon | Sens | Statut typique |
|---|---|---|
| **J+0** | Baseline | snapshot capturé, action appliquée |
| **J+7** | Premiers signaux faibles | confidence `signal_faible` ou `données_insuffisantes` |
| **J+30** | Première analyse sérieuse | confidence `impact_probable` possible si volume suffisant |
| **J+60** | Signal plus fiable | confidence `impact_probable` ou `impact_fort` |
| **J+90** | Conclusion | verdict définitif `Win/Neutral/Risk/Inconclusive` |

États de fenêtre : `pending` (trop tôt), `measuring` (fenêtre ouverte), `ready` (données capturées), `inconclusive` (volume insuffisant).

### Règle d'attente

- **Tant qu'on est < J+7**, aucun verdict définitif n'est affiché côté UI. Bandeau explicite : *« Premiers signaux attendus le {date}. »*
- **Tant qu'on est < J+30**, le verdict est marqué `signal_préliminaire` même s'il existe.
- **Une seule fenêtre par action** — pas de re-calcul opportuniste si le marchand recharge la page.

---

## 7. Confidence Score — fiabilité du signal

Reprise de `app/geo/confidence.py:139` sans modification. Score 0-100 = somme pondérée :

| Facteur | Poids max |
|---|---|
| `elapsed_score` (basé J+7/J+30/J+60/J+90) | 40 |
| `volume_score` (impressions baseline) | 20 |
| `delta_score` (+15 si amélioration GEO) | 15 |
| `gsc_score` (+10 si impressions montent) | 10 |
| `revenue_score` (+10 si revenu observé) | 10 |
| `stability_score` (+5 si stock + prix stables) | 5 |

### Labels

| Score | Label |
|---|---|
| ≥ 75 | `impact_fort` |
| 50-74 | `impact_probable` |
| 25-49 | `signal_faible` |
| < 25 | `données_insuffisantes` |

### Règles

- **Le confidence score est obligatoire** sur tout verdict, dans tout rapport, dans toute UI affichant un Win/Neutral/Risk.
- **`données_insuffisantes` n'est pas un échec** — c'est un état explicite qui empêche les fausses conclusions.
- **Stabilité commerce** : si le prix ou le stock a changé pendant la fenêtre, `stability_score` chute → le confidence baisse → le verdict est plus prudent. Aucun verdict ne tire de conclusion d'un signal pollué.

---

## 8. Verdicts — Win / Neutral / Risk / Inconclusive

Calculés dans `app/geo/impact_report.py:137`. Schéma existant :

```
verdict ∈ {positif_probable, neutre, négatif_possible, inconclusif}
```

| Verdict | Critères |
|---|---|
| `positif_probable` | `confidence ≥ 50` ET `geo_delta ≥ 0` (ou progrès GSC sans régression Shopify) |
| `neutre` | `confidence ≥ 25` ET `geo_delta == 0` |
| `négatif_possible` | `geo_delta < 0` (peu importe la confidence) |
| `inconclusif` | `confidence < 25` OU données manquantes |

### Règles

- **`négatif_possible` déclenche systématiquement** une proposition de rollback dans Next Best Action.
- **`inconclusif` ne déclenche jamais** de nouvelle action automatique — l'app attend plus de données.
- **`positif_probable` propose** la réplication sur produits similaires (cf. `app/geo/next_best_actions.py:85`).
- **`neutre`** propose un ajustement ciblé (FAQ, schema, maillage) sans rollback.

---

## 9. Next Best Action Loop — la boucle de rétention par la valeur

Reprise de `app/geo/next_best_actions.py:85` sans modification. 4 verdicts → 4 actions standardisées :

| Verdict | Next action | Priority | Dry-run | Suggested resources |
|---|---|---|---|---|
| `positif_probable` | `répliquer` | high | `True` (toujours) | produits similaires (vendor + product_type match) |
| `neutre` | `ajuster` | medium | `True` | ajustements FAQ / schema / maillage |
| `négatif_possible` | `rollback` | high | `True` (jamais bypassé) | invocation Safe Apply 135 revert |
| `inconclusif` | `attendre` | low | n/a | aucun |

### Couplage retour vers 133

Chaque Next Best Action devient une **proposition** au prochain cycle Priority Engine. L'engine 133 décide si elle entre dans les 3 actions prioritaires — pas le Tracker. Cela évite de spammer le marchand d'actions automatiques.

---

## 10. Retention Milestones — rétention par valeur réelle

Reprise de `app/geo/retention_milestones.py:54`. 4 jalons J+7 / J+30 / J+60 / J+90 visibles côté UI, accompagnés de messages bilingues (FR/EN) expliquant la valeur de garder l'app active.

### Règle anti-dark-pattern

Les messages de rétention sont basés sur des **faits techniques vrais** :
- les moteurs de recherche ont besoin de temps pour re-crawler ;
- les premiers signaux GSC apparaissent à J+7 ;
- les conclusions fiables se stabilisent à J+60-J+90.

**Jamais** :
- pas de urgency artificielle (« il vous reste 24 h »),
- pas de chiffres trompeurs,
- pas de comparaison contre un score fictif,
- pas de pop-up bloquante.

Les milestones sont une **information**, pas un levier marketing agressif.

---

## 11. UI consolidée

### Vue principale `app.impact.tsx` (existante, à recentrer)

Devient l'**entrée unique** du module Impact. Compose les 8 briques en une seule page lisible :

- En haut : **Search Performance dashboard** — score GEO global, courbes 90 jours (GEO score, impressions GSC, clics, CTR, position, sessions GA4, conversions, revenu).
- Au milieu : **Active optimizations** — liste des actions appliquées avec verdict + confidence + fenêtre en cours.
- Sur le côté : **Retention Milestones** — prochain jalon visible.
- En bas : **Next Best Actions** — propositions de réplication / ajustement / rollback / attente.
- **Encart séparé "AI Visibility"** — désactivé en V1 avec message *« Suivi des moteurs IA disponible dans une version future. »*

### Drill-downs accessibles via liens

| Page Remix | Statut post-136 | Accès |
|---|---|---|
| `app.impact-report` | Conservée, drill-down | Lien depuis une action sur `app.impact` |
| `app.retention-milestones` | Conservée, drill-down | Lien depuis l'encart Milestones |
| `app.next-best-actions` | Conservée, drill-down | Lien depuis l'encart Next Best Actions |
| `app.reports` | Conservée, drill-down | Lien "Exporter" en haut de `app.impact` |

### Pas de page dépréciée

Toutes les pages existantes restent en place et fonctionnelles. La tâche 136 ne casse rien — elle **repositionne**.

---

## 12. AI Visibility — branche future opt-in

### Position V1

- **Pas implémenté côté code aujourd'hui.** Aucun module `*visibility*.py`.
- **`app/geo/competitors.py:62`** fait déjà un mock light (cf. tâche 115 / 132).
- **UI** : encart visible mais désactivé, avec message d'attente.

### Conditions d'activation V2 (hors Phase 11.7)

- Pricing distinct (option Pro/Agency ou add-on).
- Moteur de prompts à suivre par shop (10 prompts standard + 10 personnalisés).
- Cron hebdomadaire qui interroge ChatGPT / Perplexity / Gemini.
- Persistance : nouvelle table `ai_visibility_events` (séparée de `geo_impact_events`).
- UI séparée `app.ai-visibility.tsx`, jamais fusionnée avec Search Performance.

### Garde-fous

- Aucune promesse d'apparition dans les moteurs IA, ni en V1, ni en V2.
- L'AI Visibility est un signal mesuré, jamais un objectif garanti.
- Le verdict d'optimisation reste basé sur Search Performance, même en V2.
- Les concurrents visibles sont reportés à titre informatif, jamais copiés.

### Pourquoi pas en V1

- Coûts LLM additionnels élevés (interroger 3 moteurs IA × 20 prompts × 1000 shops = budget non prévu).
- Volatilité des moteurs IA — un prompt suivi peut donner des réponses différentes à 1h d'intervalle.
- Légalité incertaine sur le scraping ChatGPT/Perplexity en V1.
- Le marchand non technique sature déjà sur Search Performance. Mieux vaut livrer une mesure fiable d'un axe que deux axes flous.

---

## 13. Endpoints — déjà en place

| Endpoint | Statut |
|---|---|
| `GET /api/shops/{shop}/geo/snapshots` | ✅ existant |
| `GET /api/shops/{shop}/geo/events` | ✅ existant |
| `GET /api/shops/{shop}/geo/validation-timeline` | ✅ existant |
| `GET /api/shops/{shop}/geo/progress` | ✅ existant |
| `GET /api/shops/{shop}/geo/confidence` | ✅ existant |
| `GET /api/shops/{shop}/geo/impact-report` | ✅ existant |
| `GET /api/shops/{shop}/geo/next-best-actions` | ✅ existant |
| `GET /api/shops/{shop}/geo/retention-milestones` | ✅ existant |

Aucun endpoint à créer pour la V1 publique. La tâche 136 vérifie seulement que :

- chaque endpoint retourne `confidence` + `verdict` + `axis: search_performance` (au lieu d'omettre cette dimension).
- l'encart AI Visibility consomme un nouvel endpoint `GET /ai-visibility/status` qui retourne `{ "enabled": false, "available_in": "v2" }` en V1.

---

## 14. Cohérence avec les autres modules Phase 11.7

- **127 Product Scope** : Impact Tracker n'agrège que les events sur produits `ACTIVE Online Store` dans le score global. Les events sur Drafts apparaissent dans une vue séparée "Pre-launch".
- **128 Crawl L3** : pas de dépendance directe — le tracker mesure le résultat des changements, pas les checks.
- **129 LLM Strategy** : le tracker ne consomme **pas** de LLM. Aucun appel `router.complete()` côté Impact Tracker.
- **130 Niche Understanding** : pas de dépendance directe. Les `forbidden_promises` violations apparaissent comme contexte sur les events liés à du contenu rejeté.
- **131 Readiness Audit** : `score_before` / `score_after` viennent du score unifié 131.
- **132 Opportunity Finder** : un Win se reboucle dans Opportunity Finder (alimente `priority_products`).
- **133 Priority Engine** : `success_metric` obligatoire devient le critère d'évaluation. Pas de tracking sans métrique.
- **134 AI Content Actions** : chaque action produit `action_id`, lié à l'event.
- **135 Safe Apply** : aucun apply terminé sans event créé. Couplage strict (cf. `docs/safe-apply.md` §7).

---

## 15. Garde-fous transversaux

- **Aucune mesure agrégée fictive.** Si GA4 manque, l'app le dit. Si le volume GSC est trop faible, confidence = `données_insuffisantes` et verdict = `inconclusif`.
- **Pas de cherry-picking** dans les rapports. Tous les events appliqués sont mesurés et reportés, y compris les `négatif_possible`.
- **Séparation Search vs AI** stricte côté code et côté UI.
- **Pas de promesse non tenable.** Tous les textes UI / docs marchand reposent sur ce qui est mesurable.
- **Stabilité commerce comptée** : un changement de prix/stock pendant la fenêtre réduit le confidence — pas de conclusion sur un signal pollué.
- **Rollback est un verdict acceptable.** Proposer un rollback est une mesure de valeur, pas un échec.
- **Pas de dark patterns** de rétention. Les milestones sont des informations, pas des leviers marketing.
- **Pas de re-mesure opportuniste.** Une fenêtre fermée reste fermée. Le marchand peut relancer une optimisation, mais la précédente est figée comme preuve.
- **Logs structurés** : chaque mesure capturée logue `shop + action_id + jalon + confidence + verdict`. Auditable.
- **Multi-tenant strict** : les events d'un shop ne fuient jamais vers un autre.

---

## 16. Mapping fichiers

### Existant à réutiliser (déjà codé, 0 modification dans 136)

| Fichier | Rôle |
|---|---|
| `app/geo/optimization_snapshots.py:103` | Snapshot avant/après |
| `app/geo/ledger.py:48` | Events GEO ledger |
| `app/geo/validation_timeline.py:100` | Timeline J+7 / J+30 / J+60 / J+90 |
| `app/geo/progress_curve.py:1` | Courbes 90 jours |
| `app/geo/confidence.py:139` | Score de confiance |
| `app/geo/impact_report.py:137` | Verdicts + Markdown export |
| `app/geo/next_best_actions.py:85` | Loop répliquer/ajuster/rollback/attendre |
| `app/geo/retention_milestones.py:54` | Jalons rétention |
| `app/db.py:144` (`geo_impact_events`) | Table events |
| `app/db.py:` (`geo_optimization_snapshots`) | Table snapshots |
| `shopify-app/app/routes/app.impact.tsx` | Dashboard principal |
| `shopify-app/app/routes/app.impact-report.tsx` | Drill-down rapport |
| `shopify-app/app/routes/app.retention-milestones.tsx` | Drill-down jalons |
| `shopify-app/app/routes/app.next-best-actions.tsx` | Drill-down actions |
| `shopify-app/app/routes/app.reports.tsx` | Export catalog |

### À ajouter pour V1 publique (post-136)

| Fichier | Rôle |
|---|---|
| `app/api/ai_visibility.py` | Endpoint `GET /ai-visibility/status` retournant `{enabled: false, available_in: "v2"}` |
| Encart "AI Visibility" dans `app.impact.tsx` | Désactivé V1, lien explicatif sans promesse |
| Recentrage du dashboard `app.impact.tsx` autour du cycle complet (sections §11) | Réorganisation UI sans réécriture des composants |

### À garder en V2 (hors Phase 11.7)

| Fichier | Rôle |
|---|---|
| `app/ai_visibility/prompts.py` | Suite de prompts standard suivis |
| `app/ai_visibility/runner.py` | Cron interrogation ChatGPT / Perplexity / Gemini |
| `app/db.py` (table `ai_visibility_events`) | Table séparée |
| `shopify-app/app/routes/app.ai-visibility.tsx` | Page dédiée |

---

## 17. Critères d'acceptation de la V1 publique

À cocher quand 136 est considéré comme livré dans le sens "cœur de valeur" :

- [ ] Le dashboard `app.impact.tsx` compose les 8 briques en une seule vue principale.
- [ ] Chaque action visible affiche `verdict` + `confidence` + `axis: search_performance`.
- [ ] L'encart AI Visibility est visible mais désactivé avec message clair.
- [ ] Aucun mélange Search Performance / AI Visibility dans les agrégations.
- [ ] Tout `applied` côté Safe Apply 135 crée un event (couplage strict vérifié par test).
- [ ] Tout event a un `success_metric` venu de 133.
- [ ] La séquence Snapshot → Apply → Event → Timeline → Confidence → Verdict → Next Action → Retention est exécutée pour chaque optimisation.
- [ ] Stabilité commerce détectée : un changement prix/stock pendant la fenêtre baisse le confidence.
- [ ] Aucun dark pattern de rétention détecté dans les textes UI.
- [ ] Les drill-downs (`impact-report`, `retention-milestones`, `next-best-actions`, `reports`) restent accessibles.
- [ ] Endpoint `GET /ai-visibility/status` retourne `{enabled: false}` en V1.
- [ ] Tests existants Phase 11.5 continuent à passer (régression nulle).

---

## 18. Limites V1 explicites

- **AI Visibility hors V1.** Mock light dans `app/geo/competitors.py:62` reste accessible en drill-down `app.geo-competitors`, mais pas dans le verdict.
- **Pas de comparaison concurrentielle automatisée.** Le marchand ne voit pas "votre concurrent X a appliqué la même optimisation".
- **Pas de A/B testing automatique** des contenus.
- **Pas de scoring multi-langues différencié.** Le verdict agrège toutes locales en V1.
- **Pas d'attribution cross-channel.** GA4 organique uniquement, pas de pondération paid / social.
- **Pas de cohort analysis.** Pas de segmentation par audience GA4.
- **Pas de re-mesure d'une fenêtre fermée.** Si le marchand veut re-mesurer, il doit re-lancer une nouvelle optimisation.

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Cycle de mesure en 10 étapes | ✅ Documenté | Section 2 |
| Question produit unique | ✅ Cadrée | Section 3 |
| Séparation Search Performance vs AI Visibility | ✅ Stricte | Section 4 |
| Structure de données canonique (snapshot + event) | ✅ Réutilisée | Section 5 |
| Fenêtres de mesure J+7 / J+30 / J+60 / J+90 | ✅ Réutilisées | Section 6 |
| Confidence Score obligatoire | ✅ Imposé | Section 7 |
| 4 verdicts standardisés | ✅ Réutilisés | Section 8 |
| Next Best Action Loop branché vers 133 | ✅ Cadré | Section 9 |
| Retention Milestones sans dark pattern | ✅ Documenté | Section 10 |
| UI consolidée (entrée unique + drill-downs) | ✅ Repositionnée | Section 11 |
| AI Visibility = branche V2 opt-in, pas de promesse | ✅ Cadré | Section 12 |
| Endpoints (déjà existants, pas de création V1 sauf `ai-visibility/status`) | ✅ Documenté | Section 13 |
| Cohérence autres modules 11.7 | ✅ Vérifiée | Section 14 |
| Recentrage UI `app.impact.tsx` avec sections §11 | ⏳ À porter | Section 16 |
| Endpoint `GET /ai-visibility/status` | ⏳ À créer | Section 16 |
| Encart "AI Visibility" désactivé | ⏳ À ajouter | Section 16 |

> Les briques Python et les pages Remix sont déjà 100 % codées (Phase 11.5). Les éléments ⏳ sont uniquement de la **réorganisation UI** + un endpoint de statut pour cadrer l'AI Visibility comme branche future. Aucun travail Python supplémentaire n'est nécessaire pour positionner Impact Tracker comme cœur de valeur V1.
