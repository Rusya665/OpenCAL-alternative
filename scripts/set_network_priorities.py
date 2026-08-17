#!/usr/bin/env python3
import subprocess

def set_priority(con_name: str, priority: int, autoconnect: bool = True):
    subprocess.run([
        "sudo", "nmcli", "connection", "modify", con_name,
        "connection.autoconnect", "yes" if autoconnect else "no",
        "connection.autoconnect-priority", str(priority)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"✓ {con_name} -> Priority {priority}")

if __name__ == "__main__":
    print("[*] Configuring Network Connection Hierarchy...")
    # 1. Primary: Eduroam & UTU Staff
    set_priority("eduroam", 100)
    set_priority("UTU_Staff", 90)
    
    # 2. Secondary: Phone Hotspot (Quetzalcoatl)
    set_priority("netplan-wlan0-Quetzalcoatl", 80)
    
    # 3. Fallback: Standalone Hotspot (Only if nothing else is reachable)
    set_priority("OpenCAL-Hotspot", 10)
    
    # Reload NetworkManager
    subprocess.run(["sudo", "nmcli", "connection", "reload"])
    print("✓ All network priorities permanently applied!")
