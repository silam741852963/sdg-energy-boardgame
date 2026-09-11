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
from .pixel_font import PixelFont
from .rocket_scene import MissionPhase, RocketScene
from . import palette

from ...config import GeneratorType
from ...logic.game_state import MissionEventKind


LAUNCH_FIREWORK_SCALES = {
    # The two-cell celebration starts at the previous four-cell intensity.
    2: (1.16, 1.12, 1.10),
    3: (1.35, 1.28, 1.18),
    4: (1.58, 1.46, 1.28),
}


class FireworkEngine:
    def __init__(
        self,
        game_state=None,
        is_mock=None,
        mock_ble=False,
        mock_hall=False,
    ):
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
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(
            pygame.GL_CONTEXT_PROFILE_MASK,
            pygame.GL_CONTEXT_PROFILE_CORE,
        )

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
        pygame.display.set_caption("Sot-kun Rocket Mission")

        # Hide OS cursor to prevent scaling/position mismatches and support custom retro cursor
        pygame.mouse.set_visible(False)
        self.mouse_pos = (960, 540)

        # Rendering has no software/Pygame drawing fallback: startup requires a
        # shader-capable OpenGL 3.3 context (V3D on the target Raspberry Pi).
        self.ctx = moderngl.create_context(require=330)
        self.gpu_info = {
            "vendor": self.ctx.info.get("GL_VENDOR", "unknown"),
            "renderer": self.ctx.info.get("GL_RENDERER", "unknown"),
            "version": self.ctx.info.get("GL_VERSION", "unknown"),
        }
        renderer_name = self.gpu_info["renderer"].lower()
        if any(
            marker in renderer_name
            for marker in ("llvmpipe", "softpipe", "swrast", "software rasterizer")
        ):
            raise RuntimeError(
                "Hardware-accelerated OpenGL is required; "
                f"detected software renderer: {self.gpu_info['renderer']}"
            )
        self.renderer = Renderer(self.ctx)
        self.pixel_font = PixelFont()
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
            "xxlarge": pygame.font.SysFont(font_names, int(72 * SCALE_Y)),
            "bold_large": pygame.font.SysFont(font_names, int(40 * SCALE_Y), bold=True),
            "bold_xlarge": pygame.font.SysFont(font_names, int(58 * SCALE_Y), bold=True),
            "bold_xxlarge": pygame.font.SysFont(font_names, int(92 * SCALE_Y), bold=True),
        }

        # Hook up the modular Drone Manager
        self.drone_manager = DroneManager()
        self.lighting = LightingSystem()
        self.gui = ControlPanel()

        self.firework_manager = FireworkManager(self.audio, self.lighting)
        self.gauge_manager = GaugeManager(self.game_state)
        self.script_manager = ScriptManager(self.firework_manager)
        self.rocket_scene = RocketScene(self.firework_manager, self.audio)
        self.last_frame_time = time.monotonic()
        self.mock_selected = []
        self.snapshot = self.game_state.snapshot() if self.game_state else None
        self.prev_selected_generators = (
            tuple(self.snapshot.selected_generators) if self.snapshot else ()
        )
        self.completed_gauges = set()
        self.completion_time = None
        self.drones_cleared = False
        self.show_leaderboard = False
        self.leaderboard_start_activity_time = 0.0
        self.show_started = False
        self.completed_gen = None
        self.completed_gen_was_active = False
        self.congrat_start_time = None

        self.show_name_entry = False
        self.name_input = ""
        self.name_suggestion = ""
        self.player_base = []
        self.leaderboard_search_input = ""
        self.name_entry_completed = False
        self.ranking_display_entry = None

        self.show_metrics = False
        self.fps_tracker = FPSTracker()
        self.cpu_tracker = CPUUsageTracker()

        self.last_interaction_time = time.time()
        self.in_attract_mode = False
        self.prev_energy_levels = {}
        self.last_fill_sound_time = 0.0

        self.drone_manager.transition_to_pattern(0, self.gui)

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
            self._reset_mission_input()
            self.firework_manager.particles.clear()
            self.firework_manager.shells.clear()
            self.script_manager.active_scripts.clear()
            self.rocket_scene.reset()
            self.gauge_manager.reset()
            self.drone_manager.transition_to_pattern(0, self.gui)
            self.snapshot = self.game_state.snapshot()
            self.prev_selected_generators = tuple(self.snapshot.selected_generators)
        self.completion_time = None
        self.drones_cleared = False
        self.show_leaderboard = False
        self.leaderboard_start_activity_time = 0.0
        self.show_started = False
        self.completed_gen = None
        self.completed_gen_was_active = False
        self.congrat_start_time = None
        self.prev_energy_levels = {}
        self.show_name_entry = False
        self.name_input = ""
        self.name_suggestion = ""
        self.leaderboard_search_input = ""
        self.name_entry_completed = False
        self.ranking_display_entry = None

    def _begin_ranking_flow(self):
        entry = self.game_state.current_ranking_entry
        if entry is None:
            self._finish_ranking_flow()
            return
        self.ranking_display_entry = entry
        self.player_base = self.game_state.load_player_base()
        known_names = {name.casefold() for name in self.player_base}
        for rankings in self.game_state.rankings.values():
            for ranking in rankings:
                key = ranking.player_name.casefold()
                if key not in known_names:
                    self.player_base.append(ranking.player_name)
                    known_names.add(key)
        self.name_input = ""
        self.name_suggestion = ""
        self.leaderboard_search_input = ""
        self.show_name_entry = True
        self.show_leaderboard = False

    def _finish_ranking_flow(self, discard_pending=False):
        if discard_pending and self.game_state:
            self.game_state.discard_current_ranking()
        self.show_name_entry = False
        self.show_leaderboard = False
        self.name_input = ""
        self.name_suggestion = ""
        self.leaderboard_search_input = ""
        self.ranking_display_entry = None
        self.rocket_scene.release_record_hold()

    def _handle_ranking_key(self, event):
        if self.show_name_entry:
            if event.key == pygame.K_ESCAPE:
                self._finish_ranking_flow(discard_pending=True)
            elif event.key == pygame.K_RETURN:
                result = self.game_state.update_player_name(self.name_input)
                if result:
                    self.game_state.add_player_to_base(result.player_name)
                self.player_base = self.game_state.load_player_base()
                self.show_name_entry = False
                self.show_leaderboard = True
            elif event.key == pygame.K_BACKSPACE:
                self.name_input = self.name_input[:-1]
                self._update_name_suggestion()
            elif event.key in (pygame.K_TAB, pygame.K_RIGHT):
                if self.name_suggestion:
                    self.name_input = self.name_suggestion
                    self._update_name_suggestion()
            elif event.unicode and event.unicode.isprintable() and len(self.name_input) < 18:
                self.name_input += event.unicode
                self._update_name_suggestion()
            return True

        if self.show_leaderboard:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self._finish_ranking_flow()
            elif event.key == pygame.K_BACKSPACE:
                self.leaderboard_search_input = self.leaderboard_search_input[:-1]
            elif event.unicode and event.unicode.isprintable() and len(self.leaderboard_search_input) < 18:
                self.leaderboard_search_input += event.unicode
            return True
        return False

    def _reset_mission_input(self):
        """Reset mission state without leaving stale or swallowed selectors."""
        self.game_state.reset_mission()
        if self.mock_hall:
            # Keep only inputs that the state accepted as genuinely rearmed.
            # Old launch keys otherwise remain toggled on, making the first
            # post-reset keypress remove them instead of selecting them.
            accepted = list(self.game_state.snapshot().selected_generators)
            self.mock_selected[:] = accepted
            self.game_state.set_active_sensors(accepted)

    def _toggle_mock_hall_sensor(self, generator):
        """Move the debug Sot-kun selector to a generator, or lift it off."""
        if self.mock_selected == [generator]:
            self.mock_selected.clear()
        else:
            self.mock_selected[:] = [generator]
        self.game_state.set_active_sensors(list(self.mock_selected))

    def _sync_gameplay_input_gate(self):
        if not self.game_state:
            return
        phase = self.rocket_scene.phase
        input_blocked = phase in (
            MissionPhase.CRASH,
            MissionPhase.IGNITION,
            MissionPhase.ASCENT,
            MissionPhase.DEPARTURE,
        )
        changed = self.game_state.set_gameplay_inputs_enabled(not input_blocked)
        if changed and not input_blocked and phase is MissionPhase.ATTRACT:
            self.audio.play_mission_ready()

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
        fps = self.fps_tracker.update()
        self.cpu_tracker.update()
        now = time.monotonic()
        dt = min(0.1, now - self.last_frame_time)
        self.last_frame_time = now
        self._sync_gameplay_input_gate()

        mouse_clicked = False
        mouse_position = pygame.mouse.get_pos()
        charge_keys = {
            pygame.K_q: GeneratorType.SOLAR,
            pygame.K_w: GeneratorType.WIND,
            pygame.K_e: GeneratorType.COIL,
            pygame.K_r: GeneratorType.HAND_CRANK,
        }
        selector_keys = {
            pygame.K_1: GeneratorType.SOLAR,
            pygame.K_2: GeneratorType.WIND,
            pygame.K_3: GeneratorType.COIL,
            pygame.K_4: GeneratorType.HAND_CRANK,
        }

        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_clicked = True
            elif event.type == pygame.KEYDOWN:
                if self._handle_ranking_key(event):
                    continue
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_m:
                    self.show_metrics = not self.show_metrics
                elif event.key == pygame.K_BACKSPACE:
                    self._restart_game()
                elif event.key == pygame.K_F5 and self.is_mock:
                    self.gui.export_current_spec()
                elif event.key == pygame.K_0 and self.mock_hall:
                    self.mock_selected.clear()
                    self.game_state.set_active_sensors([])
                elif event.key in selector_keys and self.mock_hall:
                    self._toggle_mock_hall_sensor(selector_keys[event.key])
                elif event.key in charge_keys and self.mock_ble:
                    self.game_state.add_energy(
                        charge_keys[event.key],
                        10.0,
                        is_clean_boost=True,
                    )

        if self.is_mock:
            captured = self.gui.update(events, mouse_position, mouse_clicked)
            if mouse_clicked and not captured and self.gui.has_custom_spec:
                custom_spec = copy.copy(self.gui.spec)
                self.firework_manager.launch(
                    mouse_position[0], mouse_position[1], forced_spec=custom_spec
                )

        if not self.game_state:
            self.lighting.update()
            self.script_manager.update()
            self.firework_manager.update()
            self.drone_manager.update(self.frame_count, 1.0)
            return

        if self.show_name_entry or self.show_leaderboard:
            self.snapshot = self.game_state.snapshot()
            self.rocket_scene.sustain_record_hold(dt, fps or 60.0)
            self.audio.update_mission_audio(
                self.rocket_scene.phase.name,
                self.rocket_scene.crash_progress,
            )
            self.lighting.update()
            self.script_manager.update()
            self.firework_manager.update()
            self.drone_manager.update(self.frame_count, 1.0)
            return

        self.game_state.check_inactivity()
        self.snapshot = self.game_state.snapshot()
        self._play_selection_feedback(self.snapshot)
        for mission_event in self.game_state.consume_mission_events():
            if mission_event.kind is MissionEventKind.CELL_FILLED:
                self.audio.play_success_chime()
                self.rocket_scene.show_cell_ready(mission_event.generator)
                self._play_cell_firework(mission_event.generator)
            elif mission_event.kind is MissionEventKind.LAUNCH_COMMITTED:
                self.rocket_scene.start_launch(mission_event.generators)
                self._sync_gameplay_input_gate()
                self._play_launch_fireworks(len(mission_event.generators))

        actions = self.rocket_scene.update(self.snapshot, dt, fps or 60.0)
        self._sync_gameplay_input_gate()
        self.audio.update_mission_audio(
            self.rocket_scene.phase.name,
            self.rocket_scene.crash_progress,
        )
        self.renderer.screen_shake = self.rocket_scene.screen_shake()
        if actions.launch_completed:
            self.game_state.mark_launch_complete()
            self.audio.play_end_chime()
            self.snapshot = self.game_state.snapshot()
            if (
                getattr(self.game_state, "rankings_enabled", False)
                and self.game_state.current_ranking_entry is not None
            ):
                self._begin_ranking_flow()
            if not (self.show_name_entry or self.show_leaderboard):
                self.rocket_scene.release_record_hold()
        if actions.reset_requested:
            self._reset_mission_input()
            self.rocket_scene.reset()
            self.gauge_manager.reset()
            self.snapshot = self.game_state.snapshot()
            self.prev_selected_generators = tuple(self.snapshot.selected_generators)
            self.prev_energy_levels = dict(self.snapshot.energy_levels)
            self._sync_gameplay_input_gate()

        self.lighting.update()
        self.script_manager.update()
        self.firework_manager.update()
        self.drone_manager.update(self.frame_count, 1.0)
        self.gauge_manager.update(self.snapshot, dt)

        for generator in GeneratorType:
            current = self.snapshot.energy_levels.get(generator, 0.0)
            previous = self.prev_energy_levels.get(generator, 0.0)
            if int(current) > int(previous):
                self.audio.play_fill_sound(current / 100.0)
        self.prev_energy_levels = dict(self.snapshot.energy_levels)

    def _play_selection_feedback(self, snapshot):
        """Turn accepted Hall selection changes into immediate audio feedback."""
        current = tuple(snapshot.selected_generators)
        previous = self.prev_selected_generators
        for generator in previous:
            if generator not in current:
                self.audio.play_hall_sensor(generator, selected=False)
        for generator in current:
            if generator not in previous:
                self.audio.play_hall_sensor(generator, selected=True)
        self.prev_selected_generators = current

    def _play_cell_firework(self, generator):
        script_names = {
            GeneratorType.WIND: "wind.json",
            GeneratorType.SOLAR: "solar.json",
            GeneratorType.HAND_CRANK: "hand_crank.json",
            GeneratorType.COIL: "coil.json",
        }
        script_name = script_names[generator]
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
        self.script_manager.play_sequence(script_path, variation=random.choice((0, 1)))

    def _play_launch_fireworks(self, cell_count):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(
            current_dir,
            "..",
            "..",
            "..",
            "..",
            "resource",
            "firework-scripts",
            "launch.json",
        )
        count_scale, intensity_scale, life_scale = LAUNCH_FIREWORK_SCALES.get(
            cell_count,
            (1.0, 1.0, 1.0),
        )
        self.script_manager.play_sequence(
            script_path,
            variation=random.choice((0, 1)),
            count_scale=count_scale,
            intensity_scale=intensity_scale,
            life_scale=life_scale,
        )

    @staticmethod
    def _ranking_generator_label(generator):
        return {
            GeneratorType.WIND: "WIND",
            GeneratorType.SOLAR: "SOLAR",
            GeneratorType.HAND_CRANK: "CRANK",
            GeneratorType.COIL: "COIL",
        }[generator]

    def _draw_centered_text(self, text, y, font, color, center_x=SCREEN_WIDTH / 2):
        width, _ = font.size(text)
        self.renderer.draw_text(int(center_x - width / 2), int(y), text, font, color)

    def _draw_rocket_ranking_overlay(self):
        entry = self.ranking_display_entry
        if entry is None:
            return
        loadout = self.game_state.canonical_loadout(entry.generators)
        entries = self.game_state.rankings.get(loadout, [])
        labels = [self._ranking_generator_label(generator) for generator in entry.generators]
        loadout_text = " + ".join(labels)
        accent = (0.98, 0.72, 0.20, 1.0)
        white = (0.90, 0.95, 1.0, 1.0)
        muted = (0.55, 0.66, 0.78, 1.0)

        # Four-cell split rows need substantially more horizontal room than
        # the old single-generator board. Keep a small 80 px safe margin.
        panel_w = min(int(1760 * SCALE_X), SCREEN_WIDTH - int(80 * SCALE_X))
        panel_h = int(780 * SCALE_Y)
        ox = (SCREEN_WIDTH - panel_w) // 2
        oy = (SCREEN_HEIGHT - panel_h) // 2
        self.renderer.set_blend_mode("alpha")
        self.renderer.draw_rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, (0.0, 0.01, 0.035, 0.68), fill=True)
        self.renderer.draw_rect(ox, oy, panel_w, panel_h, (0.01, 0.025, 0.06, 0.98), fill=True)
        self.renderer.draw_rect(ox, oy, panel_w, panel_h, (0.70, 0.85, 1.0, 0.95), fill=False)
        self.renderer.draw_rect(
            ox + int(8 * SCALE_X), oy + int(8 * SCALE_Y),
            panel_w - int(16 * SCALE_X), panel_h - int(16 * SCALE_Y),
            (0.15, 0.34, 0.56, 0.9), fill=False,
        )

        title = (
            f"{len(loadout)}-CELL ROCKET RECORD"
            if self.show_name_entry
            else f"{len(loadout)}-CELL ROCKET RANKINGS"
        )
        self._draw_centered_text(title, oy + 46 * SCALE_Y, self.fonts["bold_xlarge"], accent)
        self._draw_centered_text(loadout_text, oy + 120 * SCALE_Y, self.fonts["large"], white)
        self._draw_centered_text(
            f"TOTAL  {entry.time_taken:.2f}s",
            oy + 174 * SCALE_Y,
            self.fonts["bold_large"],
            accent,
        )

        cell_summary = "   ".join(
            f"{self._ranking_generator_label(generator)} {entry.cell_times.get(generator, 0.0):.2f}s"
            for generator in entry.generators
        )
        self._draw_centered_text(cell_summary, oy + 230 * SCALE_Y, self.fonts["medium"], white)

        if self.show_name_entry:
            comparison_name = self.name_suggestion or self.name_input
            previous_best = self.game_state.get_personal_best(
                comparison_name, loadout, exclude_current=True
            )
            if previous_best is not None:
                self._draw_centered_text(
                    f"{comparison_name}'S BEST FOR THIS BATTERY  {previous_best:.2f}s",
                    oy + 278 * SCALE_Y,
                    self.fonts["medium"], muted,
                )

            box_w = int(850 * SCALE_X)
            box_h = int(86 * SCALE_Y)
            bx = ox + (panel_w - box_w) // 2
            by = oy + int(350 * SCALE_Y)
            self.renderer.draw_rect(bx, by, box_w, box_h, (0.0, 0.01, 0.025, 1.0), fill=True)
            self.renderer.draw_rect(bx, by, box_w, box_h, accent, fill=False)
            display = self.name_input
            cursor = "_" if (self.frame_count // 30) % 2 == 0 else " "
            text_x = bx + int(28 * SCALE_X)
            text_y = by + int(16 * SCALE_Y)
            self.renderer.draw_text(text_x, text_y, display + cursor, self.fonts["xlarge"], white)
            if self.name_suggestion and len(self.name_suggestion) > len(self.name_input):
                typed_width, _ = self.fonts["xlarge"].size(display)
                suffix = self.name_suggestion[len(self.name_input):]
                self.renderer.draw_text(
                    text_x + typed_width, text_y, suffix, self.fonts["xlarge"], muted
                )
                self._draw_centered_text(
                    "TAB OR RIGHT: AUTO-FILL",
                    by + box_h + 20 * SCALE_Y,
                    self.fonts["small"], muted,
                )
            self._draw_centered_text(
                "ENTER: SAVE RECORD     ESC: SKIP",
                oy + panel_h - 82 * SCALE_Y,
                self.fonts["medium"], white,
            )
        else:
            result = self.game_state.last_ranking_result
            if result:
                if result.is_first_result:
                    result_text = "FIRST RECORD FOR THIS BATTERY"
                elif result.is_personal_best:
                    result_text = f"NEW PERSONAL BEST - {result.improvement:.2f}s FASTER"
                elif result.difference_from_best == 0.0:
                    result_text = "PERSONAL BEST MATCHED"
                else:
                    result_text = f"{result.difference_from_best:.2f}s FROM YOUR BEST"
                if result.final_rank is not None:
                    result_text += f"   RANK #{result.final_rank}"
                self._draw_centered_text(
                    result_text, oy + 278 * SCALE_Y, self.fonts["medium"], accent
                )

            query = self.leaderboard_search_input.casefold().strip()
            visible_entries = [
                (rank, ranked)
                for rank, ranked in enumerate(entries, start=1)
                if not query or query in ranked.player_name.casefold()
            ][:5]
            header_y = oy + int(332 * SCALE_Y)
            self.renderer.draw_text(ox + int(50 * SCALE_X), header_y, "PLAYER", self.fonts["small"], muted)
            self.renderer.draw_text(ox + int(570 * SCALE_X), header_y, "TOTAL", self.fonts["small"], muted)
            self.renderer.draw_text(ox + int(740 * SCALE_X), header_y, "CELL TIMES", self.fonts["small"], muted)
            for row, (rank, ranked) in enumerate(visible_entries, start=1):
                row_y = header_y + int((row * 58) * SCALE_Y)
                self.renderer.draw_text(
                    ox + int(50 * SCALE_X), row_y,
                    f"{rank}. {ranked.player_name}", self.fonts["medium"], white,
                )
                self.renderer.draw_text(
                    ox + int(570 * SCALE_X), row_y,
                    f"{ranked.time_taken:.2f}s", self.fonts["medium"], accent,
                )
                splits = " / ".join(
                    f"{self._ranking_generator_label(generator)} {ranked.cell_times.get(generator, 0.0):.2f}"
                    for generator in ranked.generators
                )
                self.renderer.draw_text(
                    ox + int(740 * SCALE_X), row_y, splits, self.fonts["small"], white,
                )
            search_text = f"SEARCH: {self.leaderboard_search_input}"
            self.renderer.draw_text(
                ox + int(50 * SCALE_X), oy + panel_h - int(96 * SCALE_Y),
                search_text, self.fonts["medium"], muted,
            )
            self.renderer.draw_text(
                ox + panel_w - int(490 * SCALE_X), oy + panel_h - int(96 * SCALE_Y),
                "ENTER OR ESC: NEXT MISSION", self.fonts["medium"], white,
            )
        self.renderer.set_blend_mode("additive")

    def _draw_rocket_mission(self):
        self.renderer.start_frame()
        self.lighting.draw_background(self.renderer)
        self.rocket_scene.draw_stars(self.renderer, self.frame_count)
        self.rocket_scene.draw_intro(self.renderer, self.pixel_font)
        firework_offset = self.rocket_scene.firework_y_offset
        firework_lights, launch_lights = self.firework_manager.gather_light_sources(
            firework_offset_y=firework_offset
        )
        self.rocket_scene.draw_far_city(self.renderer, firework_lights)
        self.firework_manager.draw(
            self.renderer,
            self.frame_count,
            scene_effect=False,
            world_offset_y=firework_offset,
        )
        self.rocket_scene.draw_world(
            self.renderer,
            self.frame_count,
            firework_lights=firework_lights,
            launch_lights=launch_lights,
        )
        self.firework_manager.draw(
            self.renderer,
            self.frame_count,
            scene_effect=True,
        )
        self.rocket_scene.draw_rocket_foreground(
            self.renderer,
            self.frame_count,
            firework_lights=firework_lights,
            launch_lights=launch_lights,
        )

        show_debug = self.mock_ble or self.mock_hall
        self.drone_manager.draw(
            self.renderer,
            self.fonts["small"],
            self.frame_count,
            show_debug_text=False,
            y_offset=self.rocket_scene.drone_y_offset,
        )

        if self.snapshot is not None:
            self.gauge_manager.draw(
                self.renderer,
                self.pixel_font,
                self.frame_count,
                scene_alpha=self.rocket_scene.scene_alpha,
            )
            self.rocket_scene.draw_message(
                self.renderer, self.pixel_font, self.snapshot
            )

        if self.is_mock and self.gui.visible:
            self.gui.draw(self.renderer, self.fonts)
            self.draw_cursor()

        if show_debug and self.rocket_scene.phase not in (
            MissionPhase.ATTRACT,
            MissionPhase.CRASH,
        ):
            modes = []
            if self.mock_hall:
                modes.append("HALL")
            if self.mock_ble:
                modes.append("BLE")
            label = "DEBUG " + "+".join(modes) + "  1-4 MOVE SOT-KUN  Q-W-E-R CHARGE  0 LIFT"
            self.renderer.draw_pixel_text(
                24 * SCALE_X,
                SCREEN_HEIGHT - 32 * SCALE_Y,
                label,
                self.pixel_font,
                3,
                (0.72, 0.82, 0.95, 0.9),
            )

        if self.show_metrics:
            metrics = (
                f"FPS {self.fps_tracker.fps:.1f}  CPU {self.cpu_tracker.cpu_usage:.0f}%  "
                f"RAM {self.get_memory_usage():.0f}MB  PARTICLES {len(self.firework_manager.particles)}  "
                f"DENSITY {int(self.rocket_scene.emission_scale * 100)}%"
            )
            self.renderer.draw_pixel_text(
                24 * SCALE_X,
                24 * SCALE_Y,
                metrics,
                self.pixel_font,
                3,
                (0.86, 0.92, 1.0, 0.95),
            )

        if self.show_name_entry or self.show_leaderboard:
            self._draw_rocket_ranking_overlay()

        self.rocket_scene.draw_transition_fade(self.renderer)

        try:
            screen_w, screen_h = pygame.display.get_window_size()
        except AttributeError:
            screen_w, screen_h = self.screen.get_size()
        self.renderer.end_frame(screen_w, screen_h)

    def draw(self):
        self._draw_rocket_mission()
        return
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
        if (
            self.is_mock
            and not self.in_attract_mode
        ):
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
            # Draw overlay and name entry (2x larger: 1200x600)
            overlay_w = int(1200 * SCALE_X)
            overlay_h = int(600 * SCALE_Y)
            ox = (SCREEN_WIDTH - overlay_w) // 2
            oy = (SCREEN_HEIGHT - overlay_h) // 2

            # Emphasis color index based on completed generator
            gen = self.completed_gen or GeneratorType.WIND
            gen_colors = {
                GeneratorType.WIND: 61,    # Cyan
                GeneratorType.SOLAR: 31,   # Yellow
                GeneratorType.HAND_CRANK: 11,   # Orange
                GeneratorType.COIL: 41     # Lime
            }
            emp_col_idx = gen_colors.get(gen, 51)

            self.renderer.set_blend_mode("alpha")
            self.renderer.draw_rect(
                ox, oy, overlay_w, overlay_h, (0.0, 0.0, 0.0, 0.95), fill=True
            )
            self.renderer.draw_rect(
                ox, oy, overlay_w, overlay_h, palette.get_color(122), fill=False
            )

            # Title
            title_text = "=== ENTER YOUR NAME ==="
            font_xl = self.fonts["xlarge"]
            tw, _ = font_xl.size(title_text)
            tx = ox + (overlay_w - tw) // 2
            self.renderer.draw_text(
                tx,
                oy + int(80 * SCALE_Y),
                title_text,
                font_xl,
                palette.get_color(emp_col_idx),
            )

            # Subtitle
            sub_text = "Type name for the Leaderboard"
            font_med = self.fonts["medium"]
            sw, _ = font_med.size(sub_text)
            sx = ox + (overlay_w - sw) // 2
            self.renderer.draw_text(
                sx,
                oy + int(150 * SCALE_Y),
                sub_text,
                font_med,
                palette.get_color(121),
            )

            # Times: current run time & suggested/input player's best time
            current_time_taken = 0.0
            if self.game_state and self.game_state.current_ranking_entry:
                current_time_taken = self.game_state.current_ranking_entry.time_taken
            elif self.game_state and self.game_state.last_ranking_result:
                current_time_taken = self.game_state.last_ranking_result.run_time
            elif self.game_state:
                current_time_taken = self.game_state.get_elapsed_time()

            current_time_str = f"Current Time: {current_time_taken:.2f}s"
            recommended_name = self.name_suggestion or self.name_input
            best_time = None
            if recommended_name and self.game_state and self.completed_gen:
                best_time = self.game_state.get_personal_best(
                    recommended_name,
                    self.completed_gen,
                    exclude_current=True,
                )

            best_time_str = ""
            if best_time is not None:
                best_time_str = f"  |  {recommended_name}'s Best Time: {best_time:.2f}s"

            total_str = current_time_str + best_time_str
            font_med = self.fonts["medium"]
            ti_w, _ = font_med.size(total_str)
            ti_x = ox + (overlay_w - ti_w) // 2

            # Color coding Current Time based on comparison to personal best
            if best_time is None:
                cur_time_color = palette.get_color(emp_col_idx)  # Default emphasis
            elif current_time_taken < best_time:
                cur_time_color = palette.get_color(51)           # Green for lower (better)
            elif current_time_taken > best_time:
                cur_time_color = palette.get_color(1)            # Red for higher (worse)
            else:
                cur_time_color = palette.get_color(31)           # Yellow/Gold for equal

            # Draw Current Time
            self.renderer.draw_text(
                ti_x,
                oy + int(210 * SCALE_Y),
                current_time_str,
                font_med,
                cur_time_color,
            )

            # Draw Best Time suffix if present
            if best_time_str:
                cur_w, _ = font_med.size(current_time_str)
                self.renderer.draw_text(
                    ti_x + cur_w,
                    oy + int(210 * SCALE_Y),
                    best_time_str,
                    font_med,
                    palette.get_color(121),  # White
                )

            # Input box
            box_w = int(800 * SCALE_X)
            box_h = int(80 * SCALE_Y)
            bx = ox + (overlay_w - box_w) // 2
            by = oy + int(280 * SCALE_Y)

            self.renderer.draw_rect(
                bx, by, box_w, box_h, (0.1, 0.1, 0.1, 0.8), fill=True
            )
            self.renderer.draw_rect(
                bx, by, box_w, box_h, palette.get_color(emp_col_idx), fill=False
            )

            # Cursor blinking
            cursor_char = "_" if (self.frame_count // 30) % 2 == 0 else " "

            # Input text
            input_display_text = self.name_input
            font_input = self.fonts["xlarge"]
            text_x = bx + int(30 * SCALE_X)
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
                font_small = self.fonts["small"]
                hw, _ = font_small.size(hint_text)
                hx = ox + (overlay_w - hw) // 2
                self.renderer.draw_text(
                    hx,
                    by + box_h + int(15 * SCALE_Y),
                    hint_text,
                    font_small,
                    (0.5, 0.5, 0.5, 1.0),
                )

            # Bottom instructions
            bottom_text = "[ PRESS ENTER TO SUBMIT | ESC TO SKIP ]"
            font_small = self.fonts["small"]
            bw, _ = font_small.size(bottom_text)
            bx_bottom = ox + (overlay_w - bw) // 2
            self.renderer.draw_text(
                bx_bottom,
                oy + overlay_h - int(80 * SCALE_Y),
                bottom_text,
                font_small,
                palette.get_color(121),
            )
            self.renderer.set_blend_mode("additive")

        if self.show_leaderboard:
            # Draw overlay and leaderboard (2x larger: 1200x800)
            overlay_w = int(1200 * SCALE_X)
            overlay_h = int(800 * SCALE_Y)
            ox = (SCREEN_WIDTH - overlay_w) // 2
            oy = (SCREEN_HEIGHT - overlay_h) // 2

            # Emphasis color index based on completed generator
            gen = self.completed_gen or GeneratorType.WIND
            gen_colors = {
                GeneratorType.WIND: 61,    # Cyan
                GeneratorType.SOLAR: 31,   # Yellow
                GeneratorType.HAND_CRANK: 11,   # Orange
                GeneratorType.COIL: 41     # Lime
            }
            emp_col_idx = gen_colors.get(gen, 51)

            self.renderer.set_blend_mode("alpha")
            self.renderer.draw_rect(
                ox, oy, overlay_w, overlay_h, (0.0, 0.0, 0.0, 0.95), fill=True
            )
            self.renderer.draw_rect(
                ox, oy, overlay_w, overlay_h, palette.get_color(122), fill=False
            )

            # Header
            title_text = f"=== {gen.value.upper()} CHARGED ==="
            font_xl = self.fonts["xlarge"]
            tw, _ = font_xl.size(title_text)
            tx = ox + (overlay_w - tw) // 2
            self.renderer.draw_text(
                tx,
                oy + int(45 * SCALE_Y),
                title_text,
                font_xl,
                palette.get_color(emp_col_idx),
            )

            # Display the current time in the final ranking board
            current_time_taken = 0.0
            if self.game_state and self.game_state.current_ranking_entry:
                current_time_taken = self.game_state.current_ranking_entry.time_taken
            elif self.game_state and self.game_state.last_ranking_result:
                current_time_taken = self.game_state.last_ranking_result.run_time
            elif self.game_state:
                current_time_taken = self.game_state.get_elapsed_time()

            cur_time_text = f"Your Time: {current_time_taken:.2f}s"
            font_med = self.fonts["medium"]
            ct_w, _ = font_med.size(cur_time_text)
            ct_x = ox + (overlay_w - ct_w) // 2
            self.renderer.draw_text(
                ct_x,
                oy + int(120 * SCALE_Y),
                cur_time_text,
                font_med,
                palette.get_color(emp_col_idx),
            )

            ranking_result = (
                self.game_state.last_ranking_result if self.game_state else None
            )
            if ranking_result:
                if ranking_result.is_first_result:
                    result_text = "FIRST PERSONAL RESULT SAVED"
                    result_color = palette.get_color(31)
                elif ranking_result.is_personal_best:
                    result_text = (
                        f"NEW PERSONAL BEST - {ranking_result.improvement:.2f}s FASTER"
                    )
                    result_color = palette.get_color(51)
                elif ranking_result.difference_from_best == 0.0:
                    result_text = "MATCHED YOUR PERSONAL BEST"
                    result_color = palette.get_color(31)
                else:
                    result_text = (
                        f"{ranking_result.difference_from_best:.2f}s FROM YOUR BEST"
                    )
                    result_color = palette.get_color(121)
                if ranking_result.final_rank is not None:
                    result_text += f"  |  RANK #{ranking_result.final_rank}"
                result_w, _ = font_med.size(result_text)
                self.renderer.draw_text(
                    ox + (overlay_w - result_w) // 2,
                    oy + int(170 * SCALE_Y),
                    result_text,
                    font_med,
                    result_color,
                )

            # Left column: Top 5 Fastest Players
            sub_text = "--- TOP 5 FASTEST PLAYERS ---"
            font_large = self.fonts["large"]
            font_small = self.fonts["small"]
            
            sw, _ = font_med.size(sub_text)
            sx = ox + int(300 * SCALE_X) - (sw // 2)
            self.renderer.draw_text(
                sx,
                oy + int(235 * SCALE_Y),
                sub_text,
                font_med,
                palette.get_color(121),
            )

            col1_x = ox + int(80 * SCALE_X)
            col2_x = ox + int(460 * SCALE_X)
            ranking_row_spacing = int(82 * SCALE_Y)

            rankings_list = []
            if isinstance(self.game_state.rankings, dict):
                rankings_list = self.game_state.rankings.get(gen, [])
            else:
                rankings_list = self.game_state.rankings

            for i, rank in enumerate(rankings_list[:5]):
                y_pos = oy + int(340 * SCALE_Y) + i * ranking_row_spacing
                self.renderer.draw_text(
                    col1_x,
                    y_pos,
                    f"{i + 1}. {rank.player_name}",
                    font_med,
                    palette.get_color(122),
                )
                self.renderer.draw_text(
                    col2_x,
                    y_pos,
                    f"{rank.time_taken:.2f}s",
                    font_med,
                    palette.get_color(emp_col_idx),
                )

            # Right column: Personal Bests
            pb_text = "--- PERSONAL BESTS ---"
            pbw, _ = font_med.size(pb_text)
            pbx = ox + int(900 * SCALE_X) - (pbw // 2)
            self.renderer.draw_text(
                pbx,
                oy + int(235 * SCALE_Y),
                pb_text,
                font_med,
                palette.get_color(121),
            )

            # Group by unique player to find best times & most recent timestamps across the entire player base
            player_bests = {}
            
            # Compile all unique player names from the player base and all rankings
            all_players = set(self.player_base)
            if self.game_state:
                for other_ranks in self.game_state.rankings.values():
                    for r in other_ranks:
                        all_players.add(r.player_name)
            
            for p_name in all_players:
                key = p_name.lower().strip()
                if not key:
                    continue
                
                # Find best time and most recent timestamp for this generator
                best_time = None
                most_recent_timestamp = 0.0
                
                if self.game_state:
                    gen_ranks = self.game_state.rankings.get(gen, [])
                    p_gen_ranks = [r for r in gen_ranks if r.player_name.lower().strip() == key]
                    if p_gen_ranks:
                        best_time = min(r.time_taken for r in p_gen_ranks)
                        most_recent_timestamp = max(getattr(r, "timestamp", 0.0) for r in p_gen_ranks)
                    
                    # If they haven't played this generator, find their most recent activity timestamp across all generators
                    if most_recent_timestamp == 0.0:
                        for other_ranks in self.game_state.rankings.values():
                            p_other = [r for r in other_ranks if r.player_name.lower().strip() == key]
                            if p_other:
                                most_recent_timestamp = max(most_recent_timestamp, max(getattr(r, "timestamp", 0.0) for r in p_other))
                
                player_bests[key] = {
                    "player_name": p_name,
                    "best_time": best_time,
                    "most_recent_timestamp": most_recent_timestamp
                }

            # Convert to list and sort by most recent timestamp descending
            unique_players = list(player_bests.values())
            unique_players.sort(key=lambda x: x["most_recent_timestamp"], reverse=True)

            # Filter unique players based on search query
            if self.leaderboard_search_input:
                q = self.leaderboard_search_input.lower().strip()
                unique_players = [p for p in unique_players if q in p["player_name"].lower()]

            # Draw search box for Personal Bests
            sb_x = ox + int(680 * SCALE_X)
            sb_y = oy + int(275 * SCALE_Y)
            sb_w = int(440 * SCALE_X)
            sb_h = int(45 * SCALE_Y)

            self.renderer.draw_rect(sb_x, sb_y, sb_w, sb_h, (0.1, 0.1, 0.1, 0.8), fill=True)
            self.renderer.draw_rect(sb_x, sb_y, sb_w, sb_h, palette.get_color(emp_col_idx), fill=False)

            search_prefix = "Search: "
            pref_w, _ = font_med.size(search_prefix)
            self.renderer.draw_text(
                sb_x + int(10 * SCALE_X),
                sb_y + (sb_h - font_med.size("A")[1]) // 2,
                search_prefix,
                font_med,
                palette.get_color(121),
            )

            query_display = self.leaderboard_search_input
            if not query_display:
                if (self.frame_count // 30) % 2 == 0:
                    self.renderer.draw_text(
                        sb_x + int(10 * SCALE_X) + pref_w,
                        sb_y + (sb_h - font_med.size("A")[1]) // 2,
                        "[Type name...]",
                        font_med,
                        (0.4, 0.4, 0.4, 0.8),
                    )
            else:
                self.renderer.draw_text(
                    sb_x + int(10 * SCALE_X) + pref_w,
                    sb_y + (sb_h - font_med.size("A")[1]) // 2,
                    query_display,
                    font_med,
                    palette.get_color(122),
                )
                cursor_char = "_" if (self.frame_count // 30) % 2 == 0 else " "
                query_w, _ = font_med.size(query_display)
                self.renderer.draw_text(
                    sb_x + int(10 * SCALE_X) + pref_w + query_w,
                    sb_y + (sb_h - font_med.size("A")[1]) // 2,
                    cursor_char,
                    font_med,
                    palette.get_color(122),
                )

            # Draw Personal Bests entries
            col3_x = ox + int(680 * SCALE_X)
            col4_x = ox + int(1060 * SCALE_X)

            for i, p in enumerate(unique_players[:5]):
                y_pos = oy + int(340 * SCALE_Y) + i * ranking_row_spacing
                self.renderer.draw_text(
                    col3_x,
                    y_pos,
                    p['player_name'],
                    font_med,
                    palette.get_color(122),
                )
                time_str = f"{p['best_time']:.2f}s" if p['best_time'] is not None else "--"
                self.renderer.draw_text(
                    col4_x,
                    y_pos,
                    time_str,
                    font_med,
                    palette.get_color(emp_col_idx),
                )

            # Restart/Close Instruction
            if self.mock_ble or self.mock_hall:
                restart_text = "[ PRESS ESCAPE OR ENTER TO RESTART CHALLENGE ]"
                rw, _ = font_med.size(restart_text)
                rx = ox + (overlay_w - rw) // 2
                self.renderer.draw_text(
                    rx,
                    oy + overlay_h - int(70 * SCALE_Y),
                    restart_text,
                    font_med,
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
