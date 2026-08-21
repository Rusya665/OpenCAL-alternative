import threading
import time
from typing import final
from pathlib import Path

from opencal.utils.config import Config
from .hardware_controller import HardwareController

_RECORDING_DIR = Path.home() / "OpenCAL-alternative" / "recordings"


@final
class PrintController:
    def __init__(self, config: Config, video_playing: threading.Event):
        self.hardware = HardwareController(config)
        if not self.hardware.healthy:
            print("not all peripherals connected, some functionality may not work")
        self.video_playing = video_playing
        self.running = False
        self.ui_config = config.ui
        self.recording_path: Path | None = None
        self.vial_width_px: int = (
            self.hardware.projector.get_vial_width()
            if (self.hardware and self.hardware.projector)
            else getattr(config.projector, "vial_width_px", 200)
        )

    def start_print_job(self, video_file: Path):
        """Start the print job in a new thread."""
        threading.Thread(target=self.print, args=(video_file,)).start()

    def print(self, video_file: Path):
        print(f"Starting print job... {video_file}")
        self.running = True

        ts = time.strftime("%Y%m%d_%H%M%S")
        self.recording_path = _RECORDING_DIR / f"{video_file.stem}_recording_{ts}.mp4"
        self.recording_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Pre-load video player paused on Frame 0 so Wayland surface is fully initialized
        print(f"Pre-loading video on Frame 0: {video_file.name}...")
        self.hardware.projector.prepare_video(video_file)

        # 2. Atomic Synchronous Trigger: Unpause video, start stepper, turn on LED, start camera
        print("⚡ Triggering atomic synchronous print start (Light + Stepper + Camera)...")
        self.video_playing.set()
        self.hardware.projector.unpause_video()
        self.hardware.stepper.start_rotation("CCW")
        self.hardware.led_manager.set_led((0, 240, 0, 0))
        self.hardware.camera.start_recording(self.recording_path)

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Print job interrupted by user.")
        finally:
            self.stop()
            print("Print job complete.")

    def stop(self):
        if not self.running:
            return
        print("Stopping print job...")
        self.running = False

        self.hardware.stepper.stop()
        self.hardware.led_manager.clear_leds()

        self.hardware.projector.stop_video()
        self.video_playing.clear()
        
        saved_mp4 = self.hardware.camera.stop_recording()

        # ALWAYS auto-save recording to USB drive if mounted
        if saved_mp4 and Path(saved_mp4).exists():
            print(f"✓ Local recording saved: {saved_mp4}")
            try:
                usb = self.hardware.usb_device
                if usb and usb.is_mounted():
                    import shutil
                    from opencal.hardware.usb_manager import unique_path
                    usb_dest = unique_path(usb.usb_save_path(Path(saved_mp4).name))
                    shutil.copy2(saved_mp4, usb_dest)
                    print(f"✓ AUTOMATICALLY copied recording to USB: {usb_dest}")
            except Exception as e:
                print(f"Error auto-saving recording to USB: {e}")

        print("Print job stopped and cleanup complete.")
