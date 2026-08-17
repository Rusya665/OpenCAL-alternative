import time
from smbus2 import SMBus, i2c_msg

BUS = 1
ADDRESS = 0x28

def main():
    print("=" * 60)
    print("    TESTING COMMAND PREFIXES (0xFE, 0xFD, 0x1B, 0x00)")
    print("=" * 60)
    
    with SMBus(BUS) as bus:
        # Test 1: 0xFE 0x51 with 200ms pause
        print("[1] Sending 0xFE 0x51 (Clear Screen)...")
        bus.i2c_rdwr(i2c_msg.write(ADDRESS, [0xFE, 0x51]))
        time.sleep(0.2)
        
        # Test 2: 0xFD 0x51
        print("[2] Sending 0xFD 0x51...")
        bus.i2c_rdwr(i2c_msg.write(ADDRESS, [0xFD, 0x51]))
        time.sleep(0.2)
        
        # Test 3: 0x1B 0x51
        print("[3] Sending 0x1B 0x51...")
        bus.i2c_rdwr(i2c_msg.write(ADDRESS, [0x1B, 0x51]))
        time.sleep(0.2)
        
        # Test 4: 0x00 0x01 (HD44780 raw clear)
        print("[4] Sending 0x00 0x01...")
        bus.i2c_rdwr(i2c_msg.write(ADDRESS, [0x00, 0x01]))
        time.sleep(0.2)

    print("\nCheck screen: Did ANY of these 4 commands wipe the screen?")

if __name__ == "__main__":
    main()
