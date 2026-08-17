import time
from smbus2 import SMBus, i2c_msg

BUS = 1
ADDRESS = 0x28

def main():
    print("=" * 60)
    print("  ISOLATION TEST #2: PACED BYTE-BY-BYTE TRANSMISSION")
    print("=" * 60)
    
    with SMBus(BUS) as bus:
        # Helper to send atomic command with post-delay
        def send_cmd(cmd_list, delay=0.010):
            msg = i2c_msg.write(ADDRESS, cmd_list)
            bus.i2c_rdwr(msg)
            time.sleep(delay)
            
        def write_paced_string(text, char_delay=0.0015):
            for char in text:
                bus.write_byte(ADDRESS, ord(char))
                time.sleep(char_delay)
                
        print("[1] Power-up settling pause (200ms)...")
        time.sleep(0.2)
        
        print("[2] Display ON (0xFE 0x41)...")
        send_cmd([0xFE, 0x41], delay=0.020)
        
        print("[3] Deep Clear Screen (0xFE 0x51, 100ms pause)...")
        send_cmd([0xFE, 0x51], delay=0.100)
        
        # Row 0
        print("[4] Writing Row 0: 20 'A's with 1.5ms inter-byte pacing...")
        send_cmd([0xFE, 0x45, 0x00], delay=0.010)
        write_paced_string("AAAAAAAAAAAAAAAAAAAA", char_delay=0.0015)
        time.sleep(0.010)
        
        # Row 1
        print("[5] Writing Row 1: 20 'B's with 1.5ms inter-byte pacing...")
        send_cmd([0xFE, 0x45, 0x40], delay=0.010)
        write_paced_string("BBBBBBBBBBBBBBBBBBBB", char_delay=0.0015)
        time.sleep(0.010)
        
        # Row 2
        print("[6] Writing Row 2: 20 'C's with 1.5ms inter-byte pacing...")
        send_cmd([0xFE, 0x45, 0x14], delay=0.010)
        write_paced_string("CCCCCCCCCCCCCCCCCCCC", char_delay=0.0015)
        time.sleep(0.010)
        
        # Row 3
        print("[7] Writing Row 3: 20 'D's with 1.5ms inter-byte pacing...")
        send_cmd([0xFE, 0x45, 0x54], delay=0.010)
        write_paced_string("DDDDDDDDDDDDDDDDDDDD", char_delay=0.0015)
        time.sleep(0.010)

    print("\n" + "=" * 60)
    print("TEST #2 FINISHED: Awaiting physical screen confirmation.")
    print("=" * 60)

if __name__ == "__main__":
    main()
