from __future__ import annotations

from typing import Any, MutableMapping

from config import APP_URL
from supabase_client import get_supabase_client


AUTH_SESSION_KEY = "supabase_auth_session"
PROFILE_SESSION_KEY = "supabase_profile"


def _friendly_error(action: str, exc: Exception) -> RuntimeError:
    message = str(exc).strip()
    lowered = message.lower()

    if "invalid login credentials" in lowered:
        message = "Invalid email or password."
    elif "email not confirmed" in lowered:
        message = "Please confirm your email before signing in."
    elif "user already registered" in lowered:
        message = "An account with this email already exists."
    elif "password" in lowered and "characters" in lowered:
        message = "The password does not meet Supabase password requirements."
    elif not message:
        message = "Supabase did not return an error message."

    return RuntimeError(f"{action} failed: {message}")


def _store_auth_response(
    response: Any,
    state: MutableMapping[str, Any],
) -> dict[str, Any]:
    user = getattr(response, "user", None)
    session = getattr(response, "session", None)
    if user is None:
        raise RuntimeError("Supabase did not return a user.")

    user_data = {
        "id": str(user.id),
        "email": user.email or "",
    }

    if session is None:
        state.pop(AUTH_SESSION_KEY, None)
        return {
            "user": user_data,
            "requires_email_confirmation": True,
        }

    state[AUTH_SESSION_KEY] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "user": user_data,
    }
    state.pop(PROFILE_SESSION_KEY, None)
    return {
        "user": user_data,
        "requires_email_confirmation": False,
    }


def login(
    email: str,
    password: str,
    state: MutableMapping[str, Any],
) -> dict[str, Any]:
    clean_email = email.strip().lower()
    if not clean_email or not password:
        raise ValueError("Email and password are required.")

    try:
        response = get_supabase_client().auth.sign_in_with_password(
            {"email": clean_email, "password": password}
        )
        return _store_auth_response(response, state)
    except ValueError:
        raise
    except Exception as exc:
        raise _friendly_error("Login", exc) from exc


def signup(
    email: str,
    password: str,
    state: MutableMapping[str, Any],
) -> dict[str, Any]:
    clean_email = email.strip().lower()
    if not clean_email or not password:
        raise ValueError("Email and password are required.")
    if len(password) < 6:
        raise ValueError("Password must contain at least 6 characters.")

    try:
        response = get_supabase_client().auth.sign_up(
            {
                "email": clean_email,
                "password": password,
                "options": {"email_redirect_to": APP_URL},
            }
        )
        return _store_auth_response(response, state)
    except ValueError:
        raise
    except Exception as exc:
        raise _friendly_error("Signup", exc) from exc


def get_authenticated_client(
    state: MutableMapping[str, Any],
) -> Any:
    session_data = state.get(AUTH_SESSION_KEY)
    if not session_data:
        raise RuntimeError("No active Supabase session.")

    try:
        client = get_supabase_client()
        response = client.auth.set_session(
            session_data["access_token"],
            session_data["refresh_token"],
        )
        if response.session is None or response.user is None:
            raise RuntimeError("Supabase could not restore the session.")

        state[AUTH_SESSION_KEY] = {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {
                "id": str(response.user.id),
                "email": response.user.email or "",
            },
        }
        return client
    except Exception as exc:
        state.pop(AUTH_SESSION_KEY, None)
        state.pop(PROFILE_SESSION_KEY, None)
        raise _friendly_error("Session restoration", exc) from exc


def get_logged_in_user(
    state: MutableMapping[str, Any],
) -> dict[str, Any] | None:
    session_data = state.get(AUTH_SESSION_KEY)
    return session_data.get("user") if session_data else None


def logout(state: MutableMapping[str, Any]) -> None:
    try:
        if state.get(AUTH_SESSION_KEY):
            get_authenticated_client(state).auth.sign_out()
    except Exception:
        # Local session removal must still work if Supabase is unavailable.
        pass
    finally:
        state.pop(AUTH_SESSION_KEY, None)
        state.pop(PROFILE_SESSION_KEY, None)


def get_user_profile(
    state: MutableMapping[str, Any],
) -> dict[str, Any] | None:
    cached_profile = state.get(PROFILE_SESSION_KEY)
    if cached_profile and cached_profile.get("shop_name"):
        return cached_profile

    user = get_logged_in_user(state)
    if user is None:
        return None

    try:
        client = get_authenticated_client(state)
        response = (
            client
            .table("profiles")
            .select("id, shop_id, full_name, role")
            .eq("id", user["id"])
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise _friendly_error("Profile loading", exc) from exc

    profile = response.data[0] if response.data else None
    if profile:
        try:
            shop_response = (
                client.table("shops")
                .select("name")
                .eq("id", profile["shop_id"])
                .limit(1)
                .execute()
            )
            profile["shop_name"] = (
                shop_response.data[0]["name"]
                if shop_response.data
                else "Unnamed shop"
            )
        except Exception as exc:
            raise _friendly_error("Shop loading", exc) from exc
        state[PROFILE_SESSION_KEY] = profile
    return profile


def create_shop_and_profile(
    shop_name: str,
    full_name: str,
    state: MutableMapping[str, Any],
) -> dict[str, Any]:
    clean_shop_name = shop_name.strip()
    clean_full_name = full_name.strip()
    if not clean_shop_name:
        raise ValueError("Shop name is required.")

    user = get_logged_in_user(state)
    if user is None:
        raise RuntimeError("You must be logged in to create a shop.")

    client = get_authenticated_client(state)
    try:
        shop_response = (
            client.table("shops")
            .insert({"name": clean_shop_name, "owner_id": user["id"]})
            .execute()
        )
        if not shop_response.data:
            raise RuntimeError("Supabase did not return the new shop.")

        shop = shop_response.data[0]
        profile_response = (
            client.table("profiles")
            .insert(
                {
                    "id": user["id"],
                    "shop_id": shop["id"],
                    "full_name": clean_full_name or None,
                    "role": "owner",
                }
            )
            .execute()
        )
        if not profile_response.data:
            raise RuntimeError("Supabase did not return the new profile.")
    except ValueError:
        raise
    except Exception as exc:
        raise _friendly_error("Shop onboarding", exc) from exc

    profile = profile_response.data[0]
    profile["shop_name"] = shop["name"]
    state[PROFILE_SESSION_KEY] = profile
    return profile
