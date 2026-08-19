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
                    self.hw.led_manager.set_color(GREEN if color_mode == "green" else WHITE)
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
        if self.color_filter == "red":
            # Dual HSV Mask (Hue 0-15 & 165-180) with moderate saturation
            mask_hsv1 = cv2.inRange(hsv, np.array([0, 45, 35]), np.array([16, 255, 255]))
            mask_hsv2 = cv2.inRange(hsv, np.array([165, 45, 35]), np.array([180, 255, 255]))
            mask_hsv = cv2.bitwise_or(mask_hsv1, mask_hsv2)

            # Excess Red Color Index: Red marker absorbs G & B (R - G > 20 and R - B > 20)
            roi_i16 = roi.astype(np.int16)
            b_ch, g_ch, r_ch = roi_i16[:, :, 0], roi_i16[:, :, 1], roi_i16[:, :, 2]
            diff_rg = r_ch - g_ch
            diff_rb = r_ch - b_ch
            mask_rgb = ((diff_rg > 18) & (diff_rb > 18) & (r_ch > 50)).astype(np.uint8) * 255

            mask = cv2.bitwise_and(mask_hsv, mask_rgb)
            # Morphological smoothing to connect drawn line segments and remove speckles
            k_rect = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_rect)
        elif self.color_filter == "green":
            mask = cv2.inRange(hsv, np.array([35, 70, 70]), np.array([85, 255, 255]))
        elif self.color_filter == "cyan":
            mask = cv2.inRange(hsv, np.array([80, 70, 70]), np.array([105, 255, 255]))
        elif self.color_filter == "dark_dot":
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 55, 255, cv2.THRESH_BINARY_INV)
        else:  # "bright_dot" / white / fluorescent
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
            if cv2.countNonZero(mask) < 10:
                thresh_val = max(170, int(np.percentile(gray, 97)))
                _, mask = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Strict contour validation: a drawn line or dot is compact, not a giant ambient blob!
        valid_contours = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 10 or area > 4500:
                continue
            bx, by, bw, bh = cv2.boundingRect(c)
            # Rejection: Marker lines are horizontal and thin; dots are small
            if self.marker_shape_mode == "line" or (self.color_filter == "red" and self.marker_shape_mode != "dot"):
                if bh > 40:  # line cannot be taller than 40px
                    continue
                if bw < 15:  # line must have minimal width
                    continue
                valid_contours.append(c)
            elif self.marker_shape_mode == "dot":
                if bw > 65 or bh > 65:  # dot cannot be giant
                    continue
                valid_contours.append(c)
            else:  # "auto"
                if bh > 65 and bw > 65:  # discard massive background patches
                    continue
                valid_contours.append(c)

        if valid_contours:
            # Score contours based on shape mode preference
            if self.marker_shape_mode == "line" or (self.color_filter == "red" and self.marker_shape_mode != "dot"):
                def _line_score(c):
                    bx, by, bw, bh = cv2.boundingRect(c)
                    aspect = bw / max(float(bh), 1.0)
                    length_bonus = min(bw / 15.0, 6.0)
                    return cv2.contourArea(c) * (aspect ** 1.8) * length_bonus
                best_c = max(valid_contours, key=_line_score)
            elif self.marker_shape_mode == "dot":
                def _dot_score(c):
                    bx, by, bw, bh = cv2.boundingRect(c)
                    ar = max(bw, bh) / max(1.0, min(bw, bh))
                    return cv2.contourArea(c) / (ar ** 2)
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

                if bw >= 20 and aspect_ratio >= 1.8:
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

        # 3. Sub-Frame Crossing Detection (Bidirectional & Ingress-Aware)
        if self.is_active and marker_detected:
            self.recent_positions.append((t_now, marker_norm_y))
            self.trajectory_history.append((t_now, marker_norm_y))

            # Minimum time between 360° revolutions at target RPM (e.g. 4.0s @ 9 RPM)
            min_period = (60.0 / self.target_rpm) * 0.60

            if len(self.recent_positions) >= 2:
                t_prev, y_prev = self.recent_positions[-2]
                t_curr, y_curr = self.recent_positions[-1]

                # Centerline Zero-Crossing: supports both CW (y_prev < 0 <= y_curr) and CCW (y_prev > 0 >= y_curr)
                is_zero_crossing = (y_prev < 0.0 <= y_curr) or (y_prev > 0.0 >= y_curr)
                
                if is_zero_crossing and (t_now - self.last_crossing_time > min_period):
                    if abs(y_curr - y_prev) > 1e-6:
                        dt = t_curr - t_prev
                        frac = abs(0.0 - y_prev) / abs(y_curr - y_prev)
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
        cv2.rectangle(out, (rx1, ry1), (rx2, ry2), (0, 255, 255), 2)
        mid_y = ry1 + (ry2 - ry1) // 2
        cv2.line(out, (rx1, mid_y), (rx2, mid_y), (0, 140, 255), 2, cv2.LINE_AA)
        
        # Centerline Label with filled background tag
        tag_x, tag_y = rx1 + 10, mid_y - 8
        cv2.rectangle(out, (tag_x - 4, tag_y - 18), (tag_x + 240, tag_y + 6), (15, 20, 30), -1)
        cv2.putText(out, "CENTERLINE CROSSING PLANE", (tag_x, tag_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2, cv2.LINE_AA)

        # 2. Draw Detected Marker (Line vs Dot)
        if marker_detected:
            gx, gy = rx1 + mcx, ry1 + mcy
            if shape_type == "line" and line_pts:
                (p1x, p1y), (p2x, p2y) = line_pts
                gp1 = (rx1 + p1x, ry1 + p1y)
                gp2 = (rx1 + p2x, ry1 + p2y)
                # Draw thick high-contrast line stripe
                cv2.line(out, gp1, gp2, (0, 255, 0), 4, cv2.LINE_AA)
                cv2.circle(out, gp1, 6, (0, 220, 255), -1)
                cv2.circle(out, gp2, 6, (0, 220, 255), -1)
                cv2.circle(out, (gx, gy), 7, (0, 0, 255), -1)
                
                # Filled badge for line text
                label = f"LINE [L={int(line_len)}px, Tilt={line_tilt:+.1f} deg]"
                (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
                cv2.rectangle(out, (gx - lw // 2 - 6, gy - 32), (gx + lw // 2 + 6, gy - 6), (10, 25, 10), -1)
                cv2.rectangle(out, (gx - lw // 2 - 6, gy - 32), (gx + lw // 2 + 6, gy - 6), (0, 255, 0), 1)
                cv2.putText(out, label, (gx - lw // 2, gy - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 2, cv2.LINE_AA)
            else:
                # Dot / circle marker
                r = max(8, int(line_len / 2))
                cv2.circle(out, (gx, gy), r, (0, 255, 0), 3)
                cv2.circle(out, (gx, gy), 4, (0, 0, 255), -1)
                label = f"DOT [r={r}px, y={sample['marker_norm_y']:+.2f}]"
                cv2.rectangle(out, (gx + 12, gy - 16), (gx + 220, gy + 10), (10, 25, 10), -1)
                cv2.putText(out, label, (gx + 16, gy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

        # 3. Top Telemetry Glass Bar (Larger & Bolder)
        overlay = out.copy()
        cv2.rectangle(overlay, (0, 0), (w, 82), (8, 12, 22), -1)
        cv2.addWeighted(overlay, 0.85, out, 0.15, 0, out)

        status_color = (0, 255, 128) if self.is_active else ((0, 255, 255) if self.calibration_complete else (220, 220, 220))
        cv2.putText(out, f"OPENCAL AUTO-TUNER: {self.status_message}", (14, 28), cv2.FONT_HERSHEY_DUPLEX, 0.72, status_color, 2, cv2.LINE_AA)

        metrics_text = (
            f"TARGET: {self.target_rpm:.1f} RPM  |  "
            f"MEASURED: {self.measured_avg_rpm:.4f} RPM  |  "
            f"REV: {self.revolutions_completed}/{self.target_revolutions}  |  "
            f"CORR: {self.suggested_correction_factor:.6f}"
        )
        cv2.putText(out, metrics_text, (14, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

        # 4. Bottom Hardware & Wobble Status Bar (Larger & Bolder)
        bot_overlay = out.copy()
        cv2.rectangle(bot_overlay, (0, h - 46), (w, h), (8, 12, 22), -1)
        cv2.addWeighted(bot_overlay, 0.85, out, 0.15, 0, out)

        hw_text = (
            f"PI: {sample.get('cpu_temp_c', 0)}C @ {sample.get('core_voltage_v', 0)}V  |  "
            f"MOTOR: {sample.get('motor_vin_v', 0)}V  |  "
            f"RUNOUT: {sample.get('wobble_runout_px', 0)}px, TILT: {sample.get('line_tilt_deg', 0):+.1f} deg  |  "
            f"SHAPE: {shape_type.upper()}"
        )
        cv2.putText(out, hw_text, (14, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (180, 220, 255), 2, cv2.LINE_AA)

        # 5. Mini Realtime Trajectory Waveform (Bottom Right)
        if len(self.trajectory_history) >= 2:
            gw, gh = 200, 70
            gx1, gy1 = w - gw - 15, h - gh - 55
            cv2.rectangle(out, (gx1, gy1), (gx1 + gw, gy1 + gh), (15, 22, 35), -1)
            cv2.rectangle(out, (gx1, gy1), (gx1 + gw, gy1 + gh), (80, 120, 160), 1)
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
            cv2.putText(out, "Y-WAVEFORM", (gx1 + 8, gy1 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 210, 255), 1)

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
        self.state: str = "IDLE"  # "IDLE" | "ROTATING" | "PAUSED" | "COMPLETED" | "STOPPED"
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

                    # Pause between rotations for visual marker drift inspection
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
    """Rotates the vial slowly (at ~4.5 RPM) to locate and center the drawn marker line or dot (max 2 revolutions timeout)."""
    def __init__(self, hw: Any, calibrator: Any):
        self.hw = hw
        self.calibrator = calibrator
        self.is_active: bool = False
        self._stop_requested: bool = False
        self._thread: threading.Thread | None = None
        self.state: str = "IDLE"  # "IDLE" | "SEARCHING" | "FOUND_CENTERED" | "NOT_FOUND" | "STOPPED"
        self.status_message: str = "Idle (Ready to Find Marker)"

    def start(self, rpm: float = 4.5, max_revs: float = 2.0, direction: str = "CW") -> dict[str, Any]:
        self.stop()
        self.is_active = True
        self._stop_requested = False
        self.state = "SEARCHING"
        self.status_message = f"Searching for marker line/dot at {rpm} RPM (max {max_revs:.0f} turns)..."

        def _worker():
            stepper = getattr(self.hw, "stepper", None) if self.hw else None
            try:
                if stepper:
                    stepper.set_rpm(rpm)
                    if not stepper.is_running():
                        stepper.start_rotation(direction)

                # Maximum duration for max_revs revolutions plus safety margin
                max_duration = (max_revs * 60.0 / rpm) + 2.0
                t_start = time.time()
                marker_found = False

                while time.time() - t_start < max_duration and not self._stop_requested:
                    sample = getattr(self.calibrator, "latest_sample", {})
                    detected = sample.get("marker_detected", False)
                    norm_y = sample.get("marker_norm_y", 1.0)
                    
                    # When marker is detected and close to centerline (|y| <= 0.12)
                    if detected and abs(norm_y) <= 0.12:
                        # Stop stepper immediately to hold at center!
                        if stepper:
                            stepper.stop()
                        marker_found = True
                        self.state = "FOUND_CENTERED"
                        shape = sample.get("detected_shape", "marker")
                        self.status_message = f"🎯 Marker {shape.upper()} located & centered at y={norm_y:+.3f}!"
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
                        self.status_message = f"⚠️ Marker not detected after {max_revs:.0f} full revolutions. Check tape and marker line!"
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
