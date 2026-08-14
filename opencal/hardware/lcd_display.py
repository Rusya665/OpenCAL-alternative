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
    """Driver for Newhaven NHD-0420D3Z (20x4 I2C LCD driven by PIC16F690)."""
    LINE_OFFSETS = [0x00, 0x40, 0x14, 0x54]

    def __init__(self, bus_num: int = 1, address: int = 0x28, contrast: int = 40, backlight: int = 8):
        self.bus_num = bus_num
        self.address = address
        time.sleep(0.15)  # Startup delay required for PIC microcontroller bootup
        if HAS_SMBUS2:
            try:
                self.bus = SMBus(self.bus_num)
            except Exception as e:
                print(f"Warning: Could not open SMBus({bus_num}): {e}")
                self.bus = None
        else:
            self.bus = None

        self.display_on()
        self.clear()
        self.set_contrast(contrast)
        self.set_backlight(backlight)

    def _send_cmd(self, cmd_bytes: list[int], delay: float = 0.01):
        if not self.bus:
            return
        try:
            msg = i2c_msg.write(self.address, cmd_bytes)
            self.bus.i2c_rdwr(msg)
        except Exception as e:
            print(f"I2C Cmd Error: {e}")
        time.sleep(delay)

    def display_on(self):
        self._send_cmd([0xFE, 0x41], delay=0.01)

    def clear(self):
        self._send_cmd([0xFE, 0x51], delay=0.02)

    def set_contrast(self, level: int):
        level = max(1, min(50, level))
        self._send_cmd([0xFE, 0x52, level], delay=0.01)

    def set_backlight(self, level: int):
        level = max(1, min(8, level))
        self._send_cmd([0xFE, 0x53, level], delay=0.01)

    def set_cursor(self, line: int, col: int):
        if 0 <= line <= 3 and 0 <= col <= 19:
            pos = self.LINE_OFFSETS[line] + col
            self._send_cmd([0xFE, 0x45, pos], delay=0.005)

    def write_string(self, text: str):
        if not self.bus or not text:
            return
        try:
            char_bytes = [ord(c) for c in text]
            msg = i2c_msg.write(self.address, char_bytes)
            self.bus.i2c_rdwr(msg)
        except Exception as e:
            print(f"I2C Write Char Error: {e}")
        time.sleep(0.005)

    def write_line(self, line: int, text: str):
        formatted_text = text.ljust(20)[:20]
        self.set_cursor(line, 0)
        self.write_string(formatted_text)

    def close(self):
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

        self.lcd_lock = threading.Lock()
        self.framebuffer = [""] * self.rows

        if self.type.lower() == "newhaven":
            try:
                bus_num = int(self.port)
            except ValueError:
                bus_num = 1
            contrast = getattr(config, "contrast", 40)
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

    def clear(self):
        """Clear the LCD display and reset the framebuffer."""
        with self.lcd_lock:
            if hasattr(self.backend, "clear"):
                self.backend.clear()
        self.framebuffer = [""] * self.rows

    def write_message(self, message: str, row: int = 0, _col: int = 0):
        """Write a message to a row on the LCD, truncating if over 20 characters."""
        if 0 <= row < self.rows:
            self.framebuffer[row] = message[: self.cols]
            self._update_lcd(row)

    def _update_lcd(self, row: int | None = None):
        with self.lcd_lock:
            try:
                if self.type.lower() == "newhaven":
                    if hasattr(self.backend, "write_line"):
                        if row is None:
                            for i in range(self.rows):
                                self.backend.write_line(i, self.framebuffer[i].ljust(self.cols))
                        else:
                            self.backend.write_line(row, self.framebuffer[row].ljust(self.cols))
                else:
                    if self.backend:
                        if row is None:
                            self.backend.home()
                            for i in range(self.rows):
                                self.backend.cursor_pos = (i, 0)
                                self.backend.write_string(self.framebuffer[i].ljust(self.cols))
                        else:
                            self.backend.cursor_pos = (row, 0)
                            self.backend.write_string(self.framebuffer[row].ljust(self.cols))
            except IOError:
                print("ERROR: Failed to write to LCD. Retrying.")
                time.sleep(0.1)
                self._update_lcd(row)


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
