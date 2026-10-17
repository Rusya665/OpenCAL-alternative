import math

diags = [60, 70, 80, 90, 100, 120, 130, 140, 150]
nexigo_raw_ft = {60: 5.25, 80: 7.07, 100: 8.81, 120: 10.66, 130: 11.55, 140: 12.37, 150: 13.29}

optoma_dm = {60: 1.60, 70: 1.87, 80: 2.13, 90: 2.40, 100: 2.67, 120: 3.20, 150: 3.99}
optoma_hd = {60: 0.037, 70: 0.044, 80: 0.050, 90: 0.056, 100: 0.062, 120: 0.075, 150: 0.093}

print("Diagonal | Width (m) | Height (m) | Width (in) | Height (in) | NexiGo D (m) | NexiGo D (in) | NexiGo Hd (m) | NexiGo Hd (in) | Optoma D (m) | Optoma Hd (m)")
print("-" * 140)

for d in diags:
    w_in = 16.0 / math.sqrt(337) * d
    h_in = 9.0 / math.sqrt(337) * d
    w_m = w_in * 0.0254
    h_m = h_in * 0.0254

    if d in nexigo_raw_ft:
        d_ft = nexigo_raw_ft[d]
    else:
        d_ft = (nexigo_raw_ft[d-10] + nexigo_raw_ft[d+10]) / 2.0

    d_m = d_ft * 0.3048
    d_in = d_ft * 12.0
    hd_m = 0.05 * h_m
    hd_in = 0.05 * h_in

    opt_d = optoma_dm.get(d, "-")
    opt_h = optoma_hd.get(d, "-")
    
    print(f"{d:3d}\"     | {w_m:9.2f} | {h_m:10.2f} | {w_in:10.2f} | {h_in:11.2f} | {d_m:12.2f} | {d_in:13.2f} | -{hd_m:.3f}~{hd_m:.3f} | -{hd_in:.2f}~{hd_in:.2f} | {str(opt_d):12} | -{str(opt_h)}~{str(opt_h)}")

# Now angles and CAD ray vectors:
print("\n=== OPTICAL RAY GEOMETRY COMPARISON ===")
# For 1m projection distance:
tr_nexigo = 1.213 # average throw ratio
tr_optoma = 1.203 # standard throw ratio

# In 16:9, let W = 1.0, H = 9/16 = 0.5625
# Distance D = TR * W = 1.213
# Horizontal half angle:
theta_h_nexigo = math.degrees(math.atan(0.5 / tr_nexigo))
theta_h_optoma = math.degrees(math.atan(0.5 / tr_optoma))

# In 100% offset, the optical axis is aligned with the bottom edge (or top edge).
# That means the ray angles in the vertical plane go from 0 deg (bottom ray) to theta_v_full (top ray)!
# Or if offset Hd = 0, the bottom ray is along the optical axis (angle = 0 deg), and top ray is at atan(H / D) = atan(0.5625 / 1.213)
theta_v_top_nexigo = math.degrees(math.atan((9/16) / tr_nexigo))
theta_v_top_optoma = math.degrees(math.atan((9/16) / tr_optoma))

print(f"NexiGo: Horizontal Half-Angle = {theta_h_nexigo:.2f} deg (Full H-FOV = {2*theta_h_nexigo:.2f} deg)")
print(f"NexiGo: Vertical Angle (Bottom Ray = 0.0 deg, Top Ray = {theta_v_top_nexigo:.2f} deg, Full V-FOV = {theta_v_top_nexigo:.2f} deg)")
print(f"Optoma: Horizontal Half-Angle = {theta_h_optoma:.2f} deg (Full H-FOV = {2*theta_h_optoma:.2f} deg)")
print(f"Optoma: Vertical Angle (Bottom Ray = 0.0 deg, Top Ray = {theta_v_top_optoma:.2f} deg, Full V-FOV = {theta_v_top_optoma:.2f} deg)")

import json
print("\n=== RS232 KEYSTONE & FOCUS COMMANDS ===")
with open('ml1080_rs232_dump.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data if isinstance(data, list) else [item for sub in data.values() for item in sub]
for cmd in items:
    t = json.dumps(cmd).lower()
    if 'keystone' in t or 'focus' in t:
        print(f"{cmd.get('CommandName')} | Code: {cmd.get('SendCode')} | Desc: {cmd.get('ValueDesc')}")

