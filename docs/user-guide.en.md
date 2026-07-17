# User Guide — GEO by Organically

## Table of contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Getting started — CLI mode](#getting-started--cli-mode)
5. [Embedded Shopify App](#embedded-shopify-app)
6. [CLI reference](#cli-reference)
7. [Plans](#plans)
8. [FAQ](#faq)

---

## Overview

GEO by Organically automates SEO auditing for your Shopify store. It:

- Crawls your catalog (products, collections, meta fields)
- Fetches Google Search Console data (positions, clicks, impressions)
- Measures Core Web Vitals via PageSpeed Insights
- Detects high-priority SEO issues (missing meta, absent alt text, duplicate tags…)
- Generates a weekly Markdown report with ready-to-apply fixes
- Pushes corrections directly to Shopify (with confirmation)

---

## Installation

### Prerequisites

- Python 3.11 or higher
- A Google Cloud account with Search Console enabled
- A Shopify Admin API token (Custom App or OAuth)

### Via pip

```bash
git clone https://github.com/adrienlrd/leonie-seo.git
cd leonie-seo
pip install -e .
```

### Via Docker

```bash
docker build -t leonie-seo .
docker run --rm --env-file .env leonie-seo --help
```

### Quick install script

```bash
curl -sSL https://raw.githubusercontent.com/adrienlrd/leonie-seo/main/install.sh | bash
```

---

## Configuration

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

### Required variables

| Variable | Description |
|---|---|
| `SHOPIFY_ACCESS_TOKEN` | Shopify Admin API token (`shpat_...`) |
| `SHOPIFY_STORE_DOMAIN` | myshopify domain (`xxx.myshopify.com`) |
| `PAGESPEED_API_KEY` | Google PageSpeed Insights API key |

### Web dashboard variables (OAuth)

| Variable | Description |
|---|---|
| `SHOPIFY_CLIENT_ID` | Your Shopify Partners app ID |
| `SHOPIFY_CLIENT_SECRET` | Your app secret |
| `SHOPIFY_SCOPES` | `read_products,write_products,read_content` |
| `APP_URL` | Public URL of your instance |

### Email alerts variables

| Variable | Description |
|---|---|
| `GMAIL_SENDER` | Gmail sender address |
| `GMAIL_APP_PASSWORD` | Gmail app password |
| `ALERT_EMAIL` | Alert recipient |

### License (Pro/Agency plans)

```env
LEONIE_API_KEY=LEO-...       # your license key
LICENSE_SECRET=...           # signing secret (provided with the key)
```

---

## Getting started — CLI mode

### 1. Run a full audit

```bash
# Crawl the Shopify catalog
leonie-seo audit crawl

# Google Search Console data (last 90 days)
leonie-seo audit gsc

# Core Web Vitals
leonie-seo audit pagespeed

# Detect SEO issues
leonie-seo audit detect
```

### 2. Generate the report

```bash
leonie-seo report weekly
```

The report is created at `reports/YYYY-MM-DD/report.md`. It contains:
- Global SEO score with per-component breakdown
- Issues sorted by severity (critical / high / medium / low)
- Suggested fixes with estimated impact

### 3. Apply fixes

**All apply scripts run in dry-run mode by default.**

```bash
# Preview meta fixes
leonie-seo apply meta --dry-run

# Apply after review
leonie-seo apply meta --apply

# Image alt text
leonie-seo apply alt --dry-run
leonie-seo apply alt --apply

# 301 redirects from a validated CSV
leonie-seo apply redirects --file data/raw/redirects.csv --dry-run
leonie-seo apply redirects --file data/raw/redirects.csv --apply
```

---

## Embedded Shopify App

> **Recommended distribution mode** for Shopify merchants: GEO by Organically is embedded in the Shopify Admin (App Bridge + Polaris) via the Remix scaffold in `shopify-app/`.

### Python backend (FastAPI)

```bash
# Start the Python backend (port 8000)
uvicorn app.main:app --reload
```

### Embedded Remix app

```bash
cd shopify-app
npm install
npm run dev
```

The app connects to a Shopify development store via Shopify CLI. Full documentation for this layer lives in `shopify-app/README.md`.

### Distribution modes

| Mode | Audience | Authentication | Billing |
|---|---|---|---|
| **Shopify App Store** | Shopify merchants (multi-tenant) | Shopify OAuth | Shopify Billing API (`appSubscriptionCreate`) |
| **Self-hosted / CLI** | Internal use, agencies, devs | Custom App token | HMAC license `LEONIE_API_KEY` |

> The **legacy React dashboard** (`frontend/`) has been decommissioned in favour of the embedded Remix app — see `DECISIONS.md` 2026-05-10.

---

## CLI reference

```
leonie-seo
├── audit
│   ├── crawl          Shopify catalog snapshot
│   ├── gsc            Google Search Console data (90 days)
│   ├── pagespeed      Core Web Vitals (mobile + desktop)
│   ├── detect         Detect SEO issues
│   └── screaming      Parse Screaming Frog CSV export
├── apply
│   ├── meta           Update meta titles and descriptions
│   ├── alt            Update image alt text
│   ├── redirects      Create 301 redirects in bulk
│   ├── schema         Add JSON-LD Product structured data
│   └── rollback       Undo the last N changes
├── report
│   ├── weekly         Weekly Markdown report
│   ├── delta          Before/after comparison per page
│   ├── hreflang       Hreflang tags (BE/CH expansion)
│   ├── alerts         Detect regressions and send email
│   └── dashboard      Dashboard report
├── setup
│   ├── init           Initialize a new store/tenant
│   ├── list           List configured tenants
│   └── check          Check active configuration
└── license
    ├── issue          Generate a signed license key
    └── check          Validate the active license
```

---

## Plans

| Feature | Free | Pro | Agency |
|---|:---:|:---:|:---:|
| Audit (crawl, GSC, PageSpeed) | ✅ | ✅ | ✅ |
| Issue detection | ✅ | ✅ | ✅ |
| SEO score | ✅ | ✅ | ✅ |
| Markdown report | ❌ | ✅ | ✅ |
| Meta / alt text updates | ❌ | ✅ | ✅ |
| Hreflang (BE/CH expansion) | ❌ | ✅ | ✅ |
| Email alerts | ❌ | ✅ | ✅ |
| Number of stores | 1 | 1 | Unlimited |
| SQLite rollback | ❌ | ✅ | ✅ |

### Generate a license key

```bash
# Pro plan for one store, valid 1 year
leonie-seo license issue --tenant my-store --plan pro --days 365

# Agency plan for an agency
leonie-seo license issue --tenant my-agency --plan agency --days 365
```

Add the key to the client's `.env`:

```env
LEONIE_API_KEY=LEO-<generated key>
```

---

## FAQ

**Q: Will the tool modify my store without confirmation?**
No. All `apply` commands run in `--dry-run` mode by default. You must explicitly pass `--apply` to write to Shopify.

**Q: Does my Shopify data stay on my server?**
Yes. GEO by Organically is a self-hosted tool. Your access tokens and product data never leave your environment (local CLI or Docker server).

**Q: What happens when my license expires?**
The plan automatically falls back to Free. You keep access to audit features. Write features (apply, alerts, reports) are disabled.

**Q: Can I use the tool for multiple stores?**
Yes, with the Agency plan. Each store has its own `config/tenants/XXX.yaml` file.

**Q: How do I undo an applied change?**
```bash
leonie-seo apply rollback --last 5   # undo the last 5 changes
```
All changes are tracked in `data/history.db`.

**Q: Is the app compatible with all Shopify themes?**
Audit and meta/alt update features are universal. The hreflang Liquid snippet must be manually integrated into `theme.liquid`.

**Q: How do I contact support?**
Open an issue on the GitHub repository or email `support@leonie-seo.com`.
