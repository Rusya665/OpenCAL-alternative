#!/bin/bash
set -e

# 1. Stop and disable the temporary web console service
sudo systemctl stop opencal-console.service 2>/dev/null || true
sudo systemctl disable opencal-console.service 2>/dev/null || true

# 2. Configure official OpenCAL systemd service
cat <<'EOF' > /tmp/opencal.service
[Unit]
Description=OpenCAL VAM 3D Printer Main Runtime
After=network.target

[Service]
Type=simple
User=softa-vam
WorkingDirectory=/home/softa-vam/OpenCAL-alternative
Environment=PYTHONPATH=/home/softa-vam/OpenCAL-alternative
Environment=DISPLAY=:0
ExecStart=/home/softa-vam/OpenCAL-alternative/.venv/bin/python3 -m opencal
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/opencal.service /etc/systemd/system/opencal.service
sudo systemctl daemon-reload
sudo systemctl enable opencal.service
sudo systemctl restart opencal.service
sleep 3
sudo systemctl status opencal.service --no-pager
