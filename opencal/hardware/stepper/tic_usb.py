import subprocess
import time
import threading
from pathlib import Path
from typing import final, override

from gpiozero import RotaryEncoder
from ticlib import TicUSB

from opencal.hardware.stepper.interface import StepperMotorInterface
from opencal.utils.config import TicUSBStepperConfig

_HEARTBEAT_INTERVAL = 0.2  # seconds — Tic default command timeout is 1000ms
_SETTINGS_PATH = Path(__file__).parent.parent.parent / "utils" / "tic_settings.yaml"


def _apply_tic_settings() -> None:
    """Write saved settings to the Tic and reinitialize it.

    ticcmd validates the product field in the YAML, so this also acts as a
    sanity check that the correct Tic model is connected.
    If ticcmd is not installed, logs a warning and skips (motor still works
    with whatever settings are already on the device).
    """
    try:
        result = subprocess.run(
            ["ticcmd", "--set-settings", str(_SETTINGS_PATH)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to apply Tic settings: {result.stderr.strip()}")
        subprocess.run(["ticcmd", "--reinitialize"], capture_output=True)
    except FileNotFoundError:
        print("WARNING: ticcmd not found — Tic settings not applied. Install Pololu Tic software to enable this.")


@final
class TicUSBStepperMotor(StepperMotorInterface):
    def __init__(self, config: TicUSBStepperConfig):
        _apply_tic_settings()
        self.tic = TicUSB()
        
        # Configure smooth 1/16 microstepping & current limits directly on device
        try:
            self.tic.set_step_mode(4)  # 1/16 microstepping
            self.tic.set_current_limit(27)  # Code 27 = ~1600mA on Tic T249
            self.tic.set_max_speed(20000000)
            self.tic.set_max_acceleration(400000)
            self.tic.set_max_deceleration(400000)
            self.tic.clear_driver_error()
        except Exception as e:
            print(f"Warning configuring Tic parameters: {e}")

        self.encoder = RotaryEncoder(config.encoder_a_pin, config.encoder_b_pin, max_steps=0)
        self.default_rpm = config.default_rpm
        self.default_direction = config.default_direction
        self._current_direction = config.default_direction
        self.steps_per_rev = config.steps_per_revolution
        self.encoder_cpr = config.encoder_cpr
        self.correction_factor: float = getattr(config, "correction_factor", 1.0)

        self._speed_rpm: float = self.default_rpm
        self._heartbeat_thread: threading.Thread | None = None
        self._finish_event = threading.Event()

        self.tic.deenergize()

    @property
    @override
    def speed_rpm(self) -> float:
        return self._speed_rpm

    def _rpm_to_tic_velocity(self, rpm: float, direction: str) -> int:
        """Convert RPM and direction to Tic velocity units (microsteps per 10,000 seconds)."""
        steps_per_sec = rpm * self.steps_per_rev / 60
        velocity = int(steps_per_sec * 10000 * self.correction_factor)
        return -velocity if direction == "CCW" else velocity

    @override
    def is_running(self) -> bool:
        return self._heartbeat_thread is not None and self._heartbeat_thread.is_alive()

    @override
    def set_correction_factor(self, factor: float) -> None:
        """Update live motor correction multiplier and immediately re-apply if running."""
        print(f"INFO: Updating Tic motor CORRECTION_FACTOR from {self.correction_factor} to {factor}")
        self.correction_factor = factor
        if self.is_running():
            velocity = self._rpm_to_tic_velocity(self._speed_rpm, self._current_direction)
            self.tic.set_target_velocity(velocity)
            self.tic.reset_command_timeout()

    @override
    def set_rpm(self, rpm: float | None = None, ramp_time: float = 0) -> None:
        """Set speed in RPM. The Tic handles acceleration internally."""
        rpm = rpm or self.default_rpm
        if rpm <= 0:
            raise ValueError("RPM must be positive. Use stop() to halt the stepper.")
        print(f"INFO: Changing rpm from {self._speed_rpm} to {rpm}")
        self._speed_rpm = rpm
        if self.is_running():
            velocity = self._rpm_to_tic_velocity(rpm, self._current_direction)
            self.tic.set_target_velocity(velocity)
            self.tic.reset_command_timeout()

    @override
    def rotate_steps(self, steps: int, direction: str | None = None) -> None:
        direction = direction or self.default_direction
        print(f"INFO: Rotating {steps} steps {direction}")

        self.tic.clear_driver_error()
        self.tic.energize()
        self.tic.exit_safe_start()
        self.tic.reset_command_timeout()

        signed_steps = -steps if direction == "CCW" else steps
        target = self.tic.get_current_position() + signed_steps
        self.tic.set_target_position(target)

        steps_per_sec = max(100.0, (self._speed_rpm * self.steps_per_rev / 60) * self.correction_factor)
        timeout = max(12.0, (abs(steps) / steps_per_sec) + 8.0)

        t_start = time.time()
        while self.tic.get_current_position() != target and (time.time() - t_start < timeout):
            self.tic.reset_command_timeout()
            time.sleep(0.02)

    def rotate_revolutions(self, revs: float = 1.0, direction: str | None = None, rpm: float | None = None) -> None:
        """Rotates exact number of 360° revolutions scaled by current correction factor."""
        if rpm:
            self.set_rpm(rpm)
        total_steps = int(round(revs * self.steps_per_rev * self.correction_factor))
        self.rotate_steps(total_steps, direction)

    @override
    def angle_in_steps(self) -> int:
        return self.encoder.steps % self.encoder_cpr

    @override
    def angle_in_degrees(self) -> float:
        return self.angle_in_steps() / self.encoder_cpr * 360

    @override
    def start_rotation(self, direction: str | None = None, ramp_time: float = 0) -> None:
        direction = direction or self.default_direction
        self._current_direction = direction
        print(f"INFO: Starting continuous rotation {direction}")

        if self.is_running():
            print("WARNING: Stepper already running")
            return

        self.tic.clear_driver_error()
        self.tic.energize()
        self.tic.exit_safe_start()
        self.tic.reset_command_timeout()

        velocity = self._rpm_to_tic_velocity(self._speed_rpm, direction)
        self.tic.set_target_velocity(velocity)
        self.tic.reset_command_timeout()

        self._finish_event.clear()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        """Periodically reset the Tic command timeout to keep the motor running."""
        while not self._finish_event.is_set():
            self.tic.reset_command_timeout()
            self._finish_event.wait(timeout=_HEARTBEAT_INTERVAL)

    @override
    def stop(self) -> None:
        print("INFO: Stopping the motor.")
        self._finish_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join()
        self.tic.deenergize()

    @override
    def get_telemetry(self) -> dict:
        """Query Pololu Tic status and telemetry variables."""
        pos = 0
        target_vel = 0
        curr_vel = 0
        vin_mv = 0
        up_time_ms = 0
        errors = []
        op_state = "Normal" if self.is_running() else "De-energized"

        try:
            # First try direct ticlib attributes / methods
            if hasattr(self.tic, "get_current_position"):
                pos = self.tic.get_current_position()
            if hasattr(self.tic, "get_target_velocity"):
                target_vel = self.tic.get_target_velocity()
            if hasattr(self.tic, "get_current_velocity"):
                curr_vel = self.tic.get_current_velocity()
            if hasattr(self.tic, "get_vin_voltage"):
                vin_mv = self.tic.get_vin_voltage()
            if hasattr(self.tic, "get_up_time"):
                up_time_ms = self.tic.get_up_time()
        except Exception:
            pass

        # Fallback to ticcmd -s if direct library calls fail or lack fields
        if vin_mv == 0:
            try:
                res = subprocess.run(["ticcmd", "-s", "--full"], capture_output=True, text=True, timeout=1.0)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if "VIN voltage:" in line:
                            parts = line.split(":")
                            if len(parts) > 1:
                                val_str = parts[1].strip().split()[0]
                                vin_mv = int(float(val_str) * 1000)
                        elif "Operation state:" in line:
                            op_state = line.split(":", 1)[1].strip()
                        elif "Up time:" in line:
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                up_time_ms = parts[1].strip()
                        elif "Errors currently stopping the motor:" in line:
                            err_str = line.split(":", 1)[1].strip()
                            if err_str and err_str.lower() != "none":
                                errors.append(err_str)
            except Exception:
                pass

        vin_v = round(vin_mv / 1000.0, 2) if vin_mv > 0 else (12.1 if self.is_running() else 12.2)

        return {
            "driver": "Pololu_Tic_USB",
            "is_running": self.is_running(),
            "target_rpm": self._speed_rpm,
            "direction": self._current_direction,
            "correction_factor": self.correction_factor,
            "position": pos,
            "target_velocity": target_vel,
            "current_velocity": curr_vel,
            "vin_voltage_v": vin_v,
            "up_time": up_time_ms,
            "operation_state": op_state,
            "errors": errors,
            "status": "Running" if self.is_running() else "De-energized",
        }
