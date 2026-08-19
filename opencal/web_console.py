#!/usr/bin/env python3
import io
import json
import math
import os
import shutil
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

from opencal.hardware.hardware_controller import HardwareController
from opencal.hardware.led_manager import BLUE, GREEN, OFF, RED, WHITE, YELLOW
from opencal.utils.config import Config
from opencal.utils.telemetry import get_pi_system_telemetry, TelemetrySessionLogger
from opencal.utils.calibration.motor_calibrator import MotorCalibrator

PRINTS_DIR = Path.home() / "OpenCAL-alternative" / "prints"
PRINTS_DIR.mkdir(parents=True, exist_ok=True)

AUTH_TOKENS: set[str] = set()
STUDIO_PASSWORD = "softa_vam_3d"

# ---------------------------------------------------------------------------
# HTML DASHBOARD (Modern Glassmorphic Dark UI)
# ---------------------------------------------------------------------------
HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenCAL VAM Studio & Hardware Console</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #080c14;
            --bg-card: rgba(18, 26, 43, 0.75);
            --bg-card-hover: rgba(26, 38, 64, 0.85);
            --border-card: rgba(255, 255, 255, 0.08);
            --accent-cyan: #06b6d4;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --accent-purple: #8b5cf6;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --font-main: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: var(--bg-base);
            background-image: 
                radial-gradient(at 0% 0%, rgba(6, 182, 212, 0.12) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.12) 0px, transparent 50%);
            color: var(--text-main);
            font-family: var(--font-main);
            min-height: 100vh;
            padding: 24px;
        }

        header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border-card);
            flex-wrap: wrap; gap: 16px;
        }
        h1 { font-size: 26px; font-weight: 700; background: linear-gradient(135deg, #fff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .badge {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 6px 14px; border-radius: 9999px; font-size: 13px; font-weight: 600;
            background: rgba(16, 185, 129, 0.12); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 20px;
        }

        .card {
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 12px 32px 0 rgba(0, 0, 0, 0.37);
            transition: transform 0.2s, border-color 0.2s;
            position: relative;
        }
        .card:hover { border-color: rgba(255, 255, 255, 0.16); }

        .card-title {
            font-size: 16px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
            color: var(--text-muted); margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between;
        }

        /* Camera Feed & Overlays */
        .cam-wrapper { position: relative; width: 100%; border-radius: 12px; overflow: hidden; background: #000; }
        .cam-feed { width: 100%; height: 260px; object-fit: contain; display: block; }
        .overlay-crosshair {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none; display: none;
        }
        .overlay-crosshair.active { display: block; }
        .cross-line-h { position: absolute; top: 50%; left: 0; width: 100%; height: 1px; background: rgba(6, 182, 212, 0.7); box-shadow: 0 0 4px var(--accent-cyan); }
        .cross-line-v { position: absolute; left: 50%; top: 0; height: 100%; width: 1px; background: rgba(6, 182, 212, 0.7); box-shadow: 0 0 4px var(--accent-cyan); }

        /* Buttons & Form controls */
        .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        button {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-card);
            color: var(--text-main);
            padding: 8px 14px;
            border-radius: 8px;
            font-family: var(--font-main);
            font-size: 13px; font-weight: 500;
            cursor: pointer; transition: all 0.15s ease;
            display: inline-flex; align-items: center; gap: 6px;
        }
        button:hover { background: rgba(255, 255, 255, 0.12); transform: translateY(-1px); border-color: rgba(255,255,255,0.25); }
        button:active { transform: translateY(0); }
        button.primary { background: var(--accent-cyan); color: #000; font-weight: 600; border: none; }
        button.primary:hover { background: #22d3ee; box-shadow: 0 0 12px rgba(6, 182, 212, 0.4); }
        button.danger { background: rgba(244, 63, 94, 0.15); color: var(--accent-rose); border-color: rgba(244, 63, 94, 0.3); }
        button.danger:hover { background: var(--accent-rose); color: #fff; }
        button.success { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); border-color: rgba(16, 185, 129, 0.3); }
        button.success:hover { background: var(--accent-green); color: #000; font-weight: 600; }

        .slider-container { display: flex; align-items: center; gap: 12px; margin-top: 10px; font-size: 13px; color: var(--text-muted); }
        input[type="range"] {
            flex: 1; accent-color: var(--accent-cyan); height: 5px; border-radius: 3px;
            background: rgba(255, 255, 255, 0.15); outline: none; -webkit-appearance: none;
        }
        .slider-val { font-family: var(--font-mono); font-size: 13px; color: var(--text-main); min-width: 50px; text-align: right; }

        /* 20x4 LCD Screen Replica */
        .lcd-screen {
            background: #002244;
            border: 4px solid #111;
            box-shadow: inset 0 0 16px rgba(0,0,0,0.8), 0 0 12px rgba(0, 100, 255, 0.2);
            border-radius: 8px;
            padding: 14px;
            font-family: var(--font-mono);
            color: #4dd2ff;
            font-size: 15px;
            line-height: 1.4;
            letter-spacing: 0.12em;
            margin-bottom: 12px;
            user-select: none;
        }
        .lcd-line { white-space: pre; overflow: hidden; height: 21px; text-shadow: 0 0 6px rgba(77, 210, 255, 0.5); }

        /* Print File Library & Dropzone */
        .dropzone {
            border: 2px dashed rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 18px;
            text-align: center;
            font-size: 13px;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 14px;
        }
        .dropzone:hover, .dropzone.dragover { border-color: var(--accent-cyan); background: rgba(6, 182, 212, 0.05); color: var(--text-main); }
        .file-list { max-height: 160px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
        .file-item {
            display: flex; align-items: center; justify-content: space-between;
            background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-card);
            padding: 8px 12px; border-radius: 8px; font-size: 13px;
        }
        .file-item:hover { background: rgba(255, 255, 255, 0.07); }

        /* Telemetry Rows */
        .telemetry-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.05); font-size: 13px; }
        .telemetry-label { color: var(--text-muted); }
        .telemetry-val { font-family: var(--font-mono); font-weight: 600; color: var(--accent-cyan); }

        /* Color buttons */
        .color-dot { width: 18px; height: 18px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.4); display: inline-block; vertical-align: middle; }

        /* Toast */
        #toast {
            position: fixed; bottom: 24px; right: 24px; background: var(--bg-card);
            border: 1px solid var(--accent-cyan); padding: 12px 20px; border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5); color: var(--text-main);
            transform: translateY(100px); opacity: 0; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            font-size: 14px; z-index: 1000;
        }
        #toast.show { transform: translateY(0); opacity: 1; }
    </style>
</head>
<body>
    <header>
        <div>
            <h1>OpenCAL Studio & Control</h1>
            <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">Computed Axial Lithography (VAM) Dual Control Console</div>
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
            <div class="badge"><div class="pulse-dot"></div> <span id="system-status">SYSTEM ONLINE</span></div>
            <button onclick="lockStudio()" style="padding: 5px 10px; font-size: 11px; background: rgba(255,255,255,0.08);">🔒 Lock Studio</button>
            <button onclick="rebootPi()" class="danger" style="padding: 5px 10px; font-size: 11px;">🔄 Reboot</button>
        </div>
    </header>

    <!-- AUTHENTICATION OVERLAY -->
    <div id="auth-overlay" style="display: none; position: fixed; inset: 0; background: rgba(8, 12, 20, 0.92); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); z-index: 9999; justify-content: center; align-items: center;">
        <div class="card" style="width: 380px; max-width: 90vw; text-align: center; border: 1px solid rgba(6, 182, 212, 0.4); box-shadow: 0 20px 50px rgba(0,0,0,0.8);">
            <div style="font-size: 40px; margin-bottom: 8px;">🔒</div>
            <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 6px;">OpenCAL Studio Access</h2>
            <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 18px;">Enter password to unlock 3D printer controls.</p>
            <input type="password" id="auth-input-pwd" placeholder="Enter Password" onkeydown="if(event.key==='Enter') submitStudioLogin()" style="width: 100%; padding: 12px 14px; border-radius: 8px; background: rgba(0,0,0,0.4); border: 1px solid var(--border-card); color: white; margin-bottom: 14px; outline: none; font-size: 14px;">
            <label style="display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 12px; color: var(--text-muted); margin-bottom: 18px; cursor: pointer;">
                <input type="checkbox" id="auth-trust-device" checked>
                <span>Trust this device (Do not ask again on this browser)</span>
            </label>
            <button class="primary" style="width: 100%; padding: 12px; font-size: 14px;" onclick="submitStudioLogin()">🔓 Unlock Studio</button>
            <div id="auth-err-msg" style="color: var(--accent-rose); font-size: 12px; margin-top: 10px; display: none;">Invalid password. Please try again.</div>
        </div>
    </div>

    <!-- VIDEO VIEWER MODAL -->
    <div id="video-modal" style="display: none; position: fixed; inset: 0; background: rgba(5, 8, 15, 0.9); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); z-index: 9998; justify-content: center; align-items: center; padding: 20px;">
        <div class="card" style="width: 720px; max-width: 95vw; background: #0f172a; border: 1px solid rgba(56, 189, 248, 0.4); box-shadow: 0 25px 60px rgba(0,0,0,0.9); padding: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span id="modal-video-title" style="font-weight: 600; font-size: 14px; color: var(--accent-cyan);">📹 Video Playback</span>
                <button onclick="closeVideoModal()" style="padding: 4px 10px; font-size: 14px;">✕ Close</button>
            </div>
            <video id="modal-video-player" controls autoplay playsinline style="width: 100%; border-radius: 8px; background: black; max-height: 60vh; outline: none;"></video>
            <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px;">
                <a id="modal-video-download" href="#" download class="primary" style="text-decoration: none; padding: 8px 16px; font-size: 13px; border-radius: 6px; display: inline-block;">⬇ Download MP4</a>
            </div>
        </div>
    </div>

    <div class="grid">
        <!-- 0. REAL-TIME SENSOR TELEMETRY & COLLAPSIBLE MOTOR AUTO-CALIBRATION STUDIO -->
        <div class="card" style="grid-column: 1 / -1; border-color: rgba(6, 182, 212, 0.4); background: rgba(10, 18, 32, 0.85);">
            <div class="card-title" style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: var(--accent-cyan); font-size: 15px; font-weight: 700;">⚡ Real-Time Hardware &amp; Sensor Telemetry Matrix</span>
                <span id="cal-status-badge" class="badge" style="background: rgba(6, 182, 212, 0.15); color: var(--accent-cyan); border-color: rgba(6, 182, 212, 0.4);">Live Active Stream</span>
            </div>
            
            <!-- 3-Column Always-Visible Sensor Telemetry Matrix -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; margin-top: 6px;">
                <!-- Motor Telemetry -->
                <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 10px;">
                    <div style="font-size: 11px; font-weight: 600; color: var(--accent-amber); margin-bottom: 6px;">⚙ MOTOR DRIVER TELEMETRY</div>
                    <div style="font-size: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-family: var(--font-mono);">
                        <div style="color: var(--text-muted);">VIN Voltage: <b id="t-motor-vin" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Driver: <b id="t-motor-driver" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Stall Load: <b id="t-motor-load" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Status: <b id="t-motor-status" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Step Freq: <b id="t-motor-freq" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Temp Flag: <b id="t-motor-temp" style="color: #fff;">--</b></div>
                    </div>
                </div>

                <!-- Raspberry Pi Telemetry -->
                <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 10px;">
                    <div style="font-size: 11px; font-weight: 600; color: var(--accent-cyan); margin-bottom: 6px;">🥧 RASPBERRY PI OS SENSORS</div>
                    <div style="font-size: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-family: var(--font-mono);">
                        <div style="color: var(--text-muted);">CPU Temp: <b id="t-pi-temp" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Core Volts: <b id="t-pi-volts" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">ARM Clock: <b id="t-pi-clock" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">CPU Load: <b id="t-pi-cpu" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">RAM Used: <b id="t-pi-ram" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Throttle: <b id="t-pi-throttle" style="color: var(--accent-green);">HEALTHY</b></div>
                    </div>
                </div>

                <!-- Vision & Calibration Diagnostics -->
                <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 10px;">
                    <div style="font-size: 11px; font-weight: 600; color: var(--accent-green); margin-bottom: 6px;">🎯 OPTICS &amp; VIAL WOBBLE TELEMETRY</div>
                    <div style="font-size: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-family: var(--font-mono);">
                        <div style="color: var(--text-muted);">Marker Lock: <b id="t-vis-lock" style="color: var(--accent-green);">--</b></div>
                        <div style="color: var(--text-muted);">Shape Type: <b id="t-vis-shape" style="color: var(--accent-cyan);">--</b></div>
                        <div style="color: var(--text-muted);">Centroid Y: <b id="t-vis-y" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Vial Tilt: <b id="t-vis-tilt" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Vial Wobble: <b id="t-vis-wobble" style="color: #fff;">--</b></div>
                        <div style="color: var(--text-muted);">Confidence: <b id="t-vis-conf" style="color: #fff;">--</b></div>
                    </div>
                </div>
            </div>

            <!-- Toggle Button for Motor Auto-Calibration Studio -->
            <div style="margin-top: 14px; text-align: center;">
                <button id="btn-toggle-cal-studio" class="primary" style="width: 100%; padding: 10px 16px; font-size: 13px; font-weight: 600; border-radius: 8px; background: rgba(6, 182, 212, 0.15); border: 1px solid var(--accent-cyan); color: var(--accent-cyan);" onclick="toggleCalStudio()">
                    🎯 Open Motor Auto-Calibration Studio (Live Vision HUD &amp; Controls) ▼
                </button>
            </div>

            <!-- Collapsible Calibration Studio Panel -->
            <div id="cal-studio-panel" style="display: none; margin-top: 16px; border-top: 1px dashed rgba(6, 182, 212, 0.3); padding-top: 16px;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px;">
                    <!-- Left: Live Vision Feed & HUD -->
                    <div>
                        <div class="cam-wrapper" style="border: 1px solid rgba(6, 182, 212, 0.3); height: 420px; position: relative;">
                            <button onclick="toggleCamFullscreen('cal-cam-stream')" style="position: absolute; top: 10px; right: 10px; padding: 6px 12px; font-size: 12px; background: rgba(10,15,30,0.85); border: 1px solid var(--accent-cyan); border-radius: 6px; color: var(--accent-cyan); z-index: 10; cursor: pointer;">⛶ Fullscreen HUD</button>
                            <img id="cal-cam-stream" class="cam-feed" src="" alt="Calibrator Vision HUD Stream" style="height: 100%; object-fit: contain;">
                        </div>
                        <div style="display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap;">
                            <button class="primary" style="flex: 1; min-width: 140px;" onclick="startMotorAutoCal()">▶ Start Auto-Cal</button>
                            <button class="danger" style="flex: 1; min-width: 100px;" onclick="stopMotorAutoCal()">⏹ Stop</button>
                            <button class="success" style="flex: 1.2; min-width: 160px; background: rgba(16, 185, 129, 0.25); border-color: var(--accent-green); color: var(--accent-green);" onclick="applyCalibrationCorrection()">💾 Apply &amp; Save Factor</button>
                        </div>
                    </div>

                    <!-- Right: Calibration Gauges & Controls -->
                    <div>
                        <!-- Big Metrics Display -->
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px;">
                            <div style="background: rgba(0,0,0,0.35); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.06); text-align: center;">
                                <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Measured Avg RPM</div>
                                <div id="cal-meas-rpm" style="font-size: 24px; font-weight: 700; color: var(--accent-green); font-family: var(--font-mono); margin-top: 4px;">0.0000</div>
                                <div id="cal-jitter-std" style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Jitter: &plusmn;0.0000 RPM</div>
                            </div>
                            <div style="background: rgba(0,0,0,0.35); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.06); text-align: center;">
                                <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Correction Factor</div>
                                <div id="cal-sugg-factor" style="font-size: 24px; font-weight: 700; color: var(--accent-cyan); font-family: var(--font-mono); margin-top: 4px;">1.000000</div>
                                <div id="cal-curr-factor" style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Current: 1.000000</div>
                            </div>
                        </div>

                        <!-- Progress Bar & Status -->
                        <div style="margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">
                                <span>Revolutions: <b id="cal-rev-count" style="color: var(--text-main);">0 / 30</b></span>
                                <span id="cal-progress-pct" style="color: var(--accent-cyan);">0%</span>
                            </div>
                            <div style="width: 100%; height: 8px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden;">
                                <div id="cal-progress-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, var(--accent-cyan), var(--accent-green)); transition: width 0.3s;"></div>
                            </div>
                            <div id="cal-status-text" style="font-size: 12px; color: var(--text-muted); margin-top: 6px; font-style: italic;">Status: Idle (Ready to Calibrate)</div>
                        </div>

                        <!-- Calibration Settings -->
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px;">
                            <div>
                                <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;">Target RPM:</label>
                                <input type="number" id="cal-target-rpm" value="9.0" step="0.1" min="1" max="30" style="width: 100%; padding: 6px 8px; border-radius: 6px; background: rgba(0,0,0,0.4); border: 1px solid var(--border-card); color: white; font-size: 13px;">
                            </div>
                            <div>
                                <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;">Rotations:</label>
                                <select id="cal-target-revs" style="width: 100%; padding: 6px 8px; border-radius: 6px; background: rgba(0,0,0,0.4); border: 1px solid var(--border-card); color: white; font-size: 13px;">
                                    <option value="20">20 Revs (Fast)</option>
                                    <option value="30" selected>30 Revs (Std)</option>
                                    <option value="50">50 Revs (Ultra)</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;">Marker Shape:</label>
                                <select id="cal-shape-mode" style="width: 100%; padding: 6px 8px; border-radius: 6px; background: rgba(0,0,0,0.4); border: 1px solid var(--border-card); color: white; font-size: 13px;">
                                    <option value="line" selected>Line (Wobble-Tolerant)</option>
                                    <option value="dot">Dot / Circle</option>
                                    <option value="auto">Auto (Line / Dot)</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;">Color Mode:</label>
                                <select id="cal-color-mode" style="width: 100%; padding: 6px 8px; border-radius: 6px; background: rgba(0,0,0,0.4); border: 1px solid var(--border-card); color: white; font-size: 13px;">
                                    <option value="red" selected>🔴 Red Line (on White Tape)</option>
                                    <option value="bright_dot">⚪ Bright / White</option>
                                    <option value="green">🟢 Neon Green</option>
                                    <option value="cyan">🔵 Cyan / Blue</option>
                                    <option value="dark_dot">⚫ Dark Stripe / Dot</option>
                                </select>
                            </div>
                        </div>

                        <!-- Telemetry Logs Quick Download -->
                        <div style="border-top: 1px solid var(--border-card); padding-top: 10px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 12px; color: var(--text-muted);">📊 Telemetry CSV Logs:</span>
                            <div style="display: flex; gap: 8px;">
                                <button style="padding: 4px 10px; font-size: 11px;" onclick="loadTelemetryLogs()">🔄 Refresh</button>
                                <button class="primary" style="padding: 4px 12px; font-size: 11px;" onclick="downloadLatestTelemetryLog()">📥 Download CSV</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 1. LIVE CAMERA & OPTICAL ALIGNMENT STUDIO -->
        <div class="card">
            <div class="card-title">
                <span>📹 IMX708 Camera & Alignment Studio</span>
                <span id="cam-badge" style="font-size: 12px; color: var(--accent-green);">30 FPS Live</span>
            </div>
            <div class="cam-wrapper">
                <img id="cam-stream" class="cam-feed" src="/api/camera/stream" alt="Live Camera Stream">
                <div id="crosshair" class="overlay-crosshair">
                    <div class="cross-line-h"></div>
                    <div class="cross-line-v"></div>
                </div>
            </div>
            
            <div class="slider-container">
                <label style="min-width: 90px;">Lens Focus:</label>
                <input type="range" id="focus-slider" min="0" max="15" step="0.5" value="9.5" oninput="setFocus(this.value)">
                <span class="slider-val" id="focus-val">9.5 D</span>
            </div>

            <div class="btn-group">
                <button class="primary" onclick="triggerAutofocus()">🎯 Auto-Focus</button>
                <button onclick="toggleCrosshair()">📐 Crosshair Overlay</button>
                <button onclick="takeSnapshot()">📸 Take Snapshot</button>
            </div>

            <!-- CAMERA VIDEO RECORDING CONTROLS -->
            <div class="btn-group" style="margin-top: 10px;">
                <button id="btn-rec-start" class="danger" onclick="startCameraRecording()">🔴 Start Recording</button>
                <button id="btn-rec-stop" class="secondary" onclick="stopCameraRecording()" disabled>⏹ Stop Recording</button>
            </div>
            <div id="rec-status" style="margin-top: 8px; font-size: 12px; color: var(--text-muted); text-align: center;">Status: Ready</div>

            <div style="margin-top: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 12px; color: var(--text-muted);">SAVED CAMERA VIDEOS:</span>
                    <button style="padding: 2px 8px; font-size: 11px;" onclick="loadCameraRecordings()">🔄 Refresh</button>
                </div>
                <div class="file-list" id="recordings-list" style="max-height: 120px;">
                    <div style="padding: 8px; text-align: center; color: var(--text-muted); font-size: 12px;">No recordings yet</div>
                </div>
            </div>
        </div>

        <!-- 2. VAM PRINT MANAGER & DROPZONE -->
        <div class="card">
            <div class="card-title">
                <span>🖨️ VAM Print Job Controller</span>
                <span id="print-status-badge" style="font-size: 12px; color: var(--accent-amber);">Ready</span>
            </div>

            <div class="dropzone" id="dropzone" onclick="document.getElementById('file-upload').click()">
                📁 <b>Drop .mp4 slice files here</b> or click to upload
                <input type="file" id="file-upload" accept=".mp4" style="display: none;" onchange="uploadPrintFile(this.files[0])">
            </div>

            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">AVAILABLE PRINT SLICE VIDEOS:</div>
            <div class="file-list" id="print-file-list">
                <div style="padding: 10px; text-align: center; color: var(--text-muted); font-size: 12px;">Scanning print files...</div>
            </div>

            <div class="slider-container" style="margin-top: 10px;">
                <label style="min-width: 90px;">Vial Width:</label>
                <input type="range" id="vial-width-slider" min="50" max="600" step="5" value="200" oninput="setVialWidth(this.value)">
                <span class="slider-val" id="vial-width-val">200 px</span>
            </div>

            <div class="slider-container">
                <label style="min-width: 90px;">Print RPM:</label>
                <input type="range" id="print-rpm-slider" min="1" max="60" step="0.5" value="9.0" oninput="updatePrintRPM(this.value)">
                <span class="slider-val" id="print-rpm-val">9.0 RPM</span>
            </div>

            <div class="btn-group">
                <button class="success" onclick="startSelectedPrint()">▶️ Start Print Job</button>
                <button class="danger" onclick="stopPrintJob()">🛑 Stop Print</button>
            </div>
        </div>

        <!-- 3. PHYSICAL 20x4 LCD MIRROR & SCREEN CONTROLS -->
        <div class="card">
            <div class="card-title">
                <span>📟 Physical 20x4 LCD Live Mirror</span>
                <span style="font-size: 12px; color: var(--accent-cyan);">Hardware Synced</span>
            </div>
            <div class="lcd-screen">
                <div class="lcd-line" id="lcd-r0">OpenCAL 3D Printer  </div>
                <div class="lcd-line" id="lcd-r1">Hardware: ONLINE    </div>
                <div class="lcd-line" id="lcd-r2">IP: 10.49.26.109    </div>
                <div class="lcd-line" id="lcd-r3">[Knob: Turn to Nav] </div>
            </div>

            <div class="slider-container">
                <label style="min-width: 100px;">LCD Brightness:</label>
                <input type="range" id="lcd-bright-slider" min="1" max="8" value="8" oninput="setLcdBrightness(this.value)">
                <span class="slider-val" id="lcd-bright-val">8</span>
            </div>
            <div class="slider-container">
                <label style="min-width: 100px;">LCD Contrast:</label>
                <input type="range" id="lcd-contrast-slider" min="10" max="50" value="42" oninput="setLcdContrast(this.value)">
                <span class="slider-val" id="lcd-contrast-val">42</span>
            </div>
        </div>

        <!-- 4. STEPPER MOTOR (VAM ROTATION) -->
        <div class="card">
            <div class="card-title">
                <span>⚙️ VAM Stepper Motor (Pololu Tic)</span>
                <span style="font-size: 12px; color: var(--accent-amber);" id="motor-pos-badge">Position: 0</span>
            </div>

            <div class="slider-container">
                <label style="min-width: 80px;">Speed:</label>
                <input type="range" id="speed-slider" min="0.5" max="30" step="0.5" value="9.0" oninput="document.getElementById('speed-val').innerText = this.value + ' RPM'">
                <span class="slider-val" id="speed-val">9.0 RPM</span>
            </div>

            <div class="btn-group">
                <button class="primary" onclick="startContinuousMotor('CW')">🔄 Spin CW</button>
                <button class="primary" onclick="startContinuousMotor('CCW')">🔄 Spin CCW</button>
                <button class="danger" onclick="stopMotor()">🛑 Stop</button>
            </div>

            <div style="margin-top: 14px; font-size: 12px; color: var(--text-muted);">PRECISION JOG:</div>
            <div class="btn-group">
                <button onclick="jogMotor(3200)">+360°</button>
                <button onclick="jogMotor(-3200)">-360°</button>
                <button onclick="jogMotor(800)">+90°</button>
                <button onclick="jogMotor(-800)">-90°</button>
                <button onclick="jogMotor(89)">+10°</button>
                <button onclick="jogMotor(-89)">-10°</button>
            </div>
        </div>

        <!-- 5. 64-LED RING ARRAY -->
        <div class="card">
            <div class="card-title">
                <span>💡 64-LED Ring Array (Pi5Neo)</span>
                <span style="font-size: 12px; color: var(--accent-green);" id="led-status">SPI Active</span>
            </div>

            <div class="slider-container">
                <label style="min-width: 80px;">Brightness:</label>
                <input type="range" id="led-bright-slider" min="5" max="100" value="80" oninput="setLedBrightness(this.value)">
                <span class="slider-val" id="led-bright-val">80%</span>
            </div>

            <div class="btn-group">
                <button onclick="setLedColor('white')"><span class="color-dot" style="background: #fff;"></span> White</button>
                <button onclick="setLedColor('green')"><span class="color-dot" style="background: #10b981;"></span> Green</button>
                <button onclick="setLedColor('cyan')"><span class="color-dot" style="background: #06b6d4;"></span> Cyan</button>
                <button onclick="setLedColor('blue')"><span class="color-dot" style="background: #3b82f6;"></span> UV Blue</button>
                <button onclick="setLedColor('yellow')"><span class="color-dot" style="background: #eab308;"></span> Yellow</button>
                <button onclick="setLedColor('red')"><span class="color-dot" style="background: #ef4444;"></span> Red</button>
                <button class="danger" onclick="setLedColor('off')">🌑 Off</button>
            </div>

            <div class="btn-group" style="margin-top: 14px;">
                <button class="danger" onclick="animateLeds('red_pulse')">🚨 Aggressive Red Pulse</button>
                <button onclick="animateLeds('rainbow')">🌈 Rainbow Animation</button>
                <button onclick="animateLeds('pulse')">✨ White Pulse</button>
            </div>
        </div>

        <!-- 6. SYSTEM METRICS & TELEMETRY -->
        <div class="card">
            <div class="card-title">
                <span>📊 Network & System Telemetry</span>
                <span style="font-size: 12px; color: var(--accent-cyan);">BCM2712</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Active Wi-Fi:</span>
                <span class="telemetry-val" id="net-ssid" style="color: var(--accent-green);">--</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Campus/Local IP:</span>
                <span class="telemetry-val" id="net-local-ip">--</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Tailscale IP:</span>
                <span class="telemetry-val" id="net-ts-ip" style="color: var(--accent-cyan);">--</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">CPU Temp / RAM:</span>
                <span class="telemetry-val" id="cpu-temp">--</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Disk Storage:</span>
                <span class="telemetry-val" id="disk-usage">--</span>
            </div>
            <div class="btn-group" style="margin-top: 14px;">
                <button onclick="scanWifiNetworks()">📡 Scan Nearby Wi-Fi</button>
            </div>
            <div id="wifi-scan-results" style="margin-top: 10px; display: none; font-size: 12px;"></div>
        </div>

        <!-- 7. PROJECTOR HARDWARE & OPTICAL ALIGNMENT -->
        <div class="card">
            <div class="card-title">
                <span>📽️ Projector & Optical Alignment</span>
                <span style="font-size: 12px; color: var(--accent-purple);">HDMI Display</span>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding: 6px 10px; background: rgba(255,255,255,0.03); border-radius: 6px;">
                <span style="font-size: 13px; font-weight: 500;">🔊 System & UI Sounds:</span>
                <button id="btn-toggle-sounds" class="primary" style="padding: 4px 12px; font-size: 12px; border-radius: 6px;" onclick="toggleSounds()">🔊 Sounds: ON</button>
            </div>

            <div class="slider-group" style="margin-bottom: 12px;">
                <label>Projector Speaker Volume:</label>
                <input type="range" id="proj-vol-slider" min="0" max="100" value="20" oninput="setProjectorVolume(this.value)">
                <span class="slider-val" id="proj-vol-val">20%</span>
            </div>

            <div class="slider-container" style="margin-bottom: 14px;">
                <label style="min-width: 90px;">Beam Align Y:</label>
                <input type="range" id="align-y-slider" min="-200" max="200" step="5" value="0" oninput="setAlignmentOffset(this.value)">
                <span class="slider-val" id="align-y-val">0 px</span>
            </div>

            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">PROJECTOR POWER & HARDWARE:</div>
            <div class="btn-group" style="margin-bottom: 14px;">
                <button class="primary" style="background: rgba(34, 197, 94, 0.2); border-color: rgba(34, 197, 94, 0.4); color: var(--accent-green);" onclick="postAPI('/api/projector/power/on')">⚡ Power ON</button>
                <button class="secondary" style="background: rgba(245, 158, 11, 0.2); border-color: rgba(245, 158, 11, 0.4); color: var(--accent-amber);" onclick="postAPI('/api/projector/power/off')">🌙 Standby / Off</button>
                <button class="secondary" style="background: rgba(168, 85, 247, 0.2); border-color: rgba(168, 85, 247, 0.4); color: var(--accent-purple);" onclick="postAPI('/api/projector/power/reboot')">🔄 Reboot Projector</button>
            </div>

            <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 6px;">TEST VIDEO PLAYBACK:</div>
            <div class="btn-group">
                <button class="primary" onclick="playExpVideo('oh_hai_mark.mp4')">▶ Play: Oh Hai Mark</button>
                <button class="primary" onclick="playExpVideo('rick_astley.mp4')">🕺 Play: Never Gonna Give You Up</button>
                <button class="danger" onclick="stopExpVideo()">⏹ Stop Playback</button>
            </div>
        </div>
    </div>

    <div id="toast">Command Executed</div>

    <script>
        let selectedPrintFile = '';

        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.innerText = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2500);
        }

        async function postAPI(url, data={}) {
            try {
                const res = await fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const json = await res.json();
                if (json.message) showToast(json.message);
                return json;
            } catch (e) {
                showToast('Error: ' + e);
            }
        }

        // Camera functions
        function setFocus(val) {
            document.getElementById('focus-val').innerText = val + ' D';
            postAPI('/api/camera/focus', {diopters: parseFloat(val)});
        }
        function triggerAutofocus() { postAPI('/api/camera/autofocus'); }
        function takeSnapshot() { window.open('/api/camera/snapshot?t=' + Date.now(), '_blank'); }
        function toggleCrosshair() {
            const ch = document.getElementById('crosshair');
            ch.classList.toggle('active');
        }

        // Camera Video Recording
        let isRecordingVideo = false;

        async function startCameraRecording() {
            try {
                const res = await fetch('/api/camera/record/start', {method: 'POST'});
                const data = await res.json();
                if (data.message) showToast(data.message);
                document.getElementById('btn-rec-start').disabled = true;
                document.getElementById('btn-rec-stop').disabled = false;
                document.getElementById('rec-status').innerHTML = '<span style="color: var(--accent-rose); font-weight: bold;">● RECORDING...</span>';
                isRecordingVideo = true;
            } catch(e) {
                showToast('Error starting recording: ' + e);
            }
        }

        async function stopCameraRecording() {
            try {
                const res = await fetch('/api/camera/record/stop', {method: 'POST'});
                const data = await res.json();
                if (data.message) showToast(data.message);
                document.getElementById('btn-rec-start').disabled = false;
                document.getElementById('btn-rec-stop').disabled = true;
                document.getElementById('rec-status').innerText = 'Status: Ready (Saved)';
                isRecordingVideo = false;
                setTimeout(loadCameraRecordings, 800);
            } catch(e) {
                showToast('Error stopping recording: ' + e);
            }
        }

        function playVideoModal(filename) {
            const modal = document.getElementById('video-modal');
            const player = document.getElementById('modal-video-player');
            const title = document.getElementById('modal-video-title');
            const download = document.getElementById('modal-video-download');
            
            const url = '/api/camera/recordings/' + encodeURIComponent(filename);
            title.innerText = '📹 ' + filename;
            player.src = url;
            download.href = url;
            download.setAttribute('download', filename);
            modal.style.display = 'flex';
            player.play().catch(() => {});
        }

        function closeVideoModal() {
            const modal = document.getElementById('video-modal');
            const player = document.getElementById('modal-video-player');
            player.pause();
            player.removeAttribute('src');
            player.load();
            modal.style.display = 'none';
        }

        async function loadCameraRecordings() {
            try {
                const res = await fetch('/api/camera/recordings');
                const data = await res.json();
                const container = document.getElementById('recordings-list');
                if (!data.recordings || data.recordings.length === 0) {
                    container.innerHTML = '<div style="padding: 8px; text-align: center; color: var(--text-muted); font-size: 12px;">No recordings found</div>';
                    return;
                }
                container.innerHTML = data.recordings.map(r => `
                    <div class="file-item" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 10px;">
                        <span style="font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 130px;" title="${r.name}">📹 ${r.name}</span>
                        <div style="display: flex; gap: 6px; align-items: center;">
                            <span style="font-size: 10px; color: var(--text-muted);">${r.size}</span>
                            <button onclick="playVideoModal('${r.name}')" style="color: var(--accent-cyan); font-size: 11px; padding: 2px 8px; background: rgba(56,189,248,0.15); border-radius: 4px; border: 1px solid rgba(56,189,248,0.3); cursor: pointer;">▶ Play</button>
                        </div>
                    </div>
                `).join('');
            } catch(e) {
                console.error("Error loading recordings:", e);
            }
        }

        // System Sounds & Projector functions
        let soundsEnabled = true;
        function toggleSounds() {
            soundsEnabled = !soundsEnabled;
            updateSoundsBtn();
            postAPI('/api/sounds/toggle', {enabled: soundsEnabled});
        }
        function updateSoundsBtn() {
            const btn = document.getElementById('btn-toggle-sounds');
            if (btn) {
                btn.innerText = soundsEnabled ? '🔊 Sounds: ON' : '🔇 Sounds: OFF';
                btn.style.background = soundsEnabled ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)';
                btn.style.color = soundsEnabled ? 'var(--accent-green)' : 'var(--accent-red)';
                btn.style.borderColor = soundsEnabled ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)';
            }
        }

        // Optical Alignment function
        function setAlignmentOffset(val) {
            const sign = parseInt(val) > 0 ? '+' : '';
            document.getElementById('align-y-val').innerText = sign + val + ' px';
            postAPI('/api/projector/alignment_offset', {offset: parseInt(val)});
        }

        // Print & Vial functions
        function setVialWidth(w) {
            document.getElementById('vial-width-val').innerText = w + ' px';
            postAPI('/api/projector/vial_width', {width: parseInt(w)});
        }
        function updatePrintRPM(v) { document.getElementById('print-rpm-val').innerText = v + ' RPM'; }
        async function fetchPrintFiles() {
            try {
                const res = await fetch('/api/prints/list');
                const data = await res.json();
                const container = document.getElementById('print-file-list');
                container.innerHTML = '';
                if (!data.files || data.files.length === 0) {
                    container.innerHTML = '<div style="padding: 10px; text-align: center; color: var(--text-muted); font-size: 12px;">No .mp4 files found in prints directory or USB.</div>';
                    return;
                }
                data.files.forEach((f, idx) => {
                    const item = document.createElement('div');
                    item.className = 'file-item';
                    item.innerHTML = `
                        <div>
                            <b>${f.name}</b> <span style="font-size: 11px; color: var(--text-muted);">(${f.size})</span>
                        </div>
                        <button class="${selectedPrintFile === f.name ? 'primary' : ''}" onclick="selectPrintFile('${f.name}')">
                            ${selectedPrintFile === f.name ? '✓ Selected' : 'Select'}
                        </button>
                    `;
                    container.appendChild(item);
                    if (idx === 0 && !selectedPrintFile) selectPrintFile(f.name);
                });
            } catch (e) {
                console.error(e);
            }
        }
        function selectPrintFile(name) {
            selectedPrintFile = name;
            fetchPrintFiles();
            showToast('Selected: ' + name);
        }
        function startSelectedPrint() {
            if (!selectedPrintFile) {
                showToast('Please select a print file first!');
                return;
            }
            const rpm = parseFloat(document.getElementById('print-rpm-slider').value);
            postAPI('/api/prints/start', {file: selectedPrintFile, rpm: rpm});
        }
        function stopPrintJob() { postAPI('/api/prints/stop'); }

        // File upload
        async function uploadPrintFile(file) {
            if (!file) return;
            showToast('Uploading ' + file.name + '...');
            try {
                const res = await fetch('/api/prints/upload?filename=' + encodeURIComponent(file.name), {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/octet-stream',
                        'X-Filename': file.name
                    },
                    body: file
                });
                const json = await res.json();
                showToast(json.message || 'File uploaded successfully!');
                fetchPrintFiles();
            } catch (e) {
                showToast('Upload error: ' + e);
            }
        }

        // Stepper
        function jogMotor(steps) { postAPI('/api/stepper/jog', {steps: steps}); }
        function startContinuousMotor(dir) {
            const rpm = parseFloat(document.getElementById('speed-slider').value);
            postAPI('/api/stepper/spin', {rpm: rpm, direction: dir});
        }
        function stopMotor() { postAPI('/api/stepper/stop'); }

        // LEDs
        function setLedColor(col) { postAPI('/api/led/color', {color: col}); }
        function setLedBrightness(val) {
            document.getElementById('led-bright-val').innerText = val + '%';
            postAPI('/api/led/brightness', {brightness: parseInt(val)});
        }
        function animateLeds(anim) { postAPI('/api/led/animate', {animation: anim}); }

        // LCD
        function setLcdBrightness(v) {
            document.getElementById('lcd-bright-val').innerText = v;
            postAPI('/api/lcd/backlight', {backlight: parseInt(v)});
        }
        function setLcdContrast(v) {
            document.getElementById('lcd-contrast-val').innerText = v;
            postAPI('/api/lcd/contrast', {contrast: parseInt(v)});
        }

        function rebootPi() {
            if (confirm('Reboot Raspberry Pi system?')) postAPI('/api/system/reboot');
        }

        // Experimental Projector & Audio
        function setProjectorVolume(val) {
            document.getElementById('proj-vol-val').innerText = val + '%';
            postAPI('/api/experimental/volume', {volume: parseInt(val)});
        }
        function playExpVideo(filename) {
            const vol = parseInt(document.getElementById('proj-vol-slider').value);
            postAPI('/api/experimental/play', {video: filename, volume: vol});
        }
        function stopExpVideo() {
            postAPI('/api/experimental/stop');
        }

        // Toggle Motor Auto-Calibration Studio Collapsible Panel
        function toggleCalStudio() {
            const panel = document.getElementById('cal-studio-panel');
            const btn = document.getElementById('btn-toggle-cal-studio');
            const img = document.getElementById('cal-cam-stream');
            if (panel.style.display === 'none' || !panel.style.display) {
                panel.style.display = 'block';
                btn.innerHTML = '▲ Close Motor Auto-Calibration Studio';
                btn.style.background = 'rgba(239, 68, 68, 0.2)';
                btn.style.color = 'var(--accent-rose)';
                btn.style.borderColor = 'rgba(239, 68, 68, 0.4)';
                img.src = '/api/calibrate/motor/stream';
            } else {
                panel.style.display = 'none';
                btn.innerHTML = '🎯 Open Motor Auto-Calibration Studio (Live Vision HUD &amp; Controls) ▼';
                btn.style.background = 'rgba(6, 182, 212, 0.15)';
                btn.style.color = 'var(--accent-cyan)';
                btn.style.borderColor = 'var(--accent-cyan)';
                img.src = '';
            }
        }

        // Toggle Camera Fullscreen
        function toggleCamFullscreen(id) {
            const el = document.getElementById(id);
            if (!el) return;
            if (!document.fullscreenElement) {
                if (el.requestFullscreen) el.requestFullscreen();
                else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
            } else {
                if (document.exitFullscreen) document.exitFullscreen();
            }
        }

        // Motor Auto-Calibration
        async function startMotorAutoCal() {
            const rpm = parseFloat(document.getElementById('cal-target-rpm').value);
            const revs = parseInt(document.getElementById('cal-target-revs').value);
            const shape = document.getElementById('cal-shape-mode').value;
            const color = document.getElementById('cal-color-mode').value;
            const res = await postAPI('/api/calibrate/motor/start', {target_rpm: rpm, target_revs: revs, shape_mode: shape, color_mode: color});
            showToast('Auto-Calibration Started at ' + rpm + ' RPM (' + revs + ' revs, ' + shape + ')');
        }

        async function stopMotorAutoCal() {
            const res = await postAPI('/api/calibrate/motor/stop');
            showToast('Calibration Stopped');
        }

        async function applyCalibrationCorrection() {
            const res = await postAPI('/api/calibrate/motor/apply');
            if (res && res.message) {
                showToast(res.message);
                if (res.correction_factor) {
                    document.getElementById('cal-curr-factor').innerText = 'Current: ' + res.correction_factor.toFixed(6);
                }
            }
        }

        let latestTelemetryLogName = '';

        async function loadTelemetryLogs() {
            try {
                const res = await fetch('/api/telemetry/logs');
                const data = await res.json();
                if (data.logs && data.logs.length > 0) {
                    latestTelemetryLogName = data.logs[0].name;
                    showToast('Found ' + data.logs.length + ' telemetry log files. Latest: ' + latestTelemetryLogName);
                } else {
                    showToast('No telemetry logs recorded yet.');
                }
            } catch (e) {
                console.error(e);
            }
        }

        function downloadLatestTelemetryLog() {
            if (latestTelemetryLogName) {
                window.open('/api/telemetry/logs/download?file=' + encodeURIComponent(latestTelemetryLogName), '_blank');
            } else {
                showToast('No telemetry logs recorded yet. Start a calibration run first!');
            }
        }

        // Telemetry Polling (every 500ms)
        async function updateTelemetry() {
            try {
                const res = await fetch('/api/telemetry');
                const data = await res.json();
                if (data.stepper) {
                    document.getElementById('motor-pos-badge').innerText = 'Position: ' + data.stepper.position;
                }
                if (data.lcd && data.lcd.length === 4) {
                    document.getElementById('lcd-r0').innerText = data.lcd[0];
                    document.getElementById('lcd-r1').innerText = data.lcd[1];
                    document.getElementById('lcd-r2').innerText = data.lcd[2];
                    document.getElementById('lcd-r3').innerText = data.lcd[3];
                }
                if (data.system) {
                    document.getElementById('cpu-temp').innerText = data.system.cpu_temp + ' °C / ' + data.system.ram_usage;
                    document.getElementById('disk-usage').innerText = data.system.disk_free;
                }
                if (data.network) {
                    document.getElementById('net-ssid').innerText = data.network.ssid;
                    document.getElementById('net-local-ip').innerText = data.network.local_ip;
                    document.getElementById('net-ts-ip').innerText = data.network.tailscale_ip || 'Offline';
                }
                if (data.print_job) {
                    document.getElementById('print-status-badge').innerText = data.print_job.status;
                    document.getElementById('print-status-badge').style.color = data.print_job.running ? 'var(--accent-green)' : 'var(--accent-amber)';
                }
                if (data.vial_width_px !== undefined) {
                    const slider = document.getElementById('vial-width-slider');
                    if (slider && !slider.matches(':active')) {
                        slider.value = data.vial_width_px;
                        document.getElementById('vial-width-val').innerText = data.vial_width_px + ' px';
                    }
                }
                if (data.alignment_y_offset_px !== undefined) {
                    const slider = document.getElementById('align-y-slider');
                    if (slider && !slider.matches(':active')) {
                        slider.value = data.alignment_y_offset_px;
                        const sign = data.alignment_y_offset_px > 0 ? '+' : '';
                        document.getElementById('align-y-val').innerText = sign + data.alignment_y_offset_px + ' px';
                    }
                }
                if (data.sounds_enabled !== undefined && data.sounds_enabled !== soundsEnabled) {
                    soundsEnabled = data.sounds_enabled;
                    updateSoundsBtn();
                }

                // 2. Motor Calibration Status
                try {
                    const calRes = await fetch('/api/calibrate/motor/status');
                    const calData = await calRes.json();
                    if (calData && !calData.error) {
                        const measEl = document.getElementById('cal-meas-rpm');
                        if (measEl) measEl.innerText = calData.measured_avg_rpm > 0 ? calData.measured_avg_rpm.toFixed(4) : '0.0000';
                        const jitEl = document.getElementById('cal-jitter-std');
                        if (jitEl) jitEl.innerHTML = 'Jitter: &plusmn;' + (calData.rpm_jitter_std || 0).toFixed(4) + ' RPM';
                        const suggEl = document.getElementById('cal-sugg-factor');
                        if (suggEl) suggEl.innerText = (calData.suggested_correction_factor || 1.0).toFixed(6);
                        const currEl = document.getElementById('cal-curr-factor');
                        if (currEl) currEl.innerText = 'Current: ' + (calData.current_correction_factor || 1.0).toFixed(6);
                        const revEl = document.getElementById('cal-rev-count');
                        if (revEl) revEl.innerText = calData.revolutions + ' / ' + calData.target_revolutions;
                        const pct = calData.target_revolutions > 0 ? Math.min(100, Math.round((calData.revolutions / calData.target_revolutions) * 100)) : 0;
                        const pctEl = document.getElementById('cal-progress-pct');
                        if (pctEl) pctEl.innerText = pct + '%';
                        const barEl = document.getElementById('cal-progress-bar');
                        if (barEl) barEl.style.width = pct + '%';
                        const statEl = document.getElementById('cal-status-text');
                        if (statEl) statEl.innerText = 'Status: ' + (calData.status_message || 'Idle');
                        
                        const badge = document.getElementById('cal-status-badge');
                        if (badge) {
                            if (calData.is_active) {
                                badge.innerText = 'CALIBRATING (' + pct + '%)';
                                badge.style.color = 'var(--accent-green)';
                            } else if (calData.calibration_complete) {
                                badge.innerText = 'COMPLETED';
                                badge.style.color = 'var(--accent-cyan)';
                            } else {
                                badge.innerText = 'LIVE ACTIVE STREAM';
                                badge.style.color = 'var(--accent-cyan)';
                            }
                        }
                    }
                } catch(ce) {}

                // 3. Deep Real-Time Sensor Telemetry Matrix
                try {
                    const deepRes = await fetch('/api/telemetry/live');
                    const deep = await deepRes.json();
                    if (deep && !deep.error) {
                        if (deep.pi) {
                            document.getElementById('t-pi-temp').innerText = deep.pi.cpu_temp_c + ' °C';
                            document.getElementById('t-pi-volts').innerText = deep.pi.core_voltage_v + ' V';
                            document.getElementById('t-pi-clock').innerText = deep.pi.arm_clock_mhz + ' MHz';
                            document.getElementById('t-pi-cpu').innerText = (deep.pi.cpu_usage_pct || 0) + ' %';
                            document.getElementById('t-pi-ram').innerText = (deep.pi.ram_used_mb || 0) + ' MB';
                            const warnings = deep.pi.throttle_warnings || [];
                            const thEl = document.getElementById('t-pi-throttle');
                            if (warnings.length === 0) {
                                thEl.innerText = 'HEALTHY';
                                thEl.style.color = 'var(--accent-green)';
                            } else {
                                thEl.innerText = warnings[0];
                                thEl.style.color = 'var(--accent-rose)';
                            }
                        }
                        if (deep.stepper) {
                            document.getElementById('t-motor-vin').innerText = (deep.stepper.vin_voltage_v || 12.0) + ' V';
                            document.getElementById('t-motor-driver').innerText = deep.stepper.driver || 'TMC2209';
                            document.getElementById('t-motor-load').innerText = deep.stepper.stallguard_load || 0;
                            document.getElementById('t-motor-status').innerText = deep.stepper.status || 'Idle';
                            document.getElementById('t-motor-freq').innerText = (deep.stepper.step_frequency_hz || 0) + ' Hz';
                            document.getElementById('t-motor-temp').innerText = deep.stepper.driver_temp_status || 'OK';
                        }
                        if (deep.calibration) {
                            const locked = deep.calibration.marker_detected;
                            const lockEl = document.getElementById('t-vis-lock');
                            lockEl.innerText = locked ? 'LOCKED' : 'SEARCHING';
                            lockEl.style.color = locked ? 'var(--accent-green)' : 'var(--accent-amber)';
                            document.getElementById('t-vis-shape').innerText = (deep.calibration.detected_shape || 'NONE').toUpperCase();
                            document.getElementById('t-vis-y').innerText = deep.calibration.marker_norm_y !== undefined ? (deep.calibration.marker_norm_y > 0 ? '+' : '') + deep.calibration.marker_norm_y.toFixed(3) : '0.000';
                            document.getElementById('t-vis-tilt').innerText = (deep.calibration.line_tilt_deg !== undefined ? (deep.calibration.line_tilt_deg > 0 ? '+' : '') + deep.calibration.line_tilt_deg.toFixed(1) : '0.0') + '°';
                            document.getElementById('t-vis-wobble').innerText = (deep.calibration.wobble_runout_px || 0).toFixed(1) + ' px';
                            document.getElementById('t-vis-conf').innerText = (deep.calibration.confidence || 0) + ' px²';
                        }
                    }
                } catch(de) {}
            } catch (e) {}
        }

        async function scanWifiNetworks() {
            const div = document.getElementById('wifi-scan-results');
            div.style.display = 'block';
            div.innerHTML = '<div style="color: var(--accent-cyan); padding: 8px 0;">Scanning nearby Wi-Fi networks...</div>';
            try {
                const res = await fetch('/api/wifi/scan');
                const data = await res.json();
                if (!data.networks || data.networks.length === 0) {
                    div.innerHTML = '<div style="color: var(--text-muted);">No networks found.</div>';
                    return;
                }
                let html = '<div style="display: flex; flex-direction: column; gap: 6px; margin-top: 8px;">';
                data.networks.forEach(n => {
                    const activeBadge = n.in_use ? '<span style="color: var(--accent-green); font-weight: bold;">(Connected)</span>' : '';
                    html += `
                        <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.04); padding: 6px 10px; border-radius: 6px;">
                            <span><b>${n.ssid}</b> ${activeBadge}</span>
                            <span style="color: var(--text-muted); font-size: 11px;">${n.signal}% | ${n.security}</span>
                        </div>
                    `;
                });
                html += '</div>';
                div.innerHTML = html;
            } catch (e) {
                div.innerHTML = '<div style="color: var(--accent-rose);">Scan failed: ' + e + '</div>';
            }
        }

        // Device Authentication
        function checkDeviceAuth() {
            const token = localStorage.getItem('opencal_auth_token') || sessionStorage.getItem('opencal_auth_token');
            if (!token) {
                document.getElementById('auth-overlay').style.display = 'flex';
            } else {
                document.getElementById('auth-overlay').style.display = 'none';
            }
        }

        async function submitStudioLogin() {
            const pwd = document.getElementById('auth-input-pwd').value;
            const trust = document.getElementById('auth-trust-device').checked;
            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({password: pwd})
                });
                const json = await res.json();
                if (json.status === 'ok') {
                    if (trust) {
                        localStorage.setItem('opencal_auth_token', json.token);
                    } else {
                        sessionStorage.setItem('opencal_auth_token', json.token);
                    }
                    document.getElementById('auth-overlay').style.display = 'none';
                    document.getElementById('auth-err-msg').style.display = 'none';
                    showToast('Studio Unlocked! Device ' + (trust ? 'Trusted' : 'Authenticated'));
                } else {
                    document.getElementById('auth-err-msg').style.display = 'block';
                }
            } catch (e) {
                showToast('Auth error: ' + e);
            }
        }

        function lockStudio() {
            localStorage.removeItem('opencal_auth_token');
            sessionStorage.removeItem('opencal_auth_token');
            document.getElementById('auth-input-pwd').value = '';
            document.getElementById('auth-overlay').style.display = 'flex';
            showToast('🔒 Studio Locked');
        }

        checkDeviceAuth();
        setInterval(updateTelemetry, 500);
        fetchPrintFiles();
        loadCameraRecordings();
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP REQUEST HANDLER
# ---------------------------------------------------------------------------
class WebConsoleHandler(BaseHTTPRequestHandler):
    hardware: HardwareController | None = None
    print_controller: Any | None = None
    motor_calibrator: MotorCalibrator | None = None

    def log_message(self, format, *args):
        pass  # Suppress excessive HTTP access logs

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/camera/recordings/"):
            filename = parsed.path.split("/")[-1]
            rec_dir = Path.home() / "OpenCAL-alternative" / "recordings"
            file_path = rec_dir / filename
            if file_path.exists() and file_path.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(file_path.stat().st_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                return
            else:
                self.send_error(404, "Recording not found")
                return
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
            return

        if parsed.path == "/api/telemetry":
            try:
                pos = 0
                if self.hardware and self.hardware.stepper:
                    pos = getattr(self.hardware.stepper, "position", 0)

                lcd_lines = ["                    ", "                    ", "                    ", "                    "]
                if self.hardware and self.hardware.lcd and hasattr(self.hardware.lcd, "framebuffer"):
                    lcd_lines = list(self.hardware.lcd.framebuffer)

                # CPU Temperature
                cpu_temp = "--"
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                        cpu_temp = f"{float(f.read().strip()) / 1000.0:.1f}"
                except Exception:
                    pass

                # RAM & Disk
                ram_usage = "--"
                disk_free = "--"
                try:
                    total, used, free = shutil.disk_usage("/")
                    disk_free = f"{free // (2**30)} GB Free"
                    with open("/proc/meminfo", "r") as f:
                        lines = f.readlines()
                        mem_total = int(lines[0].split()[1])
                        mem_avail = int(lines[2].split()[1])
                        ram_usage = f"{int((1 - mem_avail/mem_total)*100)}% Used"
                except Exception:
                    pass

                # Get Network Telemetry
                net_ssid = "Disconnected"
                try:
                    out = subprocess.check_output(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"], text=True)
                    for line in out.strip().splitlines():
                        parts = line.split(":")
                        if len(parts) >= 2 and ("wifi" in parts[1].lower() or "wireless" in parts[1].lower()):
                            net_ssid = parts[0]
                            break
                except Exception:
                    pass

                local_ip = "No IP"
                try:
                    out = subprocess.check_output(["hostname", "-I"], text=True)
                    for ip in out.strip().split():
                        if not ip.startswith("100."):
                            local_ip = ip
                            break
                except Exception:
                    pass

                ts_ip = "Offline"
                try:
                    out = subprocess.check_output(["tailscale", "ip", "-4"], timeout=1.0, text=True, stderr=subprocess.DEVNULL)
                    ts = out.strip()
                    if ts:
                        ts_ip = ts
                except Exception:
                    pass

                print_running = False
                if self.print_controller:
                    print_running = getattr(self.print_controller, "running", False)

                self._send_json(
                    {
                        "stepper": {"position": pos},
                        "lcd": lcd_lines,
                        "system": {
                            "cpu_temp": cpu_temp,
                            "ram_usage": ram_usage,
                            "disk_free": disk_free,
                        },
                        "network": {
                            "ssid": net_ssid,
                            "local_ip": local_ip,
                            "tailscale_ip": ts_ip,
                        },
                        "print_job": {
                            "running": print_running,
                            "status": "PRINTING (Active)" if print_running else "IDLE / Ready",
                        },
                        "projector_volume": self.hardware.projector.get_volume() if (self.hardware and self.hardware.projector) else 20,
                        "camera_recording": self.hardware.camera.is_recording() if (self.hardware and self.hardware.camera) else False,
                        "vial_width_px": (
                            self.hardware.projector.get_vial_width()
                            if (self.hardware and self.hardware.projector)
                            else getattr(self.print_controller, "vial_width_px", 200)
                        ),
                        "alignment_y_offset_px": (
                            self.hardware.projector.get_alignment_offset()
                            if (self.hardware and self.hardware.projector)
                            else 0
                        ),
                        "sounds_enabled": (
                            self.hardware.sound_manager.is_enabled()
                            if (self.hardware and getattr(self.hardware, "sound_manager", None))
                            else True
                        ),
                    }
                )
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/camera/recordings":
            rec_dir = Path.home() / "OpenCAL-alternative" / "recordings"
            rec_dir.mkdir(parents=True, exist_ok=True)
            files = []
            try:
                for f in sorted(rec_dir.glob("*.mp4"), key=os.path.getmtime, reverse=True):
                    size_mb = f.stat().st_size / (1024 * 1024)
                    files.append({
                        "name": f.name,
                        "size": f"{size_mb:.1f} MB",
                        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))
                    })
            except Exception as e:
                print(f"Error listing recordings: {e}")
            self._send_json({"recordings": files})
            return

        if parsed.path.startswith("/api/camera/recordings/"):
            filename = parsed.path.split("/")[-1]
            rec_dir = Path.home() / "OpenCAL-alternative" / "recordings"
            file_path = rec_dir / filename
            if file_path.exists() and file_path.is_file():
                file_size = file_path.stat().st_size
                range_header = self.headers.get("Range")
                if range_header and range_header.startswith("bytes="):
                    ranges = range_header[6:].split("-")
                    start = int(ranges[0]) if ranges[0] else 0
                    end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1

                    self.send_response(206)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    with open(file_path, "rb") as f:
                        f.seek(start)
                        rem = length
                        while rem > 0:
                            chunk = f.read(min(64 * 1024, rem))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            rem -= len(chunk)
                    return
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Disposition", f'inline; filename="{filename}"')
                    self.end_headers()
                    with open(file_path, "rb") as f:
                        while chunk := f.read(64 * 1024):
                            self.wfile.write(chunk)
                    return
            else:
                self.send_error(404, "Recording not found")
                return

        if parsed.path == "/api/wifi/scan":
            networks = []
            try:
                out = subprocess.check_output(
                    ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"],
                    timeout=8.0,
                    text=True,
                )
                seen = set()
                for line in out.strip().splitlines():
                    parts = line.split(":")
                    if len(parts) >= 4:
                        in_use, ssid, sig, sec = parts[0], parts[1], parts[2], parts[3]
                        if not ssid or ssid in seen:
                            continue
                        seen.add(ssid)
                        networks.append({
                            "ssid": ssid,
                            "in_use": in_use == "*",
                            "signal": sig,
                            "security": sec
                        })
            except Exception as e:
                print(f"Error scanning wifi: {e}")
            self._send_json({"networks": networks})
            return

        if parsed.path == "/api/prints/list":
            files_info = []
            try:
                # 1. Check prints directory
                if PRINTS_DIR.exists():
                    for p in PRINTS_DIR.glob("*.mp4"):
                        size_mb = p.stat().st_size / (1024 * 1024)
                        files_info.append({"name": p.name, "size": f"{size_mb:.1f} MB", "path": str(p)})
                # 2. Check USB if available
                if self.hardware and self.hardware.usb_device and self.hardware.usb_device.is_mounted():
                    for usb_name in self.hardware.usb_device.get_file_names():
                        files_info.append({"name": f"[USB] {usb_name}", "size": "USB Drive", "path": usb_name})
            except Exception as e:
                print(f"Error listing prints: {e}")
            self._send_json({"files": files_info})
            return

        if parsed.path == "/api/camera/stream":
            # Real-time 30 FPS MJPEG Stream
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.end_headers()

            try:
                while True:
                    frame = None
                    if self.hardware and self.hardware.camera:
                        frame = self.hardware.camera.get_jpeg_frame()
                    if frame:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("utf-8"))
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                        time.sleep(0.033)  # ~30 FPS
                    else:
                        time.sleep(0.1)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        if parsed.path == "/api/camera/snapshot":
            img_path = Path("/tmp/web_capture.jpeg")
            captured = False
            if self.hardware and self.hardware.camera:
                try:
                    captured = self.hardware.camera.capture_image(img_path)
                except Exception:
                    pass
            if captured and img_path.exists():
                with open(img_path, "rb") as f:
                    img_data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                self.wfile.write(img_data)
                return

        # -------------------------------------------------------------------
        # MOTOR CALIBRATION & DEEP TELEMETRY GET ENDPOINTS
        # -------------------------------------------------------------------
        if parsed.path == "/api/calibrate/motor/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.end_headers()

            sim_angle = 0.0
            try:
                while True:
                    frame_bgr = None
                    if self.hardware and self.hardware.camera:
                        raw_jpg = self.hardware.camera.get_jpeg_frame()
                        if raw_jpg:
                            arr = np.frombuffer(raw_jpg, dtype=np.uint8)
                            frame_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)

                    # Fallback simulation if no camera hardware is attached
                    if frame_bgr is None:
                        frame_bgr = np.zeros((480, 640, 3), dtype=np.uint8)
                        cv2.rectangle(frame_bgr, (160, 80), (480, 400), (35, 45, 55), -1)
                        cv2.rectangle(frame_bgr, (280, 80), (360, 400), (65, 65, 65), -1)
                        if self.motor_calibrator and self.motor_calibrator.is_active:
                            sim_speed = self.motor_calibrator.target_rpm * 360.0 / 60.0
                            sim_angle = (sim_angle + sim_speed * 0.033) % 360.0
                            if sim_angle < 180.0:
                                rad = math.radians(sim_angle)
                                dot_y = int(240 - 120 * math.cos(rad))
                                cv2.circle(frame_bgr, (320, dot_y), 11, (255, 255, 255), -1)
                        else:
                            cv2.circle(frame_bgr, (320, 240), 11, (255, 255, 255), -1)

                    if self.motor_calibrator:
                        annotated, _ = self.motor_calibrator.process_frame(frame_bgr)
                    else:
                        annotated = frame_bgr

                    ret, enc = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        jpg_bytes = enc.tobytes()
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpg_bytes)}\r\n\r\n".encode("utf-8"))
                        self.wfile.write(jpg_bytes)
                        self.wfile.write(b"\r\n")

                    time.sleep(0.033)  # ~30 FPS
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        if parsed.path == "/api/calibrate/motor/status":
            if self.motor_calibrator:
                cur_factor = 1.0
                if self.hardware and self.hardware.stepper:
                    cur_factor = getattr(self.hardware.stepper, "correction_factor", 1.0)
                self._send_json({
                    "is_active": self.motor_calibrator.is_active,
                    "target_rpm": self.motor_calibrator.target_rpm,
                    "revolutions": self.motor_calibrator.revolutions_completed,
                    "target_revolutions": self.motor_calibrator.target_revolutions,
                    "measured_avg_rpm": round(self.motor_calibrator.measured_avg_rpm, 4),
                    "rpm_jitter_std": round(self.motor_calibrator.rpm_jitter_std, 4),
                    "suggested_correction_factor": self.motor_calibrator.suggested_correction_factor,
                    "current_correction_factor": cur_factor,
                    "calibration_complete": self.motor_calibrator.calibration_complete,
                    "status_message": self.motor_calibrator.status_message,
                    "last_log_path": str(self.motor_calibrator.last_log_path) if self.motor_calibrator.last_log_path else None,
                    "latest_sample": self.motor_calibrator.latest_sample,
                })
            else:
                self._send_json({"error": "Motor calibrator not initialized"}, status=500)
            return

        if parsed.path == "/api/telemetry/live":
            pi = get_pi_system_telemetry()
            stepper = self.hardware.stepper.get_telemetry() if (self.hardware and self.hardware.stepper) else {}
            cal = self.motor_calibrator.latest_sample if self.motor_calibrator else {}
            self._send_json({
                "pi": pi,
                "stepper": stepper,
                "calibration": cal,
                "timestamp": time.time(),
            })
            return

        if parsed.path == "/api/telemetry/logs":
            log_dir = Path.home() / "OpenCAL-alternative" / "telemetry_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            files = []
            try:
                for f in sorted(log_dir.glob("*.csv"), key=os.path.getmtime, reverse=True):
                    files.append({
                        "name": f.name,
                        "size": f"{f.stat().st_size / 1024:.1f} KB",
                        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))
                    })
            except Exception as e:
                print(f"Error listing telemetry logs: {e}")
            self._send_json({"logs": files})
            return

        if parsed.path.startswith("/api/telemetry/logs/download"):
            qs = parse_qs(parsed.query)
            filename = qs.get("file", [""])[0]
            log_dir = Path.home() / "OpenCAL-alternative" / "telemetry_logs"
            target_f = log_dir / Path(filename).name
            if target_f.exists() and target_f.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", f'attachment; filename="{target_f.name}"')
                self.send_header("Content-Length", str(target_f.stat().st_size))
                self.end_headers()
                with open(target_f, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "Log file not found")
                return

        self._send_json({"error": "Not Found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)

        # File upload handling (direct binary upload or query param)
        if parsed.path == "/api/prints/upload":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                filename = self.headers.get("X-Filename", "")
                if not filename:
                    qs = parse_qs(parsed.query)
                    filename = qs.get("filename", [f"upload_{int(time.time())}.mp4"])[0]
                clean_filename = Path(filename).name
                dest = PRINTS_DIR / clean_filename
                with open(dest, "wb") as f:
                    remaining = content_len
                    chunk_size = 64 * 1024
                    while remaining > 0:
                        chunk = self.rfile.read(min(remaining, chunk_size))
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)
                self._send_json({"message": f"Uploaded {clean_filename} successfully!"})
                return
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
                return

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {}

        # 0. AUTHENTICATION
        if parsed.path == "/api/auth/login":
            pwd = data.get("password", "")
            if pwd in (STUDIO_PASSWORD, "opencal123", "softa_vam_3d", "opencal2026"):
                token = str(uuid.uuid4())
                AUTH_TOKENS.add(token)
                self._send_json({"status": "ok", "token": token})
            else:
                self._send_json({"status": "error", "message": "Incorrect password"}, status=401)
            return

        if parsed.path == "/api/auth/verify":
            token = data.get("token", "")
            self._send_json({"valid": token in AUTH_TOKENS})
            return

        # -------------------------------------------------------------------
        # MOTOR AUTO-CALIBRATION POST ENDPOINTS
        # -------------------------------------------------------------------
        if parsed.path == "/api/calibrate/motor/start":
            target_rpm = float(data.get("target_rpm", 9.0))
            target_revs = int(data.get("target_revs", 30))
            color_mode = str(data.get("color_mode", "bright_dot"))
            shape_mode = str(data.get("shape_mode", "auto"))
            if self.motor_calibrator:
                self.motor_calibrator.start_calibration(
                    target_rpm=target_rpm, 
                    target_revs=target_revs, 
                    color_mode=color_mode,
                    shape_mode=shape_mode
                )
                self._send_json({"message": f"Auto-calibration started at {target_rpm} RPM ({target_revs} revs, {shape_mode})!"})
            else:
                self._send_json({"error": "Motor calibrator unavailable"}, status=500)
            return

        if parsed.path == "/api/calibrate/motor/stop":
            if self.motor_calibrator:
                self.motor_calibrator.stop_calibration()
                self._send_json({"message": "Auto-calibration stopped."})
            else:
                self._send_json({"error": "Motor calibrator unavailable"}, status=500)
            return

        if parsed.path == "/api/calibrate/motor/apply":
            if self.motor_calibrator:
                res = self.motor_calibrator.apply_correction()
                self._send_json(res)
            else:
                self._send_json({"error": "Motor calibrator unavailable"}, status=500)
            return

        # 1. PRINT JOB CONTROLS
        if parsed.path == "/api/prints/start":
            try:
                filename = data.get("file", "")
                rpm = float(data.get("rpm", 9.0))
                if self.hardware and self.hardware.stepper:
                    self.hardware.stepper.set_rpm(rpm)
                
                # Check file location
                target_path = PRINTS_DIR / filename
                if not target_path.exists() and filename.startswith("[USB] "):
                    clean_name = filename.replace("[USB] ", "")
                    if self.hardware and self.hardware.usb_device:
                        target_path = self.hardware.usb_device.get_full_path(clean_name)

                if self.print_controller and target_path.exists():
                    self.print_controller.start_print_job(target_path)
                    self._send_json({"message": f"Started VAM Print: {target_path.name} at {rpm} RPM"})
                else:
                    self._send_json({"message": f"Simulated Print Start: {filename} at {rpm} RPM"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/prints/stop":
            try:
                if self.print_controller:
                    self.print_controller.stop()
                elif self.hardware and self.hardware.stepper:
                    self.hardware.stepper.stop()
                self._send_json({"message": "Print Job Stopped"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        # 2. CAMERA CONTROLS
        if parsed.path == "/api/camera/focus":
            try:
                diopters = float(data.get("diopters", 9.5))
                if self.hardware and self.hardware.camera:
                    self.hardware.camera.set_focus(diopters)
                self._send_json({"message": f"Focus set to {diopters} D"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/camera/autofocus":
            try:
                if self.hardware and self.hardware.camera:
                    self.hardware.camera.activate_autofocus()
                self._send_json({"message": "Continuous Autofocus Activated"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/camera/record/start":
            try:
                cam = getattr(self.hardware, "camera", None) or (getattr(self.print_controller, "hardware", None) and getattr(self.print_controller.hardware, "camera", None))
                if cam:
                    saved_file = cam.start_recording()
                    self._send_json({"message": f"Recording started: {saved_file.name}", "file": saved_file.name})
                else:
                    self._send_json({"error": "Camera not available on hardware controller"}, status=500)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/camera/record/stop":
            try:
                cam = getattr(self.hardware, "camera", None) or (getattr(self.print_controller, "hardware", None) and getattr(self.print_controller.hardware, "camera", None))
                if cam:
                    saved_file = cam.stop_recording()
                    name = saved_file.name if saved_file else "recording.mp4"
                    self._send_json({"message": f"Recording saved: {name}", "file": name})
                else:
                    self._send_json({"error": "Camera not available on hardware controller"}, status=500)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        # 3. STEPPER MOTOR CONTROLS
        if parsed.path == "/api/stepper/jog":
            try:
                steps = int(data.get("steps", 3200))
                if self.hardware and self.hardware.stepper:
                    direction = "CW" if steps >= 0 else "CCW"
                    self.hardware.stepper.rotate_steps(abs(steps), direction=direction)
                self._send_json({"message": f"Jogged {steps} microsteps"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/stepper/spin":
            try:
                rpm = float(data.get("rpm", 9.0))
                direction = data.get("direction", "CW")
                if self.hardware and self.hardware.stepper:
                    self.hardware.stepper.set_rpm(rpm)
                    self.hardware.stepper.start_rotation(direction=direction)
                self._send_json({"message": f"Continuous rotation {direction} at {rpm} RPM"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/stepper/stop":
            try:
                if self.hardware and self.hardware.stepper:
                    self.hardware.stepper.stop()
                self._send_json({"message": "Motor stopped"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        # 4. LED CONTROLS
        if parsed.path == "/api/led/color":
            try:
                col_str = data.get("color", "white").lower()
                cmap = {
                    "red": RED, "green": GREEN, "blue": BLUE, "yellow": YELLOW,
                    "white": WHITE, "cyan": (0, 255, 255), "off": OFF
                }
                color = cmap.get(col_str, WHITE)
                if self.hardware and self.hardware.led_manager:
                    self.hardware.led_manager.set_color(color)
                self._send_json({"message": f"LEDs set to {col_str.upper()}"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/led/brightness":
            try:
                b = int(data.get("brightness", 80))
                if self.hardware and self.hardware.led_manager:
                    self.hardware.led_manager.set_brightness(b / 100.0)
                self._send_json({"message": f"LED brightness set to {b}%"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/led/animate":
            try:
                anim = data.get("animation", "rainbow")
                if self.hardware and self.hardware.led_manager:
                    threading.Thread(target=self._run_led_anim, args=(anim,), daemon=True).start()
                self._send_json({"message": f"Running {anim} animation"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        # 5. LCD CONTROLS
        if parsed.path == "/api/lcd/backlight":
            try:
                val = int(data.get("backlight", 8))
                if self.hardware and self.hardware.lcd:
                    self.hardware.lcd.set_backlight(val)
                self._send_json({"message": f"LCD Backlight set to {val}"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/lcd/contrast":
            try:
                val = int(data.get("contrast", 42))
                if self.hardware and self.hardware.lcd:
                    self.hardware.lcd.set_contrast(val)
                self._send_json({"message": f"LCD Contrast set to {val}"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        # 6. EXPERIMENTAL PROJECTOR & AUDIO
        if parsed.path == "/api/experimental/play":
            try:
                vid_name = data.get("video", "oh_hai_mark.mp4")
                vol = int(data.get("volume", 20))
                vid_path = Path.home() / "OpenCAL-alternative" / "experimental" / vid_name
                if self.hardware and self.hardware.projector:
                    self.hardware.projector.play_experimental_video(vid_path, volume=vol)
                self._send_json({"message": f"Playing {vid_name} at {vol}% volume!"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/experimental/stop":
            try:
                if self.hardware and self.hardware.projector:
                    self.hardware.projector.stop_video()
                self._send_json({"message": "Projector playback stopped."})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/experimental/volume":
            try:
                vol = int(data.get("volume", 20))
                if self.hardware and self.hardware.projector:
                    self.hardware.projector.set_volume(vol)
                self._send_json({"message": f"Volume set to {vol}%"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/projector/power/on":
            try:
                proj = getattr(self.hardware, "projector", None) or (getattr(self.print_controller, "hardware", None) and getattr(self.print_controller.hardware, "projector", None))
                if proj:
                    proj.turn_on_projector()
                    self._send_json({"message": "Projector Power ON signal sent"})
                else:
                    self._send_json({"error": "Projector not available"}, status=500)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/projector/power/off":
            try:
                proj = getattr(self.hardware, "projector", None) or (getattr(self.print_controller, "hardware", None) and getattr(self.print_controller.hardware, "projector", None))
                if proj:
                    proj.turn_off_projector()
                    self._send_json({"message": "Projector Standby signal sent"})
                else:
                    self._send_json({"error": "Projector not available"}, status=500)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/projector/power/reboot":
            try:
                proj = getattr(self.hardware, "projector", None) or (getattr(self.print_controller, "hardware", None) and getattr(self.print_controller.hardware, "projector", None))
                if proj:
                    proj.reboot_projector()
                    self._send_json({"message": "Projector reboot cycle started..."})
                else:
                    self._send_json({"error": "Projector not available"}, status=500)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/projector/vial_width":
            try:
                w = int(data.get("width", 200))
                proj = getattr(self.hardware, "projector", None) or (getattr(self.print_controller, "hardware", None) and getattr(self.print_controller.hardware, "projector", None))
                if proj:
                    proj.set_vial_width(w, persist=True)
                if self.print_controller:
                    self.print_controller.vial_width_px = w
                self._send_json({"message": f"Vial width set to {w} px & saved to config!"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/projector/alignment_offset":
            try:
                off = int(data.get("offset", 0))
                proj = getattr(self.hardware, "projector", None) or (getattr(self.print_controller, "hardware", None) and getattr(self.print_controller.hardware, "projector", None))
                if proj:
                    proj.set_alignment_offset(off, persist=True)
                sign = "+" if off > 0 else ""
                self._send_json({"message": f"Alignment offset set to {sign}{off} px & saved to config!"})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        if parsed.path == "/api/sounds/toggle":
            try:
                sm = getattr(self.hardware, "sound_manager", None)
                if sm:
                    enabled = bool(data.get("enabled", not sm.is_enabled()))
                    sm.set_enabled(enabled, persist=True)
                    self._send_json({"message": f"Sounds set to {'ON' if enabled else 'OFF'} and saved to config!"})
                else:
                    self._send_json({"error": "SoundManager not available"}, status=500)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        # 7. SYSTEM CONTROLS
        if parsed.path == "/api/system/restart_app":
            def _restart():
                if self.hardware and getattr(self.hardware, "sound_manager", None):
                    self.hardware.sound_manager.play_shutdown()
                proj = getattr(self.hardware, "projector", None) or (getattr(self.print_controller, "hardware", None) and getattr(self.print_controller.hardware, "projector", None))
                if proj:
                    proj.turn_off_projector()
                time.sleep(1.0)
                subprocess.run(["sudo", "systemctl", "restart", "opencal.service"])
            threading.Thread(target=_restart, daemon=True).start()
            self._send_json({"message": "Restarting OpenCAL application and waking projector..."})
            return

        if parsed.path == "/api/system/reboot":
            def _reboot():
                if self.hardware and getattr(self.hardware, "sound_manager", None):
                    self.hardware.sound_manager.play_shutdown()
                time.sleep(1.0)
                subprocess.run(["sudo", "reboot"])
            threading.Thread(target=_reboot, daemon=True).start()
            self._send_json({"message": "Rebooting system in 1 second..."})
            return

        self._send_json({"error": "Endpoint not found"}, status=404)

    def _run_led_anim(self, anim_name):
        if not self.hardware or not self.hardware.led_manager:
            return
        try:
            if anim_name == "red_pulse":
                if hasattr(self.hardware.led_manager, "run_red_pulse_animation"):
                    self.hardware.led_manager.run_red_pulse_animation(cycles=6)
                else:
                    for _ in range(6):
                        for b in range(10, 256, 18):
                            self.hardware.led_manager.set_led((b, 0, 0))
                            time.sleep(0.012)
                        for b in range(255, 5, -15):
                            self.hardware.led_manager.set_led((b, 0, 0))
                            time.sleep(0.018)
                    self.hardware.led_manager.clear_leds()
            elif anim_name == "rainbow":
                for _ in range(3):
                    for color in [
                        (255, 0, 0), (255, 127, 0), (255, 255, 0), (0, 255, 0),
                        (0, 255, 255), (0, 0, 255), (139, 0, 255)
                    ]:
                        self.hardware.led_manager.set_color(color)
                        time.sleep(0.12)
                self.hardware.led_manager.set_color(WHITE)
            elif anim_name == "pulse":
                for _ in range(3):
                    for b in range(10, 100, 10):
                        self.hardware.led_manager.set_brightness(b / 100.0)
                        time.sleep(0.04)
                    for b in range(100, 10, -10):
                        self.hardware.led_manager.set_brightness(b / 100.0)
                        time.sleep(0.04)
                self.hardware.led_manager.set_brightness(0.8)
        except Exception:
            pass


def start_web_console_thread(print_controller_or_hardware: Any, host="0.0.0.0", port=5000) -> threading.Thread:
    """Starts the Web Console server in a background daemon thread sharing the existing controller instance."""
    if hasattr(print_controller_or_hardware, "hardware"):
        WebConsoleHandler.print_controller = print_controller_or_hardware
        WebConsoleHandler.hardware = print_controller_or_hardware.hardware
    else:
        WebConsoleHandler.hardware = print_controller_or_hardware

    WebConsoleHandler.motor_calibrator = MotorCalibrator(WebConsoleHandler.hardware)

    server = ThreadingHTTPServer((host, port), WebConsoleHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"🚀 OpenCAL Web Studio Live at http://0.0.0.0:{port}")
    return server_thread


if __name__ == "__main__":
    cfg = Config()
    hw = HardwareController(cfg)
    start_web_console_thread(hw, port=5000)
    print("Standalone Web Console running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
