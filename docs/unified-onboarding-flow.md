# Unified Onboarding Flow — GEO by Organically

> Référence Phase 11.9, tâche 154. Ce document définit l'onboarding marchand V1 en 4 étapes maximum.
>
> Statut : implémentation initiale démarrée le 2026-05-21 dans l'écran `app.onboarding`.

---

## 1. Objectif

Réduire l'onboarding visible à un parcours marchand court :

1. Connecter Google.
2. Analyser la boutique avec l'IA.
3. Valider ce que l'IA a compris.
4. Voir les 3 actions prioritaires.

Le marchand ne doit pas choisir entre PageSpeed, crawl, audit technique, jobs, GSC import, JSON-LD ou autres outils avant d'avoir compris la suite logique.

---

## 2. Règle d'écran

L'écran onboarding affiche une carte principale intitulée "Démarrer en 4 étapes".

Chaque étape contient :

- un titre marchand ;
- une phrase de valeur ;
- un statut clair ;
- un CTA seulement si l'étape est la prochaine action à faire.

Les outils techniques restent accessibles sous **Outils avancés**.

---

## 3. Séquence cible

| # | Étape | Critère terminé | CTA actif |
|---|---|---|---|
| 1 | Connecter Google | `gsc.connected = true` | Connecter Google |
| 2 | Analyser ma boutique avec l'IA | `niche_hypothesis` existe | Analyser ma boutique avec l'IA |
| 3 | Valider ce que l'IA a compris | `status = validated_by_merchant` | Valider la compréhension IA |
| 4 | Voir les 3 actions prioritaires | Action volontaire du marchand | Voir mes actions |

GA4 reste recommandé mais non bloquant. PageSpeed, crawl technique, jobs et checklist complète restent en mode avancé.

---

## 4. Briques existantes réutilisées

| Besoin | Brique existante |
|---|---|
| Connexion Google | `gsc_connect` et `/api/shops/{shop}/gsc/authorize` |
| Import Google | `gsc_import` conservé en mode avancé |
| Analyse IA | `/api/shops/{shop}/niche/understand` |
| Validation IA | écran `app.niche-understanding` |
| Actions prioritaires | écran `app.priorities` |
| Outils techniques | Installation checklist, PageSpeed, Crawl, Audit launcher |

---

## 5. Garde-fous

- Ne pas supprimer les outils techniques historiques.
- Ne pas remettre Screaming Frog comme prérequis.
- Ne pas rendre GA4 bloquant.
- Ne pas exposer PageSpeed ou crawl comme première décision marchand.
- Ne pas lancer d'application Shopify depuis l'onboarding.
- Ne pas créer de nouveau moteur ou endpoint si les routes existantes suffisent.

---

## 6. Critères de validation tâche 154

- L'onboarding visible tient en 4 étapes.
- Une seule prochaine action est mise en avant.
- Les outils avancés restent accessibles derrière un bloc replié.
- La connexion Google, l'analyse IA, la validation IA et les actions prioritaires restent reliées aux routes existantes.
- Le build frontend passe.
