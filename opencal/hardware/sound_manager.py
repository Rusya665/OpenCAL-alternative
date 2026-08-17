from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from typing import final

import pygame

SOUNDS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "sounds"
STARTUP_MP3 = SOUNDS_DIR / "win_xp_startup.mp3"
SHUTDOWN_MP3 = SOUNDS_DIR / "win_xp_shutdown.mp3"
SCROLL_WAV = SOUNDS_DIR / "doom_scroll.wav"
CLICK_WAV = SOUNDS_DIR / "doom_click.wav"


@final
class SoundManager:
    """Manages audio effects, startup/shutdown jingles, and Doom-style menu navigation sounds."""

    def __init__(self, sounds_enabled: bool = True) -> None:
        self.sounds_enabled: bool = sounds_enabled
        self._scroll_sound: pygame.mixer.Sound | None = None
        self._click_sound: pygame.mixer.Sound | None = None
        self._mixer_initialized: bool = False
        self._init_mixer()

    def _init_mixer(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            if SCROLL_WAV.exists():
                self._scroll_sound = pygame.mixer.Sound(str(SCROLL_WAV))
            if CLICK_WAV.exists():
                self._click_sound = pygame.mixer.Sound(str(CLICK_WAV))
            self._mixer_initialized = True
        except Exception as e:
            print(f"SoundManager mixer init warning: {e}")

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
        """Play Doom menu scroll sound."""
        if not self.sounds_enabled:
            return
        if not self._scroll_sound and not self._mixer_initialized:
            self._init_mixer()
        if self._scroll_sound:
            try:
                self._scroll_sound.play()
            except Exception:
                pass

    def play_click(self) -> None:
        """Play Doom menu click / select sound."""
        if not self.sounds_enabled:
            return
        if not self._click_sound and not self._mixer_initialized:
            self._init_mixer()
        if self._click_sound:
            try:
                self._click_sound.play()
            except Exception:
                pass

    def play_startup(self) -> None:
        """Play Windows XP startup sound asynchronously on boot."""
        if not self.sounds_enabled or not STARTUP_MP3.exists():
            return

        def _play():
            try:
                subprocess.run(
                    ["mpv", "--no-video", "--really-quiet", str(STARTUP_MP3)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=6.0,
                )
            except Exception as e:
                print(f"Startup sound error: {e}")

        threading.Thread(target=_play, daemon=True).start()

    def play_shutdown(self, blocking: bool = True) -> None:
        """Play Windows XP shutdown sound synchronously before shutdown/reboot."""
        if not self.sounds_enabled or not SHUTDOWN_MP3.exists():
            return
        try:
            subprocess.run(
                ["mpv", "--no-video", "--really-quiet", str(SHUTDOWN_MP3)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4.0,
            )
        except Exception as e:
            print(f"Shutdown sound error: {e}")
