"""
generate_kelly_dots.py

Generates Kelly dot-array calibration targets for resin dose/exposure response calibration
in Computed Axial Lithography (CAL / VAM) as described in:
    B. E. Kelly et al., "Volumetric additive manufacturing via tomographic reconstruction",
    Science 363, 1075-1079 (2019), Supplementary Materials Section S6: "Resin response calibration".

Target Format:
- Portrait canvas: 1080 x 1920 (matching Optoma ML1080 triple-laser projector mounted 90° on its side)
- Pixel scale: 0.0801 mm/pixel (80.1 µm/px)
- Central optical rotation axis: X = 540 px
- Center of projected beam (Z = 0 mm): Y = 960 px
- 7 circular spots of 2.0 mm diameter spaced by 5.0 mm along the central axis (Z = +15 to -15 mm)
- Relative laser power intensities: 100%, 85%, 70%, 55%, 40%, 25%, 15%
- Monochromatic Blue Channel (450 nm): R=0, G=0, B=intensity
  Ensures Optoma RGB triple laser fires ONLY the blue laser diode, shutting off Red (638nm)
  and Green (525nm) diodes to eliminate thermal convection and chromatic focal aberration.

Outputs:
1. kelly_dots_calibration_blue.png:
   Clean printing target (pure central spots on black background).
   Safe for rotation at 9 RPM without casting stray concentric cylinder rings into resin.
2. kelly_dots_calibration_blue_annotated.png:
   Annotated reference with labels, scale bar, and center crosshair for display/inspection.
"""

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Canvas & optical setup
W, H = 1080, 1920
PX_SIZE_MM = 0.0801
PX_PER_MM = 1.0 / PX_SIZE_MM
CX = W // 2           # 540 px
CY = H // 2           # 960 px (Z = 0 mm)

DOT_DIAMETER_MM = 2.0
DOT_RADIUS_PX = int(round((DOT_DIAMETER_MM / 2.0) * PX_PER_MM))

# 7 spots: (z_offset_mm, percentage, 8-bit intensity)
SPOTS = [
    (+15.0, 100, 255),
    (+10.0,  85, 217),
    ( +5.0,  70, 179),
    (  0.0,  55, 140),
    ( -5.0,  40, 102),
    (-10.0,  25,  64),
    (-15.0,  15,  38),
]


def create_targets(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Clean Blue Calibration Target for Printing (No stray text on rotating resin)
    clean_img = Image.new("RGB", (W, H), (0, 0, 0))
    clean_draw = ImageDraw.Draw(clean_img)

    for z_mm, pct, b_val in SPOTS:
        # Tomo coordinates: +Z is up (decreasing Y in image coordinates)
        y_px = int(round(CY - z_mm * PX_PER_MM))
        clean_draw.ellipse(
            [CX - DOT_RADIUS_PX, y_px - DOT_RADIUS_PX, CX + DOT_RADIUS_PX, y_px + DOT_RADIUS_PX],
            fill=(0, 0, b_val),
            outline=None,
        )

    clean_path = out_dir / "kelly_dots_calibration_blue.png"
    clean_img.save(clean_path)
    print(f"Generated clean calibration target: {clean_path}")

    # 2. Annotated Blue Calibration Target for Display / Verification
    ann_img = clean_img.copy()
    ann_draw = ImageDraw.Draw(ann_img)

    # Fonts
    try:
        font_large = ImageFont.truetype("arial.ttf", 26)
        font_small = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Center axis indicator (dotted or thin blue line)
    ann_draw.line([(CX, 100), (CX, H - 100)], fill=(0, 0, 45), width=1)
    ann_draw.line([(100, CY), (W - 100, CY)], fill=(0, 0, 45), width=1)

    # Annotations next to each spot
    for z_mm, pct, b_val in SPOTS:
        y_px = int(round(CY - z_mm * PX_PER_MM))
        label_text = f"Z={z_mm:+4.1f}mm  |  {pct:3d}%  (B={b_val})"
        # Draw text to the right in blue
        ann_draw.text((CX + 35, y_px - 13), label_text, fill=(0, 0, 200), font=font_large)

    # Title & Metadata
    title_lines = [
        "OpenCAL / Tomo - Kelly Resin Response Calibration",
        "Ref: B. E. Kelly et al., Science 363, 1075-1079 (2019) Supp. S6",
        f"Canvas: {W}x{H} portrait  |  Scale: {PX_SIZE_MM*1000:.1f} µm/px",
        "Wavelength: Monochromatic Blue ~450 nm (R=0, G=0, B)",
        "Rotation speed: 9 RPM  |  Spots: 2.0 mm dia @ 5.0 mm pitch",
    ]
    y_text = 200
    for line in title_lines:
        ann_draw.text((120, y_text), line, fill=(0, 0, 180), font=font_small)
        y_text += 32

    # Scale bar (10 mm)
    sb_len_px = int(round(10.0 * PX_PER_MM))
    sb_x, sb_y = 120, 400
    ann_draw.line([(sb_x, sb_y), (sb_x + sb_len_px, sb_y)], fill=(0, 0, 255), width=4)
    ann_draw.text((sb_x, sb_y + 10), "10.0 mm scale", fill=(0, 0, 200), font=font_small)

    ann_path = out_dir / "kelly_dots_calibration_blue_annotated.png"
    ann_img.save(ann_path)
    print(f"Generated annotated calibration target: {ann_path}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    create_targets(script_dir)
