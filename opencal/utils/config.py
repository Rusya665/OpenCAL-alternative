from pathlib import Path
import json
from typing import Any, final


BASE_CFG_PATH = Path(__file__).with_suffix(".json")
LOCAL_CFG_PATH = Path(__file__).parent / "config.local.json"
CFG_PATH = BASE_CFG_PATH  # Backward compatibility


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merges override dictionary into base dictionary."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_merged_config_dict() -> dict[str, Any]:
    """Load base config.json and overlay config.local.json if present."""
    base_data: dict[str, Any] = {}
    if BASE_CFG_PATH.exists():
        try:
            with open(BASE_CFG_PATH, "r", encoding="utf-8") as f:
                base_data = json.load(f)
        except Exception as e:
            print(f"Error loading base config.json: {e}")

    local_data: dict[str, Any] = {}
    if LOCAL_CFG_PATH.exists():
        try:
            with open(LOCAL_CFG_PATH, "r", encoding="utf-8") as f:
                local_data = json.load(f)
        except Exception as e:
            print(f"Error loading local config.local.json: {e}")

    return _deep_merge(base_data, local_data)


def save_local_override(section: str, key: str, value: Any) -> dict[str, Any]:
    """Saves a single key override to machine-specific config.local.json."""
    local_data: dict[str, Any] = {}
    if LOCAL_CFG_PATH.exists():
        try:
            with open(LOCAL_CFG_PATH, "r", encoding="utf-8") as f:
                local_data = json.load(f)
        except Exception:
            local_data = {}

    if section not in local_data or not isinstance(local_data[section], dict):
        local_data[section] = {}
    local_data[section][key] = value

    with open(LOCAL_CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(local_data, f, indent=2)

    return get_merged_config_dict()


def save_full_local_config(data: dict[str, Any]) -> dict[str, Any]:
    """Overwrites config.local.json with provided dictionary."""
    with open(LOCAL_CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return get_merged_config_dict()


def reset_local_config() -> dict[str, Any]:
    """Removes config.local.json and returns base configuration."""
    if LOCAL_CFG_PATH.exists():
        try:
            LOCAL_CFG_PATH.unlink()
        except Exception:
            pass
    return get_merged_config_dict()


def get_raw_config_files() -> dict[str, Any]:
    """Returns raw texts and parsed dicts for base, local, and merged config."""
    base_text = "{}"
    if BASE_CFG_PATH.exists():
        base_text = BASE_CFG_PATH.read_text(encoding="utf-8")

    local_text = "{}"
    if LOCAL_CFG_PATH.exists():
        local_text = LOCAL_CFG_PATH.read_text(encoding="utf-8")

    merged = get_merged_config_dict()

    return {
        "base_text": base_text,
        "local_text": local_text,
        "merged_text": json.dumps(merged, indent=2),
        "merged_dict": merged,
        "has_local": LOCAL_CFG_PATH.exists(),
        "base_path": str(BASE_CFG_PATH),
        "local_path": str(LOCAL_CFG_PATH),
    }


def load_config() -> "Config":
    return Config()


@final
class Config:
    def __init__(self, path: Path | None = None):
        if path is not None:
            with open(path, "r", encoding="utf-8") as f:
                config: dict[str, dict[str, Any]] = json.load(f)
        else:
            config = get_merged_config_dict()

        self.pygame = PygameConfig(config.get("pygame", {"active": True}))
        self.stepper = _make_stepper_config(config.get("stepper_motor", {}))
        self.camera = CameraConfig(config.get("camera", {}))
        self.led_array = LedArrayConfig(config.get("led_array", {}))
        self.lcd_display = LcdDisplayConfig(config.get("lcd_display", {}))
        self.rotary_encoder = RotaryConfig(config.get("rotary_encoder", {}))
        self.projector = ProjectorConfig(config.get("projector", {}))
        self.ui = UIConfig(config.get("ui", {}))



class PygameConfig:
    def __init__(self, config: dict[str, Any]):
        self.active: bool = config["active"]


class StepperConfigBase:
    def __init__(self, config: dict[str, Any]):
        self.driver_mode: str = config.get("driver_mode", "step_dir")
        self.encoder_a_pin: int = config["A_pin"]
        self.encoder_b_pin: int = config["B_pin"]
        self.default_rpm: float = config["default_rpm"]
        self.default_direction: str = config["default_direction"]
        self.steps_per_revolution: int = config["steps_per_revolution"]
        self.encoder_cpr: int = config["encoder_cpr"]
        self.correction_factor: float = float(config.get("correction_factor", 0.988375 if self.driver_mode == "uart" else 1.0))


# Alias so existing imports of StepperConfig still work
StepperConfig = StepperConfigBase


class TicUSBStepperConfig(StepperConfigBase):
    pass  # USB device is found automatically — no extra config needed


class StepDirStepperConfig(StepperConfigBase):
    def __init__(self, config: dict[str, Any]):
        self.enable_pin: int = config["enable_pin"]
        super().__init__(config)
        config = config["step_dir"]
        self.step_pin: int = config["step_pin"]
        self.dir_pin: int = config["dir_pin"]
        self.encoder_a_pin: int = config["A_pin"]
        self.encoder_b_pin: int = config["B_pin"]


class UARTStepperConfig(StepperConfigBase):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        config = config["uart"]
        self.uart_port: str = config["uart_port"]
        self.baud_rate: int = config["baud_rate"]
        self.uart_address: int = config["uart_address"]
        self.microsteps: int = config["microsteps"]


def _make_stepper_config(raw: dict[str, Any]) -> StepperConfigBase:
    mode: str = raw.get("driver_mode", "step_dir")
    if mode == "tic_usb":
        return TicUSBStepperConfig(raw)
    elif mode == "step_dir":
        return StepDirStepperConfig(raw)
    elif mode == "uart":
        return UARTStepperConfig(raw)
    elif mode == "mock":
        return StepperConfigBase(raw)
    raise ValueError(f"Unknown stepper driver_mode: {mode!r}")


class CameraConfig:
    def __init__(self, config: dict[str, Any]):
        self.type: str = config["type"]
        self.index: int = config["index"]
        self.save_path: str = config["save_path"]
        self.awb_enable: bool = config.get("awb_enable", True)
        gains = config.get("colour_gains", [2.0, 1.8])
        self.colour_gains: tuple[float, float] = (gains[0], gains[1])


class LedArrayConfig:
    def __init__(self, config: dict[str, Any]):
        self.num_led: int = config["num_led"]
        self.default_color: tuple[int, int, int, int] = tuple(config["default_color"])


class LcdDisplayConfig:
    def __init__(self, config: dict[str, Any]):
        self.port: str = str(config["port"])
        self.address: str = config["address"]
        self.cols: int = config["cols"]
        self.rows: int = config["rows"]
        self.type: str = config.get("type", "newhaven" if str(config["address"]) in ("0x28", "40") or str(config["port"]).isdigit() else "pcf8574")
        self.contrast: int = config.get("contrast", 40)
        self.backlight: int = config.get("backlight", 8)


class RotaryConfig:
    def __init__(self, config: dict[str, Any]):
        self.clk_pin: int = config["clk_pin"]
        self.dt_pin: int = config["dt_pin"]
        self.btn_pin: int = config["btn_pin"]


class ProjectorConfig:
    def __init__(self, config: dict[str, Any]):
        self.default_print_size: int = config["default_print_size"]
        self.calibration_img_path: str = config["calibration_img_path"]
        self.calibration_dir_path: str = config["calibration_dir_path"]
        self.vial_width_px: int = int(config.get("vial_width_px", 200))
        self.alignment_y_offset_px: int = int(config.get("alignment_y_offset_px", 0))
        self.default_volume: int = int(config.get("default_volume", 20))
        self.orientation: str = str(config.get("orientation", "90"))


def save_projector_orientation(orientation: str) -> None:
    """Persist projector display orientation (e.g. '90', '270', 'normal') to config.local.json."""
    try:
        save_local_override("projector", "orientation", str(orientation))
        print(f"✓ Saved projector orientation = {orientation} to config.local.json")
    except Exception as e:
        print(f"Error saving projector orientation: {e}")


def save_vial_width(width: int) -> None:
    """Persist calibrated vial width in pixels to machine-specific config.local.json."""
    try:
        save_local_override("projector", "vial_width_px", int(width))
        print(f"✓ Saved vial_width_px = {width} to config.local.json")
    except Exception as e:
        print(f"Error saving vial width: {e}")


def save_alignment_offset(offset: int) -> None:
    """Persist optical alignment Y-offset in pixels to machine-specific config.local.json."""
    try:
        save_local_override("projector", "alignment_y_offset_px", int(offset))
        print(f"✓ Saved alignment_y_offset_px = {offset} to config.local.json")
    except Exception as e:
        print(f"Error saving alignment offset: {e}")


def save_projector_volume(volume: int) -> None:
    """Persist projector volume percentage (0-100) to machine-specific config.local.json."""
    try:
        save_local_override("projector", "default_volume", int(volume))
        print(f"✓ Saved default_volume = {volume} to config.local.json")
    except Exception as e:
        print(f"Error saving projector volume: {e}")


def save_sounds_enabled(enabled: bool) -> None:
    """Persist sounds enabled/disabled boolean setting to machine-specific config.local.json."""
    try:
        save_local_override("ui", "sounds_enabled", bool(enabled))
        print(f"✓ Saved sounds_enabled = {enabled} to config.local.json")
    except Exception as e:
        print(f"Error saving sounds setting: {e}")



class UIConfig:
    def __init__(self, config: dict[str, Any]):
        self.prompt_usb_video_save: bool = config.get("prompt_usb_video_save", True)
        self.sounds_enabled: bool = config.get("sounds_enabled", True)


