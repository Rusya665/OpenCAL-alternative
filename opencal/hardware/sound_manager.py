from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import final

SOUNDS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "sounds"
STARTUP_WAV = SOUNDS_DIR / "win_xp_startup.wav"
SHUTDOWN_WAV = SOUNDS_DIR / "win_xp_shutdown.wav"
SCROLL_WAV = SOUNDS_DIR / "doom_scroll.wav"
CLICK_WAV = SOUNDS_DIR / "doom_click.wav"

AUDIO_ENV = os.environ.copy()
AUDIO_ENV["XDG_RUNTIME_DIR"] = "/run/user/1000"
AUDIO_ENV["PULSE_SERVER"] = "unix:/run/user/1000/pulse/native"
AUDIO_ENV["PIPEWIRE_RUNTIME_DIR"] = "/run/user/1000"


@final
class SoundManager:
    """Manages audio effects, startup/shutdown jingles, and Doom-style menu navigation sounds.

    Features intelligent rate limiting, instant queue clearing on click, and PipeWire streaming.
    """

    def __init__(self, sounds_enabled: bool = True) -> None:
        self.sounds_enabled: bool = sounds_enabled
        self._queue: queue.Queue[Path | None] = queue.Queue(maxsize=4)
        self._last_scroll_time: float = 0.0
        self._worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self._worker_thread.start()

    def _play_file(self, sound_file: Path, timeout: float = 5.0) -> None:
        """Play audio file directly through PipeWire with fallback."""
        if not sound_file.exists():
            return
        # 1. Primary: PipeWire native player (mixes audio, no 'device busy' locks)
        try:
            res = subprocess.run(
                ["pw-play", str(sound_file)],
                env=AUDIO_ENV,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
            if res.returncode == 0:
                return
        except Exception:
            pass

        # 2. Fallback: ALSA default device
        try:
            subprocess.run(
                ["aplay", "-D", "default", "-q", "-N", str(sound_file)],
                env=AUDIO_ENV,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
        except Exception:
            pass

    def _audio_worker(self) -> None:
        """Sequential background audio playback worker."""
        while True:
            try:
                sound_file = self._queue.get()
                if sound_file is None:
                    break
                if not self.sounds_enabled or not sound_file.exists():
                    continue

                timeout = 0.8 if sound_file in (SCROLL_WAV, CLICK_WAV) else 6.0
                self._play_file(sound_file, timeout=timeout)
            except Exception:
                pass
            finally:
                time.sleep(0.005)

    def set_enabled(self, enabled: bool, persist: bool = True) -> None:
        """Enable or disable system sounds and optionally save to config.json."""
        self.sounds_enabled = bool(enabled)
        if persist:
            try:
                from opencal.utils.config import save_sounds_enabled

                save_sounds_enabled(self.sounds_enabled)
            except Exception as e:
                print(f"Error saving sounds setting: {e}")

    def is_enabled(self) -> bool:
        return self.sounds_enabled

    def play_scroll(self) -> None:
        """Play Doom menu scroll sound with intelligent throttling to prevent sound pileup during fast spins."""
        if not self.sounds_enabled or not SCROLL_WAV.exists():
            return
        now = time.monotonic()
        # Throttles rapid rotation to max ~13 sounds/sec (75ms min interval)
        if now - self._last_scroll_time < 0.075:
            return
        self._last_scroll_time = now
        try:
            self._queue.put_nowait(SCROLL_WAV)
        except queue.Full:
            pass

    def play_click(self) -> None:
        """Play Doom menu click / select sound (clears queued scroll ticks for instant response)."""
        if not self.sounds_enabled or not CLICK_WAV.exists():
            return
        # Purge pending scrolls so selection sound plays immediately
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        try:
            self._queue.put_nowait(CLICK_WAV)
        except queue.Full:
            pass

    def play_startup(self) -> None:
        """Play Windows XP startup sound asynchronously on boot."""
        if not self.sounds_enabled or not STARTUP_WAV.exists():
            return
        try:
            self._queue.put_nowait(STARTUP_WAV)
        except queue.Full:
            pass

    def play_shutdown(self, blocking: bool = True) -> None:
        """Play Windows XP shutdown sound synchronously before shutdown/reboot."""
        if not self.sounds_enabled or not SHUTDOWN_WAV.exists():
            return
        self._play_file(SHUTDOWN_WAV, timeout=4.2)
