#!/usr/bin/env python3
import time
from smbus2 import SMBus

BUS = 1
ADDRESS = 0x28

def render_80(l0, l1, l2, l3):
    # HD44780 sequential order: Line 0 -> Line 2 -> Line 1 -> Line 3
    s0 = l0.ljust(20)[:20]
    s1 = l1.ljust(20)[:20]
    s2 = l2.ljust(20)[:20]
    s3 = l3.ljust(20)[:20]
    return (s0 + s2 + s1 + s3).encode("latin-1", errors="replace")

def main():
    print("=" * 60)
    print("   DIRECT SMBUS WRITE_BYTE PACED TEST (2ms per byte)   ")
    print("=" * 60)
    
    with SMBus(BUS) as bus:
        time.sleep(0.2)
        
        # 1. Wipe with 80 spaces
        print("[1] Wiping 80 spaces via write_byte...")
        for b in (b" " * 80):
            bus.write_byte(ADDRESS, b)
            time.sleep(0.002)
            
        time.sleep(0.05)
        
        # 2. Write 4 lines
        print("[2] Writing 4 lines via write_byte...")
        payload = render_80(
            "OpenCAL System Ready",
            "Hardware: ONLINE",
            "VAM Control Unit",
            "Status: 100% PERFECT"
        )
        
        for b in payload:
            bus.write_byte(ADDRESS, b)
            time.sleep(0.002)

    print("\n" + "=" * 60)
    print("DIRECT WRITE_BYTE COMPLETE! Check screen now.")
    print("=" * 60)

if __name__ == "__main__":
    main()
