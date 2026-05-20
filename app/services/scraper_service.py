import asyncio
import random
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.files import load_json_from_file
from app.paths import get_data_dir


AUDIO_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "audio/ogg,audio/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
    "Referer": "https://mynoise.net/",
    "Origin": "https://mynoise.net",
    "Sec-Fetch-Dest": "audio",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
}

REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 3

# fetch one folder's audio files together,
# then take a substantial pause before moving to the next folder.
FOLDER_WAIT_SECONDS = 120
FOLDER_WAIT_JITTER_SECONDS = 30


def get_audio_scraper_paths() -> tuple[Path, Path]:
    """Return the audio manifest path and local audio output directory."""
    data_dir = get_data_dir()

    return (
        data_dir / "manifest" / "audio_manifest.json",
        data_dir / "audio",
    )


def load_audio_manifest(manifest_file: Path) -> list[dict[str, object]]:
    """Load and validate the audio manifest from disk."""
    audio_manifest = load_json_from_file(manifest_file)

    if not isinstance(audio_manifest, list):
        raise RuntimeError(f"Expected a list in {manifest_file}")

    return [
        folder_entry
        for folder_entry in audio_manifest
        if isinstance(folder_entry, dict)
    ]


def is_audio_folder_complete(
    folder_entry: dict[str, object],
    audio_output_dir: Path,
) -> bool:
    """Return True when every manifest-listed file for a folder exists locally."""
    folder = folder_entry.get("folder")
    audio_files = folder_entry.get("audio_files")

    if not isinstance(folder, str):
        return False

    if not isinstance(audio_files, list):
        return False

    valid_audio_files = [
        audio_file
        for audio_file in audio_files
        if isinstance(audio_file, dict)
    ]

    if not valid_audio_files:
        return False

    folder_output_dir = audio_output_dir / folder

    for audio_file in valid_audio_files:
        filename = audio_file.get("filename")

        if not isinstance(filename, str):
            return False

        output_file = folder_output_dir / filename

        if not output_file.exists():
            return False

        if output_file.stat().st_size <= 0:
            return False

    return True


def build_audio_request(url: str) -> Request:
    """Build a browser-like request for one audio file."""
    return Request(
        url=url,
        headers=AUDIO_REQUEST_HEADERS,
        method="GET",
    )


def download_audio_file_sync(url: str, output_file: Path) -> None:
    """Download one audio file synchronously.

    This function is intentionally synchronous because urllib is blocking.
    It is called through asyncio.to_thread so folder downloads can still run
    concurrently without adding a third-party async HTTP dependency.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    request = build_audio_request(url)

    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        status_code = getattr(response, "status", 200)

        if status_code >= 400:
            raise RuntimeError(f"HTTP {status_code} for {url}")

        if content_type and "audio" not in content_type and "ogg" not in content_type:
            print(f"Warning: unexpected content type for {url}: {content_type}")

        output_file.write_bytes(response.read())


async def download_audio_file(
    audio_file: dict[str, object],
    folder_output_dir: Path,
) -> bool:
    """Download one manifest audio file with retries.

    Returns True when the file exists locally after this call.
    """
    filename = audio_file.get("filename")
    url = audio_file.get("url")

    if not isinstance(filename, str) or not isinstance(url, str):
        print(f"Skipping malformed audio file entry: {audio_file}")
        return False

    output_file = folder_output_dir / filename

    if output_file.exists() and output_file.stat().st_size > 0:
        print(f"Skipping existing file: {output_file}")
        return True

    for attempt_number in range(1, MAX_RETRIES + 1):
        try:
            print(f"Downloading {url}")
            await asyncio.to_thread(download_audio_file_sync, url, output_file)
            return True

        except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
            if attempt_number == MAX_RETRIES:
                print(f"Failed after {MAX_RETRIES} attempt(s): {url} ({error})")
                return False

            wait_seconds = RETRY_BACKOFF_SECONDS * attempt_number
            print(
                f"Retrying {url} in {wait_seconds}s "
                f"after attempt {attempt_number}/{MAX_RETRIES}: {error}"
            )
            await asyncio.sleep(wait_seconds)

    return False


async def scrape_audio_folder(
    folder_entry: dict[str, object],
    audio_output_dir: Path,
) -> tuple[int, int]:
    """Download all audio files for one folder concurrently."""
    folder = folder_entry.get("folder")
    audio_files = folder_entry.get("audio_files")

    if not isinstance(folder, str):
        print(f"Skipping folder entry without valid folder name: {folder_entry}")
        return 0, 0

    if not isinstance(audio_files, list):
        print(f"Skipping {folder}: missing audio_files list")
        return 0, 0

    folder_output_dir = audio_output_dir / folder
    folder_output_dir.mkdir(parents=True, exist_ok=True)

    valid_audio_files = [
        audio_file
        for audio_file in audio_files
        if isinstance(audio_file, dict)
    ]

    print(f"\nScraping folder {folder}: {len(valid_audio_files)} file(s)")

    started_at = time.perf_counter()
    results = await asyncio.gather(
        *[
            download_audio_file(audio_file, folder_output_dir)
            for audio_file in valid_audio_files
        ]
    )
    elapsed_seconds = time.perf_counter() - started_at

    successful_count = sum(1 for result in results if result)
    total_count = len(valid_audio_files)

    print(
        f"Finished {folder}: {successful_count}/{total_count} file(s) "
        f"in {elapsed_seconds:.1f}s"
    )

    return successful_count, total_count


async def scrape_audio_folders_async(
    folder_wait_seconds: int = FOLDER_WAIT_SECONDS,
    folder_wait_jitter_seconds: int = FOLDER_WAIT_JITTER_SECONDS,
) -> None:
    """Scrape every audio folder from the audio manifest.

    Files within a folder are requested concurrently. Folders themselves are
    processed sequentially with a large wait between them.
    """
    manifest_file, audio_output_dir = get_audio_scraper_paths()
    audio_manifest = load_audio_manifest(manifest_file)

    total_successful_files = 0
    total_files = 0
    scraped_folder_count = 0

    for folder_index, folder_entry in enumerate(audio_manifest, start=1):
        folder = folder_entry.get("folder")

        if is_audio_folder_complete(folder_entry, audio_output_dir):
            print(
                f"Skipping complete folder: {folder} "
                f"({folder_index}/{len(audio_manifest)})"
            )
            continue

        successful_count, file_count = await scrape_audio_folder(
            folder_entry,
            audio_output_dir,
        )

        scraped_folder_count += 1
        total_successful_files += successful_count
        total_files += file_count

        has_remaining_incomplete_folder = any(
            not is_audio_folder_complete(next_folder_entry, audio_output_dir)
            for next_folder_entry in audio_manifest[folder_index:]
            if isinstance(next_folder_entry, dict)
        )

        if not has_remaining_incomplete_folder:
            continue

        jitter = random.randint(0, folder_wait_jitter_seconds)
        wait_seconds = folder_wait_seconds + jitter

        print(
            f"Waiting {wait_seconds}s before next incomplete folder "
            f"({folder_index}/{len(audio_manifest)} checked)..."
        )
        await asyncio.sleep(wait_seconds)

    print(
        f"\nAudio scraping complete: "
        f"{total_successful_files}/{total_files} newly checked file(s), "
        f"{scraped_folder_count} folder(s) scraped this run."
    )


def scrape_audio_folders(
    folder_wait_seconds: int = FOLDER_WAIT_SECONDS,
    folder_wait_jitter_seconds: int = FOLDER_WAIT_JITTER_SECONDS,
) -> None:
    """Synchronous entry point for scraping audio folders."""
    asyncio.run(
        scrape_audio_folders_async(
            folder_wait_seconds=folder_wait_seconds,
            folder_wait_jitter_seconds=folder_wait_jitter_seconds,
        )
    )