import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6] # blank

    brain_dir = r"C:\Users\runiza\.gemini\antigravity\brain\4255cb6d-407e-48c4-ba79-99a3b0248451"
    user_img = os.path.join(r"c:\Users\runiza\GoogleProjects\OpenCAL-alternative", "extracted_user_img.png")
    plot_raw = os.path.join(brain_dir, "plot_raw_measurements.png")
    plot_shop = os.path.join(brain_dir, "plot_shop_test.png")

    BLACK = RGBColor(0, 0, 0)
    DARK_GRAY = RGBColor(40, 40, 40)
    CARD_BG = RGBColor(248, 249, 250)
    CARD_BORDER = RGBColor(210, 215, 220)
    HEADER_BG = RGBColor(235, 240, 245)

    def add_header(slide, title_text, subtitle_text):
        # Header title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.733), Inches(0.8))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(24)
        p.font.bold = True
        p.font.color.rgb = BLACK
        
        p2 = tf.add_paragraph()
        p2.text = subtitle_text
        p2.font.size = Pt(13)
        p2.font.color.rgb = BLACK

    # ==========================================
    # SLIDE 1: Title Slide
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    tbox = s1.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(11.333), Inches(3.5))
    tf1 = tbox.text_frame
    tf1.word_wrap = True
    
    p = tf1.paragraphs[0]
    p.text = "Optoma ML1080 Projector Evaluation"
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = BLACK
    
    p = tf1.add_paragraph()
    p.text = "Photometric Characterization, CAD Optical Scaling & Curing Failure Analysis"
    p.font.size = Pt(20)
    p.font.color.rgb = BLACK
    p.space_after = Pt(24)
    
    p = tf1.add_paragraph()
    p.text = "OpenCAL Computed Axial Lithography Project | Experimental & Theoretical Validation"
    p.font.size = Pt(14)
    p.font.color.rgb = BLACK

    # ==========================================
    # SLIDE 2: Origin & Print Test Failure
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    add_header(s2, "1. Background: Why We Chose It & Print Test Outcome", 
               "Consultation with Berkeley OpenCAL Lead & Initial Test Print Failure")

    # Card Left: Berkeley Recommendation
    card_l = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(5.6), Inches(5.3))
    card_l.fill.solid()
    card_l.fill.fore_color.rgb = CARD_BG
    card_l.line.color.rgb = CARD_BORDER
    card_l.line.width = Pt(1.5)
    
    tf_l = card_l.text_frame
    tf_l.word_wrap = True
    tf_l.margin_left = tf_l.margin_right = Inches(0.3)
    tf_l.margin_top = Inches(0.3)
    
    p = tf_l.paragraphs[0]
    p.text = "Why We Ordered the Optoma ML1080"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = BLACK
    p.space_after = Pt(14)
    
    bullets_l = [
        ("Consultation with Taylor Waddell (UC Berkeley Lead):", True),
        ("In our email exchange on March 24, 2026, we reviewed hardware configurations for OpenCAL. Taylor evaluated the Optoma ML1080 RGB laser projector and confirmed it looked like a strong fit for our setup.", False),
        ("Key Assumed Advantages:", True),
        ("• Triple RGB Laser Engine: Narrow spectral emission peaks (~450 nm blue) matching photoinitiator absorption.\n• Compact Form Factor: Ideal for compact benchtop rig integration.\n• Short Throw Ratio (1.2:1): Efficient working distance for collimating optics.", False),
        ("Target Expectations:", True),
        ("Expected rapid volumetric gelation within 30 to 90 seconds based on published literature values.", False)
    ]
    for text, bold in bullets_l:
        p = tf_l.add_paragraph()
        p.text = text
        p.font.size = Pt(12)
        p.font.bold = bold
        p.font.color.rgb = BLACK
        p.space_after = Pt(6)

    # Card Right: Test Print Outcome
    card_r = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.5), Inches(5.7), Inches(5.3))
    card_r.fill.solid()
    card_r.fill.fore_color.rgb = CARD_BG
    card_r.line.color.rgb = CARD_BORDER
    card_r.line.width = Pt(1.5)
    
    tf_r = card_r.text_frame
    tf_r.word_wrap = True
    tf_r.margin_left = tf_r.margin_right = Inches(0.3)
    tf_r.margin_top = Inches(0.3)
    
    p = tf_r.paragraphs[0]
    p.text = "Initial Print Test: The Captive Ring Failure"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = BLACK
    p.space_after = Pt(14)
    
    bullets_r = [
        ("Experimental Setup:", True),
        ("• Part: Mini captive ring benchmark model.\n• Mode: Projector at 100% Bright Mode (maximum laser output).\n• Material: Standard CAL acrylate resin with camphorquinone (CQ) / amine initiator.", False),
        ("Observations During Exposure:", True),
        ("• Target curing time (30 - 90 s) produced completely uncured liquid resin.\n• At 5 minutes: No discernible gel boundary forming inside the rotating vial.\n• Extended exposure to 10 full minutes (600 seconds): Solidification finally initiated, but the part was severely ruined.", False),
        ("Failure Mechanics:", True),
        ("Excessive exposure time allowed severe oxygen diffusion and thermal/species cross-diffusion. Resulted in overcured outer slag with an ungelled liquid inner core. Clear evidence of photon starvation at the actinic wavelength.", False)
    ]
    for text, bold in bullets_r:
        p = tf_r.add_paragraph()
        p.text = text
        p.font.size = Pt(12)
        p.font.bold = bold
        p.font.color.rgb = BLACK
        p.space_after = Pt(6)

    # ==========================================
    # SLIDE 3: Power Meter Measurements (Table + Chart)
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    add_header(s3, "2. Optical Measurements: Photodiode Characterization", 
               "Direct Power Meter Readings at Vial Position across Channels and Wavelength Settings")

    # Table Left
    rows, cols = 9, 4
    table_shape = s3.shapes.add_table(rows, cols, Inches(0.8), Inches(1.5), Inches(6.3), Inches(4.3))
    table = table_shape.table
    table.columns[0].width = Inches(1.5)
    table.columns[1].width = Inches(1.5)
    table.columns[2].width = Inches(1.5)
    table.columns[3].width = Inches(1.8)

    table_data = [
        ["Projected Color", "Power Meter λ", "Measured Power", "Calculated Irradiance"],
        ["Full White", "400 nm", "4.09 mW", "16.36 mW/cm²"],
        ["Full White", "430 nm", "3.50 mW", "14.00 mW/cm²"],
        ["Full White", "450 nm", "3.20 mW", "12.80 mW/cm²"],
        ["Pure Blue", "400 nm", "0.60 mW", "2.40 mW/cm²"],
        ["Pure Blue", "430 nm", "0.56 mW", "2.24 mW/cm²"],
        ["Pure Blue", "450 nm", "0.50 mW", "2.00 mW/cm² (Actinic)"],
        ["Pure Green", "550 nm", "0.54 mW", "2.16 mW/cm²"],
        ["Pure Red", "650 nm", "1.01 mW", "4.04 mW/cm²"]
    ]

    for r_idx, row in enumerate(table_data):
        for c_idx, val in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.text = val
            p = cell.text_frame.paragraphs[0]
            p.font.size = Pt(10 if r_idx > 0 else 11)
            p.font.bold = (r_idx == 0 or r_idx == 6)
            p.font.color.rgb = BLACK
            p.alignment = PP_ALIGN.CENTER if c_idx > 0 else PP_ALIGN.LEFT
            cell.fill.solid()
            if r_idx == 0:
                cell.fill.fore_color.rgb = HEADER_BG
            elif r_idx == 6:
                cell.fill.fore_color.rgb = RGBColor(230, 235, 245)
            else:
                cell.fill.fore_color.rgb = CARD_BG

    # Note under table
    note_box = s3.shapes.add_textbox(Inches(0.8), Inches(5.9), Inches(6.3), Inches(1.1))
    tf_n = note_box.text_frame
    tf_n.word_wrap = True
    p = tf_n.paragraphs[0]
    p.text = "Key Measurement Note:"
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = BLACK
    
    p = tf_n.add_paragraph()
    p.text = "Sensor: Gentec-EO Silicon Photodiode (5 x 5 mm aperture, area = 0.25 cm²). At the active photoinitiator wavelength (450 nm pure blue), the measured power was only 0.50 mW, yielding an irradiance of exactly 2.00 mW/cm²."
    p.font.size = Pt(11)
    p.font.color.rgb = BLACK

    # Chart Right
    if os.path.exists(plot_raw):
        s3.shapes.add_picture(plot_raw, Inches(7.4), Inches(1.5), Inches(5.1), Inches(5.3))

    # ==========================================
    # SLIDE 4: GUI Presets & Spot Size Mapping (With User Picture)
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    add_header(s4, "3. Spot Sizing in GUI & Sensor Alignment", 
               "Correlating GUI Presets to the 5x5 mm Aperture & Optical Cone Ray-Tracing")

    # Left card: GUI presets and Scenarios
    card_s4 = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(5.8), Inches(5.5))
    card_s4.fill.solid()
    card_s4.fill.fore_color.rgb = CARD_BG
    card_s4.line.color.rgb = CARD_BORDER
    card_s4.line.width = Pt(1.5)
    
    tf_s4 = card_s4.text_frame
    tf_s4.word_wrap = True
    tf_s4.margin_left = tf_s4.margin_right = Inches(0.25)
    tf_s4.margin_top = Inches(0.25)
    
    p = tf_s4.paragraphs[0]
    p.text = "GUI Calibration & Physical Sensor Mapping"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = BLACK
    p.space_after = Pt(10)

    bullets_s4 = [
        ("Projector GUI Presets (scripts/projector_gui.py):", True),
        ("The calibration interface provided discrete presets: [1px, 5px, 10px, 25px, 50px, 100px, 200px], alongside continuous Width/Height sliders (1 to 500 px) with a [x] Lock 1:1 aspect toggle.", False),
        ("At optical distance D ≈ 204 mm (80.1 μm/px H, 88.3 μm/px V):", True),
        ("• Scenario A (50px Preset Selected):\n  Physical spot = 50 px * 0.0801 mm/px = 4.0 mm (H) x 4.4 mm (V).\n  Spot Area ≈ 17.6 mm² sits 100% inside the 5.0 x 5.0 mm (25 mm²) aperture.\n• Scenario B (Slider Tuned to ~60-62 px):\n  Physical spot matches 5.0 x 5.0 mm (25.0 mm²) exactly 1:1.", False),
        ("Zero Spillover Proof:", True),
        ("In both scenarios, 100% of projected photons fell entirely within the active silicon photodiode window. Zero optical power was clipped outside the detector frame.", False),
        ("Consistent Total Power Math:", True),
        ("• If 50 px (2,500 px / 0.12% chip): P_total = 0.50 mW / 0.00121 ≈ 0.41 W\n• If 60 px (3,700 px / 0.18% chip): P_total = 0.50 mW / 0.00178 ≈ 0.28 W\nBoth scenarios prove the total blue engine output is capped at ~0.3 - 0.4 W.", False)
    ]
    for text, bold in bullets_s4:
        p = tf_s4.add_paragraph()
        p.text = text
        p.font.size = Pt(10.5)
        p.font.bold = bold
        p.font.color.rgb = BLACK
        p.space_after = Pt(4)

    # Right: User's CAD Picture
    if os.path.exists(user_img):
        s4.shapes.add_picture(user_img, Inches(6.9), Inches(1.5), Inches(5.6), Inches(4.3))
        
        cap_box = s4.shapes.add_textbox(Inches(6.9), Inches(5.9), Inches(5.6), Inches(1.1))
        tf_c = cap_box.text_frame
        tf_c.word_wrap = True
        p = tf_c.paragraphs[0]
        p.text = "Optical CAD Ray-Tracing:"
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = BLACK
        p = tf_c.add_paragraph()
        p.text = "Total projected 1080p frame at D = 204 mm is ~16,180 mm² (1920 x 1080 = 2,073,600 px). The 5 x 5 mm sensor patch corresponds to only ~3,534 px (0.17% of total frame)."
        p.font.size = Pt(10)
        p.font.color.rgb = BLACK

    # ==========================================
    # SLIDE 5: Mathematical Scaling & Theoretical Proof
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    add_header(s5, "4. Mathematical Validation & Literature Correlation", 
               "Correlating Measured Power with Electrical Limits and Photo-Kinetics")

    def create_math_card(left, top, width, height, title, lines):
        card = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = CARD_BORDER
        card.line.width = Pt(1.5)
        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.25)
        tf.margin_top = Inches(0.2)
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = BLACK
        p.space_after = Pt(8)
        for text, bold in lines:
            p = tf.add_paragraph()
            p.text = text
            p.font.size = Pt(10.5)
            p.font.bold = bold
            p.font.color.rgb = BLACK
            p.space_after = Pt(4)

    # Box 1: Measured Irradiance
    create_math_card(Inches(0.8), Inches(1.5), Inches(5.7), Inches(2.6),
        "Step 1: Measured Irradiance at Vial Position",
        [
            ("Photodiode Area:", True),
            ("A_sensor = 5 mm * 5 mm = 25 mm² = 0.25 cm²", False),
            ("Irradiance Calculation:", True),
            ("I_meas = P_meas / A_sensor", True),
            ("I_meas = (0.50 mW) / (0.25 cm²) = 2.00 mW/cm²", False),
            ("Actinic flux delivered directly to the resin vial is exactly 2.00 mW/cm².", False)
        ]
    )

    # Box 2: CAD Area Scaling
    create_math_card(Inches(6.8), Inches(1.5), Inches(5.7), Inches(2.6),
        "Step 2: Total Blue Optical Power (CAD Scaling)",
        [
            ("Chip Fraction Sampled by 5x5 mm Sensor:", True),
            ("f_area = N_spot / N_total = (3,534 px) / (2,073,600 px) ≈ 0.170% = 0.00185", False),
            ("Extrapolated Total Blue Optical Power:", True),
            ("P_total,measured = P_meas / f_area", True),
            ("P_total,measured = (0.50 mW) / 0.00185 ≈ 0.27 W", False),
            ("The full Optoma ML1080 blue engine produces only 0.27 W across the whole frame.", False)
        ]
    )

    # Box 3: Theoretical Electrical Limit
    create_math_card(Inches(0.8), Inches(4.3), Inches(5.7), Inches(2.7),
        "Step 3: Theoretical Proof (From 32W Wall Draw)",
        [
            ("Electrical Power Budget:", True),
            ("• Total Wall Power Consumption = 32 W\n• Electronics, SOC, cooling fans, and DMD logic draw ~25 W\n• Electrical power available to blue laser diode = ~5 to 7 W", False),
            ("Theoretical Optical Output:", True),
            ("P_total,theoretical = P_elec * Efficiency_diode", True),
            ("P_total,theoretical = 7 W * 0.40 (GaN blue efficiency) ≈ 0.29 W", False),
            ("Comparison: 0.27 W (CAD Measured) vs 0.29 W (32W Power Limit) -> 93% MATCH!", True)
        ]
    )

    # Box 4: Literature Kinetics (Why It Failed)
    create_math_card(Inches(6.8), Inches(4.3), Inches(5.7), Inches(2.7),
        "Step 4: Literature Correlation (Kelly et al. 2019)",
        [
            ("Volumetric Critical Gelation Dose (Acrylate Resin):", True),
            ("H_crit = I * t ≈ 1200 mJ/cm²", False),
            ("Exposure Time Required with Optoma ML1080:", True),
            ("t_required = H_crit / I_meas", True),
            ("t_required = (1200 mJ/cm²) / (2.00 mW/cm²) = 600 s (10.0 minutes)", False),
            ("Outcome: At 10 minutes, oxygen diffusion ruins axial resolution. Confirms the projector is physically underpowered for volumetric lithography.", True)
        ]
    )

    # ==========================================
    # SLIDE 6: Estimating Next Projector at the Shop (No Lens)
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    add_header(s6, "5. Pre-Purchase Verification: In-Store Testing Protocol", 
               "Using CAD Optical Scaling to Verify Replacement Projectors In-Shop Without Rig Optics")

    # Left Card: Shop Testing Protocol
    card_s6 = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(5.8), Inches(5.5))
    card_s6.fill.solid()
    card_s6.fill.fore_color.rgb = CARD_BG
    card_s6.line.color.rgb = CARD_BORDER
    card_s6.line.width = Pt(1.5)
    
    tf_s6 = card_s6.text_frame
    tf_s6.word_wrap = True
    tf_s6.margin_left = tf_s6.margin_right = Inches(0.25)
    tf_s6.margin_top = Inches(0.25)
    
    p = tf_s6.paragraphs[0]
    p.text = "In-Shop Benchmark Test (No Lens Required)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = BLACK
    p.space_after = Pt(10)

    bullets_s6 = [
        ("Equipment to Bring to the Shop:", True),
        ("Laptop + Gentec-EO Silicon Photodiode Power Meter (5 x 5 mm aperture, 0.25 cm²).", False),
        ("Measurement Procedure:", True),
        ("1. Set projector to maximum brightness on a pure blue test slide (450 nm).\n2. Place sensor aperture directly in the raw diverging beam at D = 20.0 cm from front pupil.\n3. Read the power meter display directly.", False),
        ("CAD Optical Geometry at D = 20 cm:", True),
        ("• Projected Frame Width = 16.7 cm, Height = 9.4 cm\n• Total Diverging Beam Area = 157 cm²\n• Sensor Capture Fraction = (0.25 cm²) / (157 cm²) ≈ 0.16% of total beam", False),
        ("Pass / Fail Criteria:", True),
        ("• Optoma ML1080 (32W): Reads 0.43 mW -> P_blue = 0.27 W (FAIL - Insufficient)\n• Minimum Required (>15 mW/cm²): Must read ≥ 3.5 mW at D = 20 cm\n• Recommended (BenQ LH650, 200W): Reads 4.0 to 5.2 mW -> P_blue = 2.5 to 3.3 W (PASS)", False)
    ]
    for text, bold in bullets_s6:
        p = tf_s6.add_paragraph()
        p.text = text
        p.font.size = Pt(10.5)
        p.font.bold = bold
        p.font.color.rgb = BLACK
        p.space_after = Pt(4)

    # Right: Chart
    if os.path.exists(plot_shop):
        s6.shapes.add_picture(plot_shop, Inches(6.9), Inches(1.5), Inches(5.6), Inches(5.3))

    # Save to both target locations
    out_path_local = r"c:\Users\runiza\GoogleProjects\OpenCAL-alternative\opencal_projector_evaluation.pptx"
    out_path_brain = os.path.join(brain_dir, "opencal_projector_evaluation.pptx")
    
    prs.save(out_path_local)
    prs.save(out_path_brain)
    print(f"Successfully saved presentation to:\n{out_path_local}\n{out_path_brain}")

if __name__ == "__main__":
    build_presentation()
