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
    
    stream = r0 + r2 + r1 + r3
    return stream.encode("ascii", errors="replace")


def main():
    print("=" * 60)
    print("      HD44780 80-CHARACTER FRAMEBUFFER STREAM TEST      ")
    print("=" * 60)
    
    with SMBus(BUS) as bus:
        print("[1] Power-up settling pause...")
        time.sleep(0.2)
        
        # 1. First wipe entire screen with 80 spaces
        print("[2] Wiping screen with 80 spaces...")
        spaces_payload = b" " * 80
        # Send in small chunks with brief pause to guarantee 0 dropped chars
        for i in range(0, 80, 20):
            chunk = spaces_payload[i:i+20]
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, chunk))
            time.sleep(0.015)
            
        time.sleep(0.1)
        
        # 2. Render 4 Clean Rows
        print("[3] Streaming 4 Clean Rows...")
        payload = render_80_chars(
            row0="OpenCAL 3D Printer",
            row1="Hardware: ONLINE",
            row2="Motor & LEDs: READY",
            row3="System 100% OK!"
        )
        
        for i in range(0, 80, 20):
            chunk = payload[i:i+20]
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, chunk))
            time.sleep(0.015)

    print("\n" + "=" * 60)
    print("STREAM FINISHED! Check the physical LCD screen now.")
    print("=" * 60)


if __name__ == "__main__":
    main()
