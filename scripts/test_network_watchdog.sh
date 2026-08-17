#!/bin/bash
FALLBACK_CONN="netplan-wlan0-Quetzalcoatl"
TARGET_CONN="$1"

if [ -z "$TARGET_CONN" ]; then
    echo "Usage: $0 target_connection_name"
    exit 1
fi

echo "[1/3] Arming 45-second failsafe rollback to $FALLBACK_CONN..."
(
    sleep 45
    if ! ping -c 2 -W 3 1.1.1.1 >/dev/null 2>&1; then
        echo "[ROLLBACK TRIGGERED] Target network unreachable. Reverting to $FALLBACK_CONN..."
        sudo nmcli connection up "$FALLBACK_CONN"
    fi
) &
WATCHDOG_PID=$!

echo "[2/3] Switching connection to $TARGET_CONN..."
sudo nmcli connection up "$TARGET_CONN"

echo "[3/3] Verifying internet and DNS connectivity..."
sleep 5
if ping -c 3 -W 3 1.1.1.1 >/dev/null 2>&1; then
    echo "[SUCCESS] $TARGET_CONN is online and verified! Disarming watchdog..."
    kill $WATCHDOG_PID 2>/dev/null || true
else
    echo "[FAILED] Network check failed. Watchdog will revert in background."
fi
