import pyxel
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
    CUSTOM_PALETTE,
    FULLSCREEN,
    COLOR_MAP,
    SCALE_X,
    SCALE_Y,
)
from .drones import DroneManager
from .lighting import LightingSystem, bake_particle_sprites
from .gui import ControlPanel
from .audio import AudioSystem
from .firework import FireworkManager
from .gauges import GaugeManager
from .scripting import ScriptManager

from config import GeneratorType

class FireworkEngine:
    def __init__(self, game_state=None, is_mock=True):
        self.game_state = game_state
        self.is_mock = is_mock
        self.audio = AudioSystem()

        pyxel.init(SCREEN_WIDTH, SCREEN_HEIGHT, fps=60, title="3D Fireworks")

        if FULLSCREEN:
            pyxel.fullscreen(True)

        pyxel.colors[: len(CUSTOM_PALETTE)] = CUSTOM_PALETTE
        bake_particle_sprites()
        pyxel.mouse(True)

        # --- NEW: Hook up the modular Drone Manager ---
        self.drone_manager = DroneManager()

        self.lighting = LightingSystem()
        self.gui = ControlPanel()

        self.firework_manager = FireworkManager(self.audio, self.lighting)
        self.gauge_manager = GaugeManager(self.game_state)
        self.script_manager = ScriptManager(self.firework_manager)
        self.completed_gauges = set()

        self.show_metrics = False
        self.fps_tracker = FPSTracker()
        self.cpu_tracker = CPUUsageTracker()
        
        self.last_interaction_time = time.time()
        self.in_attract_mode = False

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
        if self.game_state:
            self.game_state.start_new_session()
            self.completed_gauges.clear()
            self.firework_manager.particles.clear()
            self.firework_manager.shells.clear()
            self.script_manager.active_scripts.clear()
            self.drone_manager.transition_to_pattern(0, self.gui, self.audio)
            if hasattr(self, 'last_seen_gen_after_completion'):
                delattr(self, 'last_seen_gen_after_completion')

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        if pyxel.btnp(pyxel.KEY_M):
            self.show_metrics = not self.show_metrics

        self.fps_tracker.update()
        self.cpu_tracker.update()

        if self.is_mock:
            gui_captured_mouse = self.gui.update()
        else:
            gui_captured_mouse = False

        # --- ATTRACT MODE LOGIC ---
        interaction_detected = False
        if self.game_state and self.game_state.active_generator is not None:
            interaction_detected = True
        elif self.is_mock and (gui_captured_mouse or pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)):
            interaction_detected = True
        elif pyxel.btnp(pyxel.KEY_1) or pyxel.btnp(pyxel.KEY_2) or pyxel.btnp(pyxel.KEY_3) or pyxel.btnp(pyxel.KEY_4) or pyxel.btnp(pyxel.KEY_0):
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
            if pyxel.btnp(pyxel.KEY_R):
                self._restart_game()
                
            active_gen = self.game_state.active_generator
            
            is_completed = self.game_state.current_session and self.game_state.current_session.completed
            fireworks_done = len(self.script_manager.active_scripts) == 0 and len(self.firework_manager.shells) == 0 and len(self.firework_manager.particles) == 0
            
            if is_completed and fireworks_done:
                if not hasattr(self, 'last_seen_gen_after_completion'):
                    self.last_seen_gen_after_completion = active_gen
                    
                if active_gen != self.last_seen_gen_after_completion:
                    self._restart_game()

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
                # Play sound when transitioning to a different gauge/pattern (ignore startup)
                if self.drone_manager.current_index != -1:
                    self.audio.play_switch_sound()
                self.drone_manager.transition_to_pattern(target_pattern, self.gui, self.audio)

            if self.is_mock:
                # Keyboard simulation for testing
                if pyxel.btnp(pyxel.KEY_1):
                    self.game_state.set_active_generator(GeneratorType.WIND)
                elif pyxel.btnp(pyxel.KEY_2):
                    self.game_state.set_active_generator(GeneratorType.SOLAR)
                elif pyxel.btnp(pyxel.KEY_3):
                    self.game_state.set_active_generator(GeneratorType.PIEZO)
                elif pyxel.btnp(pyxel.KEY_4):
                    self.game_state.set_active_generator(GeneratorType.COIL)
                elif pyxel.btnp(pyxel.KEY_0):
                    self.game_state.set_active_generator(None)
                elif pyxel.btnp(pyxel.KEY_SPACE):
                    if self.game_state.active_generator:
                        self.game_state.add_energy(self.game_state.active_generator, 10.0)
                elif pyxel.btnp(pyxel.KEY_P):
                    self.game_state.mock_paused = not self.game_state.mock_paused

            # Check each gauge independently to trigger fireworks
            if self.game_state.current_session:
                for gen, level in self.game_state.current_session.energy_levels.items():
                    if level >= 100.0:
                        if gen not in self.completed_gauges:
                            self.completed_gauges.add(gen)
                            self.audio.play_success_chime()
                            
                            script_name = "success.json"
                            if gen == GeneratorType.WIND:
                                script_name = "wind.json"
                            elif gen == GeneratorType.SOLAR:
                                script_name = "solar.json"
                            elif gen == GeneratorType.PIEZO:
                                script_name = "piezo.json"
                            elif gen == GeneratorType.COIL:
                                script_name = "coil.json"
                                
                            script_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "resource", "firework-scripts", script_name)
                            self.script_manager.play_sequence(os.path.abspath(script_path))
                    else:
                        if gen in self.completed_gauges:
                            self.completed_gauges.remove(gen)

        # --- KEYBOARD SHORTCUTS FOR DRONE TRANSITIONS (Manual) ---
        if not self.game_state and self.is_mock:
            if pyxel.btnp(pyxel.KEY_D):
                self.drone_manager.transition_to_pattern(0, self.gui, self.audio)
            if pyxel.btnp(pyxel.KEY_RIGHT):
                self.drone_manager.next_pattern(self.gui, self.audio)
            if pyxel.btnp(pyxel.KEY_LEFT):
                self.drone_manager.prev_pattern(self.gui, self.audio)
            if pyxel.btnp(pyxel.KEY_C):
                self.drone_manager.clear_all(self.audio)

        if self.is_mock and pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and not gui_captured_mouse:
            if self.gui.visible:
                custom_spec = copy.copy(self.gui.spec)
                self.firework_manager.launch(
                    pyxel.mouse_x, pyxel.mouse_y, forced_spec=custom_spec
                )
            else:
                self.firework_manager.launch(pyxel.mouse_x, pyxel.mouse_y)

        is_completed = self.game_state and self.game_state.current_session and self.game_state.current_session.completed

        if (
            self.is_mock
            and not self.gui.visible
            and not is_completed
            and len(self.firework_manager.shells) == 0
            and len(self.firework_manager.particles) == 0
            and random.random() < 0.05
        ):
            self.firework_manager.launch(
                random.randint(int(400 * SCALE_X), SCREEN_WIDTH - int(400 * SCALE_X)),
                random.randint(int(400 * SCALE_Y), int(700 * SCALE_Y)),
            )

        self.lighting.update()

        self.firework_manager.update()

        # --- UPDATE DRONES ---
        fill_pct = 0.0
        if self.game_state and self.game_state.active_generator and self.game_state.current_session:
            from config import MAX_ENERGY_GAUGE
            active_gen = self.game_state.active_generator
            fill_pct = min(1.0, self.game_state.current_session.energy_levels.get(active_gen, 0.0) / MAX_ENERGY_GAUGE)

        self.drone_manager.update(fill_pct)
        
        # --- UPDATE GAUGES / DRAIN LOGIC ---
        if self.game_state:
            self.game_state.check_inactivity()
        self.gauge_manager.update()
        
        # --- UPDATE SCRIPTING ---
        self.script_manager.update()

    def draw(self):
        self.lighting.draw_background()
        self.lighting.draw_reflections()

        self.firework_manager.draw()

        # --- DRAW DRONES ---
        self.drone_manager.draw()
        
        # --- DRAW GAUGES ---
        if not self.in_attract_mode:
            self.gauge_manager.draw()

        if self.is_mock and not self.in_attract_mode:
            self.gui.draw()

        if self.show_metrics:
            mw = int(250 * SCALE_X)
            mh = int(160 * SCALE_Y)
            mx = SCREEN_WIDTH - mw - int(20 * SCALE_X)
            my = int(20 * SCALE_Y)
            pyxel.rect(mx, my, mw, mh, 0)
            pyxel.rectb(mx, my, mw, mh, 122)

            text_offset_x = int(15 * SCALE_X)
            self.gui.draw_text_scaled(
                mx + text_offset_x,
                my + int(15 * SCALE_Y),
                "[ SYSTEM METRICS ]",
                121,
            )
            self.gui.draw_text_scaled(
                mx + text_offset_x,
                my + int(38 * SCALE_Y),
                f"FPS: {self.fps_tracker.fps:.1f}",
                121,
            )
            self.gui.draw_text_scaled(
                mx + text_offset_x,
                my + int(60 * SCALE_Y),
                f"CPU: {self.cpu_tracker.cpu_usage:.1f}%",
                121,
            )
            self.gui.draw_text_scaled(
                mx + text_offset_x,
                my + int(82 * SCALE_Y),
                f"RAM: {self.get_memory_usage():.1f} MB",
                121,
            )
            self.gui.draw_text_scaled(
                mx + text_offset_x,
                my + int(104 * SCALE_Y),
                f"Particles: {len(self.firework_manager.particles)}",
                121,
            )
            self.gui.draw_text_scaled(
                mx + text_offset_x,
                my + int(126 * SCALE_Y),
                f"Drones: {len(self.drone_manager.drones)}",
                121,
            )

        is_completed = self.game_state and self.game_state.current_session and self.game_state.current_session.completed
        fireworks_done = len(self.script_manager.active_scripts) == 0 and len(self.firework_manager.shells) == 0 and len(self.firework_manager.particles) == 0

        if is_completed and fireworks_done:
            # Draw overlay and leaderboard
            overlay_w = int(600 * SCALE_X)
            overlay_h = int(400 * SCALE_Y)
            ox = (SCREEN_WIDTH - overlay_w) // 2
            oy = (SCREEN_HEIGHT - overlay_h) // 2
            
            pyxel.rect(ox, oy, overlay_w, overlay_h, 0)
            pyxel.rectb(ox, oy, overlay_w, overlay_h, 122)

            self.gui.draw_text_scaled(
                ox + int(150 * SCALE_X),
                oy + int(40 * SCALE_Y),
                "=== GENERATOR CHARGED ===",
                51,
            )
            
            self.gui.draw_text_scaled(
                ox + int(120 * SCALE_X),
                oy + int(100 * SCALE_Y),
                "--- TOP 5 FASTEST STUDENTS ---",
                121,
            )
            
            for i, rank in enumerate(self.game_state.rankings[:5]):
                y_pos = oy + int(140 * SCALE_Y) + (i * int(40 * SCALE_Y))
                self.gui.draw_text_scaled(
                    ox + int(80 * SCALE_X),
                    y_pos,
                    f"{i+1}. {rank.player_name}",
                    122,
                )
                self.gui.draw_text_scaled(
                    ox + int(400 * SCALE_X),
                    y_pos,
                    f"{rank.time_taken:.2f}s",
                    51,
                )
                
            self.gui.draw_text_scaled(
                ox + int(140 * SCALE_X),
                oy + overlay_h - int(60 * SCALE_Y),
                "[ PRESS 'R' TO RESTART CHALLENGE ]",
                121,
            )


    def run(self):
        pyxel.run(self.update, self.draw)


def run():
    app = FireworkEngine()
    app.run()


if __name__ == "__main__":
    run()
