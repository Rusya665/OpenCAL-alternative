#!/usr/bin/env python3
"""
OpenCAL Automated Camera-Based Motor Calibration Engine
Tracks marker on rotating vial, detects sub-frame crossings, computes high-precision RPM,
calculates CORRECTION_FACTOR, and logs full-spectrum hardware telemetry.
"""

import time
import math
import json
import threading
from collections import deque
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from opencal.utils.telemetry import get_pi_system_telemetry, TelemetrySessionLogger
from opencal.utils.config import CFG_PATH


class MotorCalibrator:
    def __init__(self, hardware_controller=None):
        self.hw = hardware_controller
        self.logger = TelemetrySessionLogger()
        self._lock = threading.RLock()

        # Calibration Configuration
        self.target_rpm: float = 9.0
        self.target_revolutions: int = 30
        self.color_filter: str = "bright_dot"  # "bright_dot", "green", "cyan", "dark_dot"
        
        # Marker Shape & Wobble Tracking
        self.marker_shape_mode: str = "auto"  # "auto", "line", "dot"
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

    def start_calibration(self, target_rpm: float = 9.0, target_revs: int = 30, color_mode: str = "bright_dot", shape_mode: str = "auto"):
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
                    self.hw.led_manager.set_solid_color(GREEN if color_mode == "green" else WHITE)
                except Exception:
                    pass

            self.last_log_path = self.logger.start_session("motor_auto_cal")
            self.status_message = "Tracking marker crossings (Line/Dot)..."

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
        """Processes one video frame: detects Line or Dot marker, measures wobble, records crossings, annotates HUD."""
        t_now = (frame_timestamp_ns / 1e9) if frame_timestamp_ns else time.time()
        h, w = frame.shape[:2]

        # 1. Define Central ROI (focus on center 60% of vial)
        roi_x1, roi_y1 = int(w * 0.15), int(h * 0.10)
        roi_x2, roi_y2 = int(w * 0.85), int(h * 0.90)
        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        roi_h, roi_w = roi.shape[:2]
        roi_center_x = roi_w / 2.0
        roi_center_y = roi_h / 2.0

        # 2. Marker Segmentation (Color / Brightness Thresholding)
        marker_detected = False
        marker_cx, marker_cy = 0, 0
        marker_norm_y = 0.0
        confidence = 0.0
        shape_type = "none"
        line_tilt = 0.0
        line_len = 0.0
        line_pts = None

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        if self.color_filter == "green":
            mask = cv2.inRange(hsv, np.array([35, 70, 70]), np.array([85, 255, 255]))
        elif self.color_filter == "cyan":
            mask = cv2.inRange(hsv, np.array([80, 70, 70]), np.array([105, 255, 255]))
        elif self.color_filter == "dark_dot":
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 45, 255, cv2.THRESH_BINARY_INV)
        else:  # "bright_dot" / white / fluorescent
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
            if cv2.countNonZero(mask) < 10:
                thresh_val = max(170, int(np.percentile(gray, 97)))
                _, mask = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Accept both compact blobs (dots) and elongated contours (lines)
        valid_contours = [c for c in contours if 15 < cv2.contourArea(c) < (roi_w * roi_h * 0.40)]

        if valid_contours:
            # Score contours based on shape mode preference
            if self.marker_shape_mode == "line":
                # Prefer elongated horizontal lines: higher width / aspect ratio
                def _line_score(c):
                    bx, by, bw, bh = cv2.boundingRect(c)
                    return cv2.contourArea(c) * (bw / max(bh, 1.0))
                best_c = max(valid_contours, key=_line_score)
            elif self.marker_shape_mode == "dot":
                # Prefer circular/compact blobs
                def _dot_score(c):
                    bx, by, bw, bh = cv2.boundingRect(c)
                    ar = max(bw, bh) / max(1.0, min(bw, bh))
                    return cv2.contourArea(c) / (ar**2)
                best_c = max(valid_contours, key=_dot_score)
            else:  # "auto"
                best_c = max(valid_contours, key=cv2.contourArea)

            M = cv2.moments(best_c)
            if M["m00"] > 0:
                marker_cx = int(M["m10"] / M["m00"])
                marker_cy = int(M["m01"] / M["m00"])
                marker_norm_y = (marker_cy - roi_center_y) / (roi_h / 2.0)
                marker_detected = True
                confidence = float(cv2.contourArea(best_c))
                self.last_marker_seen = t_now

                # Geometry analysis: Classify as Line vs Dot and measure tilt/runout
                bx, by, bw, bh = cv2.boundingRect(best_c)
                aspect_ratio = bw / max(1.0, bh)

                if bw >= 24 and aspect_ratio >= 2.0:
                    shape_type = "line"
                    # Fit 2D line to contour points
                    [vx, vy, x0, y0] = cv2.fitLine(best_c, cv2.DIST_L2, 0, 0.01, 0.01)
                    line_tilt = float(math.degrees(math.atan2(vy[0], vx[0])))
                    # Normalize tilt to [-90, +90]
                    if line_tilt > 90: line_tilt -= 180
                    elif line_tilt < -90: line_tilt += 180
                    line_len = float(bw)

                    # Compute line endpoints inside ROI for rendering
                    pt1_x = int(marker_cx - (bw / 2))
                    pt1_y = int(marker_cy - ((bw / 2) * (vy[0] / (vx[0] + 1e-6))))
                    pt2_x = int(marker_cx + (bw / 2))
                    pt2_y = int(marker_cy + ((bw / 2) * (vy[0] / (vx[0] + 1e-6))))
                    line_pts = ((pt1_x, pt1_y), (pt2_x, pt2_y))
                else:
                    shape_type = "dot"
                    line_len = float(max(bw, bh))

                self.detected_shape_type = shape_type
                self.line_tilt_deg = line_tilt
                self.line_length_px = line_len

                # Axial wobble / runout tracking (horizontal center drift)
                self.horizontal_drift_px = float(marker_cx - roi_center_x)
                self.cx_history.append(marker_cx)
                if len(self.cx_history) >= 10:
                    self.wobble_runout_px = float(max(self.cx_history) - min(self.cx_history))

        # 3. Sub-Frame Crossing Detection
        if self.is_active and marker_detected:
            self.recent_positions.append((t_now, marker_norm_y))
            self.trajectory_history.append((t_now, marker_norm_y))

            # Minimum time between 360° revolutions at target RPM (e.g. 5.5s @ 9 RPM)
            min_period = (60.0 / self.target_rpm) * 0.65

            if len(self.recent_positions) >= 2:
                t_prev, y_prev = self.recent_positions[-2]
                t_curr, y_curr = self.recent_positions[-1]

                # Centerline Zero-Crossing: y crosses 0.0 with positive vertical velocity
                if (y_prev < 0.0 <= y_curr) and (t_now - self.last_crossing_time > min_period):
                    if abs(y_curr - y_prev) > 1e-6:
                        dt = t_curr - t_prev
                        frac = (0.0 - y_prev) / (y_curr - y_prev)
                        t_cross = t_prev + frac * dt
                    else:
                        t_cross = t_now

                    self._register_crossing(t_cross)

        # 4. Telemetry Gathering
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
            "status_message": self.status_message,
        }
        self.latest_sample = sample
        if self.is_active:
            self.logger.record_sample(sample)

        # 5. Render HUD Overlay onto Frame
        annotated = self._render_hud(frame, roi_x1, roi_y1, roi_x2, roi_y2, 
                                     marker_detected, marker_cx, marker_cy, 
                                     shape_type, line_pts, line_tilt, line_len, sample)
        return annotated, sample

    def _register_crossing(self, t_cross: float):
        self.crossing_timestamps.append(t_cross)
        self.last_crossing_time = t_cross
        self.revolutions_completed = len(self.crossing_timestamps) - 1

        if len(self.crossing_timestamps) >= 2:
            p_inst = self.crossing_timestamps[-1] - self.crossing_timestamps[-2]
            rpm_inst = 60.0 / p_inst
            self.instant_rpms.append(rpm_inst)

            # Cumulative average RPM
            t_total = self.crossing_timestamps[-1] - self.crossing_timestamps[0]
            self.measured_avg_rpm = (self.revolutions_completed * 60.0) / t_total

            # Jitter Standard Deviation
            if len(self.instant_rpms) >= 2:
                self.rpm_jitter_std = float(np.std(self.instant_rpms))

            self.status_message = f"Rev {self.revolutions_completed}/{self.target_revolutions} -> Inst: {rpm_inst:.3f} RPM | Avg: {self.measured_avg_rpm:.3f} RPM"

        if self.revolutions_completed >= self.target_revolutions:
            self.calibration_complete = True
            self.is_active = False
            self.status_message = f"✅ COMPLETE! Measured: {self.measured_avg_rpm:.4f} RPM (Jitter: ±{self.rpm_jitter_std:.4f} RPM)"
            self.stop_calibration(stop_motor=True)

    def _render_hud(self, frame: np.ndarray, rx1: int, ry1: int, rx2: int, ry2: int, 
                    marker_detected: bool, mcx: int, mcy: int, 
                    shape_type: str, line_pts: Any, line_tilt: float, line_len: float, 
                    sample: dict[str, Any]) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]

        # 1. Draw ROI Box & Centerline
        cv2.rectangle(out, (rx1, ry1), (rx2, ry2), (0, 255, 255), 1)
        mid_y = ry1 + (ry2 - ry1) // 2
        cv2.line(out, (rx1, mid_y), (rx2, mid_y), (0, 165, 255), 1, cv2.LINE_AA)
        cv2.putText(out, "CENTERLINE CROSSING PLANE", (rx1 + 10, mid_y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)

        # 2. Draw Detected Marker (Line vs Dot)
        if marker_detected:
            gx, gy = rx1 + mcx, ry1 + mcy
            if shape_type == "line" and line_pts:
                (p1x, p1y), (p2x, p2y) = line_pts
                gp1 = (rx1 + p1x, ry1 + p1y)
                gp2 = (rx1 + p2x, ry1 + p2y)
                # Draw thick axial line stripe
                cv2.line(out, gp1, gp2, (0, 255, 0), 3, cv2.LINE_AA)
                cv2.circle(out, gp1, 4, (0, 200, 255), -1)
                cv2.circle(out, gp2, 4, (0, 200, 255), -1)
                cv2.circle(out, (gx, gy), 5, (0, 0, 255), -1)
                cv2.putText(out, f"LINE [L={int(line_len)}px, Tilt={line_tilt:+.1f} deg]", (gx - 50, gy - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
            else:
                # Dot / circle marker
                r = max(6, int(line_len / 2))
                cv2.circle(out, (gx, gy), r, (0, 255, 0), 2)
                cv2.circle(out, (gx, gy), 3, (0, 0, 255), -1)
                cv2.putText(out, f"DOT [r={r}px, y={sample['marker_norm_y']:+.2f}]", (gx + 16, gy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)

        # 3. Top Telemetry Glass Bar
        overlay = out.copy()
        cv2.rectangle(overlay, (0, 0), (w, 64), (10, 15, 25), -1)
        cv2.addWeighted(overlay, 0.75, out, 0.25, 0, out)

        status_color = (0, 255, 128) if self.is_active else ((0, 255, 255) if self.calibration_complete else (200, 200, 200))
        cv2.putText(out, f"OPENCAL AUTO-TUNER: {self.status_message}", (14, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.52, status_color, 1, cv2.LINE_AA)

        metrics_text = (
            f"TARGET: {self.target_rpm:.2f} RPM | "
            f"MEASURED: {self.measured_avg_rpm:.4f} RPM | "
            f"JITTER: +- {self.rpm_jitter_std:.4f} | "
            f"REV: {self.revolutions_completed}/{self.target_revolutions} | "
            f"CORR: {self.suggested_correction_factor:.6f}"
        )
        cv2.putText(out, metrics_text, (14, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # 4. Bottom Hardware & Wobble Status Bar
        bot_overlay = out.copy()
        cv2.rectangle(bot_overlay, (0, h - 36), (w, h), (10, 15, 25), -1)
        cv2.addWeighted(bot_overlay, 0.75, out, 0.25, 0, out)

        hw_text = (
            f"PI: {sample.get('cpu_temp_c', 0)}C @ {sample.get('core_voltage_v', 0)}V | "
            f"MOTOR: {sample.get('motor_vin_v', 0)}V | "
            f"WOBBLE: Runout={sample.get('wobble_runout_px', 0)}px, Tilt={sample.get('line_tilt_deg', 0):+.1f} deg | "
            f"SHAPE: {shape_type.upper()}"
        )
        cv2.putText(out, hw_text, (14, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 220, 255), 1, cv2.LINE_AA)

        # 5. Mini Realtime Trajectory Waveform (Bottom Right)
        if len(self.trajectory_history) >= 2:
            gw, gh = 180, 60
            gx1, gy1 = w - gw - 15, h - gh - 45
            cv2.rectangle(out, (gx1, gy1), (gx1 + gw, gy1 + gh), (20, 30, 45), -1)
            cv2.rectangle(out, (gx1, gy1), (gx1 + gw, gy1 + gh), (80, 100, 130), 1)
            cv2.line(out, (gx1, gy1 + gh // 2), (gx1 + gw, gy1 + gh // 2), (60, 80, 100), 1)

            pts = []
            hist = list(self.trajectory_history)
            for idx, (_, y_val) in enumerate(hist):
                px = gx1 + int((idx / len(hist)) * gw)
                py = gy1 + int(((y_val + 1.0) / 2.0) * gh)
                py = max(gy1, min(gy1 + gh, py))
                pts.append((px, py))

            for i in range(1, len(pts)):
                cv2.line(out, pts[i - 1], pts[i], (0, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(out, "Y-WAVEFORM", (gx1 + 6, gy1 + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 200, 255), 1)

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
