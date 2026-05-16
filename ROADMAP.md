# ROADMAP — SEO Leoniedelacroix.com
> Mise à jour à chaque tâche complétée. Statuts : ✅ Fait · 🔄 En cours · ⏳ À faire · ↪ Supersédée

## PHASE 1 — Fondations & Audit (Semaine 1-2)
*Objectif : premier rapport d'audit fonctionnel sur leoniedelacroix.com*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 1 | Structure repo + `.env` + `.gitignore` + instructions agent (`AGENTS.md`, ex-`CLAUDE.md`) | 🟢 | ✅ | 2026-04-20 |
| 2 | Connexion Shopify Admin API GraphQL — lister tous les produits | 🟢 | ✅ | 2026-05-05 |
| 3 | Connexion Google Search Console API — export 90 jours | 🟡 | ✅ | 2026-05-05 |
| 4 | Connexion PageSpeed Insights API — score mobile/desktop par URL | 🟢 | ✅ | 2026-05-05 |
| 5 | Parser l'export CSV Screaming Frog | 🟢 | ✅ | 2026-05-05 |
| 6 | Détecteur : meta titles manquants / trop longs / trop courts | 🟢 | ✅ | 2026-05-05 |
| 7 | Détecteur : meta descriptions manquantes / dupliquées | 🟢 | ✅ | 2026-05-05 |
| 8 | Détecteur : images sans alt text | 🟢 | ✅ | 2026-05-05 |
| 9 | Détecteur : duplicate content `/collections/*/products/*` | 🟡 | ✅ | 2026-05-05 |
| 10 | Détecteur : redirections en chaîne + pages 404 | 🟡 | ✅ | 2026-05-05 |
| 11 | Calcul du score SEO global 0-100 pondéré par impact | 🟡 | ✅ | 2026-05-05 |
| 12 | Génération rapport Markdown horodaté dans `/reports/` | 🟢 | ✅ | 2026-05-05 |
| 13 | Initialisation base SQLite — état initial du site | 🟢 | ✅ | 2026-05-05 |
| 14 | Script `update_meta.py` avec `--dry-run` par défaut | 🟡 | ✅ | 2026-05-05 |
| 15 | Premier commit propre + README avec instructions d'usage | 🟢 | ✅ | 2026-05-05 |

---

## PHASE 2 — Recommandations & Application supervisée (Semaine 3-6)
*Objectif : corriger automatiquement les issues détectées, avec validation humaine*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 16 | Matrice ICE — priorisation issues par Impact/Coût/Effort | 🟡 | ✅ | 2026-05-05 |
| 17 | Générateur de meta titles optimisés par produit | 🟡 | ✅ | 2026-05-05 |
| 18 | Générateur de meta descriptions optimisées par produit | 🟡 | ✅ | 2026-05-05 |
| 19 | Générateur d'alt text intelligent basé sur nom produit + contexte | 🟡 | ✅ | 2026-05-05 |
| 20 | Script `update_meta.py --apply` — push meta vers Shopify (26 items) | 🟡 | ✅ | 2026-05-05 |
| 21 | Script `update_alt_text.py --apply` — push alt text vers Shopify (17 images) | 🟡 | ✅ | 2026-05-05 |
| 22 | Script `create_redirects.py` — import 301 en bulk depuis CSV validé | 🟡 | ✅ | 2026-05-05 |
| 23 | Structured data JSON-LD `Product` + `AggregateRating` via metafields | 🔴 | ✅ | 2026-05-05 |
| 24 | Système de rollback SQLite — logging ✅, commande CLI rollback manquante | 🔴 | ✅ | 2026-05-05 |
| 25 | Détecteur d'opportunités GSC — requêtes positions 11-20 à optimiser | 🟡 | ✅ | 2026-05-06 |
| 26 | Analyse concurrentielle longue traîne — requêtes niche petfood FR | 🔴 | ✅ | 2026-05-06 |
| 27 | Rapport comparaison avant/après par page (delta score SEO) | 🟡 | ✅ | 2026-05-06 |
| 28 | GitHub Actions cron hebdomadaire — audit auto + commit rapport | 🔴 | ✅ | 2026-05-06 |
| 29 | Alertes email — régression CWV, nouveaux 404, chute de position | 🔴 | ✅ | 2026-05-08 |

---

## PHASE 3 — Contenu SEO & Intelligence niche (Mois 2-4)
*Objectif : produire du contenu SEO contextualisé pour la niche petfood FR*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 30 | Générateur de briefs articles blog (H1/H2, mots-clés, angle E-E-A-T) | 🟡 | ✅ | 2026-05-08 |
| 31 | Réécriture descriptions produits longue traîne — ton premium petfood FR | 🔴 | ✅ | 2026-05-08 |
| 32 | Maillage interne automatique — détection opportunités liens blog → produits | 🔴 | ✅ | 2026-05-08 |
| 33 | Analyse sémantique fiches produits vs concurrents (Zooplus, Wanimo) | 🔴 | ✅ | 2026-05-08 |
| 34 | Générateur de FAQ structurée par catégorie produit | 🟡 | ✅ | 2026-05-08 |
| 35 | Détecteur de cannibalisation — pages en compétition sur un même mot-clé | 🔴 | ✅ | 2026-05-08 |
| 36 | Score E-E-A-T par page — auteur, sources, date, expertise vétérinaire | 🔴 | ✅ | 2026-05-08 |
| 37 | Générateur balises hreflang si extension BE/CH francophone | 🟡 | ✅ | 2026-05-08 |
| 38 | Rapport mensuel synthétique PDF — trafic, conversions, gains cumulés | 🟡 | ✅ | 2026-05-08 |
| 39 | Dashboard CLI interactif `rich` — vue temps réel santé SEO du site | 🟡 | ✅ | 2026-05-08 |

---

## PHASE 4 — Productisation & Monétisation (Mois 6)
*Objectif : transformer l'outil en produit vendable à d'autres boutiques Shopify*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 40 | Abstraction multi-boutiques — config par tenant dans YAML | 🔴 | ✅ | 2026-05-08 |
| 41 | Interface CLI universelle — sélecteur de secteur/niche au démarrage | 🟡 | ✅ | 2026-05-08 |
| 42 | Bibliothèque de règles métier par secteur (cosmétique, bébé, jardinage…) | 🔴 | ✅ | 2026-05-08 |
| 43 | Système de licences API key — authentification par boutique cliente | 🔴 | ✅ | 2026-05-08 |
| 44 | Packaging PyPI ou Docker — installation en une commande | 🔴 | ✅ | 2026-05-08 |

---

## PHASE 5 — App Shopify publique (Mois 12)
*Objectif : produit SaaS scalable sur le Shopify App Store*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 45 | OAuth Shopify — authentification marchands via App Store | 🔴 | ✅ | 2026-05-09 |
| 46 | Backend FastAPI — API REST entre l'app et le moteur Python | 🔴 | ✅ | 2026-05-09 |
| 47 | Frontend dashboard React — version UI du CLI | 🔴 | ✅ | 2026-05-09 |
| 48 | Système de pricing par plan (Free/Pro/Agency) | 🔴 | ✅ | 2026-05-10 |
| 49 | Soumission et validation Shopify App Store | 🔴 | ↪ Supersédée par tâche 75 | |
| 50 | Support + documentation utilisateur multilingue | 🟡 | ✅ | 2026-05-10 |

---

## PHASE 6 — Conformité App Store & Infrastructure async (Mois 13-14)
*Objectif : lever les 3 blockers critiques (GDPR, Billing, App Bridge) ET poser l'infrastructure async*
*Budget cible : ≤ 12 €/mois en ressources externes*
*Note : la tâche 55 (async queue) est un prérequis pour les jobs LLM de Phase 7*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 51 | GDPR mandatory webhooks — `customers/data_request`, `customers/redact`, `shop/redact` | 🔴 | ✅ | 2026-05-10 |
| 52 | Shopify Billing API — `appSubscriptionCreate` / `appSubscriptionCancel` (remplace HMAC license) | 🔴 | ✅ | 2026-05-10 |
| 53 | Privacy policy page + GDPR data export endpoint (`GET /api/gdpr/export`) | 🟡 | ✅ | 2026-05-10 |
| 54 | SQLite → Neon Postgres — migration multi-tenant (pools, connexions async) | 🔴 | ✅ | 2026-05-10 |
| 55 | Async job queue — Postgres-backed background jobs (audits, LLM batch, retry, rate-limit Shopify) | 🔴 | ✅ | 2026-05-10 |
| 56 | Scaffold Shopify App Remix — `shopify app create`, App Bridge v4 + Polaris + OAuth + sessions multi-tenant | 🔴 | ✅ | 2026-05-10 |
| 57 | Intégration Remix ↔ Python backend — proxy HTTP, auth partagée, Neon Postgres commun, décommission frontend/ | 🔴 | ✅ | 2026-05-10 |

---

## PHASE 7 — Moteur IA & Intelligence niche (Mois 15-17)
*Objectif : générations LLM utiles (pas vagues), Niche Intelligence concrète, observabilité dès le départ*
*Principe : prompts déterministes + validation humaine + fallbacks + coût LLM maîtrisé*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 58 | LLM provider abstraction — GPT-4o mini (primary) + Cloudflare Workers AI + Groq (fallbacks gratuits) | 🔴 | ✅ | 2026-05-11 |
| 59 | Templates de prompts externalisés en YAML (`config/prompts/`) — meta, alt, description, brief | 🟡 | ✅ | 2026-05-11 |
| 60 | Batch generation meta titles + descriptions via LLM — 100 produits en < 60 s via queue (tâche 55) | 🔴 | ✅ | 2026-05-11 |
| 61 | Validation + review mode — diff LLM vs Shopify actuel, approbation par batch, auto-approve opt-in | 🟡 | ✅ | 2026-05-11 |
| 62 | Niche Intelligence engine — détection clusters produits réels, saturation SERP, keyword gaps vs concurrents | 🔴 | ✅ | 2026-05-11 |
| 63 | Niche signals légers — Google Suggest + pytrends + Reddit (base de données keywords, valide avant Common Crawl) | 🟡 | ✅ | 2026-05-11 |
| 64 | Semantic clustering GSC — sentence-transformers + UMAP, regroupement requêtes par intent | 🔴 | ✅ | 2026-05-11 |
| 65 | Génération briefs pages/collections + articles blog via LLM (niche-aware, templates 59) | 🟡 | ✅ | 2026-05-11 |
| 66 | Bulk apply orchestrator — utilise queue 55, rate-limit Shopify, retry exponentiel, progress UI | 🟡 | ✅ | 2026-05-11 |
| 67 | spaCy NER — extraction entités produit (matières, certifications, origines) pour enrichissement contextuel | 🔴 | ✅ | 2026-05-11 |
| 68 | Observabilité — logs structurés JSON, métriques par tenant, coût LLM par requête, alertes seuil budget | 🟡 | ✅ | 2026-05-11 |

---

## PHASE 8 — Scale, Contenu & App Store final (Mois 18-24)
*Objectif : injection de contenu propre via Theme Extension, suivi ROI réel, multilinguisme IA, soumission finale*
*Common Crawl déféré ici : sources légères (tâche 63) d'abord, Web Graph seulement si gap avéré*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 69 | Theme App Extension — injection JSON-LD sans modifier `theme.liquid` (Shopify CLI, sandbox thème) | 🔴 | ✅ | 2026-05-11 |
| 70 | Semantic embeddings store — pgvector (Neon) pour similarité produit / requête GSC | 🔴 | ✅ | 2026-05-11 |
| 71 | Impact dashboard — vue ROI (clics gagnés × taux conv × panier moyen) par URL modifiée | 🟡 | ✅ | 2026-05-11 |
| 72 | Multilinguisme IA — génération meta EN/DE/NL via LLM pour expansion marché | 🟡 | ✅ | 2026-05-11 |
| 73 | GA4 Data API — corrélation trafic organique × conversions × recettes par tenant | 🔴 | ✅ | 2026-05-11 |
| 74 | Common Crawl / Web Graph — backlinks, graph liens concurrents, mentions marque non-linkées (après validation tâche 63) | 🔴 | ✅ | 2026-05-12 |
| 75 | Soumission App Store finale — après GDPR + Billing + App Bridge validés (tâches 51-57) | 🔴 | ✅ | 2026-05-12 |

> Préparation tâche 75 — 2026-05-12 : audit closure Vagues 3-5 terminé
> (`except Exception`, `datetime.utcnow`, `asyncio.get_event_loop`, cleanup `frontend/`,
> Dockerfile, tests cross-shop/token-store/observability, UI Remix App Store,
> i18n FR/EN, niches secondaires `template-demo`). Vérification :
> `pytest` 1033/1033 ✅, `ruff check .` ✅, `npm run typecheck` ✅, `npm run build` ✅.
>
> Clôture tâche 75 — 2026-05-12 : configuration locale de preview Shopify stabilisée
> (`shopify.app.local.toml`, `shopify.web.toml`, auth catch-all, fallback session storage,
> skip webhooks en localhost), checklist App Store documentée dans
> `docs/app-store-submission-checklist.md`. Le restant est manuel côté Partner Dashboard
> et nécessite une URL publique capable de recevoir les callbacks Shopify.

---

## PHASE 9 — Pilote marchand réel avant App Store
*Objectif : tester Léonie SEO sur la vraie boutique Shopify `leoniedelacroix.com`, récolter des retours terrain, adapter le produit, puis seulement lancer la publication App Store.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 76 | Préparer l'environnement pilote hors App Store — app non listée / install directe sur la boutique réelle, URLs publiques de test, secrets et callbacks actifs | 🔴 | ✅ | 2026-05-12 |
| 77 | Installer Léonie SEO sur la boutique Shopify réelle et valider OAuth, sessions persistantes, Billing désactivé ou mode test, webhooks GDPR/app uninstall | 🔴 | ✅ | 2026-05-15 |
| 78 | Activer un mode **pilot-safe** : analyses en lecture seule + dry-run obligatoire + confirmations explicites avant toute écriture Shopify | 🔴 | ✅ | 2026-05-15 |
| 79 | Tester les parcours métier réels sur `leoniedelacroix.com` — onboarding, audit, review IA, niche intelligence, jobs, privacy, billing/settings | 🔴 | ✅ | 2026-05-16 |
| 80 | Capturer les retours d'usage, bugs, incompréhensions UX, frictions de confiance et écarts entre promesse produit et réalité marchande | 🟡 | ✅ | 2026-05-16 |
| 81 | Corriger la vague pilote prioritaire — fiabilité, wording, états vides, feedbacks UX, garde-fous mutations, temps de réponse | 🔴 | ✅ | 2026-05-16 |
| 82 | Mesurer le pilote — qualité des recommandations, taux d'approbation, coûts LLM, stabilité des jobs, signaux SEO utiles | 🟡 | ✅ | 2026-05-16 |

> Clôture tâche 76 — 2026-05-12 : stratégie pilote séparée documentée
> (`docs/pilot-real-store-setup.md`), décision enregistrée dans `DECISIONS.md`,
> exemples d'environnement alignés sur une URL HTTPS publique et sessions persistantes,
> config locale `shopify.app.pilot.toml` prévue via `shopify app config link --config pilot`.
> La création de l'app pilote custom et la génération du lien d'installation restent
> des actions Shopify Partner manuelles à exécuter avant la tâche 77.
>
> Clôture tâche 77 — 2026-05-15 : app pilote installée sur la boutique réelle,
> OAuth embedded validé, sessions et appels internes Remix → Python validés,
> Billing désactivable par environnement, webhooks/GDPR présents, jobs audit/IA/apply
> visibles et scopés au shop, snapshot Shopify réel persistant fichier + DB,
> récupération des jobs `running` obsolètes, génération IA et prévisualisation
> dry-run vérifiées. Vérification locale : `ruff check .` ✅, `pytest`
> **1050 passed** ✅, `npm run typecheck` ✅, `npm run build` ✅.
>
> Clôture tâche 78 — 2026-05-15 : ajout d'un garde-fou central
> `LEONIE_PILOT_SAFE_MODE=true` qui bloque toute écriture live Shopify pendant
> le pilote, y compris les jobs `bulk_apply` et les mutations Billing. Hors mode
> pilot-safe, les écritures live exigent `confirm_live_write=true`; les dry-runs
> et lectures Shopify restent autorisés. Le Blueprint Render pilote active ce mode.
> Vérification locale : `ruff check .` ✅, `pytest` **1060 passed** ✅,
> `npm run typecheck` ✅, `npm run build` ✅.
>
> Démarrage tâche 79 — 2026-05-15 : ajout du plan de test réel
> `docs/pilot-real-store-test-plan.md` et du journal
> `docs/pilot-real-store-test-log.md`. Smoke checks publics réussis :
> web `/healthz` → `ok`, API `/health` → `status=ok` sans variable manquante,
> privacy GET → HTTP 200. Les parcours embedded Shopify Admin restent à
> exécuter avec une session marchand connectée.
>
> Clôture tâche 79 — 2026-05-16 : parcours embedded Shopify Admin validé
> sur la boutique réelle. Installation/session, navigation, Settings pilot-safe,
> audit, crawl produits/collections, niche clusters, génération de suggestions,
> approbation/rejet, dry-run preview, Billing bloqué et Privacy sont passés.
> Aucun bug bloquant signalé ; seul le libellé exact du mode pilot-safe dans
> Settings est à considérer comme retour UX pour la tâche 80. Décision : pass.
>
> Clôture tâche 80 — 2026-05-16 : retours pilote consolidés dans
> `docs/pilot-real-store-feedback.md`. Aucun bug bloquant ou friction majeure
> n'a été signalé. Une correction candidate est retenue pour la tâche 81 :
> rendre le libellé Settings `Mode pilot-safe actif` plus explicite et stable.
> Les IDs/counts manquants dans le journal sont classés comme amélioration de
> preuve de test, pas comme bug produit. Les manques GSC/GA4/PageSpeed restent
> volontairement différés en Phase 10.
>
> Clôture tâche 81 — 2026-05-16 : vague pilote prioritaire limitée au retour
> UX confirmé. La carte Settings affiche désormais `Mode pilot-safe actif`,
> un badge `Écritures live bloquées`, et une ligne indiquant que les dry-runs
> restent autorisés mais qu'aucune écriture Shopify live ne peut partir.
> Vérification : `npm run typecheck` ✅ et `npm run build` ✅ dans `shopify-app/`.
>
> Clôture tâche 82 — 2026-05-16 : mesure pilote consolidée dans
> `docs/pilot-real-store-measurement.md`. Décision : pass avec lacunes de
> mesure. Le pilote valide le workflow coeur, la sécurité dry-run/pilot-safe,
> Billing bloqué, Privacy, Niche clusters, génération IA, review et preview.
> Les valeurs exactes job IDs/durations, compteurs produits/collections,
> taux d'approbation et coût LLM devront être capturés lors du prochain pass,
> mais ne bloquent pas l'entrée en Phase 10.

---

## PHASE 10 — Parité scripts CLI → App Shopify
*Objectif : porter dans l'app embedded les fonctionnalités SEO encore disponibles uniquement dans `scripts/`, avec une UX marchand simple, des jobs async, du dry-run par défaut, et des garde-fous adaptés à l'App Store.*
*Principe : ne pas exposer chaque script tel quel. Transformer chaque capacité en workflow produit : diagnostic clair, prévisualisation, validation humaine, historique, rollback si écriture.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 83 | Connecter Google Search Console dans l'app — OAuth/consentement marchand, import query×page, état de fraîcheur des données et erreurs actionnables | 🔴 | ✅ | 2026-05-16 |
| 84 | Porter les opportunités GSC — positions 11-20, pages à CTR faible, estimation clics gagnables et priorisation par impact | 🟡 | ✅ | 2026-05-16 |
| 85 | Ajouter PageSpeed / Core Web Vitals — job par URL prioritaire, scores mobile/desktop, alertes de régression et recommandations non techniques | 🟡 | ✅ | 2026-05-16 |
| 86 | Ajouter un import crawl technique — upload CSV Screaming Frog ou crawl externe, détection 404, redirects, canonical, duplicates et chaînes de redirection | 🔴 | ⏳ | |
| 87 | Étendre l'audit UI — afficher toutes les issues `scripts/audit/detect_issues.py` dans l'app avec filtres, gravité, ressource touchée et cause lisible | 🟡 | ⏳ | |
| 88 | Ajouter la matrice ICE dans l'app — prioriser les corrections par impact, confiance et effort, avec tri marchand exploitable | 🟡 | ⏳ | |
| 89 | Porter l'analyse longue traîne — comparer catalogue, GSC et requêtes niche pour révéler les manques mots-clés par produit/collection | 🟡 | ⏳ | |
| 90 | Porter la détection cannibalisation — identifier les pages en compétition sur une même requête et proposer consolidation, canonical ou différenciation | 🔴 | ⏳ | |
| 91 | Ajouter le maillage interne — détecter opportunités blog/collection/produit, générer ancres suggérées et préparer une prévisualisation sans écriture | 🔴 | ⏳ | |
| 92 | Porter l'alt text IA — générer, revoir, approuver/rejeter et appliquer en dry-run les textes alternatifs images, avec limites qualité et accessibilité | 🟡 | ⏳ | |
| 93 | Porter la réécriture descriptions produits — générer descriptions longue traîne, comparer avec l'existant, review humaine et application batch sécurisée | 🔴 | ⏳ | |
| 94 | Ajouter les redirects 301 supervisés — import/proposition, validation collision/handle, dry-run, application explicite et rapport de résultat | 🔴 | ⏳ | |
| 95 | Finaliser le workflow JSON-LD — preview Organization/Product/Collection, activation Theme App Extension, validation schema et statut par ressource | 🟡 | ⏳ | |
| 96 | Ajouter un rollback marchand — historique des écritures Shopify, diff avant/après, revert par job/ressource/date, confirmations fortes | 🔴 | ⏳ | |
| 97 | Porter les rapports exportables — audit Markdown/PDF, delta avant-après, rapport mensuel, téléchargement depuis l'app et stockage par shop | 🟡 | ⏳ | |
| 98 | Ajouter dashboard impact + GA4 en UI complète — funnel organique, conversions, revenus, ROI par URL modifiée et configuration GA4 guidée | 🔴 | ⏳ | |
| 99 | Ajouter analyse sémantique et E-E-A-T — score contenu, entités manquantes, preuves de confiance, recommandations par page | 🟡 | ⏳ | |
| 100 | Ajouter génération FAQ et briefs blog — workflows de contenu niche-aware, review, export, et option d'application future via pages/blog Shopify | 🟡 | ⏳ | |
| 101 | Ajouter hreflang / international SEO — diagnostic marchés/langues, preview tags, garde-fous Markets Shopify et export technique | 🟡 | ⏳ | |
| 102 | Ajouter alertes marchand — email/in-app alerts pour CWV, 404, chute CTR/position, budget LLM et jobs en échec | 🟡 | ⏳ | |
| 103 | Nettoyer les scripts transitoires après parité — documenter ce qui reste CLI-only, supprimer doublons dangereux et figer les modules canoniques app | 🟡 | ⏳ | |

### Détail des objectifs Phase 10

- **83 GSC** : remplacer les imports locaux par une connexion pilotable depuis l'app, car les opportunités SEO deviennent beaucoup plus crédibles quand elles viennent des vraies requêtes marchand.
- **84 Opportunités GSC** : transformer les données GSC en actions simples : quelles pages optimiser maintenant, pourquoi, et quel gain potentiel viser.
- **85 PageSpeed / CWV** : intégrer la santé performance comme signal SEO visible, sans noyer le marchand dans des métriques Lighthouse brutes.
- **86 Crawl technique** : couvrir les problèmes que Shopify GraphQL ne voit pas bien : 404 publiques, canonical, redirects, duplicates réels et URLs orphelines.
- **87 Audit UI complet** : faire de l'app le lieu de lecture principal des problèmes SEO, au lieu de rapports CLI séparés.
- **88 ICE** : aider à décider quoi corriger en premier, surtout quand l'audit produit trop de recommandations.
- **89 Longue traîne** : trouver les requêtes réalistes que la boutique peut gagner à partir du catalogue réel et de la demande observée.
- **90 Cannibalisation** : éviter que plusieurs pages se concurrencent entre elles et diluent les signaux SEO.
- **91 Maillage interne** : transformer les contenus existants en leviers de ranking via liens contextuels contrôlés.
- **92 Alt text** : améliorer SEO image et accessibilité avec le même modèle de confiance que Review IA.
- **93 Descriptions produits** : étendre la valeur IA au contenu visible, avec un niveau de contrôle plus strict que les meta.
- **94 Redirects 301** : porter une fonctionnalité puissante mais risquée uniquement avec validations, dry-run et rollback.
- **95 JSON-LD** : rendre l'injection structurée auditable et activable proprement via extension Shopify, sans toucher `theme.liquid`.
- **96 Rollback** : donner une vraie confiance avant toute écriture réelle Shopify.
- **97 Rapports** : permettre au marchand de garder une trace exportable des audits, progrès et décisions.
- **98 GA4 / ROI** : relier les changements SEO aux sessions, conversions et revenus, pas seulement aux scores techniques.
- **99 Sémantique / E-E-A-T** : enrichir les pages avec les signaux de confiance et de pertinence qui manquent aujourd'hui dans l'UI.
- **100 FAQ / briefs** : convertir la niche intelligence en production de contenu exploitable.
- **101 Hreflang** : préparer l'expansion internationale sans générer de tags dangereux ou incohérents avec Shopify Markets.
- **102 Alertes** : rendre l'app proactive sur les régressions et les coûts.
- **103 Cleanup** : éviter deux sources de vérité entre CLI et app, en gardant les scripts utiles comme moteur ou outils opérateur seulement.

> Clôture tâche 83 — 2026-05-16 : ajout de la connexion Google Search Console
> côté app embedded. Le backend stocke les credentials Google OAuth chiffrés par
> shop (`google_tokens`), génère une URL de consentement signée, gère le callback
> Google, expose un statut GSC avec fraîcheur du dernier import, et lance un job
> `gsc_import` qui écrit les exports shop-scopés `gsc_performance.csv`,
> `gsc_query_page.csv` et `gsc_*.json` consommables par Niche Intelligence.
> L'Onboarding Shopify affiche maintenant l'état GSC, le lien de consentement
> et l'action `Importer 90 jours`. Configuration pilote documentée via
> `GOOGLE_OAUTH_CLIENT_CONFIG`, `GOOGLE_OAUTH_REDIRECT_URI` et
> `GOOGLE_OAUTH_STATE_SECRET`. Vérification : `ruff check .` ✅,
> `pytest` **1075 passed** ✅, `npm run typecheck` ✅, `npm run build` ✅.
>
> Clôture tâche 84 — 2026-05-16 : ajout de l'endpoint
> `GET /api/shops/{shop}/gsc/opportunities`, réutilisant la logique CLI
> `detect_gsc_opportunities` pour transformer les imports GSC en quick wins
> positions 11-20, pages à CTR faible, opportunités long terme, gains de clics
> estimés et priorisation par impact. La page Niche Shopify affiche désormais
> une carte `Opportunités GSC` avec résumé, gain estimé et tableau des pages à
> optimiser, ainsi qu'un état vide quand GSC n'est pas encore connecté/importé.
> Vérification : `ruff check .` ✅, `pytest` **1077 passed** ✅,
> `npm run typecheck` ✅, `npm run build` ✅.
>
> Clôture tâche 85 — 2026-05-16 : ajout du workflow PageSpeed / Core Web
> Vitals côté app embedded. Le backend expose `GET /api/shops/{shop}/pagespeed/status`
> et `POST /api/shops/{shop}/pagespeed/import`, lance le job async
> `pagespeed_import`, sélectionne des URLs prioritaires par shop, écrit les
> exports `pagespeed.csv` et `pagespeed_*.csv`, calcule les moyennes mobile /
> desktop, les alertes CWV, les régressions de score et des recommandations
> non techniques. L'Onboarding Shopify affiche l'état PageSpeed, le bouton
> `Analyser les URLs prioritaires`, les scores et les alertes principales ;
> Jobs SEO résume aussi les imports PageSpeed. Vérification : `ruff check .` ✅,
> `pytest` **1084 passed** ✅, `npm run typecheck` ✅, `npm run build` ✅.

---

## PHASE 11 — Soumission publique Shopify App Store
*Objectif : publier l'app seulement après le pilote réel et après la parité fonctionnelle prioritaire entre scripts CLI et app embedded.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 104 | Décision go/no-go App Store après pilote réel + parité fonctionnelle prioritaire + verrouillage du périmètre V1 public | 🔴 | ⏳ | |
| 105 | Finaliser la soumission publique Shopify App Store avec preuves issues du pilote, captures à jour et configuration de production figée | 🔴 | ⏳ | |
