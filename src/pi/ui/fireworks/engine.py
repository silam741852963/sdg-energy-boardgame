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
            "courier"
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

        self.show_metrics = False
        self.fps_tracker = FPSTracker()
        self.cpu_tracker = CPUUsageTracker()
        
        self.last_interaction_time = time.time()
        self.in_attract_mode = False
        self.prev_energy_levels = {}
        self.last_fill_sound_time = 0.0

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
            self.drone_manager.transition_to_pattern(0, self.gui, self.audio)
            if hasattr(self, 'last_seen_gen_after_completion'):
                delattr(self, 'last_seen_gen_after_completion')
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

    def update(self, events):
        self.frame_count += 1
        self.fps_tracker.update()
        self.cpu_tracker.update()



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
        key_0_pressed = False
        key_space_pressed = False
        key_p_pressed = False

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
                elif event.key == pygame.K_s:
                    self.audio.toggle_music()

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
        elif key_1_pressed or key_2_pressed or key_3_pressed or key_4_pressed or key_0_pressed:
            interaction_detected = True

        if interaction_detected:
            self.last_interaction_time = time.time()
            if self.in_attract_mode:
                self.in_attract_mode = False
                self._restart_game()

        if time.time() - self.last_interaction_time > 60.0:
            if not self.in_attract_mode:
                self.in_attract_mode = True
                self._restart_game()
                
        if self.in_attract_mode:
            # Randomly cycle drones every 10 seconds
            if int(time.time()) % 10 == 0 and int(time.time() * 60) % 60 == 0:
                random_pattern = random.randint(1, 4)
                self.drone_manager.transition_to_pattern(random_pattern, self.gui, self.audio)
            
            # Occasionally spawn random fireworks
            if random.random() < 0.02:
                self.firework_manager.launch(random.randint(400, 1500), random.randint(100, 300))

        # --- HARDWARE STATE SYNC ---
        if self.game_state:
            if key_r_pressed:
                self._restart_game()
                
            active_gen = self.game_state.active_generator
            
            is_completed = self.game_state.current_session and self.game_state.current_session.completed
            fireworks_done = len(self.script_manager.active_scripts) == 0 and len(self.firework_manager.shells) == 0 and len(self.firework_manager.particles) == 0
            
            # After fireworks are done, show CONGRAT drones first, then the leaderboard
            if is_completed and len(self.completed_gauges) > 0 and self.show_started:
                if fireworks_done and self.congrat_start_time is None:
                    # Transition drones to CONGRAT pattern (index 7) with a gold color override
                    self.drone_manager.transition_to_pattern(7, self.gui, self.audio, override_color="gold")
                    self.congrat_start_time = time.time()
                
                if self.congrat_start_time is not None and not self.show_leaderboard:
                    if time.time() - self.congrat_start_time >= 8.0:
                        self.show_leaderboard = True
                        self.drone_manager.clear_all()
                        self.leaderboard_start_activity_time = self.game_state.last_activity_time
                        if self.game_state:
                            self.game_state.drain_paused = False

            # Check for key presses or other signals to close leaderboard
            if self.show_leaderboard:
                any_key_pressed = False
                for event in events:
                    if event.type == pygame.KEYDOWN:
                        any_key_pressed = True
                        break
                new_activity = False
                if self.game_state and self.game_state.last_activity_time > self.leaderboard_start_activity_time:
                    new_activity = True
                if any_key_pressed or new_activity:
                    self._restart_game()

            if not is_completed:
                active_gen = self.game_state.active_generator
                target_pattern = 0 # 0 is Ablic
                if active_gen == GeneratorType.WIND:
                    target_pattern = 1
                elif active_gen == GeneratorType.SOLAR:
                    target_pattern = 2
                elif active_gen == GeneratorType.PIEZO:
                    target_pattern = 3
                elif active_gen == GeneratorType.COIL:
                    target_pattern = 4
                    
                if self.drone_manager.current_index != target_pattern:
                    if self.drone_manager.current_index != -1:
                        self.audio.play_switch_sound()
                    self.drone_manager.transition_to_pattern(target_pattern, self.gui, self.audio)

            if self.is_mock:
                if key_1_pressed:
                    self.game_state.set_active_generator(GeneratorType.WIND)
                elif key_2_pressed:
                    self.game_state.set_active_generator(GeneratorType.SOLAR)
                elif key_3_pressed:
                    self.game_state.set_active_generator(GeneratorType.PIEZO)
                elif key_4_pressed:
                    self.game_state.set_active_generator(GeneratorType.COIL)
                elif key_0_pressed:
                    self.game_state.set_active_generator(None)
                elif key_space_pressed:
                    if self.game_state.active_generator:
                        is_cb = True if self.mock_ble else False
                        self.game_state.add_energy(self.game_state.active_generator, 10.0, is_clean_boost=is_cb)
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
                                
                            self.drone_manager.transition_to_pattern(6, self.gui, self.audio, override_color=gen_color)
                    else:
                        if gen in self.completed_gauges:
                            self.completed_gauges.remove(gen)

            # Delay fireworks show by 4.0 seconds to let user read CLEAR pattern
            if self.completion_time is not None and not self.show_started:
                if time.time() - self.completion_time >= 4.0:
                    script_name = "success.json"
                    if self.completed_gen == GeneratorType.WIND:
                        script_name = "wind.json"
                    elif self.completed_gen == GeneratorType.SOLAR:
                        script_name = "solar.json"
                    elif self.completed_gen == GeneratorType.PIEZO:
                        script_name = "piezo.json"
                    elif self.completed_gen == GeneratorType.COIL:
                        script_name = "coil.json"
                        
                    script_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "resource", "firework-scripts", script_name)
                    self.script_manager.play_sequence(os.path.abspath(script_path))
                    self.show_started = True
                    self.completion_time = time.time()  # Reset timer to be relative to show start

            # Clear drones after 3.0 seconds into the firework show
            if self.completion_time is not None and self.show_started and not self.drones_cleared:
                if time.time() - self.completion_time >= 3.0:
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
        if self.game_state and self.game_state.active_generator and self.game_state.current_session:
            from config import MAX_ENERGY_GAUGE
            active_gen = self.game_state.active_generator
            st_level = self.gauge_manager.state.get(active_gen, {}).get("level", 0.0)
            fill_pct = min(1.0, st_level / MAX_ENERGY_GAUGE)

        self.drone_manager.update(self.frame_count, fill_pct)
        
        # --- UPDATE GAUGES / DRAIN LOGIC ---
        if self.game_state:
            self.game_state.check_inactivity()
        self.gauge_manager.update()

        # Play fill sound if active generator animated level increased (per integer percentage)
        if self.game_state and self.game_state.current_session and not self.game_state.current_session.completed:
            active_gen = self.game_state.active_generator
            if active_gen:
                curr_val = self.gauge_manager.state.get(active_gen, {}).get("level", 0.0)
                prev_val = self.prev_energy_levels.get(active_gen, 0.0)
                curr_int = int(curr_val)
                prev_int = int(prev_val)
                if curr_int > prev_int:
                    from config import MAX_ENERGY_GAUGE
                    # Play sound for each integer percent gained in this step
                    for p in range(prev_int + 1, curr_int + 1):
                        fill_pct = min(1.0, p / MAX_ENERGY_GAUGE)
                        self.audio.play_fill_sound(fill_pct)
        
        # --- UPDATE SCRIPTING ---
        self.script_manager.update()

        # Save animated energy levels for the next frame's comparison
        self.prev_energy_levels = {}
        for gen in self.gauge_manager.generators:
            self.prev_energy_levels[gen] = self.gauge_manager.state.get(gen, {}).get("level", 0.0)

    def draw(self):
        # 1. Start frame (binds offscreen framebuffer and sets viewport to 1920x1080)
        self.renderer.start_frame()

        # 2. Clear background & reflections
        self.lighting.draw_background(self.renderer)
        self.lighting.draw_reflections(self.renderer)

        # 3. Draw fireworks (using instanced renderer)
        self.firework_manager.draw(self.renderer, self.frame_count)

        # 4. Draw drones
        self.drone_manager.draw(self.renderer, self.fonts["small"], self.frame_count)
        
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
                paused_str = " (PAUSED)" if (self.game_state and self.game_state.mock_paused) else ""
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
            
            self.renderer.draw_text(mx + text_offset_x, my + int(15 * SCALE_Y), "[ SYSTEM METRICS ]", self.fonts["small"], c_white)
            self.renderer.draw_text(mx + text_offset_x, my + int(38 * SCALE_Y), f"FPS: {self.fps_tracker.fps:.1f}", self.fonts["small"], c_white)
            self.renderer.draw_text(mx + text_offset_x, my + int(60 * SCALE_Y), f"CPU: {self.cpu_tracker.cpu_usage:.1f}%", self.fonts["small"], c_white)
            self.renderer.draw_text(mx + text_offset_x, my + int(82 * SCALE_Y), f"RAM: {self.get_memory_usage():.1f} MB", self.fonts["small"], c_white)
            self.renderer.draw_text(mx + text_offset_x, my + int(104 * SCALE_Y), f"Particles: {len(self.firework_manager.particles)}", self.fonts["small"], c_white)
            self.renderer.draw_text(mx + text_offset_x, my + int(126 * SCALE_Y), f"Drones: {len(self.drone_manager.drones)}", self.fonts["small"], c_white)
            self.renderer.draw_text(mx + text_offset_x, my + int(148 * SCALE_Y), f"Pool: {len(self.firework_manager.particle_system.free_indices)}/{self.firework_manager.particle_system.max_particles}", self.fonts["small"], c_white)
            self.renderer.set_blend_mode("additive")

        if self.show_leaderboard:
            # Draw overlay and leaderboard
            overlay_w = int(600 * SCALE_X)
            overlay_h = int(400 * SCALE_Y)
            ox = (SCREEN_WIDTH - overlay_w) // 2
            oy = (SCREEN_HEIGHT - overlay_h) // 2
            
            self.renderer.set_blend_mode("alpha")
            self.renderer.draw_rect(ox, oy, overlay_w, overlay_h, (0.0, 0.0, 0.0, 0.95), fill=True)
            self.renderer.draw_rect(ox, oy, overlay_w, overlay_h, palette.get_color(122), fill=False)

            # Center title: "=== GENERATOR CHARGED ==="
            title_text = "=== GENERATOR CHARGED ==="
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
            
            for i, rank in enumerate(self.game_state.rankings[:5]):
                y_pos = oy + int(140 * SCALE_Y) + (i * int(40 * SCALE_Y))
                self.renderer.draw_text(
                    col1_x,
                    y_pos,
                    f"{i+1}. {rank.player_name}",
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
