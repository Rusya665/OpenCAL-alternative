#!/usr/bin/env python3
"""
OpenCAL Deep Telemetry Aggregator & Logger
Collects real-time metrics across Raspberry Pi OS, motor drivers (TMC2209/Tic), 
camera optics, and vision calibration engines.
"""

import os
import time
import subprocess
import threading
from pathlib import Path
from typing import Any


def _read_file_safe(path: str) -> str | None:
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return None


_telemetry_cache: dict[str, Any] | None = None
_last_telemetry_time: float = 0.0
_has_vcgencmd: bool | None = None


def get_pi_system_telemetry(force_fresh: bool = False) -> dict[str, Any]:
    """Query Raspberry Pi OS thermal, voltage, clock, throttle, and memory sensors (cached for 0.5s)."""
    global _telemetry_cache, _last_telemetry_time, _has_vcgencmd
    now = time.time()
    if not force_fresh and _telemetry_cache is not None and (now - _last_telemetry_time < 0.5):
        return dict(_telemetry_cache)

    if _has_vcgencmd is None:
        import shutil
        _has_vcgencmd = shutil.which("vcgencmd") is not None

    telemetry: dict[str, Any] = {
        "timestamp_unix": now,
        "cpu_temp_c": 42.0,
        "core_voltage_v": 1.20,
        "arm_clock_mhz": 2400.0,
        "cpu_usage_pct": 0.0,
        "ram_usage_pct": 0.0,
        "ram_used_mb": 0.0,
        "ram_total_mb": 0.0,
        "disk_free_gb": 0.0,
        "throttled_code": "0x0",
        "throttle_warnings": [],
        "uptime_s": 0.0,
    }

    # 1. CPU Temperature
    temp_raw = _read_file_safe("/sys/class/thermal/thermal_zone0/temp")
    if temp_raw and temp_raw.isdigit():
        telemetry["cpu_temp_c"] = round(int(temp_raw) / 1000.0, 1)
    elif _has_vcgencmd:
        try:
            res = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True, timeout=0.3)
            if res.returncode == 0 and "temp=" in res.stdout:
                val = res.stdout.strip().replace("temp=", "").replace("'C", "")
                telemetry["cpu_temp_c"] = float(val)
        except Exception:
            pass

    # 2. Core Voltage
    if _has_vcgencmd:
        try:
            res = subprocess.run(["vcgencmd", "measure_volts", "core"], capture_output=True, text=True, timeout=0.3)
            if res.returncode == 0 and "volt=" in res.stdout:
                val = res.stdout.strip().replace("volt=", "").replace("V", "")
                telemetry["core_voltage_v"] = float(val)
        except Exception:
            pass

    # 3. ARM Clock Speed
    if _has_vcgencmd:
        try:
            res = subprocess.run(["vcgencmd", "measure_clock", "arm"], capture_output=True, text=True, timeout=0.3)
            if res.returncode == 0 and "frequency(" in res.stdout:
                val = res.stdout.split("=")[-1].strip()
                telemetry["arm_clock_mhz"] = round(int(val) / 1_000_000.0, 1)
        except Exception:
            pass
    else:
        freq_raw = _read_file_safe("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
        if freq_raw and freq_raw.isdigit():
            telemetry["arm_clock_mhz"] = round(int(freq_raw) / 1000.0, 1)

    # 4. Throttling and Under-Voltage Detection
    if _has_vcgencmd:
        try:
            res = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=0.3)
            if res.returncode == 0 and "throttled=" in res.stdout:
                code_str = res.stdout.strip().split("=")[-1]
                telemetry["throttled_code"] = code_str
                code = int(code_str, 16)

                warnings = []
                if code & (1 << 0): warnings.append("CURRENT_UNDERVOLTAGE")
                if code & (1 << 1): warnings.append("CURRENT_ARM_FREQ_CAPPED")
                if code & (1 << 2): warnings.append("CURRENT_THROTTLED")
                if code & (1 << 3): warnings.append("CURRENT_SOFT_TEMP_LIMIT")
                if code & (1 << 16): warnings.append("PAST_UNDERVOLTAGE_OCCURRED")
                if code & (1 << 17): warnings.append("PAST_ARM_FREQ_CAPPED_OCCURRED")
                if code & (1 << 18): warnings.append("PAST_THROTTLED_OCCURRED")
                if code & (1 << 19): warnings.append("PAST_SOFT_TEMP_LIMIT_OCCURRED")
                telemetry["throttle_warnings"] = warnings
        except Exception:
            pass

    # 5. RAM & Memory Usage
    try:
        meminfo = _read_file_safe("/proc/meminfo")
        if meminfo:
            lines = meminfo.splitlines()
            mem_dict = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    k = parts[0].strip()
                    v = parts[1].strip().split()[0]
                    if v.isdigit():
                        mem_dict[k] = int(v)  # in kB
            total = mem_dict.get("MemTotal", 1)
            avail = mem_dict.get("MemAvailable", total)
            used = total - avail
            telemetry["ram_total_mb"] = round(total / 1024.0, 1)
            telemetry["ram_used_mb"] = round(used / 1024.0, 1)
            telemetry["ram_usage_pct"] = round((used / total) * 100.0, 1)
    except Exception:
        pass

    # 6. Disk Free Space
    try:
        stat = os.statvfs("/")
        telemetry["disk_free_gb"] = round((stat.f_bavail * stat.f_frsize) / (1024**3), 2)
    except Exception:
        pass

    # 7. OS Uptime
    uptime_raw = _read_file_safe("/proc/uptime")
    if uptime_raw:
        try:
            telemetry["uptime_s"] = round(float(uptime_raw.split()[0]), 1)
        except Exception:
            pass
    _telemetry_cache = dict(telemetry)
    _last_telemetry_time = now
    return telemetry


class TelemetrySessionLogger:
    """Thread-safe high-frequency telemetry recorder that writes to CSV & JSON logs."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or (Path.home() / "OpenCAL-alternative" / "telemetry_logs")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.samples: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.is_logging = False
        self.current_log_file: Path | None = None

    def start_session(self, prefix: str = "motor_cal") -> Path:
        with self._lock:
            self.samples.clear()
            self.is_logging = True
            ts = time.strftime("%Y%m%d_%H%M%S")
            self.current_log_file = self.output_dir / f"{prefix}_{ts}.csv"
            return self.current_log_file

    def record_sample(self, sample: dict[str, Any]):
        if not self.is_logging:
            return
        with self._lock:
            self.samples.append(sample)

    def stop_session(self) -> Path | None:
        with self._lock:
            if not self.is_logging:
                return None
            self.is_logging = False
            file_path = self.current_log_file
            if file_path and self.samples:
                self._flush_to_csv(file_path)
            return file_path

    def _flush_to_csv(self, path: Path):
        if not self.samples:
            return
        all_keys = []
        for s in self.samples:
            for k in s.keys():
                if k not in all_keys:
                    all_keys.append(k)

        with open(path, "w", encoding="utf-8") as f:
            f.write(",".join(all_keys) + "\n")
            for s in self.samples:
                row = []
                for k in all_keys:
                    val = s.get(k, "")
                    if isinstance(val, (list, dict)):
                        val = f'"{str(val).replace(chr(34), chr(39))}"'
                    row.append(str(val))
                f.write(",".join(row) + "\n")
        print(f"[Telemetry] CSV saved: {path} ({len(self.samples)} samples)")
