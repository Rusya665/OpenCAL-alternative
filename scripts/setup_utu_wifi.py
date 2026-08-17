#!/usr/bin/env python3
import subprocess
import sys

def setup_8021x(con_name: str, ssid: str, identity: str, password: str):
    # Remove old connection if exists
    subprocess.run(["sudo", "nmcli", "connection", "delete", con_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    cmd = [
        "sudo", "nmcli", "connection", "add",
        "type", "wifi",
        "con-name", con_name,
        "ifname", "wlan0",
        "ssid", ssid,
        "wifi-sec.key-mgmt", "wpa-eap",
        "802-1x.eap", "peap",
        "802-1x.phase2-auth", "mschapv2",
        "802-1x.identity", identity,
        "802-1x.anonymous-identity", "anonymous@utu.fi",
        "802-1x.password", password,
        "802-1x.system-ca-certs", "yes",
        "802-1x.domain-suffix-match", "utu.fi",
        "connection.autoconnect", "yes",
        "connection.autoconnect-priority", "10"
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        print(f"✓ Profile configured successfully: {con_name}")
    else:
        print(f"✗ Failed to configure {con_name}: {res.stderr.strip()}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: setup_utu_wifi.py <identity> <password>")
        sys.exit(1)
    ident = sys.argv[1]
    pwd = sys.argv[2]
    setup_8021x("eduroam", "eduroam", ident, pwd)
    setup_8021x("UTU_Staff", "UTU Staff", ident, pwd)
