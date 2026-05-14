# AGENTS.md — leonie-seo

## 1. Project purpose

`leonie-seo` is a Shopify SEO automation project built first for `leoniedelacroix.com`, then intended to become a public Shopify App.

Current business context:

- Store: Léonie Delacroix
- Website: `https://www.leoniedelacroix.com`
- Shopify domain: `287c4a-bb.myshopify.com`
- Market: premium pet accessories for dogs and cats, with a French-made positioning where applicable
- Product types: dog/cat clothing, coats, pullovers, harnesses, fountains, scratching posts, design bowls, and related pet accessories
- SEO goal: grow qualified organic traffic and conversions through technical SEO, niche content, structured data, and measurable search performance improvements

Product vision:

> Niche-first Shopify SEO app: identify realistic long-tail opportunities from the merchant’s actual catalog, generate useful SEO content, apply it safely to Shopify, and measure the impact.

This is not a generic meta tag generator. The differentiator is:

- niche intelligence
- product-cluster detection
- keyword gaps
- SERP saturation analysis
- safe Shopify application
- measurable impact through GSC, GA4, and Shopify data

Target product:

- Public Shopify App Store app
- Embedded Shopify Admin app
- Merchant-reviewed recommendations
- Safe batch application
- Free/Pro/Agency pricing
- French and English support
- Infrastructure cost target: keep the early-stage MVP inexpensive and avoid unnecessary managed services

## 2. Source of truth

Do not use this file as the source of truth for current task status.

Use these files instead:

- `ROADMAP.md`: roadmap, task order, task status, completed work, upcoming work
- `PROGRESS.md`: latest working state, current blockers, last commands run, verification status, next recommended step
- `DECISIONS.md`: durable technical decisions and open decisions
- `CONTEXT.md`: market, competitors, strategic keywords, brand positioning
- `README.md`: human-facing setup and usage documentation when present

Rules:

- When the user asks to continue the roadmap, read `PROGRESS.md` first, then `ROADMAP.md`, then propose the next pending task.
- When the user gives an explicit task, prioritize that task over roadmap order.
- Do not assume that a module is implemented because this file mentions it. Verify in code, tests, `ROADMAP.md`, and `PROGRESS.md`.
- If `ROADMAP.md` and code disagree, trust the code and report the mismatch.
- If `PROGRESS.md` and `ROADMAP.md` disagree, inspect both and ask the user or make the smallest safe assumption.

## 3. Language rules

- Communicate with the user in French.
- Write code, comments, docstrings, commit messages, branch names, technical documentation, function names, class names, variables, and file names in English.
- Do not write French inside code comments or docstrings.
- Preserve French in user-facing French documentation, product copy, SEO content, merchant-facing UI text, emails, and marketing pages.
- Preserve English in user-facing English documentation and UI text.

## 4. Start-of-session workflow

Before broad, risky, roadmap-related, architecture-changing, Shopify-writing, deployment, or App Store submission work:

1. Read `PROGRESS.md`.
2. Read `ROADMAP.md`.
3. Read the relevant files for the requested task.
4. Summarize current state in 3–6 bullets.
5. Propose a short implementation plan.
6. Wait for user approval before coding.

For small, low-risk, clearly scoped tasks:

- Act directly.
- Keep the diff minimal.
- Summarize what changed and how it was verified.

Examples of tasks that require a plan first:

- Changing architecture
- Adding or replacing dependencies
- Modifying Shopify write behavior
- Creating or changing billing behavior
- Changing GDPR handling
- Modifying database schema
- Adding async jobs
- Preparing App Store submission
- Refactoring multiple modules
- Touching production configuration
- Running destructive commands

Examples of tasks that do not require prior approval:

- Fixing a typo
- Updating a small test
- Fixing an obvious import error
- Formatting a file
- Improving a small doc section
- Reading files and reporting findings

## 5. Mandatory safety rules

These rules override normal implementation convenience.

### Shopify safety

- Dry-run is the default for all Shopify write scripts.
- Any real Shopify write must require an explicit `--apply` or equivalent.
- Never write to Shopify without human confirmation.
- Never modify product handles, collection handles, page handles, blog handles, or URL slugs unless the user explicitly asks and redirect handling is part of the plan.
- Never edit `theme.liquid` directly.
- Prefer Theme App Extensions, app blocks, metafields, metaobjects, or documented Shopify extension points.
- Before any Shopify mutation, review:
  - target store
  - affected resources
  - mutation type
  - rollback path
  - rate limits
  - dry-run output
  - user confirmation
- Use GraphQL Admin API for new Shopify Admin work.
- Use a currently supported Shopify Admin API version, configured in one central place.
- Do not hardcode Shopify store URLs, access tokens, API keys, secrets, customer data, or merchant private data.

### GDPR and privacy

- Any merchant-data storage must support required Shopify GDPR webhooks:
  - customer data request
  - customer data erasure
  - shop data erasure
- Store only the data needed for the feature.
- Avoid storing customer personal data unless strictly required.
- Do not log access tokens, secrets, authorization headers, cookies, customer personal data, or raw webhook secrets.
- Treat tenant data as isolated by default.

### Billing

- Production App Store billing must use Shopify Billing API.
- Do not implement a custom off-Shopify billing system for App Store production use.
- Billing changes require a plan and explicit user approval.

### External services

- Prefer official documentation for Shopify, Google, OpenAI, Cloudflare, Neon, Render, and other external services.
- Do not perform real external mutations unless the user explicitly asks.
- Use dry-run, preview, staging, or test mode when available.
- Keep API versions and external service assumptions centralized and easy to update.

## 6. Architecture rules

Use Clean Architecture unless a local module already follows another explicit pattern.

Expected dependency direction:

```text
presentation -> application/use cases -> domain
infrastructure -> application/use cases -> domain
domain -> no infrastructure dependencies