import math

from .config import SCREEN_WIDTH, SCREEN_HEIGHT, SCALE_X, SCALE_Y
from ...config import GeneratorType, MAX_ENERGY_GAUGE
from . import palette


class GaugeManager:
    """Animated generator cells contained by one centered battery housing."""

    CELL_WIDTH = 330
    CELL_HEIGHT = 86
    CELL_GAP = 8
    ANIMATION_SPEED = 10.0

    def __init__(self, game_state=None):
        self.game_state = game_state
        self.generators = list(GeneratorType)
        self.colors = {
            GeneratorType.WIND: 61,
            GeneratorType.SOLAR: 31,
            GeneratorType.HAND_CRANK: 11,
            GeneratorType.COIL: 41,
        }
        self.labels = {
            GeneratorType.WIND: "WIND",
            GeneratorType.SOLAR: "SOLAR",
            GeneratorType.HAND_CRANK: "CRANK",
            GeneratorType.COIL: "COIL",
        }
        self.levels = {generator: 0.0 for generator in self.generators}
        self.selected = ()
        self._cell_bounds = {}
        self._cells = {}
        self._display_order = []
        self._housing_width = 0.0

    def reset(self):
        self.levels = {generator: 0.0 for generator in self.generators}
        self.selected = ()
        self._cell_bounds.clear()
        self._cells.clear()
        self._display_order.clear()
        self._housing_width = 0.0

    def update(self, snapshot=None, dt=1.0 / 60.0):
        if snapshot is None and self.game_state:
            snapshot = self.game_state.snapshot()
        if snapshot is None:
            return
        dt = min(0.1, max(0.0, dt))
        factor = 1.0 - math.exp(-self.ANIMATION_SPEED * dt)
        self.selected = tuple(snapshot.selected_generators)

        cell_width = self.CELL_WIDTH * SCALE_X
        gap = self.CELL_GAP * SCALE_X
        count = len(self.selected)
        target_width = count * cell_width + max(0, count - 1) * gap
        target_left = (SCREEN_WIDTH - target_width) / 2

        for generator in self.selected:
            if generator not in self._cells:
                index = self.selected.index(generator)
                target_x = target_left + index * (cell_width + gap)
                self._cells[generator] = {
                    "visibility": 0.0,
                    "x": target_x + 42 * SCALE_X,
                    "target_x": target_x,
                }
                self._display_order.append(generator)

        for index, generator in enumerate(self.selected):
            self._cells[generator]["target_x"] = target_left + index * (cell_width + gap)

        for generator in tuple(self._display_order):
            cell = self._cells[generator]
            visible = generator in self.selected
            target_visibility = 1.0 if visible else 0.0
            cell["visibility"] += (target_visibility - cell["visibility"]) * factor
            if visible:
                cell["x"] += (cell["target_x"] - cell["x"]) * factor
            if not visible and cell["visibility"] < 0.015:
                self._display_order.remove(generator)
                del self._cells[generator]

        self._housing_width += (target_width - self._housing_width) * factor
        if not count and not self._display_order:
            self._housing_width = 0.0

        for generator in self.generators:
            self.levels[generator] = snapshot.energy_levels.get(generator, 0.0)

    def cell_center(self, generator):
        bounds = self._cell_bounds.get(generator)
        if bounds is None:
            return SCREEN_WIDTH / 2, SCREEN_HEIGHT - 190 * SCALE_Y
        x, y, width, _ = bounds
        return x + width / 2, y

    def draw(self, renderer, pixel_font, frame_count, scene_alpha=1.0):
        if not self._display_order or scene_alpha <= 0.0:
            return
        renderer.set_blend_mode("alpha")
        cell_width = self.CELL_WIDTH * SCALE_X
        cell_height = self.CELL_HEIGHT * SCALE_Y
        # Center the complete housing vertically within the black ground block.
        ground_surface_y = 820 * SCALE_Y
        y = ground_surface_y + (SCREEN_HEIGHT - ground_surface_y - cell_height) / 2
        max_visibility = max(self._cells[g]["visibility"] for g in self._display_order)
        housing_alpha = scene_alpha * max_visibility
        housing_width = max(cell_width * 0.18, self._housing_width)
        housing_x = (SCREEN_WIDTH - housing_width) / 2
        pad_x = 15 * SCALE_X
        pad_y = 14 * SCALE_Y

        renderer.draw_rect(
            housing_x - pad_x - 5 * SCALE_X,
            y - pad_y - 5 * SCALE_Y,
            housing_width + pad_x * 2 + 10 * SCALE_X,
            cell_height + pad_y * 2 + 10 * SCALE_Y,
            (0.0, 0.0, 0.0, 0.50 * housing_alpha), fill=True,
        )
        renderer.draw_rect(
            housing_x - pad_x, y - pad_y,
            housing_width + pad_x * 2, cell_height + pad_y * 2,
            (0.018, 0.03, 0.065, 0.96 * housing_alpha), fill=True,
        )
        renderer.draw_rect(
            housing_x - pad_x, y - pad_y,
            housing_width + pad_x * 2, cell_height + pad_y * 2,
            (0.78, 0.88, 1.0, 0.95 * housing_alpha), fill=False,
        )
        renderer.draw_rect(
            housing_x - pad_x + 5 * SCALE_X, y - pad_y + 5 * SCALE_Y,
            housing_width + pad_x * 2 - 10 * SCALE_X,
            cell_height + pad_y * 2 - 10 * SCALE_Y,
            (0.18, 0.34, 0.54, 0.82 * housing_alpha), fill=False,
        )
        terminal_x = housing_x + housing_width + pad_x
        renderer.draw_rect(
            terminal_x, y + 22 * SCALE_Y, 20 * SCALE_X, 42 * SCALE_Y,
            (0.72, 0.82, 0.94, housing_alpha), fill=True,
        )
        renderer.draw_rect(
            terminal_x + 4 * SCALE_X, y + 27 * SCALE_Y, 16 * SCALE_X, 32 * SCALE_Y,
            (0.15, 0.22, 0.32, housing_alpha), fill=True,
        )

        self._cell_bounds.clear()
        for generator in self._display_order:
            cell = self._cells[generator]
            visibility = min(1.0, max(0.0, cell["visibility"]))
            cell_alpha = scene_alpha * visibility
            scale = 0.82 + visibility * 0.18
            width = cell_width * scale
            height = cell_height * scale
            x = cell["x"] + (cell_width - width) / 2
            cell_y = y + (cell_height - height) / 2 + (1.0 - visibility) * 24 * SCALE_Y
            self._cell_bounds[generator] = (x, cell_y, width, height)
            percent = min(1.0, max(0.0, self.levels[generator] / MAX_ENERGY_GAUGE))
            full = percent >= 0.999
            color_index = self.colors[generator]
            color = palette.get_color(color_index + (5 if full and frame_count % 20 < 10 else 0))

            renderer.draw_rect(x, cell_y, width, height, (0.0, 0.0, 0.0, 0.9 * cell_alpha), fill=True)
            renderer.draw_rect(
                x + 5 * SCALE_X, cell_y + 5 * SCALE_Y,
                width - 10 * SCALE_X, height - 10 * SCALE_Y,
                (0.02, 0.04, 0.065, 0.92 * cell_alpha), fill=True,
            )
            if percent > 0.0:
                renderer.draw_rect(
                    x + 7 * SCALE_X, cell_y + 7 * SCALE_Y,
                    (width - 14 * SCALE_X) * percent, height - 14 * SCALE_Y,
                    (*color[:3], 0.82 * cell_alpha), fill=True,
                )
            pulse = 0.24 * math.sin(frame_count * 0.18) if full else 0.0
            renderer.draw_rect(x, cell_y, width, height, (*color[:3], cell_alpha * (0.78 + pulse)), fill=False)
            renderer.draw_rect(
                x + 3 * SCALE_X, cell_y + 3 * SCALE_Y,
                width - 6 * SCALE_X, height - 6 * SCALE_Y,
                (0.85, 0.92, 1.0, cell_alpha * 0.54), fill=False,
            )

            label = f"{self.labels[generator]} {int(percent * 100)}%"
            text_width, text_height = pixel_font.measure(label, 5)
            # The even cell size and odd glyph size naturally center at .5 px.
            # Native 1080p V3D rasterization can duplicate a texture-edge texel
            # there, which looks like a small foot below the glyph. Pixel art
            # must stay on whole logical pixels regardless of display scaling.
            text_x = round(x + (width - text_width) / 2)
            text_y = round(cell_y + (height - text_height) / 2)
            # Render one clean label; completed cells use dark ink against their
            # bright full-cell fill.
            text_color = (0.025, 0.045, 0.07) if full else (1.0, 1.0, 1.0)
            renderer.draw_pixel_text(
                text_x,
                text_y,
                label,
                pixel_font,
                5,
                (*text_color, cell_alpha),
            )

        renderer.set_blend_mode("additive")
