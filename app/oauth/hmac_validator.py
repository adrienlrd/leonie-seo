import base64
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


def verify_webhook_hmac(body: bytes, header_hmac: str | None, client_secret: str) -> bool:
    """Verify a Shopify webhook signature: base64(HMAC-SHA256(secret, raw_body)).

    Args:
        body: Raw request body bytes.
        header_hmac: Value of the X-Shopify-Hmac-Sha256 header.
        client_secret: App client secret from env.

    Returns:
        True if the signature is valid.
    """
    if not header_hmac:
        return False
    digest = hmac_lib.new(client_secret.encode(), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac_lib.compare_digest(expected, header_hmac)
