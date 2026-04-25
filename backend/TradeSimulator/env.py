from pathlib import Path
import os

from dotenv import load_dotenv


TRUE_VALUES = {"1", "true", "yes", "on"}


def env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def load_optional_dotenv():
    """Load a dotenv file only when explicitly enabled by the caller."""
    if not env_flag("DJANGO_LOAD_DOTENV", default=False):
        return False

    dotenv_path = os.getenv("DJANGO_DOTENV_PATH")
    if dotenv_path:
        return load_dotenv(dotenv_path, override=False)

    base_dir = Path(__file__).resolve().parent.parent
    return load_dotenv(base_dir / ".env", override=False)
