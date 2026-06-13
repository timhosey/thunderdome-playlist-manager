import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Track:
    source_path: str
    display_name: str
    source_hash: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Track":
        return Track(
            source_path=data["source_path"],
            display_name=data["display_name"],
            source_hash=data.get("source_hash"),
        )


@dataclass
class Playlist:
    name: str
    target_group_json: str = ""
    target_scd_dir: str = ""
    tracks: list[Track] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "target_group_json": self.target_group_json,
            "target_scd_dir": self.target_scd_dir,
            "tracks": [t.to_dict() for t in self.tracks],
        }

    @staticmethod
    def from_dict(data: dict) -> "Playlist":
        return Playlist(
            name=data["name"],
            target_group_json=data.get("target_group_json", ""),
            target_scd_dir=data.get("target_scd_dir", ""),
            tracks=[Track.from_dict(t) for t in data.get("tracks", [])],
        )


@dataclass
class Project:
    playlists: dict[str, Playlist] = field(default_factory=dict)
    ffmpeg_path: str = "ffmpeg"
    active_playlist: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "ffmpeg_path": self.ffmpeg_path,
            "active_playlist": self.active_playlist,
            "playlists": {pid: p.to_dict() for pid, p in self.playlists.items()},
        }

    @staticmethod
    def from_dict(data: dict) -> "Project":
        return Project(
            playlists={
                pid: Playlist.from_dict(p)
                for pid, p in data.get("playlists", {}).items()
            },
            ffmpeg_path=data.get("ffmpeg_path", "ffmpeg"),
            active_playlist=data.get("active_playlist"),
        )

    def add_playlist(self, name: str) -> str:
        pid = uuid.uuid4().hex
        self.playlists[pid] = Playlist(name=name)
        return pid


def load(path: str) -> Project:
    if not os.path.exists(path):
        return Project()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Project.from_dict(data)


def save(path: str, project: Project) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(project.to_dict(), f, indent=2)
    os.replace(tmp_path, path)


def default_project_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".thunderdome_playlists.json")
