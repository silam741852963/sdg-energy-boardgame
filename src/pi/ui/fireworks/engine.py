import pygame
import moderngl
import random
import copy
import time
import os


class FPSTracker:
    def __init__(self):
        self.last_time = time.time()
        self.frame_count = 0
        self.fps = 0.0

    def update(self):
        self.frame_count += 1
        now = time.time()
        elapsed = now - self.last_time
        if elapsed >= 0.5:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.last_time = now
        return self.fps


class CPUUsageTracker:
    def __init__(self):
        self.last_time = time.time()
        self.last_cpu_time = time.process_time()
        self.cpu_usage = 0.0

    def update(self):
        now = time.time()
        now_cpu = time.process_time()
        elapsed = now - self.last_time
        if elapsed >= 0.5:
            elapsed_cpu = now_cpu - self.last_cpu_time
            self.cpu_usage = (elapsed_cpu / elapsed) * 100.0
            self.last_time = now
            self.last_cpu_time = now_cpu
        return self.cpu_usage


from .config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FULLSCREEN,
    COLOR_MAP,
    SCALE_X,
    SCALE_Y,
)
from .drones import DroneManager
from .lighting import LightingSystem
from .gui import ControlPanel
from .audio import AudioSystem
from .firework import FireworkManager
from .gauges import GaugeManager
from .scripting import ScriptManager
from .particles import Particle
from .renderer import Renderer
from . import palette

from config import GeneratorType


class FireworkEngine:
    def __init__(self, game_state=None, is_mock=None, mock_ble=False, mock_hall=False):
        self.game_state = game_state
        if is_mock is not None:
            self.is_mock = is_mock
            self.mock_ble = is_mock
            self.mock_hall = is_mock
        else:
            self.is_mock = mock_hall
            self.mock_ble = mock_ble
            self.mock_hall = mock_hall
        self.audio = AudioSystem()

        # Initialize Pygame and ModernGL
        pygame.init()
        pygame.font.init()

        flags = pygame.OPENGL | pygame.DOUBLEBUF
        if FULLSCREEN:
            flags |= pygame.FULLSCREEN
            # Get actual desktop size for native fullscreen to prevent centering/scaling issues
            info = pygame.display.Info()
            init_w = info.current_w if info.current_w > 0 else SCREEN_WIDTH
            init_h = info.current_h if info.current_h > 0 else SCREEN_HEIGHT
        else:
            init_w, init_h = SCREEN_WIDTH, SCREEN_HEIGHT

        self.screen = pygame.display.set_mode((init_w, init_h), flags)
        pygame.display.set_caption("3D Fireworks")

        # Hide OS cursor to prevent scaling/position mismatches and support custom retro cursor
        pygame.mouse.set_visible(False)
        self.mouse_pos = (960, 540)

        self.ctx = moderngl.create_context()
        self.renderer = Renderer(self.ctx)
        self.clock = pygame.time.Clock()
        self.running = True
        self.frame_count = 0

        # Load monospace system fonts for a retro/game/programming vibe
        font_names = [
            "jetbrainsmononerdfont",
            "jetbrainsmononerdfontmono",
            "caskaydiamononerdfont",
            "caskaydiamononerdfontmono",
            "monospace",
            "liberationmono",
            "dejavusansmono",
            "courier",
        ]
        # Load fonts at their actual native target size (no longer halved/scaled 2.0x)
        # to ensure crisp, clean outlines of all retro characters and symbols.
        self.fonts = {
            "small": pygame.font.SysFont(font_names, int(18 * SCALE_Y)),
            "medium": pygame.font.SysFont(font_names, int(24 * SCALE_Y)),
            "large": pygame.font.SysFont(font_names, int(36 * SCALE_Y)),
            "xlarge": pygame.font.SysFont(font_names, int(48 * SCALE_Y)),
        }

        # Hook up the modular Drone Manager
        self.drone_manager = DroneManager()
        self.lighting = LightingSystem()
        self.gui = ControlPanel()

        self.firework_manager = FireworkManager(self.audio, self.lighting)
        self.gauge_manager = GaugeManager(self.game_state)
        self.script_manager = ScriptManager(self.firework_manager)
        self.completed_gauges = set()
        self.completion_time = None
        self.drones_cleared = False
        self.show_leaderboard = False
        self.leaderboard_start_activity_time = 0.0
        self.show_started = False
        self.completed_gen = None
        self.congrat_start_time = None

        # Player name entry state
        self.show_name_entry = False
        self.name_input = ""
        self.name_suggestion = ""
        self.player_base = []

        self.show_metrics = False
        self.fps_tracker = FPSTracker()
        self.cpu_tracker = CPUUsageTracker()

        self.last_interaction_time = time.time()
        self.in_attract_mode = False
        self.prev_energy_levels = {}
        self.last_fill_sound_time = 0.0

        # Interactive combos & Simon Says local states
        self.simon_says_prev_target = None
        self.simon_says_celebration_start = None
        self.last_combo_spark_time = 0.0
        self.screen_shake_amount = 0.0
        self.konami_unlocked = False
        self.love_mode_active = False
        self.love_celebration_count = 0
        self.love_celebration_timer = 0

        # Load or initialize easter egg specs from files
        self._init_easter_egg_specs()

    def get_memory_usage(self):
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return float(parts[1]) / 1024.0
        except Exception:
            pass
        return 0.0

    def _restart_game(self):
        self.audio.play_restart_sound()
        if self.game_state:
            self.game_state.start_new_session()
            self.game_state.set_active_generator(None)
            self.game_state.drain_paused = False
            self.completed_gauges.clear()
            self.firework_manager.particles.clear()
            self.firework_manager.shells.clear()
            self.script_manager.active_scripts.clear()
            self.konami_unlocked = False
            self.love_mode_active = False
            self.love_celebration_count = 0
            self.love_celebration_timer = 0
            self.drone_manager.transition_to_pattern(0, self.gui, self.audio)
            if hasattr(self, "last_seen_gen_after_completion"):
                delattr(self, "last_seen_gen_after_completion")
            # Reset animated levels of all gauges to 0.0 to prevent visual autoplay re-trigger
            for gen in self.gauge_manager.state:
                self.gauge_manager.state[gen]["level"] = 0.0
        self.completion_time = None
        self.drones_cleared = False
        self.show_leaderboard = False
        self.leaderboard_start_activity_time = 0.0
        self.show_started = False
        self.completed_gen = None
        self.congrat_start_time = None
        self.prev_energy_levels = {}
        self.show_name_entry = False
        self.name_input = ""
        self.name_suggestion = ""

    def _update_name_suggestion(self):
        if not self.name_input:
            self.name_suggestion = ""
            return
        inp_lower = self.name_input.lower()
        for player in self.player_base:
            if player.lower().startswith(inp_lower):
                self.name_suggestion = player
                return
        self.name_suggestion = ""

    def update(self, events):
        self.frame_count += 1
        self.fps_tracker.update()
        self.cpu_tracker.update()

        # Check if ranking board / name entry should be cancelled due to selecting a different generator
        if (self.show_name_entry or self.show_leaderboard) and self.game_state:
            active_gen = self.game_state.active_generator
            if active_gen is not None and active_gen != self.completed_gen:
                self.game_state.discard_current_ranking()
                self._restart_game()
                self.game_state.set_active_generator(active_gen)

        # Get actual logical window size from Pygame
        try:
            win_w, win_h = pygame.display.get_window_size()
        except AttributeError:
            win_w, win_h = self.screen.get_size()

        # 1. Map raw mouse coordinates in logical window space
        raw_mx, raw_my = pygame.mouse.get_pos()

        # 2. Calculate aspect ratio fitting in logical space (matching renderer.py end_frame)
        target_aspect = 1920.0 / 1080.0
        win_aspect = float(win_w) / float(win_h) if win_h > 0 else target_aspect

        if win_aspect > target_aspect:
            # Pillarbox
            w_fit = win_h * target_aspect
            h_fit = win_h
            offset_x = (win_w - w_fit) / 2.0
            offset_y = 0.0
        else:
            # Letterbox
            w_fit = win_w
            h_fit = w_fit / target_aspect
            offset_x = 0.0
            offset_y = (win_h - h_fit) / 2.0

        scale_x = 1920.0 / w_fit if w_fit > 0 else 1.0
        scale_y = 1080.0 / h_fit if h_fit > 0 else 1.0

        # 3. Translate to 1920x1080 virtual space
        mx = (raw_mx - offset_x) * scale_x
        my = (raw_my - offset_y) * scale_y
        mouse_pos = (int(mx), int(my))
        self.mouse_pos = mouse_pos

        if self.show_name_entry:
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.game_state:
                            self.game_state.update_player_name(
                                self.game_state.current_session.player_name
                            )
                        self.show_name_entry = False
                        self.show_leaderboard = True
                        self.leaderboard_start_activity_time = (
                            self.game_state.last_activity_time
                        )
                    elif event.key == pygame.K_BACKSPACE:
                        self.name_input = self.name_input[:-1]
                        self._update_name_suggestion()
                    elif event.key in (pygame.K_TAB, pygame.K_RIGHT):
                        if self.name_suggestion and len(self.name_suggestion) > len(
                            self.name_input
                        ):
                            self.name_input = self.name_suggestion
                            self.name_suggestion = ""
                    elif event.key == pygame.K_RETURN:
                        entered_name = self.name_input.strip()
                        if not entered_name:
                            entered_name = (
                                self.game_state.current_session.player_name
                                if self.game_state
                                else "Student"
                            )

                        if self.game_state:
                            self.game_state.update_player_name(entered_name)
                            self.game_state.add_player_to_base(entered_name)

                        self.show_name_entry = False
                        self.show_leaderboard = True
                        self.leaderboard_start_activity_time = (
                            self.game_state.last_activity_time
                        )
                    else:
                        if (
                            event.unicode
                            and event.unicode.isprintable()
                            and len(self.name_input) < 18
                        ):
                            self.name_input += event.unicode
                            self._update_name_suggestion()

            self.lighting.update()
            self.firework_manager.update()
            self.drone_manager.update(self.frame_count, 0.0)
            self.gauge_manager.update()
            return

        mouse_clicked_left = False
        click_pos = mouse_pos  # Fallback to current mouse position

        key_r_pressed = False
        key_d_pressed = False
        key_c_pressed = False
        key_right_pressed = False
        key_left_pressed = False
        key_1_pressed = False
        key_2_pressed = False
        key_3_pressed = False
        key_4_pressed = False
        key_5_pressed = False
        key_6_pressed = False
        key_7_pressed = False
        key_0_pressed = False
        key_space_pressed = False
        key_p_pressed = False
        key_e_pressed = False

        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mouse_clicked_left = True
                    click_x = (event.pos[0] - offset_x) * scale_x
                    click_y = (event.pos[1] - offset_y) * scale_y
                    click_pos = (int(click_x), int(click_y))
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self.running = False
                elif event.key == pygame.K_m:
                    self.show_metrics = not self.show_metrics
                elif event.key == pygame.K_r:
                    key_r_pressed = True
                elif event.key == pygame.K_d:
                    key_d_pressed = True
                elif event.key == pygame.K_c:
                    key_c_pressed = True
                elif event.key == pygame.K_RIGHT:
                    key_right_pressed = True
                elif event.key == pygame.K_LEFT:
                    key_left_pressed = True
                elif event.key == pygame.K_1:
                    key_1_pressed = True
                elif event.key == pygame.K_2:
                    key_2_pressed = True
                elif event.key == pygame.K_3:
                    key_3_pressed = True
                elif event.key == pygame.K_4:
                    key_4_pressed = True
                elif event.key == pygame.K_0:
                    key_0_pressed = True
                elif event.key == pygame.K_SPACE:
                    key_space_pressed = True
                elif event.key == pygame.K_p:
                    key_p_pressed = True
                elif event.key == pygame.K_e:
                    key_e_pressed = True
                elif event.key == pygame.K_5:
                    key_5_pressed = True
                elif event.key == pygame.K_6:
                    key_6_pressed = True
                elif event.key == pygame.K_7:
                    key_7_pressed = True
                elif event.key == pygame.K_s:
                    self.audio.toggle_music()

        if key_e_pressed:
            self.gui.export_current_spec()

        if self.is_mock:
            gui_captured_mouse = self.gui.update(events, click_pos, mouse_clicked_left)
            if gui_captured_mouse:
                self.audio.play_tick_sound()
        else:
            gui_captured_mouse = False

        # --- ATTRACT MODE LOGIC ---
        interaction_detected = False
        if self.game_state and self.game_state.active_generator is not None:
            interaction_detected = True
        elif self.is_mock and (gui_captured_mouse or pygame.mouse.get_pressed()[0]):
            interaction_detected = True
        elif (
            key_1_pressed
            or key_2_pressed
            or key_3_pressed
            or key_4_pressed
            or key_0_pressed
        ):
            interaction_detected = True

        if interaction_detected:
            self.last_interaction_time = time.time()

        # --- HARDWARE STATE SYNC ---
        if self.game_state:
            if key_r_pressed:
                self._restart_game()

            active_gen = self.game_state.active_generator

            is_completed = (
                self.game_state.current_session
                and self.game_state.current_session.completed
            )
            fireworks_done = (
                len(self.script_manager.active_scripts) == 0
                and len(self.firework_manager.shells) == 0
                and len(self.firework_manager.particles) == 0
            )

            # After fireworks are done, show END drones first, then the leaderboard
            if is_completed and self.show_started:
                if fireworks_done and self.congrat_start_time is None:
                    # Transition drones to END pattern (index 7) with a gold color override
                    self.drone_manager.transition_to_pattern(
                        7, self.gui, self.audio, override_color="gold"
                    )
                    self.congrat_start_time = time.time()
                    if self.game_state:
                        self.game_state.drain_paused = False
                        if self.completed_gen:
                            self.game_state.force_immediate_drain(self.completed_gen)

                if (
                    self.congrat_start_time is not None
                    and not self.show_leaderboard
                    and not self.show_name_entry
                ):
                    if time.time() - self.congrat_start_time >= 4.0:
                        self.show_name_entry = True
                        self.name_input = ""
                        self.name_suggestion = ""
                        if self.game_state:
                            self.player_base = self.game_state.load_player_base()
                        else:
                            self.player_base = []
                        self.drone_manager.clear_all()

            # Check for key presses or other signals to close leaderboard
            if self.show_leaderboard:
                any_key_pressed = False
                for event in events:
                    if event.type == pygame.KEYDOWN:
                        any_key_pressed = True
                        break
                new_activity = False
                if (
                    self.game_state
                    and self.game_state.last_activity_time
                    > self.leaderboard_start_activity_time
                ):
                    new_activity = True
                if any_key_pressed or new_activity:
                    self._restart_game()

            if not is_completed:
                if getattr(self, "love_mode_active", False):
                    target_pattern = 8
                    override_c = "red"
                else:
                    active_gen = self.game_state.active_generator
                    target_pattern = 0  # 0 is Ablic
                    if active_gen == GeneratorType.WIND:
                        target_pattern = 1
                    elif active_gen == GeneratorType.SOLAR:
                        target_pattern = 2
                    elif active_gen == GeneratorType.PIEZO:
                        target_pattern = 3
                    elif active_gen == GeneratorType.COIL:
                        target_pattern = 4
                    override_c = (
                        "rainbow"
                        if (
                            target_pattern == 0
                            and getattr(self, "konami_unlocked", False)
                        )
                        else None
                    )

                if self.drone_manager.current_index != target_pattern:
                    if self.drone_manager.current_index != -1:
                        self.audio.play_switch_sound()
                    self.drone_manager.transition_to_pattern(
                        target_pattern, self.gui, self.audio, override_color=override_c
                    )

            if self.is_mock or self.mock_hall:
                pressed_keys = pygame.key.get_pressed()
                mock_active_sensors = []
                if pressed_keys[pygame.K_1]:
                    mock_active_sensors.append(GeneratorType.WIND)
                if pressed_keys[pygame.K_2]:
                    mock_active_sensors.append(GeneratorType.SOLAR)
                if pressed_keys[pygame.K_3]:
                    mock_active_sensors.append(GeneratorType.PIEZO)
                if pressed_keys[pygame.K_4]:
                    mock_active_sensors.append(GeneratorType.COIL)

                # Keep keys 5, 6, 7 as quick helper buttons for keyboard ghosting/easy testing
                if pressed_keys[pygame.K_5]:
                    mock_active_sensors = [GeneratorType.WIND, GeneratorType.SOLAR]
                elif pressed_keys[pygame.K_6]:
                    mock_active_sensors = [GeneratorType.PIEZO, GeneratorType.COIL]
                elif pressed_keys[pygame.K_7]:
                    mock_active_sensors = [
                        GeneratorType.WIND,
                        GeneratorType.SOLAR,
                        GeneratorType.PIEZO,
                        GeneratorType.COIL,
                    ]

                if set(mock_active_sensors) != set(self.game_state.active_sensors):
                    self.game_state.set_active_sensors(mock_active_sensors)

            if self.mock_ble:
                if key_space_pressed:
                    if self.game_state.active_generator:
                        self.game_state.add_energy(
                            self.game_state.active_generator, 10.0, is_clean_boost=True
                        )
                elif key_p_pressed:
                    self.game_state.mock_paused = not self.game_state.mock_paused
                    self.audio.play_switch_sound()

            # Check each gauge independently to trigger fireworks
            if self.game_state.current_session:
                for gen in self.gauge_manager.generators:
                    st_level = self.gauge_manager.state[gen]["level"]
                    if st_level >= 100.0:
                        if gen not in self.completed_gauges:
                            self.completed_gauges.add(gen)
                            self.audio.play_success_chime()
                            self.completion_time = time.time()
                            self.drones_cleared = False
                            self.show_started = False
                            self.completed_gen = gen
                            if self.game_state:
                                self.game_state.drain_paused = True

                            # Transition drones to CLEAR pattern (index 6) with matching color
                            gen_color = "silver"
                            if gen == GeneratorType.WIND:
                                gen_color = "cyan"
                            elif gen == GeneratorType.SOLAR:
                                gen_color = "yellow"
                            elif gen == GeneratorType.PIEZO:
                                gen_color = "orange"
                            elif gen == GeneratorType.COIL:
                                gen_color = "blue"

                            self.drone_manager.transition_to_pattern(
                                6, self.gui, self.audio, override_color=gen_color
                            )
                    else:
                        if gen in self.completed_gauges:
                            self.completed_gauges.remove(gen)

            # Delay fireworks show by 1.5 seconds to let user read CLEAR pattern
            if self.completion_time is not None and not self.show_started:
                if time.time() - self.completion_time >= 1.5:
                    script_name = "wind.json"
                    if self.completed_gen == GeneratorType.WIND:
                        script_name = "wind.json"
                    elif self.completed_gen == GeneratorType.SOLAR:
                        script_name = "solar.json"
                    elif self.completed_gen == GeneratorType.PIEZO:
                        script_name = "piezo.json"
                    elif self.completed_gen == GeneratorType.COIL:
                        script_name = "coil.json"

                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    script_path = os.path.join(
                        current_dir,
                        "..",
                        "..",
                        "..",
                        "..",
                        "resource",
                        "firework-scripts",
                        script_name,
                    )

                    self.script_manager.play_sequence(script_path)
                    self.show_started = True
                    self.completion_time = (
                        time.time()
                    )  # Reset timer to be relative to show start

            # Clear drones after 1.5 seconds into the firework show
            if (
                self.completion_time is not None
                and self.show_started
                and not self.drones_cleared
            ):
                if time.time() - self.completion_time >= 1.5:
                    self.drone_manager.clear_all()
                    self.drones_cleared = True

        # --- KEYBOARD SHORTCUTS FOR DRONE TRANSITIONS (Manual) ---
        if not self.game_state and self.is_mock:
            if key_d_pressed:
                self.drone_manager.transition_to_pattern(0, self.gui, self.audio)
            if key_right_pressed:
                self.drone_manager.next_pattern(self.gui, self.audio)
            if key_left_pressed:
                self.drone_manager.prev_pattern(self.gui, self.audio)
            if key_c_pressed:
                self.drone_manager.clear_all(self.audio)

        if self.is_mock and mouse_clicked_left and not gui_captured_mouse:
            # Check if we clicked on any gauge to set it active
            clicked_gauge = False
            for gen in self.gauge_manager.generators:
                st = self.gauge_manager.state[gen]
                if st["scale"] > 0.1:
                    w = 1200 * SCALE_X * st["scale"]
                    h = 60 * SCALE_Y * st["scale"]
                    x = (SCREEN_WIDTH / 2) - (w / 2)
                    y = st["y"] - (h / 2)
                    if x <= click_pos[0] <= x + w and y <= click_pos[1] <= y + h:
                        self.game_state.set_active_generator(gen)
                        clicked_gauge = True
                        break

            if not clicked_gauge:
                if self.gui.visible or self.gui.has_custom_spec:
                    custom_spec = copy.copy(self.gui.spec)
                    self.firework_manager.launch(
                        click_pos[0], click_pos[1], forced_spec=custom_spec
                    )
                else:
                    self.firework_manager.launch(click_pos[0], click_pos[1])

        self.lighting.update()
        self.firework_manager.update()

        # --- UPDATE DRONES ---
        fill_pct = 0.0
        if (
            self.game_state
            and self.game_state.active_generator
            and self.game_state.current_session
        ):
            from config import MAX_ENERGY_GAUGE

            active_gen = self.game_state.active_generator
            st_level = self.gauge_manager.state.get(active_gen, {}).get("level", 0.0)
            fill_pct = min(1.0, st_level / MAX_ENERGY_GAUGE)

        self.drone_manager.update(self.frame_count, fill_pct)

        # --- UPDATE GAUGES / DRAIN LOGIC ---
        if self.game_state:
            self.game_state.check_inactivity()
        self.gauge_manager.update()

        # --- INTERACTIVE COMBOS & EASTER EGGS LOGIC ---
        if self.game_state:
            # 1. Konami Combo (Concept A)
            if self.game_state.trigger_konami_combo:
                self.game_state.trigger_konami_combo = False
                self.audio.play_combo_unlock()
                self.konami_unlocked = True
                # Rainbow shifting Ablic logo
                self.drone_manager.transition_to_pattern(
                    0, self.gui, self.audio, override_color="rainbow"
                )
                # Trigger continuous supernova count
                self.konami_supernova_count = 35
                self.konami_supernova_timer = 0

            # Reset Combo (reverse Konami)
            if getattr(self.game_state, "trigger_reset_combo", False):
                self.game_state.trigger_reset_combo = False
                self._restart_game()

            # Love Combo (101022 - Solar/Wind/Solar/Wind/Piezo/Piezo)
            if getattr(self.game_state, "trigger_love_combo", False):
                self.game_state.trigger_love_combo = False
                self.audio.play_combo_unlock()
                self.love_mode_active = True

                # Load and play the secret/schneider.json show immediately
                current_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(
                    current_dir,
                    "..",
                    "..",
                    "..",
                    "..",
                    "resource",
                    "firework-scripts",
                    "secret",
                    "schneider.json",
                )
                self.script_manager.play_sequence(script_path)

                self.drone_manager.transition_to_pattern(
                    8, self.gui, self.audio, override_color="red"
                )

            # Spawn supernova fireworks for Konami combo
            if (
                hasattr(self, "konami_supernova_count")
                and self.konami_supernova_count > 0
            ):
                self.konami_supernova_timer += 1
                if self.konami_supernova_timer % 6 == 0:
                    self.konami_supernova_count -= 1
                    # Launch random large multi-color firework
                    colors_list = [
                        "red",
                        "yellow",
                        "green",
                        "cyan",
                        "blue",
                        "magenta",
                        "pink",
                        "orange",
                    ]
                    fw_color = random.choice(colors_list)
                    spec = copy.copy(self.spec_konami)
                    spec.base_color = fw_color
                    spec.colors = [fw_color]
                    self.firework_manager.launch(
                        random.randint(int(300 * SCALE_X), int(1600 * SCALE_X)),
                        random.randint(int(200 * SCALE_Y), int(600 * SCALE_Y)),
                        forced_spec=spec,
                    )

            # 2. Rhythm Spin Challenge / Overdrive (Concept B) - Removed
            pass

            # 3. Synchronized Dual Generation / Combos (Concept C)
            sensors = self.game_state.active_sensors
            is_hybrid_green = (
                GeneratorType.WIND in sensors and GeneratorType.SOLAR in sensors
            )
            is_kinetic_induction = (
                GeneratorType.PIEZO in sensors and GeneratorType.COIL in sensors
            )
            is_super_overload = len(sensors) == 4

            if is_super_overload:
                # Shake screen and launch supernova finale
                self.screen_shake_amount = 15.0
                if self.frame_count % 20 == 0:
                    spec = copy.copy(self.spec_super_overload)
                    self.firework_manager.launch(
                        random.randint(int(600 * SCALE_X), int(1320 * SCALE_X)),
                        random.randint(int(300 * SCALE_Y), int(500 * SCALE_Y)),
                        forced_spec=spec,
                    )
                    self.audio.play_explosion(spec, 0, -200)  # center/far blast sound
            elif is_hybrid_green:
                # Hybrid Helix: green and yellow spiraling fireworks
                if self.frame_count % 35 == 0:
                    spec = copy.copy(self.spec_hybrid)
                    self.firework_manager.launch(
                        random.randint(int(500 * SCALE_X), int(1400 * SCALE_X)),
                        random.randint(int(300 * SCALE_Y), int(600 * SCALE_Y)),
                        forced_spec=spec,
                    )
            elif is_kinetic_induction:
                # Sparkler sparks + sound
                current_time = time.time()
                if current_time - self.last_combo_spark_time >= 0.25:
                    self.last_combo_spark_time = current_time
                    self.audio.play_electric_spark()
                    # Spawn sparkling crossette
                    spec = copy.copy(self.spec_kinetic)
                    self.firework_manager.launch(
                        random.randint(int(600 * SCALE_X), int(1300 * SCALE_X)),
                        random.randint(int(350 * SCALE_Y), int(550 * SCALE_Y)),
                        forced_spec=spec,
                    )

            # Apply screen shake displacement to renderer
            if hasattr(self, "screen_shake_amount") and self.screen_shake_amount > 0.1:
                dx = random.uniform(-self.screen_shake_amount, self.screen_shake_amount)
                dy = random.uniform(-self.screen_shake_amount, self.screen_shake_amount)
                self.renderer.screen_shake = (dx, dy)
                self.screen_shake_amount *= 0.9  # Decay screen shake
            else:
                self.renderer.screen_shake = (0.0, 0.0)

            # 4. Simon Says Idle Mode (Concept D)
            is_completed = (
                self.game_state.current_session
                and self.game_state.current_session.completed
            )
            total_energy = (
                sum(self.game_state.current_session.energy_levels.values())
                if self.game_state.current_session
                else 0.0
            )
            is_system_idle = (
                (not is_completed)
                and (total_energy == 0.0)
                and (self.game_state.active_generator is None)
            )

            if is_system_idle and not self.show_leaderboard:
                current_time = time.time()
                if current_time - self.game_state.last_activity_time >= 6.0:
                    if not self.game_state.simon_says_active:
                        self.game_state.simon_says_active = True
                        self.game_state.simon_says_sequence = [
                            random.choice(self.gauge_manager.generators)
                            for _ in range(5)
                        ]
                        self.game_state.simon_says_step = 0
                        self.game_state.simon_says_target = (
                            self.game_state.simon_says_sequence[0]
                        )
                        self.game_state.simon_says_last_target_time = current_time
                        self.simon_says_prev_target = None
                        print("[SIMON-SAYS] Mode Started!")
            else:
                if self.game_state.simon_says_active:
                    self.game_state.simon_says_active = False
                    self.game_state.simon_says_target = None
                    self.simon_says_celebration_start = None

            if self.game_state.simon_says_active:
                current_time = time.time()
                target = self.game_state.simon_says_target

                if target and target != self.simon_says_prev_target:
                    self.audio.play_simon_note(target.name)
                    self.simon_says_prev_target = target
                    self.game_state.simon_says_last_target_time = current_time

                if target and target in sensors:
                    self.audio.play_success_chime()

                    st = self.gauge_manager.state[target]
                    w = 1200 * SCALE_X * st["scale"]
                    x_pos = int((SCREEN_WIDTH / 2) - (w / 2) + 20 * SCALE_X)
                    y_pos = int(st["y"])

                    self.firework_manager.launch(x_pos, y_pos - 150)

                    self.game_state.simon_says_step += 1
                    if self.game_state.simon_says_step >= len(
                        self.game_state.simon_says_sequence
                    ):
                        print("[SIMON-SAYS] Completed! Celebration triggered!")
                        self.audio.play_combo_unlock()
                        self.simon_says_celebration_start = current_time
                        self.game_state.simon_says_active = False
                        self.game_state.simon_says_target = None
                    else:
                        self.game_state.simon_says_target = (
                            self.game_state.simon_says_sequence[
                                self.game_state.simon_says_step
                            ]
                        )
                        self.game_state.simon_says_last_target_time = current_time
                        self.simon_says_prev_target = None

            if self.simon_says_celebration_start is not None:
                elapsed_cel = time.time() - self.simon_says_celebration_start
                if elapsed_cel < 5.0:
                    if self.frame_count % 15 == 0:
                        colors = ["yellow", "cyan", "magenta", "lime", "pink"]
                        c = random.choice(colors)
                        from .models import generate_spec

                        spec = generate_spec("Strobe")
                        spec.base_color = c
                        spec.colors = [c]
                        spec.radius = 1.8
                        spec.particle_count = 180
                        self.firework_manager.launch(
                            random.randint(int(350 * SCALE_X), int(1570 * SCALE_X)),
                            random.randint(int(200 * SCALE_Y), int(550 * SCALE_Y)),
                            forced_spec=spec,
                        )
                else:
                    self.simon_says_celebration_start = None

        # --- COMPARE ENERGY LEVELS FOR FILL SOUND ---
        if self.game_state and self.game_state.current_session:
            from config import MAX_ENERGY_GAUGE

            for gen in self.gauge_manager.generators:
                prev_val = self.prev_energy_levels.get(gen, 0.0)
                curr_val = self.gauge_manager.state.get(gen, {}).get("level", 0.0)

                prev_pct = int(min(1.0, max(0.0, prev_val / MAX_ENERGY_GAUGE)) * 100)
                curr_pct = int(min(1.0, max(0.0, curr_val / MAX_ENERGY_GAUGE)) * 100)

                if curr_pct > prev_pct:
                    self.audio.play_fill_sound(curr_pct / 100.0)
                    if getattr(self, "love_mode_active", False):
                        colors_list = ["pink", "magenta", "red", "gold"]
                        fw_color = random.choice(colors_list)
                        spec = copy.copy(self.spec_love)
                        spec.base_color = fw_color
                        spec.colors = [fw_color]
                        self.firework_manager.launch(
                            random.randint(int(400 * SCALE_X), int(1520 * SCALE_X)),
                            random.randint(int(250 * SCALE_Y), int(500 * SCALE_Y)),
                            forced_spec=spec,
                        )

        # --- UPDATE SCRIPTING ---
        self.script_manager.update(
            love_mode_active=getattr(self, "love_mode_active", False)
        )

        # Save animated energy levels for the next frame's comparison
        self.prev_energy_levels = {}
        for gen in self.gauge_manager.generators:
            self.prev_energy_levels[gen] = self.gauge_manager.state.get(gen, {}).get(
                "level", 0.0
            )

    def draw(self):
        # 1. Start frame (binds offscreen framebuffer and sets viewport to 1920x1080)
        self.renderer.start_frame()

        # 2. Clear background & reflections
        self.lighting.draw_background(self.renderer)
        self.lighting.draw_reflections(self.renderer)

        # 3. Draw fireworks (using instanced renderer)
        self.firework_manager.draw(self.renderer, self.frame_count)

        # 4. Draw drones
        show_debug = self.mock_ble or self.mock_hall
        self.drone_manager.draw(
            self.renderer,
            self.fonts["small"],
            self.frame_count,
            show_debug_text=show_debug,
        )

        # 5. Draw gauges
        if not self.in_attract_mode:
            self.gauge_manager.draw(self.renderer, self.fonts, self.frame_count)

        if not self.in_attract_mode:
            # Draw debug mode label
            debug_label = None
            if self.mock_ble and self.mock_hall:
                debug_label = "DEBUG MODE: ALL MOCKED"
            elif self.mock_ble:
                debug_label = "DEBUG MODE: BLE MOCKED"
            elif self.mock_hall:
                debug_label = "DEBUG MODE: HALL-IC MOCKED"

            if debug_label:
                self.renderer.set_blend_mode("alpha")
                paused_str = (
                    " (PAUSED)"
                    if (self.game_state and self.game_state.mock_paused)
                    else ""
                )
                self.renderer.draw_text(
                    int(20 * SCALE_X),
                    SCREEN_HEIGHT - int(80 * SCALE_Y),
                    f"{debug_label}{paused_str}",
                    self.fonts["small"],
                    palette.get_color(122),
                )
                self.renderer.set_blend_mode("additive")

        # 6. Draw laboratory GUI
        if self.is_mock and not self.in_attract_mode:
            self.gui.draw(self.renderer, self.fonts)
            self.draw_cursor()

        # 7. Metrics overlay
        if self.show_metrics:
            mw = int(250 * SCALE_X)
            mh = int(185 * SCALE_Y)
            mx = SCREEN_WIDTH - mw - int(20 * SCALE_X)
            my = int(20 * SCALE_Y)

            self.renderer.set_blend_mode("alpha")
            self.renderer.draw_rect(mx, my, mw, mh, (0.0, 0.0, 0.0, 0.95), fill=True)
            self.renderer.draw_rect(mx, my, mw, mh, palette.get_color(122), fill=False)

            text_offset_x = int(15 * SCALE_X)
            c_white = palette.get_color(121)

            self.renderer.draw_text(
                mx + text_offset_x,
                my + int(15 * SCALE_Y),
                "[ SYSTEM METRICS ]",
                self.fonts["small"],
                c_white,
            )
            self.renderer.draw_text(
                mx + text_offset_x,
                my + int(38 * SCALE_Y),
                f"FPS: {self.fps_tracker.fps:.1f}",
                self.fonts["small"],
                c_white,
            )
            self.renderer.draw_text(
                mx + text_offset_x,
                my + int(60 * SCALE_Y),
                f"CPU: {self.cpu_tracker.cpu_usage:.1f}%",
                self.fonts["small"],
                c_white,
            )
            self.renderer.draw_text(
                mx + text_offset_x,
                my + int(82 * SCALE_Y),
                f"RAM: {self.get_memory_usage():.1f} MB",
                self.fonts["small"],
                c_white,
            )
            self.renderer.draw_text(
                mx + text_offset_x,
                my + int(104 * SCALE_Y),
                f"Particles: {len(self.firework_manager.particles)}",
                self.fonts["small"],
                c_white,
            )
            self.renderer.draw_text(
                mx + text_offset_x,
                my + int(126 * SCALE_Y),
                f"Drones: {len(self.drone_manager.drones)}",
                self.fonts["small"],
                c_white,
            )
            self.renderer.draw_text(
                mx + text_offset_x,
                my + int(148 * SCALE_Y),
                f"Pool: {len(self.firework_manager.particle_system.free_indices)}/{self.firework_manager.particle_system.max_particles}",
                self.fonts["small"],
                c_white,
            )
            self.renderer.set_blend_mode("additive")

        if self.show_name_entry:
            # Draw overlay and name entry
            overlay_w = int(600 * SCALE_X)
            overlay_h = int(300 * SCALE_Y)
            ox = (SCREEN_WIDTH - overlay_w) // 2
            oy = (SCREEN_HEIGHT - overlay_h) // 2

            self.renderer.set_blend_mode("alpha")
            self.renderer.draw_rect(
                ox, oy, overlay_w, overlay_h, (0.0, 0.0, 0.0, 0.95), fill=True
            )
            self.renderer.draw_rect(
                ox, oy, overlay_w, overlay_h, palette.get_color(122), fill=False
            )

            # Title
            title_text = "=== ENTER YOUR NAME ==="
            font_med = self.fonts["medium"]
            tw, _ = font_med.size(title_text)
            tx = ox + (overlay_w - tw) // 2
            self.renderer.draw_text(
                tx,
                oy + int(40 * SCALE_Y),
                title_text,
                font_med,
                palette.get_color(51),
            )

            # Subtitle
            sub_text = "Type name for the Leaderboard"
            font_small = self.fonts["small"]
            sw, _ = font_small.size(sub_text)
            sx = ox + (overlay_w - sw) // 2
            self.renderer.draw_text(
                sx,
                oy + int(85 * SCALE_Y),
                sub_text,
                font_small,
                palette.get_color(121),
            )

            # Input box
            box_w = int(400 * SCALE_X)
            box_h = int(50 * SCALE_Y)
            bx = ox + (overlay_w - box_w) // 2
            by = oy + int(130 * SCALE_Y)

            self.renderer.draw_rect(
                bx, by, box_w, box_h, (0.1, 0.1, 0.1, 0.8), fill=True
            )
            self.renderer.draw_rect(
                bx, by, box_w, box_h, palette.get_color(51), fill=False
            )

            # Cursor blinking
            cursor_char = "_" if (self.frame_count // 30) % 2 == 0 else " "

            # Input text
            input_display_text = self.name_input
            font_input = self.fonts["medium"]
            text_x = bx + int(15 * SCALE_X)
            text_y = by + (box_h - font_input.size("A")[1]) // 2

            self.renderer.draw_text(
                text_x,
                text_y,
                input_display_text,
                font_input,
                palette.get_color(122),
            )

            input_width, _ = font_input.size(input_display_text)
            self.renderer.draw_text(
                text_x + input_width,
                text_y,
                cursor_char,
                font_input,
                palette.get_color(122),
            )

            # Autocomplete suggestion
            if self.name_suggestion and len(self.name_suggestion) > len(
                self.name_input
            ):
                suffix = self.name_suggestion[len(self.name_input) :]
                self.renderer.draw_text(
                    text_x + input_width,
                    text_y,
                    suffix,
                    font_input,
                    (0.4, 0.4, 0.4, 0.8),
                )

                # Tab hint
                hint_text = "[ Press 'TAB' or 'RIGHT' to auto-fill ]"
                hw, _ = font_small.size(hint_text)
                hx = ox + (overlay_w - hw) // 2
                self.renderer.draw_text(
                    hx,
                    by + box_h + int(10 * SCALE_Y),
                    hint_text,
                    font_small,
                    (0.5, 0.5, 0.5, 1.0),
                )

            # Bottom instructions
            bottom_text = "[ PRESS ENTER TO SUBMIT | ESC TO SKIP ]"
            bw, _ = font_small.size(bottom_text)
            bx_bottom = ox + (overlay_w - bw) // 2
            self.renderer.draw_text(
                bx_bottom,
                oy + overlay_h - int(45 * SCALE_Y),
                bottom_text,
                font_small,
                palette.get_color(121),
            )
            self.renderer.set_blend_mode("additive")

        if self.show_leaderboard:
            # Draw overlay and leaderboard
            overlay_w = int(600 * SCALE_X)
            overlay_h = int(400 * SCALE_Y)
            ox = (SCREEN_WIDTH - overlay_w) // 2
            oy = (SCREEN_HEIGHT - overlay_h) // 2

            self.renderer.set_blend_mode("alpha")
            self.renderer.draw_rect(
                ox, oy, overlay_w, overlay_h, (0.0, 0.0, 0.0, 0.95), fill=True
            )
            self.renderer.draw_rect(
                ox, oy, overlay_w, overlay_h, palette.get_color(122), fill=False
            )

            # Center title: "=== GENERATOR CHARGED ===" (dynamically generated based on completed generator)
            gen = self.completed_gen or GeneratorType.WIND
            title_text = f"=== {gen.value.upper()} CHARGED ==="
            font_med = self.fonts["medium"]
            tw, _ = font_med.size(title_text)
            tx = ox + (overlay_w - tw) // 2
            self.renderer.draw_text(
                tx,
                oy + int(40 * SCALE_Y),
                title_text,
                font_med,
                palette.get_color(51),
            )

            # Center subtitle: "--- TOP 5 FASTEST STUDENTS ---"
            sub_text = "--- TOP 5 FASTEST STUDENTS ---"
            font_small = self.fonts["small"]
            sw, _ = font_small.size(sub_text)
            sx = ox + (overlay_w - sw) // 2
            self.renderer.draw_text(
                sx,
                oy + int(100 * SCALE_Y),
                sub_text,
                font_small,
                palette.get_color(121),
            )

            # Center leaderboard entries as a column block
            col1_x = ox + int(130 * SCALE_X)
            col2_x = ox + int(370 * SCALE_X)

            rankings_list = []
            if isinstance(self.game_state.rankings, dict):
                rankings_list = self.game_state.rankings.get(gen, [])
            else:
                rankings_list = self.game_state.rankings

            for i, rank in enumerate(rankings_list[:5]):
                y_pos = oy + int(140 * SCALE_Y) + (i * int(40 * SCALE_Y))
                self.renderer.draw_text(
                    col1_x,
                    y_pos,
                    f"{i + 1}. {rank.player_name}",
                    font_small,
                    palette.get_color(122),
                )
                self.renderer.draw_text(
                    col2_x,
                    y_pos,
                    f"{rank.time_taken:.2f}s",
                    font_small,
                    palette.get_color(51),
                )

            if self.mock_ble or self.mock_hall:
                # Center bottom text: "[ PRESS 'R' TO RESTART CHALLENGE ]"
                restart_text = "[ PRESS 'R' TO RESTART CHALLENGE ]"
                rw, _ = font_small.size(restart_text)
                rx = ox + (overlay_w - rw) // 2
                self.renderer.draw_text(
                    rx,
                    oy + overlay_h - int(60 * SCALE_Y),
                    restart_text,
                    font_small,
                    palette.get_color(121),
                )
            self.renderer.set_blend_mode("additive")

        # 8. End frame (blits the offscreen framebuffer to the centered screen viewport)
        try:
            screen_w, screen_h = pygame.display.get_window_size()
        except AttributeError:
            screen_w, screen_h = self.screen.get_size()
        self.renderer.end_frame(screen_w, screen_h)

    def draw_cursor(self):
        if not pygame.mouse.get_focused():
            return
        cx, cy = self.mouse_pos
        c_white = palette.get_color(121)
        c_border = palette.get_color(123)

        # Set blend mode to alpha for UI layout
        self.renderer.set_blend_mode("alpha")

        # Draw a retro pixel arrow cursor
        # Outer border
        self.renderer.draw_line(cx, cy, cx, cy + 15, c_border)
        self.renderer.draw_line(cx, cy, cx + 10, cy + 10, c_border)
        self.renderer.draw_line(cx, cy + 15, cx + 3, cy + 12, c_border)
        self.renderer.draw_line(cx + 10, cy + 10, cx + 5, cy + 10, c_border)
        self.renderer.draw_line(cx + 3, cy + 12, cx + 5, cy + 17, c_border)
        self.renderer.draw_line(cx + 5, cy + 10, cx + 7, cy + 15, c_border)
        self.renderer.draw_line(cx + 5, cy + 17, cx + 7, cy + 15, c_border)

        # Inner Fill
        for i in range(1, 10):
            self.renderer.draw_line(cx + 1, cy + i, cx + i - 1, cy + i, c_white)
        self.renderer.draw_line(cx + 1, cy + 10, cx + 3, cy + 10, c_white)
        self.renderer.draw_line(cx + 1, cy + 11, cx + 2, cy + 11, c_white)
        self.renderer.draw_line(cx + 2, cy + 12, cx + 3, cy + 12, c_white)
        self.renderer.draw_line(cx + 3, cy + 13, cx + 4, cy + 13, c_white)
        self.renderer.draw_line(cx + 4, cy + 14, cx + 5, cy + 14, c_white)

        self.renderer.set_blend_mode("additive")

    def load_easter_egg_spec(self, egg_name, fallback_creator):
        import os
        from .models import load_spec_from_file, save_spec_to_file

        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
        filepath = os.path.join(
            root_dir, "resource", "firework-settings", f"{egg_name}.json"
        )

        if os.path.exists(filepath):
            try:
                spec = load_spec_from_file(filepath)
                print(f"[ENGINE] Loaded easter egg '{egg_name}' spec from {filepath}")
                return spec
            except Exception as e:
                print(
                    f"[ENGINE] Error loading '{egg_name}' spec: {e}. Reverting to default."
                )

        spec = fallback_creator()
        try:
            save_spec_to_file(spec, filepath)
            print(f"[ENGINE] Created default '{egg_name}' spec at {filepath}")
        except Exception as e:
            print(f"[ENGINE] Failed to save default '{egg_name}' spec: {e}")
        return spec

    def _init_easter_egg_specs(self):
        def create_konami():
            from .models import generate_spec

            spec = generate_spec("Peony")
            spec.radius = 2.0
            spec.particle_count = 250
            spec.colors = [
                "red",
                "yellow",
                "green",
                "cyan",
                "blue",
                "magenta",
                "pink",
                "orange",
            ]
            return spec

        # create_overdrive removed

        def create_hybrid():
            from .models import generate_spec

            spec = generate_spec("Pistil")
            spec.particle_count = 200
            spec.radius = 1.6
            spec.colors = ["green", "yellow"]
            return spec

        def create_kinetic():
            from .models import generate_spec

            spec = generate_spec("Crossette")
            spec.particle_count = 80
            spec.radius = 1.2
            spec.colors = ["cyan", "blue", "silver"]
            return spec

        def create_super_overload():
            from .models import generate_spec

            spec = generate_spec("Waterfall")
            spec.base_color = "gold"
            spec.colors = ["gold"]
            spec.particle_count = 350
            spec.radius = 2.5
            spec.intensity = 2.5
            return spec

        def create_love_heart():
            from .models import generate_spec

            spec = generate_spec("Heart")
            spec.particle_count = 250
            spec.radius = 2.0
            spec.colors = ["pink", "magenta", "red", "gold"]
            return spec

        self.spec_konami = self.load_easter_egg_spec("konami", create_konami)
        self.spec_hybrid = self.load_easter_egg_spec("hybrid", create_hybrid)
        self.spec_kinetic = self.load_easter_egg_spec("kinetic", create_kinetic)
        self.spec_super_overload = self.load_easter_egg_spec(
            "super_overload", create_super_overload
        )
        self.spec_love = self.load_easter_egg_spec("love_heart", create_love_heart)

    def run(self):
        while self.running:
            events = pygame.event.get()
            self.update(events)
            if not self.running:
                break
            self.draw()
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


def run():
    app = FireworkEngine()
    app.run()


if __name__ == "__main__":
    run()
