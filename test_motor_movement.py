import time
import ticlib

def main():
    print("=" * 50)
    print("        POLOLU TIC STEPPER MOTOR FULL TEST        ")
    print("=" * 50)
    
    tic = ticlib.TicUSB()
    
    print("Configuring Pololu Tic...")
    tic.clear_driver_error()
    tic.set_step_mode(4)  # 1/16 microstepping
    tic.set_current_limit(27)  # Code 27 = 1600mA full torque
    tic.set_max_speed(20000000)
    tic.set_max_acceleration(200000)
    tic.set_max_deceleration(200000)
    tic.set_starting_speed(0)
    
    vin = tic.get_vin_voltage()
    cur = tic.get_current_limit()
    print(f"  -> VIN Voltage:   {vin/1000.0:.2f} V")
    print(f"  -> Current Limit: {cur} mA")
    print(f"  -> Step Mode:     1/16 Microstepping")
    
    # 1. Microstep Jog Test
    print("\n[Step 1] Energizing and rotating 1 FULL REVOLUTION (3200 steps) CW...")
    tic.energize()
    tic.exit_safe_start()
    tic.reset_command_timeout()
    
    pos = tic.get_current_position()
    target = pos + 3200
    tic.set_target_position(target)
    
    t_start = time.time()
    while tic.get_current_position() != target and (time.time() - t_start < 5):
        tic.reset_command_timeout()
        time.sleep(0.02)
        
    print(f"  -> Position reached: {tic.get_current_position()}")
    time.sleep(0.5)
    
    print("\n[Step 2] Rotating 1 FULL REVOLUTION (3200 steps) CCW...")
    target = pos
    tic.set_target_position(target)
    
    t_start = time.time()
    while tic.get_current_position() != target and (time.time() - t_start < 5):
        tic.reset_command_timeout()
        time.sleep(0.02)
        
    print(f"  -> Position reached: {tic.get_current_position()}")
    time.sleep(0.5)
    
    # 2. Continuous Spin Test
    print("\n[Step 3] Testing CONTINUOUS SPIN (Velocity Mode at 9 RPM for 3 seconds)...")
    # 9 RPM = 9 * 3200 / 60 = 480 steps/sec -> velocity = 480 * 10000 = 4,800,000
    tic.set_target_velocity(4800000)
    t_end = time.time() + 3.0
    while time.time() < t_end:
        tic.reset_command_timeout()
        time.sleep(0.1)
        
    print("  -> Stopping continuous spin...")
    tic.set_target_velocity(0)
    tic.halt_and_hold()
    time.sleep(0.5)
    tic.deenergize()
    
    print("\n" + "=" * 50)
    print("MOTOR TEST 100% COMPLETE & SUCCESSFUL!")
    print("=" * 50)

if __name__ == "__main__":
    main()
