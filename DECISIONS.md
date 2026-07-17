# DECISIONS — Journal des choix techniques

> Un choix par entrée. Format : date, contexte, décision, raison.

---

## 2026-05-21 — Go/No-Go App Store : NO-GO Phase 12 (tâche 149)

**Contexte :** Tâche 149 — exécution de la checklist `docs/launch-readiness.md` §3.1 → §3.13 avant soumission App Store (Phase 12). Audit mécanique avec preuves sur code base courante (1520 tests verts).

**Décision : NO-GO Phase 12 à date du 2026-05-21**

Trois critères §3 non satisfaits avant corrections intégrées dans cette tâche ; un critère §3.1 ne peut pas être validé par audit interne :

| Critère | §Spec | Statut avant tâche 149 | Statut après remédiation |
|---|---|---|---|
| `LEONIE_LLM_LOW_COST_ONLY` env var opérationnel | §3.2 / §3.9 | ❌ non implémenté | ✅ implémenté (`_effective_tier()` dans `runner.py`) |
| Rollback TTL 90 jours avec avertissement | §3.10 | ❌ absent | ✅ implémenté (`confirm_stale_revert`, 409 + `stale_warning`) |
| Screaming Frog décrit comme "obligatoire" dans l'UI | §3.6 | ❌ `CrawlCard.tsx` texte "obligatoire" / "required" | ✅ corrigé en "optionnel — mode avancé" |
| Test utilisateur sur 3 marchands pilotes (§3.1 + §3.12) | §3.1 §3.12 | ⏳ non réalisé | ⏳ **bloquant permanent** |

**Critère non contournable :**
`docs/launch-readiness.md §7` est explicite : *« Test utilisateur sur 3 marchands pilotes est exigé pour §3.1 et §3.12 — pas négociable, pas remplaçable par 'test interne'. »* Ce critère exige une validation humaine réelle par 3 marchands (compréhension < 5 min + dashboard impact lisible). Aucun audit code ne peut le substituer.

**Résumé de l'audit post-remédiation (13 catégories) :**

| Section | Critères | Statut |
|---|---|---|
| §3.1 — Compréhension marchand | 5 | ✅×4 / ⏳×1 (test utilisateur) |
| §3.2 — 3 actions prioritaires | 5 | ✅×5 |
| §3.3 — IA assistante | 5 | ✅×5 |
| §3.4 — Mesure d'impact | 7 | ✅×7 |
| §3.5 — Scope produit V1 | 4 | ✅×4 |
| §3.6 — Sans Screaming Frog | 5 | ✅×5 |
| §3.7 — Pas de promesse non prouvée | 4 | ✅×4 |
| §3.8 — Google/IA séparés | 3 | ✅×3 |
| §3.9 — Coût LLM maîtrisé | 10 | ✅×10 |
| §3.10 — Rollback opérationnel | 4 | ✅×4 |
| §3.11 — Dry-run par défaut | 5 | ✅×5 |
| §3.12 — Dashboard impact lisible | 4 | ✅×3 / ⏳×1 (test utilisateur) |
| §3.13 — Niche gating | 4 | ✅×4 |

**GO conditionnel à :** Réalisation du test utilisateur sur 3 marchands pilotes (§3.1 et §3.12). Toutes les autres implémentations techniques sont complètes et validées par tests.

**Remédiation intégrée dans la tâche 149 :**
- `app/content_actions/runner.py` : `_effective_tier()` + `LEONIE_LLM_LOW_COST_ONLY` support
- `app/api/rollback.py` : TTL 90 jours, `confirm_stale_revert`, `stale_warning` en dry-run
- `shopify-app/app/components/onboarding/CrawlCard.tsx` : "obligatoire" → "optionnel — mode avancé"
- `shopify-app/app/components/onboarding/InstallationChecklistCard.tsx` : libellé SF mis à jour

**Prochaine action :** Planifier les 3 sessions test utilisateur avec marchands pilotes. Go Phase 12 possible dès validation humaine OK.

---

## 2026-05-21 — Phase 11.9 gate : NO-GO Phase 12 tant que parcours marchand non validé (tâche 163)

**Contexte :** Phase 11.9 "Merchant Journey Unification & Friction Reduction" ajoutée après la tâche 149. Tâches 152-163 : docs canoniques + ajustements UX/i18n pour rendre l'app compréhensible en < 5 minutes.

**Décision : Phase 11.9 complète + test 3 marchands pilotes sont des prérequis bloquants avant Phase 12.**

Ce prérequis s'ajoute en amont des §3 de `docs/launch-readiness.md`. Voir `docs/launch-readiness.md` §0 pour la liste complète des prérequis Phase 11.9.

| Gate | Statut | Condition de levée |
|---|---|---|
| Tâches 152-163 ✅ | ⏳ (tâches 152-163 en cours / terminées) | ROADMAP.md Phase 11.9 10/12 |
| Test 3 marchands pilotes | ⏳ | `docs/pilot-merchant-test-script.md` — 5 critères atteints |
| Vocabulaire marchand vérifié | ⏳ | `docs/merchant-language-glossary.md` — 0 terme interdit visible |
| CTA unique par écran | ⏳ | `docs/cta-matrix.md` — revue UI |

**Raison :** La tâche 149 a prouvé que les critères techniques §3 sont atteints. Le bloquant restant est humain : comprendre si un marchand non expert peut utiliser l'app sans aide. Phase 11.9 vise à réduire cette friction avant le test pilote formel.

---

## 2026-05-12 — Real-store pilot uses a separate custom-distribution Shopify app

**Context:** GEO by Organically needs real merchant feedback on `leoniedelacroix.com` before the public App Store launch, but Shopify distribution type is a long-lived product choice.

**Decision:** Use a dedicated Shopify Partner app for the pilot, configured for custom distribution and installed directly on the real merchant store through Shopify's generated install link. Keep the future public App Store app separate.

**Reason:** The pilot needs a real-store install path and real callback handling now, while the public App Store app still needs its own future review path, billing posture, and launch timing. Keeping the apps separate prevents the pilot setup from boxing in the public distribution strategy.

**Impact:**
- `shopify-app/` gains a dedicated operator workflow documented in `docs/pilot-real-store-setup.md`.
- `shopify app config link --config pilot` is the expected CLI path for the merchant pilot configuration.
- Persistent sessions, public HTTPS callbacks, and real webhook delivery become pilot prerequisites before task 77.
- Billing remains outside the merchant charging path for the pilot and is validated again later for the App Store release path.

---

## 2026-05-10 — Auth interne Remix → Python : secret partagé (Option B)

**Contexte :** Remix (couche app) doit appeler le moteur Python en authentifiant le shop sans re-demander un Shopify JWT à chaque requête serveur-to-serveur.

**Décision :** `X-Leonie-Shop` + `X-Internal-Secret` headers — secret partagé via `INTERNAL_API_SECRET` dans les deux `.env`. Python valide avec `secrets.compare_digest()` (constant-time).

**Raison :** Option A (JWT Shopify forwarding) nécessite JWKS + validation asym. côté Python — complexité injustifiée pour un setup monorepo sur hôte unique. Option B est suffisante et auditable.

**Impact :** `deps.py` accepte les headers internes en bypass du check session token. Les appels externes (navigateur direct) restent soumis à LEONIE_REQUIRE_SESSION_TOKEN.

---

## 2026-05-10 — Décommission frontend/ (legacy React dashboard)

**Contexte :** `frontend/` était le dashboard React standalone (Phase 5). `shopify-app/` (Remix, tâche 56) est désormais la couche UI native Shopify App Store.

**Décision :** Retrait du serving statique de `app/main.py` (bloc `_DIST`). Code source `frontend/` conservé comme archive (pas supprimé).

**Raison :** Le dashboard React autonome n'est pas compatible App Store (pas d'App Bridge). La migration vers Remix est le chemin vers la soumission App Store (tâche 75).

---

## 2026-04-28 — OAuth utilisateur plutôt que Service Account pour Google APIs

**Contexte :** Google Search Console refuse l'ajout d'un service account (erreur « email introuvable » même après délai de propagation).

**Décision :** Utiliser OAuth utilisateur (type Desktop app) via `oauth_client.json`. Le `token.json` est généré au premier run et rechargé ensuite.

**Raison :** GSC n'accepte que des comptes Google personnels comme propriétaires. Les service accounts ne sont pas reconnus comme utilisateurs GSC valides. L'OAuth utilisateur est plus simple pour un usage solo.

**Impact :** Le 1er run de `fetch_gsc.py` ouvre une fenêtre navigateur pour autorisation. Les runs suivants sont silencieux. `oauth_client.json` et `token.json` sont dans `.gitignore`.

---

## 2026-04-28 — Ahrefs API skippé

**Contexte :** Ahrefs API coûte ~$129/mois, incompatible avec le budget 0-50€/mois.

**Décision :** Skip total de l'API Ahrefs. Ahrefs Webmaster Tools (AWT) gratuit gardé pour usage manuel (exports CSV occasionnels).

**Raison :** GSC + GA4 + PageSpeed + Shopify couvrent 90% des besoins d'audit. Les backlinks peuvent être importés manuellement via CSV AWT si besoin ultérieur.

---

## 2026-04-20 — SQLite plutôt que Postgres

**Contexte :** Besoin d'historique des modifications et de rollback.

**Décision :** SQLite via `sqlite3` stdlib, fichier `data/history.db`.

**Raison :** Site petit (< 20 produits), usage solo, zéro infra à gérer. SQLite est suffisant pour des années d'historique SEO. Postgres serait de la sur-ingénierie pure.

---

## 2026-04-20 — Dry-run par défaut sur tous les scripts apply/

**Contexte :** Risque d'écraser des données produit Shopify par erreur.

**Décision :** Tout script dans `scripts/apply/` a `--dry-run` comme comportement par défaut. `--apply` doit être passé explicitement.

**Raison :** Éviter les accidents irréversibles. Le dry-run affiche un diff lisible avant toute écriture réelle.

---

## 2026-04-20 — Screaming Frog Free plutôt que crawler custom

**Contexte :** Besoin de crawl complet pour détecter les 404, redirects en chaîne, duplicate content.

**Décision :** Screaming Frog Free (lancement manuel, export CSV parsé par `crawl_shopify.py`).

**Raison :** Le site fait < 500 URLs (3 collections, ~20 produits), donc la limite gratuite de Screaming Frog est largement suffisante. Écrire un crawler custom serait du travail inutile quand un outil mature existe.

---

## 2026-05-10 — Architecture pivot : Option B retenue — scaffold Remix propre

**Contexte :** Le pivot de "scripts + cron mono-store" vers "SaaS multi-tenant Shopify embedded" change : auth, stockage, jobs, billing, webhooks, isolation données, rollback, UX Shopify, observabilité, queues, quotas, review App Store. Transformer progressivement le FastAPI + React existant crée une dette qui coûte typiquement 6 mois.

**Décision :** **Option B — scaffold Shopify App propre via Shopify CLI (Remix).**
- Couche app (routing, UI, auth Shopify, Billing, GDPR) → nouveau dossier `shopify-app/` en Remix
- Moteur SEO/IA Python conservé intégralement : `scripts/`, `app/llm/`, `app/niche/`, `app/jobs/`
- `shopify-app/` appelle le backend Python via HTTP interne
- `frontend/` React existant → déprécié après tâche 56

**Raison :** Shopify CLI génère le scaffold Remix avec App Bridge v4, Polaris, OAuth, sessions multi-tenant et structure multi-store câblés d'emblée. App Bridge attend un contexte Remix/Next pour les sessions — l'adapter sur Vite custom est du bricolage générateur de dette. L'investissement de 2 semaines de setup évite 6 mois de friction.

**Impact :**
- Tâche 56 : `shopify app create` → scaffold Remix (inclut App Bridge + Polaris + OAuth + sessions)
- Tâche 57 : câblage `shopify-app/` → Python backend (proxy HTTP, Neon Postgres partagé)
- `frontend/` + `app/oauth/router.py` : décommissionnés après tâche 57
- `scripts/`, `app/api/`, `app/llm/`, `app/niche/`, `app/jobs/` : conservés sans modification

---

## 2026-05-10 — Async job queue : Postgres-backed, pas Redis

**Contexte :** Les jobs LLM batch (tâche 60), les audits background, et les webhooks Shopify nécessitent une queue dès Phase 6 pour ne pas bloquer les requêtes HTTP. Redis ajoute ~15-20 €/mois sur Render/Railway.

**Décision :** Postgres-backed job queue (pattern pg-boss simplifié en Python) sur Neon Postgres déjà provisionné en tâche 54. Zéro surcoût infra.

**Raison :** Neon Postgres est déjà dans le budget. Un worker Python qui poll une table `jobs` toutes les X secondes couvre 100% des besoins Phase 7. Si le volume dépasse 10 000 jobs/jour, migrer vers Redis à ce moment-là.

**Impact :** Module `app/jobs/` à créer en tâche 55 avant les features LLM.

---

## 2026-05-10 — Common Crawl déféré après sources légères (tâche 63 avant 74)

**Contexte :** Common Crawl / Web Graph est puissant pour l'analyse de backlinks et le graph de liens concurrents, mais représente des fichiers WARC de plusieurs To et une complexité d'ingestion majeure.

**Décision :** Valider d'abord les sources légères (Google Suggest + pytrends + Reddit, tâche 63). Common Crawl en tâche 74 (Phase 8) seulement si ces sources ne suffisent pas à alimenter la Niche Intelligence.

**Raison :** 80% de la valeur du Niche Intelligence est probablement atteignable avec GSC + Google Suggest + Reddit + SERP scraping léger. Common Crawl est un puits de complexité si les signaux légers fonctionnent.

**Impact :** Tâche 74 conditionnelle — peut être skipée si tâche 63 + 62 fournissent des keyword gaps exploitables.

---

## 2026-04-20 — Pas de modification des handles produits

**Contexte :** Les handles Shopify définissent les URLs des produits.

**Décision :** Aucun script ne modifie jamais les handles produits, pour toujours.

**Raison :** Modifier un handle = changer l'URL du produit = 404 massif si la redirection n'est pas parfaite. Le risque SEO est catastrophique. Les handles actuels sont conservés tels quels pendant au minimum 3 mois.
