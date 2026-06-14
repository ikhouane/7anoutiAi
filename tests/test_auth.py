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


def test_shop_onboarding_uses_atomic_rpc(monkeypatch):
    captured = {}
    state = {
        auth.AUTH_SESSION_KEY: {
            "user": {
                "id": "user-1",
                "email": "owner@example.com",
            }
        }
    }
    expected_profile = {
        "id": "user-1",
        "shop_id": "shop-1",
        "full_name": "Owner",
        "role": "owner",
        "shop_name": "My Hanout",
    }

    class FakeRpc:
        def execute(self):
            return SimpleNamespace(data=[expected_profile.copy()])

    class FakeClient:
        def rpc(self, function_name, parameters):
            captured["function_name"] = function_name
            captured["parameters"] = parameters
            return FakeRpc()

    monkeypatch.setattr(
        auth,
        "get_authenticated_client",
        lambda current_state: FakeClient(),
    )

    result = auth.create_shop_and_profile(
        " My Hanout ",
        " Owner ",
        state,
    )

    assert captured == {
        "function_name": "onboard_shop",
        "parameters": {
            "p_shop_name": "My Hanout",
            "p_full_name": "Owner",
        },
    }
    assert result == expected_profile
    assert state[auth.PROFILE_SESSION_KEY] == expected_profile
