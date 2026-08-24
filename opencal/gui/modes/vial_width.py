from __future__ import annotations

from typing import TYPE_CHECKING, Callable, final, override

import pygame

from opencal.gui.modes.base import BasePygameMode

if TYPE_CHECKING:
    from opencal.gui.pygame_app import PygameApp


@final
class VialWidthMode(BasePygameMode):
    """Interactive vial-width measurement mode.

    The rotary encoder adjusts the width of a centered white vertical bar.
    The bar spans the full screen height and its pixel width is shown as
    an overlay so the user can read the value before confirming.
    Pressing the button confirms and exits with {"vial_width": <px_width>}.
    """

    SCROLL_RATIO = 2
    INITIAL_WIDTH = 200

    def __init__(
        self,
        app: "PygameApp",
        on_width_change: Callable[[int], None] | None = None,
        initial_width: int | None = None,
    ) -> None:
        super().__init__(app)
        self._initial_width = initial_width if initial_width is not None else self.INITIAL_WIDTH
        self.rect_width: int = self._initial_width
        self._font: pygame.font.Font | None = None
        self._on_width_change = on_width_change

    @override
    def on_activate(self) -> None:
        self.rect_width = self._initial_width
        self._font = pygame.font.Font(None, 60)
        if self._on_width_change:
            self._on_width_change(self.rect_width)

    @override
    def on_deactivate(self) -> None:
        self._font = None

    @override
    def on_encoder_delta(self, delta: int) -> None:
        max_w = self.app.width if self.app.width > 0 else 1080
        self.rect_width = max(0, min(max_w, self.rect_width + delta * self.SCROLL_RATIO))
        if self._on_width_change:
            self._on_width_change(self.rect_width)

    @override
    def on_button(self) -> None:
        self.app.signal_done({"vial_width": self.rect_width})

    @override
    def on_frame(self, surf: pygame.Surface) -> None:
        surf.fill((0, 0, 0))
        w, h = surf.get_size()

        # Vertical bar centered horizontally (X-axis), spanning the full screen height (Y-axis)
        left = max(0, (w // 2) - (self.rect_width // 2))
        pygame.draw.rect(surf, "white", (left, 0, self.rect_width, h))

        # Pixel count overlay (yellow so it's visible against the dark background)
        if self._font:
            label = self._font.render(f"Vial Width: {self.rect_width} px", True, (255, 255, 0))
            surf.blit(label, (20, 20))
