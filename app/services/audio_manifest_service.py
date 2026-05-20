from pathlib import Path

from app.files import load_json_from_file, save_json_to_file
from app.paths import get_data_dir


EXPECTED_OGG_FILENAMES = [
    f"{track_number}{variant}.ogg"
    for track_number in range(10)
    for variant in ("a", "b")
]


def get_audio_manifest_paths() -> tuple[Path, Path]:
    """Return the input scene manifest path and output audio manifest path."""
    manifest_dir = get_data_dir() / "manifest"

    return (
        manifest_dir / "scene_manifest.json",
        manifest_dir / "audio_manifest.json",
    )


def load_scene_manifest(input_file: Path) -> list[dict[str, object]]:
    """Load and validate the scene manifest from disk."""
    scene_manifest = load_json_from_file(input_file)

    if not isinstance(scene_manifest, list):
        raise RuntimeError(f"Expected a list in {input_file}")

    return [
        scene
        for scene in scene_manifest
        if isinstance(scene, dict)
    ]


def collect_audio_folders(
    scene_manifests: list[dict[str, object]],
) -> dict[str, str]:
    """Collect unique audio folders and their base URLs from scene manifest entries."""
    folders_by_name: dict[str, str] = {}

    for scene_manifest in scene_manifests:
        audio_files = scene_manifest.get("audio_files", [])

        if not isinstance(audio_files, list):
            continue

        for audio_file in audio_files:
            if not isinstance(audio_file, dict):
                continue

            folder = audio_file.get("folder")
            base_url = audio_file.get("base_url")

            if not isinstance(folder, str):
                continue

            if not isinstance(base_url, str):
                continue

            folders_by_name[folder] = base_url

    return folders_by_name


def build_audio_file_entry(base_url: str, filename: str) -> dict[str, str]:
    """Build a single inferred audio file manifest entry."""
    return {
        "filename": filename,
        "url": f"{base_url}{filename}",
    }


def infer_audio_files(base_url: str) -> list[dict[str, str]]:
    """Infer all expected audio files for a folder using expected .ogg filenames."""
    return [
        build_audio_file_entry(base_url, filename)
        for filename in EXPECTED_OGG_FILENAMES
    ]


def build_audio_folder_entry(folder: str, base_url: str) -> dict[str, object]:
    """Build a manifest entry for one audio folder."""
    return {
        "folder": folder,
        "base_url": base_url,
        "audio_files": infer_audio_files(base_url),
    }


def build_audio_folder_manifest(
    scene_manifests: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Infer server-side audio folders and expected .ogg files from scene usage."""
    folders_by_name = collect_audio_folders(scene_manifests)

    return [
        build_audio_folder_entry(folder, folders_by_name[folder])
        for folder in sorted(folders_by_name)
    ]


def save_audio_manifest(
    output_file: Path,
    audio_folder_manifest: list[dict[str, object]],
) -> None:
    """Save the audio manifest to disk."""
    save_json_to_file(output_file, audio_folder_manifest)


def print_audio_manifest_summary(
    audio_folder_manifest: list[dict[str, object]],
) -> None:
    """Print how many folders and audio files were inferred."""
    folder_count = len(audio_folder_manifest)
    audio_file_count = sum(
        len(audio_folder.get("audio_files", []))
        for audio_folder in audio_folder_manifest
        if isinstance(audio_folder.get("audio_files", []), list)
    )

    print(
        f"Inferred {folder_count} audio folder(s) "
        f"and {audio_file_count} audio file(s)."
    )


def build_audio_manifest() -> None:
    """Build an audio manifest from the captured scene manifest.

    The generated manifest contains one entry per unique audio folder. Each folder
    includes inferred URLs for all expected `.ogg` files.
    """
    input_file, output_file = get_audio_manifest_paths()
    scene_manifests = load_scene_manifest(input_file)
    audio_folder_manifest = build_audio_folder_manifest(scene_manifests)

    save_audio_manifest(output_file, audio_folder_manifest)
    print_audio_manifest_summary(audio_folder_manifest)