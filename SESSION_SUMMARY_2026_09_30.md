# OpenCAL & TOMO Session Summary — September 30, 2026

## 1. Overview & Objectives

Today's session focused on optical characterization, calibration video generation, and interactive projector tooling for computed axial lithography (CAL / VAM):
1. Replicating the resin response calibration method from **Kelly et al. 2019** (*Supplementary Information Fig. S2 & Section S6*).
2. Generating OpenCAL-compliant calibration videos for stepper rotation and exposure testing.
3. Creating desktop and web GUI tools for full-brightness projector illumination (White, Blue laser mode, Green, Red, etc.).
4. Adding an optical alignment spot with shape switching (**Circle** vs. **Rectangle**) and continuous dimension control (1 px pinhole up to 500 px).
5. Deploying all changes directly to the Raspberry Pi 5 (`SOFTA-VAM`) over Tailscale SSH and uploading print assets.

---

## 2. Chronological Timeline & Actions Taken

### 12:34 EEST — Kelly et al. 2019 Calibration Analysis & Asset Generation
- **User Directive:**
  > *"I need this callibaration image. both in shades of white and gray ... this ismage is from '2019 - Kelly - Volumetric additive manufacturing via tomographic reconstruction SI.pdf' ... the same as we now do with TOMO def _frame(k) ... keep the saved video in the 'C:\Users\runiza\GoogleProjects\tomo-alternative'"*
- **Why:**
  Kelly et al. 2019 Section S6 ("Resin response calibration") measures resin inhibition time ($t_{\text{inhb}}$) and critical gelation dose ($D_{c0}$) by projecting a static vertical column of 10 circular dots while the resin vial rotates. The linear response ($1/t_{\text{inhb}}$ vs. intensity, $R^2 = 0.9874$) validates linear dose recording.
- **Actions:**
  - Parsed the reference PDF and extracted the original high-resolution Fig. S2C subfigure crop (`kelly_2019_fig_s2c_original.png`).
  - Measured the profile: exactly 10 circular spots centered horizontally ($x = W/2$), evenly spaced vertically (~18 px / ~10% height intervals), with intensities linearly stepped from 100% (255) down to 25% (64), matching the $1.6 - 0.4\text{ mW/cm}^2$ calibration range.
  - Implemented the projection pipeline matching TOMO's `VAM_Ob._frame(k)`:
    - Pure monochromatic blue channel (`RGB: [0, 0, g]`) to shut off red (638 nm) and green (525 nm) laser diodes on the Optoma ML1080 triple-laser projector, preventing thermal convection and chromatic focal dispersion.
    - Vertical inversion (`np.flipud`) to align with vamtoolbox's bottom-origin pyglet projector texture coordinate system.
    - Standard resolution: `1080x1920` portrait mode.

---

### 13:05 EEST — OpenCAL File Naming Convention & Video Pruning
- **User Directive:**
  > *"we need 2 videos (i dunno why you made 4). and check the file name - opencal will understand only a cirtain type of it"*
- **Why:**
  - Four videos had initially been created (blue and grey variants of each pattern). The user clarified that only **2 videos** were needed: one in shades of gray (intensity dose response) and one in uniform white (geometric alignment and baseline threshold), both using the active monochromatic blue projection channel.
  - In OpenCAL ([`opencal/gui/menus.py`](opencal/gui/menus.py#L36-L40)), motor speed is extracted directly from the filename using `re.search(r"_(\d+(?:\.\d+)?)rpm", filename, re.IGNORECASE)`. Without `_<rpm>rpm.mp4`, OpenCAL cannot pre-set the motor speed automatically upon file selection.
- **Actions:**
  - Deleted the 4 intermediate video files from `tomo-alternative`.
  - Generated exactly 2 OpenCAL-compliant video files at 9.0 RPM (54.0 fps, 300 s duration):
    1. **`calibration_gray_9rpm.mp4`** (10 stepped-intensity dots, blue channel, `np.flipud`)
    2. **`calibration_white_9rpm.mp4`** (10 uniform white dots, blue channel, `np.flipud`)
  - Updated `UIMain/Python_Backend/generate_calibration.py` to enforce this naming scheme.

---

### 13:13 EEST — Interactive Desktop Projector Studio GUI
- **User Directive:**
  > *"quickly make a code which will in GUI allowed me to show a full image at full brgitness of white, blkue etc."*
- **Why:**
  For optical alignment, laser diode testing, optical power meter verification, and resin curing tests, the user needed a rapid way to project solid color fields at 100% full brightness on the physical projector without needing to slice a model or encode a video.
- **Actions:**
  - Created [`scripts/projector_gui.py`](scripts/projector_gui.py) and a double-clickable batch launcher [`run_projector_gui.bat`](run_projector_gui.bat).
  - Used native Win32 `EnumDisplayMonitors` via `ctypes` to automatically detect secondary HDMI displays/projectors.
  - Implemented dual-window architecture: borderless true fullscreen window on the projector while the control dashboard remains on the laptop screen.
  - Added 1-click presets: ⚪ Full White (100%), 🔵 Full Blue (ML1080 Laser), 🟢 Green, 🔴 Red, 🌊 Cyan, 🌸 Magenta, 🟡 Yellow, and custom color picker.
  - Added `0% – 100%` brightness slider and instant blackout hotkeys (<kbd>Esc</kbd>, <kbd>Q</kbd>, <kbd>Space</kbd>).

---

### 13:15 EEST — Center Alignment Dot with Size Control
- **User Directive:**
  > *"also make it there to do a tiny dot in the center (make me control the size of it)"*
- **Why:**
  Optical centering on the rotational axis of cylindrical vials requires a pinpoint center spot. Controlling the spot radius (from single-pixel pinholes up to large circles) allows the user to test focal beam waist, center the vial mount, and observe spot refraction through the index-matching fluid.
- **Actions:**
  - Added the **"🎯 Center Alignment Dot"** panel to `projector_gui.py`.
  - Implemented continuous radius slider (`1 px` to `100 px`, diameter `2 px` to `200 px`) with live real-time canvas rendering.
  - Added quick presets: `1px (Pinhole)`, `2px`, `5px`, `10px`, `20px`, `50px`.
  - Added color presets and an optional faint crosshair guide.

---

### 13:17 EEST — GitHub Push & Raspberry Pi Tailscale Deployment
- **User Directive:**
  > *"push changes so my rasp can actually implement them ... and ssh to it using Tailscale. user softa_vam password softa_vam_3d"*
- **Why:**
  The printer hardware runs on a Raspberry Pi 5 (`SOFTA-VAM`) running `opencal.service`. Changes needed to be pushed to GitHub, pulled to the Pi, print files copied to local storage, and the daemon restarted.
- **Actions:**
  - Discovered the Pi's Tailscale IP: `100.88.53.89`.
  - Resolved the Linux username to `softa-vam` (with hyphen).
  - Committed changes to branch `custom-newhaven-lcd` and pushed to GitHub ([Commit `fd460a0`](https://github.com/Rusya665/OpenCAL-alternative/commit/fd460a0)).
  - Connected to the Pi via SSH/Paramiko over Tailscale.
  - Stashed local hardware motor calibration (`correction_factor: 1.000287`), pulled the latest git commit, and restored the motor calibration cleanly.
  - Transferred `calibration_gray_9rpm.mp4` (3.9 MB) and `calibration_white_9rpm.mp4` (4.4 MB) via SFTP directly into `/home/softa-vam/OpenCAL-alternative/prints/`.
  - Restarted `opencal.service` with `sudo systemctl restart opencal.service` and verified active status.

---

### 13:27 EEST — Shape Switching (Circle ⚪ vs. Rectangle ⬛)
- **User Directive:**
  > *"amazing! make me to be able change the circle to recntanlge shape"*
- **Why:**
  VAM optical testing often requires rectangular slits (e.g. for light sheet characterization, cylindrical lens focus, or rectangular mask alignment) in addition to circular dots.
- **Actions:**
  - **In [`scripts/projector_gui.py`](scripts/projector_gui.py)**:
    - Added shape switching: **`🔘 Circle`** vs. **`⬛ Rectangle`**.
    - Added independent Width (`1 - 500 px`) and Height (`1 - 500 px`) sliders.
    - Added `[x] Lock 1:1` toggle for square / circle symmetry, and presets (`1px`, `5px`, `10px`, `25px`, `50px`, `100px`, `200px`).
  - **In [`opencal/hardware/projector_controller.py`](opencal/hardware/projector_controller.py)**:
    - Updated `project_color_patch()` to support `shape="circle"` and `shape="rect"` with arbitrary `width_px` and `height_px`.
  - **In [`opencal/web_console.py`](opencal/web_console.py)**:
    - Added `🔘 Center Circle` and `⏹️ Center Rectangle` to the size dropdown in Card 8.
    - Added interactive `W` and `H` dimension sliders with `1:1` lock directly in the browser UI.
  - **Deployment**:
    - Committed and pushed to GitHub ([Commit `8b002b2`](https://github.com/Rusya665/OpenCAL-alternative/commit/8b002b2)).
    - SSH'd to the Raspberry Pi over Tailscale, pulled the commit, preserved motor calibration, and restarted `opencal.service`.

---

## 3. Files Created & Modified

| File | Status | Description |
| :--- | :--- | :--- |
| [`scripts/projector_gui.py`](scripts/projector_gui.py) | **Created** | Standalone multi-monitor desktop GUI for full brightness solid illumination, center circle/rectangle spot sizing, and calibration pattern display. |
| [`run_projector_gui.bat`](run_projector_gui.bat) | **Created** | Double-click batch launcher for `projector_gui.py`. |
| [`opencal/hardware/projector_controller.py`](opencal/hardware/projector_controller.py) | **Modified** | Added `shape="circle"|"rect"`, `width_px`, and `height_px` support in `project_color_patch()`. |
| [`opencal/web_console.py`](opencal/web_console.py) | **Modified** | Added Center Circle and Center Rectangle options with live Width/Height/Lock controls in Card 8; updated `/api/projector/color` handler. |
| `tomo-alternative/calibration_gray_9rpm.mp4` | **Created** | Kelly et al. shades of gray 10-dot calibration video (9 RPM, 54 fps, 300 s, blue channel). |
| `tomo-alternative/calibration_white_9rpm.mp4` | **Created** | Kelly et al. uniform white 10-dot calibration video (9 RPM, 54 fps, 300 s, blue channel). |
| `UIMain/Python_Backend/generate_calibration.py` | **Created** | Script to generate OpenCAL-compliant calibration videos and standalone PNG patterns. |
| `SESSION_SUMMARY_2026_09_30.md` | **Created** | Detailed session summary documenting all requests, rationale, and timestamps. |

---

## 4. Current Operational Status

- **GitHub Repository**: Up to date on branch `custom-newhaven-lcd`.
- **Raspberry Pi 5 (`SOFTA-VAM`, 100.88.53.89)**:
  - Systemd service `opencal.service` is **active (running)**.
  - Web Console accessible at `http://100.88.53.89:8080` with full solid illumination, circle/rectangle spot controls, and camera stream.
  - Calibration prints available on the Pi in `/home/softa-vam/OpenCAL-alternative/prints/`.
