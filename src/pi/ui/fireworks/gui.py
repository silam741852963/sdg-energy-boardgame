import pygame
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, SCALE_X, SCALE_Y, FIREWORK_TYPES, COLORS
from .models import generate_spec
from . import palette

class ControlPanel:
    def __init__(self):
        self.visible = False
        self.selected_type = FIREWORK_TYPES[0]
        self.selected_colors = [COLORS[0]]
        self.spec = generate_spec(self.selected_type)
        self.spec.colors = self.selected_colors
        self.spec.base_color = self.selected_colors[0]
        self.has_custom_spec = False

        # Keyboard Navigation state
        self.kb_col = 0
        self.kb_row = 0

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
        self.save_message = ""
        self.save_message_time = 0.0

    def update(self, events, mouse_pos, mouse_click_left) -> bool:
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    self.visible = not self.visible
                
                if self.visible:
                    if event.key == pygame.K_UP:
                        self.kb_row = max(0, self.kb_row - 1)
                    elif event.key == pygame.K_DOWN:
                        max_row = self._get_max_row_for_col(self.kb_col)
                        self.kb_row = min(max_row, self.kb_row + 1)
                    elif event.key == pygame.K_LEFT:
                        self.kb_col = max(0, self.kb_col - 1)
                        max_row = self._get_max_row_for_col(self.kb_col)
                        self.kb_row = min(max_row, self.kb_row)
                    elif event.key == pygame.K_RIGHT:
                        self.kb_col = min(2, self.kb_col + 1)
                        max_row = self._get_max_row_for_col(self.kb_col)
                        self.kb_row = min(max_row, self.kb_row)
                    elif event.key in [pygame.K_LEFTBRACKET, pygame.K_MINUS, pygame.K_KP_MINUS]:
                        self._adjust_focused_numeric(-1)
                    elif event.key in [pygame.K_RIGHTBRACKET, pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS]:
                        self._adjust_focused_numeric(1)
                    elif event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                        self._activate_focused_item()

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
                        self.spec.colors = self.selected_colors
                        self.spec.base_color = self.selected_colors[0] if self.selected_colors else COLORS[0]
                        self.has_custom_spec = True
                        return True

                for i, color in enumerate(COLORS):
                    y = self.color_start_y + i * self.item_height
                    if (
                        self.col1_x <= mx < self.col1_x + int(300 * SCALE_X)
                        and y <= my < y + self.item_height
                    ):
                        self._toggle_color_selection(color)
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
                            if prop == "multicolor":
                                self._truncate_colors_to_limit()
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
                            if prop == "multicolor":
                                self._truncate_colors_to_limit()
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
                    elif btn_y + self.item_height * 3 <= my < btn_y + self.item_height * 4:
                        self.export_current_spec()
                        return True

                return True

        return False

    def _get_max_row_for_col(self, col: int) -> int:
        if col == 0:
            return len(FIREWORK_TYPES) + len(COLORS) - 1
        elif col == 1:
            return len(self.num_props) + len(self.bool_props) - 1
        elif col == 2:
            return len(self.drone_props) + 3 - 1
        return 0

    def _adjust_focused_numeric(self, direction: int):
        if self.kb_col == 1 and self.kb_row < len(self.num_props):
            prop, disp, step, min_v, max_v = self.num_props[self.kb_row]
            val = getattr(self.spec, prop)
            if prop in ["particle_count", "life_span", "multicolor", "variant"]:
                if direction == -1:
                    new_val = int(max(min_v, val - step))
                else:
                    new_val = int(min(max_v, val + step))
                setattr(self.spec, prop, new_val)
                if prop == "multicolor":
                    self._truncate_colors_to_limit()
            else:
                if direction == -1:
                    new_val = round(max(min_v, val - step), 2)
                else:
                    new_val = round(min(max_v, val + step), 2)
                setattr(self.spec, prop, new_val)
            self.has_custom_spec = True
            
        elif self.kb_col == 2 and self.kb_row < len(self.drone_props):
            prop, disp, step, min_v, max_v = self.drone_props[self.kb_row]
            val = getattr(self, prop)
            if direction == -1:
                new_val = round(max(min_v, val - step), 2)
            else:
                new_val = round(min(max_v, val + step), 2)
            setattr(self, prop, new_val)

    def _activate_focused_item(self):
        if self.kb_col == 0:
            if self.kb_row < len(FIREWORK_TYPES):
                fw_type = FIREWORK_TYPES[self.kb_row]
                self.selected_type = fw_type
                self.spec = generate_spec(fw_type)
                self.spec.colors = self.selected_colors
                self.spec.base_color = self.selected_colors[0] if self.selected_colors else COLORS[0]
                self.has_custom_spec = True
            else:
                color_index = self.kb_row - len(FIREWORK_TYPES)
                color = COLORS[color_index]
                self._toggle_color_selection(color)
                
        elif self.kb_col == 1:
            if self.kb_row >= len(self.num_props):
                bool_index = self.kb_row - len(self.num_props)
                prop = self.bool_props[bool_index]
                val = getattr(self.spec, prop)
                setattr(self.spec, prop, not val)
                self.has_custom_spec = True
                
        elif self.kb_col == 2:
            act_row = self.kb_row - len(self.drone_props)
            if act_row == 0:
                self.trigger_drones = True
            elif act_row == 1:
                self.clear_drones = True
            elif act_row == 2:
                self.export_current_spec()

    def _toggle_color_selection(self, color: str):
        limit = self.spec.multicolor
        if color in self.selected_colors:
            if len(self.selected_colors) > 1:
                self.selected_colors.remove(color)
        else:
            if limit == 1:
                self.selected_colors = [color]
            elif len(self.selected_colors) < limit:
                self.selected_colors.append(color)
        
        self.spec.colors = self.selected_colors
        self.spec.base_color = self.selected_colors[0] if self.selected_colors else COLORS[0]
        self.has_custom_spec = True

    def _truncate_colors_to_limit(self):
        limit = self.spec.multicolor
        if len(self.selected_colors) > limit:
            self.selected_colors = self.selected_colors[:limit]
            self.spec.colors = self.selected_colors
            self.spec.base_color = self.selected_colors[0] if self.selected_colors else COLORS[0]

    def export_current_spec(self) -> bool:
        import os
        import time
        from .models import save_spec_to_file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
        filepath = os.path.join(root_dir, "resource", "firework-settings", "custom.json")
        try:
            save_spec_to_file(self.spec, filepath)
            self.save_message = "Saved to resource/firework-settings/custom.json!"
            self.save_message_time = time.time()
            print(f"[LAB] Exported custom firework setting to {filepath}")
            return True
        except Exception as e:
            self.save_message = f"Error saving spec: {e}"
            self.save_message_time = time.time()
            print(f"[LAB] Failed to save setting: {e}")
            return False

    def draw(self, renderer, fonts):
        renderer.set_blend_mode("alpha")

        if not self.visible:
            c = palette.get_color(121)
            msg = "Press TAB for Laboratory"
            if self.has_custom_spec:
                msg += f" | Active: Custom {self.selected_type.capitalize()}"
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
            is_sel = c_name in self.selected_colors
            color = c_white if is_sel else c_gray
            prefix = "[X] " if is_sel else "[ ] "
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

        export_y = btn_y + self.item_height * 3
        renderer.draw_text(
            mx_off + self.col3_x,
            my_off + export_y,
            "[ EXPORT/SAVE SETTING ] (Key: E)",
            fonts["small"],
            c_white
        )

        import time
        if getattr(self, "save_message", "") and time.time() - getattr(self, "save_message_time", 0.0) < 4.0:
            renderer.draw_text(
                mx_off + self.col3_x,
                my_off + export_y + self.item_height * 1.2,
                self.save_message,
                fonts["small"],
                c_green if "Error" not in self.save_message else c_red
            )

        # Draw keyboard navigation cursor if active
        if self.visible:
            c_yellow = (1.0, 0.8, 0.0, 1.0)
            cursor_x = 0
            cursor_y = 0
            if self.kb_col == 0:
                cursor_x = mx_off + self.col1_x - int(25 * SCALE_X)
                if self.kb_row < len(FIREWORK_TYPES):
                    cursor_y = my_off + self.type_start_y + self.kb_row * self.item_height
                else:
                    color_r = self.kb_row - len(FIREWORK_TYPES)
                    cursor_y = my_off + self.color_start_y + color_r * self.item_height
            elif self.kb_col == 1:
                cursor_x = mx_off + self.col2_x - int(25 * SCALE_X)
                if self.kb_row < len(self.num_props):
                    cursor_y = my_off + self.num_start_y + self.kb_row * self.item_height
                else:
                    bool_r = self.kb_row - len(self.num_props)
                    cursor_y = my_off + self.bool_start_y + bool_r * self.item_height
            elif self.kb_col == 2:
                cursor_x = mx_off + self.col3_x - int(25 * SCALE_X)
                if self.kb_row < len(self.drone_props):
                    cursor_y = my_off + self.num_start_y + self.kb_row * self.item_height
                else:
                    act_r = self.kb_row - len(self.drone_props)
                    if act_r == 0:
                        cursor_y = by
                    elif act_r == 1:
                        cursor_y = by + self.item_height
                    elif act_r == 2:
                        cursor_y = my_off + export_y

            renderer.draw_text(cursor_x, cursor_y, ">", fonts["small"], c_yellow)

        renderer.draw_text(
            mx_off + int(20 * SCALE_X),
            SCREEN_HEIGHT - int(30 * SCALE_Y),
            ">>> CLICK SKY TO LAUNCH | TAB: LAB | M: TOGGLE SYSTEM METRICS <<<",
            fonts["small"],
            c_gray,
        )

        renderer.set_blend_mode("additive")
