# ARCHIVE — BRIEF INITIAL HISTORIQUE

> Document de cadrage initial, conservé pour traçabilité. Il ne représente plus l'état courant du projet.
> Pour Codex, utiliser `AGENTS.md`, `ROADMAP.md` et `PROGRESS.md` comme sources actives.

# PROJET SEO — Leoniedelacroix.com
## Briefing initial du projet

> Ce fichier contient TOUT le contexte du projet. Lis-le intégralement avant de faire quoi que ce soit.
> Il définit le business, les phases de travail, les 50 tâches, et les fichiers .md à créer.

---

## 1. CONTEXTE BUSINESS

- **Site** : https://leoniedelacroix.com (Shopify)
- **Secteur** : animalerie / petfood, produits pour chien et chat, marché français
- **Problème** : trafic organique faible, conversions quasi nulles en SEO
- **Positionnement visé** : niche premium/santé, "fabriqué en France", longue traîne
- **Concurrents principaux** : Zooplus (~50% du marché online FR), Maxi Zoo, Wanimo, Croquetteland, Ultra Premium Direct, Japhy
- **Objectif 12 mois** : 5 000 à 10 000 visites organiques/mois, 40 à 100 conversions/mois

---

## 2. CONTRAINTES

- **Niveau technique** : bases en CLI et Python — PAS développeur confirmé
- **Budget outils** : 0 à 50 €/mois maximum (scénario D, stack gratuite)
- **Langage** : Python 3.11+ uniquement
- **Interface** : CLI + rapports Markdown — pas de dashboard web, pas de Streamlit
- **Pilote IA actuel** : Codex (`AGENTS.md`) ; Claude Code est legacy

---

## 3. STACK TECHNIQUE IMPOSÉE (0 €/MOIS)

| Outil | Usage | Coût |
|---|---|---|
| Shopify Admin API GraphQL | Lire/modifier produits, meta, redirects, alt text | Gratuit |
| Google Search Console API | Requêtes, clics, impressions, positions, erreurs | Gratuit |
| PageSpeed Insights API | Core Web Vitals, scores mobile/desktop | Gratuit |
| Ahrefs Webmaster Tools API | Audit technique, backlinks, crawl 5000 URLs/mois | Gratuit |
| GA4 Data API | Trafic, conversions, canaux | Gratuit |
| Screaming Frog (free) | Crawl local <500 URLs, export CSV | Gratuit |
| SQLite | Historique modifications, rollback | Gratuit |
| GitHub Actions | Cron hebdomadaire, audit automatique | Gratuit |

---

## 4. RÈGLES DE TRAVAIL NON NÉGOCIABLES

1. **Plan avant code** — toute tâche >15 lignes commence par un plan validé
2. **Dry-run par défaut** — tout script Shopify nécessite `--apply` explicite
3. **Jamais de secrets en dur** — tout dans `.env`, jamais commité
4. **Français obligatoire** — commits, commentaires, rapports, docstrings
5. **Commits atomiques** — format `feat:`, `fix:`, `docs:`, `refactor:`
6. **Pas d'hallucination** — si une donnée manque, exception explicite
7. **Tests minimaux** — un test unitaire mocké par fonction qui touche une API
8. **Pas de réécriture de handles produits** — risque 404 massif, interdit pendant 3 mois

---

## 5. FORME FINALE DU PROJET

Un **CLI Python** qui tourne chaque semaine, audite leoniedelacroix.com via les APIs gratuites, génère un rapport Markdown avec les problèmes SEO priorisés et les corrections prêtes à appliquer. L'utilisateur valide, tape `--apply`, le site est mis à jour directement sur Shopify.

L'outil est **100% générique** dans son architecture : l'animalerie n'est que dans les fichiers de config YAML. Changer de secteur = remplacer deux fichiers. C'est le MVP d'une future app Shopify publique.

---

## 6. LES 5 PHASES DU PROJET

### PHASE 1 — Fondations & Audit (Semaine 1-2)
*Objectif : avoir un premier rapport d'audit fonctionnel sur leoniedelacroix.com*

| # | Tâche | Difficulté |
|---|---|---|
| 1 | Créer la structure de repo + `.env` + `.gitignore` + `AGENTS.md` | 🟢 Facile |
| 2 | Connexion Shopify Admin API GraphQL — lister tous les produits | 🟢 Facile |
| 3 | Connexion Google Search Console API — export 90 jours | 🟡 Moyen |
| 4 | Connexion PageSpeed Insights API — score mobile/desktop par URL | 🟢 Facile |
| 5 | Parser l'export CSV Screaming Frog | 🟢 Facile |
| 6 | Détecteur : meta titles manquants / trop longs / trop courts | 🟢 Facile |
| 7 | Détecteur : meta descriptions manquantes / dupliquées | 🟢 Facile |
| 8 | Détecteur : images sans alt text | 🟢 Facile |
| 9 | Détecteur : duplicate content `/collections/*/products/*` | 🟡 Moyen |
| 10 | Détecteur : redirections en chaîne + pages 404 | 🟡 Moyen |
| 11 | Calcul du score SEO global 0-100 pondéré par impact | 🟡 Moyen |
| 12 | Génération du rapport Markdown horodaté dans `/reports/` | 🟢 Facile |
| 13 | Initialisation base SQLite — état initial du site | 🟢 Facile |
| 14 | Script `update_meta.py` avec `--dry-run` par défaut | 🟡 Moyen |
| 15 | Premier commit propre + README avec instructions d'usage | 🟢 Facile |

---

### PHASE 2 — Recommandations & Application supervisée (Semaine 3-6)
*Objectif : pouvoir corriger automatiquement les issues détectées, avec validation humaine*

| # | Tâche | Difficulté |
|---|---|---|
| 16 | Matrice ICE — priorisation issues par Impact/Coût/Effort | 🟡 Moyen |
| 17 | Générateur de meta titles optimisés par produit | 🟡 Moyen |
| 18 | Générateur de meta descriptions optimisées par produit | 🟡 Moyen |
| 19 | Générateur d'alt text intelligent basé sur nom produit + contexte | 🟡 Moyen |
| 20 | Script `update_meta.py --apply` — push meta vers Shopify | 🟡 Moyen |
| 21 | Script `update_alt_text.py --apply` — push alt text vers Shopify | 🟡 Moyen |
| 22 | Script `create_redirects.py` — import 301 en bulk depuis CSV validé | 🟡 Moyen |
| 23 | Structured data JSON-LD `Product` + `AggregateRating` via metafields | 🔴 Difficile |
| 24 | Système de rollback SQLite — annuler toute modification appliquée | 🔴 Difficile |
| 25 | Détecteur d'opportunités GSC — requêtes positions 11-20 à optimiser | 🟡 Moyen |
| 26 | Analyse concurrentielle longue traîne — requêtes niche petfood FR | 🔴 Difficile |
| 27 | Rapport comparaison avant/après par page (delta score SEO) | 🟡 Moyen |
| 28 | GitHub Actions cron hebdomadaire — audit auto + commit rapport | 🔴 Difficile |
| 29 | Alertes email — régression CWV, nouveaux 404, chute de position | 🔴 Difficile |

---

### PHASE 3 — Contenu SEO & Intelligence niche (Mois 2-4)
*Objectif : produire du contenu SEO contextualisé pour la niche petfood FR*

| # | Tâche | Difficulté |
|---|---|---|
| 30 | Générateur de briefs articles blog (H1/H2, mots-clés, angle E-E-A-T) | 🟡 Moyen |
| 31 | Réécriture descriptions produits longue traîne — ton premium petfood FR | 🔴 Difficile |
| 32 | Maillage interne automatique — détection opportunités liens blog → produits | 🔴 Difficile |
| 33 | Analyse sémantique fiches produits vs concurrents (Zooplus, Wanimo) | 🔴 Difficile |
| 34 | Générateur de FAQ structurée par catégorie produit | 🟡 Moyen |
| 35 | Détecteur de cannibalisation — pages en compétition sur un même mot-clé | 🔴 Difficile |
| 36 | Score E-E-A-T par page — auteur, sources, date, expertise vétérinaire | 🔴 Difficile |
| 37 | Générateur balises hreflang si extension BE/CH francophone | 🟡 Moyen |
| 38 | Rapport mensuel synthétique PDF — trafic, conversions, gains cumulés | 🟡 Moyen |
| 39 | Dashboard CLI interactif `rich` — vue temps réel santé SEO du site | 🟡 Moyen |

---

### PHASE 4 — Productisation & Monétisation (Mois 6)
*Objectif : transformer l'outil en produit vendable à d'autres boutiques Shopify*

| # | Tâche | Difficulté |
|---|---|---|
| 40 | Abstraction multi-boutiques — config par tenant dans YAML | 🔴 Difficile |
| 41 | Interface CLI universelle — sélecteur de secteur/niche au démarrage | 🟡 Moyen |
| 42 | Bibliothèque de règles métier par secteur (cosmétique, bébé, jardinage…) | 🔴 Difficile |
| 43 | Système de licences API key — authentification par boutique cliente | 🔴 Difficile |
| 44 | Packaging PyPI ou Docker — installation en une commande | 🔴 Difficile |

---

### PHASE 5 — App Shopify publique (Mois 12)
*Objectif : produit SaaS scalable sur le Shopify App Store*

| # | Tâche | Difficulté |
|---|---|---|
| 45 | OAuth Shopify — authentification marchands via App Store | 🔴 Difficile |
| 46 | Backend FastAPI — API REST entre l'app et le moteur Python | 🔴 Difficile |
| 47 | Frontend dashboard React — version UI du CLI | 🔴 Difficile |
| 48 | Système de pricing par plan (Free/Pro/Agency) | 🔴 Difficile |
| 49 | Soumission et validation Shopify App Store | 🔴 Difficile |
| 50 | Support + documentation utilisateur multilingue | 🟡 Moyen |

---

## 7. VUE MACRO

| Phase | Tâches | Horizon | Valeur produite |
|---|---|---|---|
| 1 — Audit | 1 → 15 | Semaine 1-2 | Outil personnel fonctionnel |
| 2 — Application | 16 → 29 | Semaine 3-6 | Outil automatisé sur le site |
| 3 — Contenu | 30 → 39 | Mois 2-4 | Avantage concurrentiel niche |
| 4 — Productisation | 40 → 44 | Mois 6 | Outil vendable à d'autres |
| 5 — App Shopify | 45 → 50 | Mois 12 | Produit SaaS scalable |

---

## 8. FICHIERS .MD À CRÉER

### `AGENTS.md` — Les règles actives Codex *(Jour 1, priorité absolue)*
Lu automatiquement par Codex dans le projet. Contient les règles de comportement, la stack technique, l'arborescence du repo, les commandes fréquentes. Sans lui, le contexte du projet doit être reconstruit à chaque session.
**Contenu** : règles des sections 2, 3, 4 de ce document + arborescence repo + commandes CLI.

---

### `ROADMAP.md` — La mémoire vivante du projet *(Jour 1)*
Les tâches organisées par phase avec statut ✅ / 🔄 / ⏳. Codex s'y réfère pour savoir où il en est et met à jour le statut après chaque tâche validée.
**Contenu** : tableau des 5 phases avec cases à cocher, date de complétion, notes.

---

### `README.md` — La notice utilisateur *(Jour 1)*
Documentation d'usage pour l'utilisateur dans 6 mois (ou un client). Installation, prérequis, commandes, exemples. Zéro jargon technique.
**Contenu** : installation Python + deps, configuration `.env`, liste des commandes avec exemples, FAQ.

---

### `DECISIONS.md` — Le journal des choix techniques *(Semaine 1)*
Chaque choix structurant est documenté ici avec date et raisonnement. Évite de refaire les mêmes débats à chaque session.
**Exemples** : "Pourquoi SQLite plutôt que Postgres", "Pourquoi dry-run par défaut", "Pourquoi Screaming Frog Free et non un crawler custom".

---

### `CONTEXT.md` — La fiche marché *(Semaine 1)*
Tout ce que Codex doit savoir sur le business sans que l'utilisateur le répète : concurrents, positionnement, personas, saisonnalité petfood, historique du site, mots-clés stratégiques.
**Contenu** : fiche concurrents (Zooplus, Wanimo, etc.), liste mots-clés prioritaires par catégorie, règles E-E-A-T secteur vétérinaire.

---

### `ALERTS.md` — Le registre des anomalies *(Mois 1)*
Chaque alerte déclenchée par le monitoring est loggée ici : date, page concernée, type d'issue, action prise, résolution.
**Format** : tableau chronologique, alimenté automatiquement par le script d'alertes (tâche 29).

---

### `skills/seo-technique.md` — Règles d'audit SEO *(Semaine 1)*
Définit les seuils et règles de scoring : longueur acceptable d'un title (50-60 chars), d'une meta description (120-155 chars), score CWV acceptable, règles de canonicalisation Shopify.
**Utilisé par** : tâches 6, 7, 8, 9, 10, 11.

---

### `skills/shopify-graphql.md` — Patterns API Shopify *(Semaine 1)*
Catalogue des mutations GraphQL sûres à utiliser, avec exemples de requêtes validées, limites de rate limiting (2 req/s REST, 1000 pts/min GraphQL), et liste des opérations interdites (modification de handles).
**Utilisé par** : tâches 2, 20, 21, 22, 23.

---

### `skills/petfood-niche.md` — Intelligence sectorielle *(Semaine 2)*
Base de connaissance métier : liste de mots-clés longue traîne par catégorie (croquettes chien/chat, friandises, accessoires), règles de contenu E-E-A-T pour le secteur quasi-YMYL, positionnement vs Zooplus/Wanimo.
**Utilisé par** : tâches 17, 18, 19, 26, 30, 31, 33.

---

### `skills/content-fr.md` — Règles rédactionnelles *(Mois 1)*
Ton éditorial, règles de style pour le marché français, structure des descriptions produits premium, règles de maillage interne, contraintes légales (allégations nutrition animale).
**Utilisé par** : tâches 17, 18, 30, 31, 34.

---

## 9. ORDRE DE CRÉATION DES FICHIERS .MD

```
Jour 1      → AGENTS.md + README.md + ROADMAP.md
Semaine 1   → DECISIONS.md + CONTEXT.md
              + skills/seo-technique.md + skills/shopify-graphql.md
Semaine 2   → skills/petfood-niche.md
Mois 1      → ALERTS.md + skills/content-fr.md
```

---

## 10. STRUCTURE DU REPO CIBLE

```
leonie-seo/
├── AGENTS.md                        ← lu automatiquement par Codex
├── ROADMAP.md                       ← 50 tâches avec statuts
├── README.md                        ← notice utilisateur
├── DECISIONS.md                     ← journal des choix techniques
├── CONTEXT.md                       ← fiche marché + concurrents
├── ALERTS.md                        ← registre des anomalies
├── .env                             ← secrets (jamais commité)
├── .env.example                     ← template secrets
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── config/
│   ├── keywords.yaml                ← mots-clés cibles par thème
│   └── seo_rules.yaml               ← règles métier (longueurs, seuils)
├── skills/
│   ├── seo-technique.md
│   ├── shopify-graphql.md
│   ├── petfood-niche.md
│   └── content-fr.md
├── scripts/
│   ├── audit/                       ← lecture seule, sans risque
│   │   ├── crawl_shopify.py
│   │   ├── fetch_gsc.py
│   │   ├── fetch_pagespeed.py
│   │   └── detect_issues.py
│   ├── apply/                       ← écriture Shopify, dry-run par défaut
│   │   ├── update_meta.py
│   │   ├── update_alt_text.py
│   │   ├── create_redirects.py
│   │   └── add_schema.py
│   └── report/
│       └── generate_report.py
├── data/
│   ├── raw/                         ← exports bruts (gitignored)
│   └── history.db                   ← SQLite
├── reports/                         ← rapports Markdown horodatés
│   └── YYYY-MM-DD/
└── .github/
    └── workflows/
        └── weekly_audit.yml
```

---

## 11. ARCHIVE — anciennes best practices Claude Code

> Ces règles sont conservées comme historique de la méthode Claude Code utilisée au démarrage. Pour Codex, ne pas les appliquer telles quelles : les règles actives sont dans `AGENTS.md`.
> Adaptation Codex : pas de `/compact`, pas de `/clear`, pas de `/review`, pas de `!<cmd>` ; utiliser les outils Codex disponibles, `update_plan`, les validations shell, et les fichiers durables `PROGRESS.md` / `ROADMAP.md`.

---

### 11.1 `AGENTS.md` — Règles de structure Codex

- **Court et dense** — Codex lit `AGENTS.md`, qui doit rester centré sur les règles qui changent réellement le comportement
- **Court et dense** : uniquement ce qui change le comportement, pas la documentation
- **Commité dans Git** — il s'applique à toute l'équipe (ou à toi dans 6 mois)
- **Nested `AGENTS.md`** possibles dans les sous-dossiers si une zone a des règles spécifiques
- **Chaque bug récurrent → une règle ajoutée immédiatement dans `AGENTS.md` ou dans un skill/fichier projet pertinent** : ne jamais corriger une instance, corriger le système

---

### 11.2 GESTION DU CONTEXTE — version Codex

Codex Desktop compacte automatiquement le contexte quand nécessaire. Ne pas utiliser les anciennes commandes Claude Code `/compact` et `/clear`.

Règle active : écrire l'état important dans `PROGRESS.md` avant toute longue séquence, relire `PROGRESS.md` + `ROADMAP.md` après reprise/compaction, et s'appuyer sur les fichiers du repo plutôt que sur la mémoire de conversation.

---

### 11.3 WORKFLOW — Explore → Plan → Implement

Ne jamais démarrer une tâche sans ce séquençage :

1. **Explore** : "Lis les fichiers concernés et dis-moi ce que tu comprends"
2. **Plan** : "Fais un plan en bullet points, ne code pas encore"
3. **Review** : Je valide le plan (ou je le corrige)
4. **Implement** : "Exécute le plan approuvé, étape par étape"
5. **Verify** : "Lance les tests et prouve-moi que ça marche"

Commandes utiles pour forcer ce workflow :
- `"Before you write code, make a plan"` — dans chaque prompt de tâche complexe
- `"Explore then → plan → implement"` — raccourci pour le séquençage complet
- `"Prove to me this works"` — force Codex à vérifier lui-même avant de valider

---

### 11.4 SUBAGENTS — Délégation pour les tâches isolées

Pour les tâches complexes, utilise le pattern **Writer/Reviewer** avec un contexte frais :

```bash
# Exemple : Codex écrit le code, puis applique les critères de review sécurité
"Tu viens d'écrire le script update_meta.py.
Fais une review sécurité de ce code avec les critères `shopify-safety` :
vérifie les injections, les secrets exposés, les appels API non bornés."
```

Les profils Codex actifs vivent dans `.codex/agents/` :
- `shopify-safety.toml` — vérifie qu'aucune mutation dangereuse n'est générée (handles, publications)
- `python-quality.toml` — vérifie style, tests, docstrings avant chaque commit

---

### 11.5 HOOKS — Automatisation avant/après actions

Codex peut utiliser des hooks configurés dans `.codex/hooks.json` quand ils existent et sont approuvés :

```bash
# Hook pre-edit : vérifier que le fichier cible n'est pas dans la liste interdite
# Hook post-edit : lancer les tests unitaires automatiquement
# Hook pre-commit : scanner les secrets avec detect-secrets
```

Règle absolue : **tout script `apply/` déclenche un hook de confirmation** avant exécution réelle.

---

### 11.6 AUTOMATISATION CI/CD

Pour le cron GitHub Actions, utiliser directement les commandes du projet plutôt qu'un prompt Claude headless :

```bash
leonie-seo audit crawl
leonie-seo audit gsc
leonie-seo audit pagespeed
leonie-seo audit detect
leonie-seo report weekly
```

Les secrets restent dans GitHub Actions secrets ; jamais de permissions larges ni d'écriture Shopify sans `--apply` explicite.

---

### 11.7 PATTERN PRD — Avant chaque phase majeure

Avant de démarrer une nouvelle phase, crée un mini-fichier PRD (Product Requirements Doc) :

```markdown
# PRD — Phase 2 : Application supervisée
## Mission
Permettre la correction automatique des issues SEO avec validation humaine.
## Périmètre
- Scripts : update_meta.py, update_alt_text.py, create_redirects.py
- Hors périmètre : structured data (phase 3), handles produits (jamais)
## Critères de succès
- dry-run produit un diff lisible en <5 secondes
- --apply loggue chaque modification dans history.db
- Rollback possible en une commande
## Contraintes
- Aucune modification sans token Shopify valide en .env
- Tests unitaires obligatoires avant merge
```

---

### 11.8 GESTION DES ERREURS — Corriger le système, pas l'instance

> "Every bug is a system failure, not a one-time mistake." — Boris Cherny

Quand une erreur se répète :
1. ❌ Ne pas juste corriger le bug
2. ✅ Ajouter la règle dans `AGENTS.md` ou le skill/fichier concerné
3. ✅ Ajouter un test qui aurait détecté l'erreur

Quand Codex produit une correction médiocre :
- Dire : *"En tenant compte de tout ce que tu sais maintenant, jette cette solution et implémente l'approche élégante"*
- Ne jamais accepter un fix bancal par confort de ne pas recommencer

---

### 11.9 SÉCURITÉ — Règles non négociables

- **Auditer chaque MCP server** avant installation (655 MCP malveillants identifiés en 2026 — source FlorianBruniaux)
- **Jamais de secrets dans les fichiers commités** — `.env` reste gitignored
- **Revue manuelle obligatoire** pour tout ce qui touche auth, access control, ou API write
- **`detect-secrets`** en pre-commit hook sur tout le repo
- Les assistants IA peuvent générer des erreurs logiques — **toujours vérifier la logique métier** des scripts `apply/`

---

### 11.10 COMMANDES CLAUDE OBSOLÈTES

| Ancienne commande | Remplacement Codex |
|---|---|
| `/compact` | Compaction automatique Codex + notes durables dans `PROGRESS.md` |
| `/clear` | Nouvelle session si nécessaire + relecture `AGENTS.md`, `PROGRESS.md`, `ROADMAP.md` |
| `/review` | Demander explicitement une review ; Codex adopte alors la posture code-review |
| `/plan` | Demander un plan ; Codex utilise `update_plan` si utile |
| `!<cmd>` | Codex lance les commandes via ses outils shell avec sandbox/approbations |

---

## 12. TA PREMIÈRE TÂCHE

1. Lis ce fichier en entier — sections 1 à 11 — et confirme que tu as tout intégré.
2. Applique immédiatement la règle 11.3 (Explore → Plan → Implement) pour la suite.
3. Crée dans l'ordre : `AGENTS.md`, `README.md`, `ROADMAP.md` (50 tâches, statut ⏳).
4. Crée `.codex/agents/shopify-safety.toml` et `.codex/agents/python-quality.toml` (profils de review de base).
5. Pose-moi uniquement les questions bloquantes pour la tâche n°1 (credentials, versions).
6. Propose un plan pour la Phase 1 complète (tâches 1 à 15) — **aucun code avant validation.**
