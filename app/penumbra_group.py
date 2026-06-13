import json
import os

from app.project import Playlist

DAM_PATH = "sound/dam.scd"

_OFF_OPTION = {
    "Name": "Off",
    "Description": "",
    "Files": {},
    "FileSwaps": {},
    "Manipulations": [],
}

_DEFAULT_GROUP = {
    "Version": 0,
    "Name": "",
    "Description": "",
    "Image": "",
    "Page": 0,
    "Priority": 0,
    "Type": "Single",
    "DefaultSettings": 0,
    "Options": [dict(_OFF_OPTION)],
}


def load_group(path: str) -> dict:
    if not os.path.exists(path):
        return json.loads(json.dumps(_DEFAULT_GROUP))
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _track_swap_path(index: int) -> str:
    return f"sound\\mylist\\{index}.scd"


def regenerate_options(group_json: dict, playlist: Playlist) -> dict:
    """Rebuild Options[] from the playlist's tracks, preserving root fields and Off."""
    options = group_json.get("Options") or []
    off_option = dict(options[0]) if options else dict(_OFF_OPTION)
    off_option.setdefault("Name", "Off")
    off_option["Files"] = {}
    off_option["FileSwaps"] = off_option.get("FileSwaps", {})
    off_option["Manipulations"] = off_option.get("Manipulations", [])

    new_options = [off_option]
    for i, track in enumerate(playlist.tracks, start=1):
        new_options.append({
            "Name": track.display_name,
            "Description": "",
            "Files": {DAM_PATH: _track_swap_path(i)},
            "FileSwaps": {},
            "Manipulations": [],
        })

    group_json["Options"] = new_options
    return group_json


def save_group(path: str, group_json: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(group_json, f, indent=2)
    os.replace(tmp_path, path)
