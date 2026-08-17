#!/usr/bin/env python3
import threading
import time
from smbus2 import SMBus, i2c_msg


class Newhaven0420D3Z:
    """
    Direct Python translation of Newhaven Display's Official Serial_LCD.ino reference.
    Target: NHD-0420D3Z-NSW-BBW-V3 (PIC16F690 controller)
    """
    DEFAULT_ADDRESS = 0x28
    LINE_OFFSETS = (0x00, 0x40, 0x14, 0x54)
    PREFIX = 0xFE

    CMD_DISPLAY_ON = 0x41
    CMD_DISPLAY_OFF = 0x42
    CMD_SET_CURSOR = 0x45
    CMD_CURSOR_HOME = 0x46
    CMD_CLEAR = 0x51
    CMD_SET_CONTRAST = 0x52
    CMD_SET_BACKLIGHT = 0x53

    def __init__(
        self,
        bus_number: int = 1,
        address: int = DEFAULT_ADDRESS,
        startup_delay: float = 0.5,
        operation_delay: float = 0.1,
    ):
        self.bus_number = int(bus_number)
        self.address = int(address)
        self.operation_delay = float(operation_delay)
        self._lock = threading.RLock()
        self._closed = False
        self.bus = SMBus(self.bus_number)
        
        # Newhaven official reference uses 500ms startup delay
        print(f"[1] Initializing Newhaven LCD with {startup_delay*1000:.0f}ms startup delay...")
        time.sleep(startup_delay)

    def _write(self, payload, delay: float | None = None) -> None:
        if self._closed:
            raise RuntimeError("LCD bus is closed")
        data = bytes(payload)
        if not data:
            return
        wait = self.operation_delay if delay is None else delay
        with self._lock:
            message = i2c_msg.write(self.address, data)
            self.bus.i2c_rdwr(message)
            if wait > 0:
                time.sleep(wait)

    def command(self, command: int, *parameters: int, delay: float | None = None) -> None:
        payload = bytes([self.PREFIX, command, *parameters])
        print(f"  -> CMD TX: {payload.hex(' ')} (wait {self.operation_delay*1000:.0f}ms)")
        self._write(payload, delay=delay)

    def display_on(self) -> None:
        self.command(self.CMD_DISPLAY_ON)

    def display_off(self) -> None:
        self.command(self.CMD_DISPLAY_OFF)

    def clear(self) -> None:
        self.command(self.CMD_CLEAR, delay=0.150)

    def home(self) -> None:
        self.command(self.CMD_CURSOR_HOME)

    def set_contrast(self, level: int) -> None:
        level = max(1, min(50, int(level)))
        self.command(self.CMD_SET_CONTRAST, level)

    def set_backlight(self, level: int) -> None:
        level = max(1, min(8, int(level)))
        self.command(self.CMD_SET_BACKLIGHT, level)

    def set_cursor(self, row: int, column: int = 0) -> None:
        if not 0 <= row <= 3:
            raise ValueError("row must be between 0 and 3")
        if not 0 <= column <= 19:
            raise ValueError("column must be between 0 and 19")
        position = self.LINE_OFFSETS[row] + column
        self.command(self.CMD_SET_CURSOR, position)

    def write(self, text: str) -> None:
        data = text.encode("ascii", errors="replace")
        print(f"  -> TEXT TX: {text!r}")
        self._write(data)

    def write_line(self, row: int, text: str) -> None:
        line = text.ljust(20)[:20]
        with self._lock:
            self.set_cursor(row, 0)
            self.write(line)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self.bus.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def main():
    print("=" * 60)
    print("  OFFICIAL NEWHAVEN SERIAL_LCD PORT TEST (100ms I2C_DELAY) ")
    print("=" * 60)
    
    with Newhaven0420D3Z(
        bus_number=1,
        address=0x28,
        startup_delay=0.5,
        operation_delay=0.1,
    ) as lcd:
        print("\n[Step 1] Sending Display ON...")
        lcd.display_on()
        
        print("\n[Step 2] Sending Clear Screen (150ms delay)...")
        lcd.clear()
        
        print("\n[Step 3] Writing 4 Distinct Rows...")
        lcd.write_line(0, "Newhaven Display")
        lcd.write_line(1, "4x20 Serial LCD")
        lcd.write_line(2, "Python Raspberry Pi")
        lcd.write_line(3, "I2C address 0x28")

    print("\n" + "=" * 60)
    print("OFFICIAL PORT TEST COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
