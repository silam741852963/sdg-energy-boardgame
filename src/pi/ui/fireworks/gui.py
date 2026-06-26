import pygame
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, SCALE_X, SCALE_Y, FIREWORK_TYPES, COLORS
from .models import generate_spec
from . import palette

class ControlPanel:
    def __init__(self):
        self.visible = False
        self.selected_type = FIREWORK_TYPES[0]
        self.selected_color = COLORS[0]
        self.spec = generate_spec(self.selected_type)
        self.spec.base_color = self.selected_color
        self.has_custom_spec = False

        self.width = int(1350 * SCALE_X)
        self.item_height = int(30 * SCALE_Y)
        
        self.margin_x = int(40 * SCALE_X)
        self.margin_top = int(50 * SCALE_Y)
        self.margin_bottom = int(40 * SCALE_Y)
        self.panel_height = SCREEN_HEIGHT - self.margin_top - self.margin_bottom

        self.col1_x = int(20 * SCALE_X)
        self.type_start_y = int(100 * SCALE_Y)
        self.color_start_y = (
            self.type_start_y
            + len(FIREWORK_TYPES) * self.item_height
            + int(50 * SCALE_Y)
        )

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

    def update(self, events, mouse_pos, mouse_click_left) -> bool:
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    self.visible = not self.visible

        if not self.visible:
            return False

        if mouse_click_left:
            mx, my = mouse_pos
            mx -= self.margin_x
            my -= self.margin_top

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
                        self.has_custom_spec = True
                        return True

                for i, color in enumerate(COLORS):
                    y = self.color_start_y + i * self.item_height
                    if (
                        self.col1_x <= mx < self.col1_x + int(300 * SCALE_X)
                        and y <= my < y + self.item_height
                    ):
                        self.selected_color = color
                        self.spec.base_color = color
                        self.has_custom_spec = True
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
                        self.has_custom_spec = True
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
                        self.has_custom_spec = True
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
                        self.has_custom_spec = True
                        return True

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

    def draw(self, renderer, fonts):
        renderer.set_blend_mode("alpha")

        if not self.visible:
            c = palette.get_color(121)
            msg = "Press TAB for Laboratory"
            if self.has_custom_spec:
                msg += f" | Active: Custom {self.selected_type.capitalize()} ({self.selected_color.capitalize()})"
            renderer.draw_text(
                int(20 * SCALE_X), int(50 * SCALE_Y), msg, fonts["small"], c
            )
            renderer.set_blend_mode("additive")
            return

        # Draw panel background (floating dashboard box)
        renderer.draw_rect(self.margin_x, self.margin_top, self.width, self.panel_height, (0.0, 0.0, 0.0, 0.95), fill=True)
        renderer.draw_rect(self.margin_x, self.margin_top, self.width, self.panel_height, palette.get_color(122), fill=False)

        mx_off = self.margin_x
        my_off = self.margin_top

        c_white = palette.get_color(121)
        c_gray = palette.get_color(123)
        c_green = palette.get_color(51)
        c_red = palette.get_color(1)

        renderer.draw_text(
            mx_off + int(20 * SCALE_X),
            my_off + int(20 * SCALE_Y),
            "[ FIREWORK LABORATORY ] (TAB to hide)",
            fonts["medium"],
            c_white,
        )

        renderer.draw_text(
            mx_off + self.col1_x, my_off + int(60 * SCALE_Y), "--- 1. BASE PRESET ---", fonts["small"], c_white
        )
        for i, fw_type in enumerate(FIREWORK_TYPES):
            y = my_off + self.type_start_y + i * self.item_height
            color = c_white if fw_type == self.selected_type else c_gray
            prefix = "> " if fw_type == self.selected_type else "  "
            renderer.draw_text(mx_off + self.col1_x, y, f"{prefix}{fw_type}", fonts["small"], color)

        renderer.draw_text(
            mx_off + self.col1_x, my_off + self.color_start_y - int(30 * SCALE_Y), "--- 2. COLOR ---", fonts["small"], c_white
        )
        for i, c_name in enumerate(COLORS):
            y = my_off + self.color_start_y + i * self.item_height
            color = c_white if c_name == self.selected_color else c_gray
            prefix = "> " if c_name == self.selected_color else "  "
            renderer.draw_text(
                mx_off + self.col1_x, y, f"{prefix}{c_name.capitalize()}", fonts["small"], color
            )

        renderer.draw_text(
            mx_off + self.col2_x, my_off + int(60 * SCALE_Y), "--- 3. TWEAK PHYSICS ---", fonts["small"], c_white
        )
        for i, (prop, disp, step, min_v, max_v) in enumerate(self.num_props):
            y = my_off + self.num_start_y + i * self.item_height
            val = getattr(self.spec, prop)
            renderer.draw_text(mx_off + self.col2_x, y, f"{disp}", fonts["small"], c_white)
            renderer.draw_text(mx_off + self.col2_x + int(250 * SCALE_X), y, "[-]", fonts["small"], c_gray)
            val_str = f"{val:.2f}" if isinstance(val, float) else f"{val}"
            renderer.draw_text(mx_off + self.col2_x + int(300 * SCALE_X), y, val_str, fonts["small"], c_white)
            renderer.draw_text(mx_off + self.col2_x + int(380 * SCALE_X), y, "[+]", fonts["small"], c_gray)

        renderer.draw_text(
            mx_off + self.col2_x,
            my_off + self.bool_start_y - int(30 * SCALE_Y),
            "--- 4. ATTRIBUTES ---",
            fonts["small"],
            c_white,
        )
        for i, prop in enumerate(self.bool_props):
            y = my_off + self.bool_start_y + i * self.item_height
            val = getattr(self.spec, prop)
            renderer.draw_text(mx_off + self.col2_x, y, f"{prop}", fonts["small"], c_white)
            box_text = "[X]" if val else "[ ]"
            box_color = c_green if val else c_gray
            renderer.draw_text(
                mx_off + self.col2_x + int(300 * SCALE_X), y, box_text, fonts["small"], box_color
            )

        renderer.draw_text(
            mx_off + self.col3_x, my_off + int(60 * SCALE_Y), "--- 5. DRONE SHOW ---", fonts["small"], c_white
        )
        for i, (prop, disp, step, min_v, max_v) in enumerate(self.drone_props):
            y = my_off + self.num_start_y + i * self.item_height
            val = getattr(self, prop)

            renderer.draw_text(mx_off + self.col3_x, y, f"{disp}", fonts["small"], c_white)
            renderer.draw_text(mx_off + self.col3_x + int(180 * SCALE_X), y, "[-]", fonts["small"], c_gray)

            val_str = f"{val:.2f}" if isinstance(val, float) else f"{val}"
            renderer.draw_text(mx_off + self.col3_x + int(220 * SCALE_X), y, val_str, fonts["small"], c_white)
            renderer.draw_text(mx_off + self.col3_x + int(280 * SCALE_X), y, "[+]", fonts["small"], c_gray)

        btn_y = (
            self.num_start_y
            + len(self.drone_props) * self.item_height
            + int(30 * SCALE_Y)
        )
        by = my_off + btn_y
        renderer.draw_text(mx_off + self.col3_x, by, "[ LAUNCH DRONES ] (Key: D)", fonts["small"], c_green)
        renderer.draw_text(
            mx_off + self.col3_x, by + self.item_height, "[ CLEAR DRONES ] (Key: C)", fonts["small"], c_red
        )

        renderer.draw_text(
            mx_off + int(20 * SCALE_X),
            SCREEN_HEIGHT - int(30 * SCALE_Y),
            ">>> CLICK SKY TO LAUNCH | TAB: LAB | M: TOGGLE SYSTEM METRICS <<<",
            fonts["small"],
            c_gray,
        )

        renderer.set_blend_mode("additive")
