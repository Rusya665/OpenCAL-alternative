#!/usr/bin/env python3
import threading
import time
from smbus2 import SMBus


class PacedNewhaven0420D3Z:
    """
    Paced Character Driver for Newhaven NHD-0420D3Z.
    Eliminates byte-dropping by giving the PIC16F690 1.2ms per character.
    """
    DEFAULT_ADDRESS = 0x28
    LINE_OFFSETS = (0x00, 0x40, 0x14, 0x54)
    PREFIX = 0xFE

    CMD_DISPLAY_ON = 0x41
    CMD_CLEAR = 0x51
    CMD_SET_CURSOR = 0x45
    CMD_SET_CONTRAST = 0x52
    CMD_SET_BACKLIGHT = 0x53

    def __init__(self, bus_number: int = 1, address: int = DEFAULT_ADDRESS):
        self.bus_number = bus_number
        self.address = address
        self._lock = threading.RLock()
        self.bus = SMBus(self.bus_number)
        time.sleep(0.5)

    def command(self, cmd: int, *params: int, delay: float = 0.050) -> None:
        with self._lock:
            # Send 0xFE prefix with inter-byte delay
            self.bus.write_byte(self.address, self.PREFIX)
            time.sleep(0.003)
            self.bus.write_byte(self.address, cmd)
            time.sleep(0.003)
            for p in params:
                self.bus.write_byte(self.address, p)
                time.sleep(0.003)
            time.sleep(delay)

    def display_on(self) -> None:
        self.command(self.CMD_DISPLAY_ON, delay=0.020)

    def clear(self) -> None:
        # Clear screen requires at least 150ms on PIC16F690
        self.command(self.CMD_CLEAR, delay=0.150)

    def set_cursor(self, row: int, col: int = 0) -> None:
        pos = self.LINE_OFFSETS[row] + col
        self.command(self.CMD_SET_CURSOR, pos, delay=0.010)

    def write_line(self, row: int, text: str) -> None:
        line = text.ljust(20)[:20]
        with self._lock:
            self.set_cursor(row, 0)
            # Write each character with 1.2ms pacing to prevent skipped letters
            for char in line:
                self.bus.write_byte(self.address, ord(char))
                time.sleep(0.0012)
            time.sleep(0.010)

    def close(self) -> None:
        self.bus.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    print("=" * 60)
    print("      FINAL PACED CHARACTER TEST (NO SKIPPED BYTES)     ")
    print("=" * 60)
    
    with PacedNewhaven0420D3Z() as lcd:
        print("[1] Display ON...")
        lcd.display_on()
        
        print("[2] Clear Screen (150ms delay)...")
        lcd.clear()
        
        print("[3] Writing 4 Perfect Lines...")
        lcd.write_line(0, "Newhaven Display")
        lcd.write_line(1, "4x20 Serial LCD")
        lcd.write_line(2, "Python Raspberry Pi")
        lcd.write_line(3, "I2C address 0x28")

    print("\n" + "=" * 60)
    print("TEST FINISHED! Check physical screen now.")
    print("=" * 60)


if __name__ == "__main__":
    main()
