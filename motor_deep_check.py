import time
import ticlib

def test():
    print("=" * 60)
    print("      POLOLU TIC DEEP MOTOR DIAGNOSTICS & ENERGIZE      ")
    print("=" * 60)
    
    tic = ticlib.TicUSB()
    
    # 1. Read All Diagnostics
    print("[1] Reading Tic Status Registers...")
    print("  Operation State:", tic.get_operation_state())
    print("  VIN Voltage:", tic.get_vin_voltage(), "mV")
    print("  Current Limit:", tic.get_current_limit(), "mA")
    print("  Step Mode:", tic.get_step_mode())
    print("  Last Driver Error:", tic.get_last_motor_driver_error())
    print("  Last HP Driver Error:", tic.get_last_hp_driver_errors())
    print("  Errors Occurred:", tic.get_error_occured())
    print("  Current Velocity:", tic.get_current_velocity())
    print("  Planning Mode:", tic.get_planning_mode())
    
    # 2. Test Holding Torque
    print("\n[2] ENERGIZING MOTOR COILS (Holding Torque Test)...")
    tic.clear_driver_error()
    # Code 32 is maximum current for Tic T249 (~1900 mA)
    tic.set_current_limit(32)
    tic.set_step_mode(0) # 0 = Full step mode for maximum holding torque
    tic.energize()
    tic.exit_safe_start()
    
    print("  -> COILS ARE NOW ENERGIZED FOR 5 SECONDS.")
    print("  -> TRY TO TURN THE MOTOR SHAFT BY HAND RIGHT NOW.")
    print("  -> Does it feel locked / stiff / vibrating, or totally free?")
    
    t_end = time.time() + 5.0
    while time.time() < t_end:
        tic.reset_command_timeout()
        time.sleep(0.1)
        
    print("\n[3] Testing Low-Speed Continuous Rotation...")
    # Velocity 200,000 (20 steps/sec in full-step mode = 6 RPM)
    tic.set_max_speed(2000000)
    tic.set_target_velocity(200000)
    
    t_end = time.time() + 4.0
    while time.time() < t_end:
        tic.reset_command_timeout()
        time.sleep(0.1)
        
    print("  -> Stopping motor...")
    tic.set_target_velocity(0)
    tic.deenergize()
    print("\nDiagnostic finished.")

if __name__ == "__main__":
    test()
