#!/usr/bin/env python3
import io
import json
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

from opencal.hardware.hardware_controller import HardwareController
from opencal.hardware.led_manager import BLUE, GREEN, OFF, RED, WHITE, YELLOW
from opencal.utils.config import Config

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

    <div class="grid">
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

        <!-- 7. EXPERIMENTAL PROJECTOR & AUDIO CONTROLS -->
        <div class="card">
            <div class="card-title">
                <span>🎬 Experimental Projector & Audio Player</span>
                <span style="font-size: 12px; color: var(--accent-purple);">HDMI Media</span>
            </div>
            
            <div class="slider-group" style="margin-bottom: 16px;">
                <label>Projector Speaker Volume:</label>
                <input type="range" id="proj-vol-slider" min="0" max="100" value="20" oninput="setProjectorVolume(this.value)">
                <span class="slider-val" id="proj-vol-val">20%</span>
            </div>

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

        // Print functions
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

    def log_message(self, format, *args):
        pass  # Suppress excessive HTTP access logs

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
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
                    }
                )
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
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

        # 7. SYSTEM CONTROLS
        if parsed.path == "/api/system/reboot":
            threading.Thread(target=lambda: (time.sleep(1), subprocess.run(["sudo", "reboot"])), daemon=True).start()
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
