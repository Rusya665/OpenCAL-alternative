import time
from smbus2 import SMBus, i2c_msg

BUS = 1
ADDRESS = 0x28

def write(bus, payload, delay=0.005):
    payload = bytes(payload)
    print("TX:", payload.hex(" "))
    bus.i2c_rdwr(i2c_msg.write(ADDRESS, payload))
    time.sleep(delay)

def main():
    print("=" * 60)
    print("    ISOLATION TEST: 4-ROW PURE TEXT TRANSPORT")
    print("=" * 60)
    
    with SMBus(BUS) as bus:
        print("[1] Power-up settling pause (200ms)...")
        time.sleep(0.2)
        
        print("[2] Display ON (0xFE 0x41)...")
        write(bus, [0xFE, 0x41], delay=0.010)
        
        print("[3] Clear Screen (0xFE 0x51, 50ms pause)...")
        write(bus, [0xFE, 0x51], delay=0.050)
        
        print("[4] Writing Row 0 (0x00)...")
        write(bus, [0xFE, 0x45, 0x00], delay=0.005)
        write(bus, b"AAAAAAAAAAAAAAAAAAAA", delay=0.005)
        
        print("[5] Writing Row 1 (0x40)...")
        write(bus, [0xFE, 0x45, 0x40], delay=0.005)
        write(bus, b"BBBBBBBBBBBBBBBBBBBB", delay=0.005)
        
        print("[6] Writing Row 2 (0x14)...")
        write(bus, [0xFE, 0x45, 0x14], delay=0.005)
        write(bus, b"CCCCCCCCCCCCCCCCCCCC", delay=0.005)
        
        print("[7] Writing Row 3 (0x54)...")
        write(bus, [0xFE, 0x45, 0x54], delay=0.005)
        write(bus, b"DDDDDDDDDDDDDDDDDDDD", delay=0.005)

    print("\n" + "=" * 60)
    print("TEST FINISHED: Awaiting physical screen confirmation.")
    print("=" * 60)

if __name__ == "__main__":
    main()
