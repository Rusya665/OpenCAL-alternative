#!/usr/bin/env python3
import os
import subprocess
import sys
import uuid

def create_system_8021x(con_name: str, ssid: str, identity: str, password: str):
    file_path = f"/etc/NetworkManager/system-connections/{con_name}.nmconnection"
    u = str(uuid.uuid4())
    content = f"""[connection]
id={con_name}
uuid={u}
type=wifi
interface-name=wlan0
autoconnect=true
autoconnect-priority=10

[wifi]
mode=infrastructure
ssid={ssid}

[wifi-security]
key-mgmt=wpa-eap

[802-1x]
eap=peap;
identity={identity}
anonymous-identity=anonymous@utu.fi
password={password}
password-flags=0
phase2-auth=mschapv2
system-ca-certs=false

[ipv4]
method=auto

[ipv6]
addr-gen-mode=default
method=auto
"""
    tmp_path = f"/tmp/{con_name}.nmconnection"
    with open(tmp_path, "w") as f:
        f.write(content)

    subprocess.run(["sudo", "mv", tmp_path, file_path], check=True)
    subprocess.run(["sudo", "chmod", "600", file_path], check=True)
    subprocess.run(["sudo", "chown", "root:root", file_path], check=True)
    print(f"✓ Created system-wide keyfile for {con_name}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: setup_system_eduroam.py <identity> <password>")
        sys.exit(1)
    ident = sys.argv[1]
    pwd = sys.argv[2]
    create_system_8021x("eduroam", "eduroam", ident, pwd)
    create_system_8021x("UTU_Staff", "UTU Staff", ident, pwd)
    subprocess.run(["sudo", "nmcli", "connection", "reload"], check=True)
    print("✓ NetworkManager configuration reloaded.")
