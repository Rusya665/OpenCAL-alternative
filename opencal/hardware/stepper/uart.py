import time
import threading
from typing import final, override

import serial
import math

from opencal.hardware.stepper.interface import StepperMotorInterface
from opencal.utils.config import UARTStepperConfig

# TMC2209 internal oscillator; verify against hardware (typically 12 MHz)
_TMC_CLK_HZ = 12_000_000
_REG_VACTUAL = 0x22
_REG_GCONF = 0x00
_REG_CHOPCONF = 0x6C
_SYNC_BYTE = 0x05


def _crc8(data: bytes) -> int:
    """CRC8 with polynomial 0x07, as required by the TMC2209 UART protocol."""
    crc = 0
    for byte in data:
        for _ in range(8):
            if (crc >> 7) ^ (byte & 0x01):
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
            byte >>= 1
    return crc


@final
class UARTStepperMotor(StepperMotorInterface):
    def __init__(self, config: UARTStepperConfig):
        self.default_rpm = config.default_rpm
        self.default_direction = config.default_direction
        self.steps_per_rev = config.steps_per_revolution
        self.encoder_cpr = config.encoder_cpr
        self.uart_address = config.uart_address
        self.microsteps = config.microsteps
        self.correction_factor: float = getattr(config, "correction_factor", 0.988375)

        self._speed_rpm: float = config.default_rpm
        self._current_direction: str = config.default_direction
        self._rotation_thread: threading.Thread | None = None
        self._finish_event = threading.Event()

        self._serial: serial.Serial | None = None

        try:
            self._serial = serial.Serial(
                config.uart_port,
                baudrate=config.baud_rate,
                timeout=0.5,
            )
            self.initialize()

            print("INFO: TMC2209 UART driver initialized.")
        except Exception as e:
            print(f"WARNING: UARTStepperMotor init failed: {e}")

    def initialize(self):
        self._write_register(_REG_GCONF, 0x000001C5)
        mres = 8 - int(math.log2(self.microsteps))
        chopconf = ((0x10 | mres) << 24) | 0x00020055
        self._write_register(_REG_CHOPCONF, chopconf)

    def _write_register(self, reg: int, value: int) -> None:
        """Send a TMC2209 UART write datagram (8 bytes: sync, addr, reg|0x80, 4 data, CRC)."""
        if self._serial is None:
            return
        datagram = bytes(
            [
                _SYNC_BYTE,
                self.uart_address,
                reg | 0x80,
                (value >> 24) & 0xFF,
                (value >> 16) & 0xFF,
                (value >> 8) & 0xFF,
                value & 0xFF,
            ]
        )
        self._serial.write(datagram + bytes([_crc8(datagram)]))
        # Single-wire UART echoes TX back on RX; read and discard the 8-byte echo.
        self._serial.read(8)

    def _read_register(self, reg: int) -> int | None:
        """Read a 32-bit register from the TMC2209 via UART."""
        if self._serial is None:
            return None
        try:
            # 4-byte read request datagram: sync (0x05), addr, reg, crc
            req = bytes([_SYNC_BYTE, self.uart_address, reg & 0x7F])
            req += bytes([_crc8(req)])
            self._serial.flushInput()
            self._serial.write(req)
            # Echo of 4-byte request + 8-byte response
            raw = self._serial.read(12)
            if len(raw) < 12:
                return None
            resp = raw[4:]
            if resp[0] != _SYNC_BYTE or resp[1] != 0xFF or resp[2] != (reg & 0x7F):
                return None
            val = (resp[3] << 24) | (resp[4] << 16) | (resp[5] << 8) | resp[6]
            return val
        except Exception:
            return None

    def _write_vactual(self, vactual: int) -> None:
        # Encode as 24-bit (handles sign via two's complement masking).
        self._write_register(_REG_VACTUAL, vactual & 0xFFFFFF)

    def _signed_vactual(self, rpm: float) -> int:
        """Return VACTUAL with sign encoding direction (positive=CW, negative=CCW)."""
        magnitude = self._rpm_to_vactual(abs(rpm), self.steps_per_rev)
        return magnitude if self._current_direction == "CW" else -magnitude

    @property
    @override
    def speed_rpm(self) -> float:
        return self._speed_rpm

    @override
    def set_correction_factor(self, factor: float) -> None:
        """Update live motor correction multiplier and immediately re-apply if running."""
        print(f"INFO: Updating motor CORRECTION_FACTOR from {self.correction_factor} to {factor}")
        self.correction_factor = factor
        if self.is_running():
            self._write_vactual(self._signed_vactual(self._speed_rpm))

    @override
    def set_rpm(self, rpm: float | None = None, ramp_time: float = 0) -> None:
        print(f"INFO: Changing rpm from {self._speed_rpm} to {rpm} in {ramp_time} sec.")
        rpm = rpm or self.default_rpm
        if rpm <= 0:
            raise ValueError("RPM must be positive. Use stop() to halt the stepper.")

        if ramp_time == 0:
            self._speed_rpm = rpm
            self._write_vactual(self._signed_vactual(rpm))
        else:
            thread = threading.Thread(target=self._ramp_rpm, args=(rpm, ramp_time), daemon=True)
            thread.start()

    def _ramp_rpm(self, target: float, ramp_time: float) -> None:
        TIMESTEPS = 100
        dt = ramp_time / TIMESTEPS
        start_rpm = max(self._speed_rpm, 1)

        for i in range(TIMESTEPS):
            if self._finish_event.is_set():
                return
            self._speed_rpm = start_rpm + (target - start_rpm) * ((i + 1) / TIMESTEPS)
            self._write_vactual(self._signed_vactual(self._speed_rpm))
            time.sleep(dt)

        self._speed_rpm = target
        self._write_vactual(self._signed_vactual(self._speed_rpm))

    @override
    def start_rotation(self, direction: str | None = None, ramp_time: float = 0) -> None:
        direction = direction or self.default_direction
        self._current_direction = direction
        print(f"INFO: Starting UART rotation {direction}")

        if self.is_running():
            print("WARNING: Stepper already running")
            return

        self._finish_event.clear()

        if ramp_time > 0:
            target_rpm, self._speed_rpm = self._speed_rpm, 0
            self._write_vactual(0)
            self._rotation_thread = threading.Thread(target=self._run_until_stopped, daemon=True)
            self._rotation_thread.start()
            self.set_rpm(target_rpm, ramp_time)
        else:
            self._write_vactual(self._signed_vactual(self._speed_rpm))
            self._rotation_thread = threading.Thread(target=self._run_until_stopped, daemon=True)
            self._rotation_thread.start()

    def _run_until_stopped(self) -> None:
        _ = self._finish_event.wait()

    @override
    def is_running(self) -> bool:
        return self._rotation_thread is not None and self._rotation_thread.is_alive()

    @override
    def stop(self) -> None:
        """Stop the motor. Blocks until motor stops and rotation thread exits."""
        print("INFO: Stopping the motor.")
        self._write_vactual(0)
        self._finish_event.set()

        if self._rotation_thread is not None:
            self._rotation_thread.join()

    @override
    def rotate_steps(self, steps: int, direction: str | None = None) -> None:
        raise NotImplementedError("rotate_steps is not yet implemented for UART mode")

    @override
    def angle_in_steps(self) -> int:
        return 0

    @override
    def angle_in_degrees(self) -> float:
        return 0.0

    def _rpm_to_vactual(self, rpm: float, steps_per_rev: int) -> int:
        """Convert RPM to unsigned VACTUAL magnitude for the TMC2209."""
        steps_per_rev_eff: float = steps_per_rev * (self.microsteps / 8)
        fstep = rpm * steps_per_rev_eff / 60.0
        frac_vactual = self.correction_factor * fstep * (2**24) / _TMC_CLK_HZ
        return round(frac_vactual)

    @override
    def get_telemetry(self) -> dict:
        """Query TMC2209 driver registers for real-time motor health and load telemetry."""
        drv_status = self._read_register(0x6F)  # DRV_STATUS
        sg_result = self._read_register(0x41)   # SG_RESULT (StallGuard load)
        ioin = self._read_register(0x06)        # IOIN
        tstep = self._read_register(0x12)       # TSTEP

        errors = []
        driver_temp_flag = "OK (<120C)"
        standstill = True
        current_scale = 0

        if drv_status is not None:
            standstill = bool(drv_status & (1 << 31))
            current_scale = (drv_status >> 16) & 0x1F
            if drv_status & (1 << 8): errors.append("OVERTEMPERATURE_SHUTDOWN")
            if drv_status & (1 << 9): errors.append("OVERTEMPERATURE_PREWARNING")
            if drv_status & (1 << 0): errors.append("SHORT_TO_GROUND_A")
            if drv_status & (1 << 1): errors.append("SHORT_TO_GROUND_B")
            if drv_status & (1 << 2): errors.append("OPEN_LOAD_A")
            if drv_status & (1 << 3): errors.append("OPEN_LOAD_B")

            if drv_status & (1 << 7): driver_temp_flag = "Critical (>=157C)"
            elif drv_status & (1 << 6): driver_temp_flag = "Warning (>=150C)"
            elif drv_status & (1 << 5): driver_temp_flag = "Elevated (>=143C)"
            elif drv_status & (1 << 4): driver_temp_flag = "Warm (>=120C)"

        steps_per_rev_eff = self.steps_per_rev * (self.microsteps / 8)
        fstep = (self._speed_rpm * steps_per_rev_eff / 60.0) if self.is_running() else 0.0

        return {
            "driver": "TMC2209_UART",
            "is_running": self.is_running(),
            "target_rpm": self._speed_rpm,
            "direction": self._current_direction,
            "microsteps": self.microsteps,
            "correction_factor": self.correction_factor,
            "step_frequency_hz": round(fstep, 2),
            "stallguard_load": sg_result if sg_result is not None else 0,
            "driver_temp_status": driver_temp_flag,
            "current_scale": current_scale,
            "standstill": standstill,
            "tstep": tstep if tstep is not None else 0,
            "errors": errors,
            "status": "Running" if self.is_running() else "Standstill",
        }
