# One Primary CTA per Screen — Tâche 156

## Principe

Chaque écran principal de l'app expose un seul bouton en `variant="primary"` (vert). Ce bouton = l'action suivante dans le parcours marchand. Les autres actions sont `variant="secondary"` (neutre) ou `variant="plain"` (discret).

## Matrice écran → CTA unique

| Écran | État | CTA primaire | Autres boutons |
|---|---|---|---|
| **Accueil** | IA non validée | "Valider ce que l'IA a compris" (Zone 1) | Zone 2 : texte gate sans bouton primaire |
| **Accueil** | IA validée | "Préparer cette action" sur chaque ActionCard | Zone 3 : "Voir l'impact détaillé" → secondary |
| **Compréhension boutique** | Normal | "Valider" | "Analyser" → secondary ; "Enregistrer" → plain |
| **Top 3 Actions** | Gate (non validée) | "Voir ce que l'IA a compris" | — |
| **Top 3 Actions** | Actions chargées | "Préparer cette action" (1 par carte) | — |
| **Améliorations proposées** | draft/needs_review | "Valider" (accept) | "Prévisualiser" → secondary ; "Refuser" → plain |
| **Améliorations proposées** | approved | "Publier" (live_apply) | "Prévisualiser" → secondary ; "Annuler" → plain |
| **Mesure** | Normal | "Voir prochaines actions" (bas de page) | Autres liens → secondary |

## Règles d'application

1. **`variant="primary"` = 1 maximum par état de page.** Si plusieurs cartes affichent chacune un primary CTA, c'est acceptable dans une grille (chaque carte est une unité indépendante).
2. **`tone="critical"` sur un bouton d'action positive est interdit.** Le bouton "Publier" n'est pas critique — il est primaire (vert). Utiliser `tone="critical"` uniquement pour les actions destructives irréversibles.
3. **`tone="success"` implicite sur primary buttons Polaris.** Ne pas ajouter un ton vert manuellement sur un bouton primary.

## Garde-fous i18n

Tous les libellés de CTA passent par `t(locale, key)` — aucun texte hardcodé dans les composants.

## Fichiers concernés

- `shopify-app/app/routes/app._index.tsx` — Zone1 CTA, Zone2 gate
- `shopify-app/app/routes/app.niche-understanding.tsx` — boutons Analyser/Enregistrer/Valider
- `shopify-app/app/routes/app.priorities.tsx` — bouton Préparer cette action
- `shopify-app/app/routes/app.safe-apply.tsx` — boutons Valider/Prévisualiser/Publier/Refuser
- `shopify-app/app/routes/app.impact.tsx` — bouton Voir prochaines actions
