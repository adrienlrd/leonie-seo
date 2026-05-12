# SEO Technique — Règles d'audit et seuils

> Référence pour les tâches 6, 7, 8, 9, 10, 11. Vérifier ces seuils avant tout scoring.

---

## Meta titles

| Critère | Seuil | Sévérité |
|---|---|---|
| Longueur idéale | 50–60 caractères | Info |
| Trop court | < 30 caractères | Haute |
| Trop long | > 65 caractères | Moyenne |
| Manquant | Absent | Critique |
| Dupliqué | Même title sur 2+ pages | Haute |
| Sans mot-clé cible | Title générique | Moyenne |

## Meta descriptions

| Critère | Seuil | Sévérité |
|---|---|---|
| Longueur idéale | 120–155 caractères | Info |
| Trop courte | < 80 caractères | Moyenne |
| Trop longue | > 160 caractères | Faible |
| Manquante | Absente | Haute |
| Dupliquée | Même desc sur 2+ pages | Haute |

## Images et alt text

| Critère | Seuil | Sévérité |
|---|---|---|
| Alt text manquant | Absent sur image produit | Haute |
| Alt text vide (`alt=""`) | Acceptable si décoratif | Info |
| Alt text trop long | > 125 caractères | Faible |
| Alt text générique | "image1.jpg", "photo" | Moyenne |

## Core Web Vitals (PageSpeed)

| Métrique | Bon | À améliorer | Mauvais |
|---|---|---|---|
| LCP (Largest Contentful Paint) | ≤ 2.5s | 2.5–4s | > 4s |
| INP (Interaction to Next Paint) | ≤ 200ms | 200–500ms | > 500ms |
| CLS (Cumulative Layout Shift) | ≤ 0.1 | 0.1–0.25 | > 0.25 |
| Score Performance mobile | ≥ 80 | 50–79 | < 50 |
| Score Performance desktop | ≥ 90 | 70–89 | < 70 |

## Duplicate content Shopify

Shopify génère deux URLs pour chaque produit :
- Canonique : `/products/[handle]`
- Dupliquée : `/collections/[collection]/products/[handle]`

Règle : la balise `<link rel="canonical">` doit pointer vers `/products/[handle]` sur toutes les pages produit. Vérifier que Shopify l'a bien injecté (généralement automatique sur les thèmes récents).

## Redirections

| Problème | Sévérité |
|---|---|
| Redirection en chaîne (A→B→C) | Haute — consolider en A→C |
| Boucle de redirection (A→B→A) | Critique |
| Page 404 liée depuis le site | Critique |
| Redirection 302 au lieu de 301 | Moyenne (perte PageRank) |

## Scoring global SEO (0–100)

| Composant | Poids |
|---|---|
| Meta titles (présence + longueur) | 20% |
| Meta descriptions (présence + longueur) | 15% |
| Alt texts images | 15% |
| Core Web Vitals (LCP + CLS) | 25% |
| Redirections + 404 | 15% |
| Duplicate content | 10% |

Formule : `score = Σ(composant_score × poids)` où `composant_score` = ratio pages conformes / total pages.

## URLs Shopify à auditer (priorité décroissante)

1. Homepage `/`
2. Pages collections `/collections/[handle]`
3. Pages produits `/products/[handle]`
4. Pages blog `/blogs/[handle]/[article]`
5. Pages statiques `/pages/[handle]`
