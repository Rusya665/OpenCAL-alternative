import time
from smbus2 import SMBus, i2c_msg

bus = SMBus(1)
addr = 0x28

def send_byte(b, d=0.0025):
    msg = i2c_msg.write(addr, [b])
    bus.i2c_rdwr(msg)
    time.sleep(d)

def set_cursor(pos):
    send_byte(0xFE, 0.003)
    send_byte(0x45, 0.003)
    send_byte(pos, 0.005)

def clear():
    send_byte(0xFE, 0.003)
    send_byte(0x51, 0.100)

print("1. Clearing screen...")
clear()

print("2. Writing 4 lines using 1-byte framed set_cursor...")
set_cursor(0x00)
for c in "Print from USB      ":
    send_byte(ord(c))

set_cursor(0x40)
for c in ">Manual Control     ":
    send_byte(ord(c))

set_cursor(0x14)
for c in "Settings            ":
    send_byte(ord(c))

set_cursor(0x54)
for c in "Power Options       ":
    send_byte(ord(c))

print("Displayed successfully! Testing 5 simulated scroll cycles...")
time.sleep(2)

menus = [
    [">Print from USB     ", " Manual Control     ", " Settings           ", " Power Options      "],
    [" Print from USB     ", ">Manual Control     ", " Settings           ", " Power Options      "],
    [" Print from USB     ", " Manual Control     ", ">Settings           ", " Power Options      "],
    [" Print from USB     ", " Manual Control     ", " Settings           ", ">Power Options      "],
    [">Print from USB     ", " Manual Control     ", " Settings           ", " Power Options      "],
]

for cycle in range(3):
    for menu in menus:
        set_cursor(0x00)
        for c in menu[0]: send_byte(ord(c))
        set_cursor(0x40)
        for c in menu[1]: send_byte(ord(c))
        set_cursor(0x14)
        for c in menu[2]: send_byte(ord(c))
        set_cursor(0x54)
        for c in menu[3]: send_byte(ord(c))
        time.sleep(0.3)

print("Test complete!")
