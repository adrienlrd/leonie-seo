"""Shared Google OAuth scopes for Search Console + Analytics.

GSC and GA4 store ONE token row per shop (shared ``google_tokens`` table). If each
consent flow requested only its own scope, connecting one would overwrite the
token with a narrower scope set and the other API would start returning HTTP 403
"insufficient authentication scopes". Both flows therefore request the SAME union
of scopes, so a single consent yields one token valid for both APIs.
"""

from __future__ import annotations

GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]
