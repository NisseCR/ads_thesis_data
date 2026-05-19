def build_audio_folder_manifest(
    scene_manifests: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Infer server-side audio folders and expected .ogg files from scene usage."""
    folders_by_name: dict[str, dict[str, object]] = {}

    for scene_manifest in scene_manifests:
        audio_files = scene_manifest.get("audio_files", [])

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

        audio_folder_manifest.append(
            {
                "folder": folder,
                "base_url": base_url
            }
        )

    return sorted(
        audio_folder_manifest,
        key=lambda audio_folder: str(audio_folder["folder"]),
    )