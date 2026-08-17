#!/bin/bash
set -e

cat <<'EOF' > /tmp/opencal-console.service
[Unit]
Description=OpenCAL Hardware Control Web Console
After=network.target

[Service]
Type=simple
User=softa-vam
WorkingDirectory=/home/softa-vam/OpenCAL-alternative
Environment=PYTHONPATH=/home/softa-vam/OpenCAL-alternative
ExecStart=/home/softa-vam/OpenCAL-alternative/.venv/bin/python3 -m opencal.web_console
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/opencal-console.service /etc/systemd/system/opencal-console.service
sudo systemctl daemon-reload
sudo systemctl enable opencal-console.service
sudo systemctl restart opencal-console.service
sleep 3
sudo systemctl status opencal-console.service --no-pager
