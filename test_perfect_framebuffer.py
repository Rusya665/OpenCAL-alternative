#!/usr/bin/env python3
import time
from smbus2 import SMBus, i2c_msg

BUS = 1
ADDRESS = 0x28


def render_80_chars(row0: str, row1: str, row2: str, row3: str) -> bytes:
    """
    Assembles a 20x4 screen buffer in HD44780 sequential memory order:
    Row 0 (20 chars) -> Row 2 (20 chars) -> Row 1 (20 chars) -> Row 3 (20 chars)
    Total = 80 characters exactly.
    """
    r0 = row0.ljust(20)[:20]
    r1 = row1.ljust(20)[:20]
    r2 = row2.ljust(20)[:20]
    r3 = row3.ljust(20)[:20]
    
    # Sequential memory flow of 20x4 HD44780: Line 0 -> Line 2 -> Line 1 -> Line 3
    stream = r0 + r2 + r1 + r3
    return stream.encode("ascii", errors="replace")


def main():
    print("=" * 60)
    print("      PERFECT 80-CHARACTER PACED FRAMEBUFFER TEST       ")
    print("=" * 60)
    
    with SMBus(BUS) as bus:
        print("[1] Power-up settling pause...")
        time.sleep(0.2)
        
        # 1. First wipe entire screen with 80 spaces (1.0ms per space)
        print("[2] Wiping screen with 80 paced spaces...")
        for b in (b" " * 80):
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, [b]))
            time.sleep(0.001)
            
        time.sleep(0.05)
        
        # 2. Render 4 Perfect Rows
        print("[3] Streaming 4 Perfect Rows (1.2ms per char)...")
        payload = render_80_chars(
            row0="OpenCAL 3D Printer",
            row1="Hardware: ONLINE",
            row2="Motor & LEDs: READY",
            row3="System 100% PERFECT!"
        )
        
        for b in payload:
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, [b]))
            time.sleep(0.0012)

    print("\n" + "=" * 60)
    print("TEST FINISHED! Look at the physical screen now.")
    print("=" * 60)


if __name__ == "__main__":
    main()
