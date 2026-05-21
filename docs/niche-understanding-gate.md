# Niche Understanding Gate — Léonie SEO

> Référence Phase 11.9, tâche 153. Ce document définit la règle produit qui fait de la compréhension IA validée le passage obligatoire avant les recommandations principales.
>
> Statut : implémentation initiale démarrée le 2026-05-21 sur l'accueil marchand et l'écran Top 3 Actions.

---

## 1. Règle produit

Les recommandations principales ne doivent pas être présentées au marchand tant que l'IA n'a pas produit une compréhension de la boutique validée par le marchand.

Statut bloquant :

```text
niche_hypothesis.status != "validated_by_merchant"
```

Dans ce cas, l'application affiche un chemin simple :

1. analyser la boutique avec l'IA ;
2. relire ce que l'IA a compris ;
3. corriger si nécessaire ;
4. valider ;
5. revenir aux actions prioritaires.

---

## 2. Ce qui est bloqué

| Surface | Comportement standard tant que non validé |
|---|---|
| Accueil, zone actions | Remplacer les cartes d'actions par un message de validation préalable |
| Top 3 Actions | Ne pas charger les recommandations principales ; afficher un CTA vers la compréhension IA |
| Content Actions factuelles | Ne pas générer de contenu qui utilise les hypothèses marchand |
| Safe Apply | Ne pas présenter l'application comme prochaine étape recommandée |

---

## 3. Ce qui reste accessible

| Surface | Raison |
|---|---|
| Compte & configuration | Le marchand doit pouvoir connecter Google, GA4, gérer son plan et ses réglages |
| Compréhension boutique | C'est l'écran de résolution du blocage |
| Mode avancé | Les agents et marchands experts peuvent diagnostiquer sans polluer le parcours standard |
| Historique et mesure | Les optimisations déjà appliquées restent consultables |

---

## 4. Briques existantes réutilisées

| Besoin | Brique existante |
|---|---|
| Lire la dernière hypothèse | `/api/shops/{shop}/niche/hypothesis` |
| Relancer l'analyse | `/api/shops/{shop}/niche/understand` |
| Corriger l'hypothèse | PATCH `/api/shops/{shop}/niche/hypothesis` |
| Valider humainement | `status = validated_by_merchant` |
| Consommer ensuite | Unified Readiness Audit, Opportunity Finder, Priority Engine, AI Content Actions |

---

## 5. Garde-fous

- Ne pas créer de nouveau moteur SEO/GEO.
- Ne pas créer de nouveau score.
- Ne pas bloquer les réglages, l'aide, l'historique ou le mode avancé.
- Ne pas utiliser une hypothèse non validée pour écrire ou recommander un contenu marchand.
- Ne pas valider automatiquement à la place du marchand.
- Ne pas appliquer Shopify sans dry-run et confirmation humaine.
- Ne pas promettre de résultat garanti dans Google ou dans les moteurs IA.

---

## 6. Critères de validation tâche 153

- L'accueil ne pousse plus vers les actions si la compréhension IA n'est pas validée.
- La page Top 3 Actions affiche une gate claire au lieu de recommandations principales.
- Le CTA de résolution pointe vers l'écran "Compréhension boutique".
- Les réglages et modes avancés ne sont pas supprimés.
- Aucun nouveau moteur, endpoint ou score n'est ajouté.
