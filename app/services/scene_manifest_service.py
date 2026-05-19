import json
import re
import time
from pathlib import Path
from typing import Any

from selenium.webdriver.remote.webdriver import WebDriver

from app.browser import open_url, wait_random_seconds
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


def get_scene_manifest_paths() -> tuple[Path, Path]:
    """Return the input index manifest path and output scene manifest path."""
    manifest_dir = get_data_dir() / "manifest"

    return (
        manifest_dir / "index_manifest.json",
        manifest_dir / "scene_manifest.json",
    )


def load_index_manifest(input_file: Path) -> list[object]:
    """Load and validate the index manifest from disk.

    Args:
        input_file: Path to the JSON index manifest file.

    Returns:
        The loaded index manifest as a list.

    Raises:
        RuntimeError: If the JSON file does not contain a list.
    """
    index_manifest = load_json_from_file(input_file)

    if not isinstance(index_manifest, list):
        raise RuntimeError(f"Expected a list in {input_file}")

    return index_manifest


def load_existing_scene_manifest(output_file: Path) -> list[dict[str, object]]:
    """Load existing scene manifest entries, or return an empty list if missing."""
    if not output_file.exists():
        return []

    scene_manifest = load_json_from_file(output_file)

    if not isinstance(scene_manifest, list):
        raise RuntimeError(f"Expected a list in {output_file}")

    return [
        scene
        for scene in scene_manifest
        if isinstance(scene, dict)
    ]


def get_scraped_scene_urls(scene_manifests: list[dict[str, object]]) -> set[str]:
    """Return normalized scene URLs already present in the scene manifest."""
    return {
        str(scene.get("url", "")).strip()
        for scene in scene_manifests
        if str(scene.get("url", "")).strip()
    }


def get_scene_name(scene: dict[str, object]) -> str:
    """Extract and normalize the scene name from an index manifest entry."""
    return str(scene.get("name", "")).strip()


def get_scene_url(scene: dict[str, object]) -> str:
    """Extract and normalize the scene URL from an index manifest entry."""
    return str(scene.get("url", "")).strip()


def clear_performance_logs(driver: WebDriver) -> None:
    """Clear existing Chrome performance logs before opening a scene page."""
    try:
        driver.get_log("performance")
    except Exception:
        pass


def parse_performance_log_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Parse a raw Chrome performance log entry into its event payload.

    Args:
        entry: A single item returned by Selenium's ``driver.get_log``.

    Returns:
        The nested Chrome DevTools Protocol event payload, or an empty dict if
        the entry cannot be parsed.
    """
    try:
        message = json.loads(entry["message"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return {}

    event = message.get("message", {})

    if not isinstance(event, dict):
        return {}

    return event


def is_get_request_event(event: dict[str, Any]) -> bool:
    """Return whether a performance log event represents a GET network request."""
    if event.get("method") != "Network.requestWillBeSent":
        return False

    params = event.get("params", {})

    if not isinstance(params, dict):
        return False

    request = params.get("request", {})

    if not isinstance(request, dict):
        return False

    return request.get("method") == "GET"


def get_request_url_from_event(event: dict[str, Any]) -> str:
    """Extract the request URL from a Chrome network request event."""
    params = event.get("params", {})

    if not isinstance(params, dict):
        return ""

    request = params.get("request", {})

    if not isinstance(request, dict):
        return ""

    return str(request.get("url", ""))


def parse_audio_url(url: str) -> dict[str, str] | None:
    """Parse a myNoise ``.ogg`` URL into structured audio-file metadata.

    Args:
        url: The requested URL captured from browser performance logs.

    Returns:
        A dictionary containing the clean URL, base URL, folder, and filename
        when the URL matches the expected myNoise audio format. Otherwise,
        returns ``None``.
    """
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


def sort_audio_files(audio_files: list[dict[str, str]]) -> list[dict[str, str]]:
    """Sort captured audio files by folder, filename, and URL."""
    return sorted(
        audio_files,
        key=lambda audio_file: (
            audio_file["folder"],
            audio_file["filename"],
            audio_file["url"],
        ),
    )


def extract_audio_files_from_performance_logs(
    driver: WebDriver,
) -> list[dict[str, str]]:
    """Extract requested myNoise ``.ogg`` files from Chrome performance logs.

    The browser may request the same audio file more than once. Results are
    deduplicated by cleaned URL before being sorted.
    """
    audio_files_by_url: dict[str, dict[str, str]] = {}

    for entry in driver.get_log("performance"):
        event = parse_performance_log_entry(entry)

        if not is_get_request_event(event):
            continue

        url = get_request_url_from_event(event)
        parsed_audio_file = parse_audio_url(url)

        if parsed_audio_file:
            audio_files_by_url[parsed_audio_file["url"]] = parsed_audio_file

    return sort_audio_files(list(audio_files_by_url.values()))


def capture_scene_audio_files(driver: WebDriver, url: str) -> list[dict[str, str]]:
    """Open a scene URL and capture the audio files requested by that page.

    Args:
        driver: Active Selenium WebDriver instance.
        url: Scene page URL to open.

    Returns:
        A sorted list of captured audio-file metadata dictionaries.
    """
    clear_performance_logs(driver)
    open_url(driver, url)
    wait_random_seconds(10, 25)

    return extract_audio_files_from_performance_logs(driver)


def get_audio_folders(audio_files: list[dict[str, str]]) -> list[str]:
    """Return the sorted unique audio folders referenced by captured audio files."""
    return sorted(
        {
            audio_file["folder"]
            for audio_file in audio_files
        }
    )


def build_scene_manifest_entry(
    scene: dict[str, object],
    name: str,
    url: str,
    audio_files: list[dict[str, str]],
) -> dict[str, object]:
    """Build a single scene manifest entry.

    Args:
        scene: Original index manifest scene entry.
        name: Normalized scene name.
        url: Normalized scene URL.
        audio_files: Captured audio-file metadata for the scene.

    Returns:
        A dictionary ready to be written to the scene manifest JSON file.
    """
    audio_folders = get_audio_folders(audio_files)

    return {
        "name": name,
        "url": url,
        "category": scene.get("category"),
        "is_tonal": scene.get("is_tonal"),
        "audio_folders": audio_folders,
        "audio_files": audio_files,
    }


def print_scene_capture_start(
    index: int,
    total_scenes: int,
    scene_name: str,
) -> None:
    """Print a progress message before capturing audio files for a scene."""
    print(f"[{index}/{total_scenes}] Capturing audio files for: {scene_name}")


def print_scene_capture_summary(audio_files: list[dict[str, str]]) -> None:
    """Print a short summary after capturing audio files for a scene."""
    audio_folders = get_audio_folders(audio_files)

    print(
        f"  Found {len(audio_files)} audio file request(s) "
        f"from {len(audio_folders)} folder(s)"
    )


def print_scene_already_scraped(
    index: int,
    total_scenes: int,
    scene_name: str,
) -> None:
    """Print a progress message when skipping an already scraped scene."""
    print(f"[{index}/{total_scenes}] Already scraped, skipping: {scene_name}")


def should_skip_scene(scene: object) -> bool:
    """Return whether an index manifest entry should be skipped."""
    if not isinstance(scene, dict):
        return True

    return not get_scene_url(scene)


def process_scene(
    driver: WebDriver,
    scene: dict[str, object],
    index: int,
    total_scenes: int,
) -> dict[str, object] | None:
    """Capture and build the manifest entry for a single scene.

    Args:
        driver: Active Selenium WebDriver instance.
        scene: One scene entry from the index manifest.
        index: One-based position of the scene in the index manifest.
        total_scenes: Total number of entries in the index manifest.

    Returns:
        A scene manifest dictionary, or ``None`` when the scene has no URL.
    """
    name = get_scene_name(scene)
    url = get_scene_url(scene)

    if not url:
        return None

    print_scene_capture_start(index, total_scenes, name)

    audio_files = capture_scene_audio_files(driver, url)
    scene_manifest = build_scene_manifest_entry(scene, name, url, audio_files)

    print_scene_capture_summary(audio_files)

    return scene_manifest


def build_scene_manifests(
    driver: WebDriver,
    index_manifest: list[object],
    output_file: Path,
) -> list[dict[str, object]]:
    """Build missing scene manifest entries and save progress after each scene."""
    scene_manifests = load_existing_scene_manifest(output_file)
    scraped_scene_urls = get_scraped_scene_urls(scene_manifests)

    for index, scene in enumerate(index_manifest, start=1):
        if should_skip_scene(scene):
            continue

        if not isinstance(scene, dict):
            continue

        name = get_scene_name(scene)
        url = get_scene_url(scene)

        if url in scraped_scene_urls:
            print_scene_already_scraped(index, len(index_manifest), name)
            continue

        scene_manifest = process_scene(
            driver=driver,
            scene=scene,
            index=index,
            total_scenes=len(index_manifest),
        )

        if scene_manifest:
            scene_manifests.append(scene_manifest)
            scraped_scene_urls.add(url)
            save_scene_manifest(output_file, scene_manifests)

    return scene_manifests


def save_scene_manifest(
    output_file: Path,
    scene_manifests: list[dict[str, object]],
) -> None:
    """Save scene manifest entries to disk and print the output path."""
    save_json_to_file(output_file, scene_manifests)


def build_scene_audio_manifest(driver: WebDriver) -> None:
    """Build a manifest of ``.ogg`` audio files used by each soundscape scene.

    This function orchestrates the full scene-manifest workflow:

    1. Load the existing index manifest.
    2. Visit each scene URL.
    3. Capture requested myNoise audio files from Chrome performance logs.
    4. Write the collected scene audio metadata to ``scene_manifest.json``.
    """
    input_file, output_file = get_scene_manifest_paths()
    index_manifest = load_index_manifest(input_file)
    scene_manifests = build_scene_manifests(driver, index_manifest, output_file)

    save_scene_manifest(output_file, scene_manifests)