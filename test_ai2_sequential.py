#!/usr/bin/env python3
import time
from smbus2 import SMBus, i2c_msg


class NewhavenSequentialLCD:
    """
    Pure Framebuffer Driver for Newhaven NHD-0420D3Z.
    Requires NO 0xFE commands. Uses hardware sequential DDRAM progression:
    Line 0 (0x00) -> Line 2 (0x14) -> Line 1 (0x40) -> Line 3 (0x54)
    """
    def __init__(self, bus_num: int = 1, address: int = 0x28, char_delay: float = 0.0015):
        self.bus_num = bus_num
        self.address = address
        self.char_delay = char_delay  # 1.5ms per character prevents FIFO drops
        self.bus = SMBus(self.bus_num)
        time.sleep(0.150)  # Power-on delay

    def render(self, line0: str = "", line1: str = "", line2: str = "", line3: str = "") -> None:
        """
        Pads each line to 20 characters and writes an 80-byte continuous frame.
        Physical DDRAM progression maps Line 0 -> Line 2 -> Line 1 -> Line 3.
        """
        # 1. Normalize lines to 20 characters each
        l0 = line0.ljust(20)[:20]
        l1 = line1.ljust(20)[:20]
        l2 = line2.ljust(20)[:20]
        l3 = line3.ljust(20)[:20]

        # 2. Arrange into the hardware DDRAM layout
        framebuffer = (l0 + l2 + l1 + l3).encode("latin-1", errors="replace")

        # 3. Transmit paced bytes sequentially (1 byte per transaction)
        for char_byte in framebuffer:
            msg = i2c_msg.write(self.address, [char_byte])
            self.bus.i2c_rdwr(msg)
            time.sleep(self.char_delay)

    def clear(self) -> None:
        """Clears the screen by overwriting all 80 characters with spaces."""
        self.render(" ", " ", " ", " ")

    def close(self) -> None:
        self.bus.close()


if __name__ == "__main__":
    print("=" * 60)
    print("    TESTING AI 2 SEQUENTIAL FRAMEBUFFER DRIVER    ")
    print("=" * 60)
    
    lcd = NewhavenSequentialLCD(bus_num=1, address=0x28, char_delay=0.0015)
    
    print("[1] Wiping 80 spaces...")
    lcd.clear()
    time.sleep(0.050)
    
    print("[2] Rendering 4 Clean Rows...")
    lcd.render(
        line0="OpenCAL System Ready",
        line1="Status: Online",
        line2="VAM Control Unit",
        line3="IP: 10.49.26.109"
    )
    
    print("\n" + "=" * 60)
    print("RENDER COMPLETE! Look at the physical screen now.")
    print("=" * 60)
