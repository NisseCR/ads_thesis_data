from app.browser import create_driver
from app.config import load_environment
from app.files import save_text_to_file
from app.paths import get_data_dir
from app.services.login_service import ensure_log_in
from app.services.manifest_service import build_soundscape_manifest


def main() -> None:
    load_environment()
    driver = create_driver()

    try:
        ensure_log_in(driver)
        build_soundscape_manifest(driver)

        html = driver.page_source
        save_text_to_file(get_data_dir() / "html" / "index.html", html)

    finally:
        driver.quit()