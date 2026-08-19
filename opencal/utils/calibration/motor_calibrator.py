"""OpenCAL High-Precision Motor Auto-Calibration and Optical Studio.

Features:
- Interactive Draggable & Resizable Optical Gate ROI: process ONLY the defined inspection window over the tape/marker.
- Vertical Center of Mass tracking: 100% immune to marker width/height extending beyond the gate.
- Sub-Frame interpolation on zero-crossings for micro-second accurate RPM and jitter calculation.
- Rejection of ambient background glare, chamber boundaries, and false contours.
- Stepped rotation drift tester and Auto-Find Homing assistant.
"""

from __future__ import annotations

import csv
import json
import math
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from opencal.utils.telemetry import get_pi_system_telemetry
from opencal.utils.config import CFG_PATH


class TelemetrySessionLogger:
    """Logs high-frequency calibration samples to a dedicated timestamped CSV file."""
    def __init__(self, output_dir: str | Path | None = None):
        if output_dir is None:
            self.output_dir = Path.home() / "OpenCAL-alternative" / "telemetry_logs"
        else:
            self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._current_file: Path | None = None
        self._csv_writer: Any | None = None
        self._csv_handle: Any | None = None
        self._write_count: int = 0
        self._lock = threading.RLock()

    def start_session(self, prefix: str = "motor_auto_cal") -> Path:
        with self._lock:
            self.stop_session()
            self._write_count = 0
            t_str = time.strftime("%Y%m%d_%H%M%S")
            self._current_file = self.output_dir / f"{prefix}_{t_str}.csv"
            self._csv_handle = open(self._current_file, mode="w", newline="", encoding="utf-8")
            fieldnames = [
                "timestamp_unix", "frame_timestamp_ns", "is_calibrating", "target_rpm",
                "revolutions", "target_revolutions", "measured_avg_rpm", "rpm_jitter_std",
                "suggested_correction_factor", "current_correction_factor",
                "marker_detected", "detected_shape", "line_tilt_deg", "line_length_px",
                "wobble_runout_px", "marker_norm_y", "confidence",
                "cpu_temp_c", "core_voltage_v", "arm_clock_mhz", "cpu_usage_pct",
                "motor_vin_v", "motor_load", "motor_driver", "status_message"
            ]
            self._csv_writer = csv.DictWriter(self._csv_handle, fieldnames=fieldnames)
            self._csv_writer.writeheader()
            self._csv_handle.flush()
            return self._current_file

    def record_sample(self, sample: dict[str, Any]):
        with self._lock:
            if self._csv_writer and self._csv_handle:
                clean_sample = {k: v for k, v in sample.items() if k in self._csv_writer.fieldnames}
                self._csv_writer.writerow(clean_sample)
                self._write_count += 1
                if self._write_count % 30 == 0:
                    try:
                        self._csv_handle.flush()
                    except Exception:
                        pass


    def stop_session(self) -> Path | None:
        with self._lock:
            if self._csv_handle:
                try:
                    self._csv_handle.close()
                except Exception:
                    pass
                self._csv_handle = None
                self._csv_writer = None
            f = self._current_file
            self._current_file = None
            return f


class MotorCalibrator:
    def __init__(self, hardware_controller=None):
        self.hw = hardware_controller
        self.logger = TelemetrySessionLogger()
        self._lock = threading.RLock()

        # Calibration Configuration
        self.target_rpm: float = 9.0
        self.target_revolutions: int = 30
        self.color_filter: str = "dark_line"  # "dark_line", "red", "green", "cyan", "bright_dot"
        
        # Draggable & Resizable Optical Gate ROI (normalized 0.0 to 1.0)
        self.gate_x: float = 0.38
        self.gate_y: float = 0.22
        self.gate_w: float = 0.24
        self.gate_h: float = 0.56

        # Marker Shape & Wobble Tracking
        self.marker_shape_mode: str = "line"  # "line", "dot", "auto"
        self.detected_shape_type: str = "none"  # "line", "dot", "none"
        self.line_tilt_deg: float = 0.0
        self.line_length_px: float = 0.0
        self.horizontal_drift_px: float = 0.0
        self.cx_history: deque = deque(maxlen=60)
        self.wobble_runout_px: float = 0.0

        # State Machine
        self.is_active: bool = False
        self.status_message: str = "Idle (Ready to Calibrate)"
        self.start_time: float = 0.0
        self.revolutions_completed: int = 0
        
        # Tracking & Crossing History
        self.crossing_timestamps: list[float] = []
        self.instant_rpms: list[float] = []
        self.trajectory_history: deque = deque(maxlen=60)  # for waveform HUD
        self.recent_positions: deque = deque(maxlen=5)     # (timestamp, y_norm)
        self.last_crossing_time: float = 0.0
        self.last_marker_seen: float = 0.0
        self.in_transit: bool = False

        # Results
        self.measured_avg_rpm: float = 0.0
        self.rpm_jitter_std: float = 0.0
        self.suggested_correction_factor: float = 1.0
        self.calibration_complete: bool = False
        self.last_log_path: Path | None = None
        self.latest_sample: dict[str, Any] = {}

    @property
    def current_correction_factor(self) -> float:
        if self.hw and hasattr(self.hw, "stepper") and self.hw.stepper:
            return getattr(self.hw.stepper, "correction_factor", 1.0)
        return 1.0

    def set_gate_roi(self, x: float, y: float, w: float, h: float) -> dict[str, float]:

        with self._lock:
            self.gate_x = max(0.0, min(0.95, float(x)))
            self.gate_y = max(0.0, min(0.95, float(y)))
            self.gate_w = max(0.05, min(1.0 - self.gate_x, float(w)))
            self.gate_h = max(0.05, min(1.0 - self.gate_y, float(h)))
            return self.get_gate_roi()

    def get_gate_roi(self) -> dict[str, float]:
        return {
            "x": round(self.gate_x, 4),
            "y": round(self.gate_y, 4),
            "w": round(self.gate_w, 4),
            "h": round(self.gate_h, 4)
        }

    def start_calibration(self, target_rpm: float = 9.0, target_revs: int = 30, color_mode: str = "dark_line", shape_mode: str = "line"):
        with self._lock:
            self.target_rpm = float(target_rpm)
            self.target_revolutions = int(target_revs)
            self.color_filter = color_mode
            self.marker_shape_mode = shape_mode
            self.is_active = True
            self.calibration_complete = False
            self.revolutions_completed = 0
            self.crossing_timestamps.clear()
            self.instant_rpms.clear()
            self.trajectory_history.clear()
            self.recent_positions.clear()
            self.cx_history.clear()
            self.last_crossing_time = 0.0
            self.in_transit = False
            self.start_time = time.time()
            self.status_message = f"Accelerating motor to {self.target_rpm} RPM..."

            # Start Motor
            if self.hw and hasattr(self.hw, "stepper") and self.hw.stepper:
                try:
                    self.hw.stepper.set_rpm(self.target_rpm)
                    if not self.hw.stepper.is_running():
                        self.hw.stepper.start_rotation("CW")
                except Exception as e:
                    print(f"Warning starting stepper: {e}")

            # Turn on LED for bright illumination
            if self.hw and hasattr(self.hw, "led_manager") and self.hw.led_manager:
                try:
                    from opencal.hardware.led_manager import GREEN, WHITE
                    self.hw.led_manager.set_color(GREEN if color_mode == "green" else WHITE)
                except Exception:
                    pass

            self.last_log_path = self.logger.start_session("motor_auto_cal")
            self.status_message = "Tracking marker crossings (Optical Gate)..."

    def stop_calibration(self, stop_motor: bool = True):
        with self._lock:
            self.is_active = False
            self.status_message = "Calibration Stopped"
            if stop_motor and self.hw and hasattr(self.hw, "stepper") and self.hw.stepper:
                try:
                    self.hw.stepper.stop()
                except Exception:
                    pass
            self.last_log_path = self.logger.stop_session()

    def process_frame(self, frame: np.ndarray, frame_timestamp_ns: int | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        """Processes one video frame: detects marker exclusively inside the draggable Optical Gate ROI."""
        t_now = (frame_timestamp_ns / 1e9) if frame_timestamp_ns else time.time()
        h, w = frame.shape[:2]

        # 1. Crop to Draggable Optical Gate ROI
        gx1 = max(0, min(w - 20, int(self.gate_x * w)))
        gy1 = max(0, min(h - 20, int(self.gate_y * h)))
        gx2 = max(gx1 + 20, min(w, int((self.gate_x + self.gate_w) * w)))
        gy2 = max(gy1 + 20, min(h, int((self.gate_y + self.gate_h) * h)))
        gate_img = frame[gy1:gy2, gx1:gx2]
        gate_w = max(1, gx2 - gx1)
        gate_h = max(1, gy2 - gy1)
        gate_center_y = gate_h / 2.0
        gate_center_x = gate_w / 2.0

        # 2. Marker Segmentation within Optical Gate
        marker_detected = False
        marker_cx, marker_cy = 0, 0
        marker_norm_y = 0.0
        confidence = 0.0
        shape_type = "none"
        line_tilt = 0.0
        line_len = 0.0

        gray_gate = cv2.cvtColor(gate_img, cv2.COLOR_BGR2GRAY)

        if self.color_filter in ("dark_line", "dark_dot", "black", "black_line"):
            # Illumination-invariant absorption detection (works in red LED, white LED, or ambient)
            max_ch = np.max(gate_img, axis=2)
            mean_illum = float(np.mean(max_ch))
            dark_thresh = min(120, max(30, int(mean_illum * 0.55)))
            mask = (max_ch < dark_thresh).astype(np.uint8) * 255
            k_clean = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_clean)
        elif self.color_filter == "red":
            hsv_gate = cv2.cvtColor(gate_img, cv2.COLOR_BGR2HSV)
            m1 = cv2.inRange(hsv_gate, np.array([0, 50, 40]), np.array([14, 255, 255]))
            m2 = cv2.inRange(hsv_gate, np.array([168, 50, 40]), np.array([180, 255, 255]))
            mask_hsv = cv2.bitwise_or(m1, m2)
            roi_i16 = gate_img.astype(np.int16)
            b_ch, g_ch, r_ch = roi_i16[:, :, 0], roi_i16[:, :, 1], roi_i16[:, :, 2]
            diff_rg = r_ch - g_ch
            diff_rb = r_ch - b_ch
            mask_rgb = ((diff_rg > 25) & (diff_rb > 20) & (r_ch > 60)).astype(np.uint8) * 255
            mask = cv2.bitwise_and(mask_hsv, mask_rgb)
            k_rect = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_rect)
        elif self.color_filter == "green":
            hsv_gate = cv2.cvtColor(gate_img, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv_gate, np.array([35, 70, 70]), np.array([85, 255, 255]))
        elif self.color_filter == "cyan":
            hsv_gate = cv2.cvtColor(gate_img, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv_gate, np.array([80, 70, 70]), np.array([105, 255, 255]))
        else:  # "bright_dot" / white / fluorescent
            _, mask = cv2.threshold(gray_gate, 210, 255, cv2.THRESH_BINARY)

        # 3. Contour Validation & Centroid Extraction within Optical Gate
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_targets = []
        for c in contours:
            area = cv2.contourArea(c)
            bx, by, bw, bh = cv2.boundingRect(c)
            if self.marker_shape_mode == "line" or self.color_filter in ("dark_line", "black", "black_line"):
                # Line must span across at least 12% of the gate width and have substantial area
                if bw >= max(16, int(gate_w * 0.12)) and area >= 30 and bh <= int(gate_h * 0.85):
                    valid_targets.append(c)


            elif self.marker_shape_mode == "dot":
                if max(bw, bh) <= int(gate_h * 0.50) and area >= 25:
                    valid_targets.append(c)
            else:
                if area >= 40:
                    valid_targets.append(c)

        if valid_targets:
            best_c = max(valid_targets, key=cv2.contourArea)
            M = cv2.moments(best_c)
            if M["m00"] > 0:
                marker_cx = int(M["m10"] / M["m00"])
                marker_cy = int(M["m01"] / M["m00"])
                marker_norm_y = (marker_cy - gate_center_y) / gate_center_y
                marker_detected = True
                confidence = float(cv2.contourArea(best_c))
                self.last_marker_seen = t_now
                shape_type = "line" if self.marker_shape_mode != "dot" else "dot"
                self.detected_shape_type = shape_type
                line_len = float(gate_w)

                # Line tilt calculation within the gate
                if len(best_c) >= 5:
                    [vx, vy, x0, y0] = cv2.fitLine(best_c, cv2.DIST_L2, 0, 0.01, 0.01)
                    line_tilt = float(math.degrees(math.atan2(vy[0], vx[0])))
                    if line_tilt > 90: line_tilt -= 180
                    elif line_tilt < -90: line_tilt += 180

                self.line_tilt_deg = line_tilt
                self.line_length_px = line_len
                self.horizontal_drift_px = float(marker_cx - gate_center_x)
                self.cx_history.append(marker_cx)
                if len(self.cx_history) >= 10:
                    self.wobble_runout_px = float(max(self.cx_history) - min(self.cx_history))

        # 4. Sub-Frame Crossing Detection (Bidirectional Zero Crossing)
        if self.is_active and marker_detected:
            self.recent_positions.append((t_now, marker_norm_y))
            self.trajectory_history.append((t_now, marker_norm_y))

            min_period = (60.0 / self.target_rpm) * 0.60

            if len(self.recent_positions) >= 2:
                t_prev, y_prev = self.recent_positions[-2]
                t_curr, y_curr = self.recent_positions[-1]
                dt = t_curr - t_prev
                # Only valid if frames are continuous in time (not across wrap-around gap) and delta-y is reasonable
                is_continuous = (0.001 < dt < 0.25) and (abs(y_curr - y_prev) < 0.80)
                is_zero_crossing = is_continuous and ((y_prev < 0.0 <= y_curr) or (y_prev > 0.0 >= y_curr))

                if is_zero_crossing and (self.last_crossing_time == 0.0 or (t_now - self.last_crossing_time > min_period)):
                    if abs(y_curr - y_prev) > 1e-6:
                        frac = abs(0.0 - y_prev) / abs(y_curr - y_prev)
                        t_cross = t_prev + frac * dt
                    else:
                        t_cross = t_now

                    self._register_crossing(t_cross)


        # 5. Telemetry Gathering
        pi_telemetry = get_pi_system_telemetry()
        motor_telemetry = {}
        if self.hw and hasattr(self.hw, "stepper") and self.hw.stepper:
            try:
                motor_telemetry = self.hw.stepper.get_telemetry()
            except Exception:
                pass

        curr_cf = motor_telemetry.get("correction_factor", 1.0)
        if self.measured_avg_rpm > 0.1:
            self.suggested_correction_factor = round(curr_cf * (self.target_rpm / self.measured_avg_rpm), 6)

        sample = {
            "timestamp_unix": t_now,
            "frame_timestamp_ns": frame_timestamp_ns or int(t_now * 1e9),
            "is_calibrating": self.is_active,
            "target_rpm": self.target_rpm,
            "revolutions": self.revolutions_completed,
            "target_revolutions": self.target_revolutions,
            "measured_avg_rpm": round(self.measured_avg_rpm, 4),
            "rpm_jitter_std": round(self.rpm_jitter_std, 4),
            "suggested_correction_factor": self.suggested_correction_factor,
            "current_correction_factor": curr_cf,
            "marker_detected": marker_detected,
            "detected_shape": shape_type,
            "line_tilt_deg": round(line_tilt, 2),
            "line_length_px": round(line_len, 1),
            "wobble_runout_px": round(self.wobble_runout_px, 1),
            "marker_norm_y": round(marker_norm_y, 4),
            "confidence": round(confidence, 1),
            "cpu_temp_c": pi_telemetry.get("cpu_temp_c", 0.0),
            "core_voltage_v": pi_telemetry.get("core_voltage_v", 0.0),
            "arm_clock_mhz": pi_telemetry.get("arm_clock_mhz", 0.0),
            "cpu_usage_pct": pi_telemetry.get("cpu_usage_pct", 0.0),
            "motor_vin_v": motor_telemetry.get("vin_voltage_v", 0.0),
            "motor_load": motor_telemetry.get("stallguard_load", 0),
            "motor_driver": motor_telemetry.get("driver", "unknown"),
            "gate_roi": self.get_gate_roi(),
            "status_message": self.status_message,
        }
        self.latest_sample = sample
        if self.is_active:
            self.logger.record_sample(sample)

        # 6. Render HUD Overlay onto Frame
        annotated = self._render_hud(frame, gx1, gy1, gx2, gy2, 
                                     marker_detected, marker_cx, marker_cy, 
                                     shape_type, None, line_tilt, line_len, sample)
        return annotated, sample

    def _register_crossing(self, t_cross: float):
        self.crossing_timestamps.append(t_cross)
        self.last_crossing_time = t_cross
        self.revolutions_completed = len(self.crossing_timestamps) - 1

        if len(self.crossing_timestamps) >= 2:
            p_inst = self.crossing_timestamps[-1] - self.crossing_timestamps[-2]
            rpm_inst = 60.0 / p_inst
            self.instant_rpms.append(rpm_inst)

            t_total = self.crossing_timestamps[-1] - self.crossing_timestamps[0]
            self.measured_avg_rpm = (self.revolutions_completed * 60.0) / t_total

            if len(self.instant_rpms) >= 2:
                self.rpm_jitter_std = float(np.std(self.instant_rpms))

            self.status_message = f"Rev {self.revolutions_completed}/{self.target_revolutions} -> Inst: {rpm_inst:.3f} RPM | Avg: {self.measured_avg_rpm:.3f} RPM"

        if self.revolutions_completed >= self.target_revolutions:
            self.calibration_complete = True
            self.is_active = False
            self.status_message = f"✅ COMPLETE! Measured: {self.measured_avg_rpm:.4f} RPM (Jitter: ±{self.rpm_jitter_std:.4f} RPM)"
            self.stop_calibration(stop_motor=True)

    def _render_hud(self, frame: np.ndarray, gx1: int, gy1: int, gx2: int, gy2: int, 
                    marker_detected: bool, mcx: int, mcy: int, 
                    shape_type: str, line_pts: Any, line_tilt: float, line_len: float, 
                    sample: dict[str, Any]) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]

        gate_w, gate_h = gx2 - gx1, gy2 - gy1
        gate_center_y = gy1 + (gate_h // 2)

        # 1. Optical Gate Neon Box & Corner Brackets
        gate_color = (0, 255, 255) if marker_detected else (180, 160, 60)
        cv2.rectangle(out, (gx1, gy1), (gx2, gy2), gate_color, 2)
        
        brk = 18
        # Corner brackets
        cv2.line(out, (gx1, gy1), (gx1 + brk, gy1), (0, 255, 255), 3)
        cv2.line(out, (gx1, gy1), (gx1, gy1 + brk), (0, 255, 255), 3)
        cv2.line(out, (gx2, gy1), (gx2 - brk, gy1), (0, 255, 255), 3)
        cv2.line(out, (gx2, gy1), (gx2, gy1 + brk), (0, 255, 255), 3)
        cv2.line(out, (gx1, gy2), (gx1 + brk, gy2), (0, 255, 255), 3)
        cv2.line(out, (gx1, gy2), (gx1, gy2 - brk), (0, 255, 255), 3)
        cv2.line(out, (gx2, gy2), (gx2 - brk, gy2), (0, 255, 255), 3)
        cv2.line(out, (gx2, gy2), (gx2, gy2 - brk), (0, 255, 255), 3)

        # Gate Horizontal Equator (Centerline)
        cv2.line(out, (gx1, gate_center_y), (gx2, gate_center_y), (0, 140, 255), 2, cv2.LINE_AA)
        
        # Centerline Tag Label
        tag_x, tag_y = gx1 + 8, max(20, gy1 - 8)
        tag_text = f"OPTICAL GATE: LOCKED (y={sample['marker_norm_y']:+.3f})" if marker_detected else "OPTICAL GATE: IDLE / SEARCHING"
        tag_bg_color = (0, 60, 0) if marker_detected else (25, 25, 25)
        (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(out, (tag_x - 4, tag_y - th - 4), (tag_x + tw + 4, tag_y + 4), tag_bg_color, -1)
        cv2.rectangle(out, (tag_x - 4, tag_y - th - 4), (tag_x + tw + 4, tag_y + 4), (0, 255, 255), 1)
        cv2.putText(out, tag_text, (tag_x, tag_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 128) if marker_detected else (200, 220, 255), 2, cv2.LINE_AA)

        # 2. Draw Marker Position Inside Gate
        if marker_detected:
            abs_x, abs_y = gx1 + mcx, gy1 + mcy
            cv2.circle(out, (abs_x, abs_y), 7, (0, 0, 255), -1)
            cv2.circle(out, (abs_x, abs_y), 3, (255, 255, 255), -1)
            cv2.line(out, (gx1, abs_y), (gx2, abs_y), (0, 255, 0), 3, cv2.LINE_AA)

        # 3. Top Telemetry Glass Bar
        overlay = out.copy()
        cv2.rectangle(overlay, (0, 0), (w, 82), (8, 12, 22), -1)
        cv2.addWeighted(overlay, 0.85, out, 0.15, 0, out)

        status_color = (0, 255, 128) if self.is_active else ((0, 255, 255) if self.calibration_complete else (220, 220, 220))
        cv2.putText(out, f"OPENCAL AUTO-TUNER: {self.status_message}", (14, 28), cv2.FONT_HERSHEY_DUPLEX, 0.70, status_color, 2, cv2.LINE_AA)

        # Compensation State Tag on Top Right of HUD
        cur_f = self.current_correction_factor
        is_comp = abs(cur_f - 1.0) > 0.00005
        comp_pct = (cur_f - 1.0) * 100.0
        comp_badge_text = f"MOTOR: COMPENSATED ({cur_f:.6f} | {comp_pct:+.2f}%)" if is_comp else "MOTOR: RAW 1:1 BASELINE (NO COMP)"
        comp_badge_color = (0, 255, 128) if is_comp else (0, 180, 255)
        (cw, ch), _ = cv2.getTextSize(comp_badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)
        cv2.rectangle(out, (w - cw - 20, 10), (w - 10, 36), (20, 30, 45), -1)
        cv2.rectangle(out, (w - cw - 20, 10), (w - 10, 36), comp_badge_color, 1)
        cv2.putText(out, comp_badge_text, (w - cw - 15, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.52, comp_badge_color, 2, cv2.LINE_AA)

        metrics_text = (
            f"TARGET: {self.target_rpm:.1f} RPM  |  "
            f"MEASURED: {self.measured_avg_rpm:.4f} RPM  |  "
            f"REV: {self.revolutions_completed}/{self.target_revolutions}  |  "
            f"SUGGESTED: {self.suggested_correction_factor:.6f}"
        )
        cv2.putText(out, metrics_text, (14, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)


        # 4. Bottom Hardware Status Bar
        bot_overlay = out.copy()
        cv2.rectangle(bot_overlay, (0, h - 46), (w, h), (8, 12, 22), -1)
        cv2.addWeighted(bot_overlay, 0.85, out, 0.15, 0, out)

        hw_text = (
            f"GATE: {gate_w}x{gate_h}px @ ({gx1},{gy1})  |  "
            f"PI: {sample.get('cpu_temp_c', 0)}C @ {sample.get('core_voltage_v', 0)}V  |  "
            f"MOTOR: {sample.get('motor_vin_v', 0)}V  |  "
            f"TILT: {sample.get('line_tilt_deg', 0):+.1f} deg"
        )
        cv2.putText(out, hw_text, (14, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (180, 220, 255), 2, cv2.LINE_AA)

        # 5. Mini Realtime Trajectory Waveform (Bottom Right)
        if len(self.trajectory_history) >= 2:
            gw, gh = 200, 70
            gx1_w, gy1_w = w - gw - 15, h - gh - 55
            cv2.rectangle(out, (gx1_w, gy1_w), (gx1_w + gw, gy1_w + gh), (15, 22, 35), -1)
            cv2.rectangle(out, (gx1_w, gy1_w), (gx1_w + gw, gy1_w + gh), (80, 120, 160), 1)
            cv2.line(out, (gx1_w, gy1_w + gh // 2), (gx1_w + gw, gy1_w + gh // 2), (60, 80, 100), 1)

            pts = []
            hist = list(self.trajectory_history)
            for idx, (_, y_val) in enumerate(hist):
                px = gx1_w + int((idx / len(hist)) * gw)
                py = gy1_w + int(((y_val + 1.0) / 2.0) * gh)
                py = max(gy1_w, min(gy1_w + gh, py))
                pts.append((px, py))

            for i in range(1, len(pts)):
                cv2.line(out, pts[i - 1], pts[i], (0, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(out, "Y-WAVEFORM", (gx1_w + 8, gy1_w + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 210, 255), 1)

        return out

    def apply_correction(self) -> dict[str, Any]:
        """Applies suggested CORRECTION_FACTOR to live motor and persists to config.json."""
        if self.suggested_correction_factor <= 0:
            return {"success": False, "message": "Invalid correction factor"}

        new_factor = self.suggested_correction_factor

        # 1. Update Live Stepper Motor
        if self.hw and hasattr(self.hw, "stepper") and self.hw.stepper:
            try:
                self.hw.stepper.set_correction_factor(new_factor)
            except Exception as e:
                print(f"Error applying correction to stepper: {e}")

        # 2. Persist into config.json
        try:
            with open(CFG_PATH, "r") as f:
                cfg_data = json.load(f)
            
            if "stepper_motor" not in cfg_data:
                cfg_data["stepper_motor"] = {}
            cfg_data["stepper_motor"]["correction_factor"] = new_factor

            with open(CFG_PATH, "w") as f:
                json.dump(cfg_data, f, indent=2)

            return {
                "success": True, 
                "message": f"Successfully applied and saved CORRECTION_FACTOR = {new_factor:.6f} to config.json!",
                "correction_factor": new_factor
            }
        except Exception as e:
            return {"success": False, "message": f"Failed to save config.json: {e}"}

    def revert_correction(self, factor: float = 1.0) -> dict[str, Any]:
        """Reverts motor correction factor back to uncompensated default (1.000000) or specified value."""
        target_factor = float(factor)
        if self.hw and hasattr(self.hw, "stepper") and self.hw.stepper:
            try:
                self.hw.stepper.set_correction_factor(target_factor)
            except Exception as e:
                print(f"Error resetting stepper correction factor: {e}")

        try:
            with open(CFG_PATH, "r") as f:
                cfg_data = json.load(f)
            
            if "stepper_motor" not in cfg_data:
                cfg_data["stepper_motor"] = {}
            cfg_data["stepper_motor"]["correction_factor"] = target_factor

            with open(CFG_PATH, "w") as f:
                json.dump(cfg_data, f, indent=2)

            return {
                "success": True, 
                "message": f"Motor reset to uncompensated base speed (factor = {target_factor:.6f})!",
                "correction_factor": target_factor
            }
        except Exception as e:
            return {"success": False, "message": f"Failed to update config.json: {e}"}


class SteppedRotationRunner:
    """Controls stepped rotation test: 1 revolution -> pause -> repeat X times."""
    def __init__(self, hw: Any):
        self.hw = hw
        self.is_active: bool = False
        self._stop_requested: bool = False
        self._thread: threading.Thread | None = None
        self.current_rev: int = 0
        self.total_revs: int = 0
        self.state: str = "IDLE"
        self.status_message: str = "Idle (Ready for Stepped Test)"

    def start(self, total_revs: int = 1, rpm: float = 9.0, pause_s: float = 1.5, direction: str = "CW") -> dict[str, Any]:
        self.stop()
        self.is_active = True
        self._stop_requested = False
        self.total_revs = max(1, int(total_revs))
        self.current_rev = 0
        self.state = "STARTING"
        self.status_message = f"Starting stepped test: {self.total_revs} turns at {rpm} RPM (pause {pause_s}s)..."

        def _worker():
            stepper = getattr(self.hw, "stepper", None) if self.hw else None
            try:
                for rev_idx in range(1, self.total_revs + 1):
                    if self._stop_requested:
                        break
                    self.current_rev = rev_idx
                    self.state = "ROTATING"
                    self.status_message = f"Rotating Turn {rev_idx}/{self.total_revs} (360°)..."

                    if stepper:
                        if hasattr(stepper, "rotate_revolutions"):
                            stepper.rotate_revolutions(1.0, direction=direction, rpm=rpm)
                        elif hasattr(stepper, "rotate_steps"):
                            steps_per_rev = getattr(stepper, "steps_per_rev", 3200)
                            cf = getattr(stepper, "correction_factor", 1.0)
                            total_steps = int(round(steps_per_rev * cf))
                            stepper.set_rpm(rpm)
                            stepper.rotate_steps(total_steps, direction=direction)

                    if self._stop_requested:
                        break

                    if rev_idx < self.total_revs:
                        self.state = "PAUSED"
                        self.status_message = f"Turn {rev_idx}/{self.total_revs} done! Pausing {pause_s}s (Observe line position)..."
                        t_pause_start = time.time()
                        while time.time() - t_pause_start < pause_s and not self._stop_requested:
                            time.sleep(0.05)

                if not self._stop_requested:
                    self.state = "COMPLETED"
                    self.status_message = f"Completed all {self.total_revs} stepped turns!"
                else:
                    self.state = "STOPPED"
                    self.status_message = "Stepped rotation stopped."
            except Exception as e:
                self.state = "ERROR"
                self.status_message = f"Error during stepped rotation: {e}"
            finally:
                self.is_active = False

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()
        return {"success": True, "message": f"Stepped test started ({self.total_revs} revs)"}

    def stop(self) -> dict[str, Any]:
        self._stop_requested = True
        stepper = getattr(self.hw, "stepper", None) if self.hw else None
        if stepper:
            try:
                stepper.stop()
            except Exception:
                pass
        self.is_active = False
        self.state = "STOPPED"
        self.status_message = "Stopped"
        return {"success": True, "message": "Stepped rotation stopped."}

    def get_status(self) -> dict[str, Any]:
        return {
            "is_active": self.is_active,
            "current_rev": self.current_rev,
            "total_revs": self.total_revs,
            "state": self.state,
            "status_message": self.status_message,
        }


class MarkerFinder:
    """Rotates the vial slowly to locate and center the drawn marker in the Optical Gate (max 2 revs)."""
    def __init__(self, hw: Any, calibrator: Any):
        self.hw = hw
        self.calibrator = calibrator
        self.is_active: bool = False
        self._stop_requested: bool = False
        self._thread: threading.Thread | None = None
        self.state: str = "IDLE"
        self.status_message: str = "Idle (Ready to Find Marker)"

    def start(self, rpm: float = 4.5, max_revs: float = 2.0, direction: str = "CW", color_mode: str = "dark_line", shape_mode: str = "line") -> dict[str, Any]:
        self.stop()
        self.is_active = True
        self._stop_requested = False
        self.state = "SEARCHING"
        if self.calibrator:
            self.calibrator.color_filter = color_mode
            self.calibrator.marker_shape_mode = shape_mode
        self.status_message = f"Searching for {color_mode.replace('_', ' ')} marker at {rpm} RPM (max {max_revs:.0f} turns)..."

        def _worker():
            stepper = getattr(self.hw, "stepper", None) if self.hw else None
            try:
                if stepper:
                    stepper.set_rpm(rpm)
                    if not stepper.is_running():
                        stepper.start_rotation(direction)

                max_duration = (max_revs * 60.0 / rpm) + 2.0
                t_start = time.time()
                marker_found = False

                while time.time() - t_start < max_duration and not self._stop_requested:
                    sample = getattr(self.calibrator, "latest_sample", {})
                    detected = sample.get("marker_detected", False)
                    norm_y = sample.get("marker_norm_y", 1.0)
                    
                    # When marker is detected and close to equator (|y| <= 0.15)
                    if detected and abs(norm_y) <= 0.15:
                        if stepper:
                            stepper.stop()
                        marker_found = True
                        self.state = "FOUND_CENTERED"
                        self.status_message = f"🎯 Marker located & centered in Optical Gate at y={norm_y:+.3f}!"
                        break

                    time.sleep(0.033)

                if not marker_found:
                    if stepper:
                        stepper.stop()
                    if self._stop_requested:
                        self.state = "STOPPED"
                        self.status_message = "Marker search cancelled."
                    else:
                        self.state = "NOT_FOUND"
                        self.status_message = f"⚠️ Marker not detected after {max_revs:.0f} full revolutions."
            except Exception as e:
                self.state = "ERROR"
                self.status_message = f"Search error: {e}"
                if stepper:
                    try:
                        stepper.stop()
                    except Exception:
                        pass
            finally:
                self.is_active = False

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()
        return {"success": True, "message": "Marker search started"}

    def stop(self) -> dict[str, Any]:
        self._stop_requested = True
        stepper = getattr(self.hw, "stepper", None) if self.hw else None
        if stepper:
            try:
                stepper.stop()
            except Exception:
                pass
        self.is_active = False
        self.state = "STOPPED"
        self.status_message = "Search stopped"
        return {"success": True, "message": "Marker search stopped."}

    def get_status(self) -> dict[str, Any]:
        return {
            "is_active": self.is_active,
            "state": self.state,
            "status_message": self.status_message,
        }
