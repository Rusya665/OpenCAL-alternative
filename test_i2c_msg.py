import time
from smbus2 import SMBus, i2c_msg

def main():
    print("=" * 60)
    print("   NEWHAVEN LCD TEST USING SINGLE I2C_MSG PACKETS   ")
    print("=" * 60)
    
    addr = 0x28
    bus = SMBus(1)
    
    def send_cmd(cmd_list, delay=0.01):
        msg = i2c_msg.write(addr, cmd_list)
        bus.i2c_rdwr(msg)
        time.sleep(delay)
        
    def write_text_at(line, text):
        offsets = [0x00, 0x40, 0x14, 0x54]
        # Set cursor in single packet
        send_cmd([0xFE, 0x45, offsets[line]], delay=0.005)
        # Send text characters in single packet
        formatted = text.ljust(20)[:20]
        char_bytes = [ord(c) for c in formatted]
        msg = i2c_msg.write(addr, char_bytes)
        bus.i2c_rdwr(msg)
        time.sleep(0.005)

    print("1. Display ON...")
    send_cmd([0xFE, 0x41], delay=0.01)
    
    print("2. Setting Backlight to 8...")
    send_cmd([0xFE, 0x53, 8], delay=0.01)
    
    print("3. Setting Contrast to 40...")
    send_cmd([0xFE, 0x52, 40], delay=0.01)
    
    print("4. Clear Screen...")
    send_cmd([0xFE, 0x51], delay=0.02)
    
    print("5. Writing 4 Lines...")
    write_text_at(0, "OpenCAL V2 Ready!")
    write_text_at(1, "Newhaven I2C Packet")
    write_text_at(2, "Hardware: ONLINE")
    write_text_at(3, "Status: 100% PERFECT")
    
    print("\nSUCCESS! Check the physical LCD screen now.")

if __name__ == "__main__":
    main()
