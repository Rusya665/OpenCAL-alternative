"""
projector_gui.py
================
Desktop GUI for VAM / CAL Projector Control & Optical Illumination.

Allows projecting:
1. Full-brightness solid color fields (White, Blue, Green, Red, Cyan, etc.)
2. Center Alignment Spot with shape control (Circle ⚪ or Rectangle ⬛) and
   full size/dimension control (1px to 500px) for optical centering,
   beam alignment, focal pinpointing, and vial axis calibration
3. Kelly et al. 2019 VAM 10-dot calibration patterns (shades of gray & white)
4. Brightness scaling (0 - 100%) and multi-monitor projector targeting

Features:
- Instant 1-click full brightness presets (Full White, Full Blue, Red, Green, etc.)
- Center Spot: Switch between Circle / Dot and Rectangle / Box
- Independent or locked Width & Height sliders (1px - 500px) with quick presets
- Optional faint alignment crosshair to help locate tiny pinhole spots
- Multi-monitor selector (automatically targets HDMI projector on secondary screen)
- Borderless true fullscreen projector window (ESC / Q / Space to blackout)
- Dual-window architecture: Control panel stays on laptop/primary screen while
  projector window sits on the projector display.
"""

import sys
import tkinter as tk
from tkinter import ttk, colorchooser
import numpy as np


# Multi-monitor enumeration via Win32 ctypes
def get_monitors():
    monitors = []
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            def _cb(hMonitor, hdcMonitor, lprcMonitor, dwData):
                r = lprcMonitor.contents
                monitors.append({
                    "id": len(monitors),
                    "x": r.left,
                    "y": r.top,
                    "width": r.right - r.left,
                    "height": r.bottom - r.top,
                    "name": f"Monitor {len(monitors)}: {r.right - r.left}x{r.bottom - r.top} at ({r.left}, {r.top})"
                })
                return True
            MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
            user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), 0)
        except Exception:
            pass

    if not monitors:
        monitors.append({"id": 0, "x": 0, "y": 0, "width": 1920, "height": 1080, "name": "Primary Display (Default)"})
    return monitors


class ProjectorWindow(tk.Toplevel):
    """Borderless fullscreen window dedicated to the projector output."""
    def __init__(self, master, monitor_info):
        super().__init__(master)
        self.monitor = monitor_info
        self.title("Projector Output")
        self.configure(bg="black", cursor="none")
        self.overrideredirect(True)  # Borderless fullscreen

        # Geometry for selected monitor
        x, y = self.monitor["x"], self.monitor["y"]
        w, h = self.monitor["width"], self.monitor["height"]
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Canvas for rendering patterns / solid colors / spots
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0, width=w, height=h)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Keyboard shortcuts
        self.bind("<Escape>", lambda e: self.blackout())
        self.bind("<q>", lambda e: self.blackout())
        self.bind("<space>", lambda e: self.blackout())

        self.current_mode = "solid"
        self.current_color = (0, 0, 0)
        self.brightness = 1.0

    def set_solid_color(self, r: int, g: int, b: int, brightness: float = 1.0):
        self.current_mode = "solid"
        scaled_r = int(min(255, max(0, r * brightness)))
        scaled_g = int(min(255, max(0, g * brightness)))
        scaled_b = int(min(255, max(0, b * brightness)))
        hex_color = f"#{scaled_r:02x}{scaled_g:02x}{scaled_b:02x}"

        self.canvas.delete("all")
        self.canvas.configure(bg=hex_color)
        self.configure(bg=hex_color)

    def draw_center_spot(
        self,
        shape: str = "circle",
        width: int = 10,
        height: int = 10,
        r: int = 255,
        g: int = 255,
        b: int = 255,
        brightness: float = 1.0,
        offset_x: int = 0,
        offset_y: int = 0,
        show_crosshair: bool = False
    ):
        """Draw a single controllable circle or rectangle spot centered on the display axis."""
        self.current_mode = "spot"
        self.canvas.delete("all")
        self.canvas.configure(bg="black")
        self.configure(bg="black")

        w, h = self.monitor["width"], self.monitor["height"]
        cx = (w // 2) + offset_x
        cy = (h // 2) + offset_y

        scaled_r = int(min(255, max(0, r * brightness)))
        scaled_g = int(min(255, max(0, g * brightness)))
        scaled_b = int(min(255, max(0, b * brightness)))
        hex_color = f"#{scaled_r:02x}{scaled_g:02x}{scaled_b:02x}"

        if show_crosshair:
            # Faint crosshair lines
            self.canvas.create_line(0, cy, w, cy, fill="#1e293b", width=1, dash=(4, 8))
            self.canvas.create_line(cx, 0, cx, h, fill="#1e293b", width=1, dash=(4, 8))

        rx = max(1, width // 2)
        ry = max(1, height // 2)

        if shape.lower() == "circle":
            if width <= 1 and height <= 1:
                self.canvas.create_rectangle(cx, cy, cx + 1, cy + 1, fill=hex_color, outline=hex_color)
            else:
                self.canvas.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=hex_color, outline="")
        else:  # rectangle
            self.canvas.create_rectangle(cx - rx, cy - ry, cx + rx, cy + ry, fill=hex_color, outline="")

    def draw_calibration_pattern(self, mode: str = "gray", color_mode: str = "blue", brightness: float = 1.0):
        self.current_mode = "pattern"
        self.canvas.delete("all")
        self.canvas.configure(bg="black")
        self.configure(bg="black")

        w, h = self.monitor["width"], self.monitor["height"]
        cx = w // 2

        num_dots = 10
        dot_radius = max(10, int(h * 0.02))
        span_y = h * 0.75
        y_start = (h - span_y) / 2.0
        y_step = span_y / (num_dots - 1)

        if mode == "white":
            raw_vals = [1.0] * num_dots
        else:
            raw_vals = list(np.linspace(1.0, 0.25, num_dots))

        for i in range(num_dots):
            cy = y_start + i * y_step
            v = raw_vals[i] * brightness
            val = int(round(255 * v))

            if color_mode == "blue":
                hex_c = f"#0000{val:02x}"
            else:
                hex_c = f"#{val:02x}{val:02x}{val:02x}"

            self.canvas.create_oval(
                cx - dot_radius, cy - dot_radius,
                cx + dot_radius, cy + dot_radius,
                fill=hex_c, outline=""
            )

    def blackout(self):
        self.set_solid_color(0, 0, 0, 1.0)


class ProjectorControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OpenCAL / TOMO Projector Illumination Studio")
        self.geometry("660x900")
        self.minsize(580, 780)
        self.configure(bg="#121316")

        self.monitors = get_monitors()
        # Default to secondary monitor if available (the projector), else primary
        default_mon_idx = 1 if len(self.monitors) > 1 else 0
        self.selected_monitor_idx = tk.IntVar(value=default_mon_idx)

        self.brightness_var = tk.IntVar(value=100)
        self.active_color = (255, 255, 255)
        self.active_type = "solid"

        # Center Spot state (Circle or Rectangle)
        self.spot_shape_var = tk.StringVar(value="circle")  # "circle" or "rectangle"
        self.spot_w_var = tk.IntVar(value=10)
        self.spot_h_var = tk.IntVar(value=10)
        self.spot_lock_var = tk.BooleanVar(value=True)      # Lock 1:1 (square/circle)
        self.spot_color = (255, 255, 255)                  # Default white
        self.spot_crosshair_var = tk.BooleanVar(value=False)
        self.spot_offset_x_var = tk.IntVar(value=0)
        self.spot_offset_y_var = tk.IntVar(value=0)

        self.proj_win = None
        self._build_ui()
        self.open_projector_window()

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        main_frame = tk.Frame(self, bg="#121316")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = tk.Frame(main_frame, bg="#1a1c23", padx=16, pady=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="📽️ Projector Optical Illumination & Alignment", font=("Segoe UI", 15, "bold"), fg="#38bdf8", bg="#1a1c23").pack(anchor="w")
        tk.Label(hdr, text="Project full-brightness fields, center circle/rectangle alignment spots, and VAM calibration patterns.", font=("Segoe UI", 9), fg="#94a3b8", bg="#1a1c23").pack(anchor="w")

        # 1. Monitor Selector Card
        mon_card = tk.LabelFrame(main_frame, text=" 🖥️ Target Projector / Display ", font=("Segoe UI", 10, "bold"), fg="#e2e8f0", bg="#1e2029", padx=12, pady=8)
        mon_card.pack(fill=tk.X, padx=14, pady=6)

        mon_options = [m["name"] for m in self.monitors]
        mon_combo = ttk.Combobox(mon_card, values=mon_options, state="readonly", font=("Segoe UI", 9))
        mon_combo.current(self.selected_monitor_idx.get())
        mon_combo.pack(fill=tk.X, pady=2)
        mon_combo.bind("<<ComboboxSelected>>", lambda e: self.on_monitor_changed(mon_combo.current()))

        btn_row = tk.Frame(mon_card, bg="#1e2029")
        btn_row.pack(fill=tk.X, pady=4)
        tk.Button(btn_row, text="🔄 Reposition Projector Window", bg="#334155", fg="#f8fafc", font=("Segoe UI", 9), relief=tk.FLAT, padx=10, pady=4, command=self.open_projector_window).pack(side=tk.LEFT)
        tk.Button(btn_row, text="⬛ Blackout (Off)", bg="#b91c1c", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=14, pady=4, command=self.do_blackout).pack(side=tk.RIGHT)

        # 2. Center Alignment Spot Card (Circle or Rectangle)
        spot_card = tk.LabelFrame(main_frame, text=" 🎯 Center Alignment Spot (Circle / Rectangle) ", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e2029", padx=12, pady=8)
        spot_card.pack(fill=tk.X, padx=14, pady=6)

        # Row 1: Action + Shape Selector + Color
        s_top = tk.Frame(spot_card, bg="#1e2029")
        s_top.pack(fill=tk.X, pady=2)

        tk.Button(s_top, text="🎯 Project Spot", bg="#0284c7", fg="#ffffff", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=12, pady=5, cursor="hand2", command=self.activate_center_spot).pack(side=tk.LEFT, padx=(0, 6))

        # Shape buttons: Circle vs Rectangle
        self.btn_shape_circle = tk.Button(s_top, text="🔘 Circle", bg="#0369a1", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=8, pady=5, command=lambda: self.set_spot_shape("circle"))
        self.btn_shape_circle.pack(side=tk.LEFT, padx=2)

        self.btn_shape_rect = tk.Button(s_top, text="⬛ Rectangle", bg="#334155", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=8, pady=5, command=lambda: self.set_spot_shape("rectangle"))
        self.btn_shape_rect.pack(side=tk.LEFT, padx=2)

        tk.Button(s_top, text="⚪ White", bg="#475569", fg="#ffffff", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=6, pady=5, command=lambda: self.set_spot_color((255, 255, 255))).pack(side=tk.LEFT, padx=(8, 2))
        tk.Button(s_top, text="🔵 Blue", bg="#1d4ed8", fg="#ffffff", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=6, pady=5, command=lambda: self.set_spot_color((0, 0, 255))).pack(side=tk.LEFT, padx=2)
        tk.Button(s_top, text="🟢 Green", bg="#15803d", fg="#ffffff", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=6, pady=5, command=lambda: self.set_spot_color((0, 255, 0))).pack(side=tk.LEFT, padx=2)
        tk.Button(s_top, text="🔴 Red", bg="#b91c1c", fg="#ffffff", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=6, pady=5, command=lambda: self.set_spot_color((255, 0, 0))).pack(side=tk.LEFT, padx=2)

        # Row 2: Width Slider
        w_row = tk.Frame(spot_card, bg="#1e2029")
        w_row.pack(fill=tk.X, pady=(6, 2))

        tk.Label(w_row, text="Width (px):", font=("Segoe UI", 9, "bold"), fg="#e2e8f0", bg="#1e2029", width=10, anchor="w").pack(side=tk.LEFT)
        self.lbl_spot_w = tk.Label(w_row, text="10 px", font=("Segoe UI", 9, "bold"), fg="#38bdf8", bg="#1e2029", width=7, anchor="e")
        self.lbl_spot_w.pack(side=tk.RIGHT)

        slider_w = ttk.Scale(w_row, from_=1, to=500, variable=self.spot_w_var, orient=tk.HORIZONTAL, command=lambda v: self.on_dim_slider_change("w", v))
        slider_w.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # Row 3: Height Slider
        h_row = tk.Frame(spot_card, bg="#1e2029")
        h_row.pack(fill=tk.X, pady=2)

        tk.Label(h_row, text="Height (px):", font=("Segoe UI", 9, "bold"), fg="#e2e8f0", bg="#1e2029", width=10, anchor="w").pack(side=tk.LEFT)
        self.lbl_spot_h = tk.Label(h_row, text="10 px", font=("Segoe UI", 9, "bold"), fg="#38bdf8", bg="#1e2029", width=7, anchor="e")
        self.lbl_spot_h.pack(side=tk.RIGHT)

        slider_h = ttk.Scale(h_row, from_=1, to=500, variable=self.spot_h_var, orient=tk.HORIZONTAL, command=lambda v: self.on_dim_slider_change("h", v))
        slider_h.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # Row 4: Quick Presets + Lock 1:1 Checkbox
        opt_row = tk.Frame(spot_card, bg="#1e2029")
        opt_row.pack(fill=tk.X, pady=4)

        chk_lock = tk.Checkbutton(opt_row, text="Lock 1:1 (Square / Circle)", variable=self.spot_lock_var, font=("Segoe UI", 8, "bold"), fg="#cbd5e1", bg="#1e2029", selectcolor="#0f172a", activebackground="#1e2029", activeforeground="#38bdf8", command=self.on_lock_toggle)
        chk_lock.pack(side=tk.LEFT, padx=(0, 8))

        presets_dims = [
            ("1px", 1),
            ("5px", 5),
            ("10px", 10),
            ("25px", 25),
            ("50px", 50),
            ("100px", 100),
            ("200px", 200),
        ]
        for label, sz in presets_dims:
            tk.Button(opt_row, text=label, bg="#334155", fg="#f8fafc", font=("Segoe UI", 8), relief=tk.FLAT, padx=4, pady=2, command=lambda s=sz: self.set_spot_size_preset(s)).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        # Row 5: Crosshair option
        chk_ch = tk.Checkbutton(spot_card, text="Show Faint Optical Crosshair Guide", variable=self.spot_crosshair_var, font=("Segoe UI", 8), fg="#94a3b8", bg="#1e2029", selectcolor="#0f172a", activebackground="#1e2029", activeforeground="#38bdf8", command=self.apply_current_state)
        chk_ch.pack(anchor="w", pady=(2, 4))

        # 3. Full Brightness Presets Card
        preset_card = tk.LabelFrame(main_frame, text=" ⚡ Full Brightness Solid Illumination (100% Power) ", font=("Segoe UI", 10, "bold"), fg="#e2e8f0", bg="#1e2029", padx=12, pady=8)
        preset_card.pack(fill=tk.X, padx=14, pady=6)

        grid_frame = tk.Frame(preset_card, bg="#1e2029")
        grid_frame.pack(fill=tk.X)

        presets = [
            ("⚪ Full White", "#ffffff", "#000000", (255, 255, 255)),
            ("🔵 Full Blue (ML1080 Laser)", "#2563eb", "#ffffff", (0, 0, 255)),
            ("🟢 Full Green", "#16a34a", "#ffffff", (0, 255, 0)),
            ("🔴 Full Red", "#dc2626", "#ffffff", (255, 0, 0)),
            ("🌊 Full Cyan", "#0891b2", "#ffffff", (0, 255, 255)),
            ("🌸 Full Magenta", "#c026d3", "#ffffff", (0, 255, 255)),
            ("🟡 Full Yellow", "#ca8a04", "#ffffff", (255, 255, 0)),
            ("🎨 Custom Color...", "#475569", "#ffffff", None),
        ]

        for i, (label, bg_c, fg_c, rgb) in enumerate(presets):
            row, col = divmod(i, 2)
            cmd = (lambda r=rgb: self.set_solid_color_preset(r)) if rgb else self.choose_custom_color
            btn = tk.Button(grid_frame, text=label, bg=bg_c, fg=fg_c, font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=10, pady=6, cursor="hand2", command=cmd)
            btn.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)

        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        # 4. Brightness Slider Card
        bright_card = tk.LabelFrame(main_frame, text=" 💡 Optical Brightness / Power Scaling ", font=("Segoe UI", 10, "bold"), fg="#e2e8f0", bg="#1e2029", padx=12, pady=8)
        bright_card.pack(fill=tk.X, padx=14, pady=6)

        sl_row = tk.Frame(bright_card, bg="#1e2029")
        sl_row.pack(fill=tk.X)

        self.lbl_bright = tk.Label(sl_row, text="100%", font=("Segoe UI", 11, "bold"), fg="#38bdf8", bg="#1e2029", width=5)
        self.lbl_bright.pack(side=tk.RIGHT)

        slider = ttk.Scale(sl_row, from_=0, to=100, variable=self.brightness_var, orient=tk.HORIZONTAL, command=self.on_brightness_change)
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        # Quick Brightness Buttons
        q_row = tk.Frame(bright_card, bg="#1e2029")
        q_row.pack(fill=tk.X, pady=(4, 2))
        for pct in [10, 25, 50, 75, 100]:
            tk.Button(q_row, text=f"{pct}%", bg="#334155", fg="#f8fafc", font=("Segoe UI", 8), relief=tk.FLAT, padx=8, pady=2, command=lambda p=pct: self.set_brightness_pct(p)).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        # 5. Kelly et al. Calibration Patterns Card
        cal_card = tk.LabelFrame(main_frame, text=" 🎯 Kelly et al. 2019 VAM Calibration Patterns ", font=("Segoe UI", 10, "bold"), fg="#e2e8f0", bg="#1e2029", padx=12, pady=8)
        cal_card.pack(fill=tk.X, padx=14, pady=6)

        cal_grid = tk.Frame(cal_card, bg="#1e2029")
        cal_grid.pack(fill=tk.X)

        cal_btns = [
            ("🔘 10 Dots: Shades of Gray (Blue Mode)", lambda: self.set_pattern("gray", "blue")),
            ("⚪ 10 Dots: Uniform White (Blue Mode)", lambda: self.set_pattern("white", "blue")),
            ("🔘 10 Dots: Shades of Gray (Mono/RGB)", lambda: self.set_pattern("gray", "grey")),
            ("⚪ 10 Dots: Uniform White (Mono/RGB)", lambda: self.set_pattern("white", "grey")),
        ]

        for i, (text, cmd) in enumerate(cal_btns):
            row, col = divmod(i, 2)
            btn = tk.Button(cal_grid, text=text, bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=6, pady=5, cursor="hand2", command=cmd)
            btn.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)

        cal_grid.columnconfigure(0, weight=1)
        cal_grid.columnconfigure(1, weight=1)

        # Status Footer
        self.status_lbl = tk.Label(main_frame, text="Active: Full White at 100% Brightness | ESC/Space in projector to blackout", font=("Segoe UI", 9), fg="#94a3b8", bg="#121316", pady=6)
        self.status_lbl.pack(side=tk.BOTTOM, fill=tk.X)

    def open_projector_window(self):
        if self.proj_win and self.proj_win.winfo_exists():
            self.proj_win.destroy()

        idx = self.selected_monitor_idx.get()
        mon = self.monitors[min(idx, len(self.monitors) - 1)]
        self.proj_win = ProjectorWindow(self, mon)
        self.apply_current_state()

    def on_monitor_changed(self, idx):
        self.selected_monitor_idx.set(idx)
        self.open_projector_window()

    def set_solid_color_preset(self, rgb):
        self.active_color = rgb
        self.active_type = "solid"
        self.apply_current_state()

    def choose_custom_color(self):
        col = colorchooser.askcolor(title="Select Illumination Color", initialcolor="#ffffff")
        if col and col[0]:
            r, g, b = [int(c) for c in col[0]]
            self.set_solid_color_preset((r, g, b))

    def activate_center_spot(self):
        self.active_type = "spot"
        self.apply_current_state()

    def set_spot_shape(self, shape):
        self.spot_shape_var.set(shape)
        if shape == "circle":
            self.btn_shape_circle.configure(bg="#0369a1")
            self.btn_shape_rect.configure(bg="#334155")
        else:
            self.btn_shape_circle.configure(bg="#334155")
            self.btn_shape_rect.configure(bg="#0369a1")
        self.active_type = "spot"
        self.apply_current_state()

    def set_spot_color(self, rgb):
        self.spot_color = rgb
        self.active_type = "spot"
        self.apply_current_state()

    def on_dim_slider_change(self, source, val):
        v = max(1, int(float(val)))
        if source == "w":
            self.lbl_spot_w.configure(text=f"{v} px")
            if self.spot_lock_var.get():
                self.spot_h_var.set(v)
                self.lbl_spot_h.configure(text=f"{v} px")
        elif source == "h":
            self.lbl_spot_h.configure(text=f"{v} px")
            if self.spot_lock_var.get():
                self.spot_w_var.set(v)
                self.lbl_spot_w.configure(text=f"{v} px")

        if self.active_type == "spot":
            self.apply_current_state()

    def on_lock_toggle(self):
        if self.spot_lock_var.get():
            w = self.spot_w_var.get()
            self.spot_h_var.set(w)
            self.lbl_spot_h.configure(text=f"{w} px")
            if self.active_type == "spot":
                self.apply_current_state()

    def set_spot_size_preset(self, sz):
        self.spot_w_var.set(sz)
        self.lbl_spot_w.configure(text=f"{sz} px")
        if self.spot_lock_var.get():
            self.spot_h_var.set(sz)
            self.lbl_spot_h.configure(text=f"{sz} px")
        self.active_type = "spot"
        self.apply_current_state()

    def set_pattern(self, mode, color_mode):
        self.active_type = f"pattern_{mode}_{color_mode}"
        self.apply_current_state()

    def on_brightness_change(self, val):
        pct = int(float(val))
        self.lbl_bright.configure(text=f"{pct}%")
        self.apply_current_state()

    def set_brightness_pct(self, pct):
        self.brightness_var.set(pct)
        self.lbl_bright.configure(text=f"{pct}%")
        self.apply_current_state()

    def do_blackout(self):
        if self.proj_win and self.proj_win.winfo_exists():
            self.proj_win.blackout()
        self.status_lbl.configure(text="Projector Blackout / OFF (Press any color or spot button to resume)")

    def apply_current_state(self):
        if not (self.proj_win and self.proj_win.winfo_exists()):
            return

        b = self.brightness_var.get() / 100.0

        if self.active_type == "solid":
            r, g, b_val = self.active_color
            self.proj_win.set_solid_color(r, g, b_val, brightness=b)
            self.status_lbl.configure(text=f"Projecting Solid RGB({r},{g},{b_val}) at {int(b*100)}% brightness")
        elif self.active_type == "spot":
            r, g, b_val = self.spot_color
            shape = self.spot_shape_var.get()
            w = self.spot_w_var.get()
            h = self.spot_h_var.get()
            show_ch = self.spot_crosshair_var.get()
            off_x = self.spot_offset_x_var.get()
            off_y = self.spot_offset_y_var.get()
            self.proj_win.draw_center_spot(
                shape=shape,
                width=w,
                height=h,
                r=r,
                g=g,
                b=b_val,
                brightness=b,
                offset_x=off_x,
                offset_y=off_y,
                show_crosshair=show_ch
            )
            col_name = "White" if (r, g, b_val) == (255, 255, 255) else ("Blue" if b_val == 255 and r == 0 else f"RGB({r},{g},{b_val})")
            shape_desc = f"Circle (Ø {w}px)" if shape == "circle" else f"Rectangle ({w}x{h}px)"
            self.status_lbl.configure(text=f"Projecting Center Spot: {shape_desc}, {col_name} at {int(b*100)}% brightness")
        elif self.active_type.startswith("pattern_"):
            parts = self.active_type.split("_")
            mode = parts[1]
            col_mode = parts[2]
            self.proj_win.draw_calibration_pattern(mode=mode, color_mode=col_mode, brightness=b)
            self.status_lbl.configure(text=f"Projecting Kelly et al. Pattern ({mode}, {col_mode}) at {int(b*100)}% brightness")


if __name__ == "__main__":
    app = ProjectorControlApp()
    app.mainloop()
