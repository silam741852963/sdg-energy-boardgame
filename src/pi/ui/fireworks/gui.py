import pyxel
from .models import FIREWORK_TYPES, COLORS, generate_spec


class ControlPanel:
    def __init__(self):
        self.visible = False

        self.selected_type = FIREWORK_TYPES[0]
        self.selected_color = COLORS[0]

        # The live configuration we are actively tweaking
        self.spec = generate_spec(self.selected_type)
        self.spec.base_color = self.selected_color

        # UI Dimensions Scaled for 1080p
        self.scale = 3
        self.width = 900  # Reduced from 1250 to 900 for a 2-column layout
        self.item_height = 30

        # Column 1: Presets & Colors
        self.col1_x = 20
        self.type_start_y = 100
        self.color_start_y = (
            self.type_start_y + len(FIREWORK_TYPES) * self.item_height + 50
        )

        # Column 2: Physics (Numbers) & Attributes (Booleans)
        self.col2_x = 450
        self.num_start_y = 100

        # Property Name, Step Amount, Min Value, Max Value
        self.num_props = [
            ("particle_count", 10, 10, 500),
            ("speed_variance", 1.0, 1.0, 50.0),
            ("gravity_mod", 0.1, -2.0, 5.0),
            ("drag", 0.01, 0.0, 1.0),
            ("life_span", 10, 10, 500),
            ("variant", 1, 0, 1),
        ]

        # Stack Booleans below the Physics numbers in Column 2
        self.bool_start_y = (
            self.num_start_y + len(self.num_props) * self.item_height + 50
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
        ]

    def update(self) -> bool:
        """Returns True if the mouse click was captured by a UI element."""
        if pyxel.btnp(pyxel.KEY_TAB):
            self.visible = not self.visible

        if not self.visible:
            return False

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            mx, my = pyxel.mouse_x, pyxel.mouse_y

            # If clicked inside the panel background area
            if mx < self.width:
                # 1. Check if a Firework Type was clicked (Col 1)
                for i, fw_type in enumerate(FIREWORK_TYPES):
                    y = self.type_start_y + i * self.item_height
                    if (
                        self.col1_x <= mx < self.col1_x + 300
                        and y <= my < y + self.item_height
                    ):
                        self.selected_type = fw_type
                        self.spec = generate_spec(fw_type)
                        self.spec.base_color = self.selected_color
                        return True

                # 2. Check if a Color was clicked (Col 1)
                for i, color in enumerate(COLORS):
                    y = self.color_start_y + i * self.item_height
                    if (
                        self.col1_x <= mx < self.col1_x + 300
                        and y <= my < y + self.item_height
                    ):
                        self.selected_color = color
                        self.spec.base_color = color
                        return True

                # 3. Check Numeric Controls [-], [+] (Col 2)
                for i, (prop, step, min_v, max_v) in enumerate(self.num_props):
                    y = self.num_start_y + i * self.item_height

                    # Hitbox for [-]
                    if (
                        self.col2_x + 250 <= mx < self.col2_x + 290
                        and y <= my < y + self.item_height
                    ):
                        val = getattr(self.spec, prop)
                        setattr(self.spec, prop, round(max(min_v, val - step), 2))
                        return True

                    # Hitbox for [+]
                    if (
                        self.col2_x + 380 <= mx < self.col2_x + 420
                        and y <= my < y + self.item_height
                    ):
                        val = getattr(self.spec, prop)
                        setattr(self.spec, prop, round(min(max_v, val + step), 2))
                        return True

                # 4. Check Boolean Toggles [X] (Col 2, lower section)
                for i, prop in enumerate(self.bool_props):
                    y = self.bool_start_y + i * self.item_height

                    # Hitbox for [X] aligned with numeric controls
                    if (
                        self.col2_x + 300 <= mx < self.col2_x + 340
                        and y <= my < y + self.item_height
                    ):
                        val = getattr(self.spec, prop)
                        setattr(self.spec, prop, not val)
                        return True

                return True  # Clicked empty space inside the panel

        return False

    def draw_text_scaled(self, x, y, text, color):
        w = len(text) * 4
        h = 6
        pyxel.images[2].rect(0, 0, w, h, 0)
        pyxel.images[2].text(0, 0, text, color)

        for j in range(h):
            for i in range(w):
                if pyxel.images[2].pget(i, j) == color:
                    pyxel.rect(
                        x + i * self.scale,
                        y + j * self.scale,
                        self.scale,
                        self.scale,
                        color,
                    )

    def draw(self):
        if not self.visible:
            self.draw_text_scaled(20, 20, "Press TAB for Laboratory", 71)
            return

        # Draw dark background for the panel
        pyxel.rect(0, 0, self.width, pyxel.height, 0)
        pyxel.rectb(0, 0, self.width, pyxel.height, 71)

        self.draw_text_scaled(20, 20, "[ FIREWORK LABORATORY ] (TAB to hide)", 71)

        # COLUMN 1: Presets & Colors
        self.draw_text_scaled(self.col1_x, 60, "--- 1. BASE PRESET ---", 71)
        for i, fw_type in enumerate(FIREWORK_TYPES):
            y = self.type_start_y + i * self.item_height
            color = 71 if fw_type == self.selected_type else 13
            prefix = "> " if fw_type == self.selected_type else "  "
            self.draw_text_scaled(self.col1_x, y, f"{prefix}{fw_type}", color)

        self.draw_text_scaled(
            self.col1_x, self.color_start_y - 30, "--- 2. COLOR ---", 71
        )
        for i, c_name in enumerate(COLORS):
            y = self.color_start_y + i * self.item_height
            color = 71 if c_name == self.selected_color else 13
            prefix = "> " if c_name == self.selected_color else "  "
            self.draw_text_scaled(
                self.col1_x, y, f"{prefix}{c_name.capitalize()}", color
            )

        # COLUMN 2 (Top): Numeric Physics Properties
        self.draw_text_scaled(self.col2_x, 60, "--- 3. TWEAK PHYSICS ---", 71)
        for i, (prop, step, min_v, max_v) in enumerate(self.num_props):
            y = self.num_start_y + i * self.item_height
            val = getattr(self.spec, prop)

            self.draw_text_scaled(self.col2_x, y, f"{prop}", 71)
            self.draw_text_scaled(self.col2_x + 250, y, "[-]", 14)  # Silver bracket

            # Format floats cleanly, leave ints alone
            val_str = f"{val:.2f}" if isinstance(val, float) else f"{val}"
            self.draw_text_scaled(self.col2_x + 300, y, val_str, 71)
            self.draw_text_scaled(self.col2_x + 380, y, "[+]", 14)

        # COLUMN 2 (Bottom): Boolean Attributes
        self.draw_text_scaled(
            self.col2_x, self.bool_start_y - 30, "--- 4. ATTRIBUTES ---", 71
        )
        for i, prop in enumerate(self.bool_props):
            y = self.bool_start_y + i * self.item_height
            val = getattr(self.spec, prop)

            self.draw_text_scaled(self.col2_x, y, f"{prop}", 71)

            box_text = "[X]" if val else "[ ]"
            box_color = 36 if val else 13  # Mint green if true, gray if false

            # Aligned exactly under the numeric values (x + 300)
            self.draw_text_scaled(self.col2_x + 300, y, box_text, box_color)

        self.draw_text_scaled(
            20,
            pyxel.height - 50,
            ">>> CLICK THE SKY OUTSIDE THIS PANEL TO LAUNCH! <<<",
            10,
        )
