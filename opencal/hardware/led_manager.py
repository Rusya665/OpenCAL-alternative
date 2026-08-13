import time
from typing import final

try:
    from pi5neo.pi5neo import Pi5Neo, EPixelType
    HAS_PI5NEO = True
except (ImportError, ModuleNotFoundError):
    Pi5Neo = None
    EPixelType = None
    HAS_PI5NEO = False

from opencal.utils.config import LedArrayConfig

RED    = (0,   240, 0,   0)
GREEN  = (240, 0,   0,   0)
BLUE   = (0,   0,   240, 0)
YELLOW = (240, 240, 0,   0)
WHITE  = (0,   0,   0,   240)
OFF    = (0,   0,   0,   0)


@final
class LEDManager:
    def __init__(self, config: LedArrayConfig):
        self.num_led: int = config.num_led
        self.default_color: tuple[int, int, int, int] = config.default_color

        if HAS_PI5NEO:
            try:
                self.neo = Pi5Neo("/dev/spidev0.0", self.num_led, 800, pixel_type=EPixelType.RGBW)
                self.clear_leds()
            except Exception as e:
                self.neo = None
                print(f"WARNING: Could not init Pi5Neo: {e}")
        else:
            self.neo = None
            print("WARNING: Pi5Neo library not available, LED array disabled.")

    def set_led(
        self,
        color: tuple[int, int, int, int],
        led_index: list[int] | None = None,
        update: bool = True,
    ):
        if not self.neo:
            return
        if led_index is None:
            self.neo.fill_strip(*color)
        else:
            for idx in led_index:
                _ = self.neo.set_led_color(idx, *color)
        if update:
            self.neo.update_strip()

    def clear_leds(self):
        if not self.neo:
            return
        self.neo.clear_strip()
        self.neo.update_strip()

    def run_start_animation(self):
        if not self.neo:
            return
        CYCLES = 5
        DELAY = 0.5
        ROWS, COLS = 8, 8

        group_1: list[int] = []
        group_2: list[int] = []

        for i in range(ROWS):
            for j in range(COLS):
                k = i // 2 + j // 2
                idx = i * COLS + j
                if k % 2 == 0:
                    group_1.append(idx)
                else:
                    group_2.append(idx)

        for _ in range(CYCLES):
            self.set_led(YELLOW, group_1, update=False)
            self.set_led(BLUE, group_2)
            time.sleep(DELAY)

            self.set_led(BLUE, group_1, update=False)
            self.set_led(YELLOW, group_2)
            time.sleep(DELAY)

        self.clear_leds()
