import threading
import time
from pathlib import Path

import vlc

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv"}
SUB_EXTS = {".srt", ".sub", ".ass", ".ssa", ".vtt", ".smi"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


class Player:
    def __init__(self, movie_dir: Path, fullscreen: bool = True):
        self.movie_dir = movie_dir
        self.fullscreen = fullscreen
        self._lock = threading.Lock()
        self._instance = vlc.Instance()
        self._player = self._instance.media_player_new()
        self._current: str | None = None

    def _find(self, folder: Path, stem: str, exts: set[str]) -> Path | None:
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.stem.lower() == stem and p.suffix.lower() in exts:
                return p
        return None

    def _entry(self, folder: Path) -> dict | None:
        movie = self._find(folder, "movie", VIDEO_EXTS)
        if movie is None:
            return None
        return {
            "name": folder.name,
            "movie": movie,
            "sub": self._find(folder, "sub", SUB_EXTS),
            "image": self._find(folder, "image", IMAGE_EXTS),
        }

    def _entries(self) -> dict[str, dict]:
        if not self.movie_dir.is_dir():
            return {}
        out = {}
        for d in sorted(self.movie_dir.iterdir()):
            if d.is_dir():
                e = self._entry(d)
                if e:
                    out[e["name"]] = e
        return out

    def list_movies(self) -> list[dict]:
        return [{"name": n, "has_image": e["image"] is not None, "has_sub": e["sub"] is not None}
                for n, e in self._entries().items()]

    def image_path(self, name: str) -> Path | None:
        e = self._entries().get(name)
        return e["image"] if e else None

    def play(self, name: str) -> bool:
        # Only names from the listing are accepted -> no path traversal.
        e = self._entries().get(name)
        if e is None:
            return False
        with self._lock:
            media = self._instance.media_new(str(e["movie"]))
            if e["sub"]:
                media.add_option(f":sub-file={e['sub']}")
            self._player.set_media(media)
            self._player.play()
            self._player.set_fullscreen(self.fullscreen)
            self._current = name
        return True

    def pause(self):
        with self._lock:
            if self._player.is_playing():
                self._player.set_pause(1)

    def resume(self):
        with self._lock:
            if self._current and not self._player.is_playing():
                self._player.set_pause(0)

    def stop(self):
        with self._lock:
            self._player.stop()
            self._current = None

    def seek(self, seconds: float):
        with self._lock:
            length = self._player.get_length()
            ms = max(0, int(seconds * 1000))
            if length > 0:
                ms = min(ms, length)
            self._player.set_time(ms)

    def status(self) -> dict:
        with self._lock:
            state = self._player.get_state()
            pos = self._player.get_time()
            length = self._player.get_length()
            current = self._current
            lookup = time.time()
        if current is None or state in (vlc.State.Stopped, vlc.State.Ended, vlc.State.NothingSpecial):
            if state == vlc.State.Ended:
                current = None
            state_name = "stopped"
        elif state == vlc.State.Paused:
            state_name = "paused"
        elif state == vlc.State.Playing:
            state_name = "playing"
        else:
            state_name = "loading"
        return {
            "movie": current,
            "state": state_name,
            "position_s": max(pos, 0) / 1000 if current else None,
            "length_s": length / 1000 if current and length > 0 else None,
            "lookup_time": lookup,
        }
