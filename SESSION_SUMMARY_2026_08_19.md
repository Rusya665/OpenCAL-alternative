# OpenCAL Session Summary — August 19, 2026

## 1. Outstanding User Requests & Status

- **Interactive Draggable & Resizable Optical Gate in Web Console:**
  - *User Directive:* *"make that area drug and droppable in the webciew. thus I can position it myself. also the mark might be bigger that the area. we need to compencapte for that somehow. implament"*
  - *Status:* **COMPLETED & DEPLOYED**
  - *Details:* Added an interactive cyan overlay (`#optical-gate-overlay`) directly over the live 16:9 video frame (`#cal-video-frame-box`). Bidirectional sync with the Raspberry Pi backend via `POST /api/calibrate/gate` and `GET /api/calibrate/gate`.

- **Stepped Rotations & Drift Visualizer ("Do X Rotations"):**
  - *User Directive:* *"add 'do X rotations'. so we do 1 rotation. stop for a bit. do wnother. and thus we can see how the originial was bad - the line will mofve away"*
  - *Status:* **COMPLETED & DEPLOYED**
  - *Details:* Added `SteppedRotationRunner` with single 360° turn (`[ 🔄 1 Turn (360°) ]`) and multi-turn stepped testing (`[ ▶ Do X Turns ]`) with configurable pause intervals.

- **Auto-Find Marker Routine (Auto-Homing):**
  - *User Directive:* *"and also add the FIND line (or a dot) thus the orinter will rotate the will till it finds it. no more than 2 revolutions (like there might be no mark! )"*
  - *Status:* **COMPLETED & DEPLOYED**
  - *Details:* `MarkerFinder` rotates at 4.5 RPM search speed up to a 2.0 revolution limit, auto-locks onto the marker, and stops precisely centered on the optical equator ($y = 0.0$).

- **Illumination & Glare Invariance (Black Marker on White Tape):**
  - *User Directive:* *"shall I have a black line instead? on white tape black color ... this looks black to me. he cannt even autodetect it"*
  - *Status:* **COMPLETED & DEPLOYED**
  - *Details:* Replaced fixed-grayscale thresholding with peak illumination channel absorption (`np.max(gate_img, axis=2)`). Works reliably under red LED, white LED, green LED, or ambient lighting.

- **Eliminate Video Frame Freezes & Stuttering:**
  - *User Directive:* *"should it freeze while auto correction?"*
  - *Status:* **COMPLETED & DEPLOYED**
  - *Details:* Diagnosed blocking subprocess calls (`ticcmd` and `vcgencmd`) invoked at 30 FPS inside the frame loop. Implemented a 0.5s TTL telemetry cache in both `TicUSBStepperMotor` and `get_pi_system_telemetry()`.

---

## 2. User Knowledge & Directives

- *"why he fals detects the line? he detects a dot of the fucking white color . omg"* → Specular reflections from cylindrical glass were falsely triggering dot detection.
- *"shall I have a black line instead? on white tape black color"* → Switched to a thick black marker on white tape to maximize contrast.
- *"why we even consider the are behind and around the vial. hard code for this vial its dimentions"* → Chamber walls, motor chucks, and backdrop shadows introduced background noise.
- *"no stop. not even like that. noi matter the size of the vial, we need to check only a tiny area of the camera. no matter what vile we place - we can store different coefficents for different vials laler on! thus we can make the checker super robust."* → User defined the core Optical Gate architecture.
- *"this is absolutely horrible. it dosenot work properly! see yopu scrennshot and will now position all properly"* → User identified a letterbox aspect ratio offset between the HTML draggable box and the OpenCV video frame.

---

## 3. Work Accomplished

### 1. Draggable & Resizable Optical Gate Overlay
- Built `#cal-video-frame-box` in [opencal/web_console.py](opencal/web_console.py) locked strictly to `aspect-ratio: 16 / 9; max-height: 420px;` to eliminate letterbox/pillarbox offset.
- Added mouse and touch drag/resize listeners (`pointerdown`, `pointermove`, `pointerup`) with throttled 80ms backend sync.
- Added quick presets: `[ 🎯 30mm Standard Vial ]` ($x=38\%, y=22\%, w=24\%, h=56\%$), `[ ↔ Wide Gate ]`, and `[ ↕ Tall Gate ]`.

### 2. Illumination-Invariant Computer Vision Pipeline
- Rewrote `MotorCalibrator.process_frame()` in [opencal/utils/calibration/motor_calibrator.py](opencal/utils/calibration/motor_calibrator.py):
  - Crops strictly to normalized gate ROI $(gx_1, gy_1, gx_2, gy_2)$.
  - Uses peak channel absorption $I_{\text{max}} = \max(B, G, R)$ with adaptive dark thresholding $\tau = \text{clamp}(0.55 \cdot \bar{I}_{\text{max}}, 30, 120)$.
  - Applies morphological opening (`k=(7, 3)`) to reject paper grain texture.
  - Validates contours for horizontal span ($bw \ge 0.25 \cdot W_{\text{gate}}$ and $\text{Area} \ge 60\text{ px}$).
  - Computes sub-pixel Center of Mass $Y_{\text{cm}} = M_{01} / M_{00}$ and normalized equator coordinate $y_{\text{norm}} = (Y_{\text{cm}} - H_g/2) / (H_g/2)$.

### 3. Stepper Homing & Stepped Drift Runner
- Built `MarkerFinder` in [opencal/utils/calibration/motor_calibrator.py](opencal/utils/calibration/motor_calibrator.py) to search up to 2 revolutions at 4.5 RPM and brake within $<10\%$ of equator centerline.
- Built `SteppedRotationRunner` to execute $N$ sequential 360° turns with pause intervals to visualize cumulative mechanical drift.

### 4. Telemetry Caching & Frame Rate Optimization
- Cached `get_pi_system_telemetry()` in [opencal/utils/telemetry.py](opencal/utils/telemetry.py) (0.5s TTL) and guarded with `_has_vcgencmd`.
- Cached `get_telemetry()` in [opencal/hardware/stepper/tic_usb.py](opencal/hardware/stepper/tic_usb.py) (0.5s TTL) to eliminate 30 FPS blocking `ticcmd` subprocess calls.

### 5. Git & Live Deployment
- Pushed commits `562934a`, `5eafbe1`, `ac6f971`, `f43904b`, `52b1077` to branch `custom-newhaven-lcd`.
- Deployed and restarted `opencal.service` on the live Raspberry Pi (`100.88.53.89` / `130.232.229.29`). Confirmed `active`.

---

## 4. Model Knowledge & Algorithms

### Optical Gate Coordinate & Centroid Math
$$\text{Crop} = \text{Frame}[gy_1 : gy_2, \; gx_1 : gx_2]$$
$$M_{00} = \sum_{(x,y) \in \text{Mask}} 1, \quad M_{01} = \sum_{(x,y) \in \text{Mask}} y \implies Y_{\text{cm}} = \frac{M_{01}}{M_{00}}$$
$$y_{\text{norm}} = \frac{Y_{\text{cm}} - H_{\text{gate}} / 2}{H_{\text{gate}} / 2} \in [-1.0, +1.0]$$

### Sub-Frame Zero-Crossing Time Interpolation
$$t_{\text{cross}} = t_{\text{prev}} + \frac{|0.0 - y_{\text{prev}}|}{|y_{\text{curr}} - y_{\text{prev}}|} \cdot (t_{\text{curr}} - t_{\text{prev}})$$

### Illumination Invariance Under Monochromatic Light
Under pure red LED light, standard grayscale transforms $(R, G, B)$ as $0.299R + 0.587G + 0.114B$. Since $G=0, B=0$, white tape at $R=255$ collapses to Grayscale $\approx 76$, causing fixed thresholds ($>78$) to fail. Evaluating $\max(R, G, B)$ guarantees white tape is evaluated at $255$ and black ink at $<110$, regardless of illumination wavelength.

---

## 5. Files and Code

### Edited Files
- [opencal/utils/calibration/motor_calibrator.py](opencal/utils/calibration/motor_calibrator.py):
  - Optical Gate ROI storage, getter, setter (`set_gate_roi()`, `get_gate_roi()`).
  - Illumination-invariant peak channel segmentation and contour span filter.
  - Zero-crossing sub-frame interpolation and auto-homing `MarkerFinder`.
  - Neon HUD overlay with equator line, corner brackets, and tracking crosshairs.
- [opencal/web_console.py](opencal/web_console.py):
  - Draggable & resizable `#optical-gate-overlay` inside 16:9 `#cal-video-frame-box`.
  - `POST /api/calibrate/gate` and `GET /api/calibrate/gate` endpoints.
  - Quick preset buttons (`30mm Standard Vial`, `Wide Gate`, `Tall Gate`).
  - Stepped rotation and Auto-Find Marker UI controls.
- [opencal/hardware/stepper/tic_usb.py](opencal/hardware/stepper/tic_usb.py):
  - Added 0.5s TTL telemetry caching in `get_telemetry()` to prevent `ticcmd` subprocess blocking.
- [opencal/utils/telemetry.py](opencal/utils/telemetry.py):
  - Added 0.5s TTL caching to `get_pi_system_telemetry()`.

---

## 6. Current State & Verification

1. **Optical Gate Alignment:** 1:1 pixel match between web UI draggable box and OpenCV server processing.
2. **Marker Lock:** Confirmed live lock on black marker line with $y = +0.052$ under bright red illumination.
3. **Auto-Homing:** Verified `Find Marker` rotates and centers marker within $<10\%$ of equator centerline.
4. **Smooth Streaming:** Video stream latency and frame rate restored by eliminating blocking subprocess calls.
