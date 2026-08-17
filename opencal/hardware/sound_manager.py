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

# Fallbacks if WAVs are not yet generated
STARTUP_MP3 = SOUNDS_DIR / "win_xp_startup.mp3"
SHUTDOWN_MP3 = SOUNDS_DIR / "win_xp_shutdown.mp3"

AUDIO_ENV = os.environ.copy()
AUDIO_ENV["XDG_RUNTIME_DIR"] = "/run/user/1000"
AUDIO_ENV["PULSE_SERVER"] = "unix:/run/user/1000/pulse/native"
AUDIO_ENV["PIPEWIRE_RUNTIME_DIR"] = "/run/user/1000"


@final
class SoundManager:
    """Manages audio effects, startup/shutdown jingles, and Doom-style menu navigation sounds.

    Directly routes uncompressed PCM to the HDMI projector output via ALSA plughw:0,0
    and PipeWire pw-play with zero external dependencies.
    """

    def __init__(self, sounds_enabled: bool = True) -> None:
        self.sounds_enabled: bool = sounds_enabled
        self._queue: queue.Queue[Path | None] = queue.Queue(maxsize=16)
        self._worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self._worker_thread.start()

    def _play_file(self, sound_file: Path, timeout: float = 5.0) -> None:
        """Play audio file directly to HDMI output with fallback."""
        if not sound_file.exists():
            return
        # 1. Try ALSA direct hardware output (HDMI card 0)
        try:
            res = subprocess.run(
                ["aplay", "-D", "plughw:0,0", "-q", "-N", str(sound_file)],
                env=AUDIO_ENV,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
            if res.returncode == 0:
                return
        except Exception:
            pass

        # 2. Fallback to PipeWire pw-play
        try:
            subprocess.run(
                ["pw-play", str(sound_file)],
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
        """Play Doom menu scroll sound (non-blocking, drops if queue full)."""
        if not self.sounds_enabled or not SCROLL_WAV.exists():
            return
        try:
            self._queue.put_nowait(SCROLL_WAV)
        except queue.Full:
            pass

    def play_click(self) -> None:
        """Play Doom menu click / select sound (non-blocking)."""
        if not self.sounds_enabled or not CLICK_WAV.exists():
            return
        try:
            self._queue.put_nowait(CLICK_WAV)
        except queue.Full:
            pass

    def play_startup(self) -> None:
        """Play Windows XP startup sound asynchronously on boot."""
        target = STARTUP_WAV if STARTUP_WAV.exists() else STARTUP_MP3
        if not self.sounds_enabled or not target.exists():
            return
        try:
            self._queue.put_nowait(target)
        except queue.Full:
            pass

    def play_shutdown(self, blocking: bool = True) -> None:
        """Play Windows XP shutdown sound synchronously before shutdown/reboot."""
        target = SHUTDOWN_WAV if SHUTDOWN_WAV.exists() else SHUTDOWN_MP3
        if not self.sounds_enabled or not target.exists():
            return
        self._play_file(target, timeout=4.2)
