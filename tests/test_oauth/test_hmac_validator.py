from app.oauth.hmac_validator import compute_hmac, validate_hmac

SECRET = "test_client_secret"


def test_compute_hmac_returns_64_char_hex():
    result = compute_hmac({"shop": "test.myshopify.com", "code": "abc"}, SECRET)
    assert isinstance(result, str) and len(result) == 64


def test_validate_hmac_valid():
    params = {"shop": "test.myshopify.com", "code": "abc123", "state": "xyz"}
    params["hmac"] = compute_hmac(params, SECRET)
    assert validate_hmac(params, SECRET) is True


def test_validate_hmac_wrong_secret():
    params = {"shop": "test.myshopify.com", "code": "abc123", "hmac": "badhash"}
    assert validate_hmac(params, SECRET) is False


def test_validate_hmac_missing_returns_false():
    params = {"shop": "test.myshopify.com", "code": "abc123"}
    assert validate_hmac(params, SECRET) is False


def test_hmac_excludes_itself_from_computation():
    base = {"shop": "test.myshopify.com"}
    with_hmac = {**base, "hmac": "ignored_value"}
    assert compute_hmac(with_hmac, SECRET) == compute_hmac(base, SECRET)


def test_hmac_is_order_independent():
    a = compute_hmac({"shop": "s.myshopify.com", "code": "c", "state": "s"}, SECRET)
    b = compute_hmac({"state": "s", "code": "c", "shop": "s.myshopify.com"}, SECRET)
    assert a == b
