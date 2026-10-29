import threading
import time
from pathlib import Path

import vlc

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv"}


class Player:
    def __init__(self, movie_dir: Path, fullscreen: bool = True):
        self.movie_dir = movie_dir
        self.fullscreen = fullscreen
        self._lock = threading.Lock()
        self._instance = vlc.Instance()
        self._player = self._instance.media_player_new()
        self._current: str | None = None

    def list_movies(self) -> list[str]:
        if not self.movie_dir.is_dir():
            return []
        return sorted(
            p.name for p in self.movie_dir.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS
        )

    def play(self, filename: str) -> bool:
        # Only names from the listing are accepted -> no path traversal.
        if filename not in self.list_movies():
            return False
        with self._lock:
            media = self._instance.media_new(str(self.movie_dir / filename))
            self._player.set_media(media)
            self._player.play()
            self._player.set_fullscreen(self.fullscreen)
            self._current = filename
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
