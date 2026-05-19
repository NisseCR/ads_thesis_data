import json
import re
import time

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


def extract_audio_files_from_performance_logs(
    driver: WebDriver,
) -> list[dict[str, str]]:
    """Extract requested myNoise .ogg files from Chrome performance logs."""
    audio_files_by_url: dict[str, dict[str, str]] = {}

    for entry in driver.get_log("performance"):
        message = json.loads(entry["message"])
        event = message.get("message", {})

        if event.get("method") != "Network.requestWillBeSent":
            continue

        params = event.get("params", {})
        request = params.get("request", {})

        if request.get("method") != "GET":
            continue

        url = request.get("url", "")

        parsed_audio_file = parse_audio_url(url)

        if parsed_audio_file:
            audio_files_by_url[parsed_audio_file["url"]] = parsed_audio_file

    return sorted(
        audio_files_by_url.values(),
        key=lambda audio_file: (
            audio_file["folder"],
            audio_file["filename"],
            audio_file["url"],
        ),
    )


def build_scene_audio_manifest(driver: WebDriver) -> None:
    """Build a manifest of .ogg audio files used by each soundscape scene."""
    input_file = get_data_dir() / "manifest" / "index_manifest.json"
    output_file = get_data_dir() / "manifest" / "scene_manifest.json"

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

        audio_files = extract_audio_files_from_performance_logs(driver)
        audio_folders = sorted(
            {
                audio_file["folder"]
                for audio_file in audio_files
            }
        )

        scene_manifests.append(
            {
                "name": name,
                "url": url,
                "category": scene.get("category"),
                "is_tonal": scene.get("is_tonal"),
                "audio_folders": audio_folders,
                "audio_files": audio_files,
            }
        )

        print(
            f"  Found {len(audio_files)} audio file request(s) "
            f"from {len(audio_folders)} folder(s)"
        )

    save_json_to_file(output_file, scene_manifests)

    print(f"Saved scene audio manifest to: {output_file.resolve()}")
