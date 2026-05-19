from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium.webdriver.remote.webdriver import WebDriver

from app.browser import open_url
from app.config import INDEX_URL
from app.files import save_json_to_file
from app.paths import get_data_dir


def extract_soundscape_metadata(html: str) -> list[dict[str, object]]:
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
                is_tonal = (
                    scene_container.select_one('i[alt="tone"][onclick*="TON"]')
                    is not None
                )

            scenes.append(
                {
                    "name": link.get_text(strip=True),
                    "url": absolute_url,
                    "category": category,
                    "is_tonal": is_tonal,
                }
            )

    return scenes


def build_index_manifest(driver: WebDriver) -> None:
    """Scrape the index page and save all available soundscape metadata."""
    open_url(driver, INDEX_URL)

    index_manifest = extract_soundscape_metadata(driver.page_source)
    output_file = get_data_dir() / "manifest" / "index_manifest.json"

    save_json_to_file(output_file, index_manifest)

    print(
        f"Saved {len(index_manifest)} soundscapes "
        f"to: {output_file.resolve()}"
    )