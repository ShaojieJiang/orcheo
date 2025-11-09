"""JWKS resolution tests split from the extended suite."""

from __future__ import annotations
import pytest
from orcheo_backend.app.authentication import (
    Authenticator,
    ServiceTokenManager,
    load_auth_settings,
)
from tests.backend.authentication_test_utils import reset_auth_state


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    yield from reset_auth_state(monkeypatch)


@pytest.mark.asyncio
async def test_match_fetched_key_with_mismatched_kid() -> None:
    """_match_fetched_key skips keys with mismatched kid."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm
    from orcheo_backend.app.authentication import Authenticator

    # Generate actual RSA keys for proper JWKS
    private_key1 = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key1 = private_key1.public_key()
    jwk1 = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key1, as_dict=True)
    jwk1["kid"] = "key1"
    jwk1["alg"] = "RS256"

    private_key2 = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key2 = private_key2.public_key()
    jwk2 = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key2, as_dict=True)
    jwk2["kid"] = "key2"
    jwk2["alg"] = "RS256"

    settings = load_auth_settings(refresh=True)
    from orcheo_backend.app.service_token_repository import (
        InMemoryServiceTokenRepository,
    )

    repository = InMemoryServiceTokenRepository()
    token_manager = ServiceTokenManager(repository)
    authenticator = Authenticator(settings, token_manager)

    entries = [jwk1, jwk2]
    jwt_auth = authenticator._jwt_authenticator  # noqa: SLF001

    # Try to match with kid that doesn't exist
    key = jwt_auth._match_fetched_key(entries, "key3", "RS256")  # noqa: SLF001

    assert key is None


@pytest.mark.asyncio
async def test_match_fetched_key_with_mismatched_algorithm() -> None:
    """_match_fetched_key skips keys with mismatched algorithm."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    jwk_dict = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key, as_dict=True)
    jwk_dict["kid"] = "test-kid"
    jwk_dict["alg"] = "RS256"

    settings = load_auth_settings(refresh=True)
    from orcheo_backend.app.service_token_repository import (
        InMemoryServiceTokenRepository,
    )

    repository = InMemoryServiceTokenRepository()
    token_manager = ServiceTokenManager(repository)
    authenticator = Authenticator(settings, token_manager)

    jwt_auth = authenticator._jwt_authenticator  # noqa: SLF001

    # Try to match with different algorithm
    key = jwt_auth._match_fetched_key([jwk_dict], "test-kid", "RS384")  # noqa: SLF001

    assert key is None


@pytest.mark.asyncio
async def test_match_fetched_key_with_non_mapping_entry() -> None:
    """_match_fetched_key handles entries that aren't mappings."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm
    from orcheo_backend.app.authentication import Authenticator

    # Generate actual RSA key for proper JWKS
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()
    jwk = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key, as_dict=True)
    jwk["kid"] = "key1"

    settings = load_auth_settings(refresh=True)
    from orcheo_backend.app.service_token_repository import (
        InMemoryServiceTokenRepository,
    )

    repository = InMemoryServiceTokenRepository()
    token_manager = ServiceTokenManager(repository)
    authenticator = Authenticator(settings, token_manager)

    entries = [
        jwk,
        "not-a-dict",  # Non-mapping
        123,  # Non-mapping
    ]
    jwt_auth = authenticator._jwt_authenticator  # noqa: SLF001

    # Should handle non-mapping gracefully
    key = jwt_auth._match_fetched_key(entries, "key1", None)  # noqa: SLF001

    # Should find the valid key
    assert key is not None
