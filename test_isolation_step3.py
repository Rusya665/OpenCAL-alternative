import time
from smbus2 import SMBus, i2c_msg

BUS = 1
ADDRESS = 0x28

def main():
    print("=" * 60)
    print("  ISOLATION TEST #3: PROTOCOL & REGISTER FORMAT PROBE")
    print("=" * 60)
    
    with SMBus(BUS) as bus:
        print("[1] Test SMBus write_byte_data (Reg=0xFE, Data=0x51 - Clear Screen)...")
        try:
            bus.write_byte_data(ADDRESS, 0xFE, 0x51)
            print("  -> write_byte_data(0xFE, 0x51) SUCCESS!")
        except Exception as e:
            print(f"  -> write_byte_data ERROR: {e}")
        time.sleep(0.100)
        
        print("\n[2] Test SMBus write_i2c_block_data (Reg=0xFE, [0x45, 0x00] - Cursor Line 0)...")
        try:
            bus.write_i2c_block_data(ADDRESS, 0xFE, [0x45, 0x00])
            print("  -> write_i2c_block_data(0xFE, [0x45, 0x00]) SUCCESS!")
        except Exception as e:
            print(f"  -> write_i2c_block_data ERROR: {e}")
        time.sleep(0.020)
        
        print("\n[3] Writing 'HELLO WORLD' with write_byte...")
        for char in "HELLO WORLD":
            bus.write_byte(ADDRESS, ord(char))
            time.sleep(0.002)
            
    print("\n" + "=" * 60)
    print("TEST #3 FINISHED: Check physical screen now.")
    print("Did the screen CLEAR? Does it show 'HELLO WORLD' at the top?")
    print("=" * 60)

if __name__ == "__main__":
    main()
