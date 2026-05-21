# Safe Apply Narrative Simplification — Tâche 160

## Objectif

Le workflow "Améliorations proposées" doit être compris par un marchand sans explication externe. La promesse centrale est simple : **rien n'est publié sur votre boutique sans votre validation explicite.**

## Narration à 3 temps

```
1. PROPOSÉ     → Léonie a généré une amélioration. Elle attend votre avis.
2. PRÉVISUALISÉ → Vous pouvez voir ce que ça donnera sans publier.
3. PUBLIÉ      → Vous avez dit OK. La modification est live sur votre boutique.
   (ou REFUSÉ  → Vous avez dit Non. Rien n'a changé.)
```

## Mapping statuts internes → libellés marchands

| Statut interne | Libellé affiché | Badge tone |
|---|---|---|
| draft | En attente | info |
| needs_review | À valider | warning |
| approved | Validé | success |
| applied | Publié | success |
| rejected | Refusé | critical |

## Mapping types de contenu internes → libellés marchands

| Type interne | Libellé affiché |
|---|---|
| product_title | Titre produit |
| product_description | Description produit |
| meta_title | Titre SEO |
| meta_description | Description SEO |
| faq_product | FAQ produit |
| buying_guide | Guide d'achat |

## Boutons par état

| État de l'item | CTA primaire (vert) | CTA secondaire (neutre) | CTA destructif (discret) |
|---|---|---|---|
| draft / needs_review | "Valider" (accepter) | "Prévisualiser" | "Refuser" (plain + critique) |
| approved | "Publier" | "Prévisualiser" | "Annuler" (plain + critique) |
| applied | — | "Voir l'historique" | "Annuler cette modification" |

## Règles d'interface

1. **Bannière de sécurité permanente** en haut de page : "Aucune modification publiée sans votre validation."
2. **Aucun `tone="critical"` sur un bouton d'action positive** (Publier n'est pas critique).
3. **Erreurs techniques traduites** : "length_out_of_bounds" → "Texte trop long ou trop court".
4. **resource_id non exposé brut** — toujours précédé du libellé "Produit concerné :".
5. **content_type traduit** avant affichage.

## Fichier concerné

`shopify-app/app/routes/app.safe-apply.tsx`
