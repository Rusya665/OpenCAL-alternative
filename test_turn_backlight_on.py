#!/usr/bin/env python3
import time
from smbus2 import SMBus, i2c_msg

BUS = 1
ADDRESS = 0x28

def main():
    print("=" * 60)
    print("      TURNING BACKLIGHT TO MAX BRIGHTNESS (8)      ")
    print("=" * 60)
    
    with SMBus(BUS) as bus:
        # Method 1: Single packet i2c_msg
        print("[1] Sending Backlight Max (0xFE 0x53 0x08)...")
        try:
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, [0xFE, 0x53, 8]))
            time.sleep(0.050)
            print("  -> Backlight command 0x53 0x08 sent!")
        except Exception as e:
            print(f"Error: {e}")
            
        # Method 2: Also set Contrast to 42
        print("[2] Sending Contrast (0xFE 0x52 42)...")
        try:
            bus.i2c_rdwr(i2c_msg.write(ADDRESS, [0xFE, 0x52, 42]))
            time.sleep(0.050)
            print("  -> Contrast command 0x52 42 sent!")
        except Exception as e:
            print(f"Error: {e}")

    print("\nCheck screen: Did the backlight glow brightly?")

if __name__ == "__main__":
    main()
