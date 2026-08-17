import time
from typing import final
from pathlib import Path

try:
    from picamera2 import Picamera2, Preview
    from picamera2.encoders import H264Encoder
    from libcamera import controls  # pyright: ignore
    HAS_PICAMERA2 = True
except (ImportError, ModuleNotFoundError):
    Picamera2 = None
    Preview = None
    H264Encoder = None
    controls = None
    HAS_PICAMERA2 = False

from opencal.utils.config import CameraConfig


@final
class CameraController:
    def __init__(self, config: CameraConfig):
        self.cam_type = config.type
        self.camera_index = config.index
        self.save_path = Path(config.save_path)

        self.capture = None
        self._stream_thread = None
        self.streaming = False
        self._record_thread = None
        self._recording = False
        self.writer = None
        self.record_file = None
        self._proc = None
        self._raw_file = None
        self.fps = 20
        self._focus_diopters: float = 9.5
        self._awb_enable: bool = config.awb_enable
        self._colour_gains: tuple[float, float] = config.colour_gains
        self._cam_lock = threading.RLock()

        if HAS_PICAMERA2:
            try:
                self.picam = Picamera2()
                self.still_config = self.picam.create_still_configuration(buffer_count=2)
                self.video_config = self.picam.create_video_configuration()
                self.picam.configure(self.still_config)
            except Exception as e:
                self.picam = None
                print(f"WARNING: Camera init failed: {e}")
        else:
            self.picam = None
            print("WARNING: Picamera2 library not available, camera functionality disabled.")

    def start_camera(self, preview: bool = False):
        if not self.picam:
            print("WARNING: No camera connected, cannot start camera.")
            return
        if self.picam.started:
            return

        if preview:
            config = self.picam.create_preview_configuration()
            self.picam.configure(config)

        self.picam.start()
        self._apply_controls()

    def capture_image(self, save_path: Path | None = None) -> bool:
        if not self.picam:
            print("WARNING: No camera connected, cannot capture image.")
            return False

        try:
            if not self.picam.started:
                self.start_camera(preview=True)

            if save_path is None:
                save_path = self.save_path / "capture.jpeg"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            self.picam.switch_mode_and_capture_file(self.still_config, save_path)
            return True
        except Exception as e:
            print(f"ERROR: Image capture failed: {e}")
            return False

    def _apply_controls(self):
        if not self.picam or not controls:
            return
        self.picam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": self._focus_diopters})
        if self._awb_enable:
            self.picam.set_controls({"AwbEnable": True})
        else:
            self.picam.set_controls({"AwbEnable": False, "ColourGains": self._colour_gains})

    def set_focus(self, diopters: float):
        if not self.picam or not controls:
            print("WARNING: No camera connected, cannot set focus.")
            return
        self._focus_diopters = diopters
        self.picam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": diopters})

    def get_jpeg_frame(self) -> bytes | None:
        """Capture a direct JPEG frame from memory for 30 FPS MJPEG streaming."""
        if not self.picam:
            return None
        with self._cam_lock:
            try:
                if not self.picam.started:
                    try:
                        preview_config = self.picam.create_preview_configuration(main={"size": (1280, 720)})
                        self.picam.configure(preview_config)
                        self.picam.start()
                        self._apply_controls()
                    except Exception:
                        pass
                import io
                stream = io.BytesIO()
                self.picam.capture_file(stream, format="jpeg")
                return stream.getvalue()
            except Exception:
                return None

    def activate_autofocus(self):
        if not self.picam or not controls:
            print("WARNING: No camera connected, cannot activate autofocus.")
            return
        with self._cam_lock:
            self.picam.set_controls({"AfMode": controls.AfModeEnum.Continuous})

    def start_recording(self, file: Path | None = None) -> Path:
        if not self.picam:
            raise RuntimeError("No camera connected, cannot start recording.")
        if file is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            rec_dir = Path.home() / "OpenCAL-alternative" / "recordings"
            rec_dir.mkdir(parents=True, exist_ok=True)
            file = rec_dir / f"recording_{ts}.mp4"

        with self._cam_lock:
            self._recording = True
            self.recording = True
            if self.picam.started:
                try:
                    self.picam.stop()
                except Exception:
                    pass

            video_config = self.picam.create_video_configuration(main={"size": (1280, 720)})
            if controls:
                video_config["controls"]["AfMode"] = controls.AfModeEnum.Continuous
            self.picam.configure(video_config)
            encoder = H264Encoder()
            try:
                from picamera2.outputs import FfmpegOutput
                output = FfmpegOutput(str(file))
            except Exception:
                output = str(file)

            self.picam.start_recording(encoder=encoder, output=output)
            self._current_recording_file = file
            print(f"DEBUG: Camera recording started -> {file}")
            return file

    def stop_recording(self) -> Path | None:
        if not self.picam:
            return None
        with self._cam_lock:
            saved_file = getattr(self, "_current_recording_file", None)
            if self._recording:
                print(f"DEBUG: stopping camera recording -> {saved_file}")
                try:
                    self.picam.stop_recording()
                except Exception as e:
                    print(f"Error stopping recording: {e}")
                self._recording = False
                self.recording = False
                self._current_recording_file = None
            return saved_file

    def is_recording(self) -> bool:
        return bool(self._recording)

    def stop_camera(self):
        if not self.picam:
            return
        self.picam.stop()
