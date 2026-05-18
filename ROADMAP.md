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
| 86 | Ajouter un import crawl technique — upload CSV Screaming Frog ou crawl externe, détection 404, redirects, canonical, duplicates et chaînes de redirection | 🔴 | ✅ | 2026-05-16 |
| 87 | Étendre l'audit UI — afficher toutes les issues `scripts/audit/detect_issues.py` dans l'app avec filtres, gravité, ressource touchée et cause lisible | 🟡 | ✅ | 2026-05-16 |
| 88 | Ajouter la matrice ICE dans l'app — prioriser les corrections par impact, confiance et effort, avec tri marchand exploitable | 🟡 | ✅ | 2026-05-16 |
| 89 | Porter l'analyse longue traîne — comparer catalogue, GSC et requêtes niche pour révéler les manques mots-clés par produit/collection | 🟡 | ✅ | 2026-05-16 |
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

## PHASE 11 — Différenciation GEO : AI Search Readiness & Revenue-Aware Shopify Intelligence
*Objectif : transformer Léonie SEO en assistant GEO Shopify-native capable d'identifier quelles pages, produits et collections sont les plus importants à optimiser pour Google, ChatGPT, Perplexity, Gemini et les moteurs IA, en priorisant selon la complétude factuelle, le potentiel business, le risque SEO, le stock, la marge et la preuve d'impact.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 106 | GEO Product Facts Layer — structurer les faits produits fiables utiles aux IA, JSON-LD, FAQ, descriptions, snippets et recommandations ; détecter faits confirmés/manquants, suggestions à vérifier et score de complétude factuelle | 🔴 | ✅ | 2026-05-18 |
| 107 | AI Search Readiness Score — calculer un score GEO par produit, collection et boutique à partir des faits produits, schema, FAQ, requêtes conversationnelles, preuves de confiance, maillage, stock, performance et crawlabilité | 🔴 | ✅ | 2026-05-18 |
| 108 | Revenue-Aware GEO Prioritization — croiser GSC, GA4, Shopify, stock, marge, conversion, panier moyen, score GEO, risque et effort pour prioriser les actions les plus utiles business et AI Search | 🔴 | ✅ | 2026-05-18 |
| 109 | Weekly GEO Action Assistant — agréger score GEO, priorisation revenue-aware, GSC, GA4, PageSpeed, crawl, stock, saisonnalité et ledger pour afficher seulement 3 actions GEO prioritaires par semaine avec gain potentiel, effort, risque et preview | 🟡 | ✅ | 2026-05-18 |
| 110 | GEO Impact Ledger — historiser chaque optimisation GEO avec snapshot avant/après, faits ajoutés, FAQ, JSON-LD, requêtes conversationnelles ciblées, source, utilisateur, job ID, métriques GSC/GA4 avant puis après 7/30/60 jours et impact estimé vs observé | 🔴 | ✅ | 2026-05-18 |
| 111 | GEO Risk Guard — protéger les pages SEO ou business déjà performantes, éviter les sur-optimisations IA, bloquer les écritures automatiques sauf confirmation forte et propager la protection aux workflows contenu, FAQ, JSON-LD, maillage, collections et redirects | 🟡 | ✅ | 2026-05-18 |
| 112 | AI Search Collection Builder — détecter les opportunités de collections Shopify adaptées aux intentions conversationnelles via catalogue, tags, types produits, requêtes GSC, signaux niche, embeddings et stock ; proposer nom, handle, H1, metas, description, FAQ, produits et dry-run avant création | 🔴 | ✅ | 2026-05-18 |
| 113 | FAQ & Answer Block Generator — générer des FAQ et blocs de réponses orientés moteurs IA à partir des faits produits confirmés, avec review humaine, séparation fait confirmé / suggestion à vérifier et option d'application future sur pages produits, collections ou blogs Shopify | 🟡 | ✅ | 2026-05-18 |
| 114 | llms.txt & AI Crawlability Advisor — préparer un fichier de guidage IA listant les pages, collections, politiques et contenus clés de la boutique, recommander les pages à inclure/exclure et auditer la lisibilité IA sans promettre de ranking ou citation garantie | 🟡 | ✅ | 2026-05-18 |
| 115 | AI Answer Competitor Monitor — comparer les concurrents visibles sur les requêtes conversationnelles prioritaires, d'abord via SERP ou import manuel, puis analyser contenus, prix, avis, FAQ, schema, preuves, angle IA et recommander collection, enrichissement produit, FAQ ou maillage sans copier | 🔴 | ✅ | 2026-05-18 |

### Détail des objectifs Phase 11

1. **106 GEO Product Facts Layer**
   - Créer une base de faits produits fiable pour nourrir le GEO sans hallucination.
   - Extraire depuis Shopify : matières, dimensions, poids, compatibilités, usages, entretien, origine, garanties, livraison, retours, certifications, bénéfices, limites, type d'animal, taille recommandée et problème résolu.
   - Output attendu : fiche faits produit, faits confirmés, faits manquants, suggestions à vérifier, score de complétude et recommandations.
   - Garde-fous : ne jamais inventer origine, matière, certification, garantie ou preuve ; séparer explicitement fait confirmé / suggestion marchande à valider.

2. **107 AI Search Readiness Score**
   - Créer un score boutique / collection / produit.
   - Composants : faits produits complets, JSON-LD, FAQ conversationnelle, alignement requêtes longues, preuves de confiance, maillage interne, stock, performance et crawlabilité.
   - Output attendu : score 0-100, sous-scores, raisons lisibles et actions d'amélioration.
   - Garde-fous : présenter le score comme une readiness interne, pas comme une garantie de visibilité dans ChatGPT, Perplexity, Gemini ou Google AI Overviews.

3. **108 Revenue-Aware GEO Prioritization**
   - Classer les actions GEO par impact business probable.
   - Croiser GSC, GA4, Shopify, stock, statut produit, variantes, panier moyen, marge si disponible, score GEO, risque et effort.
   - Output attendu : tableau pages/actions, gain estimé, effort, risque, raison lisible et confiance faible/moyenne/forte.
   - Garde-fous : fallback GSC + Shopify + panier moyen global si GA4 ou marge manque, et aucune estimation présentée comme une promesse.

4. **109 Weekly GEO Action Assistant**
   - Réduire la complexité à 3 décisions GEO actionnables par semaine.
   - Agréger score GEO, priorisation revenue-aware, opportunités GSC, Risk Guard, PageSpeed, crawl, stock, saisonnalité et ledger.
   - Output attendu : carte dashboard avec 3 actions, gain potentiel, effort, risque, preview et raison simple.
   - Garde-fous : ne pas répéter des recommandations faibles, masquer l'incertain et privilégier l'impact business au volume d'erreurs.

5. **110 GEO Impact Ledger**
   - Transformer l'app en système de preuve pour les optimisations GEO.
   - Enregistrer état avant/après, faits produits ajoutés, FAQ, schema JSON-LD, requêtes conversationnelles ciblées, utilisateur, job ID, source de recommandation, métriques GSC/GA4 et mesures après 7/30/60 jours.
   - Output attendu : journal chronologique, impact estimé vs observé, statut positif/neutre/négatif/inconclusif et rollback si possible.
   - Garde-fous : snapshot obligatoire, distinction corrélation/causalité et état “impact non encore mesurable”.

6. **111 GEO Risk Guard**
   - Éviter qu'une optimisation GEO abîme une page qui performe déjà en SEO ou en revenu.
   - Détecter top trafic, CTR supérieur à la moyenne, revenus organiques élevés, conversion élevée, stabilité 30/60/90 jours et pages déjà suffisamment claires pour l'IA.
   - Output attendu : pages protégées, raison, niveau de risque et recommandation.
   - Garde-fous : blocage des modifications automatiques, confirmation forte avant écriture Shopify et protection appliquée aux workflows contenu, FAQ, JSON-LD, maillage, collections et redirects.

7. **112 AI Search Collection Builder**
   - Proposer des collections Shopify pensées pour les intentions conversationnelles, pas seulement pour les mots-clés courts.
   - Utiliser catalogue, tags, types produits, requêtes GSC, signaux niche, embeddings produit/requête et stock.
   - Output attendu : cartes de collections suggérées avec preview nom, handle, H1, metas, description, FAQ, produits inclus, liens internes et estimation d'opportunité.
   - Garde-fous : éviter collections trop pauvres, cannibales ou déjà existantes, et ne jamais publier sans validation.

8. **113 FAQ & Answer Block Generator**
   - Transformer les faits produits en réponses exploitables par les moteurs IA et compréhensibles par les clients.
   - Générer des questions/réponses sur usage, taille, matière, compatibilité, entretien, différence avec alternatives, livraison, retours et garanties.
   - Output attendu : FAQ par produit/collection, blocs de réponse courts, sources factuelles utilisées, preview et review humaine.
   - Garde-fous : ne pas inventer de faits, ne pas surcharger les pages et permettre l'export sans écriture Shopify.

9. **114 llms.txt & AI Crawlability Advisor**
   - Préparer une couche de guidage IA sans vendre de promesse irréaliste.
   - Lister les pages, collections, politiques, guides et contenus clés à rendre facilement découvrables par les moteurs IA.
   - Ajouter recommandations d'inclusion/exclusion et audit de lisibilité.
   - Output attendu : preview `llms.txt`, pages incluses/exclues, raisons et alertes de pages faibles.
   - Garde-fous : présenter `llms.txt` comme un fichier de guidage émergent, pas comme un standard garanti ni un levier de ranking prouvé.

10. **115 AI Answer Competitor Monitor**
   - Comprendre pourquoi des concurrents sont plus recommandables ou visibles sur des requêtes prioritaires.
   - Utiliser suivi limité des requêtes GSC/conversationnelles prioritaires, import manuel ou SERP au départ, classification des pages et comparaison contenu/prix/avis/FAQ/schema/preuves/angle IA.
   - Output attendu : tableau par requête, concurrents visibles, raisons probables et action recommandée.
   - Garde-fous : plafonner les requêtes, éviter le scraping agressif, proposer un import CSV au départ et interdire la copie de contenu.

### Priorité produit recommandée

1. **106 GEO Product Facts Layer** — Socle indispensable : sans faits fiables, le GEO risque de générer du contenu vague ou halluciné.
2. **107 AI Search Readiness Score** — Rend le positionnement GEO visible et compréhensible dans l'UI.
3. **108 Revenue-Aware GEO Prioritization** — Connecte le GEO au business Shopify : revenu, stock, marge, conversion et risque.
4. **109 Weekly GEO Action Assistant** — Transforme la complexité en 3 actions simples par semaine pour marchands non techniques.
5. **110 GEO Impact Ledger** — Prouve l'impact, prépare le rollback et évite les promesses impossibles à démontrer.
6. **111 GEO Risk Guard** — Protège les pages performantes contre les optimisations IA excessives.
7. **112 AI Search Collection Builder** — Très Shopify-native et différenciant pour capter les intentions conversationnelles.
8. **113 FAQ & Answer Block Generator** — Génère des contenus très utiles aux moteurs IA, mais dépend de la qualité du Facts Layer.
9. **114 llms.txt & AI Crawlability Advisor** — Signal GEO intéressant, à présenter prudemment comme guidage IA.
10. **115 AI Answer Competitor Monitor** — Différenciant mais coûteux ; à garder après validation marché ou avec import manuel au départ.

---

## PHASE 11.5 — GEO Impact Validation & Retention Loop
*Objectif : mesurer l'impact réel des optimisations GEO/SEO appliquées, suivre la progression dans le temps, comparer les pages modifiées à des pages témoins et afficher une courbe de progression claire pour prouver la valeur de l'app au marchand pendant la période de validation.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 116 | Optimization Snapshot — enregistrer l'état avant chaque modification : score GEO/SEO, contenu, facts, FAQ, JSON-LD, GSC, GA4, Shopify, stock, prix et statut produit | 🔴 | ✅ | 2026-05-18 |
| 117 | Optimization Event Tracking — créer un événement traçable pour chaque action appliquée avec page, type d'action, date, utilisateur, job ID, score avant/après, hypothèse et statut | 🟡 | ✅ | 2026-05-18 |
| 118 | Control Group Builder — sélectionner des pages témoins similaires non modifiées pour comparer l'évolution des pages optimisées à une baseline crédible | 🔴 | ✅ | 2026-05-18 |
| 119 | Validation Timeline J+7/J+30/J+60/J+90 — planifier automatiquement les fenêtres de mesure et afficher au marchand quand les premiers signaux et conclusions seront disponibles | 🟡 | ✅ | 2026-05-18 |
| 120 | Progress Curve Dashboard — afficher les courbes score GEO, impressions, clics, CTR, position, sessions organiques, conversions, revenu et impact estimé vs observé | 🔴 | ✅ | 2026-05-19 |
| 121 | Impact Confidence Score — calculer un score de confiance de l'impact selon durée, volume, groupe contrôle, stabilité stock/prix et cohérence GSC/GA4 | 🔴 | ✅ | 2026-05-19 |
| 122 | Before/After Impact Report — générer un rapport lisible par page/action avec score avant/après, métriques GSC/GA4, verdict et recommandations suivantes | 🟡 | ✅ | 2026-05-19 |
| 123 | Retention Milestones — afficher des jalons d'abonnement J+7, J+30, J+60, J+90 pour montrer pourquoi l'app doit rester active pendant la validation | 🟡 | ⏳ | |
| 124 | Win/Neutral/Risk Detection — classer automatiquement chaque optimisation en impact positif probable, neutre, négatif possible ou inconclusif | 🟡 | ⏳ | |
| 125 | Next Best Action Loop — transformer les résultats validés en nouvelles recommandations : répliquer, ajuster, attendre ou rollback | 🔴 | ⏳ | |

### Détail des objectifs Phase 11.5

1. **116 Optimization Snapshot**
   - Enregistrer l’état exact avant chaque modification.
   - Capturer score GEO avant, score SEO avant, contenu avant, facts produits avant, FAQ avant, JSON-LD avant, métriques GSC, métriques GA4, stock, prix, statut produit et contexte saisonnier.
   - Output attendu : snapshot horodaté par page/action, exploitable pour comparaison, rollback et preuve d’impact.
   - Garde-fous : aucun impact ne doit être calculé sans snapshot initial.

2. **117 Optimization Event Tracking**
   - Créer un événement traçable pour chaque optimisation appliquée.
   - Stocker page, action, type d’action, date, utilisateur, job ID, score avant/après, hypothèse d’impact, statut, source de recommandation et éventuel rollback.
   - Output attendu : journal d’événements d’optimisation relié aux jobs et aux pages.
   - Garde-fous : distinguer recommandation, preview, dry-run, application réelle et rollback.

3. **118 Control Group Builder**
   - Sélectionner des pages témoins similaires non modifiées.
   - Matcher par type de page, catégorie, trafic initial, impressions GSC, prix, stock, score GEO initial, saisonnalité et position moyenne.
   - Output attendu : groupe test vs groupe contrôle pour chaque vague d’optimisation.
   - Garde-fous : ne pas présenter une comparaison comme causale si les pages ne sont pas suffisamment comparables.

4. **119 Validation Timeline J+7/J+30/J+60/J+90**
   - Planifier automatiquement les fenêtres de mesure.
   - J+0 : modification appliquée.
   - J+7 : premiers signaux faibles.
   - J+30 : première analyse sérieuse.
   - J+60 : signal plus fiable.
   - J+90 : conclusion complète.
   - Output attendu : timeline visible dans l’UI avec statut pending / measuring / ready / inconclusive.
   - Garde-fous : expliquer que le SEO/GEO nécessite du temps et que les premiers jours ne suffisent pas pour conclure.

5. **120 Progress Curve Dashboard**
   - Afficher une courbe de progression claire pour le marchand.
   - Courbes : score GEO, score SEO si disponible, impressions, clics, CTR, position moyenne, sessions organiques, conversions, revenu, pages améliorées, impact estimé vs observé.
   - Output attendu : dashboard Impact avec courbe globale, courbes par page et résumé des optimisations en validation.
   - Garde-fous : signaler les périodes à faible volume, stock indisponible, changement de prix ou tracking incomplet.

6. **121 Impact Confidence Score**
   - Calculer un score de confiance de l’impact.
   - Facteurs : délai depuis modification, volume d’impressions, évolution vs groupe contrôle, stabilité stock/prix, cohérence GSC/GA4, conversions observées, nouvelles requêtes longues, absence de rollback.
   - Output attendu : score 0-100 avec labels `données insuffisantes`, `signal faible`, `impact probable`, `impact fort`.
   - Garde-fous : ne jamais présenter le score comme une preuve causale absolue.

7. **122 Before/After Impact Report**
   - Générer un rapport clair par page/action.
   - Inclure score GEO avant/après, actions appliquées, requêtes ciblées, métriques GSC avant/après, métriques GA4 avant/après, évolution vs groupe contrôle, verdict et prochaine recommandation.
   - Output attendu : rapport exportable Markdown/PDF ou affichable dans l’app.
   - Garde-fous : distinguer impact estimé, impact observé et impact non encore mesurable.

8. **123 Retention Milestones**
   - Créer des jalons qui expliquent pourquoi l’app doit rester active pendant la validation.
   - Afficher J+7, J+30, J+60, J+90 avec les prochaines étapes.
   - Exemple de message : “Vos optimisations GEO sont appliquées. Les moteurs de recherche et IA ont besoin de temps pour recrawler et réévaluer vos pages. Gardez l’app active pour mesurer les résultats, éviter les pertes et recevoir les prochaines actions prioritaires.”
   - Output attendu : jalons visibles dans le dashboard et dans les rapports.
   - Garde-fous : ne pas utiliser de dark pattern ; la rétention doit être justifiée par la mesure réelle et la valeur du suivi.

9. **124 Win/Neutral/Risk Detection**
   - Classer automatiquement chaque optimisation.
   - Verdicts : `Win`, `Neutral`, `Risk`, `Inconclusive`.
   - Critères : évolution pages test vs pages contrôle, GSC, GA4, revenu, stabilité contexte, volume disponible.
   - Output attendu : verdict par optimisation avec explication simple.
   - Garde-fous : `Inconclusive` doit être utilisé si volume trop faible, tracking incomplet, changement de prix, rupture stock ou période trop courte.

10. **125 Next Best Action Loop**
   - Transformer les résultats validés en nouvelles recommandations.
   - Si Win : répliquer sur pages similaires.
   - Si Neutral : ajuster FAQ, facts, schema ou maillage.
   - Si Risk : proposer rollback ou pause.
   - Si Inconclusive : attendre plus de données ou choisir des pages à plus fort volume.
   - Output attendu : boucle d’amélioration continue reliant validation, recommandations et nouvelles actions.
   - Garde-fous : toute recommandation d’application doit rester en dry-run par défaut et passer par validation humaine.

### Priorité produit recommandée Phase 11.5

1. **116 Optimization Snapshot** — Socle obligatoire pour toute mesure avant/après.
2. **117 Optimization Event Tracking** — Rend chaque optimisation traçable.
3. **119 Validation Timeline J+7/J+30/J+60/J+90** — Donne au marchand une attente claire et justifie le suivi dans le temps.
4. **120 Progress Curve Dashboard** — Rend la progression visible et compréhensible.
5. **121 Impact Confidence Score** — Évite les fausses certitudes et structure la preuve.
6. **122 Before/After Impact Report** — Transforme les résultats en preuve partageable.
7. **124 Win/Neutral/Risk Detection** — Simplifie la lecture des résultats.
8. **125 Next Best Action Loop** — Crée la boucle de rétention et d’amélioration continue.
9. **118 Control Group Builder** — Renforce la crédibilité statistique, mais peut être simplifié en V1.
10. **123 Retention Milestones** — Utile commercialement, mais doit rester basé sur une vraie valeur produit.

---

## PHASE 11.6 — GEO Content Automation
*Objectif : industrialiser la génération IA de contenus GEO utiles (FAQ produits/collections, Answer Blocks, guides d'achat courts, JSON-LD FAQPage) à partir des faits produits confirmés et des intentions conversationnelles réelles, avec revue humaine obligatoire avant publication.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 126 | GEO FAQ & Buying Guide Automation — générer automatiquement des FAQ, Answer Blocks et guides d'achat GEO à partir des faits produits confirmés, requêtes GSC, intentions conversationnelles et catalogue Shopify ; proposer review humaine, scoring qualité, preview, export et application future sur produits, collections ou blogs | 🔴 | ⏳ | |

### Détail objectif tâche 126

## 126 GEO FAQ & Buying Guide Automation

- **But :** transformer les faits produits confirmés et les requêtes réelles des clients en contenus GEO utiles, prêts à être validés par le marchand.
- **Automatisation attendue :**
  - générer des FAQ produit ;
  - générer des FAQ collection ;
  - générer des blocs courts de réponses IA / Answer Blocks ;
  - générer des guides d'achat courts ;
  - proposer des comparatifs simples ;
  - suggérer des blocs "choisir ce produit si…" ;
  - suggérer des blocs "à savoir avant achat" ;
  - proposer des liens internes vers produits, collections ou guides ;
  - générer le JSON-LD `FAQPage` quand pertinent.
- **Sources à utiliser :**
  - Product Facts Layer ;
  - catalogue Shopify ;
  - descriptions produits existantes ;
  - collections ;
  - Google Search Console ;
  - clusters de niche ;
  - requêtes longues ;
  - intentions conversationnelles ;
  - données de stock ;
  - avis ou preuves de confiance si disponibles.
- **Revue humaine obligatoire :**
  - afficher chaque suggestion en mode preview ;
  - montrer les faits utilisés ;
  - séparer faits confirmés, faits manquants et suggestions à vérifier ;
  - permettre d'accepter, modifier, rejeter ou exporter ;
  - aucune publication automatique par défaut ;
  - toute écriture Shopify doit passer par confirmation explicite.
- **Output attendu :**
  - FAQ par produit ;
  - FAQ par collection ;
  - Answer Blocks courts ;
  - guides d'achat courts ;
  - suggestions de liens internes ;
  - JSON-LD FAQPage ;
  - score qualité / confiance ;
  - statut : `draft`, `needs_review`, `approved`, `rejected`, `exported`, `applied`.
- **Garde-fous :**
  - ne jamais inventer matière, origine, garantie, certification, compatibilité ou bénéfice médical ;
  - ne pas générer de contenu générique sans lien avec le catalogue ;
  - ne pas créer d'articles de blog en masse ;
  - ne pas publier sans validation humaine ;
  - éviter les FAQ artificielles, répétitives ou trop longues ;
  - privilégier les contenus qui répondent à une vraie intention client ou GEO.
- **Valeur GEO attendue :**
  - rendre les produits plus compréhensibles par les moteurs IA ;
  - couvrir les requêtes conversationnelles ;
  - améliorer la clarté des pages produits et collections ;
  - enrichir le JSON-LD ;
  - renforcer le maillage interne ;
  - aider les moteurs IA à associer les produits aux bons cas d'usage.

### Principe contenu GEO

> La génération de contenu GEO ne doit pas être pensée comme un générateur automatique d'articles de blog en masse. L'objectif est de produire des réponses utiles, factuelles et validées à partir du catalogue réel : FAQ produits, FAQ collections, Answer Blocks, guides d'achat courts et comparatifs simples. L'IA automatise la préparation, mais le marchand garde toujours la validation finale avant publication.

---

## PHASE 12 — Soumission publique Shopify App Store
*Objectif : publier l'app seulement après le pilote réel et après la parité fonctionnelle prioritaire entre scripts CLI et app embedded.*

| # | Tâche | Difficulté | Statut | Date |
|---|---|---|---|---|
| 127 | Décision go/no-go App Store après pilote réel + parité fonctionnelle prioritaire + verrouillage du périmètre V1 public | 🔴 | ⏳ | |
| 128 | Finaliser la soumission publique Shopify App Store avec preuves issues du pilote, captures à jour et configuration de production figée | 🔴 | ⏳ | |
