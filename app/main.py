import json
import os
from pathlib import Path
import time
import random

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# Scraper config
PAGE_LOAD_WAIT_SECONDS = 15
ELEMENT_WAIT_SECONDS = 10

# .env variables
EMAIL_ENV_VAR = "MYNOISE_EMAIL"

# URLs
HOME_URL = "https://mynoise.net/noiseMachines.php"
LOGIN_URL = "https://mynoise.net/login.php"

# CSS selectors
LOGIN_EMAIL_SELECTOR = 'input[name="email"]'
LOGIN_SUBMIT_SELECTOR = 'input[type="submit"][value="Log In"].submit'

LOGGED_IN_MARKER = "/logout_script.php"
LOGGED_OUT_MARKER = "/login.php"


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


def save_text_to_file(file_path: Path, text: str) -> None:
    """Write text content to a file, creating parent directories if needed."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(text, encoding="utf-8")


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


def create_chrome_options() -> Options:
    """Create and configure Chrome browser options for the Selenium session."""
    options = Options()
    options.add_argument("--window-size=1920,1080")

    profile_path = get_browser_profile_path()
    profile_path.mkdir(parents=True, exist_ok=True)

    options.add_argument(f"--user-data-dir={profile_path}")

    return options


def create_driver() -> WebDriver:
    """Create and return a Selenium Chrome WebDriver instance."""
    return webdriver.Chrome(options=create_chrome_options())


def wait_for_page_to_load(driver: WebDriver) -> None:
    """Wait until the browser reports that the current page has fully loaded."""
    wait = WebDriverWait(driver, PAGE_LOAD_WAIT_SECONDS)
    wait.until(
        lambda current_driver: current_driver.execute_script(
            "return document.readyState"
        )
        == "complete"
    )


def wait_random_seconds(min_seconds: float = 1, max_seconds: float = 3) -> None:
    """Pause execution for a random duration between min_seconds and max_seconds."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def find_login_email_input(driver: WebDriver) -> WebElement:
    """Find the email input field on the login page."""
    wait = WebDriverWait(driver, ELEMENT_WAIT_SECONDS)
    return wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, LOGIN_EMAIL_SELECTOR))
    )


def find_login_submit_button(driver: WebDriver) -> WebElement:
    """Find the login form submit button."""
    wait = WebDriverWait(driver, ELEMENT_WAIT_SECONDS)
    return wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, LOGIN_SUBMIT_SELECTOR))
    )


def is_login_form_available(driver: WebDriver) -> bool:
    """Return True if the login form is present on the current page."""
    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, LOGIN_SUBMIT_SELECTOR))
        )
        return True
    except TimeoutException:
        return False


def login(driver: WebDriver) -> None:
    """Open the login page, enter the configured email, and submit the login form."""
    driver.get(LOGIN_URL)
    wait_for_page_to_load(driver)
    wait_random_seconds()

    if not is_login_form_available(driver):
        print("Login form was not found. Existing cookies/session may already be valid.")
        return

    email_input = find_login_email_input(driver)
    email_input.clear()
    email_input.send_keys(get_login_email())
    wait_random_seconds()

    submit_button = find_login_submit_button(driver)
    submit_button.click()

    wait_for_page_to_load(driver)


def index_scenes(driver: WebDriver) -> None:
    """Scrape the index page for scene information."""
    driver.get(HOME_URL)


def main():
    load_environment()
    driver = create_driver()

    try:
        # login(driver)
        index_scenes(driver)

        html = driver.page_source
        save_text_to_file(get_data_dir() / "home_logged_in.html", html)

    finally:
        time.sleep(200)
        driver.quit()