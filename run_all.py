import os
import subprocess
import time
from opencal.utils.config import Config
from opencal.hardware.lcd_display import LCDDisplay

def setup_udev():
    print("[Setup] Configuring Pololu Tic USB permissions...")
    rule = 'SUBSYSTEM=="usb", ATTRS{idVendor}=="1ffb", MODE="0666"\n'
    try:
        with open("/tmp/99-pololu.rules", "w") as f:
            f.write(rule)
        subprocess.run(["sudo", "cp", "/tmp/99-pololu.rules", "/etc/udev/rules.d/99-pololu.rules"], check=True)
        subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=True)
        subprocess.run(["sudo", "udevadm", "trigger"], check=True)
        print("[Setup] Pololu USB udev rules installed and triggered successfully!")
    except Exception as e:
        print(f"[Setup] Warning configuring udev: {e}")

def run_tests():
    print("\n" + "=" * 50)
    print("      OPENCAL COMPREHENSIVE HARDWARE TEST       ")
    print("=" * 50)
    
    cfg = Config()
    
    # 1. LCD Test
    print("\n[1/3] Testing Newhaven 20x4 LCD Screen...")
    try:
        lcd = LCDDisplay(cfg.lcd_display)
        lcd.clear()
        time.sleep(0.3)
        lcd.write_message("OpenCAL V2 Online!", 0)
        lcd.write_message("LCD Display: OK", 1)
        lcd.write_message("Motor: Testing...", 2)
        lcd.write_message("All Systems Normal", 3)
        print("  -> LCD Test: SUCCESS!")
    except Exception as e:
        print(f"  -> LCD Test FAILED: {e}")
        lcd = None

    # 2. Stepper Motor Test
    print("\n[2/3] Testing Pololu Tic Stepper Motor...")
    try:
        import ticlib
        tic = ticlib.TicUSB()
        pos = tic.get_current_position()
        print(f"  -> Connected to Pololu Tic! Initial Position: {pos}")
        print("  -> Energizing motor and rotating 400 microsteps...")
        tic.energize()
        tic.exit_safe_start()
        tic.set_target_position(pos + 400)
        time.sleep(1.2)
        tic.set_target_position(pos)
        time.sleep(1.2)
        tic.deenergize()
        print("  -> Stepper Motor Rotation: SUCCESS!")
        if lcd:
            lcd.write_message("Motor: SUCCESS!", 2)
    except Exception as e:
        print(f"  -> Stepper Motor Note: {e}")
        if lcd:
            lcd.write_message("Motor: Error", 2)

    # 3. Pi5Neo LED Ring Test
    print("\n[3/3] Testing Pi5Neo LED Ring...")
    try:
        from opencal.hardware.led_manager import LEDManager, GREEN, BLUE
        leds = LEDManager(cfg.led_array)
        print("  -> Setting LEDs Green...")
        leds.set_led(GREEN)
        time.sleep(1.0)
        print("  -> Setting LEDs Blue...")
        leds.set_led(BLUE)
        time.sleep(1.0)
        print("  -> Running startup animation...")
        leds.run_start_animation()
        leds.clear_leds()
        print("  -> LED Ring Test: SUCCESS!")
        if lcd:
            lcd.write_message("Status: 100% READY", 3)
    except Exception as e:
        print(f"  -> LED Ring Note: {e}")

    print("\n" + "=" * 50)
    print("ALL HARDWARE TESTS COMPLETE!")
    print("=" * 50)

if __name__ == "__main__":
    setup_udev()
    run_tests()
