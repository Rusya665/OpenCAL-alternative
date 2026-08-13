# OpenCAL Alternative - Newhaven LCD Integration & Developer Setup Guide

This document provides a comprehensive, step-by-step record of all modifications made to the **OpenCAL** project repository for the **Newhaven NHD-0420D3Z LCD display integration** and **cross-platform virtual environment compatibility**.

> **Note for Future AI Agents & Developers**: This repository (`Rusya665/OpenCAL-alternative`) has already been configured and patched. Follow the **[Quick Start for Fresh Computers](#quick-start-for-fresh-computers)** section below to set up your environment immediately without repeating trial-and-error steps.

---

## Table of Contents
1. [Project Overview & Context](#project-overview--context)
2. [Hardware Specification: Newhaven NHD-0420D3Z](#hardware-specification-newhaven-nhd-0420d3z)
3. [Git Repository Architecture](#git-repository-architecture)
4. [Summary of All Code & Configuration Changes Made](#summary-of-all-code--configuration-changes-made)
   - [1. Newhaven LCD Hardware Driver (`opencal/hardware/lcd_display.py`)](#1-newhaven-lcd-hardware-driver-opencalhardwarelcd_displaypy)
   - [2. Config Schema Update (`opencal/utils/config.py` & `config.json`)](#2-config-schema-update-opencalutilsconfigpy--configjson)
   - [3. Cross-Platform Dependencies (`requirements.txt`)](#3-cross-platform-dependencies-requirementstxt)
   - [4. Graceful Hardware Fallbacks (`camera_controller.py` & `led_manager.py`)](#4-graceful-hardware-fallbacks-camera_controllerpy--led_managerpy)
5. [System-Level Setup Required on the Raspberry Pi 5](#system-level-setup-required-on-the-raspberry-pi-5)
6. [Quick Start for Fresh Computers](#quick-start-for-fresh-computers)
7. [Verification & Testing Commands](#verification--testing-commands)

---

## Project Overview & Context

**OpenCAL** is an open-source Volumetric Additive Manufacturing (VAM) 3D printer platform developed by UC Berkeley researchers. It uses **Computed Axial Lithography (CAL)** to cure an entire 3D object all at once inside a rotating vial of photopolymer resin using dynamic 2D projections from a DLP projector.

The printer operates headlessly on a **Raspberry Pi 5**, navigated via a $20	imes4$ character LCD screen and a rotary encoder knob.

---

## Hardware Specification: Newhaven NHD-0420D3Z

The default OpenCAL setup assumes a PCF8574 I2C expander driving an HD44780 LCD module. This custom branch adapts OpenCAL to use the industrial **Newhaven NHD-0420D3Z** screen.

### Critical Hardware Rules for Newhaven NHD-0420D3Z:
1. **PIC16F690 Microcontroller Speed Limit**: The onboard PIC microcontroller cannot process standard 100 kHz I2C clock signals. The Raspberry Pi I2C baudrate **MUST be reduced to 50 kHz** (`50000` Hz).
2. **7-Bit I2C Address**: Defaults to `0x28` (40 decimal).
3. **Protocol & Command Format**: Accepts raw ASCII bytes for characters and 2-byte command sequences prefixed with `0xFE`:
   * **Prefix Byte**: `0xFE`
   * **Display On**: `0xFE 0x41`
   * **Clear Screen**: `0xFE 0x51` *(Requires a 1.5 ms execution delay before sending next byte)*
   * **Set Contrast**: `0xFE 0x52 [1-50]` *(Default: 40)*
   * **Set Backlight**: `0xFE 0x53 [1-8]` *(Default: 8)*
   * **Set Cursor Position**: `0xFE 0x45 [pos_hex]`
4. **Line Offset Memory Addresses**:
   * **Line 0 (Col 0–19)**: `0x00` to `0x13`
   * **Line 1 (Col 0–19)**: `0x40` to `0x53`
   * **Line 2 (Col 0–19)**: `0x14` to `0x27`
   * **Line 3 (Col 0–19)**: `0x54` to `0x67`

---

## Git Repository Architecture

* **Upstream Official Repository**: `https://github.com/computed-axial-lithography/OpenCAL.git`
* **Personal Fork Repository**: `https://github.com/Rusya665/OpenCAL-alternative.git`
* **Active Hardware Branch**: `custom-newhaven-lcd`

### Git Remote Configuration:
```text
origin    https://github.com/Rusya665/OpenCAL-alternative.git (fetch & push)
upstream  https://github.com/computed-axial-lithography/OpenCAL.git (fetch & push)
```

---

## Summary of All Code & Configuration Changes Made

### 1. Newhaven LCD Hardware Driver (`opencal/hardware/lcd_display.py`)
* Created `NewhavenLCDBackend` class using `smbus2.SMBus`:
  * Handled `0xFE` byte commands for display control, cursor movement, contrast, and backlight.
  * Implemented line offset mapping `[0x00, 0x40, 0x14, 0x54]`.
* Maintained full backward compatibility with the existing OpenCAL menu system by retaining the exact `LCDDisplay` class interface (`clear()`, `write_message(message, row)`).
* Added conditional imports for `smbus2` (`HAS_SMBUS2`) and `RPLCD` (`HAS_RPLCD`) with error handling for non-Linux operating systems.

### 2. Config Schema Update (`opencal/utils/config.py` & `config.json`)
* Extended `LcdDisplayConfig` in `opencal/utils/config.py` to support `type`, `contrast`, and `backlight` attributes.
* Updated `opencal/utils/config.json`:
  ```json
  "lcd_display": {
    "type": "newhaven",
    "port": "1",
    "address": "0x28",
    "cols": 20,
    "rows": 4,
    "contrast": 40,
    "backlight": 8
  }
  ```

### 3. Cross-Platform Dependencies (`requirements.txt`)
* Standard OpenCAL `requirements.txt` included Linux-only hardware C libraries (`lgpio`, `picamera2`, `Pi5Neo`). On Windows, `pip install` crashed trying to build these packages.
* Added PEP 508 environment markers (`sys_platform == "linux"`) so Windows skips Linux kernel headers while Raspberry Pi installs them automatically.
* Added `Pillow` (PIL) requirement required by `projector_controller.py`.

### 4. Graceful Hardware Fallbacks (`camera_controller.py` & `led_manager.py`)
* Wrapped `picamera2` and `pi5neo` top-level imports in `try...except (ImportError, ModuleNotFoundError)` blocks (`HAS_PICAMERA2`, `HAS_PI5NEO`).
* Allows developers/agents to import, run, and test OpenCAL Python modules on Windows/macOS workstations without requiring physical Raspberry Pi camera or LED hardware attached.

---

## System-Level Setup Required on the Raspberry Pi 5

When deploying this code to the physical OpenCAL printer (Raspberry Pi 5):

1. **Lower I2C Clock Baudrate to 50 kHz**:
   Edit `/boot/firmware/config.txt` (or `/boot/config.txt`):
   ```bash
   sudo nano /boot/firmware/config.txt
   ```
   Add or update the following line:
   ```text
   dtparam=i2c_arm=on,i2c_arm_baudrate=50000
   ```

2. **Reboot the Pi**:
   ```bash
   sudo reboot
   ```

3. **Restart OpenCAL Service**:
   ```bash
   sudo systemctl restart opencal.service
   ```

---

## Quick Start for Fresh Computers

To set up this project on a fresh workstation or laptop, follow these steps:

### 1. Clone the Fork & Checkout Branch
```bash
git clone https://github.com/Rusya665/OpenCAL-alternative.git
cd OpenCAL-alternative
git checkout custom-newhaven-lcd
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scriptsctivate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
*(Notice: Windows will automatically install all core packages cleanly without crashing on `lgpio` or `picamera2`).*

---

## Verification & Testing Commands

To verify that the environment and hardware driver modules load cleanly:

```bash
# Run Python import check
python -c "from opencal.hardware.lcd_display import LCDDisplay; print('SUCCESS: OpenCAL and LCDDisplay loaded cleanly!')"
```

To run the standalone LCD test script:
```bash
python lcd_test.py
```
