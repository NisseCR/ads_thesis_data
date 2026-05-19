from pathlib import Path


def get_project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    """Return the project's data directory."""
    return get_project_root() / "data"


def get_env_file_path() -> Path:
    """Return the path to the project's local .env file."""
    return get_project_root() / ".env"


def get_browser_profile_path() -> Path:
    """Return the local Chrome profile path used to preserve cookies."""
    return get_data_dir() / "chrome_profile"