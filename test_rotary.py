from opencal.utils.config import Config
from opencal.hardware.rotary_controller import RotaryEncoderHandler

try:
    cfg = Config()
    rot = RotaryEncoderHandler(cfg.rotary_encoder)
    print("Rotary Initialized Successfully! Steps:", rot.get_steps())
except Exception as e:
    print("Rotary Init Error:", type(e), e)
