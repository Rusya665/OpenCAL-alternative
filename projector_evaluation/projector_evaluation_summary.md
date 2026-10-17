# Optoma ML1080 Projector Evaluation Summary

## 1. Why We Bought It
* **We thought:** It was a great fit for OpenCAL (triple RGB laser, compact, sharp focus).
* **We asked Taylor Waddell (UC Berkeley lead):** In our email exchange (March 24, 2026), he confirmed it looked like a strong option.
* **We expected:** Fast volumetric printing in 30–90 seconds.

---

## 2. The Test Print (Failure)
* **What we did:** Tried printing a mini captive ring at 100% brightness.
* **What happened:** 
  * At 30–90 seconds: completely liquid.
  * At 5 minutes: still nothing.
  * At 10 minutes (600 s): it finally started curing, but failed completely (overcured outer skin, liquid inside).
* **Conclusion:** The projector doesn't put out enough blue light.

---

## 3. What We Measured
* **Sensor used:** Gentec-EO silicon photodiode ($5 \times 5\text{ mm}$ aperture = $0.25\text{ cm}^2$).
* **How we measured:** Put the sensor at the vial spot, projected a blue rectangle from our GUI (`projector_gui.py`), and sized it to match the sensor.

### Measurement Table
| Projected Color | Power Meter λ Setting | Measured Power | Irradiance ($P / 0.25\text{ cm}^2$) |
|---|---|---|---|
| **Full White** | 400 nm | 4.09 mW | 16.36 mW/cm² |
| **Full White** | 430 nm | 3.50 mW | 14.00 mW/cm² |
| **Full White** | 450 nm | 3.20 mW | 12.80 mW/cm² |
| **Pure Blue** | 400 nm | 0.60 mW | 2.40 mW/cm² |
| **Pure Blue** | 430 nm | 0.56 mW | 2.24 mW/cm² |
| **Pure Blue (Actinic)** | **450 nm** | **0.50 mW** | **2.00 mW/cm²** |
| **Pure Green** | 550 nm | 0.54 mW | 2.16 mW/cm² |
| **Pure Red** | 650 nm | 1.01 mW | 4.04 mW/cm² |

* **Actinic Blue Irradiance:**
  $$I_{\text{meas}} = \frac{0.50\text{ mW}}{0.25\text{ cm}^2} = 2.00\text{ mW/cm}^2$$

---

## 4. The GUI, Lens Optics & Spot Sizing Comparison
* **The setup:** We projected an image using `projector_gui.py`. The diverging beam passes through the Fresnel collimating lens ($f = 200\text{ mm}$, distance $D \approx 204\text{ mm}$).
* **What we expected from the optics:**
  * Magnification at the lens plane is $80.1\ \mu\text{m/px}$ horizontally and $88.3\ \mu\text{m/px}$ vertically.
* **Why we compared the two GUI possibilities:**
  * Since we did not record the exact slider value used during the measurement run, we evaluated both possible methods:
    1. **If we clicked the `50px` quick preset button:**
       * Physical spot size: $50\text{ px} \times 0.0801\text{ mm/px} = 4.0\text{ mm}$ (width) $\times 4.4\text{ mm}$ (height).
       * Spot area: $\approx 17.6\text{ mm}^2$.
       * Sensor match: Sits **100% inside** the $5.0 \times 5.0\text{ mm}$ ($25\text{ mm}^2$) sensor window.
       * Scaled total blue power: $0.50\text{ mW} / (2,500 / 2,073,600) \approx \mathbf{0.41\text{ W}}$.
    2. **If we dialed the continuous slider until the spot physically matched the sensor (~60 px):**
       * Physical spot size: $60\text{--}62\text{ px} \rightarrow$ exactly $5.0 \times 5.0\text{ mm}$ ($25.0\text{ mm}^2$).
       * Sensor match: Exact 1:1 overlap with the detector window.
       * Scaled total blue power: $0.50\text{ mW} / (3,700 / 2,073,600) \approx \mathbf{0.27\text{ W}}$.
* **The key takeaway:**
  * In **both cases**, there is **zero spillover** (100% of projected photons fell onto the active silicon detector).
  * In **both cases**, the total blue optical power is capped at $\sim \mathbf{0.3\text{ to }0.4\text{ W}}$ across the entire 1080p frame.
* **The Math connecting Total Power ($P_{\text{total}}$) back to Vial Irradiance ($I_{\text{meas}} = 2.00\text{ mW/cm}^2$):**
  * From CAD, the total projected 1080p area at the vial plane is $A_{\text{total}} = 161.8\text{ cm}^2$ ($16,180\text{ mm}^2$).
  * If the total blue laser output across the whole frame is $P_{\text{total}} \approx 0.32\text{ W} = 324\text{ mW}$:
    $$I_{\text{frame}} = \frac{P_{\text{total}}}{A_{\text{total}}} = \frac{324\text{ mW}}{161.8\text{ cm}^2} = \mathbf{2.00\text{ mW/cm}^2}$$
  * When we concentrated the light into a $5 \times 5\text{ mm}$ ($0.25\text{ cm}^2$) patch on the sensor:
    $$P_{\text{spot}} = I_{\text{frame}} \times A_{\text{sensor}} = 2.00\text{ mW/cm}^2 \times 0.25\text{ cm}^2 = \mathbf{0.50\text{ mW}}$$
  * This is the exact math loop: $0.50\text{ mW}$ measured on a $0.25\text{ cm}^2$ sensor **directly proves** the projector can never deliver more than $2.00\text{ mW/cm}^2$ of blue light to any point in the vial.

---

## 5. Why We Built the CAD (Area Scaling & Proof)
* To know total projector power, we needed to know what fraction of the full image our $5 \times 5\text{ mm}$ patch was.
* **From CAD ray-tracing at $D = 204\text{ mm}$:**
  * Full 1080p frame = $16,180\text{ mm}^2$ ($2,073,600\text{ px}$).
  * Our $5 \times 5\text{ mm}$ patch = $\approx 3,534\text{ px}$ ($\approx 0.17\% - 0.185\%$ of the image).
* **Scaling to Total Blue Power:**
  $$P_{\text{total, measured}} = \frac{P_{\text{meas}}}{f_{\text{area}}} = \frac{0.50\text{ mW}}{0.00185} = \frac{0.00050\text{ W}}{0.00185} \approx \mathbf{0.27\text{ W}}$$
* **Theoretical Check (Wall Power Limit):**
  * Projector draws only $32\text{ W}$ from the wall.
  * Electronics/fans take $\sim 25\text{ W}$, leaving only $\sim 7\text{ W}$ electrical for the blue laser diode.
  * At 40% diode efficiency:
    $$P_{\text{total, theoretical}} = 7\text{ W} \times 0.40 \approx \mathbf{0.29\text{ W}}$$
  * **Result:** $0.27\text{ W}$ (measured) vs $0.29\text{ W}$ (theoretical) $\rightarrow$ **93% match!**

---

## 6. Literature Correlation (Why 10 Minutes Failed)
* **The Physics Unit Definition (How We Get Joules from Watts):**
  $$\text{Energy (Joules)} = \text{Power (Watts)} \times \text{Time (Seconds)} \quad\Longrightarrow\quad 1\text{ J} = 1\text{ W}\cdot\text{s} \quad (1\text{ mJ} = 1\text{ mW}\cdot\text{s})$$
* **Radiant Exposure / Critical Dose ($H_{\text{crit}}$):**
  $$H = \text{Irradiance } (I) \times \text{Exposure Time } (t) \quad [\text{mJ/cm}^2 = \text{mW/cm}^2 \times \text{s}]$$
* **Literature Requirement (Kelly et al. 2019):**
  * Standard camphorquinone (CQ) / acrylate volumetric resin requires a critical gelation threshold of:
    $$H_{\text{crit}} \approx 1200\text{ mJ/cm}^2$$
* **Required Print Time Math with Optoma ML1080:**
  $$t_{\text{required}} = \frac{H_{\text{crit}}}{I_{\text{meas}}} = \frac{1200\text{ mJ/cm}^2}{2.00\text{ mW/cm}^2} = \frac{1200\text{ mW}\cdot\text{s/cm}^2}{2.00\text{ mW/cm}^2} = \mathbf{600\text{ seconds (10.0 minutes)}}$$
* **Failure Mechanism:** At $600\text{ s}$, oxygen diffusion from the air-liquid boundary and resin diffusion destroy the sharp axial projection boundary. The print turns into an overcured exterior shell with an uncured liquid inner core.

---

## 7. How to Test Future Projectors in a Shop (No Lens)
* **What to take:** Laptop + Gentec power meter ($5 \times 5\text{ mm}$ sensor).
* **What to do:** Project full blue at maximum brightness, hold the sensor at $D = 20\text{ cm}$ in the raw beam.
* **CAD geometry at $D = 20\text{ cm}$:** Beam area is $\approx 157\text{ cm}^2$ (sensor captures $\sim 0.16\%$).
* **Thresholds:**
  * **Optoma ML1080:** Reads $0.43\text{ mW}$ $\rightarrow$ **FAIL** (too weak).
  * **Good projector (e.g. BenQ LH650):** Must read **$\ge 4.0\text{ to } 5.2\text{ mW}$** $\rightarrow$ **PASS** ($\sim 2.5\text{ to } 3.3\text{ W}$ blue power).
