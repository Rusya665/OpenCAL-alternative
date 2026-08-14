import time
import ticlib
from smbus2 import SMBus

def check_tic():
    print("=" * 50)
    print("      POLOLU TIC MOTOR CONTROLLER DIAGNOSTIC      ")
    print("=" * 50)
    try:
        tic = ticlib.TicUSB()
        err = tic.get_error_status()
        state = tic.get_operation_state()
        vin = tic.get_vin_voltage()
        cur = tic.get_current_limit()
        step = tic.get_step_mode()
        pos = tic.get_current_position()
        target = tic.get_target_position()
        
        print(f"  Operation State: {state}")
        print(f"  Error Status:    {hex(err)} (0x0 = No Error)")
        print(f"  VIN Voltage:     {vin} mV ({vin/1000.0:.2f} V)")
        print(f"  Current Limit:   {cur} mA")
        print(f"  Step Mode:       {step}")
        print(f"  Position:        {pos} (Target: {target})")
        
        # Test basic movement
        print("\nTesting safe reset & 200 step movement...")
        tic.energize()
        tic.exit_safe_start()
        tic.set_target_position(pos + 200)
        time.sleep(0.5)
        print(f"  Position after 200 steps: {tic.get_current_position()}")
        tic.set_target_position(pos)
        time.sleep(0.5)
        tic.deenergize()
        print("  -> Tic Diagnostic Complete!")
    except Exception as e:
        print("Tic Diagnostic Error:", e)

def check_lcd():
    print("\n" + "=" * 50)
    print("      NEWHAVEN LCD CONTROLLER DIAGNOSTIC         ")
    print("=" * 50)
    try:
        bus = SMBus(1)
        addr = 0x28
        print(f"Sending raw I2C Display ON and Contrast/Backlight sweeps to 0x{addr:X}...")
        
        # Turn display on
        bus.write_byte(addr, 0xFE)
        time.sleep(0.001)
        bus.write_byte(addr, 0x41)
        time.sleep(0.01)
        
        # Backlight max (8)
        bus.write_byte(addr, 0xFE)
        time.sleep(0.001)
        bus.write_byte(addr, 0x53)
        time.sleep(0.001)
        bus.write_byte(addr, 0x08)
        time.sleep(0.01)
        
        # Clear screen
        bus.write_byte(addr, 0xFE)
        time.sleep(0.001)
        bus.write_byte(addr, 0x51)
        time.sleep(0.02)
        
        # Set contrast to 35, 40, 45, 50 to see if text appears
        for contrast in [40, 45, 50, 30]:
            print(f"Testing Contrast Level {contrast}...")
            bus.write_byte(addr, 0xFE)
            time.sleep(0.001)
            bus.write_byte(addr, 0x52)
            time.sleep(0.001)
            bus.write_byte(addr, contrast)
            time.sleep(0.01)
            
            # Write Hello
            bus.write_byte(addr, 0xFE)
            time.sleep(0.001)
            bus.write_byte(addr, 0x45)
            time.sleep(0.001)
            bus.write_byte(addr, 0x00) # Line 0
            time.sleep(0.01)
            
            msg = f"TEST CONTRAST {contrast}"
            for ch in msg:
                bus.write_byte(addr, ord(ch))
                time.sleep(0.001)
            time.sleep(1.0)
            
        print("  -> LCD Diagnostic Complete!")
    except Exception as e:
        print("LCD Diagnostic Error:", e)

if __name__ == "__main__":
    check_tic()
    check_lcd()
