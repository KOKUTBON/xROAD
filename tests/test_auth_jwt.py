"""Exercise real JWKS signature and claim validation for API bearer tokens."""

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.api import auth
from apps.api.settings import ApiSettings


@pytest.fixture
def signed_token(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update(kid="test-key", alg="RS256", use="sig")
    monkeypatch.setattr(auth, "_load_jwks", lambda settings: {"keys": [jwk]})
    settings = ApiSettings(
        auth_issuer="https://sso.example.test",
        auth_audience="road-risk-api",
        auth_algorithms="RS256",
    )
    claims = {
        "sub": "synthetic-user",
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
        "exp": int(time.time()) + 300,
    }

    def encode(overrides=None, *, key=private_key, kid="test-key"):
        return jwt.encode(
            {**claims, **(overrides or {})}, key, algorithm="RS256", headers={"kid": kid}
        )

    return settings, claims, encode


def test_valid_jwks_token(signed_token):
    settings, claims, encode = signed_token
    assert auth._decode_token(encode(), settings) == claims


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": 1},
        {"aud": "another-api"},
        {"iss": "https://another.example.test"},
        {"nbf": int(time.time()) + 600},
    ],
)
def test_invalid_claims_are_rejected(signed_token, overrides):
    settings, _, encode = signed_token
    with pytest.raises(jwt.PyJWTError):
        auth._decode_token(encode(overrides), settings)


def test_invalid_signature_is_rejected(signed_token):
    settings, _, encode = signed_token
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(jwt.InvalidSignatureError):
        auth._decode_token(encode(key=other_key), settings)


def test_missing_jwks_key_is_rejected(signed_token):
    settings, _, encode = signed_token
    with pytest.raises(RuntimeError, match="matching key"):
        auth._decode_token(encode(kid="unknown"), settings)


def test_algorithm_allowlist_is_enforced(signed_token):
    settings, _, encode = signed_token
    settings.auth_algorithms = "ES256"
    with pytest.raises(jwt.InvalidAlgorithmError):
        auth._decode_token(encode(), settings)
