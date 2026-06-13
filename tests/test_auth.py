from types import SimpleNamespace

import auth


def test_signup_uses_configured_email_redirect(monkeypatch):
    captured = {}

    class FakeAuth:
        def sign_up(self, credentials):
            captured.update(credentials)
            return SimpleNamespace(
                user=SimpleNamespace(id="user-1", email="owner@example.com"),
                session=None,
            )

    monkeypatch.setattr(
        auth,
        "get_supabase_client",
        lambda: SimpleNamespace(auth=FakeAuth()),
    )
    monkeypatch.setattr(auth, "APP_URL", "https://shop.streamlit.app")

    result = auth.signup("Owner@Example.com", "secret1", {})

    assert captured == {
        "email": "owner@example.com",
        "password": "secret1",
        "options": {
            "email_redirect_to": "https://shop.streamlit.app",
        },
    }
    assert result["requires_email_confirmation"] is True
