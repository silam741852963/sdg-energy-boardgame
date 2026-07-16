import math
import random
import copy
import numpy as np

from .config import SCREEN_WIDTH, SCREEN_HEIGHT, SCALE_X, SCALE_Y, COLOR_MAP, COLORS, FOV, VIEWER_DISTANCE
from .physics import calculate_launch_velocity
from .models import get_random_preset
from .particles import ParticleSystem

class ShellMock:
    def __init__(self, vx, vy, vz, launch_vx, launch_vy, launch_vz):
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.launch_vx = launch_vx
        self.launch_vy = launch_vy
        self.launch_vz = launch_vz

class ParticlesWrapper:
    def __init__(self, ps):
        self.ps = ps
    def __len__(self):
        return int(np.count_nonzero(self.ps.active & ~self.ps.is_shell))
    def clear(self):
        self.ps.active[:] = False
        self.ps.free_indices = list(range(self.ps.max_particles))
        self.ps.history_x[:] = 0.0
        self.ps.history_y[:] = 0.0
        self.ps.history_factor[:] = 0.0

class ShellsWrapper:
    def __init__(self, ps, specs):
        self.ps = ps
        self.specs = specs
    def __len__(self):
        return int(np.count_nonzero(self.ps.active & self.ps.is_shell))
    def clear(self):
        shell_indices = np.where(self.ps.active & self.ps.is_shell)[0]
        self.ps.active[shell_indices] = False
        self.ps.free_indices.extend(shell_indices)
        self.specs.clear()
    def __iter__(self):
        return iter([])

class FireworkManager:
    def __init__(self, audio_system, lighting_system):
        self.audio = audio_system
        self.lighting = lighting_system
        self.particle_system = ParticleSystem(10000)
        self.active_shell_specs = {}
        
        # Emulated lists for backward compatibility with engine.py
        self._particles_wrapper = ParticlesWrapper(self.particle_system)
        self._shells_wrapper = ShellsWrapper(self.particle_system, self.active_shell_specs)

    @property
    def particles(self):
        return self._particles_wrapper

    @particles.setter
    def particles(self, val):
        pass

    @property
    def shells(self):
        return self._shells_wrapper

    @shells.setter
    def shells(self, val):
        pass

    def launch(
        self,
        target_px,
        target_py,
        forced_spec=None,
        source_px=None,
        source_py=None,
    ):
        tz = random.uniform(-100, 100)
        
        factor = FOV / (VIEWER_DISTANCE + tz) if (VIEWER_DISTANCE + tz) != 0 else 1.0
        
        tx = (target_px - (SCREEN_WIDTH / 2)) / factor
        clamped_py = max(
            int(350 * SCALE_Y), min(target_py, SCREEN_HEIGHT - int(300 * SCALE_Y))
        )
        ty = (clamped_py - (SCREEN_HEIGHT / 2)) / factor

        spec = forced_spec if forced_spec else get_random_preset()

        if source_px is not None and source_py is not None:
            source_factor = FOV / VIEWER_DISTANCE
            sx = (source_px - (SCREEN_WIDTH / 2)) / source_factor
            sy = (source_py - (SCREEN_HEIGHT / 2)) / source_factor
            sz = 0.0
        elif spec.name == "Rising Tail":
            sx = tx
            sz = tz
            sy = SCREEN_HEIGHT / 2
        else:
            sx = random.uniform(-600 * SCALE_X, 600 * SCALE_X)
            sz = random.uniform(-100, 100)
            sy = SCREEN_HEIGHT / 2
        gravity = 0.3
        vx, vy, vz = calculate_launch_velocity((sx, sy, sz), (tx, ty, tz), gravity)

        self.audio.play_launch(sx)
        
        # In launch strategies, they call manager.particle_system.spawn(...)
        # Wait, how does it track the spawned shell's spec?
        # The launch strategy apply methods will run and spawn a shell.
        # We need to capture the index of that spawned shell.
        # To do this, we can override or intercept the spawn method during launch,
        # or we can check which indices were activated!
        # Let's count active shell indices before and after applying strategy!
        pre_active_shells = np.where(self.particle_system.active & self.particle_system.is_shell)[0]
        
        spec.launch_strategy.apply(self, sx, sy, sz, vx, vy, vz, spec)
        
        post_active_shells = np.where(self.particle_system.active & self.particle_system.is_shell)[0]
        
        # New shells are those in post but not in pre
        new_shells = np.setdiff1d(post_active_shells, pre_active_shells)
        for idx in new_shells:
            self.active_shell_specs[idx] = spec

    def explode_vectorized(self, idx):
        spec = self.active_shell_specs.pop(idx, None)
        if not spec or not spec.burst:
            return

        shell_x = self.particle_system.x[idx]
        shell_y = self.particle_system.y[idx]
        shell_z = self.particle_system.z[idx]

        self.audio.play_explosion(spec, shell_x, shell_y)

        if spec.base_color != "silver":
            darkest_shade_idx = COLOR_MAP[spec.base_color] + (spec.variant * 5) + 4
            self.lighting.trigger_sky_flash(darkest_shade_idx)

        self.lighting.add_ground_reflection(
            shell_x,
            shell_z,
            spec.life_span,
            self.lighting.sky_flash_color,
            radius_mod=spec.radius,
        )

        layers = [False]
        if spec.pistil:
            layers.append(True)

        color_pool = [spec.base_color]
        if spec.colors:
            color_pool = spec.colors
        elif spec.multicolor > 1:
            color_pool = random.sample(COLORS, min(spec.multicolor, len(COLORS)))

        # Create shell mock for strategy calculations
        shell_mock = ShellMock(
            self.particle_system.vx[idx],
            self.particle_system.vy[idx],
            self.particle_system.vz[idx],
            self.particle_system.launch_vx[idx],
            self.particle_system.launch_vy[idx],
            self.particle_system.launch_vz[idx]
        )

        for is_inner in layers:
            count = spec.particle_count // 2 if is_inner else spec.particle_count
            speed_mult = 0.4 if is_inner else 1.0

            pvx, pvy, pvz = spec.burst_strategy.get_velocities(shell_mock, speed_mult, spec, count)

            if is_inner and getattr(spec, "pistil_color", None):
                colors_choice = spec.pistil_color
            elif len(color_pool) > 1:
                colors_choice = [random.choice(color_pool) for _ in range(count)]
            else:
                colors_choice = color_pool[0]

            self.particle_system.spawn(
                shell_x, shell_y, shell_z,
                pvx, pvy, pvz,
                spec, count,
                is_inner=is_inner,
                particle_color=colors_choice
            )

    def update(self):
        # Update particles/shells (positions, physics, culling, split)
        self.particle_system.update()

        # Check for exploding shells
        explode_mask = (
            self.particle_system.active &
            self.particle_system.is_shell &
            self.particle_system.burst &
            (self.particle_system.vy >= 0.0)
        )
        explode_indices = np.where(explode_mask)[0]

        for idx in explode_indices:
            self.explode_vectorized(idx)
            self.particle_system.active[idx] = False
            self.particle_system.free_indices.append(idx)

    def draw(self, renderer, frame_count):
        instance_data = self.particle_system.gather_instances(frame_count)
        renderer.draw_particles(instance_data)
