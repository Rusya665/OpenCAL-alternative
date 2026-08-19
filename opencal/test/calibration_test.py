#!/usr/bin/env python3
"""
Unit and Integration Test for OpenCAL Automated Motor Calibration and Telemetry Engine.
Tests both Dot markers and Wobble-Tolerant Axial Line markers with runout analysis.
"""

import os
import math
import time
import cv2
import numpy as np
from pathlib import Path

from opencal.utils.config import Config, load_config
from opencal.hardware.stepper.mock import MockStepperMotor
from opencal.hardware.hardware_controller import HardwareController
from opencal.utils.telemetry import get_pi_system_telemetry, TelemetrySessionLogger
from opencal.utils.calibration.motor_calibrator import MotorCalibrator


def test_telemetry_gathering():
    print("[1/5] Testing Raspberry Pi & System Telemetry Gathering...")
    telem = get_pi_system_telemetry()
    assert "cpu_temp_c" in telem
    assert "core_voltage_v" in telem
    assert "arm_clock_mhz" in telem
    assert "ram_usage_pct" in telem
    print(f"  [OK] System Telemetry: CPU Temp={telem['cpu_temp_c']}C, Voltage={telem['core_voltage_v']}V, Clock={telem['arm_clock_mhz']}MHz")


def test_telemetry_csv_logger():
    print("[2/5] Testing Telemetry Session CSV Logger...")
    test_dir = Path.home() / "OpenCAL-alternative" / "test_logs"
    test_dir.mkdir(parents=True, exist_ok=True)
    logger = TelemetrySessionLogger(output_dir=test_dir)
    log_file = logger.start_session("unit_test")
    
    for i in range(10):
        logger.record_sample({
            "sample_idx": i,
            "target_rpm": 9.0,
            "meas_rpm": 9.083,
            "vin_voltage": 12.18,
            "cpu_temp": 45.2,
            "detected_shape": "line",
            "wobble_runout_px": 2.4,
        })
    
    saved_path = logger.stop_session()
    assert saved_path is not None
    assert saved_path.exists()
    assert saved_path.stat().st_size > 50
    print(f"  [OK] CSV Logger verified: {saved_path} ({saved_path.stat().st_size} bytes)")
    saved_path.unlink(missing_ok=True)


def test_mock_stepper_telemetry():
    print("[3/5] Testing Stepper Motor Telemetry & Live Correction...")
    cfg = load_config()
    mock_motor = MockStepperMotor(cfg.stepper)
    mock_motor.start_rotation("CW")
    telem = mock_motor.get_telemetry()
    assert telem["is_running"] is True
    assert telem["vin_voltage_v"] > 10.0
    mock_motor.set_correction_factor(0.991234)
    telem2 = mock_motor.get_telemetry()
    assert telem2["correction_factor"] == 0.991234
    mock_motor.stop()
    print(f"  [OK] Stepper Telemetry & Correction Factor update verified!")


class DummyHW:
    def __init__(self, stepper):
        self.stepper = stepper
        self.led_manager = None


def test_vision_dot_calibration():
    print("[4/5] Testing Vision Dot Marker Tracking & Zero-Crossing...")
    cfg = load_config()
    mock_motor = MockStepperMotor(cfg.stepper)
    hw = DummyHW(mock_motor)
    calibrator = MotorCalibrator(hw)

    SIM_RPM = 9.0
    TARGET_REVS = 2
    calibrator.set_gate_roi(0.20, 0.10, 0.60, 0.80)
    calibrator.start_calibration(target_rpm=SIM_RPM, target_revs=TARGET_REVS, color_mode="bright_dot", shape_mode="dot")

    FPS = 30
    DT = 1.0 / FPS
    total_frames = int((TARGET_REVS * (60.0 / SIM_RPM) + 2.0) * FPS)
    sim_angle = 0.0

    for frame_i in range(total_frames):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(frame, (160, 80), (480, 400), (35, 45, 55), -1)
        cv2.rectangle(frame, (280, 80), (360, 400), (65, 65, 65), -1)

        sim_speed = SIM_RPM * 360.0 / 60.0
        sim_angle = (sim_angle + sim_speed * DT) % 360.0

        if sim_angle < 180.0:
            rad = math.radians(sim_angle)
            dot_y = int(240 - 120 * math.cos(rad))
            cv2.circle(frame, (320, dot_y), 11, (255, 255, 255), -1)

        sim_ts_ns = int((frame_i * DT) * 1e9)
        annotated, sample = calibrator.process_frame(frame, frame_timestamp_ns=sim_ts_ns)
        if calibrator.calibration_complete:
            break

    print(f"  Dot Mode: Revs={calibrator.revolutions_completed}/{TARGET_REVS}, Avg RPM={calibrator.measured_avg_rpm:.4f}")
    assert calibrator.revolutions_completed >= TARGET_REVS - 1
    assert abs(calibrator.measured_avg_rpm - SIM_RPM) < 0.1
    print("  [OK] Dot Marker Calibration PASSED!")


def test_vision_line_calibration_with_wobble():
    print("[5/5] Testing Axial Line / Stripe Marker Tracking & Wobble Runout Detection...")
    cfg = load_config()
    mock_motor = MockStepperMotor(cfg.stepper)
    hw = DummyHW(mock_motor)
    calibrator = MotorCalibrator(hw)

    SIM_RPM = 9.0
    TARGET_REVS = 2
    calibrator.set_gate_roi(0.20, 0.10, 0.60, 0.80)
    calibrator.start_calibration(target_rpm=SIM_RPM, target_revs=TARGET_REVS, color_mode="bright_dot", shape_mode="line")

    FPS = 30
    DT = 1.0 / FPS
    total_frames = int((TARGET_REVS * (60.0 / SIM_RPM) + 2.0) * FPS)
    sim_angle = 0.0
    detected_line_count = 0

    for frame_i in range(total_frames):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Vial
        cv2.rectangle(frame, (160, 80), (480, 400), (35, 45, 55), -1)
        # Center opaque tape
        cv2.rectangle(frame, (250, 80), (390, 400), (65, 65, 65), -1)

        sim_speed = SIM_RPM * 360.0 / 60.0
        sim_angle = (sim_angle + sim_speed * DT) % 360.0

        # Simulate horizontal line stripe rotating with slight tilt and axial wobble
        if sim_angle < 180.0:
            rad = math.radians(sim_angle)
            line_y = int(240 - 120 * math.cos(rad))
            # Wobble: horizontal precession +/- 8px
            wobble_x = int(8.0 * math.sin(rad * 2))
            cx = 320 + wobble_x
            # Draw horizontal stripe (width=60px, height=8px) with slight 3° tilt
            p1 = (cx - 30, line_y - 2)
            p2 = (cx + 30, line_y + 2)
            cv2.line(frame, p1, p2, (255, 255, 255), 6)

        sim_ts_ns = int((frame_i * DT) * 1e9)
        annotated, sample = calibrator.process_frame(frame, frame_timestamp_ns=sim_ts_ns)
        
        if sample.get("detected_shape") == "line":
            detected_line_count += 1

        if calibrator.calibration_complete:
            break

    print(f"  Line Mode: Revs={calibrator.revolutions_completed}/{TARGET_REVS}, Avg RPM={calibrator.measured_avg_rpm:.4f}")
    print(f"  Detected Shape: '{calibrator.detected_shape_type}', Line Frames: {detected_line_count}")
    print(f"  Vial Wobble Runout: {calibrator.wobble_runout_px:.1f} px, Tilt: {calibrator.line_tilt_deg:+.1f} deg")

    assert detected_line_count > 10
    assert calibrator.revolutions_completed >= TARGET_REVS - 1
    assert abs(calibrator.measured_avg_rpm - SIM_RPM) < 0.1
    assert calibrator.wobble_runout_px > 0.0
    print("  [OK] Axial Line Marker & Wobble Runout Tracking PASSED!")


if __name__ == "__main__":
    test_telemetry_gathering()
    test_telemetry_csv_logger()
    test_mock_stepper_telemetry()
    test_vision_dot_calibration()
    test_vision_line_calibration_with_wobble()
    print("\n>>> ALL 5 TEST SUITES PASSED SUCCESSFULLY! <<<")
