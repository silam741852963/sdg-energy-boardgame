import pyxel
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, SCALE_X, SCALE_Y, FIREWORK_TYPES, COLORS
from .models import generate_spec


class ControlPanel:
    def __init__(self):
        self.visible = False
        self.selected_type = FIREWORK_TYPES[0]
        self.selected_color = COLORS[0]
        self.spec = generate_spec(self.selected_type)
        self.spec.base_color = self.selected_color

        self.scale_x = max(1, int(3 * SCALE_X))
        self.scale_y = max(1, int(3 * SCALE_Y))

        self.width = int(1350 * SCALE_X)
        self.item_height = int(30 * SCALE_Y)

        self.col1_x = int(20 * SCALE_X)
        self.type_start_y = int(100 * SCALE_Y)
        self.color_start_y = (
            self.type_start_y
            + len(FIREWORK_TYPES) * self.item_height
            + int(50 * SCALE_Y)
        )

        # Shifted Column 2 slightly left to make room
        self.col2_x = int(420 * SCALE_X)
        self.num_start_y = int(100 * SCALE_Y)

        self.num_props = [
            ("particle_count", "particles", 10, 10, 500),
            ("speed_variance", "radius (speed)", 1.0, 1.0, 50.0),
            ("radius", "light area", 0.1, 0.1, 5.0),
            ("gravity_mod", "gravity", 0.1, -2.0, 5.0),
            ("drag", "air drag", 0.01, 0.0, 1.0),
            ("life_span", "fade time", 10, 10, 500),
            ("intensity", "brightness", 0.1, 0.1, 5.0),
            ("multicolor", "mixed colors", 1, 1, len(COLORS)),
            ("variant", "color variant", 1, 0, 1),
        ]

        self.bool_start_y = (
            self.num_start_y
            + len(self.num_props) * self.item_height
            + int(50 * SCALE_Y)
        )

        self.bool_props = [
            "burst",
            "has_trails",
            "flicker",
            "swim",
            "split",
            "crackle",
            "pistil",
            "spin",
            "waterfall",
            "palm_tail",
            "glitter",
        ]

        # --- NEW: Pushed Column 3 safely to the right ---
        self.col3_x = int(880 * SCALE_X)
        self.drone_spacing = 30
        self.drone_altitude = -120
        self.drone_radius = 1.5
        self.drone_intensity = 1.5

        self.drone_props = [
            ("drone_spacing", "spacing", 5, 5, 100),
            ("drone_altitude", "altitude (y)", 20, -500, 500),
            ("drone_radius", "dot size", 0.5, 0.5, 5.0),
            ("drone_intensity", "brightness", 0.2, 0.2, 5.0),
        ]

        self.trigger_drones = False
        self.clear_drones = False
        self.char_cache = {}

    def update(self) -> bool:
        if pyxel.btnp(pyxel.KEY_TAB):
            self.visible = not self.visible

        if not self.visible:
            return False

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            mx, my = pyxel.mouse_x, pyxel.mouse_y

            if mx < self.width:
                for i, fw_type in enumerate(FIREWORK_TYPES):
                    y = self.type_start_y + i * self.item_height
                    if (
                        self.col1_x <= mx < self.col1_x + int(300 * SCALE_X)
                        and y <= my < y + self.item_height
                    ):
                        self.selected_type = fw_type
                        self.spec = generate_spec(fw_type)
                        self.spec.base_color = self.selected_color
                        return True

                for i, color in enumerate(COLORS):
                    y = self.color_start_y + i * self.item_height
                    if (
                        self.col1_x <= mx < self.col1_x + int(300 * SCALE_X)
                        and y <= my < y + self.item_height
                    ):
                        self.selected_color = color
                        self.spec.base_color = color
                        return True

                for i, (prop, disp, step, min_v, max_v) in enumerate(self.num_props):
                    y = self.num_start_y + i * self.item_height
                    if (
                        self.col2_x + int(250 * SCALE_X)
                        <= mx
                        < self.col2_x + int(290 * SCALE_X)
                        and y <= my < y + self.item_height
                    ):
                        val = getattr(self.spec, prop)
                        if prop in [
                            "particle_count",
                            "life_span",
                            "multicolor",
                            "variant",
                        ]:
                            setattr(self.spec, prop, int(max(min_v, val - step)))
                        else:
                            setattr(self.spec, prop, round(max(min_v, val - step), 2))
                        return True

                    if (
                        self.col2_x + int(380 * SCALE_X)
                        <= mx
                        < self.col2_x + int(420 * SCALE_X)
                        and y <= my < y + self.item_height
                    ):
                        val = getattr(self.spec, prop)
                        if prop in [
                            "particle_count",
                            "life_span",
                            "multicolor",
                            "variant",
                        ]:
                            setattr(self.spec, prop, int(min(max_v, val + step)))
                        else:
                            setattr(self.spec, prop, round(min(max_v, val + step), 2))
                        return True

                for i, prop in enumerate(self.bool_props):
                    y = self.bool_start_y + i * self.item_height
                    if (
                        self.col2_x + int(300 * SCALE_X)
                        <= mx
                        < self.col2_x + int(340 * SCALE_X)
                        and y <= my < y + self.item_height
                    ):
                        val = getattr(self.spec, prop)
                        setattr(self.spec, prop, not val)
                        return True

                # --- UPDATED: Adjusted hitboxes for Column 3 Math ---
                for i, (prop, disp, step, min_v, max_v) in enumerate(self.drone_props):
                    y = self.num_start_y + i * self.item_height
                    if (
                        self.col3_x + int(180 * SCALE_X)
                        <= mx
                        < self.col3_x + int(220 * SCALE_X)
                        and y <= my < y + self.item_height
                    ):
                        val = getattr(self, prop)
                        setattr(self, prop, round(max(min_v, val - step), 2))
                        return True

                    if (
                        self.col3_x + int(280 * SCALE_X)
                        <= mx
                        < self.col3_x + int(320 * SCALE_X)
                        and y <= my < y + self.item_height
                    ):
                        val = getattr(self, prop)
                        setattr(self, prop, round(min(max_v, val + step), 2))
                        return True

                btn_y = (
                    self.num_start_y
                    + len(self.drone_props) * self.item_height
                    + int(30 * SCALE_Y)
                )
                if self.col3_x <= mx < self.col3_x + int(400 * SCALE_X):
                    if btn_y <= my < btn_y + self.item_height:
                        self.trigger_drones = True
                        return True
                    elif btn_y + self.item_height <= my < btn_y + self.item_height * 2:
                        self.clear_drones = True
                        return True

                return True

        return False

    def get_char_pixels(self, char, color):
        cache_key = (char, color)
        if cache_key not in self.char_cache:
            pyxel.images[2].rect(0, 0, 4, 6, 0)
            pyxel.images[2].text(0, 0, char, color)
            pixels = []
            for j in range(6):
                for i in range(4):
                    if pyxel.images[2].pget(i, j) == color:
                        pixels.append((i, j))
            self.char_cache[cache_key] = pixels
        return self.char_cache[cache_key]

    def draw_text_scaled(self, x, y, text, color):
        for idx, char in enumerate(text):
            char_pixels = self.get_char_pixels(char, color)
            char_x = x + idx * 4 * self.scale_x
            for dx, dy in char_pixels:
                pyxel.rect(
                    char_x + dx * self.scale_x,
                    y + dy * self.scale_y,
                    self.scale_x,
                    self.scale_y,
                    color,
                )

    def draw(self):
        if not self.visible:
            self.draw_text_scaled(
                int(20 * SCALE_X), int(20 * SCALE_Y), "Press TAB for Laboratory", 121
            )
            return

        pyxel.rect(0, 0, self.width, pyxel.height, 0)
        pyxel.rectb(0, 0, self.width, pyxel.height, 122)

        self.draw_text_scaled(
            int(20 * SCALE_X),
            int(20 * SCALE_Y),
            "[ FIREWORK LABORATORY ] (TAB to hide)",
            121,
        )

        self.draw_text_scaled(
            self.col1_x, int(60 * SCALE_Y), "--- 1. BASE PRESET ---", 121
        )
        for i, fw_type in enumerate(FIREWORK_TYPES):
            y = self.type_start_y + i * self.item_height
            color = 121 if fw_type == self.selected_type else 123
            prefix = "> " if fw_type == self.selected_type else "  "
            self.draw_text_scaled(self.col1_x, y, f"{prefix}{fw_type}", color)

        self.draw_text_scaled(
            self.col1_x, self.color_start_y - int(30 * SCALE_Y), "--- 2. COLOR ---", 121
        )
        for i, c_name in enumerate(COLORS):
            y = self.color_start_y + i * self.item_height
            color = 121 if c_name == self.selected_color else 123
            prefix = "> " if c_name == self.selected_color else "  "
            self.draw_text_scaled(
                self.col1_x, y, f"{prefix}{c_name.capitalize()}", color
            )

        self.draw_text_scaled(
            self.col2_x, int(60 * SCALE_Y), "--- 3. TWEAK PHYSICS ---", 121
        )
        for i, (prop, disp, step, min_v, max_v) in enumerate(self.num_props):
            y = self.num_start_y + i * self.item_height
            val = getattr(self.spec, prop)
            self.draw_text_scaled(self.col2_x, y, f"{disp}", 121)
            self.draw_text_scaled(self.col2_x + int(250 * SCALE_X), y, "[-]", 122)
            val_str = f"{val:.2f}" if isinstance(val, float) else f"{val}"
            self.draw_text_scaled(self.col2_x + int(300 * SCALE_X), y, val_str, 121)
            self.draw_text_scaled(self.col2_x + int(380 * SCALE_X), y, "[+]", 122)

        self.draw_text_scaled(
            self.col2_x,
            self.bool_start_y - int(30 * SCALE_Y),
            "--- 4. ATTRIBUTES ---",
            121,
        )
        for i, prop in enumerate(self.bool_props):
            y = self.bool_start_y + i * self.item_height
            val = getattr(self.spec, prop)
            self.draw_text_scaled(self.col2_x, y, f"{prop}", 121)
            box_text = "[X]" if val else "[ ]"
            box_color = 51 if val else 123
            self.draw_text_scaled(
                self.col2_x + int(300 * SCALE_X), y, box_text, box_color
            )

        self.draw_text_scaled(
            self.col3_x, int(60 * SCALE_Y), "--- 5. DRONE SHOW ---", 121
        )
        for i, (prop, disp, step, min_v, max_v) in enumerate(self.drone_props):
            y = self.num_start_y + i * self.item_height
            val = getattr(self, prop)

            self.draw_text_scaled(self.col3_x, y, f"{disp}", 121)
            self.draw_text_scaled(self.col3_x + int(180 * SCALE_X), y, "[-]", 122)

            val_str = f"{val:.2f}" if isinstance(val, float) else f"{val}"
            self.draw_text_scaled(self.col3_x + int(220 * SCALE_X), y, val_str, 121)
            self.draw_text_scaled(self.col3_x + int(280 * SCALE_X), y, "[+]", 122)

        btn_y = (
            self.num_start_y
            + len(self.drone_props) * self.item_height
            + int(30 * SCALE_Y)
        )
        # Added explicit hotkey text to the buttons!
        self.draw_text_scaled(self.col3_x, btn_y, "[ LAUNCH DRONES ] (Key: D)", 51)
        self.draw_text_scaled(
            self.col3_x, btn_y + self.item_height, "[ CLEAR DRONES ] (Key: C)", 1
        )

        self.draw_text_scaled(
            int(20 * SCALE_X),
            pyxel.height - int(50 * SCALE_Y),
            ">>> CLICK SKY TO LAUNCH | TAB: LAB | M: TOGGLE SYSTEM METRICS <<<",
            122,
        )
