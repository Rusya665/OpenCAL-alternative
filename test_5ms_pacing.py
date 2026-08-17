#!/usr/bin/env python3
import time
from smbus2 import SMBus, i2c_msg

BUS = 1
ADDRESS = 0x28

def render_80_chars(r0: str, r1: str, r2: str, r3: str) -> bytes:
    # 20x4 HD44780 sequential memory: Line 0 -> Line 2 -> Line 1 -> Line 3
    stream = r0.ljust(20)[:20] + r2.ljust(20)[:20] + r1.ljust(20)[:20] + r3.ljust(20)[:20]
    return stream.encode("ascii", errors="replace")

def main():
    print("=" * 60)
    print("      GENEROUS 5MS-PER-CHAR PACED STREAM TEST          ")
    print("=" * 60)
    
    with SMBus(BUS) as bus:
        print("[1] Settling delay...")
        time.sleep(0.3)
        
        # 1. Send Clear / Home commands with generous delays
        print("[2] Sending Display ON & Clear Screen (200ms pause)...")
        try:
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, [0xFE, 0x41]))
            time.sleep(0.050)
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, [0xFE, 0x51]))
            time.sleep(0.200)
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, [0xFE, 0x45, 0x00]))
            time.sleep(0.050)
        except Exception as e:
            print(f"Command Error: {e}")
            
        # 2. Write 80 characters with 5ms pacing per character
        print("[3] Streaming 80 characters with 5.0ms pacing...")
        payload = render_80_chars(
            r0="OpenCAL 3D Printer",
            r1="Hardware: ONLINE",
            r2="Motor & LEDs: READY",
            r3="System 100% PERFECT!"
        )
        
        for idx, char_byte in enumerate(payload):
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, [char_byte]))
            time.sleep(0.005) # 5.0ms generous pause per character!
            
    print("\n" + "=" * 60)
    print("5MS PACED TEST FINISHED! Check screen now.")
    print("=" * 60)

if __name__ == "__main__":
    main()
