import pyxel
import random
import copy
import time


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


class FireworkEngine:
    def __init__(self):
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

        self.show_metrics = False
        self.fps_tracker = FPSTracker()
        self.cpu_tracker = CPUUsageTracker()

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

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        if pyxel.btnp(pyxel.KEY_M):
            self.show_metrics = not self.show_metrics

        self.fps_tracker.update()
        self.cpu_tracker.update()

        gui_captured_mouse = self.gui.update()

        # --- KEYBOARD SHORTCUTS FOR DRONE TRANSITIONS ---
        if pyxel.btnp(pyxel.KEY_D):
            self.drone_manager.transition_to_pattern(0, self.gui, self.audio)
        if pyxel.btnp(pyxel.KEY_RIGHT):
            self.drone_manager.next_pattern(self.gui, self.audio)
        if pyxel.btnp(pyxel.KEY_LEFT):
            self.drone_manager.prev_pattern(self.gui, self.audio)
        if pyxel.btnp(pyxel.KEY_C):
            self.drone_manager.clear_all(self.audio)

        # --- GUI BUTTON SIGNALS ---
        if self.gui.trigger_drones:
            self.gui.trigger_drones = False
            self.drone_manager.transition_to_pattern(0, self.gui, self.audio)

        if self.gui.clear_drones:
            self.gui.clear_drones = False
            self.drone_manager.clear_all(self.audio)

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and not gui_captured_mouse:
            if self.gui.visible:
                custom_spec = copy.copy(self.gui.spec)
                self.firework_manager.launch(
                    pyxel.mouse_x, pyxel.mouse_y, forced_spec=custom_spec
                )
            else:
                self.firework_manager.launch(pyxel.mouse_x, pyxel.mouse_y)

        if (
            not self.gui.visible
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
        self.drone_manager.update()

    def draw(self):
        self.lighting.draw_background()
        self.lighting.draw_reflections()

        self.firework_manager.draw()

        # --- DRAW DRONES ---
        self.drone_manager.draw()

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


def run():
    app = FireworkEngine()
    pyxel.run(app.update, app.draw)


if __name__ == "__main__":
    run()
