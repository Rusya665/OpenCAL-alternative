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
            --bg-card: rgba(20, 27, 45, 0.75);
            --border-card: rgba(64, 93, 150, 0.25);
            --accent-cyan: #00f0ff;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --lcd-bg: #002244;
            --lcd-text: #66e0ff;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
        body { background: var(--bg-primary); color: var(--text-main); min-height: 100vh; padding: 24px; }
        
        header {
            display: flex; justify-content: space-between; align-items: center;
            max-width: 1200px; margin: 0 auto 28px; padding-bottom: 16px;
            border-bottom: 1px solid var(--border-card);
        }
        h1 { font-size: 26px; font-weight: 700; background: linear-gradient(135deg, #00f0ff, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .badge { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.3); display: flex; align-items: center; gap: 6px; }
        .pulse-dot { width: 8px; height: 8px; background: var(--accent-green); border-radius: 50%; box-shadow: 0 0 8px var(--accent-green); }

        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 24px; max-width: 1200px; margin: 0 auto; }
        
        .card {
            background: var(--bg-card); border: 1px solid var(--border-card);
            border-radius: 16px; padding: 22px; backdrop-filter: blur(12px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3); transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .card:hover { border-color: rgba(0, 240, 255, 0.4); transform: translateY(-2px); }
        .card-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 10px; color: var(--text-main); }
        
        /* LCD Component */
        .lcd-screen {
            background: var(--lcd-bg); border: 3px solid #001122; border-radius: 8px;
            padding: 12px 16px; font-family: 'JetBrains Mono', monospace; font-size: 16px;
            color: var(--lcd-text); letter-spacing: 2px; line-height: 1.5;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.8), 0 0 15px rgba(0, 240, 255, 0.15);
            margin-bottom: 16px;
        }
        .lcd-line { white-space: pre; min-height: 24px; }
        
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
            color: var(--text-main); font-weight: 600; font-size: 14px;
            cursor: pointer; transition: all 0.15s ease;
        }
        button:hover { background: rgba(59, 130, 246, 0.4); border-color: var(--accent-cyan); transform: scale(1.02); }
        button.danger { background: rgba(244, 63, 94, 0.2); border-color: rgba(244, 63, 94, 0.4); color: #fda4af; }
        button.danger:hover { background: rgba(244, 63, 94, 0.4); }
        button.success { background: rgba(16, 185, 129, 0.2); border-color: rgba(16, 185, 129, 0.4); color: #6ee7b7; }
        button.success:hover { background: rgba(16, 185, 129, 0.4); }

        /* Color Buttons */
        .color-palette { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
        .color-btn { width: 38px; height: 38px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.2); cursor: pointer; transition: transform 0.15s ease; }
        .color-btn:hover { transform: scale(1.15); border-color: white; }

        /* Telemetry Readouts */
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
        .stat-box { background: rgba(10, 14, 23, 0.6); padding: 12px; border-radius: 8px; border: 1px solid var(--border-card); }
        .stat-value { font-size: 22px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: var(--accent-cyan); }
        .stat-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; }

        /* Slider */
        .range-wrap { display: flex; align-items: center; gap: 12px; }
        input[type="range"] { flex: 1; accent-color: var(--accent-cyan); }
    </style>
</head>
<body>
    <header>
        <div>
            <h1>OpenCAL Hardware Control Suite</h1>
            <p style="color: var(--text-muted); font-size: 14px;">Interactive Diagnostic & Testing Dashboard</p>
        </div>
        <div class="badge">
            <div class="pulse-dot"></div>
            <span>Connected: Raspberry Pi 5</span>
        </div>
    </header>

    <div class="grid">
        <!-- 1. LCD Screen Controller -->
        <div class="card">
            <div class="card-title">📺 Newhaven 20x4 LCD Screen</div>
            <div class="lcd-screen" id="lcd-preview">
                <div class="lcd-line" id="line-0">                    </div>
                <div class="lcd-line" id="line-1">                    </div>
                <div class="lcd-line" id="line-2">                    </div>
                <div class="lcd-line" id="line-3">                    </div>
            </div>
            <div class="form-group">
                <label>Row 0 Text</label>
                <input type="text" id="input-0" maxlength="20" placeholder="Row 0 message...">
            </div>
            <div class="form-group">
                <label>Row 1 Text</label>
                <input type="text" id="input-1" maxlength="20" placeholder="Row 1 message...">
            </div>
            <div class="form-group">
                <label>Row 2 Text</label>
                <input type="text" id="input-2" maxlength="20" placeholder="Row 2 message...">
            </div>
            <div class="form-group">
                <label>Row 3 Text</label>
                <input type="text" id="input-3" maxlength="20" placeholder="Row 3 message...">
            </div>
            <div class="form-group" style="margin-top: 14px;">
                <label>Contrast (1-50): <span id="contrast-val">42</span></label>
                <div class="range-wrap">
                    <input type="range" id="contrast-slider" min="1" max="50" value="42" oninput="document.getElementById('contrast-val').innerText=this.value" onchange="setLcdContrast(this.value)">
                </div>
            </div>
            <div class="form-group">
                <label>Backlight Brightness (1-8): <span id="backlight-val">8</span></label>
                <div class="range-wrap">
                    <input type="range" id="backlight-slider" min="1" max="8" value="8" oninput="document.getElementById('backlight-val').innerText=this.value" onchange="setLcdBacklight(this.value)">
                </div>
            </div>
            <div class="btn-group">
                <button class="success" onclick="sendLcdLines()">Send to LCD</button>
                <button class="danger" onclick="clearLcd()">Clear Screen</button>
            </div>
        </div>

        <!-- 2. Stepper Motor Engine -->
        <div class="card">
            <div class="card-title">⚙️ Stepper Motor Engine</div>
            <div class="stat-grid">
                <div class="stat-box">
                    <div class="stat-label">Current Position</div>
                    <div class="stat-value" id="motor-pos">0</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Speed (RPM)</div>
                    <div class="stat-value" id="motor-rpm-disp">9.0</div>
                </div>
            </div>
            <div class="form-group">
                <label>Target Speed (RPM): <span id="rpm-val">9</span> RPM</label>
                <div class="range-wrap">
                    <input type="range" id="rpm-slider" min="1" max="30" value="9" oninput="updateRpmLabel(this.value)">
                    <button onclick="setRpm()">Set Speed</button>
                </div>
            </div>
            <div class="form-group">
                <label>Jog Microsteps</label>
                <div class="btn-group">
                    <button onclick="jogSteps(-1000)">-1000</button>
                    <button onclick="jogSteps(-200)">-200</button>
                    <button onclick="jogSteps(200)">+200</button>
                    <button onclick="jogSteps(1000)">+1000</button>
                </div>
            </div>
            <div class="form-group">
                <label>Continuous Spin</label>
                <div class="btn-group">
                    <button class="success" onclick="startSpin('CW')">Spin CW</button>
                    <button class="success" onclick="startSpin('CCW')">Spin CCW</button>
                    <button class="danger" onclick="stopSpin()">Stop Motor</button>
                </div>
            </div>
        </div>

        <!-- 3. NeoPixel LED Ring -->
        <div class="card">
            <div class="card-title">💡 Pi5Neo 64-LED Ring</div>
            <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 12px;">Select color preset or run dynamic animations:</p>
            <div class="color-palette">
                <div class="color-btn" style="background: #ff0000;" onclick="setLedPreset('red')" title="Red"></div>
                <div class="color-btn" style="background: #00ff00;" onclick="setLedPreset('green')" title="Green"></div>
                <div class="color-btn" style="background: #0088ff;" onclick="setLedPreset('blue')" title="Blue"></div>
                <div class="color-btn" style="background: #ffcc00;" onclick="setLedPreset('yellow')" title="Yellow"></div>
                <div class="color-btn" style="background: #ffffff;" onclick="setLedPreset('white')" title="White"></div>
                <div class="color-btn" style="background: #222222;" onclick="setLedPreset('off')" title="Off"></div>
            </div>
            <div class="btn-group">
                <button class="success" onclick="runLedAnimation()">Run Startup Animation</button>
                <button class="danger" onclick="setLedPreset('off')">Turn Off LEDs</button>
            </div>
        </div>

        <!-- 4. Rotary Knob & Encoder -->
        <div class="card">
            <div class="card-title">🎛️ Rotary Encoder & Knob</div>
            <div class="stat-grid">
                <div class="stat-box">
                    <div class="stat-label">Knob Steps</div>
                    <div class="stat-value" id="knob-steps">0</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Button State</div>
                    <div class="stat-value" id="btn-state" style="color: var(--text-muted);">RELEASED</div>
                </div>
            </div>
            <p style="color: var(--text-muted); font-size: 13px;">Turn the physical knob or press the button on the machine to see live updates!</p>
        </div>
    </div>

    <script>
        function updateRpmLabel(val) {
            document.getElementById('rpm-val').innerText = val;
        }

        async function sendLcdLines() {
            const lines = [
                document.getElementById('input-0').value,
                document.getElementById('input-1').value,
                document.getElementById('input-2').value,
                document.getElementById('input-3').value,
            ];
            await fetch('/api/lcd/write', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({lines})
            });
            for(let i=0; i<4; i++) {
                document.getElementById('line-' + i).innerText = (lines[i] || '').padEnd(20, ' ');
            }
        }

        async function setLcdContrast(val) {
            await fetch('/api/lcd/contrast', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({contrast: parseInt(val)})
            });
        }

        async function setLcdBacklight(val) {
            await fetch('/api/lcd/backlight', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({backlight: parseInt(val)})
            });
        }

        async function jogSteps(steps) {
            await fetch('/api/stepper/jog', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({steps})
            });
        }

        async function setRpm() {
            const rpm = parseFloat(document.getElementById('rpm-slider').value);
            await fetch('/api/stepper/rpm', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({rpm})
            });
            document.getElementById('motor-rpm-disp').innerText = rpm.toFixed(1);
        }

        async function startSpin(direction) {
            const rpm = parseFloat(document.getElementById('rpm-slider').value);
            await fetch('/api/stepper/spin', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({direction, rpm})
            });
        }

        async function stopSpin() {
            await fetch('/api/stepper/stop', {method: 'POST'});
        }

        async function setLedPreset(preset) {
            await fetch('/api/led/preset', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({preset})
            });
        }

        async function runLedAnimation() {
            await fetch('/api/led/animation', {method: 'POST'});
        }

        // Live Telemetry Poller
        setInterval(async () => {
            try {
                const res = await fetch('/api/telemetry');
                if (res.ok) {
                    const data = await res.json();
                    if (data.rotary) {
                        document.getElementById('knob-steps').innerText = data.rotary.steps;
                        const btnEl = document.getElementById('btn-state');
                        if (data.rotary.button) {
                            btnEl.innerText = 'PRESSED';
                            btnEl.style.color = 'var(--accent-green)';
                        } else {
                            btnEl.innerText = 'RELEASED';
                            btnEl.style.color = 'var(--text-muted)';
                        }
                    }
                    if (data.stepper) {
                        document.getElementById('motor-pos').innerText = data.stepper.position;
                    }
                }
            } catch (e) {}
        }, 400);
    </script>
</body>
</html>
"""


class WebConsoleHandler(BaseHTTPRequestHandler):
    hardware: HardwareController = None

    def log_message(self, format, *args):
        pass  # Suppress default noisy access logs

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
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
            if self.hardware and self.hardware.stepper:
                try:
                    if hasattr(self.hardware.stepper, "tic") and self.hardware.stepper.tic:
                        pos = self.hardware.stepper.tic.get_current_position()
                except Exception:
                    pass

            self._send_json({
                "rotary": {"steps": steps, "button": btn_active},
                "stepper": {"position": pos}
            })
            return

        self._send_json({"error": "Not Found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        data = json.loads(body.decode("utf-8")) if body else {}

        # 1. LCD Endpoints
        if parsed.path == "/api/lcd/write":
            lines = data.get("lines", [])
            if self.hardware and self.hardware.lcd:
                for i, text in enumerate(lines[:4]):
                    self.hardware.lcd.write_message(text, row=i)
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/lcd/clear":
            if self.hardware and self.hardware.lcd:
                self.hardware.lcd.clear()
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/lcd/contrast":
            val = int(data.get("contrast", 42))
            if self.hardware and self.hardware.lcd and hasattr(self.hardware.lcd.backend, "set_contrast"):
                self.hardware.lcd.backend.set_contrast(val)
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/lcd/backlight":
            val = int(data.get("backlight", 8))
            if self.hardware and self.hardware.lcd and hasattr(self.hardware.lcd.backend, "set_backlight"):
                self.hardware.lcd.backend.set_backlight(val)
            self._send_json({"status": "ok"})
            return

        # 2. Stepper Endpoints
        if parsed.path == "/api/stepper/jog":
            steps = int(data.get("steps", 0))
            if self.hardware and self.hardware.stepper:
                try:
                    self.hardware.stepper.rotate_steps(steps)
                except Exception as e:
                    self._send_json({"error": str(e)}, status=500)
                    return
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/stepper/rpm":
            rpm = float(data.get("rpm", 9.0))
            if self.hardware and self.hardware.stepper:
                try:
                    self.hardware.stepper.set_rpm(rpm)
                except Exception as e:
                    self._send_json({"error": str(e)}, status=500)
                    return
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/stepper/spin":
            direction = str(data.get("direction", "CW"))
            rpm = float(data.get("rpm", 9.0))
            if self.hardware and self.hardware.stepper:
                try:
                    self.hardware.stepper.set_rpm(rpm)
                    self.hardware.stepper.start_rotation(direction)
                except Exception as e:
                    self._send_json({"error": str(e)}, status=500)
                    return
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/stepper/stop":
            if self.hardware and self.hardware.stepper:
                try:
                    self.hardware.stepper.stop()
                except Exception as e:
                    self._send_json({"error": str(e)}, status=500)
                    return
            self._send_json({"status": "ok"})
            return

        # 3. LED Endpoints
        if parsed.path == "/api/led/preset":
            preset = str(data.get("preset", "off")).lower()
            color_map = {
                "red": RED,
                "green": GREEN,
                "blue": BLUE,
                "yellow": YELLOW,
                "white": WHITE,
                "off": OFF,
            }
            color = color_map.get(preset, OFF)
            if self.hardware and self.hardware.led_manager:
                try:
                    self.hardware.led_manager.set_led(color)
                except Exception as e:
                    self._send_json({"error": str(e)}, status=500)
                    return
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/led/animation":
            if self.hardware and self.hardware.led_manager:
                threading.Thread(target=self.hardware.led_manager.run_start_animation, daemon=True).start()
            self._send_json({"status": "ok"})
            return

        self._send_json({"error": "Invalid endpoint"}, status=404)


def launch_web_console(port: int = 5000):
    print("=" * 60)
    print("       OPENCAL HARDWARE TESTING & CONTROL CONSOLE       ")
    print("=" * 60)
    print("Initializing hardware controller...")
    cfg = Config()
    hw = HardwareController(cfg)
    WebConsoleHandler.hardware = hw

    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, WebConsoleHandler)
    print(f"\n[READY] Web Console is live at:")
    print(f"  -> Local Network: http://softa-vam.local:{port}")
    print(f"  -> Direct IP:     http://0.0.0.0:{port}\n")
    print("Press Ctrl+C in terminal to stop.")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Web Console...")
        httpd.server_close()


if __name__ == "__main__":
    launch_web_console(5000)
