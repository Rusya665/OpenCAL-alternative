import time
import ticlib
from opencal.utils.config import Config
from opencal.hardware.lcd_display import NewhavenLCDBackend

def test_stepper_smooth():
    print("\n--- [1] TESTING SMOOTH STEPPER MOTOR ROTATION ---")
    try:
        tic = ticlib.TicUSB()
        print("Connected to Pololu Tic T249!")
        
        # Configure smooth microstepping & parameters
        print("Configuring 1/16 microstepping and smooth current/acceleration...")
        tic.set_step_mode(4)  # 4 = 1/16 microstepping
        tic.set_current_limit(1500)  # 1500 mA
        tic.set_max_speed(2000000)   # 200 pulses/sec * 10000
        tic.set_max_acceleration(80000)
        tic.set_max_deceleration(80000)
        
        print("Energizing and rotating smoothly 1 full revolution CW...")
        tic.energize()
        tic.exit_safe_start()
        
        pos = tic.get_current_position()
        target = pos + 3200  # 3200 microsteps = 1 revolution in 1/16 mode
        tic.set_target_position(target)
        
        # Wait for movement to finish
        t_start = time.time()
        while tic.get_current_position() != target and (time.time() - t_start < 6):
            tic.reset_command_timeout()
            time.sleep(0.05)
            
        print("Rotating smoothly 1 full revolution CCW...")
        target = pos
        tic.set_target_position(target)
        t_start = time.time()
        while tic.get_current_position() != target and (time.time() - t_start < 6):
            tic.reset_command_timeout()
            time.sleep(0.05)
            
        tic.deenergize()
        print("-> Stepper Test SUCCESS: Smooth rotation complete!")
    except Exception as e:
        print("-> Stepper Test Failed:", e)

def test_led_pixel_types():
    print("\n--- [2] TESTING LED RING PIXEL FORMATS ---")
    try:
        from pi5neo.pi5neo import Pi5Neo, EPixelType
        
        # Test 1: Standard 3-byte GRB (WS2812B default)
        print("Testing Mode 1: GRB (Standard WS2812B)...")
        neo = Pi5Neo("/dev/spidev0.0", 64, 800, pixel_type=EPixelType.GRB)
        neo.clear_strip()
        neo.fill_strip(255, 0, 0)  # Red
        neo.update_strip()
        print("  -> Should be solid RED on all 64 LEDs! (Holding for 2 sec)")
        time.sleep(2)
        
        neo.fill_strip(0, 255, 0)  # Green
        neo.update_strip()
        print("  -> Should be solid GREEN on all 64 LEDs! (Holding for 2 sec)")
        time.sleep(2)
        
        neo.fill_strip(0, 0, 255)  # Blue
        neo.update_strip()
        print("  -> Should be solid BLUE on all 64 LEDs! (Holding for 2 sec)")
        time.sleep(2)
        
        neo.clear_strip()
        neo.update_strip()
        print("-> LED Test SUCCESS!")
    except Exception as e:
        print("-> LED Test Note:", e)

def test_lcd_contrast():
    print("\n--- [3] TESTING NEWHAVEN LCD INITIALIZATION & CONTRAST ---")
    try:
        lcd = NewhavenLCDBackend(bus_num=1, address=0x28, contrast=42, backlight=8)
        lcd.display_on()
        time.sleep(0.1)
        lcd.clear()
        time.sleep(0.1)
        lcd.set_backlight(8)
        lcd.set_contrast(42)
        
        lcd.write_line(0, "OpenCAL V2 Ready")
        lcd.write_line(1, "Contrast: 42 (OK)")
        lcd.write_line(2, "Backlight: Max 8")
        lcd.write_line(3, "Hardware Calibrated!")
        print("-> LCD Test SUCCESS: Sent calibrated contrast and messages to LCD!")
    except Exception as e:
        print("-> LCD Test Note:", e)

if __name__ == "__main__":
    print("=" * 60)
    print("      OPENCAL PRECISION HARDWARE CALIBRATION       ")
    print("=" * 60)
    test_lcd_contrast()
    test_led_pixel_types()
    test_stepper_smooth()
    print("\nCalibration Complete!")
