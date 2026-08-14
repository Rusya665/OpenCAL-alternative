import time
import sys
from opencal.utils.config import Config
from opencal.hardware.lcd_display import LCDDisplay

def main():
    print("=" * 50)
    print("      OPENCAL COMPREHENSIVE HARDWARE TEST       ")
    print("=" * 50)
    
    cfg = Config()
    
    # 1. LCD Test
    print("\n[1/3] Testing Newhaven 20x4 LCD...")
    try:
        lcd = LCDDisplay(cfg.lcd_display)
        lcd.clear()
        time.sleep(0.3)
        lcd.write_message("OpenCAL Hardware Test", 0)
        lcd.write_message("LCD Screen: OK!", 1)
        lcd.write_message("Testing Motor...", 2)
        lcd.write_message("Step 1/3 Complete", 3)
        print("  -> LCD Test: SUCCESS (Sent messages to rows 0-3)")
    except Exception as e:
        print(f"  -> LCD Test FAILED: {e}")

    # 2. Pololu Tic Stepper Motor Test
    print("\n[2/3] Testing Pololu Tic Stepper Motor...")
    try:
        import ticlib
        tic = ticlib.TicUSB()
        pos = tic.get_current_position()
        print(f"  -> Pololu Tic USB Connected! Current Position: {pos}")
        print("  -> Energizing motor and testing micro-step rotation...")
        tic.energize()
        tic.exit_safe_start()
        # Rotate 200 steps
        tic.set_target_position(pos + 200)
        time.sleep(1.0)
        tic.set_target_position(pos)
        time.sleep(1.0)
        tic.deenergize()
        print("  -> Stepper Motor Test: SUCCESS!")
        if 'lcd' in locals():
            lcd.write_message("Motor Test: SUCCESS", 2)
    except Exception as e:
        print(f"  -> Stepper Motor Test Note: {e}")
        if 'lcd' in locals():
            lcd.write_message("Motor: Check USB/Perm", 2)

    # 3. Pi5Neo LED Array Test
    print("\n[3/3] Testing Pi5Neo LED Ring...")
    try:
        from opencal.hardware.led_manager import LEDManager
        leds = LEDManager(cfg.led_array)
        print("  -> Setting LEDs to Green...")
        leds.set_color([0, 200, 0, 0])
        time.sleep(1.0)
        print("  -> Setting LEDs to Blue...")
        leds.set_color([0, 0, 200, 0])
        time.sleep(1.0)
        leds.clear()
        print("  -> LED Ring Test: SUCCESS!")
        if 'lcd' in locals():
            lcd.write_message("All Tests Finished!", 3)
    except Exception as e:
        print(f"  -> LED Ring Test Note: {e}")

    print("\n" + "=" * 50)
    print("Diagnostic Complete!")
    print("=" * 50)

if __name__ == "__main__":
    main()
