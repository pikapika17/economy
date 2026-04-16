import os


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


def env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None:
        return default
    values = [item.strip() for item in raw.split(",")]
    return [value for value in values if value]


SECRET_KEY = require_env("SECRET_KEY")

DB_HOST = require_env("DB_HOST")
DB_USER = require_env("DB_USER")
DB_PASSWORD = require_env("DB_PASSWORD")
DB_NAME = require_env("DB_NAME")

BOOTSTRAP_ADMIN = env_bool("BOOTSTRAP_ADMIN", default=False)
APP_USER = os.environ.get("APP_USER")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

ALLOWED_LANGUAGES = env_list("ALLOWED_LANGUAGES", ["pt", "en", "de", "es", "it", "pl", "ru", "fr"])
COMMON_CURRENCIES = env_list(
    "COMMON_CURRENCIES",
    ["CHF", "EUR", "USD", "GBP", "JPY", "CNY", "CAD", "AUD"],
)

FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = env_int("FLASK_PORT", 5000)
FLASK_DEBUG = env_bool("FLASK_DEBUG", default=False)