import random
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from app.config import PAGE_LOAD_WAIT_SECONDS
from app.paths import get_browser_profile_path


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