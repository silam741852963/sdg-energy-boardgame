import os
import pygame
import random
from .config import SCALE_X


class AudioSystem:
    def __init__(self):
        self.enabled = False
        self.sounds = {}
        self.music_muted = True

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

        self._load_sound("launch", "Firework_launch.wav")
        self._load_sound("blast_near", "Firework_blast.wav")
        self._load_sound("blast_far", "Firework_blast_far.wav")
        self._load_sound("large_blast_near", "Firework_large_blast.wav")
        self._load_sound("large_blast_far", "Firework_large_blast_far.wav")
        self._load_sound("twinkle_near", "Firework_twinkle.wav")
        self._load_sound("twinkle_far", "Firework_twinkle_far.wav")

        if self.enabled:
            try:
                import numpy as np
                self.sounds["success_chime"] = pygame.mixer.Sound(array=self._generate_success_chime_samples())
                self.sounds["switch_blip"] = pygame.mixer.Sound(array=self._generate_switch_blip_samples())
                self.sounds["tick"] = pygame.mixer.Sound(array=self._generate_tick_samples())
                self.sounds["restart_chime"] = pygame.mixer.Sound(array=self._generate_restart_chime_samples())
                self.sounds["end_chime"] = pygame.mixer.Sound(array=self._generate_end_chime_samples())

                # Pre-generate Simon Says notes & interactive combo sounds
                self.sounds["simon_note_wind"] = pygame.mixer.Sound(array=self._generate_note_samples(523.25))
                self.sounds["simon_note_solar"] = pygame.mixer.Sound(array=self._generate_note_samples(659.25))
                self.sounds["simon_note_piezo"] = pygame.mixer.Sound(array=self._generate_note_samples(783.99))
                self.sounds["simon_note_coil"] = pygame.mixer.Sound(array=self._generate_note_samples(1046.50))
                self.sounds["overdrive_unlock"] = pygame.mixer.Sound(array=self._generate_overdrive_unlock_samples())
                self.sounds["combo_unlock"] = pygame.mixer.Sound(array=self._generate_combo_unlock_samples())
                self.sounds["electric_spark"] = pygame.mixer.Sound(array=self._generate_electric_spark_samples())

                # Pre-generate 101 fill tick sounds at different pitch levels
                self.fill_sounds = []
                for i in range(101):
                    # Frequencies from 400 Hz to 1200 Hz
                    freq = 400.0 + i * 8.0
                    samples = self._generate_fill_tick_samples(freq)
                    self.fill_sounds.append(pygame.mixer.Sound(array=samples))
            except Exception as e:
                print(f"Failed to synthesize UI sounds: {e}")

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
        if not self.enabled or self.music_muted:
            return
        path = os.path.join(self.audio_dir, filename)
        if os.path.exists(path):
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(0.4) # Tune background music volume (0.0 to 1.0)
                pygame.mixer.music.play(-1)  # -1 loops the track indefinitely
            except Exception as e:
                print(f"Failed to play music {filename}: {e}")
        else:
            print(f"Music file missing: {path}")

    def stop_music(self):
        if not self.enabled:
            return
        pygame.mixer.music.fadeout(2000)  # Smooth 2-second fade out

    def toggle_music(self):
        if not self.enabled:
            return
        self.music_muted = not self.music_muted
        if self.music_muted:
            pygame.mixer.music.stop()
        else:
            self.play_music("ablic-theme.wav")

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

    def _generate_success_chime_samples(self):
        import numpy as np
        sample_rate = 44100
        # Notes: C5 (523.25), E5 (659.25), G5 (783.99), C6 (1046.50)
        freqs = [523.25, 659.25, 783.99, 1046.50]
        durations = [0.12, 0.12, 0.12, 0.44] # total 0.8s
        volume = 0.4 * 32767 # signed 16-bit max is 32767

        buffer = []
        for freq, dur in zip(freqs, durations):
            num_samples = int(sample_rate * dur)
            t = np.linspace(0, dur, num_samples, endpoint=False)
            # Sine wave
            wave = np.sin(2 * np.pi * freq * t)
            # Decay envelope
            envelope = np.exp(-4.0 * t)
            note_samples = (wave * envelope * volume).astype(np.int16)
            buffer.append(note_samples)

        mono_samples = np.concatenate(buffer)
        return np.column_stack((mono_samples, mono_samples))

    def _generate_switch_blip_samples(self):
        import numpy as np
        sample_rate = 44100
        dur = 0.08
        f_start = 600.0
        f_end = 900.0
        num_samples = int(sample_rate * dur)
        t = np.linspace(0, dur, num_samples, endpoint=False)
        phi = 2 * np.pi * (f_start * t + (f_end - f_start) / (2 * dur) * (t ** 2))
        wave = np.sin(phi)
        envelope = 1.0 - (t / dur)
        volume = 0.3 * 32767
        mono = (wave * envelope * volume).astype(np.int16)
        return np.column_stack((mono, mono))

    def _generate_tick_samples(self):
        import numpy as np
        sample_rate = 44100
        dur = 0.03
        freq = 1200.0
        num_samples = int(sample_rate * dur)
        t = np.linspace(0, dur, num_samples, endpoint=False)
        wave = np.sin(2 * np.pi * freq * t)
        envelope = np.exp(-30.0 * t)
        volume = 0.15 * 32767
        mono = (wave * envelope * volume).astype(np.int16)
        return np.column_stack((mono, mono))

    def _generate_restart_chime_samples(self):
        import numpy as np
        sample_rate = 44100
        # Notes: G5 (783.99), C5 (523.25)
        freqs = [783.99, 523.25]
        durations = [0.15, 0.25]
        volume = 0.4 * 32767

        buffer = []
        for freq, dur in zip(freqs, durations):
            num_samples = int(sample_rate * dur)
            t = np.linspace(0, dur, num_samples, endpoint=False)
            wave = np.sin(2 * np.pi * freq * t)
            envelope = np.exp(-6.0 * t)
            note_samples = (wave * envelope * volume).astype(np.int16)
            buffer.append(note_samples)

        mono = np.concatenate(buffer)
        return np.column_stack((mono, mono))

    def play_success_chime(self):
        if not self.enabled:
            return
        
        # Play the synthesized retro synth chime (not a firework sound)
        if "success_chime" in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(0.8)
                channel.play(self.sounds["success_chime"])

    def play_switch_sound(self):
        if not self.enabled:
            return
        
        # Play a quick synthesized chirp blip
        if "switch_blip" in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(0.6)
                channel.play(self.sounds["switch_blip"])

    def play_tick_sound(self):
        if not self.enabled:
            return
        
        # Play a satisfying short tick click
        if "tick" in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(0.5)
                channel.play(self.sounds["tick"])

    def play_restart_sound(self):
        if not self.enabled:
            return
        
        # Play a descending restart resolution chime
        if "restart_chime" in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(0.7)
                channel.play(self.sounds["restart_chime"])

    def _generate_fill_tick_samples(self, freq):
        import numpy as np
        sample_rate = 44100
        dur = 0.05
        num_samples = int(sample_rate * dur)
        t = np.linspace(0, dur, num_samples, endpoint=False)
        wave = np.sin(2 * np.pi * freq * t)
        envelope = np.sin(np.pi * (t / dur)) * np.exp(-12.0 * t)
        volume = 0.3 * 32767
        mono = (wave * envelope * volume).astype(np.int16)
        return np.column_stack((mono, mono))

    def play_fill_sound(self, fill_pct):
        if not self.enabled or not hasattr(self, 'fill_sounds') or not self.fill_sounds:
            return
        
        # Map fill_pct (0.0 to 1.0) to index 0..100
        idx = int(min(1.0, max(0.0, fill_pct)) * 100)
        channel = pygame.mixer.find_channel()
        if channel:
            channel.set_volume(0.6)
            channel.play(self.fill_sounds[idx])

    def _generate_end_chime_samples(self):
        import numpy as np
        sample_rate = 44100
        # Progression of quick bright arpeggios: E5, G5, C6, E6
        freqs = [659.25, 783.99, 1046.50, 1318.51]
        durations = [0.08, 0.08, 0.08, 0.36]
        volume = 0.45 * 32767

        buffer = []
        for freq, dur in zip(freqs, durations):
            num_samples = int(sample_rate * dur)
            t = np.linspace(0, dur, num_samples, endpoint=False)
            wave = np.sin(2 * np.pi * freq * t)
            # Add second harmonic for a retro glockenspiel timbre
            wave += 0.25 * np.sin(2 * np.pi * (freq * 2.0) * t)
            envelope = np.exp(-5.0 * t)
            note_samples = (wave * envelope * volume).astype(np.int16)
            buffer.append(note_samples)

        mono_samples = np.concatenate(buffer)
        return np.column_stack((mono_samples, mono_samples))

    def play_end_chime(self):
        if not self.enabled:
            return
        if "end_chime" in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(0.8)
                channel.play(self.sounds["end_chime"])

    def play_simon_note(self, gen_type_name):
        if not self.enabled:
            return
        # gen_type_name should match WIND, SOLAR, PIEZO, COIL
        key = f"simon_note_{gen_type_name.lower()}"
        if key in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(0.6)
                channel.play(self.sounds[key])

    def play_overdrive_unlock(self):
        if not self.enabled:
            return
        if "overdrive_unlock" in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(0.7)
                channel.play(self.sounds["overdrive_unlock"])

    def play_combo_unlock(self):
        if not self.enabled:
            return
        if "combo_unlock" in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(0.7)
                channel.play(self.sounds["combo_unlock"])

    def play_electric_spark(self):
        if not self.enabled:
            return
        if "electric_spark" in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(0.3)
                channel.play(self.sounds["electric_spark"])

    def _generate_note_samples(self, freq):
        import numpy as np
        sample_rate = 44100
        dur = 0.3
        volume = 0.4 * 32767
        num_samples = int(sample_rate * dur)
        t = np.linspace(0, dur, num_samples, endpoint=False)
        wave = np.sin(2 * np.pi * freq * t)
        # Add fundamental retro Glockenspiel-like overtone
        wave += 0.2 * np.sin(2 * np.pi * (freq * 2.0) * t)
        envelope = np.exp(-5.0 * t)
        mono = (wave * envelope * volume).astype(np.int16)
        return np.column_stack((mono, mono))

    def _generate_overdrive_unlock_samples(self):
        import numpy as np
        sample_rate = 44100
        freqs = [440.0, 554.37, 659.25, 880.0]
        durations = [0.08, 0.08, 0.08, 0.3]
        volume = 0.4 * 32767
        buffer = []
        for freq, dur in zip(freqs, durations):
            num_samples = int(sample_rate * dur)
            t = np.linspace(0, dur, num_samples, endpoint=False)
            wave = np.sin(2 * np.pi * freq * t)
            wave += 0.15 * np.sin(2 * np.pi * (freq * 2.0) * t)
            envelope = np.exp(-4.0 * t)
            note_samples = (wave * envelope * volume).astype(np.int16)
            buffer.append(note_samples)
        mono = np.concatenate(buffer)
        return np.column_stack((mono, mono))

    def _generate_combo_unlock_samples(self):
        import numpy as np
        sample_rate = 44100
        freqs = [523.25, 783.99, 1046.50, 1318.51, 1567.98, 2093.00]
        durations = [0.06, 0.06, 0.06, 0.06, 0.06, 0.4]
        volume = 0.35 * 32767
        buffer = []
        for freq, dur in zip(freqs, durations):
            num_samples = int(sample_rate * dur)
            t = np.linspace(0, dur, num_samples, endpoint=False)
            wave = np.sin(2 * np.pi * freq * t)
            wave += 0.2 * np.sin(2 * np.pi * (freq * 2.0) * t)
            envelope = np.exp(-4.0 * t)
            note_samples = (wave * envelope * volume).astype(np.int16)
            buffer.append(note_samples)
        mono = np.concatenate(buffer)
        return np.column_stack((mono, mono))

    def _generate_electric_spark_samples(self):
        import numpy as np
        sample_rate = 44100
        dur = 0.12
        num_samples = int(sample_rate * dur)
        t = np.linspace(0, dur, num_samples, endpoint=False)
        noise = np.random.uniform(-1.0, 1.0, num_samples)
        modulator = np.sin(2 * np.pi * 3000.0 * t)
        wave = noise * modulator
        envelope = np.exp(-22.0 * t)
        volume = 0.25 * 32767
        mono = (wave * envelope * volume).astype(np.int16)
        return np.column_stack((mono, mono))
