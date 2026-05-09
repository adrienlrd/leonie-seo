import hashlib
import hmac as hmac_lib
from urllib.parse import urlencode


def compute_hmac(params: dict[str, str], client_secret: str) -> str:
    """Compute Shopify HMAC-SHA256 over sorted query params (excluding 'hmac')."""
    filtered = {k: v for k, v in params.items() if k != "hmac"}
    message = urlencode(sorted(filtered.items()))
    return hmac_lib.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validate_hmac(params: dict[str, str], client_secret: str) -> bool:
    """Return True if the 'hmac' param matches the computed HMAC."""
    provided = params.get("hmac", "")
    if not provided:
        return False
    expected = compute_hmac(params, client_secret)
    return hmac_lib.compare_digest(expected, provided)
