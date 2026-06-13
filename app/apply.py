import hashlib
import os
from typing import Callable, Optional

from app import penumbra_group, scd_converter
from app.project import Playlist


class ApplyError(Exception):
    pass


ProgressCallback = Callable[[int, int, str], None]


def file_hash(path: str) -> str:
    """Cheap content fingerprint: size + mtime, falling back to sha1 if unavailable."""
    try:
        stat = os.stat(path)
        return f"{stat.st_size}:{int(stat.st_mtime)}"
    except OSError:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()


def _scd_output_path(target_scd_dir: str, index: int) -> str:
    return os.path.join(target_scd_dir, f"{index}.scd")


def apply_playlist(
    playlist: Playlist,
    ffmpeg_path: str = "ffmpeg",
    progress_cb: Optional[ProgressCallback] = None,
) -> None:
    """Convert all tracks, lay them out in target_scd_dir, and regenerate the group JSON.

    Tracks are skipped (cached) if their source_hash is unchanged and the previously
    converted .scd file already exists at its target slot.
    """
    if not playlist.target_scd_dir:
        raise ApplyError("Playlist has no target SCD directory configured.")
    if not playlist.target_group_json:
        raise ApplyError("Playlist has no target group JSON configured.")

    total = len(playlist.tracks)

    def report(i: int, message: str) -> None:
        if progress_cb:
            progress_cb(i, total, message)

    # Step 1: convert tracks (with caching), staging output bytes in memory.
    staged: list[bytes] = []
    for i, track in enumerate(playlist.tracks, start=1):
        if not os.path.exists(track.source_path):
            raise ApplyError(f"Track source not found: {track.source_path}")

        current_hash = file_hash(track.source_path)
        existing_path = _scd_output_path(playlist.target_scd_dir, i)
        if (
            track.source_hash == current_hash
            and os.path.exists(existing_path)
        ):
            report(i, f"Cached: {track.display_name}")
            with open(existing_path, "rb") as f:
                staged.append(f.read())
            continue

        report(i, f"Converting: {track.display_name}")
        scd_bytes = scd_converter.convert_track(track.source_path, ffmpeg_path)
        staged.append(scd_bytes)
        track.source_hash = current_hash

    # Step 2: clear the target SCD directory of existing .scd files.
    os.makedirs(playlist.target_scd_dir, exist_ok=True)
    for name in os.listdir(playlist.target_scd_dir):
        if name.lower().endswith(".scd"):
            os.remove(os.path.join(playlist.target_scd_dir, name))

    # Step 3: write staged files into their numbered slots.
    for i, scd_bytes in enumerate(staged, start=1):
        out_path = _scd_output_path(playlist.target_scd_dir, i)
        with open(out_path, "wb") as f:
            f.write(scd_bytes)

    # Step 4: regenerate and save the group JSON.
    report(total, "Updating mod group JSON")
    group_json = penumbra_group.load_group(playlist.target_group_json)
    group_json = penumbra_group.regenerate_options(group_json, playlist)
    penumbra_group.save_group(playlist.target_group_json, group_json)

    report(total, "Done")
