import os
import pygame
import random
from .config import SCALE_X


class AudioSystem:
    def __init__(self):
        self.enabled = False
        self.sounds = {}

        try:
            pygame.init()
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

            if pygame.mixer.get_init() is None:
                print(
                    "WARNING: Pygame mixer failed to open the audio device. Running silent."
                )
                return

            pygame.mixer.set_num_channels(32)
            self.enabled = True
        except Exception as e:
            print(
                f"WARNING: Could not initialize Pygame Audio. Running in silent mode. Error: {e}"
            )
            return

        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
        self.audio_dir = os.path.join(root_dir, "resource", "audio")

        self._load_sound("launch", "Firework_launch.ogg")
        self._load_sound("blast_near", "Firework_blast.ogg")
        self._load_sound("blast_far", "Firework_blast_far.ogg")
        self._load_sound("large_blast_near", "Firework_large_blast.ogg")
        self._load_sound("large_blast_far", "Firework_large_blast_far.ogg")
        self._load_sound("twinkle_near", "Firework_twinkle.ogg")
        self._load_sound("twinkle_far", "Firework_twinkle_far.ogg")

    def _load_sound(self, key, filename):
        if not self.enabled:
            return

        path = os.path.join(self.audio_dir, filename)
        if os.path.exists(path):
            try:
                self.sounds[key] = pygame.mixer.Sound(path)
            except Exception as e:
                print(f"Failed to load {filename}: {e}")
                self.enabled = False
        else:
            print(f"Audio file missing: {path}")

    # --- NEW: Background Music Controls ---
    def play_music(self, filename):
        if not self.enabled:
            return
        path = os.path.join(self.audio_dir, filename)
        if os.path.exists(path):
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.play(-1)  # -1 loops the track indefinitely
            except Exception as e:
                print(f"Failed to play music {filename}: {e}")
        else:
            print(f"Music file missing: {path}")

    def stop_music(self):
        if not self.enabled:
            return
        pygame.mixer.music.fadeout(2000)  # Smooth 2-second fade out

    def _get_stereo_pan(self, x_position):
        max_x = 600.0 * SCALE_X
        pan = (x_position + max_x) / (max_x * 2.0)
        return max(0.1, min(0.9, pan))

    def play_launch(self, x_position):
        if not self.enabled or "launch" not in self.sounds:
            return
        base_vol = random.uniform(0.5, 0.9)
        pan = self._get_stereo_pan(x_position)
        channel = pygame.mixer.find_channel()
        if channel:
            channel.set_volume((1.0 - pan) * base_vol, pan * base_vol)
            channel.play(self.sounds["launch"])

    def play_explosion(self, spec, x_position, y_position):
        if not self.enabled:
            return

        is_far = y_position < -150
        is_large = spec.particle_count >= 150 or spec.radius >= 2.0
        
        from .behaviors import CrackleBehavior, FlickerBehavior, TrailBehavior
        is_twinkle = False
        for b in spec.draw_behaviors:
            if isinstance(b, (CrackleBehavior, FlickerBehavior)):
                is_twinkle = True
                break
            if isinstance(b, TrailBehavior) and b.glitter:
                is_twinkle = True
                break

        if is_twinkle:
            key = "twinkle_far" if is_far else "twinkle_near"
        elif is_large:
            key = "large_blast_far" if is_far else "large_blast_near"
        else:
            key = "blast_far" if is_far else "blast_near"

        if key in self.sounds:
            base_vol = (
                random.uniform(0.6, 1.0) if not is_far else random.uniform(0.4, 0.7)
            )
            pan = self._get_stereo_pan(x_position)
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume((1.0 - pan) * base_vol, pan * base_vol)
                channel.play(self.sounds[key])
