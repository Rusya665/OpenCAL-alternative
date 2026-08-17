#!/usr/bin/env python3
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from opencal.utils.config import Config
from opencal.hardware.hardware_controller import HardwareController
from opencal.hardware.led_manager import RED, GREEN, BLUE, YELLOW, WHITE, OFF

# OpenCAL Interactive Documentation & Control Pages for Rotary Knob
OPENCAL_PAGES = [
    {
        "title": "SYSTEM DASHBOARD",
        "lines": [
            "OpenCAL 3D Printer  ",
            "Hardware: ONLINE    ",
            "IP: 10.49.26.109    ",
            "[Knob: Turn to Nav] "
        ],
        "action": "refresh",
        "action_desc": "Refreshed Status"
    },
    {
        "title": "STEPPER MOTOR JOG",
        "lines": [
            "== VAM ROTATION ==  ",
            "Target: 9.0 RPM     ",
            "1/16 Microstepping  ",
            "[Press: 360 Spin]   "
        ],
        "action": "jog_motor_360",
        "action_desc": "Jogged 360 Degrees"
    },
    {
        "title": "64-LED RING CONTROL",
        "lines": [
            "== 64-LED RING ==   ",
            "Pattern: Rainbow Arc",
            "Brightness: 100%    ",
            "[Press: LED Rainbow]"
        ],
        "action": "run_rainbow",
        "action_desc": "Rainbow Animation"
    },
    {
        "title": "CAMERA IMX708 FOCUS",
        "lines": [
            "== CAMERA IMX708 == ",
            "Sony 12MP Autofocus ",
            "Stream: 30 FPS Live ",
            "[Press: Auto-Focus] "
        ],
        "action": "trigger_autofocus",
        "action_desc": "Triggered Autofocus"
    },
    {
        "title": "VAM PRINT PROCESS",
        "lines": [
            "== VAM PRINTING ==  ",
            "Computed Axial Litho",
            "Vial Rotation Ready ",
            "[Press: Start Print]"
        ],
        "action": "start_print_demo",
        "action_desc": "VAM Print Demo Started"
    },
    {
        "title": "ABOUT OPENCAL",
        "lines": [
            "OpenCAL 2026 Build  ",
            "VAM Volumetric Print",
            "Univ of Turku Lab   ",
            "[Knob: Turn to Nav] "
        ],
        "action": "refresh",
        "action_desc": "About OpenCAL"
    }
]

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenCAL Hardware Control Suite</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-card: rgba(20, 27, 45, 0.85);
            --border-card: rgba(64, 93, 150, 0.3);
            --accent-cyan: #00f0ff;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --lcd-bg: #001a33;
            --lcd-text: #55eeff;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
        body { background: var(--bg-primary); color: var(--text-main); min-height: 100vh; padding: 24px; }
        
        header {
            display: flex; justify-content: space-between; align-items: center;
            max-width: 1300px; margin: 0 auto 24px; padding-bottom: 16px;
            border-bottom: 1px solid var(--border-card);
        }
        h1 { font-size: 26px; font-weight: 700; background: linear-gradient(135deg, #00f0ff, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .badge { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.3); display: flex; align-items: center; gap: 6px; }
        .pulse-dot { width: 8px; height: 8px; background: var(--accent-green); border-radius: 50%; box-shadow: 0 0 8px var(--accent-green); }

        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 24px; max-width: 1300px; margin: 0 auto; }
        
        .card {
            background: var(--bg-card); border: 1px solid var(--border-card);
            border-radius: 16px; padding: 22px; backdrop-filter: blur(12px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3); transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .card:hover { border-color: rgba(0, 240, 255, 0.4); transform: translateY(-2px); }
        .card-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; color: var(--text-main); }
        
        /* LCD Component */
        .lcd-screen {
            background: var(--lcd-bg); border: 3px solid #000d1a; border-radius: 8px;
            padding: 14px 18px; font-family: 'JetBrains Mono', monospace; font-size: 17px;
            color: var(--lcd-text); letter-spacing: 2px; line-height: 1.5;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.9), 0 0 15px rgba(0, 240, 255, 0.2);
            margin-bottom: 16px;
        }
        .lcd-line { white-space: pre; min-height: 26px; }
        
        .form-group { margin-bottom: 12px; }
        label { display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 6px; }
        input[type="text"], input[type="number"] {
            width: 100%; padding: 10px 14px; background: rgba(10, 14, 23, 0.8);
            border: 1px solid var(--border-card); border-radius: 8px;
            color: var(--text-main); font-family: 'JetBrains Mono', monospace; font-size: 14px;
        }
        input:focus { outline: none; border-color: var(--accent-cyan); }
        
        .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        button {
            padding: 10px 16px; background: rgba(59, 130, 246, 0.2);
            border: 1px solid rgba(59, 130, 246, 0.4); border-radius: 8px;
            color: var(--text-main); font-weight: 600; font-size: 13px;
            cursor: pointer; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 6px;
        }
        button:hover { background: rgba(59, 130, 246, 0.4); border-color: var(--accent-blue); }
        button.primary { background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan)); border: none; color: #000; font-weight: 700; }
        button.primary:hover { opacity: 0.9; box-shadow: 0 0 12px rgba(0, 240, 255, 0.4); }
        button.danger { background: rgba(244, 63, 94, 0.2); border-color: rgba(244, 63, 94, 0.4); color: #fda4af; }
        button.danger:hover { background: rgba(244, 63, 94, 0.4); }
        button.success { background: rgba(16, 185, 129, 0.2); border-color: rgba(16, 185, 129, 0.4); color: #6ee7b7; }
        button.success:hover { background: rgba(16, 185, 129, 0.4); }

        /* Sliders */
        .slider-container { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
        input[type="range"] { flex: 1; accent-color: var(--accent-cyan); }
        .slider-val { font-family: 'JetBrains Mono', monospace; font-size: 14px; min-width: 45px; color: var(--accent-cyan); }

        /* Camera Stream */
        .cam-feed {
            width: 100%; height: 260px; background: #000; border-radius: 8px;
            border: 1px solid var(--border-card); object-fit: cover; margin-bottom: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }

        /* Telemetry Pill */
        .telemetry-row { display: flex; justify-content: space-between; padding: 8px 12px; background: rgba(10, 14, 23, 0.5); border-radius: 6px; margin-bottom: 6px; font-size: 13px; }
        .telemetry-label { color: var(--text-muted); }
        .telemetry-val { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: var(--accent-cyan); }

        /* Toast notification */
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
            <h1>OpenCAL Hardware Suite</h1>
            <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">Computed Axial Lithography (VAM) Controller</div>
        </div>
        <div class="badge"><div class="pulse-dot"></div> <span id="system-status">SYSTEM ONLINE</span></div>
    </header>

    <div class="grid">
        <!-- 1. LIVE 30 FPS CAMERA FEED (IMX708) -->
        <div class="card" style="grid-column: span 1;">
            <div class="card-title">
                <span>📹 Live Camera Stream (30 FPS)</span>
                <span id="cam-badge" style="font-size: 12px; color: var(--accent-green);">Sony IMX708 Active</span>
            </div>
            <img id="cam-stream" class="cam-feed" src="/api/camera/stream" alt="Live Camera Stream">
            
            <div class="slider-container">
                <label style="margin: 0;">Lens Focus:</label>
                <input type="range" id="focus-slider" min="0" max="15" step="0.5" value="9.5" oninput="setFocus(this.value)">
                <span class="slider-val" id="focus-val">9.5 D</span>
            </div>

            <div class="btn-group" style="margin-top: 14px;">
                <button class="primary" onclick="triggerAutofocus()">🎯 Auto-Focus</button>
                <button onclick="toggleStream()">⏯️ Toggle Stream</button>
                <button onclick="takeSnapshot()">📸 Full Snapshot</button>
            </div>
        </div>

        <!-- 2. LCD DISPLAY & PHYSICAL ROTARY KNOB PAGER -->
        <div class="card" style="grid-column: span 1;">
            <div class="card-title">
                <span>📟 20x4 LCD Mirror & Rotary Pager</span>
                <span id="pager-badge" style="font-size: 12px; color: var(--accent-cyan);">Page 1/6</span>
            </div>
            <div class="lcd-screen">
                <div class="lcd-line" id="lcd-r0">OpenCAL 3D Printer  </div>
                <div class="lcd-line" id="lcd-r1">Hardware: ONLINE    </div>
                <div class="lcd-line" id="lcd-r2">IP: 10.49.26.109    </div>
                <div class="lcd-line" id="lcd-r3">[Knob: Turn to Nav] </div>
            </div>

            <div class="btn-group" style="margin-bottom: 12px;">
                <button onclick="prevDocPage()">◀️ Prev Doc Page</button>
                <button onclick="nextDocPage()">▶️ Next Doc Page</button>
                <button class="primary" onclick="executeKnobAction()">🔘 Press Knob Action</button>
            </div>

            <div class="form-group">
                <label>Custom Text to Row 0:</label>
                <div style="display: flex; gap: 8px;">
                    <input type="text" id="lcd-custom-text" placeholder="Type custom message..." maxlength="20">
                    <button class="primary" onclick="sendCustomLCD()">Send</button>
                </div>
            </div>
        </div>

        <!-- 3. STEPPER MOTOR (VAM ROTATION) -->
        <div class="card">
            <div class="card-title">
                <span>⚙️ VAM Stepper Motor (Pololu Tic T249)</span>
                <span style="font-size: 12px; color: var(--accent-amber);" id="motor-status">Driver OK</span>
            </div>
            
            <div class="telemetry-row">
                <span class="telemetry-label">Current Position:</span>
                <span class="telemetry-val" id="motor-pos">0 steps</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Driver Error Status:</span>
                <span class="telemetry-val" id="driver-err" style="color: var(--accent-green);">0x0000 (Clear)</span>
            </div>

            <div class="slider-container" style="margin: 14px 0;">
                <label style="margin: 0;">Velocity:</label>
                <input type="range" id="speed-slider" min="1" max="20" step="0.5" value="9" oninput="document.getElementById('speed-val').innerText = this.value + ' RPM'">
                <span class="slider-val" id="speed-val">9.0 RPM</span>
            </div>

            <div class="btn-group">
                <button onclick="jogMotor(-3200)">⏪ -1 Rev (3200 steps)</button>
                <button onclick="jogMotor(3200)">⏩ +1 Rev (3200 steps)</button>
                <button class="success" onclick="startContinuousMotor()">🔄 Continuous Spin</button>
                <button class="danger" onclick="stopMotor()">🛑 Emergency Stop</button>
            </div>
        </div>

        <!-- 4. 64-LED RING ILLUMINATION -->
        <div class="card">
            <div class="card-title">
                <span>💡 64-LED Ring Illumination</span>
                <span style="font-size: 12px; color: var(--accent-cyan);">Pi5Neo GRB</span>
            </div>

            <div class="slider-container" style="margin-bottom: 14px;">
                <label style="margin: 0;">Brightness:</label>
                <input type="range" id="led-bright-slider" min="5" max="100" value="80" oninput="setBrightness(this.value)">
                <span class="slider-val" id="led-bright-val">80%</span>
            </div>

            <label>Quick Colors & Patterns:</label>
            <div class="btn-group">
                <button style="background: rgba(255,255,255,0.2); border-color: #fff;" onclick="setLedColor('white')">⚪ White</button>
                <button style="background: rgba(0,240,255,0.2); border-color: #00f0ff;" onclick="setLedColor('cyan')">🌐 Cyan</button>
                <button style="background: rgba(59,130,246,0.2); border-color: #3b82f6;" onclick="setLedColor('blue')">🔵 Blue</button>
                <button style="background: rgba(16,185,129,0.2); border-color: #10b981;" onclick="setLedColor('green')">🟢 Green</button>
                <button style="background: rgba(244,63,94,0.2); border-color: #f43f5e;" onclick="setLedColor('red')">🔴 Red</button>
                <button style="background: rgba(245,158,11,0.2); border-color: #f59e0b;" onclick="setLedColor('yellow')">🟡 Yellow</button>
            </div>
            <div class="btn-group" style="margin-top: 8px;">
                <button class="primary" onclick="runLedAnimation('rainbow')">🌈 Rainbow Cycle</button>
                <button onclick="runLedAnimation('pulse')">✨ Pulse Effect</button>
                <button class="danger" onclick="setLedColor('off')">🌑 Turn Off</button>
            </div>
        </div>

        <!-- 5. ROTARY KNOB & SYSTEM TELEMETRY -->
        <div class="card">
            <div class="card-title">
                <span>🎛️ Rotary Encoder & System Telemetry</span>
            </div>
            
            <div class="telemetry-row">
                <span class="telemetry-label">Encoder Step Count:</span>
                <span class="telemetry-val" id="rotary-steps">0</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Knob Push Button:</span>
                <span class="telemetry-val" id="rotary-btn">RELEASED</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Active Documentation Page:</span>
                <span class="telemetry-val" id="active-doc-title">SYSTEM DASHBOARD</span>
            </div>
            <div class="telemetry-row">
                <span class="telemetry-label">Current Page Action:</span>
                <span class="telemetry-val" id="active-doc-action" style="color: var(--accent-amber);">Refreshed Status</span>
            </div>
        </div>
    </div>

    <div id="toast">Command Executed</div>

    <script>
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
        function toggleStream() {
            const img = document.getElementById('cam-stream');
            if (img.src.includes('stream')) {
                img.src = '/api/camera/placeholder';
                showToast('Stream Paused');
            } else {
                img.src = '/api/camera/stream?t=' + Date.now();
                showToast('Live Stream Resumed');
            }
        }

        // LCD & Pager functions
        function prevDocPage() { postAPI('/api/pager/prev'); }
        function nextDocPage() { postAPI('/api/pager/next'); }
        function executeKnobAction() { postAPI('/api/pager/action'); }
        function sendCustomLCD() {
            const text = document.getElementById('lcd-custom-text').value;
            if (text) postAPI('/api/lcd/write', {row: 0, text: text});
        }

        // Stepper Motor
        function jogMotor(steps) { postAPI('/api/stepper/jog', {steps: steps}); }
        function startContinuousMotor() {
            const rpm = parseFloat(document.getElementById('speed-slider').value);
            postAPI('/api/stepper/spin', {rpm: rpm});
        }
        function stopMotor() { postAPI('/api/stepper/stop'); }

        // LED
        function setLedColor(c) { postAPI('/api/led/color', {color: c}); }
        function setBrightness(b) {
            document.getElementById('led-bright-val').innerText = b + '%';
            postAPI('/api/led/brightness', {brightness: parseInt(b)});
        }
        function runLedAnimation(anim) { postAPI('/api/led/animate', {animation: anim}); }

        // Poller for Real-time telemetry
        setInterval(async () => {
            try {
                const res = await fetch('/api/telemetry');
                if (res.ok) {
                    const data = await res.json();
                    if (data.lcd) {
                        document.getElementById('lcd-r0').innerText = data.lcd[0] || '';
                        document.getElementById('lcd-r1').innerText = data.lcd[1] || '';
                        document.getElementById('lcd-r2').innerText = data.lcd[2] || '';
                        document.getElementById('lcd-r3').innerText = data.lcd[3] || '';
                    }
                    if (data.pager) {
                        document.getElementById('pager-badge').innerText = `Page ${data.pager.index + 1}/${data.pager.total}`;
                        document.getElementById('active-doc-title').innerText = data.pager.title;
                        document.getElementById('active-doc-action').innerText = data.pager.action_desc;
                    }
                    if (data.rotary) {
                        document.getElementById('rotary-steps').innerText = data.rotary.steps;
                        document.getElementById('rotary-btn').innerText = data.rotary.button ? 'PRESSED' : 'RELEASED';
                        document.getElementById('rotary-btn').style.color = data.rotary.button ? 'var(--accent-green)' : 'var(--accent-cyan)';
                    }
                    if (data.stepper) {
                        document.getElementById('motor-pos').innerText = data.stepper.position + ' steps';
                    }
                }
            } catch (e) {}
        }, 300);
    </script>
</body>
</html>
"""


class WebConsoleHandler(BaseHTTPRequestHandler):
    hardware: HardwareController = None
    current_doc_page = 0

    def log_message(self, format, *args):
        pass  # Suppress default noisy logs

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
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
            return

        if parsed.path == "/api/telemetry":
            steps = 0
            btn_active = False
            if self.hardware and self.hardware.rotary:
                try:
                    steps = self.hardware.rotary.get_steps()
                    btn_active = self.hardware.rotary.was_button_pressed()
                except Exception:
                    pass

            pos = 0
            if self.hardware and self.hardware.stepper and hasattr(self.hardware.stepper, "tic") and self.hardware.stepper.tic:
                try:
                    pos = self.hardware.stepper.tic.get_current_position()
                except Exception:
                    pass

            page = OPENCAL_PAGES[WebConsoleHandler.current_doc_page]
            lcd_lines = getattr(self.hardware.lcd, "framebuffer", page["lines"]) if self.hardware and self.hardware.lcd else page["lines"]

            self._send_json({
                "rotary": {"steps": steps, "button": btn_active},
                "stepper": {"position": pos},
                "pager": {
                    "index": WebConsoleHandler.current_doc_page,
                    "total": len(OPENCAL_PAGES),
                    "title": page["title"],
                    "action_desc": page["action_desc"]
                },
                "lcd": lcd_lines
            })
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

        if parsed.path == "/api/camera/placeholder":
            svg = '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360"><rect width="100%" height="100%" fill="#0a0f1d"/><text x="50%" y="50%" fill="#94a3b8" font-family="sans-serif" font-size="16" text-anchor="middle">Stream Paused</text></svg>'
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.end_headers()
            self.wfile.write(svg.encode("utf-8"))
            return

        self._send_json({"error": "Not Found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {}

        # 1. PAGER & ROTARY ACTIONS
        if parsed.path == "/api/pager/next":
            WebConsoleHandler.current_doc_page = (WebConsoleHandler.current_doc_page + 1) % len(OPENCAL_PAGES)
            self._render_current_page()
            self._send_json({"message": f"Switched to {OPENCAL_PAGES[WebConsoleHandler.current_doc_page]['title']}"})
            return

        if parsed.path == "/api/pager/prev":
            WebConsoleHandler.current_doc_page = (WebConsoleHandler.current_doc_page - 1) % len(OPENCAL_PAGES)
            self._render_current_page()
            self._send_json({"message": f"Switched to {OPENCAL_PAGES[WebConsoleHandler.current_doc_page]['title']}"})
            return

        if parsed.path == "/api/pager/action":
            msg = self._trigger_page_action()
            self._send_json({"message": msg})
            return

        # 2. LCD DIRECT WRITE
        if parsed.path == "/api/lcd/write":
            row = data.get("row", 0)
            text = data.get("text", "")
            if self.hardware and self.hardware.lcd:
                self.hardware.lcd.write_message(text, row=row)
            self._send_json({"message": f"Updated LCD row {row}"})
            return

        # 3. CAMERA CONTROLS
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

        # 4. STEPPER MOTOR CONTROLS
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
                if self.hardware and self.hardware.stepper:
                    self.hardware.stepper.set_rpm(rpm)
                    self.hardware.stepper.start_rotation(direction="CW")
                self._send_json({"message": f"Continuous rotation at {rpm} RPM"})
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

        # 5. LED CONTROLS
        if parsed.path == "/api/led/color":
            try:
                col_str = data.get("color", "white").lower()
                cmap = {"red": RED, "green": GREEN, "blue": BLUE, "yellow": YELLOW, "white": WHITE, "cyan": (0, 255, 255), "off": OFF}
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

        self._send_json({"error": "Endpoint not found"}, status=404)

    def _render_current_page(self):
        page = OPENCAL_PAGES[WebConsoleHandler.current_doc_page]
        if self.hardware and self.hardware.lcd:
            for idx, line in enumerate(page["lines"]):
                self.hardware.lcd.write_message(line, row=idx)

    def _trigger_page_action(self) -> str:
        page = OPENCAL_PAGES[WebConsoleHandler.current_doc_page]
        action = page["action"]
        try:
            if action == "jog_motor_360":
                if self.hardware and self.hardware.stepper:
                    self.hardware.stepper.rotate_steps(3200, direction="CW")
                return "Motor Jogged 360 Degrees"
            elif action == "run_rainbow":
                if self.hardware and self.hardware.led_manager:
                    threading.Thread(target=self._run_led_anim, args=("rainbow",), daemon=True).start()
                return "LED Rainbow Started"
            elif action == "trigger_autofocus":
                if self.hardware and self.hardware.camera:
                    self.hardware.camera.activate_autofocus()
                return "Autofocus Triggered"
            elif action == "start_print_demo":
                if self.hardware and self.hardware.stepper:
                    self.hardware.stepper.set_rpm(9.0)
                    self.hardware.stepper.start_rotation(direction="CW")
                return "VAM Print Demo Started (9 RPM)"
            else:
                self._render_current_page()
                return f"Page {page['title']} Refreshed"
        except Exception as e:
            return f"Action Error: {e}"

    def _run_led_anim(self, anim_name):
        if not self.hardware or not self.hardware.led_manager:
            return
        try:
            if anim_name == "rainbow":
                for _ in range(3):
                    for color in [(255,0,0), (255,127,0), (255,255,0), (0,255,0), (0,255,255), (0,0,255), (139,0,255)]:
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


def rotary_hardware_listener(hardware: HardwareController):
    """Background listener tracking physical rotary knob rotation and button clicks."""
    if not hardware or not hardware.rotary:
        return
    last_step = hardware.rotary.get_steps()
    
    # Initialize LCD with Page 0
    page = OPENCAL_PAGES[WebConsoleHandler.current_doc_page]
    if hardware.lcd:
        for idx, line in enumerate(page["lines"]):
            hardware.lcd.write_message(line, row=idx)

    while True:
        try:
            current_step = hardware.rotary.get_steps()
            diff = current_step - last_step
            if diff >= 2:  # Clockwise rotation
                WebConsoleHandler.current_doc_page = (WebConsoleHandler.current_doc_page + 1) % len(OPENCAL_PAGES)
                page = OPENCAL_PAGES[WebConsoleHandler.current_doc_page]
                if hardware.lcd:
                    for idx, line in enumerate(page["lines"]):
                        hardware.lcd.write_message(line, row=idx)
                last_step = current_step
            elif diff <= -2:  # Counter-clockwise rotation
                WebConsoleHandler.current_doc_page = (WebConsoleHandler.current_doc_page - 1) % len(OPENCAL_PAGES)
                page = OPENCAL_PAGES[WebConsoleHandler.current_doc_page]
                if hardware.lcd:
                    for idx, line in enumerate(page["lines"]):
                        hardware.lcd.write_message(line, row=idx)
                last_step = current_step

            # Button Click Check
            if hardware.rotary.was_button_pressed():
                page = OPENCAL_PAGES[WebConsoleHandler.current_doc_page]
                if hardware.lcd:
                    hardware.lcd.write_message(">>> ACTION RUN <<<  ", row=3)
                # Execute action
                action = page["action"]
                if action == "jog_motor_360" and hardware.stepper:
                    hardware.stepper.rotate_steps(3200, direction="CW")
                elif action == "run_rainbow" and hardware.led_manager:
                    for color in [(255,0,0), (0,255,0), (0,0,255), (255,255,255)]:
                        hardware.led_manager.set_color(color)
                        time.sleep(0.15)
                elif action == "trigger_autofocus" and hardware.camera:
                    hardware.camera.activate_autofocus()
                elif action == "start_print_demo" and hardware.stepper:
                    hardware.stepper.set_rpm(9.0)
                    hardware.stepper.start_rotation(direction="CW")
                time.sleep(0.8)
                if hardware.lcd:
                    hardware.lcd.write_message(page["lines"][3], row=3)

            time.sleep(0.05)
        except Exception:
            time.sleep(0.1)


def run_web_console(host="0.0.0.0", port=5000):
    print("=" * 60)
    print("     STARTING OPENCAL HARDWARE WEB CONSOLE (PORT 5000)   ")
    print("=" * 60)
    
    cfg = Config()
    hardware = HardwareController(cfg)
    WebConsoleHandler.hardware = hardware

    # Start physical Rotary Encoder Background Pager Listener
    threading.Thread(target=rotary_hardware_listener, args=(hardware,), daemon=True).start()

    server = ThreadingHTTPServer((host, port), WebConsoleHandler)
    print(f"🚀 Console Live: http://softa-vam.local:{port} or http://10.49.26.109:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Web Console...")
        server.shutdown()
        hardware.close()


if __name__ == "__main__":
    run_web_console()
