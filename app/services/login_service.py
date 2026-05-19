from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.browser import open_url, wait_for_page_to_load, wait_random_seconds
from app.config import (
    ELEMENT_WAIT_SECONDS,
    INDEX_URL,
    LOGIN_EMAIL_SELECTOR,
    LOGIN_SUBMIT_SELECTOR,
    LOGIN_URL,
    LOGGED_IN_MARKER,
    LOGGED_OUT_MARKER,
    get_login_email,
)


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


def submit_email(driver: WebDriver) -> None:
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


def ensure_log_in(driver: WebDriver) -> None:
    """Open the index page and log in first if the current session is logged out."""
    open_url(driver, INDEX_URL)
    html = driver.page_source

    if is_logged_in_html(html):
        print("Already logged in.")
        return

    if is_logged_out_html(html):
        print("Not logged in yet. Logging in now.")
        submit_email(driver)
        open_url(driver, INDEX_URL)

        if not is_logged_in_html(driver.page_source):
            raise RuntimeError("Login completed, but the index page still appears logged out.")

        print("Logged in successfully.")
        return

    raise RuntimeError("Could not determine login state from the index page HTML.")