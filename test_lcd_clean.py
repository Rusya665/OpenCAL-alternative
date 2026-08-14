import time
from smbus2 import SMBus

def main():
    print("=" * 50)
    print("      NEWHAVEN LCD CLEAN CHARACTER TEST          ")
    print("=" * 50)
    
    addr = 0x28
    bus = SMBus(1)
    
    # 1. Turn display ON
    print("Sending Display ON...")
    bus.write_byte(addr, 0xFE)
    time.sleep(0.002)
    bus.write_byte(addr, 0x41)
    time.sleep(0.010)
    
    # 2. Clear Screen
    print("Sending Clear Screen...")
    bus.write_byte(addr, 0xFE)
    time.sleep(0.002)
    bus.write_byte(addr, 0x51)
    time.sleep(0.020)
    
    # 3. Set Backlight to 8
    print("Setting Backlight Max...")
    bus.write_byte(addr, 0xFE)
    time.sleep(0.002)
    bus.write_byte(addr, 0x53)
    time.sleep(0.002)
    bus.write_byte(addr, 8)
    time.sleep(0.010)
    
    # 4. Set Contrast to 40
    print("Setting Contrast 40...")
    bus.write_byte(addr, 0xFE)
    time.sleep(0.002)
    bus.write_byte(addr, 0x52)
    time.sleep(0.002)
    bus.write_byte(addr, 40)
    time.sleep(0.010)
    
    # 5. Write 4 Clean Lines
    lines = [
        "OpenCAL 3D Printer",
        "Line 1: 1234567890",
        "Line 2: Ready!",
        "Line 3: Clean Text"
    ]
    offsets = [0x00, 0x40, 0x14, 0x54]
    
    for row, text in enumerate(lines):
        print(f"Writing Row {row}: '{text}'...")
        # Set cursor
        bus.write_byte(addr, 0xFE)
        time.sleep(0.002)
        bus.write_byte(addr, 0x45)
        time.sleep(0.002)
        bus.write_byte(addr, offsets[row])
        time.sleep(0.005)
        
        # Write characters with 2.5ms spacing
        padded = text.ljust(20)[:20]
        for char in padded:
            bus.write_byte(addr, ord(char))
            time.sleep(0.0025)
            
    print("\nTest Complete! Look at the physical LCD screen now.")

if __name__ == "__main__":
    main()
