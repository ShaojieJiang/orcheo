from orcheo.auth.sso import SsoAuthenticator, SsoProviderConfig


def test_sso_authenticator_validates_standard_claims() -> None:
    config = SsoProviderConfig(
        issuer="https://accounts.example.com",
        client_id="orcheo",
        jwks_url="https://accounts.example.com/.well-known/jwks.json",
    )
    authenticator = SsoAuthenticator(config)
    claims = {
        "iss": config.issuer,
        "aud": config.client_id,
        "email": "user@example.com",
    }
    assert authenticator.validate_claims(claims)
    assert not authenticator.validate_claims({"iss": "other", "aud": "orcheo"})
