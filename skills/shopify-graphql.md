# Shopify GraphQL — Patterns sûrs et limites

> Référence pour les tâches 2, 20, 21, 22, 23. Lire avant tout appel en écriture.

---

## Rate Limiting

| Type | Limite | Stratégie |
|---|---|---|
| GraphQL Admin API | 1000 points/minute (Leaky Bucket) | Surveiller `extensions.cost.throttleStatus` |
| REST Admin API | 2 req/seconde | Non utilisé dans ce projet |
| Coût typique d'une requête | 1–10 points | Requêtes simples = 1pt, mutations bulk = 10pt+ |

Toujours lire `throttleStatus.currentlyAvailable` dans la réponse et attendre si < 100.

---

## Opérations INTERDITES (jamais modifier)

- `handle` des produits — change l'URL → 404 massif
- `id` de toute ressource
- `publishedAt` sans confirmation explicite (dépublier un produit = catastrophe)
- Suppression de variantes si une seule variante existe

---

## Queries de lecture (sans risque)

### Lister tous les produits
```graphql
query GetProducts($cursor: String) {
  products(first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        title
        handle
        seo { title description }
        images(first: 10) {
          edges { node { id url altText } }
        }
      }
    }
  }
}
```

### Lister toutes les collections
```graphql
query GetCollections($cursor: String) {
  collections(first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        title
        handle
        seo { title description }
      }
    }
  }
}
```

---

## Mutations d'écriture (dry-run obligatoire)

### Mettre à jour SEO d'un produit
```graphql
mutation UpdateProductSEO($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      seo { title description }
    }
    userErrors { field message }
  }
}
```
Variables : `{ "input": { "id": "gid://shopify/Product/123", "seo": { "title": "...", "description": "..." } } }`

### Mettre à jour l'alt text d'une image
```graphql
mutation UpdateImageAltText($productId: ID!, $images: [ImageInput!]!) {
  productUpdateMedia(productId: $productId, media: $images) {
    media { ... on MediaImage { image { altText } } }
    userErrors { field message }
  }
}
```

### Créer une redirection 301
```graphql
mutation CreateRedirect($redirect: UrlRedirectInput!) {
  urlRedirectCreate(urlRedirect: $redirect) {
    urlRedirect { id path target }
    userErrors { field message }
  }
}
```
Variables : `{ "redirect": { "path": "/ancien-slug", "target": "/products/nouveau-handle" } }`

---

## Pagination

Toujours paginer avec le pattern cursor-based :
```python
cursor = None
while True:
    data = query(cursor=cursor)
    process(data["edges"])
    if not data["pageInfo"]["hasNextPage"]:
        break
    cursor = data["pageInfo"]["endCursor"]
```

---

## Gestion des erreurs

- `userErrors` dans la réponse = erreur métier Shopify (champ invalide, permission manquante)
- Status HTTP 429 = rate limit atteint → attendre `Retry-After` secondes
- Status HTTP 402 = feature non disponible sur le plan Shopify

---

## Headers obligatoires

```python
headers = {
    "X-Shopify-Access-Token": os.getenv("SHOPIFY_ACCESS_TOKEN"),
    "Content-Type": "application/json",
}
endpoint = f"https://{os.getenv('SHOPIFY_STORE_DOMAIN')}/admin/api/2025-01/graphql.json"
```
