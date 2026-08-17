#!/usr/bin/env python3
import threading
import time
from smbus2 import SMBus, i2c_msg


class Newhaven0420D3Z:
    """
    Exact 1-to-1 Python implementation of Newhaven's official Serial_LCD.ino:
    Every byte is sent in its own isolated I2C transaction:
    START -> Address -> 1 Data Byte -> STOP -> Delay
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
        byte_delay: float = 0.001,
    ):
        self.bus_number = int(bus_number)
        self.address = int(address)
        self.byte_delay = float(byte_delay)
        self._lock = threading.RLock()
        self._closed = False
        self.bus = SMBus(self.bus_number)
        print(f"Initializing LCD: {startup_delay * 1000:.0f} ms startup delay, {byte_delay * 1000:.1f} ms byte delay")
        time.sleep(startup_delay)

    def _write_byte(self, value: int) -> None:
        """
        One byte per complete I2C transaction:
        START -> Slave Address+W -> One Data Byte -> STOP
        """
        if self._closed:
            raise RuntimeError("LCD bus is closed")
        if not 0 <= value <= 0xFF:
            raise ValueError(f"I2C byte outside range: {value}")
        with self._lock:
            message = i2c_msg.write(self.address, [value])
            self.bus.i2c_rdwr(message)
            if self.byte_delay > 0:
                time.sleep(self.byte_delay)

    def _write_sequence(self, values) -> None:
        """Send every byte as a separate I2C transaction with STOP condition."""
        with self._lock:
            for value in values:
                self._write_byte(int(value))

    def command(self, command: int, *parameters: int, execution_delay: float = 0.002) -> None:
        sequence = (self.PREFIX, command, *parameters)
        print("CMD TX:", " ".join(f"{v:02X}" for v in sequence))
        with self._lock:
            self._write_sequence(sequence)
            if execution_delay > 0:
                time.sleep(execution_delay)

    def display_on(self) -> None:
        self.command(self.CMD_DISPLAY_ON, execution_delay=0.005)

    def display_off(self) -> None:
        self.command(self.CMD_DISPLAY_OFF, execution_delay=0.005)

    def clear(self) -> None:
        self.command(self.CMD_CLEAR, execution_delay=0.020)

    def home(self) -> None:
        self.command(self.CMD_CURSOR_HOME, execution_delay=0.010)

    def set_contrast(self, level: int) -> None:
        level = max(1, min(50, int(level)))
        self.command(self.CMD_SET_CONTRAST, level, execution_delay=0.005)

    def set_backlight(self, level: int) -> None:
        level = max(1, min(8, int(level)))
        self.command(self.CMD_SET_BACKLIGHT, level, execution_delay=0.005)

    def set_cursor(self, row: int, column: int = 0) -> None:
        if not 0 <= row <= 3:
            raise ValueError("row must be between 0 and 3")
        if not 0 <= column <= 19:
            raise ValueError("column must be between 0 and 19")
        position = self.LINE_OFFSETS[row] + column
        self.command(self.CMD_SET_CURSOR, position, execution_delay=0.002)

    def write(self, text: str) -> None:
        data = text.encode("ascii", errors="replace")
        print(f"TEXT TX: {text!r}")
        self._write_sequence(data)

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
    print("  EXACT 1-BYTE-PER-TRANSACTION OFFICIAL NEWHAVEN TEST  ")
    print("=" * 60)
    
    with Newhaven0420D3Z(
        bus_number=1,
        address=0x28,
        startup_delay=0.5,
        byte_delay=0.001,
    ) as lcd:
        print("\n[1] Display ON...")
        lcd.display_on()
        
        print("\n[2] Clear Screen (20ms delay)...")
        lcd.clear()
        
        print("\n[3] Writing 4 Repeating Lines...")
        lcd.write_line(0, "11111111111111111111")
        lcd.write_line(1, "22222222222222222222")
        lcd.write_line(2, "33333333333333333333")
        lcd.write_line(3, "44444444444444444444")

    print("\n" + "=" * 60)
    print("TEST FINISHED! Look at the physical screen now.")
    print("=" * 60)


if __name__ == "__main__":
    main()
