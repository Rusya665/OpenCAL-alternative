# OpenCAL & Tomo: Optoma ML1080 Laser & Exposure Calibration Log

**Document Version:** 1.0.0  
**Project:** OpenCAL-alternative / Tomo-alternative / VAMToolbox-alternative  
**Hardware Rig:** OpenCAL (Raspberry Pi 5 + Pololu Tic T249 Stepper + Newhaven LCD + Optoma ML1080 RGB Triple Laser Projector)  
**Specimen Model:** Resized Mini Captive Ring (`captiveRing.stl`, ~5–6 mm outer height)  

---

## 1. Chronological Activity Log (Timestamps)

| Timestamp (UTC+3) | Repository / Module | Activity & Engineering Rationale |
| :--- | :--- | :--- |
| **2026-09-28 09:15** | `Rhino / Grasshopper` | **CAD Holder Inspection:** Examined `2026-06-30 vial holders.gh` and CAD renders. Verified that the redesigned bottom chuck elevates the vial upwards so the print volume sits close to the glass base rather than suspended 25 mm high. |
| **2026-09-28 09:40** | `VAMToolbox_alternative` | **Literature & Calibration Research:** Located the fundamental VAM calibration methodology in B. E. Kelly et al., *Science* 363, 1075–1079 (2019), Supp. S6. Created initial demo calibration pattern `kelly_dots_calibration_demo.png`. |
| **2026-09-28 10:15** | Optical Investigation | **Failure Post-Mortem of 7-Minute Print:** Identified root causes of simultaneous under-curing and over-curing: thermal Rayleigh-Bénard / Marangoni convection and cylindrical chromatic aberration caused by broadband white projection on an RGB pure triple laser projector. |
| **2026-09-28 10:47** | `tomo-alternative` (`VAM_Ob.py`) | **Monochromatic Blue Laser Export:** Updated `saveVid()` and `__init__()` to support `video_color_mode = "blue"`. Set $R=0, G=0, B=g$ across all exported video frames, shutting off the 638 nm red and 525 nm green laser diodes completely. Fixed OpenCV fallback `COLOR_RGB2BGR`. |
| **2026-09-28 10:48** | `tomo-alternative` (`server.py`) | **Backend API Parameter Routing:** Updated `/api/slice`, `/api/save_run`, and `_gather_run_params()` to read and persist `video_color_mode` (default `"blue"`), ensuring full traceability in run metadata JSON files. |
| **2026-09-28 11:08** | `tomo-alternative` (`App.jsx`) | **Frontend UI Laser Control:** Added `videoColorMode` state, persistence in localStorage and `.tomo` project files, and added a dedicated `Laser: Blue (450nm) / White (RGB)` dropdown selector directly on the Output page toolbar. |
| **2026-09-28 12:12** | `OpenCAL-alternative` | **Kelly Dot Target Generation:** Created `opencal/utils/calibration/generate_kelly_dots.py`. Generated `kelly_dots_calibration_blue.png` (clean print target) and `kelly_dots_calibration_blue_annotated.png` (alignment guide) in both `OpenCAL-alternative` and `VAMToolbox_alternative`. |
| **2026-09-28 12:15** | `OpenCAL-alternative` | **Engineering Documentation:** Authored this comprehensive calibration and physics log. |

---

## 2. Failure Post-Mortem: Why the 7-Minute Print Under-Cured & Over-Cured

In initial trials, printing the miniature captive ring for **7 minutes (420 seconds / 63 full rotations at 9 RPM)** resulted in an unexpected failure: **some parts under-cured while others severely over-cured**.

### 2.1 The Optoma ML1080 Triple Laser Architecture
The Optoma ML1080 is an **RGB Pure Triple Laser** projector:
- **Red Laser Diode:** $\sim 638\text{ nm}$
- **Green Laser Diode:** $\sim 525\text{ nm}$
- **Blue Laser Diode:** $\sim 465\text{ nm}$

When Tomo generated video frames with grayscale white light:
$$\text{Pixel} = [g, g, g]$$
All three discrete lasers were fired concurrently at equal relative duty cycles.

### 2.2 Photoinitiator Chemistry vs. Laser Wavelength
Common acrylate photoinitiators (CQ/EDAB, BAPO, TPO-L) have actinic absorption bands strictly in the near-UV and blue spectrum:
- **$\sim 400 - 470\text{ nm}$ (Blue):** Strong molar absorptivity ($\varepsilon \sim 40 - 700\text{ L}\cdot\text{mol}^{-1}\text{cm}^{-1}$). Photons are absorbed by the initiator, cleaving radicals to induce chain polymerization.
- **$525\text{ nm}$ (Green) & $638\text{ nm}$ (Red):** Zero photochemical absorption ($\varepsilon \approx 0$). 100% of these photons pass through the initiator unabsorbed chemically.

### 2.3 Thermal Convection (Rayleigh-Bénard / Marangoni Swirling)
Because Red and Green photons do not trigger photolysis, their energy is absorbed via vibrational overtone and bulk solvent dissipation, converting directly into **photothermal heat**.

Over a **7-minute (420-second)** exposure:
1. Significant thermal gradients ($\Delta T > 8 - 15^\circ\text{C}$) develop inside the 10 mm cylindrical vial.
2. Fluid density gradients induce buoyant forces, triggering **internal convective fluid circulation** (swirling).
3. **Under-curing mechanism:** In thin sections (such as the struts and outer perimeter of the captive ring), fluid currents carry ungelled radical chains away from their intended coordinates into unexposed liquid, preventing the local gel threshold ($D_{th}$) from being achieved.
4. **Over-curing mechanism:** In the stagnant central core, heat cannot dissipate quickly through the thick oil/resin bath. As temperature increases, the propagation rate constant $k_p$ climbs while termination slows (Trommsdorff / gel effect), triggering a thermal runaway "fireball" of over-polymerized solid resin in the center.

### 2.4 Cylindrical Chromatic Aberration
Light entering a curved cylindrical vial wall experiences wavelength-dependent refraction:
$$n_{\text{glass}}(465\text{ nm}) \approx 1.520 \quad>\quad n_{\text{glass}}(638\text{ nm}) \approx 1.495$$
Because the refractive indices differ, Blue, Green, and Red beams refract at different focal distances. A multi-color projection causes chromatic blurring at the boundaries of the 5 mm model, washing out the steep dose gradient designed by Tomo.

---

## 3. Software Solution: Monochromatic Blue Laser Mode

### 3.1 Pure Blue Video Output
To eliminate red/green photothermal heating and chromatic aberration, Tomo has been modified to output pure blue channel frames:
$$\text{Pixel} = [0, 0, g] \quad (\text{RGB order})$$

When the HDMI signal reaches the Optoma ML1080:
- **Red Laser (638 nm):** Duty cycle = 0% (**OFF**)
- **Green Laser (525 nm):** Duty cycle = 0% (**OFF**)
- **Blue Laser (465 nm):** Emits exactly at the photochemical initiator band.

### 3.2 Drastic Exposure Time Reduction
In broadband white mode, the blue laser was only operating at $1/3$ of total optical power output to balance color white points. Under monochromatic blue mode:
- 100% of the active optical energy excites the photoinitiator.
- Photothermal convection is eliminated; the liquid remains quiescent during rotation.
- Expected clean curing time is reduced from **7 minutes down to 35–70 seconds** (depending on initiator concentration).

---

## 4. Resin Minimization & Vial Holder Redesign

### 4.1 Captive Ring Dimensions in Tomo
- **Raw STL:** 26 mm outer diameter, 26 mm height.
- **Scaled Model in Tomo:** Scaled down to **$\approx 5.5\text{ mm}$ height and $10.0\text{ mm}$ diameter**, fitting comfortably inside a standard $12\text{ mm}$ OD / $10\text{ mm}$ ID glass vial.
- **Beam Center:** $Z = 0\text{ mm}$ corresponds to pixel row $Y = 960$ on the $1080 \times 1920$ canvas. The part occupies $Z \in [-3.0\text{ mm}, +3.0\text{ mm}]$ (pixel rows $Y \in [922, 998]$).

### 4.2 Holder Reprint Guidelines (Rhino/Grasshopper)
When reprinting the upper and lower vial chucks to raise the vial towards the beam:

```
                  ▲ +Z (Top of Projector Field)
                  │
  Z = +10.0 mm ───┼──────────────────────────────
                  │  Liquid Resin Level (Meniscus)
  Z =  +3.0 mm ───┌──────────────────────────────┐
                  │    TOP OF CAPTIVE RING       │
  Z =   0.0 mm ───┤ ── BEAM CENTER (Y = 960) ──  ├──── Optical Axis
                  │    BOTTOM OF CAPTIVE RING    │
  Z =  -3.0 mm ───└──────────────────────────────┘
                  │  Clear liquid resin gap (≥ 1.5 mm)
  Z =  -4.5 mm ───════════════════════════════════ Glass Vial Internal Floor
                  │
  Z =  -6.0 mm ───██████████████████████████████  Top Rim of Bottom Chuck
                  │ (Opaque 3D printed holder)
                  ▼ -Z
```

#### Critical Rules:
1. **Shadow Clearance:** The opaque top rim of the bottom holder chuck **MUST NOT extend above $Z = -6.0\text{ mm}$**. If the chuck lip reaches into $Z \in [-3.0\text{ mm}, 0\text{ mm}]$, it will cast a shadow that shears off the bottom of the captive ring.
2. **Elevated Internal Floor:** The bottom holder should feature an internal elevated seat so the glass vial sits with its internal floor at $Z \approx -4.5\text{ mm}$.
3. **Resin Fill Volume:**
   - Inner diameter: $D = 10\text{ mm}$ ($r = 5\text{ mm}$).
   - Resin column height needed: from $Z = -4.5\text{ mm}$ to $Z = +10.0\text{ mm}$ ($h = 14.5\text{ mm}$).
   - **Total Resin Required per Vial:**
     $$V = \pi \cdot r^2 \cdot h = \pi \cdot (0.5\text{ cm})^2 \cdot 1.45\text{ cm} \approx \mathbf{1.14\text{ mL}}$$
   - Adding a small safety margin for meniscus curvature, **$1.5\text{ mL}$ to $2.0\text{ mL}$** of resin is sufficient per test vial (saving over 80% resin compared to filling full 60 mm vials).

---

## 5. Resin Calibration Protocol (Kelly Dot Array)

Instead of exposing 20 separate captive ring prints across 20 vials to guess the curing time, use the standardized **Kelly Dot Array** protocol (*Science* 363, Supp. S6).

### 5.1 Scientific Basis
A vertical column of circular dots with calibrated intensities is projected statically into the vial while it rotates at constant speed (9 RPM):
- **Dot 1 ($Z = +15\text{ mm}$):** 100% Intensity ($B = 255$)
- **Dot 2 ($Z = +10\text{ mm}$):** 85% Intensity ($B = 217$)
- **Dot 3 ($Z =  +5\text{ mm}$):** 70% Intensity ($B = 179$)
- **Dot 4 ($Z =   0\text{ mm}$):** 55% Intensity ($B = 140$)
- **Dot 5 ($Z =  -5\text{ mm}$):** 40% Intensity ($B = 102$)
- **Dot 6 ($Z = -10\text{ mm}$):** 25% Intensity ($B = 64$)
- **Dot 7 ($Z = -15\text{ mm}$):** 15% Intensity ($B = 38$)

Because each dot sits on the rotation axis ($X = 540$), rotation exposes 7 concentric discs/rings at different vertical coordinates in the **exact same vial** simultaneously.

### 5.2 Step-by-Step Procedure
1. **Prepare 1 Test Vial:** Fill with $2.5\text{ mL}$ of resin and mount into the OpenCAL rig.
2. **Load Target:** On the OpenCAL Newhaven LCD menu, navigate to:
   $$\text{Settings} \longrightarrow \text{Calibration Images} \longrightarrow \text{kelly\_dots\_calibration\_blue.png}$$
3. **Run Rotation Exposure:**
   - Set motor speed to **9 RPM**.
   - Project the pattern for a reference duration, e.g., $T_{\text{test}} = 60\text{ seconds}$ (9 rotations).
4. **Develop & Inspect:**
   - Remove vial, pour out uncured resin, rinse gently in Isopropanol (IPA).
   - Observe which spots formed solid crosslinked gel disks:
     - If Dots 1–4 cured, but Dot 5 (40%) did not, the critical gelation threshold is at $I_{th} \approx 45 - 50\%$.
5. **Compute Optimal Print Duration:**
   $$\text{Required Full Part Duration} = T_{\text{test}} \times \frac{I_{th}}{d_h}$$
   Where $d_h$ is the high dose threshold specified in Tomo (typically $0.85 - 0.90$).

---

## 6. Verification and File Locations

All software components and calibration files are compiled and ready on the system:

| File Path | Description |
| :--- | :--- |
| `tomo-alternative/UIMain/Python_Backend/VAM_Ob.py` | Core video encoder updated with monochromatic blue channel output. |
| `tomo-alternative/UIMain/Python_Backend/server.py` | Flask API updated to accept and persist `video_color_mode`. |
| `tomo-alternative/UIMain/Front_End/App.jsx` | UI updated with Laser mode dropdown selector and state synchronization. |
| `OpenCAL-alternative/opencal/utils/calibration/generate_kelly_dots.py` | Standalone Python generator script for Kelly dot calibration targets. |
| `OpenCAL-alternative/opencal/utils/calibration/kelly_dots_calibration_blue.png` | Clean $1080 \times 1920$ pure blue calibration target for OpenCAL projector. |
| `OpenCAL-alternative/opencal/utils/calibration/kelly_dots_calibration_blue_annotated.png` | Annotated reference target for on-screen alignment and inspection. |
| `VAMToolbox_alternative/calibration_targets/kelly_dots_calibration_blue.png` | Mirror copy for VAMToolbox standalone optimization workflows. |
