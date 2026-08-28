import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, final
from enum import Enum
import json

import numpy as np
from PIL import Image

from opencal.utils.config import ProjectorConfig

MPV_IPC_SOCKET = Path("/tmp/mpv_projector_socket")


class ProjectorOrientation(Enum):
    """
    Wayland wlr-randr display rotation mapping:
    - NORMAL: Landscape 1920x1080 ('normal')
    - LEFT:   Rotated 90° CCW -> Native portrait 1080x1920 canvas ('90') for Optoma ML1080 left-side mount
    - RIGHT:  Rotated 270° CCW ('270')
    - FLIPPED: Inverted 180° ('180')
    """
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



def get_laser_filtered_video(video_path: Path, laser_mode: str = "white") -> Path:
    """
    Returns laser-filtered video if cached and complete, otherwise returns video_path directly
    so printing starts instantly with zero lag.
    """
    if not video_path:
        return video_path

    vpath = Path(video_path)
    if not vpath.exists():
        return vpath

    if laser_mode in ("white", "rgb", "none", "off", "broadband"):
        return vpath

    target_dir = Path("/tmp/opencal_laser_cache")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"laser_{laser_mode}_{vpath.name}"

    # Return cached version if valid and complete
    if target_path.exists() and target_path.stat().st_mtime >= vpath.stat().st_mtime and target_path.stat().st_size > 50000:
        return target_path

    # If not ready, launch background conversion so future runs have it, but return vpath now
    def _convert_bg():
        tmp_target = target_dir / f"tmp_{laser_mode}_{vpath.name}"
        filter_map = {
            "blue_450nm": "colorchannelmixer=rr=0:rg=0:rb=0:gr=0:gg=0:gb=0:br=0:bg=0:bb=1",
            "green_532nm": "colorchannelmixer=rr=0:rg=0:rb=0:gr=0:gg=1:gb=0:br=0:bg=0:bb=0",
            "red_638nm": "colorchannelmixer=rr=1:rg=0:rb=0:gr=0:gg=0:gb=0:br=0:bg=0:bb=0",
        }
        vf = filter_map.get(laser_mode, filter_map["blue_450nm"])
        try:
            cmd = [
                "/usr/bin/ffmpeg", "-y", "-i", str(vpath),
                "-vf", vf,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                "-an", str(tmp_target)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if res.returncode == 0 and tmp_target.exists() and tmp_target.stat().st_size > 10000:
                tmp_target.rename(target_path)
                print(f"✓ Background laser filter complete: {target_path}")
        except Exception as e:
            print(f"Background laser conversion warning: {e}")

    threading.Thread(target=_convert_bg, daemon=True).start()
    return vpath


@final
class Projector:
    def __init__(self, config: ProjectorConfig):
        # Initialize the process attribute to keep track of the playback process.
        self.size = config.default_print_size
        self.calibration_img_path = Path(config.calibration_img_path)
        self.calibration_dir_path = Path(config.calibration_dir_path)
        self.vial_width: int = getattr(config, "vial_width_px", 200)
        self.alignment_y_offset: int = getattr(config, "alignment_y_offset_px", 0)
        self.laser_mode: str = getattr(config, "laser_mode", "white")
        self.process = None
        self.thread = None  # We'll use this to keep track of the playback thread.
        self._orientation = None
        self.volume: int = getattr(config, "default_volume", 20)
        self.orientation_str: str = getattr(config, "orientation", "90")
        self.set_volume(self.volume, persist=False)
        # Automatically sync display orientation from configured setting
        try:
            orient_enum = ProjectorOrientation.from_wlr_randr(self.orientation_str)
            self.set_projector_orientation(orient_enum, persist=False)
        except Exception as e:
            print(f"Initial orientation sync notice: {e}")
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

    def set_projector_orientation(self, orient: ProjectorOrientation, persist: bool = False) -> None:
        transform = orient.to_wlr_randr()
        if persist:
            from opencal.utils.config import save_projector_orientation
            save_projector_orientation(transform)

        try:
            current_orient = self.get_projector_orientation()
            if orient == current_orient:
                return
        except Exception:
            pass

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

    def get_laser_mode(self) -> str:
        """Get active print laser wavelength filter mode."""
        return getattr(self, "laser_mode", "white")

    def set_laser_mode(self, mode: str, persist: bool = True) -> None:
        """Set active print laser wavelength filter mode (blue_450nm, white, green_532nm, red_638nm)."""
        self.laser_mode = str(mode)
        print(f"Projector print laser mode set to: {self.laser_mode}")

    def is_mpv_available(self) -> bool:
        """Check if mpv binary is available on system."""
        return bool(shutil.which("mpv") or Path("/usr/bin/mpv").exists())

    def send_mpv_command(self, cmd: list[Any], timeout: float = 0.5) -> dict | None:
        """Send JSON IPC command to running mpv instance via Unix domain socket."""
        if not MPV_IPC_SOCKET.exists() or not hasattr(socket, "AF_UNIX"):
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect(str(MPV_IPC_SOCKET))
                msg = json.dumps({"command": cmd}) + "\n"
                s.sendall(msg.encode("utf-8"))
                data = s.recv(4096)
                if data:
                    return json.loads(data.decode("utf-8").strip().split("\n")[0])
        except Exception:
            pass
        return None

    def is_player_ready(self) -> bool:
        """Returns True if the video player process is alive and responsive."""
        if self.process is None or self.process.poll() is not None:
            return False
        if self.is_mpv_available() and MPV_IPC_SOCKET.exists():
            resp = self.send_mpv_command(["get_property", "pause"])
            return bool(resp and resp.get("error") == "success")
        return True

    def unpause_video(self) -> bool:
        """Unpause pre-loaded video atomically via IPC."""
        if self.is_mpv_available() and MPV_IPC_SOCKET.exists():
            resp = self.send_mpv_command(["set_property", "pause", False])
            return bool(resp and resp.get("error") == "success")
        return True

    def prepare_video(self, video_path: Path, laser_mode: str | None = None) -> bool:
        """
        Prepares and starts video player for print job.
        """
        self.play_video(video_path, laser_mode=laser_mode)
        return True

    def play_video(self, video_path: Path, laser_mode: str | None = None, pause: bool = False):
        """
        Unified video playback entry point.
        Uses cvlc with native Wayland wl_dmabuf which reliably decodes HEVC 1080x1920
        portrait videos on Raspberry Pi 5 without dmabuf mapping crashes.
        """
        self.play_video_with_vlc(video_path, laser_mode=laser_mode)

    def play_video_with_mpv(self, video_path: Path, laser_mode: str | None = None, pause: bool = False):
        """
        Play the video using mpv with zero-copy hardware decoding, persistent GPU Wayland surface,
        and zero-flicker seamless looping (--loop-file=inf).
        """
        if self.process:
            self.stop_video()

        mode = laser_mode if laser_mode is not None else self.get_laser_mode()
        actual_video_path = get_laser_filtered_video(video_path, mode)

        orig_width, orig_height = self.get_video_dimensions(actual_video_path)
        scale_factor = self.size / 100
        new_width = int(orig_width / scale_factor)
        new_height = int(orig_height / scale_factor)

        # Calculate crop coordinates to keep video centered
        crop_x = max(0, int((orig_width - new_width) / 2))
        crop_y = max(0, int((orig_height - new_height) / 2))

        # Cleanup any stale IPC socket
        if MPV_IPC_SOCKET.exists():
            try:
                MPV_IPC_SOCKET.unlink()
            except Exception:
                pass

        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        env["WAYLAND_DISPLAY"] = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        env["XDG_RUNTIME_DIR"] = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")

        mpv_bin = "/usr/bin/mpv" if Path("/usr/bin/mpv").exists() else "mpv"
        command = [
            mpv_bin,
            "--fullscreen",
            "--loop-file=inf",
            "--hwdec=auto-safe",
            "--vo=gpu",
            "--keep-open=yes",
            "--no-osc",
            "--no-osd-bar",
            "--no-input-default-bindings",
            "--idle=no",
            f"--input-ipc-server={MPV_IPC_SOCKET}",
            "--pause=yes" if pause else "--pause=no",
        ]

        if crop_x > 0 or crop_y > 0 or (new_width != orig_width) or (new_height != orig_height):
            command.append(f"--vf=crop={int(new_width)}:{int(new_height)}:{int(crop_x)}:{int(crop_y)}")

        command.append(str(actual_video_path))
        print(" ".join(command))

        if self.video_playing:
            self.video_playing.set()
        self.process = subprocess.Popen(command, env=env)
        threading.Thread(target=self._monitor_playback, args=(self.process,), daemon=True).start()
        print(f"mpv video playback launched with laser mode [{mode}] (paused={pause}).")

    def play_video_with_vlc(self, video_path: Path, laser_mode: str | None = None):
        """
        Play the video using cvlc (VLC command-line interface) with the window positioned
        at x=1920 and y=0, and loop the video indefinitely. Automatically applies laser wavelength filtering.
        """
        if self.process:
            self.stop_video()

        mode = laser_mode if laser_mode is not None else self.get_laser_mode()
        actual_video_path = get_laser_filtered_video(video_path, mode)

        orig_width, orig_height = self.get_video_dimensions(actual_video_path)
        scale_factor = self.size / 100
        new_width = int(orig_width / scale_factor)
        new_height = int(orig_height / scale_factor)

        # Calculate the cropping values to ensure the video remains centered
        crop_x = int((orig_width) / 2) - new_width / 2
        crop_y = int((orig_height) / 2) - new_height / 2

        # Set up the environment for the video
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        env["WAYLAND_DISPLAY"] = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        env["XDG_RUNTIME_DIR"] = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
        # VLC command
        command = [
            "/usr/bin/cvlc",
            "--fullscreen",
            "--loop",
            "--no-video-title-show",
        ]
        if crop_x > 2 or crop_y > 2:
            command.extend([
                "--video-filter=croppadd",
                f"--croppadd-cropleft={int(crop_x)}",
                f"--croppadd-cropright={int(crop_x)}",
                f"--croppadd-croptop={int(crop_y)}",
                f"--croppadd-cropbottom={int(crop_y)}",
            ])
        command.append(str(actual_video_path))
        print(" ".join(command))

        if hasattr(self, "video_playing") and self.video_playing is not None:
            self.video_playing.set()
        self.process = subprocess.Popen(command, env=env)
        threading.Thread(target=self._monitor_playback, args=(self.process,), daemon=True).start()
        print(f"cvlc video playback started with laser mode [{mode}]: {actual_video_path}")

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
        Stop video playback by quitting mpv via IPC or terminating the player process.
        """
        if MPV_IPC_SOCKET.exists():
            try:
                self.send_mpv_command(["quit"])
            except Exception:
                pass

        if self.process is not None:
            try:
                self.process.terminate()
                _ = self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        # Clean up any rogue mpv or vlc processes
        try:
            subprocess.run(["killall", "-9", "mpv"], capture_output=True, timeout=1.0)
        except Exception:
            pass
        if MPV_IPC_SOCKET.exists():
            try:
                MPV_IPC_SOCKET.unlink()
            except Exception:
                pass

        if hasattr(self, "video_playing") and self.video_playing is not None:
            self.video_playing.clear()

    def start_video_thread(self, video_path: Path | None = None):
        """
        Start the video playback in a new thread.
        """
        if not video_path:
            raise ValueError("start_video_thread() requires a `video_path` argument")

        # Create a new thread for playing the video.
        self.thread = threading.Thread(target=self.play_video, args=(video_path,))
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
        Display a vertical white bar spanning the full height to calibrate vial width.
        """
        self.set_vial_width(width, persist=False)
        is_portrait = True
        try:
            res = subprocess.run(
                ["wlr-randr", "--output", "HDMI-A-1", "--json"],
                env={"WAYLAND_DISPLAY": "wayland-0", "XDG_RUNTIME_DIR": "/run/user/1000"},
                capture_output=True, text=True
            )
            if res.returncode == 0:
                data = json.loads(res.stdout)
                transform = data[0].get("transform", "90")
                if transform in ("normal", "180", "flipped", "flipped-180"):
                    is_portrait = False
        except Exception:
            pass

        w, h = (1080, 1920) if is_portrait else (1920, 1080)
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        cx = w // 2
        hw = max(1, int(self.vial_width) // 2)
        x1 = max(0, cx - hw)
        x2 = min(w, cx + hw)
        arr[:, x1:x2] = [255, 255, 255]

        im = Image.fromarray(arr, "RGB")
        p = Path("/tmp/vial_width.png")
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
        env["WAYLAND_DISPLAY"] = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        env["XDG_RUNTIME_DIR"] = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")

        command = [
            "/usr/bin/cvlc",
            "--fullscreen",
            "--loop",
            "--no-video-title-show",
            str(image_path),
        ]
        try:
            if self.video_playing:
                self.video_playing.set()
            self.process = subprocess.Popen(command, env=env)
            threading.Thread(target=self._monitor_playback, args=(self.process,), daemon=True).start()
            print(f"Image displayed: {image_path}")
        except Exception as e:
            print(f"Warning: Could not display image: {e}")

    def project_color_patch(
        self,
        color_rgb: tuple[int, int, int] | list[int] = (255, 0, 0),
        brightness_pct: int = 100,
        width_px: int | None = None,
        height_px: int | None = None,
        offset_y: int | None = None,
        full_screen: bool = False
    ):
        """
        Projects a solid color rectangle in the center of the projector (matching vial/video size)
        or fullscreen, scaled by brightness percentage (0-100%).
        """
        # Determine current display orientation
        is_portrait = True
        try:
            res = subprocess.run(
                ["wlr-randr", "--output", "HDMI-A-1", "--json"],
                env={"WAYLAND_DISPLAY": "wayland-0", "XDG_RUNTIME_DIR": "/run/user/1000"},
                capture_output=True, text=True
            )
            if res.returncode == 0:
                data = json.loads(res.stdout)
                transform = data[0].get("transform", "normal")
                if transform in ("normal", "180", "flipped", "flipped-180"):
                    is_portrait = False
        except Exception:
            pass

        if is_portrait:
            canvas_w, canvas_h = 1080, 1920
            default_w, default_h = self.vial_width, 1000
        else:
            canvas_w, canvas_h = 1920, 1080
            default_w, default_h = self.vial_width, 650

        # Scale RGB by brightness percentage (0.0 to 1.0)
        scale = max(0.0, min(1.0, float(brightness_pct) / 100.0))
        scaled_rgb = [int(min(255, max(0, c * scale))) for c in color_rgb]

        arr = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

        if full_screen:
            arr[:, :] = scaled_rgb
        else:
            w = int(width_px) if width_px is not None else default_w
            h = int(height_px) if height_px is not None else default_h
            off_y = int(offset_y) if offset_y is not None else self.alignment_y_offset

            cx = canvas_w // 2
            cy = (canvas_h // 2) + off_y

            x1 = max(0, cx - (w // 2))
            x2 = min(canvas_w, cx + (w // 2))
            y1 = max(0, cy - (h // 2))
            y2 = min(canvas_h, cy + (h // 2))

            arr[y1:y2, x1:x2] = scaled_rgb

        img_path = Path("/tmp/projector_color_patch.png")
        Image.fromarray(arr, "RGB").save(img_path)
        self.display_image(img_path)
        print(f"Projecting color patch {scaled_rgb} (brightness: {brightness_pct}%, size: {width_px or default_w}x{height_px or default_h})")

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
