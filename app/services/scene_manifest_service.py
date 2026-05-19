import json
import re
import time
from urllib.parse import urljoin

from selenium.webdriver.remote.webdriver import WebDriver

from app.browser import open_url
from app.files import load_json_from_file, save_json_to_file
from app.paths import get_data_dir


AUDIO_DATA_URL_PATTERN = re.compile(
    r"^https://mynoise\.world/Data/(?P<folder>[^/?]+)/(?P<filename>[0-9][ab]\.ogg)(?:\?.*)?$",
    re.IGNORECASE,
)

EXPECTED_OGG_FILENAMES = [
    f"{track_number}{variant}.ogg"
    for track_number in range(10)
    for variant in ("a", "b")
]


def clear_performance_logs(driver: WebDriver) -> None:
    """Clear existing Chrome performance logs before opening a scene page."""
    try:
        driver.get_log("performance")
    except Exception:
        pass


def parse_audio_url(url: str) -> dict[str, str] | None:
    """Parse a myNoise .ogg URL into structured metadata."""
    clean_url = url.split("?", maxsplit=1)[0]
    match = AUDIO_DATA_URL_PATTERN.match(clean_url)

    if not match:
        return None

    folder = match.group("folder")
    filename = match.group("filename")
    base_url = clean_url.rsplit("/", maxsplit=1)[0] + "/"

    return {
        "url": clean_url,
        "base_url": base_url,
        "folder": folder,
        "filename": filename,
    }


def extract_request_event(entry: dict[str, object]) -> dict[str, object] | None:
    """Extract the nested CDP event from a Selenium performance log entry."""
    raw_message = entry.get("message")

    if not isinstance(raw_message, str):
        return None

    message = json.loads(raw_message)
    event = message.get("message")

    if not isinstance(event, dict):
        return None

    return event


def extract_audio_file_from_request_event(
    event: dict[str, object],
) -> dict[str, str] | None:
    """Extract an audio file from a Network.requestWillBeSent event."""
    if event.get("method") != "Network.requestWillBeSent":
        return None

    params = event.get("params")

    if not isinstance(params, dict):
        return None

    request = params.get("request")

    if not isinstance(request, dict):
        return None

    request_method = request.get("method")

    if request_method != "GET":
        return None

    url = request.get("url")

    if not isinstance(url, str):
        return None

    parsed_audio_file = parse_audio_url(url)

    if not parsed_audio_file:
        return None

    document_url = params.get("documentURL")

    if isinstance(document_url, str):
        parsed_audio_file["document_url"] = document_url

    return parsed_audio_file


def extract_audio_files_from_performance_logs(
    driver: WebDriver,
) -> list[dict[str, str]]:
    """Extract requested .ogg files from Selenium Chrome performance logs."""
    audio_files_by_url: dict[str, dict[str, str]] = {}

    for entry in driver.get_log("performance"):
        event = extract_request_event(entry)

        if not event:
            continue

        audio_file = extract_audio_file_from_request_event(event)

        if not audio_file:
            continue

        audio_files_by_url[audio_file["url"]] = audio_file

    return sorted(
        audio_files_by_url.values(),
        key=lambda f: (
            f["folder"],
            f["filename"],
            f["url"],
        ),
    )


def build_audio_folder_manifest(
    scene_manifests: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Infer server-side audio folders and expected .ogg files from scene usage."""
    folders_by_name: dict[str, dict[str, object]] = {}

    for scene_manifest in scene_manifests:
        audio_files = scene_manifest.get("audio_files", [])

        if not isinstance(audio_files, list):
            continue

        for audio_file in audio_files:
            if not isinstance(audio_file, dict):
                continue

            folder = audio_file.get("folder")
            base_url = audio_file.get("base_url")
            filename = audio_file.get("filename")

            if not isinstance(folder, str):
                continue

            if not isinstance(base_url, str):
                continue

            if not isinstance(filename, str):
                continue

            if folder not in folders_by_name:
                folders_by_name[folder] = {
                    "folder": folder,
                    "base_url": base_url,
                    "observed_files": set(),
                }

            observed_files = folders_by_name[folder]["observed_files"]

            if isinstance(observed_files, set):
                observed_files.add(filename)

    audio_folder_manifest: list[dict[str, object]] = []

    for folder_data in folders_by_name.values():
        folder = str(folder_data["folder"])
        base_url = str(folder_data["base_url"])
        observed_files = folder_data["observed_files"]

        if not isinstance(observed_files, set):
            observed_files = set()

        audio_folder_manifest.append(
            {
                "folder": folder,
                "base_url": base_url,
                "observed_files": sorted(observed_files),
                "inferred_files": EXPECTED_OGG_FILENAMES,
                "inferred_urls": [
                    urljoin(base_url, filename)
                    for filename in EXPECTED_OGG_FILENAMES
                ],
            }
        )

    return sorted(
        audio_folder_manifest,
        key=lambda audio_folder: str(audio_folder["folder"]),
    )


def build_scene_audio_manifest(driver: WebDriver) -> dict[str, object]:
    """Build a manifest of .ogg audio files used by each soundscape scene."""
    input_file = get_data_dir() / "manifest" / "index_manifest.json"
    output_file = get_data_dir() / "manifest" / "scene_audio_manifest.json"

    index_manifest = load_json_from_file(input_file)

    if not isinstance(index_manifest, list):
        raise RuntimeError(f"Expected a list in {input_file}")

    scene_manifests: list[dict[str, object]] = []

    for index, scene in enumerate(index_manifest, start=1):
        if not isinstance(scene, dict):
            continue

        name = str(scene.get("name", "")).strip()
        url = str(scene.get("url", "")).strip()

        if not url:
            continue

        print(f"[{index}/{len(index_manifest)}] Capturing audio files for: {name}")

        clear_performance_logs(driver)
        open_url(driver, url)

        # Some audio requests happen shortly after document.readyState is complete.
        time.sleep(4)
