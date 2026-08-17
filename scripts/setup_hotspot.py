#!/usr/bin/env python3
import subprocess
import sys

def setup_standalone_hotspot(ssid: str = "OpenCAL-3D-Printer", password: str = "opencal123"):
    con_name = "OpenCAL-Hotspot"
    print(f"[*] Setting up Standalone Access Point: {ssid}")
    
    # 1. Delete existing hotspot connection if exists
    subprocess.run(["sudo", "nmcli", "connection", "delete", con_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 2. Add AP Hotspot Connection
    cmd = [
        "sudo", "nmcli", "connection", "add",
        "type", "wifi",
        "ifname", "wlan0",
        "con-name", con_name,
        "connection.autoconnect", "yes",
        "connection.autoconnect-priority", "100",
        "ssid", ssid,
        "mode", "ap",
        "802-11-wireless.band", "bg",
        "802-11-wireless.channel", "1",
        "802-11-wireless-security.key-mgmt", "wpa-psk",
        "802-11-wireless-security.psk", password,
        "ipv4.method", "shared",
        "ipv4.addresses", "192.168.4.1/24",
        "ipv6.method", "disabled"
    ]
    
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        print(f"✓ Standalone AP '{ssid}' created successfully!")
    else:
        print(f"✗ Error creating AP: {res.stderr.strip()}")
        sys.exit(1)
        
    # 3. Activate Hotspot
    print(f"[*] Activating '{con_name}'...")
    act_res = subprocess.run(["sudo", "nmcli", "connection", "up", con_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if act_res.returncode == 0:
        print(f"✓ '{ssid}' is now broadcasting live on 192.168.4.1!")
    else:
        print(f"✗ Activation note: {act_res.stderr.strip()}")

if __name__ == "__main__":
    ssid = sys.argv[1] if len(sys.argv) > 1 else "OpenCAL-3D-Printer"
    pwd = sys.argv[2] if len(sys.argv) > 2 else "opencal123"
    setup_standalone_hotspot(ssid, pwd)
