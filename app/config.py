import os

from dotenv import load_dotenv

from app.paths import get_env_file_path


# Scraper config
PAGE_LOAD_WAIT_SECONDS = 15
ELEMENT_WAIT_SECONDS = 10

# .env variables
EMAIL_ENV_VAR = "MYNOISE_EMAIL"

# URLs
INDEX_URL = "https://mynoise.net/noiseMachines.php"
LOGIN_URL = "https://mynoise.net/login.php"

# CSS selectors
LOGIN_EMAIL_SELECTOR = 'input[name="email"]'
LOGIN_SUBMIT_SELECTOR = 'input[type="submit"][value="Log In"].submit'

LOGGED_IN_MARKER = "/logout_script.php"
LOGGED_OUT_MARKER = "/login.php"


def load_environment() -> None:
    """Load environment variables from the project's .env file."""
    load_dotenv(dotenv_path=get_env_file_path())


def get_login_email() -> str:
    """Return the configured login email from the environment."""
    email = os.environ.get(EMAIL_ENV_VAR, "").strip()

    if not email:
        raise RuntimeError(
            f"Missing login email. Add {EMAIL_ENV_VAR}=your-email@example.com "
            "to the project's .env file."
        )

    return email