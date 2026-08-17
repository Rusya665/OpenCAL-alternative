from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, final, override

import pygame

from opencal.gui.modes.base import BasePygameMode

if TYPE_CHECKING:
    from opencal.gui.pygame_app import PygameApp

_STEP_PX = 5  # pixels moved per encoder click (~0.45 mm at 90 µm/pixel)


@final
class AlignmentMode(BasePygameMode):
    """Displays the alignment tool image with live vertical translation.

    Rotate encoder up/down to shift the image transversely.
    Press button to exit and save alignment offset.
    """

    def __init__(
        self,
        app: "PygameApp",
        image_path: str | Path,
        initial_y_offset: int = 0,
        on_offset_change: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(app)
        self._image_path = Path(image_path)
        self._surface: pygame.Surface | None = None
        self._initial_y_offset: int = initial_y_offset
        self._y_offset: int = initial_y_offset
        self._on_offset_change = on_offset_change
        self._font: pygame.font.Font | None = None

    @override
    def on_activate(self) -> None:
        self._y_offset = self._initial_y_offset
        self._font = pygame.font.Font(None, 48)
        raw = pygame.image.load(str(self._image_path)).convert()
        self._surface = pygame.transform.scale(raw, (self.app.width, self.app.height))
        if self._on_offset_change:
            self._on_offset_change(self._y_offset)

    @override
    def on_deactivate(self) -> None:
        self._surface = None
        self._font = None

    @override
    def on_encoder_delta(self, delta: int) -> None:
        self._y_offset += delta * _STEP_PX
        if self._on_offset_change:
            self._on_offset_change(self._y_offset)

    @override
    def on_button(self) -> None:
        self.app.signal_done({"y_offset": self._y_offset})

    @override
    def on_frame(self, surf: pygame.Surface) -> None:
        surf.fill((0, 0, 0))
        if self._surface is not None:
            _ = surf.blit(self._surface, (0, self._y_offset))
        if self._font is not None:
            sign = "+" if self._y_offset > 0 else ""
            txt = self._font.render(f"Offset: {sign}{self._y_offset} px", True, (0, 255, 200))
            surf.blit(txt, (40, 40))

