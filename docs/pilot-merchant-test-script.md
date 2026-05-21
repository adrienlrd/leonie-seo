# Pilot Merchant Test Script — Tâche 162

## Objectif

Valider que l'app est compréhensible par un marchand non expert en moins de 5 minutes, sans explication préalable. Ce test est le dernier critère bloquant avant la soumission App Store.

## Profil des marchands testés

- 3 marchands pilotes avec boutique Shopify active
- Pas de formation SEO ni IA
- Accepte de partager son écran (session vidéo ou présentiel)
- Durée totale : 20-30 minutes

## Protocole

### Avant le test
1. Accéder à l'app sur la boutique du marchand (ou sur une boutique de démo)
2. Ne pas expliquer les fonctionnalités à l'avance
3. Dire uniquement : "Je vais vous demander de naviguer dans cette app. Dites à voix haute ce que vous pensez."

### Tâches observées (6 tâches)

| # | Tâche | Temps max | Succès si |
|---|---|---|---|
| T1 | Connectez Google Search Console depuis l'app | 3 min | Bouton trouvé, flow OAuth lancé |
| T2 | Lancez l'analyse IA de votre boutique | 2 min | Bouton "Analyser ma boutique" cliqué |
| T3 | Lisez ce que l'IA a compris de votre boutique et dites si c'est correct | 3 min | Merchant identifie la niche et peut confirmer/corriger |
| T4 | Validez la compréhension IA puis trouvez vos 3 actions prioritaires | 2 min | "Valider" cliqué, page Top 3 Actions atteinte |
| T5 | Prévisualisez la première action recommandée | 2 min | "Prévisualiser" cliqué, dry-run lancé |
| T6 | Lisez votre résultat d'impact et dites ce que vous comprenez | 3 min | Merchant identifie son dernier résultat (Win/Neutre/Risque) |

**Total tâches : 15 min max. Buffer discussion : 10-15 min.**

### Questions post-test (5 min)

1. Sur une échelle de 1 à 5, à quel point avez-vous compris ce que fait l'app ?
2. Y a-t-il des termes que vous n'avez pas compris ? Lesquels ?
3. À quel moment avez-vous hésité ou cherché quoi cliquer ?
4. Feriez-vous confiance à l'app pour modifier votre boutique ? Pourquoi ?
5. Qu'est-ce qui manquait pour vous sentir en confiance ?

## Grille de friction (observateur)

Pour chaque tâche, noter :

| Critère | Score 0-5 |
|---|---|
| 0 : Aucune hésitation, action immédiate | |
| 1 : Hésitation brève (< 5s) | |
| 2 : Lecture de toute la page avant d'agir | |
| 3 : Question verbalisée ("c'est quoi X ?") | |
| 4 : Aide demandée | |
| 5 : Tâche abandonnée ou erreur de navigation | |

## Seuils de passage (critères go/no-go §3.1 et §3.12)

| Critère | Seuil |
|---|---|
| Compréhension IA validée (T3) | 3 marchands sur 3 identifient leur niche correctement |
| CTA principal trouvé sans aide (T2, T4) | Friction ≤ 1 pour 3 marchands sur 3 |
| Dashboard impact compris (T6) | 3 marchands sur 3 identifient un résultat (Win/Neutre/Risque) |
| Aucune question sur le vocabulaire technique | 0 occurrence de "c'est quoi GEO ?" ou "c'est quoi crawl ?" |
| Confiance Safe Apply (T5) | Score question 4 ≥ 4/5 pour 3 marchands sur 3 |

## Résultat attendu

Si ces 5 critères sont atteints → Phase 11.9 validée → GO Phase 12 (tâche 150).

Si l'un est manqué → identifier la friction spécifique → correction ciblée → re-test sur 1 marchand.
