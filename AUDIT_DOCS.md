# AUDIT DOCS — Lot 1 du grand audit (2026-05-12)

> Lecture comparative des 14 .md du projet. Identification des écarts entre documentation et réalité du code, classés par sévérité. **Ce document est un rapport — il ne corrige rien.**

---

## Méthodologie

Fichiers lus :
- Racine : `CLAUDE.md`, `ROADMAP.md`, `PROGRESS.md`, `DECISIONS.md`, `RAPPORT_AUDIT.md`, `AUDIT_CLAUDE_CODE.md`, `PROJECT_BRIEF.md`, `CONTEXT.md`, `README.md`
- `docs/` : `guide-utilisateur.fr.md`, `user-guide.en.md`, `plans.md`
- `skills/` : `seo-technique.md`, `shopify-graphql.md`, `pet-accessories-niche.md`
- `frontend/README.md`, `.claude/agents/python-quality.md`, `.claude/agents/shopify-safety.md`

Référentiels de vérité utilisés pour confronter les autres docs :
- **ROADMAP.md** (à jour 2026-05-12, 73/75 tâches ✅)
- **DECISIONS.md** (décisions de pivot 2026-05-10)
- **Mémoire projet** (Phase 8 progression, 960 tests)

---

## Classification des écarts

### 🔴 CRITIQUES (induisent en erreur les nouveaux contributeurs ou utilisateurs)

#### D1. `CONTEXT.md` → secteur business obsolète
**Drift** : Document dit "animalerie / petfood", concurrents "Zooplus, Wanimo, Maxi Zoo, Croquetteland, Ultra Premium Direct, Japhy". Mots-clés cibles : "croquettes chien sans céréales", "friandises chien naturelles". GA4 Property `properties/459014688`.

**Réalité** : Le secteur a été redéfini en Phase 4 (tâche 41) comme "accessoires premium chiens/chats fabriqués en France". Concurrents = Miacara, Zara Pets, Ferplast. Le catalogue réel est documenté dans `skills/pet-accessories-niche.md` : vêtements, fontaines, griffoirs, bols.

**Impact** : Tout nouvel agent IA ou contributeur qui lit `CONTEXT.md` recommande des stratégies SEO pour des croquettes inexistantes. Conflit direct avec `skills/pet-accessories-niche.md` et `CLAUDE.md` section 1.

**Action recommandée** : réécrire `CONTEXT.md` autour du catalogue réel (déjà fait dans `skills/pet-accessories-niche.md` — soit fusionner soit redéfinir le rôle de chaque fichier).

---

#### D2. `docs/guide-utilisateur.fr.md` + `docs/user-guide.en.md` → instructions Dashboard React mort
**Drift** : Les deux guides documentent activement :
```
cd frontend && npm run dev    # port 5173
```
Et listent les onglets "Dashboard / Issues / Apply / Help" du dashboard React comme l'interface principale.

**Réalité** : `frontend/` est **explicitement décommissionné** par DECISIONS.md (2026-05-10) :
> "frontend/ React standalone (Phase 5) → shopify-app/ (Remix, tâche 56) est désormais la couche UI native Shopify App Store"

CLAUDE.md confirme : *"frontend/ React existant → décommissionné après tâche 57"*.

**Impact** : Un utilisateur qui suit le guide va lancer un système mort. La doc le guide vers `localhost:5173` qui ne sera pas la cible App Store.

**Action recommandée** : retirer toute mention du dashboard React, ou ajouter un encadré "legacy — sera remplacé par l'app Shopify embedded". Réécrire la section "Premiers pas — Dashboard web" pour pointer vers `shopify-app/` (Remix).

---

#### D3. `docs/plans.md` et `README.md` → pitch HMAC license en contradiction avec règle App Store
**Drift** : `docs/plans.md` documente intégralement le système HMAC (`LEONIE_API_KEY=LEO-...`, `leonie-seo license issue --tenant ... --plan pro --days 365`). `README.md` reprend ce système comme méthode officielle de monétisation.

**Réalité** : `CLAUDE.md` règle 12 (non négociable) :
> "Shopify Billing API — toute monétisation passe par `appSubscriptionCreate`, jamais un système maison en production App Store"

DECISIONS.md tâche 52 et la mémoire projet confirment : Shopify Billing API est implémentée (`app/billing/router.py`), tâche 52 ✅ 2026-05-10.

**Impact** : Les docs présentent une voie de monétisation interdite pour l'App Store comme la voie officielle. Risque réel : un marchand inscrit qui paie via HMAC sans passer par Shopify Billing = rejet App Store.

**Action recommandée** : repositionner le système HMAC comme "mode self-hosted / agence" (cas d'usage hors App Store) et faire de Shopify Billing la voie standard documentée pour les marchands App Store. Mettre à jour `docs/plans.md` avec les deux modes clairement distingués.

---

### 🟡 STATUS DRIFT (cosmétique mais sème la confusion sur l'état du projet)

#### D4. `CLAUDE.md` section 3 — Tableau des phases obsolète
**Drift** : Le tableau dit :
- Phase 6 — Statut "⏳ Priorité absolue"
- Phase 7 — "⏳ Non démarrée"
- Phase 8 — "⏳ Non démarrée"

**Réalité** : Phase 6 ✅ 2026-05-10, Phase 7 ✅ 2026-05-11, Phase 8 ✅ 73/75 (manque 75 + 49).

**Impact** : Modéré — Claude relit ce tableau chaque session et risque de mal estimer la priorité courante.

---

#### D5. `CLAUDE.md` section 6 — Modules listés comme "à créer"
**Drift** :
- *"IA & NLP (Phase 7 — à ajouter)"* — pourtant `app/llm/`, `app/llm/providers/`, `config/prompts/` existent.
- *"Niche Intelligence (Phase 7 — tâche 62-63)"* listé comme à venir — `app/niche/` complet.
- *"Nouveaux modules à créer (Phases 7-8) : `app/llm/`, `app/niche/`, `app/jobs/`, `app/billing/`, `app/observability/`, `extensions/`"* — **TOUS existent** au commit courant.

**Impact** : Confusion sur ce qui est implémenté. Un nouveau contributeur lit le CLAUDE.md et peut dupliquer du travail.

---

#### D6. `PROGRESS.md` — État global figé au 2026-05-10
**Drift** : En-tête dit :
- "Phase actuelle : Phase 6 — Conformité App Store (tâche 51 à démarrer)"
- "Tests : 537/537 ✅"
- "Phase 5 : 5/6 complètes ✅ (tâche 49 bloquée)"
- Pas de log de sessions du 2026-05-10 à 2026-05-12 (les phases 6, 7, et 8 ne sont pas dans l'historique).

**Réalité** : 960 tests, Phase 8 quasi-complète.

**Impact** : Le fichier "mémoire vivante" est 3 jours en retard. Le protocole CLAUDE.md section 2 ("Lire PROGRESS.md à chaque début de session") fait que Claude lit un état obsolète.

---

#### D7. `README.md` — Tableau de roadmap périmé
**Drift** : Tableau "Roadmap en 8 phases" dit Phase 5 🔄, Phases 6-8 toutes ⏳.

**Réalité** : Phases 1-7 ✅, Phase 8 ⏳ (2 tâches restantes : 49, 75).

**Impact** : Mauvais signal aux visiteurs GitHub / futurs marchands. Donne l'impression d'un projet à 60% alors qu'il en est à 95%.

---

### 🟢 HISTORIQUE (faible priorité, à archiver ou marquer comme tels)

#### D8. `PROJECT_BRIEF.md` — Document Day-1, désaligné depuis Phase 5
**Drift** :
- *"Interface : CLI + rapports Markdown — pas de dashboard web, pas de Streamlit"* → faux depuis Phase 5
- *"Budget outils : 0 à 50 €/mois maximum"* → contredit par CLAUDE.md ("≤ 12 €/mois")
- *"skills/petfood-niche.md"* → fichier renommé `pet-accessories-niche.md` en tâche 41
- *"50 tâches"* → 75 tâches dans ROADMAP.md
- Section 11 (best practices Claude Code) cite des sources 2026-mars dans le passé du projet (cohérent en temps mais le texte se présente comme un guide d'onboarding qui ne reflète plus l'état)

**Impact** : Faible — c'est un document de cadrage initial. **Action recommandée** : ajouter un en-tête "ARCHIVE — document de cadrage initial (2026-04-20), conservé pour traçabilité. État courant : voir ROADMAP.md, CLAUDE.md, PROGRESS.md."

---

#### D9. `RAPPORT_AUDIT.md` — Snapshot 2026-05-10 obsolète
**Drift** : TL;DR dit "Couverture estimée : 28 %", liste comme gaps : GDPR webhooks absents, Billing API absente, App Bridge absent, async queue absent, LLM absent, niche absente, embeddings absents, GA4 absent, theme extension absente, observabilité absente — **tous résolus depuis** (phases 6-8).

**Impact** : Faible — c'est un snapshot daté, mais il est cité par PROGRESS.md comme référence. **Action recommandée** : ajouter en-tête "Snapshot daté 2026-05-10 — voir suivi de comblement des gaps dans ROADMAP.md tâches 51-74".

---

#### D10. `AUDIT_CLAUDE_CODE.md` — Brief d'audit, pas un état
Document de spec qui a produit `RAPPORT_AUDIT.md`. Pas obsolète à proprement parler (c'est un input), mais sa présence à la racine peut induire en erreur. **Action recommandée** : déplacer dans `docs/archive/` ou ajouter en-tête.

---

#### D11. `frontend/README.md` — Template Vite par défaut
Fichier généré par Vite, jamais customisé. `frontend/` est décommissionné. **Action recommandée** : supprimer le dossier `frontend/` complet une fois la tâche 75 (soumission App Store) confirmée, ou ajouter `frontend/README.md` réécrit avec mention "LEGACY — voir shopify-app/".

---

### ⚙️ CONTRADICTIONS INTERNES (entre deux docs)

#### C1. Concurrents : CONTEXT vs skills/pet-accessories-niche
- `CONTEXT.md` : Zooplus, Maxi Zoo, Wanimo, Croquetteland, Ultra Premium Direct, Japhy
- `skills/pet-accessories-niche.md` : Zara Pets, Miacara, Ferplast
- `CLAUDE.md` : Miacara, Zara Pets, Ferplast

**Verdict** : `CONTEXT.md` à mettre en cohérence avec les deux autres (voir D1).

---

#### C2. Nom de la niche : différents fichiers ne sont pas alignés
- `PROJECT_BRIEF.md` : "petfood-niche.md"
- `CLAUDE.md` : "pet_accessories_fr"
- ROADMAP.md tâche 41 : "renommage niche `petfood_fr` → `pet_accessories_fr`"
- Réalité fichier : `skills/pet-accessories-niche.md` ✅

**Verdict** : seul `PROJECT_BRIEF.md` est en retard.

---

#### C3. Phase 5 statut
- `CLAUDE.md` : "✅ Complète (49 bloqué review)"
- `PROGRESS.md` : "🔄 5/6 complètes (tâche 49 bloquée)"
- `README.md` : "🔄 5/6"
- `ROADMAP.md` : tâche 49 ⏳, toutes les autres ✅

**Verdict** : cohérent dans l'intention. Mais sémantique des emojis pas uniforme.

---

#### C4. Budget infra
- `PROJECT_BRIEF.md` : "0 à 50 €/mois"
- `CLAUDE.md` : "≤ 12 €/mois jusqu'à 100 stores"
- `README.md` : "≤ 12 €/mois"

**Verdict** : `PROJECT_BRIEF.md` obsolète (résolu par D8).

---

## Synthèse par priorité

| Rang | Action | Fichier | Effort | Pourquoi |
|---|---|---|---|---|
| 🔴 1 | Réécrire le secteur business (accessoires, pas petfood) | `CONTEXT.md` | M | Désalignement direct vs business réel |
| 🔴 2 | Retirer les instructions `frontend/` actives des guides | `docs/guide-utilisateur.fr.md`, `docs/user-guide.en.md` | S | Les utilisateurs lancent un système mort |
| 🔴 3 | Repositionner HMAC vs Shopify Billing dans la doc | `docs/plans.md`, `README.md` | M | Risque rejet App Store |
| 🟡 4 | Mettre à jour le tableau des phases | `CLAUDE.md` section 3 | S | Lu à chaque session par Claude |
| 🟡 5 | Marquer les modules comme "implémentés" | `CLAUDE.md` section 6 | S | Évite duplication de travail |
| 🟡 6 | Rafraîchir l'état global et l'historique | `PROGRESS.md` | S | Source de vérité session par session |
| 🟡 7 | Mettre à jour la roadmap publique | `README.md` | S | Image projet vers contributeurs |
| 🟢 8 | Archiver / en-têter les documents historiques | `PROJECT_BRIEF.md`, `RAPPORT_AUDIT.md`, `AUDIT_CLAUDE_CODE.md` | S | Clarté |
| 🟢 9 | Supprimer ou réécrire `frontend/README.md` | `frontend/README.md` | XS | Cohérent avec D2 |

---

## Recommandation pour le Lot 2 (audit code)

L'audit doc révèle que **plusieurs modules sont implémentés mais documentés comme à venir**. Pour le Lot 2, prioriser :

1. **Vérifier que `app/llm/`, `app/niche/`, `app/billing/`, `app/jobs/`, `app/observability/`, `extensions/`, `shopify-app/` existent et sont fonctionnels** (la doc ment plus que le code).
2. **Identifier les références hardcodées à `leoniedelacroix.com`** dans `.github/workflows/`, scripts, configs — déjà flaggé dans RAPPORT_AUDIT.md mais à reconfirmer.
3. **Vérifier l'état de `scripts/license.py`** vs `app/billing/` — quelle voie est canon ?
4. **Vérifier que `frontend/` peut être supprimé sans casser de tests ni d'imports** dans le code Python actif.

---

*Lot 1 terminé. Aucune modification de code ou de doc effectuée. 11 dérives identifiées (3 critiques, 4 status, 4 historiques) + 4 contradictions internes.*
