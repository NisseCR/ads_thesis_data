import json
import os
from pathlib import Path
import time
import random
from urllib.parse import urljoin

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
INDEX_URL = "https://mynoise.net/noiseMachines.php"
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


def save_json_to_file(file_path: Path, data: object) -> None:
    """Write JSON data to a file, creating parent directories if needed."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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


def wait_random_seconds(min_seconds: float = 1, max_seconds: float = 2) -> None:
    """Pause execution for a random duration between min_seconds and max_seconds."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def open_url(driver: WebDriver, url: str) -> None:
    """Open a URL and wait until the page has fully loaded."""
    driver.get(url)
    wait_for_page_to_load(driver)
    wait_random_seconds()


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
    open_url(driver, LOGIN_URL)

    if not is_login_form_available(driver):
        print("Login form was not found. Existing cookies/session may already be valid.")
        return

    # Clear the email input field and enter the configured email.
    email_input = find_login_email_input(driver)
    email_input.clear()
    email_input.send_keys(get_login_email())
    wait_random_seconds()

    # Submit the login form.
    submit_button = find_login_submit_button(driver)
    submit_button.click()

    # Wait for the login form to load.
    wait_for_page_to_load(driver)
    wait_random_seconds()


def is_logged_in_html(html: str) -> bool:
    """Return True if the index page HTML indicates an authenticated session."""
    return LOGGED_IN_MARKER in html


def is_logged_out_html(html: str) -> bool:
    """Return True if the index page HTML indicates the user still needs to log in."""
    return LOGGED_OUT_MARKER in html and LOGGED_IN_MARKER not in html


def open_index_page_logged_in(driver: WebDriver) -> None:
    """Open the index page and log in first if the current session is logged out."""
    open_url(driver, INDEX_URL)
    html = driver.page_source

    if is_logged_in_html(html):
        print("Already logged in.")
        return

    if is_logged_out_html(html):
        print("Not logged in yet. Logging in now.")
        login(driver)
        open_url(driver, INDEX_URL)

        if not is_logged_in_html(driver.page_source):
            raise RuntimeError("Login completed, but the index page still appears logged out.")

        print("Logged in successfully.")
        return

    raise RuntimeError("Could not determine login state from the index page HTML.")


def extract_soundscape_manifest(html: str) -> list[dict[str, object]]:
    """Extract soundscape metadata from the index page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    scenes: list[dict[str, object]] = []
    seen_urls: set[str] = set()

    for section in soup.select("div.generator-list"):
        category_heading = section.find("h1")
        category = category_heading.get_text(strip=True) if category_heading else None

        for link in section.select('a[href^="/NoiseMachines/"]'):
            href = link.get("href")

            if not href:
                continue

            absolute_url = urljoin(INDEX_URL, href)

            if absolute_url in seen_urls:
                continue

            seen_urls.add(absolute_url)

            scene_container = link.find_parent("span")
            is_tonal = False

            if scene_container:
                is_tonal = scene_container.select_one(
                    'i[alt="tone"][onclick*="TON"]'
                ) is not None

            scenes.append(
                {
                    "name": link.get_text(strip=True),
                    "url": absolute_url,
                    "category": category,
                    "is_tonal": is_tonal,
                }
            )

    return scenes


def build_soundscape_manifest(driver: WebDriver) -> None:
    """Scrape the index page and save all available soundscape metadata."""
    open_index_page_logged_in(driver)

    soundscape_manifest = extract_soundscape_manifest(driver.page_source)
    output_file = get_data_dir() / "manifest" / "soundscape_manifest.json"

    save_json_to_file(output_file, soundscape_manifest)

    print(
        f"Saved {len(soundscape_manifest)} soundscapes "
        f"to: {output_file.resolve()}"
    )


def main():
    load_environment()
    driver = create_driver()

    try:
        build_soundscape_manifest(driver)

        html = driver.page_source
        save_text_to_file(get_data_dir() / "html" / "index.html", html)

    finally:
        driver.quit()