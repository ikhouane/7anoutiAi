from __future__ import annotations

import os
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
DB_PATH = BASE_DIR / "data" / "hanout.db"

_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SUPPORTED_BACKENDS = {"sqlite", "supabase"}
_PLACEHOLDER_VALUES = {
    "",
    "your_app_url_here",
    "your_supabase_url_here",
    "your_supabase_anon_key_here",
}


def _load_local_env(path: Path = ENV_PATH) -> None:
    """Load simple KEY=VALUE pairs without replacing real environment values."""
    if not path.is_file():
        return

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise RuntimeError(
                f"Invalid .env entry on line {line_number}: expected KEY=VALUE."
            )

        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not _ENV_NAME_PATTERN.fullmatch(name):
            raise RuntimeError(
                f"Invalid environment variable name on .env line {line_number}."
            )
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(name, value)


def _read_setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


_load_local_env()

DATABASE_BACKEND = _read_setting("DATABASE_BACKEND", "sqlite").lower()
APP_URL = _read_setting("APP_URL", "http://localhost:8501").rstrip("/")
SUPABASE_URL = _read_setting("SUPABASE_URL")
SUPABASE_ANON_KEY = _read_setting("SUPABASE_ANON_KEY")

if DATABASE_BACKEND not in _SUPPORTED_BACKENDS:
    supported = ", ".join(sorted(_SUPPORTED_BACKENDS))
    raise RuntimeError(
        f"Unsupported DATABASE_BACKEND={DATABASE_BACKEND!r}. "
        f"Choose one of: {supported}."
    )

if DATABASE_BACKEND == "supabase":
    missing = [
        name
        for name, value in (
            ("APP_URL", APP_URL),
            ("SUPABASE_URL", SUPABASE_URL),
            ("SUPABASE_ANON_KEY", SUPABASE_ANON_KEY),
        )
        if value.lower() in _PLACEHOLDER_VALUES
    ]
    if missing:
        raise RuntimeError(
            "Supabase configuration is incomplete. Missing: "
            + ", ".join(missing)
            + ". Copy .env.example to .env for local use, or add these values "
            "to Streamlit Community Cloud secrets. Never commit real keys."
        )
