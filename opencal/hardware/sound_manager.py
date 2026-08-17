from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import final

SOUNDS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "sounds"
STARTUP_MP3 = SOUNDS_DIR / "win_xp_startup.mp3"
SHUTDOWN_MP3 = SOUNDS_DIR / "win_xp_shutdown.mp3"
SCROLL_WAV = SOUNDS_DIR / "doom_scroll.wav"
CLICK_WAV = SOUNDS_DIR / "doom_click.wav"

AUDIO_ENV = os.environ.copy()
AUDIO_ENV["XDG_RUNTIME_DIR"] = "/run/user/1000"
AUDIO_ENV["PULSE_SERVER"] = "unix:/run/user/1000/pulse/native"
AUDIO_ENV["PIPEWIRE_RUNTIME_DIR"] = "/run/user/1000"


@final
class SoundManager:
    """Manages audio effects, startup/shutdown jingles, and Doom-style menu navigation sounds.

    Uses a dedicated non-blocking worker queue and ALSA/PipeWire subprocesses to ensure
    100% thread-safety across GPIO interrupts, web threads, and LCD rendering loops.
    """

    def __init__(self, sounds_enabled: bool = True) -> None:
        self.sounds_enabled: bool = sounds_enabled
        self._queue: queue.Queue[Path | None] = queue.Queue(maxsize=16)
        self._worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self._worker_thread.start()

    def _audio_worker(self) -> None:
        """Sequential background audio playback worker."""
        while True:
            try:
                sound_file = self._queue.get()
                if sound_file is None:
                    break
                if not self.sounds_enabled or not sound_file.exists():
                    continue

                if sound_file.suffix.lower() == ".wav":
                    # Instantaneous low-latency playback for UI ticks
                    subprocess.run(
                        ["aplay", "-q", "-N", str(sound_file)],
                        env=AUDIO_ENV,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=0.8,
                    )
                else:
                    # MP3 playback for startup/shutdown jingles
                    subprocess.run(
                        ["mpv", "--no-video", "--really-quiet", str(sound_file)],
                        env=AUDIO_ENV,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=6.0,
                    )
            except Exception:
                pass
            finally:
                time.sleep(0.01)

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
        if not self.sounds_enabled or not STARTUP_MP3.exists():
            return
        try:
            self._queue.put_nowait(STARTUP_MP3)
        except queue.Full:
            pass

    def play_shutdown(self, blocking: bool = True) -> None:
        """Play Windows XP shutdown sound synchronously before shutdown/reboot."""
        if not self.sounds_enabled or not SHUTDOWN_MP3.exists():
            return
        try:
            subprocess.run(
                ["mpv", "--no-video", "--really-quiet", str(SHUTDOWN_MP3)],
                env=AUDIO_ENV,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4.0,
            )
        except Exception as e:
            print(f"Shutdown sound error: {e}")
