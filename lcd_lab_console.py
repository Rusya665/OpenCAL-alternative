import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from smbus2 import SMBus, i2c_msg

BUS_NUM = 1
DEFAULT_ADDRESS = 0x28

HTML_LAB = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newhaven LCD Interactive Protocol Lab</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #07090e;
            --bg-card: #0d121f;
            --bg-input: #141b2d;
            --accent-cyan: #00f0ff;
            --accent-purple: #a855f7;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border-card: rgba(255, 255, 255, 0.08);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg-primary);
            color: var(--text-main);
            min-height: 100vh;
            padding: 24px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border-card);
        }
        h1 { font-size: 24px; font-weight: 700; color: var(--accent-cyan); display: flex; align-items: center; gap: 10px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card {
            background: var(--bg-card); border-radius: 14px; padding: 20px;
            border: 1px solid var(--border-card); box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        .card-title {
            font-size: 16px; font-weight: 600; color: var(--text-main); margin-bottom: 14px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .btn-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-bottom: 14px; }
        button {
            background: var(--bg-input); color: var(--text-main); border: 1px solid var(--border-card);
            padding: 10px 14px; border-radius: 8px; font-family: 'Outfit', sans-serif; font-size: 13px;
            font-weight: 600; cursor: pointer; transition: all 0.2s ease;
        }
        button:hover { background: rgba(0, 240, 255, 0.15); border-color: var(--accent-cyan); color: var(--accent-cyan); }
        button.primary { background: linear-gradient(135deg, #00f0ff, #0284c7); color: #000; border: none; }
        button.primary:hover { opacity: 0.9; }
        button.danger { background: rgba(239, 68, 68, 0.2); border-color: var(--accent-red); color: var(--accent-red); }
        button.warning { background: rgba(245, 158, 11, 0.2); border-color: var(--accent-amber); color: var(--accent-amber); }
        .form-group { margin-bottom: 14px; }
        label { display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 6px; }
        input[type="text"], select, textarea {
            width: 100%; background: var(--bg-input); border: 1px solid var(--border-card);
            border-radius: 8px; padding: 10px 14px; color: var(--text-main); font-family: 'JetBrains Mono', monospace; font-size: 14px;
        }
        input:focus, textarea:focus { outline: none; border-color: var(--accent-cyan); }
        .log-box {
            background: #030508; border-radius: 10px; padding: 14px; font-family: 'JetBrains Mono', monospace;
            font-size: 12px; height: 380px; overflow-y: auto; border: 1px solid rgba(255,255,255,0.05);
        }
        .log-entry { margin-bottom: 6px; line-height: 1.4; border-bottom: 1px solid rgba(255,255,255,0.03); padding-bottom: 4px; }
        .log-time { color: var(--text-muted); }
        .log-tx { color: var(--accent-cyan); font-weight: 600; }
        .log-ok { color: var(--accent-green); }
        .log-err { color: var(--accent-red); }
        .badge {
            background: rgba(0, 240, 255, 0.1); color: var(--accent-cyan);
            padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>🔬 Newhaven LCD Protocol Lab</h1>
                <p style="color: var(--text-muted); font-size: 13px;">Send individual byte sequences, test framing modes, and inspect raw I2C behavior.</p>
            </div>
            <div class="badge">Target: 0x28 (50 kHz)</div>
        </header>

        <div class="grid">
            <!-- Left Column: Controls -->
            <div>
                <!-- 1. Quick Official Commands -->
                <div class="card" style="margin-bottom: 20px;">
                    <div class="card-title">⚡ 1. Test Clear Commands & Wipes</div>
                    <div class="btn-grid">
                        <button class="danger" onclick="sendQuick([0xFE, 0x14], 'Clear V3 (0xFE 0x14)', 50)">🧹 Clear (FE 14)</button>
                        <button class="danger" onclick="sendQuick([0xFE, 0x51], 'Clear Legacy (0xFE 0x51)', 50)">🧹 Clear (FE 51)</button>
                        <button class="danger" onclick="sendQuick([0xFE, 0x01], 'Clear Raw (0xFE 0x01)', 50)">🧹 Clear (FE 01)</button>
                        <button class="warning" onclick="sendSpacesWipe()">🧽 Wipe 80 Spaces</button>
                    </div>

                    <div class="card-title" style="font-size: 13px; color: var(--text-muted); margin-top: 10px;">Display ON / Home Commands:</div>
                    <div class="btn-grid">
                        <button class="primary" onclick="sendQuick([0xFE, 0x41], 'Display ON (0xFE 0x41)', 10)">💡 ON (FE 41)</button>
                        <button class="primary" onclick="sendQuick([0xFE, 0x0C], 'ON/NoCursor (0xFE 0x0C)', 10)">💡 ON (FE 0C)</button>
                        <button onclick="sendQuick([0xFE, 0x46], 'Cursor Home (0xFE 0x46)', 20)">🏠 Home (FE 46)</button>
                        <button onclick="sendQuick([0xFE, 0x02], 'Home Raw (0xFE 0x02)', 20)">🏠 Home (FE 02)</button>
                    </div>

                    <div class="card-title" style="font-size: 13px; color: var(--text-muted); margin-top: 10px;">Cursor Row Positioning Variations:</div>
                    <div class="btn-grid">
                        <button onclick="sendQuick([0xFE, 0x45, 0x00], 'FE 45 00 (Row 0)', 5)">📍 FE 45 00 (R0)</button>
                        <button onclick="sendQuick([0xFE, 0x45, 0x40], 'FE 45 40 (Row 1)', 5)">📍 FE 45 40 (R1)</button>
                        <button onclick="sendQuick([0xFE, 0x45, 0x14], 'FE 45 14 (Row 2)', 5)">📍 FE 45 14 (R2)</button>
                        <button onclick="sendQuick([0xFE, 0x45, 0x54], 'FE 45 54 (Row 3)', 5)">📍 FE 45 54 (R3)</button>
                    </div>
                    <div class="btn-grid" style="margin-top: 6px;">
                        <button onclick="sendQuick([0xFE, 0x80], 'Raw DDRAM 0x80 (Row 0)', 5)">🎯 FE 80 (R0)</button>
                        <button onclick="sendQuick([0xFE, 0xC0], 'Raw DDRAM 0xC0 (Row 1)', 5)">🎯 FE C0 (R1)</button>
                        <button onclick="sendQuick([0xFE, 0x94], 'Raw DDRAM 0x94 (Row 2)', 5)">🎯 FE 94 (R2)</button>
                        <button onclick="sendQuick([0xFE, 0xD4], 'Raw DDRAM 0xD4 (Row 3)', 5)">🎯 FE D4 (R3)</button>
                    </div>

                    <div class="card-title" style="font-size: 13px; color: var(--text-muted); margin-top: 10px;">Contrast & Backlight:</div>
                    <div class="btn-grid">
                        <button onclick="sendQuick([0xFE, 0x52, 40], 'Contrast 40', 10)">🎚️ Contrast 40</button>
                        <button onclick="sendQuick([0xFE, 0x52, 50], 'Contrast 50', 10)">🎚️ Contrast 50</button>
                        <button onclick="sendQuick([0xFE, 0x53, 8], 'Brightness 8', 10)">☀️ Brightness 8</button>
                        <button onclick="sendQuick([0xFE, 0x53, 2], 'Brightness 2', 10)">🔅 Brightness 2</button>
                    </div>
                </div>

                <!-- 2. Custom Hex & Text Sender -->
                <div class="card">
                    <div class="card-title">✍️ 2. Custom Hex & Text Injector</div>
                    <div class="form-group">
                        <label>Transmission Mode:</label>
                        <select id="mode-select">
                            <option value="single_msg">Mode 1: Single Atomic Packet (i2c_msg.write)</option>
                            <option value="byte_by_byte">Mode 2: Byte-by-Byte (write_byte + 2ms Delay)</option>
                            <option value="smbus_block">Mode 3: SMBus Block (write_i2c_block_data)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Send Raw Hex Bytes (space-separated, e.g. "FE 51" or "48 65 6C 6C 6F"):</label>
                        <div style="display: flex; gap: 8px;">
                            <input type="text" id="hex-input" placeholder="FE 45 00 48 45 4C 4C 4F">
                            <button class="primary" onclick="sendHex()">Send Hex</button>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Send Plain Text String (ASCII):</label>
                        <div style="display: flex; gap: 8px;">
                            <input type="text" id="text-input" placeholder="OpenCAL Test">
                            <button class="primary" onclick="sendText()">Send Text</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right Column: Live TX Log & Notes -->
            <div>
                <div class="card">
                    <div class="card-title">
                        <span>📋 Live I2C Transaction Log</span>
                        <button style="padding: 4px 10px; font-size: 11px;" onclick="clearLog()">Clear Log</button>
                    </div>
                    <div class="log-box" id="log-box">
                        <div class="log-entry log-time">-- Protocol Lab Ready. Select a command or inject hex bytes --</div>
                    </div>
                </div>

                <div class="card" style="margin-top: 20px;">
                    <div class="card-title">📝 My Physical Screen Notes</div>
                    <textarea id="lab-notes" rows="4" placeholder="Type what you observe on the screen here (e.g. 'Button 0xFE 0x51 cleared row 0, row 3 still visible')..."></textarea>
                </div>
            </div>
        </div>
    </div>

    <script>
        function logMessage(txHex, desc, status, isOk) {
            const box = document.getElementById('log-box');
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            const time = new Date().toLocaleTimeString();
            entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-tx">TX: ${txHex}</span> <em>(${desc})</em> &rarr; <span class="${isOk ? 'log-ok' : 'log-err'}">${status}</span>`;
            box.appendChild(entry);
            box.scrollTop = box.scrollHeight;
        }

        async function sendPayload(bytesArr, desc, delay=10) {
            const mode = document.getElementById('mode-select').value;
            const res = await fetch('/api/lab/send', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({bytes: bytesArr, mode: mode, delay_ms: delay})
            });
            const data = await res.json();
            logMessage(data.hex, desc, data.status, data.ok);
        }

        function sendQuick(bytesArr, desc, delay) {
            sendPayload(bytesArr, desc, delay);
        }

        function sendSpacesWipe() {
            const spaces = Array(80).fill(32); // 80 ASCII spaces (0x20)
            sendPayload(spaces, 'Wipe 80 Spaces', 20);
        }

        function sendHex() {
            const raw = document.getElementById('hex-input').value.trim();
            if (!raw) return;
            const parts = raw.split(/[\s,]+/).filter(x => x.length > 0);
            const bytesArr = parts.map(p => parseInt(p, 16));
            sendPayload(bytesArr, 'Custom Hex: ' + raw, 10);
        }

        function sendText() {
            const text = document.getElementById('text-input').value;
            if (!text) return;
            const bytesArr = Array.from(text).map(c => c.charCodeAt(0));
            sendPayload(bytesArr, 'Text: "' + text + '"', 5);
        }

        function clearLog() {
            document.getElementById('log-box').innerHTML = '';
        }
    </script>
</body>
</html>
"""


class LabHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_LAB.encode("utf-8"))
            return
        self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/lab/send":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            data = json.loads(body.decode("utf-8"))
            
            bytes_list = data.get("bytes", [])
            mode = data.get("mode", "single_msg")
            delay_ms = float(data.get("delay_ms", 10)) / 1000.0
            
            hex_repr = " ".join(f"{b:02X}" for b in bytes_list)
            
            try:
                with SMBus(BUS_NUM) as bus:
                    if mode == "single_msg":
                        msg = i2c_msg.write(DEFAULT_ADDRESS, bytes_list)
                        bus.i2c_rdwr(msg)
                    elif mode == "byte_by_byte":
                        for b in bytes_list:
                            bus.write_byte(DEFAULT_ADDRESS, b)
                            time.sleep(0.002)
                    elif mode == "smbus_block":
                        if len(bytes_list) >= 2:
                            bus.write_i2c_block_data(DEFAULT_ADDRESS, bytes_list[0], bytes_list[1:])
                        elif len(bytes_list) == 1:
                            bus.write_byte(DEFAULT_ADDRESS, bytes_list[0])
                            
                    time.sleep(delay_ms)
                    
                self._send_json({"ok": True, "hex": hex_repr, "status": "I2C ACK (200 OK)"})
            except Exception as e:
                self._send_json({"ok": False, "hex": hex_repr, "status": f"I2C ERROR: {e}"}, status=500)
            return

        self._send_json({"error": "Not found"}, 404)


def run_lab(port: int = 8080):
    print("=" * 60)
    print(f"      NEWHAVEN LCD PROTOCOL LAB LIVE ON PORT {port}      ")
    print("=" * 60)
    server = HTTPServer(("0.0.0.0", port), LabHandler)
    print(f"Lab UI: http://softa-vam.local:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    run_lab(8080)
