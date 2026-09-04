import os
import pygame
import random
from .config import LAUNCH_TIER_TIMINGS, SCALE_X
from ...config import GeneratorType


class AudioSystem:
    def __init__(self):
        self.enabled = False
        self.sounds = {}
        self.rocket_channel = None
        self.ambient_channel = None
        self.cockpit_channel = None
        self._mission_audio_phase = None
        self._last_crash_progress = 0.0

        try:
            pygame.init()
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

            if pygame.mixer.get_init() is None:
                print(
                    "WARNING: Pygame mixer failed to open the audio device. Running silent."
                )
                return

            pygame.mixer.set_num_channels(32)
            pygame.mixer.set_reserved(2)
            self.ambient_channel = pygame.mixer.Channel(0)
            self.cockpit_channel = pygame.mixer.Channel(1)
            self.enabled = True
        except Exception as e:
            print(
                f"WARNING: Could not initialize Pygame Audio. Running in silent mode. Error: {e}"
            )
            return

        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
        self.audio_dir = os.path.join(root_dir, "resource", "audio")

        ambient_path = os.path.join(self.audio_dir, "Space_ambient_airy.ogg")
        try:
            self.sounds["space_ambient"] = pygame.mixer.Sound(ambient_path)
        except Exception as e:
            print(f"Failed to load {ambient_path}: {e}")

        self._load_sound_variants("blast_near", "Firework_blast")
        self._load_sound_variants("blast_far", "Firework_blast_far")
        self._load_sound_variants("large_blast_near", "Firework_large_blast")
        self._load_sound_variants("large_blast_far", "Firework_large_blast_far")
        self._load_sound_variants("twinkle_near", "Firework_twinkle")
        self._load_sound_variants("twinkle_far", "Firework_twinkle_far")

        if self.enabled:
            try:
                import numpy as np
                self.sounds["success_chime"] = pygame.mixer.Sound(array=self._generate_success_chime_samples())
                self.sounds["switch_blip"] = pygame.mixer.Sound(array=self._generate_switch_blip_samples())
                self.sounds["tick"] = pygame.mixer.Sound(array=self._generate_tick_samples())
                self.sounds["restart_chime"] = pygame.mixer.Sound(array=self._generate_restart_chime_samples())
                self.sounds["end_chime"] = pygame.mixer.Sound(array=self._generate_end_chime_samples())
                self.sounds["mission_ready"] = pygame.mixer.Sound(
                    array=self._generate_mission_ready_samples()
                )
                self.sounds["cockpit_zoom"] = pygame.mixer.Sound(
                    array=self._generate_cockpit_zoom_samples()
                )
                self.sounds["cockpit_power_failure"] = pygame.mixer.Sound(
                    array=self._generate_cockpit_power_failure_samples()
                )
                self.sounds["cockpit_alarm"] = pygame.mixer.Sound(
                    array=self._generate_cockpit_alarm_samples()
                )
                self.sounds["cockpit_lock"] = pygame.mixer.Sound(
                    array=self._generate_cockpit_lock_samples()
                )
                self.sounds["cockpit_impact"] = pygame.mixer.Sound(
                    array=self._generate_cockpit_impact_samples()
                )

                hall_frequencies = {
                    GeneratorType.WIND: 620.0,
                    GeneratorType.SOLAR: 780.0,
                    GeneratorType.HAND_CRANK: 520.0,
                    GeneratorType.COIL: 690.0,
                }
                for generator, frequency in hall_frequencies.items():
                    stem = generator.name.lower()
                    self.sounds[f"hall_select_{stem}"] = pygame.mixer.Sound(
                        array=self._generate_hall_sensor_samples(frequency, selected=True)
                    )
                    self.sounds[f"hall_remove_{stem}"] = pygame.mixer.Sound(
                        array=self._generate_hall_sensor_samples(frequency, selected=False)
                    )

                for cells, timing in LAUNCH_TIER_TIMINGS.items():
                    duration = sum(timing)
                    samples = self._generate_rocket_thrust_samples(cells, duration)
                    self.sounds[f"rocket_thrust_{cells}"] = pygame.mixer.Sound(array=samples)

                # Pre-generate 101 fill tick sounds at different pitch levels
                self.fill_sounds = []
                for i in range(101):
                    # Frequencies from 400 Hz to 1200 Hz
                    freq = 400.0 + i * 8.0
                    samples = self._generate_fill_tick_samples(freq)
                    self.fill_sounds.append(pygame.mixer.Sound(array=samples))
            except Exception as e:
                print(f"Failed to synthesize UI sounds: {e}")

    def update_mission_audio(self, phase_name, crash_progress=0.0):
        """Synchronize long-running audio and one-shot cues with the cutscene."""
        if not self.enabled:
            return

        previous_phase = self._mission_audio_phase
        phase_changed = phase_name != previous_phase
        if phase_changed:
            if previous_phase == "CRASH":
                self._stop_cockpit_alarm()
            if phase_name == "ATTRACT":
                self._start_space_ambient()
            elif previous_phase == "ATTRACT":
                self._stop_space_ambient()
            if phase_name == "CRASH":
                self._last_crash_progress = 0.0
                self._play_scene_sound("cockpit_zoom", 0.72)
            self._mission_audio_phase = phase_name

        if phase_name != "CRASH":
            self._last_crash_progress = 0.0
            return

        progress = max(0.0, min(1.0, float(crash_progress)))
        previous = self._last_crash_progress

        def crossed(threshold):
            return previous < threshold <= progress

        if crossed(0.11):
            self._play_scene_sound("cockpit_power_failure", 0.72)
        if crossed(0.27):
            self._start_cockpit_alarm()
        if crossed(0.66):
            self._play_scene_sound("cockpit_lock", 0.76)
        if crossed(0.90):
            self._stop_cockpit_alarm()
            self._play_scene_sound("cockpit_impact", 0.92)
        self._last_crash_progress = progress

    def _play_scene_sound(self, key, volume):
        sound = self.sounds.get(key)
        if sound is None:
            return
        channel = pygame.mixer.find_channel()
        if channel:
            channel.set_volume(volume)
            channel.play(sound)

    def _start_space_ambient(self):
        sound = self.sounds.get("space_ambient")
        if sound is None or self.ambient_channel is None:
            return
        if not self.ambient_channel.get_busy():
            self.ambient_channel.set_volume(0.38)
            self.ambient_channel.play(sound, loops=-1, fade_ms=1400)

    def _stop_space_ambient(self):
        if self.ambient_channel is not None and self.ambient_channel.get_busy():
            self.ambient_channel.fadeout(700)

    def _start_cockpit_alarm(self):
        sound = self.sounds.get("cockpit_alarm")
        if sound is None or self.cockpit_channel is None:
            return
        self.cockpit_channel.set_volume(0.48)
        self.cockpit_channel.play(sound, loops=-1, fade_ms=180)

    def _stop_cockpit_alarm(self):
        if self.cockpit_channel is not None and self.cockpit_channel.get_busy():
            self.cockpit_channel.fadeout(180)

    def _load_sound_variants(self, key, stem, count=3):
        variants = []
        for index in range(1, count + 1):
            suffix = "" if index == 1 else f"_{index}"
            path = os.path.join(self.audio_dir, f"{stem}{suffix}.wav")
            if not os.path.exists(path):
                print(f"Audio file missing: {path}")
                continue
            try:
                variants.append(pygame.mixer.Sound(path))
            except Exception as e:
                print(f"Failed to load {path}: {e}")
        if variants:
            self.sounds[key] = variants

    def _get_stereo_pan(self, x_position):
        max_x = 600.0 * SCALE_X
        pan = (x_position + max_x) / (max_x * 2.0)
        return max(0.1, min(0.9, pan))

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
                random.uniform(0.85, 1.0)
                if not is_far
                else random.uniform(0.58, 0.78)
            )
            pan = self._get_stereo_pan(x_position)
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(
                    ((1.0 - pan) ** 0.5) * base_vol, (pan**0.5) * base_vol
                )
                channel.play(random.choice(self.sounds[key]))

    def play_crossette_split(self, x_position, y_position):
        if not self.enabled:
            return
        is_far = y_position < -150
        key = "blast_far" if is_far else "blast_near"
        if key not in self.sounds:
            return
        base_vol = random.uniform(0.58, 0.74) if not is_far else random.uniform(0.4, 0.56)
        pan = self._get_stereo_pan(x_position)
        channel = pygame.mixer.find_channel()
        if channel:
            channel.set_volume(
                ((1.0 - pan) ** 0.5) * base_vol, (pan**0.5) * base_vol
            )
            channel.play(random.choice(self.sounds[key]))

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

    def _generate_hall_sensor_samples(self, base_frequency, selected):
        """Create a short pitched confirmation for one Hall sensor edge."""
        import numpy as np

        sample_rate = 44100
        duration = 0.16
        sample_count = int(sample_rate * duration)
        time_axis = np.arange(sample_count, dtype=np.float32) / sample_rate
        if selected:
            start_frequency = base_frequency * 0.82
            end_frequency = base_frequency * 1.32
        else:
            start_frequency = base_frequency * 1.08
            end_frequency = base_frequency * 0.68
        sweep = (end_frequency - start_frequency) / duration
        phase = 2.0 * np.pi * (
            start_frequency * time_axis + 0.5 * sweep * time_axis * time_axis
        )
        wave = np.sin(phase) + 0.22 * np.sin(phase * 2.0)
        attack = np.minimum(1.0, time_axis / 0.012)
        envelope = attack * np.exp(-12.0 * time_axis)
        mono = np.clip(wave * envelope * 0.34, -1.0, 1.0)
        mono = (mono * 32767).astype(np.int16)
        return np.column_stack((mono, mono))

    def _generate_mission_ready_samples(self):
        """Create a compact three-note cue that announces an interactive screen."""
        import numpy as np

        sample_rate = 44100
        notes = ((523.25, 0.09), (659.25, 0.09), (1046.5, 0.25))
        chunks = []
        for frequency, duration in notes:
            sample_count = int(sample_rate * duration)
            time_axis = np.arange(sample_count, dtype=np.float32) / sample_rate
            wave = np.sin(2.0 * np.pi * frequency * time_axis)
            wave += 0.18 * np.sin(4.0 * np.pi * frequency * time_axis)
            envelope = np.minimum(1.0, time_axis / 0.008) * np.exp(
                -7.0 * time_axis
            )
            chunks.append((wave * envelope * 0.31 * 32767).astype(np.int16))
        mono = np.concatenate(chunks)
        return np.column_stack((mono, mono))

    def _generate_cockpit_zoom_samples(self):
        import numpy as np

        sample_rate = 44100
        duration = 1.55
        count = int(sample_rate * duration)
        time_axis = np.arange(count, dtype=np.float32) / sample_rate
        sweep = 72.0 * time_axis + 145.0 * time_axis * time_axis
        engine = np.sin(2.0 * np.pi * sweep)
        shimmer = np.sin(2.0 * np.pi * (310.0 * time_axis + 85.0 * time_axis**2))
        rng = np.random.default_rng(401)
        noise = rng.uniform(-1.0, 1.0, count).astype(np.float32)
        noise = np.convolve(noise, np.ones(32, dtype=np.float32) / 32.0, mode="same")
        envelope = np.sin(np.pi * np.minimum(1.0, time_axis / duration)) ** 0.6
        mono = np.clip((engine * 0.30 + shimmer * 0.13 + noise) * envelope, -1.0, 1.0)
        left = (mono * 0.42 * 32767).astype(np.int16)
        right = (np.roll(mono, 17) * 0.42 * 32767).astype(np.int16)
        return np.column_stack((left, right))

    def _generate_cockpit_power_failure_samples(self):
        import numpy as np

        sample_rate = 44100
        duration = 1.25
        count = int(sample_rate * duration)
        time_axis = np.arange(count, dtype=np.float32) / sample_rate
        phase = 2.0 * np.pi * (520.0 * time_axis - 175.0 * time_axis**2)
        falling_tone = np.sin(phase) + 0.28 * np.sign(np.sin(phase * 0.5))
        stutter = 0.42 + 0.58 * (np.sin(2.0 * np.pi * 8.0 * time_axis) > -0.15)
        envelope = np.minimum(1.0, time_axis / 0.012) * np.exp(-1.8 * time_axis)
        mono = np.clip(falling_tone * stutter * envelope * 0.34, -1.0, 1.0)
        mono = (mono * 32767).astype(np.int16)
        return np.column_stack((mono, mono))

    def _generate_cockpit_alarm_samples(self):
        import numpy as np

        sample_rate = 44100
        duration = 2.0
        count = int(sample_rate * duration)
        time_axis = np.arange(count, dtype=np.float32) / sample_rate
        carrier = np.sin(2.0 * np.pi * 438.0 * time_axis)
        carrier += 0.34 * np.sin(2.0 * np.pi * 876.0 * time_axis)
        pulse = np.maximum(0.0, np.sin(2.0 * np.pi * time_axis)) ** 2.2
        edge_fade = np.minimum(1.0, np.minimum(time_axis, duration - time_axis) / 0.012)
        mono = np.clip(carrier * pulse * edge_fade * 0.35, -1.0, 1.0)
        left = (mono * 32767).astype(np.int16)
        right = (np.roll(mono, 11) * 32767).astype(np.int16)
        return np.column_stack((left, right))

    def _generate_cockpit_lock_samples(self):
        import numpy as np

        sample_rate = 44100
        chunks = []
        for frequency, duration in ((780.0, 0.10), (0.0, 0.055), (1050.0, 0.10), (0.0, 0.055), (1420.0, 0.22)):
            count = int(sample_rate * duration)
            time_axis = np.arange(count, dtype=np.float32) / sample_rate
            if frequency == 0.0:
                chunks.append(np.zeros(count, dtype=np.float32))
                continue
            envelope = np.sin(np.pi * time_axis / duration) ** 0.45
            chunks.append(np.sin(2.0 * np.pi * frequency * time_axis) * envelope)
        mono = (np.concatenate(chunks) * 0.34 * 32767).astype(np.int16)
        return np.column_stack((mono, mono))

    def _generate_cockpit_impact_samples(self):
        import numpy as np

        sample_rate = 44100
        duration = 1.7
        count = int(sample_rate * duration)
        time_axis = np.arange(count, dtype=np.float32) / sample_rate
        rng = np.random.default_rng(402)
        noise = rng.uniform(-1.0, 1.0, count).astype(np.float32)
        rumble = np.convolve(noise, np.ones(64, dtype=np.float32) / 64.0, mode="same")
        boom = np.sin(2.0 * np.pi * (46.0 * time_axis - 7.5 * time_axis**2))
        crack = noise * np.exp(-24.0 * time_axis)
        envelope = np.minimum(1.0, time_axis / 0.006) * np.exp(-2.25 * time_axis)
        mono = np.clip((boom * 0.62 + rumble * 3.2 + crack * 0.42) * envelope, -1.0, 1.0)
        mono = (mono * 0.66 * 32767).astype(np.int16)
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

    def play_hall_sensor(self, generator, selected):
        if not self.enabled or not isinstance(generator, GeneratorType):
            return
        action = "select" if selected else "remove"
        sound = self.sounds.get(f"hall_{action}_{generator.name.lower()}")
        if sound is None:
            return
        channel = pygame.mixer.find_channel()
        if channel:
            channel.set_volume(0.72 if selected else 0.55)
            channel.play(sound)

    def play_mission_ready(self):
        if not self.enabled:
            return
        sound = self.sounds.get("mission_ready")
        if sound is None:
            return
        channel = pygame.mixer.find_channel()
        if channel:
            channel.set_volume(0.68)
            channel.play(sound)

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

    def _generate_rocket_thrust_samples(self, cells, duration):
        import numpy as np

        sample_rate = 44100
        count = int(sample_rate * duration)
        rng = np.random.default_rng(7300 + cells)
        noise = rng.uniform(-1.0, 1.0, count).astype(np.float32)

        # Use a circular moving average so the filtered noise is continuous at
        # the loop boundary instead of fading or padding toward silence.
        filter_width = 48
        wrapped_noise = np.concatenate((noise[-(filter_width - 1):], noise))
        cumulative = np.concatenate(
            (
                np.zeros(1, dtype=np.float32),
                np.cumsum(wrapped_noise, dtype=np.float32),
            )
        )
        rumble = (
            cumulative[filter_width:] - cumulative[:-filter_width]
        ) / filter_width

        # Integer cycle counts make both tonal layers periodic over the exact
        # sample length, preventing a phase jump when Pygame repeats the sound.
        loop_phase = np.arange(count, dtype=np.float32) / count
        low_cycles = round((34.0 + cells * 3.0) * duration)
        high_cycles = round(67.0 * duration)
        tones = (
            np.sin(2 * np.pi * low_cycles * loop_phase)
            + 0.45 * np.sin(2 * np.pi * high_cycles * loop_phase)
        )
        mono = np.clip(rumble * 2.4 + tones * 0.28, -1.0, 1.0)
        mono = (mono * (0.32 + cells * 0.05) * 32767).astype(np.int16)
        return np.column_stack((mono, mono))

    def start_rocket_thrust(self, cells):
        if not self.enabled:
            return
        self.stop_rocket_thrust()
        sound = self.sounds.get(f"rocket_thrust_{min(4, max(2, cells))}")
        if sound is None:
            return
        self.rocket_channel = pygame.mixer.find_channel()
        if self.rocket_channel:
            self.rocket_channel.set_volume(0.72)
            self.rocket_channel.play(sound, loops=-1, fade_ms=250)

    def stop_rocket_thrust(self):
        if self.rocket_channel:
            self.rocket_channel.fadeout(180)
            self.rocket_channel = None
