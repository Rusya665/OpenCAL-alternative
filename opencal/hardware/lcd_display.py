import threading
import time
from typing import final

from opencal.utils.config import LcdDisplayConfig

try:
    from smbus2 import SMBus, i2c_msg
    HAS_SMBUS2 = True
except ImportError:
    HAS_SMBUS2 = False

try:
    from RPLCD.i2c import CharLCD
    HAS_RPLCD = True
except ImportError:
    HAS_RPLCD = False


class NewhavenLCDBackend:
    """Robust Sequential Framebuffer Driver for Newhaven NHD-0420D3Z."""
    DEFAULT_ADDRESS = 0x28

    def __init__(self, bus_num: int = 1, address: int = DEFAULT_ADDRESS, contrast: int = 42, backlight: int = 8):
        self.bus_num = bus_num
        self.address = address
        self._lock = threading.RLock()
        self.char_delay = 0.0015  # 1.5ms per char prevents PIC buffer drops
        time.sleep(0.2)
        if HAS_SMBUS2:
            try:
                self.bus = SMBus(self.bus_num)
            except Exception as e:
                print(f"Warning: Could not open SMBus({bus_num}): {e}")
                self.bus = None
        else:
            self.bus = None

        self.display_on()
        self.set_backlight(backlight)
        self.set_contrast(contrast)
        self.clear()

    def _send_cmd(self, cmd_bytes: list[int], delay: float = 0.050):
        if not self.bus:
            return
        with self._lock:
            try:
                msg = i2c_msg.write(self.address, cmd_bytes)
                self.bus.i2c_rdwr(msg)
            except Exception as e:
                print(f"I2C Cmd Error: {e}")
            time.sleep(delay)

    def display_on(self):
        self._send_cmd([0xFE, 0x41], delay=0.020)

    def set_contrast(self, level: int):
        level = max(1, min(50, level))
        self._send_cmd([0xFE, 0x52, level], delay=0.020)

    def set_backlight(self, level: int):
        level = max(1, min(8, level))
        self._send_cmd([0xFE, 0x53, level], delay=0.020)

    def render_frame(self, line0: str = "", line1: str = "", line2: str = "", line3: str = ""):
        """
        Exact 128-byte Circular DDRAM Stream:
        Row 0 (20) -> Row 2 (20) -> Gap (24) -> Row 1 (20) -> Row 3 (20) -> Gap (24) = 128 bytes
        Because total HD44780 DDRAM is 128 bytes (0x00-0x7F), writing 128 bytes
        guarantees the hardware Address Counter wraps back to 0x00 every frame with zero drift.
        """
        if not self.bus:
            return
        l0 = line0.ljust(20)[:20]
        l1 = line1.ljust(20)[:20]
        l2 = line2.ljust(20)[:20]
        l3 = line3.ljust(20)[:20]
        gap = " " * 24
        payload = (l0 + l2 + gap + l1 + l3 + gap).encode("latin-1", errors="replace")

        with self._lock:
            try:
                for char_byte in payload:
                    msg = i2c_msg.write(self.address, [char_byte])
                    self.bus.i2c_rdwr(msg)
                    time.sleep(self.char_delay)
            except Exception as e:
                print(f"I2C Render Error: {e}")

    def clear(self):
        self.render_frame(" ", " ", " ", " ")

    def close(self):
        with self._lock:
            if self.bus:
                try:
                    self.bus.close()
                except Exception:
                    pass


@final
class LCDDisplay:
    def __init__(self, config: LcdDisplayConfig):
        if isinstance(config.address, str):
            self.address = int(config.address, 16) if config.address.startswith("0x") else int(config.address)
        else:
            self.address = config.address
        self.port = str(config.port)
        self.cols = config.cols
        self.rows = config.rows
        self.type = getattr(config, "type", "newhaven" if self.address == 0x28 or self.port.isdigit() else "pcf8574")

        self.lcd_lock = threading.RLock()
        self.framebuffer = [""] * self.rows

        if self.type.lower() == "newhaven":
            try:
                bus_num = int(self.port)
            except ValueError:
                bus_num = 1
            contrast = getattr(config, "contrast", 42)
            backlight = getattr(config, "backlight", 8)
            self.backend = NewhavenLCDBackend(bus_num=bus_num, address=self.address, contrast=contrast, backlight=backlight)
        else:
            if HAS_RPLCD:
                try:
                    self.backend = CharLCD(self.port, self.address)
                except Exception as e:
                    print(f"Warning: Could not init CharLCD: {e}")
                    self.backend = None
            else:
                self.backend = None

    def render_page(self, lines: list[str]):
        """Atomically update all 4 lines and send ONE 80-byte framebuffer frame."""
        with self.lcd_lock:
            for i in range(min(self.rows, len(lines))):
                self.framebuffer[i] = lines[i][: self.cols]
            self._update_lcd()

    def set_backlight(self, level: int):
        with self.lcd_lock:
            if hasattr(self.backend, "set_backlight"):
                self.backend.set_backlight(level)

    def set_contrast(self, level: int):
        with self.lcd_lock:
            if hasattr(self.backend, "set_contrast"):
                self.backend.set_contrast(level)

    def clear(self):
        """Clear the LCD display and reset the framebuffer."""
        with self.lcd_lock:
            if hasattr(self.backend, "clear"):
                self.backend.clear()
            self.framebuffer = [""] * self.rows

    def write_message(self, message: str, row: int = 0, _col: int = 0):
        """Write a message to a row on the LCD, updating framebuffer and rendering."""
        if 0 <= row < self.rows:
            with self.lcd_lock:
                self.framebuffer[row] = message[: self.cols]
                self._update_lcd()

    def _update_lcd(self, row: int | None = None):
        with self.lcd_lock:
            try:
                if self.type.lower() == "newhaven":
                    if hasattr(self.backend, "render_frame"):
                        self.backend.render_frame(*self.framebuffer)
                else:
                    if self.backend:
                        self.backend.home()
                        for i in range(self.rows):
                            self.backend.cursor_pos = (i, 0)
                            self.backend.write_string(self.framebuffer[i].ljust(self.cols))
            except OSError as e:
                print(f"ERROR: Failed to write to LCD: {e}")


if __name__ == "__main__":
    from opencal.utils.config import Config

    cfg = Config()
    lcd = LCDDisplay(cfg.lcd_display)
    lcd.clear()
    lcd.write_message("OpenCAL Project", row=0)
    lcd.write_message("Newhaven NHD0420D3Z", row=1)
    lcd.write_message("I2C Speed: 50 kHz", row=2)
    lcd.write_message("Status: Ready", row=3)
    time.sleep(3)
    lcd.clear()
