import os
import subprocess
import threading
from pathlib import Path
from typing import Any, final
from enum import Enum
import json

import numpy as np
from PIL import Image

from opencal.utils.config import ProjectorConfig


class ProjectorOrientation(Enum):
    # FIXME: These values are kinda misleading
    NORMAL = "normal"
    LEFT = "left"
    RIGHT = "right"
    FLIPPED = "flipped"

    @classmethod
    def from_wlr_randr(cls, s: str) -> "ProjectorOrientation":
        if s == "normal":
            return cls.NORMAL
        elif s == "90":
            return cls.LEFT
        elif s == "180":
            return cls.FLIPPED
        elif s == "270":
            return cls.RIGHT
        else:
            raise NotImplementedError(f"Can't parse wlr-randr transform value: {s}")

    def to_wlr_randr(self) -> str:
        match self:
            case ProjectorOrientation.NORMAL:
                return "normal"
            case ProjectorOrientation.LEFT:
                return "90"
            case ProjectorOrientation.RIGHT:
                return "270"
            case ProjectorOrientation.FLIPPED:
                return "180"


@final
class Projector:
    def __init__(self, config: ProjectorConfig):
        # Initialize the process attribute to keep track of the playback process.
        self.size = config.default_print_size
        self.calibration_img_path = Path(config.calibration_img_path)
        self.calibration_dir_path = Path(config.calibration_dir_path)
        self.vial_width: int = getattr(config, "vial_width_px", 200)
        self.alignment_y_offset: int = getattr(config, "alignment_y_offset_px", 0)
        self.process = None
        self.thread = None  # We'll use this to keep track of the playback thread.
        self._orientation = None
        self.volume: int = getattr(config, "default_volume", 20)
        self.video_playing: threading.Event | None = None
        self.set_volume(self.volume, persist=False)
        # Automatically power on and wake projector on application boot/restart
        threading.Thread(target=self.turn_on_projector, daemon=True).start()

    def get_projector_orientation(self) -> ProjectorOrientation:
        """Query display orientation from wlr-randr, so that it cannot silently be changed in the background."""

        result = subprocess.run(
            ["wlr-randr", "--output", "HDMI-A-1", "--json"], capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"ERROR: Failed to query projector orientation: {result.stderr}")
            return ProjectorOrientation.NORMAL

        out: dict[str, Any] = json.loads(result.stdout)[0]
        assert out["name"] == "HDMI-A-1"

        transform: str = out["transform"]
        orient = ProjectorOrientation.from_wlr_randr(transform)

        return orient

    def set_projector_orientation(self, orient: ProjectorOrientation) -> None:
        current_orient = self.get_projector_orientation()
        if orient == current_orient:
            return

        transform = orient.to_wlr_randr()

        cmd = f"wlr-randr --output HDMI-A-1 --transform {transform}"
        result = subprocess.run(cmd.split(), capture_output=True, text=True)

        if result.returncode != 0:
            print(f"ERROR failed to rotate display: {result.stderr}")

    def get_video_dimensions(self, video_path: Path):
        """
        Uses ffprobe to retrieve the video dimensions (width and height) dynamically.
        Expects ffprobe to output a single line like: widthxheight (e.g., 1920x1080).
        """
        cmd = [
            "/usr/bin/ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(video_path),
        ]
        output = subprocess.check_output(cmd).decode().strip()
        try:
            width, height = map(int, output.split("x"))
        except Exception as e:
            raise ValueError(f"Unable to parse video dimensions from output: {output}") from e
        return width, height

    def play_video_with_vlc(self, video_path: Path):
        """
        Play the video using cvlc (VLC command-line interface) with the window positioned
        at x=1920 and y=0, and loop the video indefinitely.
        """

        orig_width, orig_height = self.get_video_dimensions(video_path)
        scale_factor = self.size / 100
        new_width = int(orig_width / scale_factor)
        new_height = int(orig_height / scale_factor)

        # Calculate the cropping values to ensure the video remains centered
        crop_x = int((orig_width) / 2) - new_width / 2
        crop_y = int((orig_height) / 2) - new_height / 2

        # Set up the environment for the video
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        # env["XAUTHORITY"] = "/home/opencal/.Xauthority"

        # VLC command
        command = [
            "/usr/bin/cvlc",
            "--fullscreen",
            "--loop",
            "--no-video-title-show",
            "--video-filter=croppadd",
            f"--croppadd-cropleft={int(crop_x)}",
            f"--croppadd-cropright={int(crop_x)}",
            f"--croppadd-croptop={int(crop_y)}",
            f"--croppadd-cropbottom={int(crop_y)}",
            str(video_path),
        ]
        print(" ".join(command))

        if self.video_playing:
            self.video_playing.set()
        self.process = subprocess.Popen(command, env=env)
        threading.Thread(target=self._monitor_playback, args=(self.process,), daemon=True).start()
        print("Video playback started.")

    def _monitor_playback(self, proc):
        try:
            proc.wait()
        except Exception:
            pass
        if self.video_playing:
            self.video_playing.clear()
        if self.process == proc:
            self.process = None

    def get_calibration_file_names(self) -> list[str]:
        if not self.calibration_dir_path.exists():
            default_dir = Path(__file__).parent.parent / "utils" / "calibration"
            if default_dir.exists():
                self.calibration_dir_path = default_dir
            else:
                return []
        files = sorted(path.name for path in self.calibration_dir_path.glob("*.png"))
        return files

    def resize(self, size_new: int):
        """Set print size scaling as a percent"""
        self.size = size_new

    def get_volume(self) -> int:
        """Get current HDMI projector audio volume as a percentage (0-100)."""
        return getattr(self, "volume", 20)

    def set_volume(self, volume_percent: int, persist: bool = True) -> None:
        """Set HDMI projector audio volume as a percentage (0-100) and remember it."""
        self.volume = max(0, min(100, int(volume_percent)))
        val = self.volume
        if persist:
            try:
                from opencal.utils.config import save_projector_volume

                save_projector_volume(self.volume)
            except Exception as e:
                print(f"Error saving volume setting: {e}")
        try:
            subprocess.run(["amixer", "-c", "0", "set", "PCM", f"{val}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0)
            subprocess.run(
                ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{val/100.0:.2f}"],
                env={"XDG_RUNTIME_DIR": "/run/user/1000", "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.0,
            )
        except Exception as e:
            print(f"Error setting volume: {e}")

    def turn_on_projector(self) -> None:
        """Send HDMI-CEC signal and enable Wayland/DRM display output to wake up and power on the projector."""
        try:
            # 1. Enable Wayland display output
            subprocess.run(
                ["wlopm", "--on", "HDMI-A-1"],
                env={"WAYLAND_DISPLAY": "wayland-0", "XDG_RUNTIME_DIR": "/run/user/1000", "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.5
            )
        except Exception:
            pass

        try:
            # 2. Send HDMI-CEC Power On commands
            subprocess.run(["cec-ctl", "-d", "/dev/cec0", "--to", "0", "--image-view-on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5)
            subprocess.run(["cec-ctl", "-d", "/dev/cec0", "--to", "0", "--text-view-on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5)
            subprocess.run(["cec-ctl", "-d", "/dev/cec0", "--to", "0", "--active-source", "phys-addr=1.0.0.0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5)
        except Exception:
            pass
        print("[OK] Sent Projector Power ON signal")

    def turn_off_projector(self) -> None:
        """Send HDMI-CEC standby signal and turn off HDMI display output to put projector into standby/off."""
        try:
            # 1. Send HDMI-CEC Standby
            subprocess.run(["cec-ctl", "-d", "/dev/cec0", "--to", "0", "--standby"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5)
        except Exception:
            pass

        try:
            # 2. Disable Wayland display output
            subprocess.run(
                ["wlopm", "--off", "HDMI-A-1"],
                env={"WAYLAND_DISPLAY": "wayland-0", "XDG_RUNTIME_DIR": "/run/user/1000", "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.5
            )
        except Exception:
            pass
        print("✓ Sent Projector Standby / Turn OFF signal")

    def reboot_projector(self) -> None:
        """Reboot the projector by cycling standby and power-on."""
        def _cycle():
            print("Cycling projector power...")
            self.turn_off_projector()
            import time
            time.sleep(5.0)
            self.turn_on_projector()
            print("✓ Projector reboot cycle complete")
        threading.Thread(target=_cycle, daemon=True).start()

    def play_experimental_video(self, video_path: Path, volume: int | None = None):
        """Play an experimental video fullscreen on the projector with audio enabled at remembered volume."""
        if self.process:
            self.stop_video()

        if volume is not None:
            self.set_volume(volume)
        else:
            self.set_volume(self.volume)

        env = os.environ.copy()
        env["DISPLAY"] = ":0"

        # VLC gain (1.0 = 100%, 0.2 = 20%)
        vlc_gain = max(0.0, min(2.0, self.volume / 50.0))
        command = [
            "/usr/bin/cvlc",
            "--fullscreen",
            "--no-video-title-show",
            "--play-and-exit",
            "--aout=alsa",
            f"--gain={vlc_gain:.2f}",
            str(video_path),
        ]
        if self.video_playing:
            self.video_playing.set()
        self.process = subprocess.Popen(command, env=env)
        threading.Thread(target=self._monitor_playback, args=(self.process,), daemon=True).start()
        print(f"Playing experimental video: {video_path} at volume {self.volume}%")

    def stop_video(self):
        """
        Stop the video playback by terminating the cvlc process.
        """
        if self.process is not None:
            try:
                self.process.terminate()
                _ = self.process.wait(timeout=2.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
            print("Video playback stopped.")
        if self.video_playing:
            self.video_playing.clear()

    def start_video_thread(self, video_path: Path | None = None):
        """
        Start the video playback in a new thread.
        """
        if not video_path:
            raise ValueError("start_video_thread() requires a `video_path` argument")

        # Create a new thread for playing the video.
        self.thread = threading.Thread(target=self.play_video_with_vlc, args=(video_path,))
        self.thread.start()

    def get_vial_width(self) -> int:
        """Get current calibrated vial width in pixels."""
        return getattr(self, "vial_width", 200)

    def set_vial_width(self, width: int, persist: bool = True) -> None:
        """Set calibrated vial width in pixels and optionally persist to config.json."""
        self.vial_width = max(10, int(width))
        if persist:
            try:
                from opencal.utils.config import save_vial_width
                save_vial_width(self.vial_width)
            except Exception as e:
                print(f"Error persisting vial width: {e}")

    def get_alignment_offset(self) -> int:
        """Get current optical alignment Y-offset in pixels."""
        return getattr(self, "alignment_y_offset", 0)

    def set_alignment_offset(self, offset: int, persist: bool = True) -> None:
        """Set optical alignment Y-offset in pixels and optionally persist to config.json."""
        self.alignment_y_offset = int(offset)
        if persist:
            try:
                from opencal.utils.config import save_alignment_offset
                save_alignment_offset(self.alignment_y_offset)
            except Exception as e:
                print(f"Error persisting alignment offset: {e}")

    def show_vial_width(self, width: int):
        """
        Display a rectangle to calibrate the vial width.
        """
        self.set_vial_width(width, persist=False)
        w, h = 1920, 1080
        arr = np.zeros((h, w), dtype=np.uint8)
        cx, cy = w // 2, h // 2
        dy, dx = self.vial_width // 2, 400
        arr[cy - dy : cy + dy, cx - dx : cx + dx] = 255
        im = Image.fromarray(arr, "L")
        p = Path.cwd() / "opencal/utils/calibration/vial_width.png"
        im.save(p)
        self.display_image(p)

    def display_image(self, image_path: Path | None = None):
        """
        Display a still image fullscreen until stop_video() is called.
        """
        if image_path is None:
            image_path = self.calibration_img_path
        if not Path(image_path).exists():
            print(f"Warning: Image {image_path} does not exist, skipping display_image.")
            return

        # If something’s already playing, stop it.
        if self.process:
            self.stop_video()

        env = os.environ.copy()
        env["DISPLAY"] = ":0"

        try:
            command = [
                "/usr/bin/mpv",
                "--fs",  # fullscreen
                "--loop-file=inf",  # loop indefinitely
                "--no-audio",  # no sound
                "--image-display-duration=inf",  # keep image up forever
                str(image_path),
            ]
            self.process = subprocess.Popen(command, env=env)
            print(f"Image displayed: {image_path}")
        except FileNotFoundError:
            print(f"Warning: /usr/bin/mpv not installed. Cannot display still image {image_path}.")
        except Exception as e:
            print(f"Warning: Could not display image: {e}")

    def start_image_thread_for_image(self, image_path: Path):
        """
        Same as display_image(), but in a background thread.
        """
        self.thread = threading.Thread(target=self.display_image, args=(image_path,), daemon=True)
        self.thread.start()


def main():
    # Example test for playback on projector:
    from opencal.utils.config import Config

    cfg = Config()
    projector = Projector(cfg.projector)
    projector.resize(100)
    # Start video playback in a new thread.
    projector.play_video_with_vlc(Path("test/path/here"))  # include video path here

    # Wait for user input to stop the video.
    _ = input("Press Enter to stop video playback...")
    projector.stop_video()

    # Optionally, wait for the video thread to finish.
    if projector.thread is not None:
        projector.thread.join()


if __name__ == "__main__":
    main()
