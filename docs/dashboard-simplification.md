# Merchant-Friendly Dashboard Simplification — Léonie SEO

> Référence canonique du dashboard marchand non-expert. Définit la vue d'accueil unique qui synthétise les sorties des 6 modules précédents (127-136) en cartes lisibles, sans jargon SEO/GEO en premier niveau, avec séparation stricte Google / IA et coût LLM visible.
>
> Statut : décisions produit/architecture figées au 2026-05-20 (tâche 137, Phase 11.7). Aucun code applicatif n'est modifié dans cette tâche.

---

## 1. Pourquoi ce cadrage

Le dashboard actuel (`shopify-app/app/routes/app._index.tsx:1`) affiche 4 cartes : **SetupCard**, **AlertsCard**, **ShortcutsCard** (4 hubs), **Recent activity**. C'est un bon socle technique mais il ne montre pas :

- ❌ le score GEO global de la boutique ;
- ❌ la niche détectée par l'IA (`niche_hypothesis` de la tâche 130) ;
- ❌ les **3 actions prioritaires** issues du Priority Engine (133) ;
- ❌ l'impact des optimisations en cours (verdict Win/Neutral/Risk de 136) ;
- ❌ la **séparation Google ↔ IA** des métriques ;
- ❌ le coût LLM ou le budget utilisé (seulement dans Settings aujourd'hui).

Côté navigation, **5 hubs + 14 pages GEO score/diagnostic** sont accessibles, mais le marchand ne sait pas par où commencer. La tâche 137 fixe les règles pour un dashboard qui :

1. **Résume la valeur produit** en moins de 30 secondes de lecture.
2. **Pousse vers l'action** (boutons "Préparer cette action" depuis 133).
3. **Sépare strictement** Search Performance et AI Visibility (cf. `docs/impact-tracker.md` §4).
4. **Affiche le coût LLM** comme première classe (cohérence `docs/llm-strategy.md`).
5. **Sans jargon en premier niveau** — vocabulaire marchand non-technique.

---

## 2. Promesse de la vue d'accueil

> *« En une vue, je sais où ma boutique en est, ce que l'IA a compris d'elle, les 3 choses à faire maintenant, et ce que les optimisations en cours ont déjà donné. »*

Critères de réussite :

- Lecture en **moins de 30 secondes** par un marchand non-technique.
- **Zéro jargon SEO/GEO** au premier niveau (mots interdits cf. §9).
- **Une seule action principale** visible en haut (CTA Priority Engine).
- **Aucun chiffre brut sans contexte** : chaque métrique a une phrase de cadrage en français.

---

## 3. Structure cible — 6 zones

```
┌──────────────────────────────────────────────────────────────┐
│  Header                                                       │
│  [Boutique] [Plan] [Statut système ✓]   [Coût LLM ce mois]    │
├──────────────────────────────────────────────────────────────┤
│  Zone 1 — État de votre boutique                              │
│  Score AI Search Readiness + niveau (excellent/bon/partiel)   │
│  Niche détectée (1 phrase) + nb produits Active évalués       │
├──────────────────────────────────────────────────────────────┤
│  Zone 2 — Vos 3 actions prioritaires (cartes 133)             │
│  [Carte 1] [Carte 2] [Carte 3]                                │
│  Chaque carte : titre lisible, "pourquoi maintenant", bouton │
├──────────────────────────────────────────────────────────────┤
│  Zone 3 — Impact des optimisations en cours                  │
│  Mini-courbe Search Performance + nb optimisations actives   │
│  Prochain jalon de mesure (J+7, J+30, ...)                   │
├──────────────────────────────────────────────────────────────┤
│  Zone 4 — Onboarding & connexions (si incomplet)             │
│  Étapes restantes : GSC, GA4, Niche validée                  │
├──────────────────────────────────────────────────────────────┤
│  Zone 5 — Alertes (si non vide)                              │
│  Top 3 alertes : régression CTR, budget LLM 80 %, jobs échoués│
├──────────────────────────────────────────────────────────────┤
│  Zone 6 — AI Visibility (désactivé V1)                       │
│  Encart explicatif : "Disponible dans une version future"     │
└──────────────────────────────────────────────────────────────┘
```

Le bandeau "Recent activity" actuel est déplacé dans `app.jobs` (déjà existant). Pas de duplication.

---

## 4. Détail des zones

### Header — statut système et coût LLM

| Élément | Source | Wording |
|---|---|---|
| Boutique | `shop` (session Shopify) | *"Boutique : {shop_name}"* |
| Plan | `subscriptions.plan` (`app/api/plans.py:10`) | Badge Polaris : Free / Pro / Agency |
| Statut système | endpoint `/health` | ✓ / ⚠ — pas de jargon, juste icône |
| **Coût LLM ce mois** | `get_shop_metrics(shop, days=30)` (`app/observability/metrics.py:47`) + plan budget | *"3,20 € / 15 € ce mois"* + barre de progression |

Le coût LLM en première classe est un signal de transparence : le marchand voit ce que ses générations coûtent. Cohérent avec `docs/llm-strategy.md` §6 (budget par shop).

### Zone 1 — État de votre boutique

| Sous-zone | Contenu | Source |
|---|---|---|
| Score principal | Score `AI Search Readiness` 0-100 + niveau (`excellent` / `bon` / `partiel` / `faible`) + couleur | `docs/readiness-audit.md` §2, endpoint `/audit/readiness?scope=active` |
| Sous-titre | *"sur {N} produits actifs sur votre site"* | snapshot Shopify + `docs/product-scope.md` |
| Niche détectée | 1 phrase synthèse `niche_hypothesis.shop_summary.what_you_sell` | `docs/niche-understanding.md` §5 |
| Action niche | Bouton *"Voir ce que l'IA a compris"* → `app.niche-understanding.tsx` | — |

Wording exemple : *"Score : 68/100 (Bon) — sur 247 produits actifs. Votre boutique vend des accessoires premium pour chiens et chats."*

**Si `niche_hypothesis` non validée** : *"L'IA n'a pas encore analysé votre boutique. {CTA : Lancer l'analyse}."*

### Zone 2 — Vos 3 actions prioritaires

Affichage des **exactement 3 cartes** du Priority Engine (133). Pas une liste paginée — 3 cartes côte à côte (Polaris `Grid` ou `InlineStack`).

Pour chaque carte :

```
┌─────────────────────────────────────┐
│  [Rank #1]                          │
│  {Produit : Fontaine céramique chat}│
│                                     │
│  {Action lisible}                   │
│  "Compléter les caractéristiques    │
│   de cette page produit"            │
│                                     │
│  Pourquoi maintenant :              │
│  "Cette page reçoit déjà 800        │
│   impressions Google par mois mais  │
│   aucune matière n'est confirmée."  │
│                                     │
│  ⏱ Effort : faible                  │
│  📈 Impact attendu : moyen          │
│                                     │
│  [Préparer cette action →]          │
└─────────────────────────────────────┘
```

Sources : `docs/priority-engine.md` §5 (schéma dossier d'action). Le CTA "Préparer cette action" mène à `app.safe-apply.tsx` (cf. `docs/safe-apply.md`).

**Si moins de 3 actions disponibles** (`sparse_signal` cf. `docs/priority-engine.md` §3) :

- Affichage des cartes disponibles.
- Bandeau : *"L'IA cherche encore les meilleures actions. Revenez dans quelques jours."*

**Si aucune action** :

- Message d'attente avec étapes (cf. Zone 4).

### Zone 3 — Impact des optimisations en cours

| Élément | Source | Wording |
|---|---|---|
| Mini-courbe Search Performance 30 j | `app/geo/progress_curve.py:1` | Sparkline : score AI Search Readiness, impressions GSC, clics |
| Compteur optimisations actives | `geo_impact_events.status = applied` | *"7 optimisations en cours de mesure"* |
| Prochain jalon | `validation_timeline` (`app/geo/validation_timeline.py:100`) | *"Prochain bilan : J+7 le 27 mai"* |
| Action | Bouton *"Voir l'impact détaillé"* → `app.impact.tsx` | — |

**Si zéro optimisation appliquée** : *"Aucune optimisation appliquée pour l'instant. Lancez votre première action ci-dessus."*

### Zone 4 — Onboarding & connexions (conditionnelle)

Affichée uniquement si une étape critique manque. Reprise allégée de `app.onboarding.tsx`.

| Étape | Critère affichage |
|---|---|
| Connecter Shopify | toujours validé (OAuth requis pour entrer) |
| Importer Google Search Console | `google_tokens` absent ou `last_import > 14j` |
| Connecter Google Analytics 4 (recommandé) | `ga4_settings` absent — *"recommandé"*, pas bloquant |
| Valider la niche détectée | `niche_hypothesis.status != "validated_by_merchant"` |
| Choisir un plan | `subscriptions.plan = none` |

Aucune étape "appliquer votre première action" ici (c'est Zone 2 qui pousse).

### Zone 5 — Alertes (conditionnelle)

Affichée uniquement si `alerts.count > 0`. Max 3 alertes les plus critiques.

Types d'alertes prioritaires :

- Régression CTR ou position sur page Active (depuis `app/api/alerts.py`).
- Budget LLM ≥ 80 % (`docs/llm-strategy.md` §6).
- Jobs échoués récurrents (`app/jobs/store.py`).
- Snapshot Shopify obsolète (> 7 jours).
- `niche_hypothesis` désynchronisée du catalogue (> 20 % changement, cf. `docs/niche-understanding.md` §4).

Wording : *"⚠ Le budget IA est utilisé à 82 % ce mois. {Lien : ajuster les quotas}."*

### Zone 6 — AI Visibility (désactivé V1)

Encart fixe expliquant la branche future, sans promesse. Cohérent avec `docs/impact-tracker.md` §12.

Wording :

> **Suivi des moteurs IA (ChatGPT, Perplexity, Gemini)**
> Cette fonctionnalité optionnelle sera disponible dans une version ultérieure. Elle permettra de mesurer si votre marque est citée dans les réponses des moteurs IA. *La présence dans ces moteurs n'est jamais garantie ; il s'agit d'un signal mesuré, pas d'une promesse.*

Bouton *"Être notifié"* (opt-in newsletter) — pas de bouton activer / acheter en V1.

---

## 5. États dégradés explicites

| Situation | Affichage |
|---|---|
| Aucun snapshot Shopify | Zone 1 vide + bandeau *"Importation Shopify en cours…"* |
| GSC non connecté | Zone 3 vide + Zone 4 affiche l'étape GSC en premier |
| Plan Free, budget LLM atteint | Zone 2 affiche les 3 actions en mode "export uniquement", pas de bouton "Appliquer en live" |
| `niche_hypothesis` non validée | Zone 1 affiche prompt validation, Zone 2 limitée aux content_types non-factuels (`docs/ai-content-actions.md` §9) |
| Mode `pilot-safe` actif | Bandeau global *"Mode pilote actif — toute écriture Shopify est désactivée."* |
| Job `bulk_apply` en cours | Bandeau *"Application en cours… ({n}/{N})"* avec lien `app.jobs` |
| Snapshot obsolète > 7 j | Bandeau *"Vos données catalogue datent de plus de 7 jours. {Lien : Relancer le snapshot}"* |
| `sparse_signal` (< 3 actions) | Zone 2 affiche le nombre disponible + message d'attente |

Chaque état est explicite, sans message d'erreur technique, sans `null` affiché brut.

---

## 6. Wording — règles strictes

### Vocabulaire interdit en Zone 1-3

| ❌ Jargon | ✅ Remplacement |
|---|---|
| GEO | "moteurs IA" ou "recherche conversationnelle" |
| JSON-LD | "données structurées" |
| Schema.org | "données structurées" (idem) |
| Crawl L3 | "analyse de votre site" |
| Cannibalisation | "deux pages qui se concurrencent" |
| Score readiness | "Score Léonie" ou "Score IA" |
| CTR | "taux de clic" |
| Impressions | "vues Google" |
| Position moyenne | "position dans Google" |
| KW gap / longue traîne | "requêtes que vous pourriez gagner" |
| `forbidden_promises` | "à éviter" |
| `do_not_say` | "à éviter" |
| `confidence_score` | "fiabilité" |
| Verdict `positif_probable` | "impact probablement positif" |
| `inconclusif` | "encore trop tôt pour conclure" |

### Vocabulaire technique autorisé en Zones 4-6 (avec bulle d'aide)

- *Plan Free / Pro / Agency*
- *Budget IA* (LLM)
- *Mode pilote*
- *Snapshot* (avec tooltip "copie de votre catalogue")

### Tooltips Polaris

Chaque chiffre ou badge a une `Tooltip` Polaris qui explique en 1 phrase. Pas d'icône `?` brute sans contenu.

---

## 7. Internationalisation FR / EN

Toutes les chaînes nouvelles doivent vivre dans `shopify-app/app/lib/i18n.ts` (FR lignes 1-247, EN 249-491). Aucune chaîne en dur dans `app._index.tsx`.

Clés à ajouter (à porter par tâche d'implémentation, pas dans 137) :

```
dashboardZone1Title, dashboardZone1Niche, dashboardZone1Cta,
dashboardZone2Title, dashboardZone2SparseSignal, dashboardZone2NoAction,
dashboardZone3Title, dashboardZone3Sparkline, dashboardZone3NextMilestone,
dashboardZone3Cta,
dashboardZone4Title, dashboardZone4StepGSC, dashboardZone4StepGA4,
dashboardZone4StepNiche, dashboardZone4StepPlan,
dashboardZone5Title, dashboardZone5Empty,
dashboardZone6Title, dashboardZone6Body, dashboardZone6Cta,
dashboardHeaderShop, dashboardHeaderPlan, dashboardHeaderHealth,
dashboardHeaderLLMBudget,
dashboardStaleSnapshot, dashboardPilotSafeBanner, dashboardBulkApplyBanner
```

Pour chaque clé : version FR + EN strictement traduites, pas de jargon SEO dans la version FR cible non-experte.

---

## 8. Navigation cible

### Menu principal (`app.tsx:1`) — simplifié

| Entrée | Lien | Description en hover |
|---|---|---|
| Tableau de bord | `/app` | Page d'accueil |
| Analyse | `/app/audit-hub` | Diagnostic complet de votre boutique |
| Actions | `/app/optimization` (ou nouveau `/app/actions`) | Vos optimisations en cours et passées |
| Contenu | `/app/content-hub` | Génération assistée par IA |
| Mesure | `/app/insights` (renommé "Mesure") | Suivi de l'impact dans le temps |
| Réglages | `/app/account` | Connexions, plan, équipe |

Renommages :

- `/app/insights` → "Mesure" (plus parlant que "Insights")
- `/app/optimization` peut devenir `/app/actions` (plus parlant)
- `/app/account` → "Réglages" (FR) / "Settings" (EN)

Pas de suppression d'entrée — seulement renommage et clarté.

### Hubs intermédiaires — pas de changement structurel

Les 5 hubs (`HubGrid`) restent en place. Ils servent de drill-down depuis le dashboard. Le marchand averti peut y aller directement ; le marchand non-expert n'a pas besoin de les voir.

**Important** : aucune fonctionnalité existante n'est cachée. Chaque page reste accessible via son hub. Le dashboard est une **synthèse**, pas un masquage.

---

## 9. Performance et chargement

| Critère | Cible |
|---|---|
| First Contentful Paint | < 1.5 s |
| Time to Interactive | < 3 s |
| Loader Remix | 1 seule requête `GET /api/shops/{shop}/dashboard` (à créer, agrège les 6 zones) |
| Mise à jour Zone 3 (impact) | Polling 5 min en arrière-plan, pas de blocage |
| États dégradés | Affichés immédiatement, pas d'attente d'API |

### Endpoint canonique `GET /dashboard`

À créer côté backend pour éviter 6 appels parallèles depuis le loader Remix :

```
GET /api/shops/{shop}/dashboard
→ {
  "shop": "string",
  "plan": "free|pro|agency",
  "health": "ok|degraded|error",
  "llm_budget": {"used_usd": float, "limit_usd": float, "pct": 0-100},
  "zone1": {
    "global_score": int|null,
    "global_level": "excellent|bon|partiel|faible|null",
    "products_in_scope": int,
    "niche_summary": "string|null",
    "niche_validated": true|false
  },
  "zone2": {
    "actions": [...],  # exactement 3 du Priority Engine
    "sparse_signal": true|false,
    "no_action_reason": "string|null"
  },
  "zone3": {
    "active_optimizations_count": int,
    "next_milestone_at": "ISO date|null",
    "search_performance_sparkline": [{"date": "ISO", "value": number}],
    "trend": "up|flat|down"
  },
  "zone4": {
    "completed_steps": ["shopify", ...],
    "pending_steps": [{"key": "gsc|ga4|niche|plan", "label": "string"}]
  },
  "zone5": {
    "alerts": [...]  # max 3
  },
  "zone6": {"ai_visibility_enabled": false, "available_in": "v2"},
  "banners": {
    "pilot_safe": true|false,
    "stale_snapshot": true|false,
    "bulk_apply_in_progress": {"running": true|false, "current": int, "total": int}
  },
  "generated_at": "ISO date"
}
```

Cet endpoint **agrège** les modules existants côté serveur. Pas de cache long (5 min max pour éviter données obsolètes). Cohérent avec le pattern des dashboards Polaris.

---

## 10. Cohérence avec les modules 11.7

| Module | Apport au dashboard |
|---|---|
| 127 Product Scope | Zone 1 : "X produits actifs". Pas de Drafts/Archived dans le score principal. |
| 128 Crawl L3 | Zone 5 : alerte snapshot obsolète (> 7 j). |
| 129 LLM Strategy | Header : budget LLM en première classe. Zone 5 : alerte budget 80 %. |
| 130 Niche Understanding | Zone 1 : phrase de niche détectée. Zone 4 : étape validation niche. |
| 131 Readiness Audit | Zone 1 : score + niveau. Lien drill-down. |
| 132 Opportunity Finder | Source amont du Priority Engine, pas visible directement au dashboard. |
| 133 Priority Engine | Zone 2 : les 3 actions, c'est la pièce centrale du dashboard. |
| 134 Content Actions | Bouton "Préparer cette action" mène au workflow 135. |
| 135 Safe Apply | Bouton "Préparer cette action" + bandeau bulk-apply en cours. |
| 136 Impact Tracker | Zone 3 : impact en cours, prochain jalon. Zone 6 : AI Visibility V2 désactivé. |

Aucun module n'a un widget dédié à lui — le dashboard **synthétise**.

---

## 11. Mapping fichiers

### Existant à réutiliser

| Fichier | Rôle |
|---|---|
| `shopify-app/app/routes/app._index.tsx:1` | Dashboard actuel, **à recentrer** autour des 6 zones |
| `shopify-app/app/routes/app.tsx:1` | NavMenu Polaris, à renommer (Mesure, Actions, Réglages) |
| `shopify-app/app/components/HubGrid.tsx:1` | Hubs intermédiaires inchangés |
| `shopify-app/app/lib/i18n.ts:1` | i18n FR/EN à étendre avec clés `dashboard*` |
| `app/observability/metrics.py:47` | `get_shop_metrics` pour Header budget LLM |
| `app/observability/metrics.py:113` | `check_budget` pour alerte 80 % |
| `app/api/plans.py:10` | `plan` pour Header + comportement Zone 2 |
| Modules 127-136 cités §10 | Sources de données du nouvel endpoint `/dashboard` |

### À créer par la tâche d'implémentation (post-137)

| Fichier | Rôle |
|---|---|
| `app/api/dashboard.py` | Endpoint canonique `GET /api/shops/{shop}/dashboard` (agrégation §9) |
| `shopify-app/app/routes/app._index.tsx` (refactor) | 6 zones §3 + 7 banners §5 |
| `shopify-app/app/components/DashboardZone1.tsx` ... `Zone6.tsx` | Composants Polaris isolés |
| `shopify-app/app/components/DashboardHeader.tsx` | Budget LLM en première classe |
| Tests UI minimal Playwright | Vérif 6 zones rendues + accessibilité |

### Aucune dépréciation

Les 14 pages GEO score/diagnostic restent en place et accessibles. La tâche 137 simplifie la **vue d'accueil**, pas l'arborescence complète.

---

## 12. Garde-fous

- **Zéro jargon en Zone 1-3.** Vocabulaire marchand non-technique.
- **Score `AI Search Readiness` jamais agrégé avec autre chose.** Cohérent avec `docs/readiness-audit.md`.
- **AI Visibility jamais sur le score principal.** Cohérent avec `docs/impact-tracker.md`.
- **3 actions max** au premier niveau. Pas 5, pas 10.
- **Tooltips au lieu d'options de personnalisation** en V1. Le dashboard est figé, pas customizable.
- **Aucun chiffre sans contexte.** Toujours une phrase de cadrage.
- **Aucun message technique (`null`, `undefined`, stack trace).**
- **Aucun bouton "Appliquer" sur Free.** Bouton "Exporter" à la place (cf. `docs/safe-apply.md` §10).
- **Aucune notification push intrusive** en V1. Les alertes restent dans Zone 5.
- **Aucun dark pattern de rétention.** Cohérent avec `docs/impact-tracker.md` §10.
- **Conformité Polaris stricte.** Pas de composants custom inattendus pour le marchand habitué à Shopify Admin.
- **i18n exhaustif FR/EN.** Aucune chaîne en dur.

---

## 13. Critères d'acceptation de l'implémentation future

À cocher quand le dashboard est livré dans le sens de la tâche 137 :

- [ ] La vue d'accueil affiche les 6 zones §3 dans cet ordre.
- [ ] Header expose le budget LLM en première classe.
- [ ] Zone 1 affiche score + niveau coloré + phrase de niche.
- [ ] Zone 2 affiche exactement 3 cartes (ou message `sparse_signal`).
- [ ] Chaque carte Zone 2 a un bouton CTA qui mène à Safe Apply 135.
- [ ] Zone 3 affiche mini-courbe + prochain jalon + compteur d'optimisations actives.
- [ ] Zone 4 est conditionnelle, n'affiche que les étapes restantes.
- [ ] Zone 5 plafonnée à 3 alertes les plus critiques.
- [ ] Zone 6 affiche AI Visibility V2 désactivé sans promesse.
- [ ] Endpoint `GET /api/shops/{shop}/dashboard` retourne le schéma §9.
- [ ] Aucun mot interdit (§6) en Zone 1-3.
- [ ] Tooltips Polaris sur chaque badge ou chiffre.
- [ ] i18n FR/EN complet (clés §7).
- [ ] NavMenu renommé (Mesure / Actions / Réglages).
- [ ] States dégradés (§5) rendus sans erreur technique visible.
- [ ] Performance : FCP < 1.5 s, TTI < 3 s.
- [ ] Pas de page existante supprimée — les 14 pages diagnostic restent accessibles via hubs.

---

## 14. Limites V1 explicites

- **Pas de dashboard customizable.** Pas de widgets drag-and-drop, pas de masquage de zones.
- **Pas d'objectifs SMART configurables.** Pas de "atteindre 80/100 d'ici 30 jours".
- **Pas de leaderboard inter-marchands.** Pas de gamification.
- **Pas de digest email hebdo** en V1 (tâche 102 ultérieure si pertinent).
- **Pas de comparaison historique multi-période.** Une seule fenêtre de courbe (30 j) sur le dashboard ; le détail multi-fenêtre reste dans `app.impact`.
- **Pas de pré-visualisation Shopify thème** depuis le dashboard. Reste accessible via Safe Apply 135.
- **Pas de filtre par segment client.** Une seule vue agrégée par boutique.

---

## Annexe — État d'avancement

| Décision | État | Référence |
|---|---|---|
| Promesse vue d'accueil < 30 s | ✅ Cadrée | Section 2 |
| Structure 6 zones | ✅ Spécifiée | Section 3 |
| Wording (vocabulaire interdit + autorisé) | ✅ Documenté | Section 6 |
| Internationalisation FR/EN | ✅ Cadrée | Section 7 |
| NavMenu simplifié (renommages) | ✅ Décidé | Section 8 |
| Endpoint canonique `GET /dashboard` | ✅ Spécifié | Section 9 |
| Cohérence modules 127-136 | ✅ Vérifiée | Section 10 |
| États dégradés explicites | ✅ Documentés | Section 5 |
| AI Visibility V2 cadré sans promesse | ✅ Documenté | Section 4 (Zone 6) |
| Budget LLM en première classe | ✅ Documenté | Section 4 (Header) |
| Refactor `app._index.tsx` autour des 6 zones | ⏳ À porter | Section 11 |
| Endpoint `app/api/dashboard.py` | ⏳ À créer | Section 11 |
| Clés i18n `dashboard*` FR/EN | ⏳ À créer | Section 7 |
| NavMenu renommages Polaris | ⏳ À porter | Section 8 |
| Tests Playwright minimum | ⏳ À écrire | Section 11 |

> Les éléments ⏳ ne sont pas le périmètre de la tâche 137. Ils seront pris en charge par la tâche d'implémentation Dashboard ultérieure, qui consommera les sorties de tous les modules 127-136 pour composer la vue.
