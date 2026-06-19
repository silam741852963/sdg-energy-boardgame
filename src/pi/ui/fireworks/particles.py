import numpy as np
import math
import random
from .config import (
    COLOR_MAP,
    COLORS,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FOV,
    VIEWER_DISTANCE,
    FIREWORK_TYPES,
)
from . import palette

HALF_SCREEN_WIDTH = SCREEN_WIDTH / 2.0
HALF_SCREEN_HEIGHT = SCREEN_HEIGHT / 2.0
PALETTE_ARR = np.array(palette.RGB_PALETTE, dtype=np.float32)
FIREWORK_NAME_TO_TYPE = {name: idx for idx, name in enumerate(FIREWORK_TYPES)}


# Dummy Particle class for compatibility with old metrics display or references if needed
class Particle:
    _pool = []
    _POOL_MAX = 2000


class ParticleSystem:
    def __init__(self, max_particles=100000):
        self.max_particles = max_particles

        # 3D Positions, velocities, launch velocities (float32)
        self.x = np.zeros(max_particles, dtype=np.float32)
        self.y = np.zeros(max_particles, dtype=np.float32)
        self.z = np.zeros(max_particles, dtype=np.float32)

        self.vx = np.zeros(max_particles, dtype=np.float32)
        self.vy = np.zeros(max_particles, dtype=np.float32)
        self.vz = np.zeros(max_particles, dtype=np.float32)

        self.launch_vx = np.zeros(max_particles, dtype=np.float32)
        self.launch_vy = np.zeros(max_particles, dtype=np.float32)
        self.launch_vz = np.zeros(max_particles, dtype=np.float32)

        # Lifecycle
        self.active = np.zeros(max_particles, dtype=bool)
        self.age = np.zeros(max_particles, dtype=np.int32)
        self.life = np.zeros(max_particles, dtype=np.int32)
        self.intensity = np.zeros(max_particles, dtype=np.float32)
        self.cull_age = np.zeros(max_particles, dtype=np.int32)
        self.crackle_start = np.zeros(max_particles, dtype=np.int32)
        self.crackle_end = np.zeros(max_particles, dtype=np.int32)

        # Specs and physical properties
        self.gravity = np.zeros(max_particles, dtype=np.float32)
        self.drag = np.zeros(max_particles, dtype=np.float32)
        self.drag_factor = np.zeros(max_particles, dtype=np.float32)

        self.base_color_idx = np.zeros(max_particles, dtype=np.int32)
        self.flicker_offset = np.zeros(max_particles, dtype=np.int32)

        self.radius = np.zeros(max_particles, dtype=np.float32)
        self.intensity_mod = np.zeros(max_particles, dtype=np.float32)

        # Boolean masks/flags
        self.is_shell = np.zeros(max_particles, dtype=bool)
        self.is_inner = np.zeros(max_particles, dtype=bool)
        self.is_split_child = np.zeros(max_particles, dtype=bool)
        self.split = np.zeros(max_particles, dtype=bool)
        self.burst = np.zeros(max_particles, dtype=bool)

        self.is_palm_tail_shell = np.zeros(max_particles, dtype=bool)
        self.has_flicker = np.zeros(max_particles, dtype=bool)
        self.has_crackle = np.zeros(max_particles, dtype=bool)
        self.has_trail = np.zeros(max_particles, dtype=bool)
        self.trail_len = np.zeros(max_particles, dtype=np.int32)
        self.glitter = np.zeros(max_particles, dtype=bool)

        # Behavior type (0=None, 1=Swim, 2=Spin, 3=Waterfall)
        self.behavior_type = np.zeros(max_particles, dtype=np.int8)

        # Spin angle (for SpinBehavior)
        self.spin_angle = np.zeros(max_particles, dtype=np.float32)

        # Projected 2D coordinates and perspective factor
        self.px = np.zeros(max_particles, dtype=np.float32)
        self.py = np.zeros(max_particles, dtype=np.float32)
        self.factor = np.zeros(max_particles, dtype=np.float32)

        # History buffers for trails (Max trail length is 20)
        self.history_x = np.zeros((max_particles, 20), dtype=np.float32)
        self.history_y = np.zeros((max_particles, 20), dtype=np.float32)
        self.history_factor = np.zeros((max_particles, 20), dtype=np.float32)

        # Store integer mapping of spec.name
        self.spec_name_type = np.zeros(max_particles, dtype=np.int8)

        # Free indices pool (using a simple Python list)
        self.free_indices = list(range(max_particles))

    def spawn(
        self,
        x,
        y,
        z,
        vx,
        vy,
        vz,
        spec,
        count=1,
        is_shell=False,
        is_inner=False,
        is_split_child=False,
        particle_color=None,
    ):
        if len(self.free_indices) < count:
            return

        idxs = [self.free_indices.pop() for _ in range(count)]
        idxs_arr = np.array(idxs, dtype=np.int32)

        # Initialize positions and velocities
        self.active[idxs_arr] = True
        self.x[idxs_arr] = x
        self.y[idxs_arr] = y
        self.z[idxs_arr] = z

        self.vx[idxs_arr] = vx
        self.vy[idxs_arr] = vy
        self.vz[idxs_arr] = vz
        self.launch_vx[idxs_arr] = vx
        self.launch_vy[idxs_arr] = vy
        self.launch_vz[idxs_arr] = vz

        self.age[idxs_arr] = 0
        if is_shell:
            self.life[idxs_arr] = spec.life_span
        else:
            self.life[idxs_arr] = spec.life_span * np.random.uniform(0.8, 1.2, count)

        self.cull_age[idxs_arr] = (self.life[idxs_arr] * 0.88).astype(np.int32)
        self.crackle_start[idxs_arr] = (self.life[idxs_arr] * 0.5).astype(np.int32)
        self.crackle_end[idxs_arr] = (self.life[idxs_arr] * 0.8).astype(np.int32)
        self.intensity[idxs_arr] = spec.intensity

        self.is_shell[idxs_arr] = is_shell
        self.is_inner[idxs_arr] = is_inner
        self.is_split_child[idxs_arr] = is_split_child
        self.split[idxs_arr] = spec.split
        self.burst[idxs_arr] = spec.burst

        self.gravity[idxs_arr] = 0.15 * (1.0 if is_shell else spec.gravity_mod)
        self.drag[idxs_arr] = 0.01 if is_shell else spec.drag
        self.drag_factor[idxs_arr] = 1.0 - self.drag[idxs_arr]

        # Determine base color index
        color = particle_color if particle_color else spec.base_color
        if is_inner:
            color = "silver" if color != "blue" else "red"

        if color == "silver":
            color_idx = 121
        else:
            color_idx = COLOR_MAP.get(color, 121) + (spec.variant * 5)

        self.base_color_idx[idxs_arr] = color_idx
        self.flicker_offset[idxs_arr] = np.random.randint(0, 60, count)

        # Behavior mappings
        self.has_flicker[idxs_arr] = spec.flicker and not is_shell
        self.has_crackle[idxs_arr] = spec.crackle and not is_shell

        from .behaviors import TrailBehavior

        trail_len_val = 0
        is_palm = False
        glitter_val = False

        # Check spec.draw_behaviors first (respect custom trails even for shells)
        for b in spec.draw_behaviors:
            if isinstance(b, TrailBehavior):
                trail_len_val = b.trail_len
                is_palm = b.palm_tail
                glitter_val = b.glitter
                break

        # Fallback to shell defaults if no custom trail behavior is specified
        if trail_len_val == 0 and is_shell and spec.burst:
            if spec.name in ["Rising Tail", "Palm Tree"]:
                trail_len_val = 8
                is_palm = True
            else:
                trail_len_val = 5

        self.trail_len[idxs_arr] = trail_len_val
        self.has_trail[idxs_arr] = trail_len_val > 0
        self.is_palm_tail_shell[idxs_arr] = is_palm
        self.glitter[idxs_arr] = glitter_val

        b_code = 0
        if not is_shell:
            if spec.swim:
                b_code = 1
            elif spec.spin:
                b_code = 2
            elif spec.waterfall:
                b_code = 3
        self.behavior_type[idxs_arr] = b_code
        self.spin_angle[idxs_arr] = np.random.uniform(0, math.pi * 2, count)

        self.spec_name_type[idxs_arr] = FIREWORK_NAME_TO_TYPE.get(spec.name, 0)
        self.radius[idxs_arr] = spec.radius
        self.intensity_mod[idxs_arr] = spec.intensity

        # Perspective projection init
        divisor = VIEWER_DISTANCE + z
        if isinstance(divisor, np.ndarray):
            divisor[divisor == 0.0] = 1.0
            factor = FOV / divisor
        else:
            factor = FOV / divisor if divisor != 0.0 else 1.0
        self.factor[idxs_arr] = factor
        self.px[idxs_arr] = x * factor + HALF_SCREEN_WIDTH
        self.py[idxs_arr] = y * factor + HALF_SCREEN_HEIGHT

        # Initialize history
        self.history_x[idxs_arr] = 0.0
        self.history_y[idxs_arr] = 0.0
        self.history_factor[idxs_arr] = 0.0

    def spawn_split_children(self, parent_indices):
        num_parents = len(parent_indices)
        count = num_parents * 4
        if len(self.free_indices) < count:
            return

        pxs = np.repeat(self.x[parent_indices], 4)
        pys = np.repeat(self.y[parent_indices], 4)
        pzs = np.repeat(self.z[parent_indices], 4)

        p_vxs = np.repeat(self.vx[parent_indices], 4)
        p_vys = np.repeat(self.vy[parent_indices], 4)
        p_vzs = np.repeat(self.vz[parent_indices], 4)

        p_lifes = np.repeat(self.life[parent_indices], 4)
        p_base_color_idxs = np.repeat(self.base_color_idx[parent_indices], 4)
        p_spec_types = np.repeat(self.spec_name_type[parent_indices], 4)
        p_radius = np.repeat(self.radius[parent_indices], 4)
        p_intensity_mod = np.repeat(self.intensity_mod[parent_indices], 4)
        p_trail_len = np.repeat(self.trail_len[parent_indices], 4)
        p_has_trail = np.repeat(self.has_trail[parent_indices], 4)

        # Calculate split child velocities
        cos_vals = np.array([2.82842712, -2.82842712, -2.82842712, 2.82842712], dtype=np.float32)
        sin_vals = np.array([2.82842712, 2.82842712, -2.82842712, -2.82842712], dtype=np.float32)

        nvxs = (p_vxs * 0.4) + np.tile(cos_vals, num_parents)
        nvys = (p_vys * 0.4) + np.tile(sin_vals, num_parents)
        nvzs = p_vzs * 0.4

        idxs = [self.free_indices.pop() for _ in range(count)]
        idxs_arr = np.array(idxs, dtype=np.int32)

        self.active[idxs_arr] = True
        self.x[idxs_arr] = pxs
        self.y[idxs_arr] = pys
        self.z[idxs_arr] = pzs

        self.vx[idxs_arr] = nvxs
        self.vy[idxs_arr] = nvys
        self.vz[idxs_arr] = nvzs
        self.launch_vx[idxs_arr] = nvxs
        self.launch_vy[idxs_arr] = nvys
        self.launch_vz[idxs_arr] = nvzs

        self.age[idxs_arr] = 0
        self.life[idxs_arr] = (p_lifes * 0.4).astype(np.int32)

        self.cull_age[idxs_arr] = (self.life[idxs_arr] * 0.88).astype(np.int32)
        self.crackle_start[idxs_arr] = (self.life[idxs_arr] * 0.5).astype(np.int32)
        self.crackle_end[idxs_arr] = (self.life[idxs_arr] * 0.8).astype(np.int32)
        self.intensity[idxs_arr] = p_intensity_mod

        self.is_shell[idxs_arr] = False
        self.is_inner[idxs_arr] = False
        self.is_split_child[idxs_arr] = True
        self.split[idxs_arr] = False
        self.burst[idxs_arr] = True

        # Crossette spec gravity is 0.2, drag is 0.04
        self.gravity[idxs_arr] = 0.15 * 0.2
        self.drag[idxs_arr] = 0.04
        self.drag_factor[idxs_arr] = 1.0 - 0.04

        self.base_color_idx[idxs_arr] = p_base_color_idxs
        self.flicker_offset[idxs_arr] = np.random.randint(0, 60, count)

        self.has_flicker[idxs_arr] = False
        self.has_crackle[idxs_arr] = False
        self.has_trail[idxs_arr] = p_has_trail
        self.trail_len[idxs_arr] = p_trail_len
        self.glitter[idxs_arr] = False
        self.is_palm_tail_shell[idxs_arr] = False
        self.behavior_type[idxs_arr] = 0
        self.spec_name_type[idxs_arr] = p_spec_types
        self.radius[idxs_arr] = p_radius
        self.intensity_mod[idxs_arr] = p_intensity_mod

        self.history_x[idxs_arr] = 0.0
        self.history_y[idxs_arr] = 0.0
        self.history_factor[idxs_arr] = 0.0

        # Projected coords
        divisor = VIEWER_DISTANCE + pzs
        divisor[divisor == 0] = 1.0
        factor = FOV / divisor
        self.factor[idxs_arr] = factor
        self.px[idxs_arr] = pxs * factor + HALF_SCREEN_WIDTH
        self.py[idxs_arr] = pys * factor + HALF_SCREEN_HEIGHT



    def update_intensity(self, active_mask):
        if not np.any(active_mask):
            return

        self.intensity[~active_mask] = 0.0

        shell_burst = active_mask & self.is_shell & self.burst
        self.intensity[shell_burst] = self.intensity_mod[shell_burst]

        other_mask = active_mask & ~shell_burst
        if np.any(other_mask):
            age_other = self.age[other_mask]
            life_other = self.life[other_mask]
            intensity_mod_other = self.intensity_mod[other_mask]
            spec_type_other = self.spec_name_type[other_mask]

            remaining = np.maximum(0.0, 1.0 - age_other / np.maximum(1.0, life_other))
            val = remaining.copy()

            comet_mask = spec_type_other == 2
            val[comet_mask] *= 1.5

            pearls_mask = spec_type_other == 4
            val[pearls_mask] *= 3.0

            self.intensity[other_mask] = np.minimum(1.0, val) * intensity_mod_other

    def get_intensity_subset(self, indices):
        return self.intensity[indices]

    def update(self):
        active_mask = self.active
        if not np.any(active_mask):
            return

        # 1. Update age
        self.age[active_mask] += 1

        # Update intensities for active particles
        self.update_intensity(active_mask)

        # 2. Cull expired/faded particles
        cull_eligible = active_mask & ~(self.is_shell & self.burst)
        if np.any(cull_eligible):
            cull_indices = np.where(cull_eligible)[0]
            cull_mask = (
                (self.age[cull_indices] > self.cull_age[cull_indices])
                | (self.intensity[cull_indices] < 0.12)
            )
            culled_indices = cull_indices[cull_mask]
            if len(culled_indices) > 0:
                self.active[culled_indices] = False
                self.free_indices.extend(culled_indices)
                active_mask = self.active
                if not np.any(active_mask):
                    return

        # 3. Store current projected position to history *before* updating position
        trail_update_mask = active_mask & self.has_trail
        if np.any(trail_update_mask):
            self.history_x[trail_update_mask, :-1] = self.history_x[
                trail_update_mask, 1:
            ]
            self.history_y[trail_update_mask, :-1] = self.history_y[
                trail_update_mask, 1:
            ]
            self.history_factor[trail_update_mask, :-1] = self.history_factor[
                trail_update_mask, 1:
            ]

            self.history_x[trail_update_mask, -1] = self.px[trail_update_mask]
            self.history_y[trail_update_mask, -1] = self.py[trail_update_mask]
            self.history_factor[trail_update_mask, -1] = self.factor[trail_update_mask]

        # 4. Apply update behaviors
        # Swim behavior (behavior_type == 1)
        swim_mask = active_mask & (self.behavior_type == 1)
        n_swim = np.count_nonzero(swim_mask)
        if n_swim > 0:
            self.vx[swim_mask] += np.random.uniform(-3.0, 3.0, n_swim)
            self.vz[swim_mask] += np.random.uniform(-3.0, 3.0, n_swim)
            self.vy[swim_mask] += np.random.uniform(-1.0, 1.0, n_swim)

        # Spin behavior (behavior_type == 2)
        spin_mask = active_mask & (self.behavior_type == 2)
        n_spin = np.count_nonzero(spin_mask)
        if n_spin > 0:
            self.spin_angle[spin_mask] += 1.2
            self.vx[spin_mask] += np.cos(self.spin_angle[spin_mask]) * 2.5
            self.vz[spin_mask] += np.sin(self.spin_angle[spin_mask]) * 2.5
            self.vy[spin_mask] += np.random.uniform(-0.5, 0.5, n_spin)

        # Waterfall behavior (behavior_type == 3)
        waterfall_mask = active_mask & (self.behavior_type == 3)
        if np.any(waterfall_mask):
            self.gravity[waterfall_mask] = np.minimum(
                0.3, self.gravity[waterfall_mask] + 0.005
            )

        # 5. Physics update (gravity & drag)
        self.vy[active_mask] += self.gravity[active_mask]
        self.vx[active_mask] *= self.drag_factor[active_mask]
        self.vy[active_mask] *= self.drag_factor[active_mask]
        self.vz[active_mask] *= self.drag_factor[active_mask]

        self.x[active_mask] += self.vx[active_mask]
        self.y[active_mask] += self.vy[active_mask]
        self.z[active_mask] += self.vz[active_mask]

        # 6. Perspective projection
        divisor = VIEWER_DISTANCE + self.z[active_mask]
        divisor[divisor == 0] = 1.0
        factor = FOV / divisor

        self.factor[active_mask] = factor
        self.px[active_mask] = self.x[active_mask] * factor + HALF_SCREEN_WIDTH
        self.py[active_mask] = self.y[active_mask] * factor + HALF_SCREEN_HEIGHT

        # 7. Split check
        split_eligible = (
            active_mask & self.split & ~self.is_split_child & ~self.is_shell
        )
        if np.any(split_eligible):
            half_life = (self.life[split_eligible] * 0.5).astype(np.int32)
            should_split = np.zeros_like(split_eligible)
            should_split[split_eligible] = self.age[split_eligible] == half_life
            split_indices = np.where(should_split)[0]
            if len(split_indices) > 0:
                self.active[split_indices] = False
                self.free_indices.extend(split_indices)
                self.spawn_split_children(split_indices)

    def gather_instances(self, frame_count):
        active_indices = np.where(self.active)[0]
        if len(active_indices) == 0:
            return np.empty((0, 7), dtype=np.float32)

        chunks = []

        # 1. Main particles
        flicker_skip = self.has_flicker & (
            ((frame_count + self.flicker_offset) % 6) < 3
        )
        crackle_phase2 = self.has_crackle & (self.age > self.crackle_end)
        crackle_phase1 = (
            self.has_crackle
            & (self.age > self.crackle_start)
            & (self.age <= self.crackle_end)
        )

        draw_main = self.active & ~flicker_skip & ~crackle_phase1 & ~crackle_phase2
        # Willow is type 14 (willow_mask)
        willow_mask = self.spec_name_type == 14
        draw_main = draw_main & (~willow_mask | self.is_shell)

        main_indices = np.where(draw_main)[0]
        num_main = len(main_indices)
        if num_main > 0:
            px_main = self.px[main_indices]
            py_main = self.py[main_indices]
            factor_main = self.factor[main_indices]
            base_col_main = self.base_color_idx[main_indices]
            is_palm_main = self.is_palm_tail_shell[main_indices]
            radius_main = self.radius[main_indices]
            intensity_main = self.get_intensity_subset(main_indices)

            shade_offset = np.clip(np.floor((1.2 - factor_main) * 5.0).astype(np.int32) + 1, 0, 4)

            color_idx = base_col_main + shade_offset
            color_idx[base_col_main == 121] = 121
            color_idx[is_palm_main] = 121

            rgb = PALETTE_ARR[color_idx]
            size = np.maximum(2.0, factor_main * radius_main * 24.0)

            main_chunk = np.column_stack((px_main, py_main, size, rgb, intensity_main))
            chunks.append(main_chunk)

            # Scatter & Glitter for active particle heads (run on main_indices to avoid per-segment CPU overhead)
            # Scatter 1 (40% chance of colored sparks)
            has_trail_main = self.has_trail[main_indices]
            if np.any(has_trail_main):
                t_indices = main_indices[has_trail_main]
                t_factor = factor_main[has_trail_main]
                t_intensity = intensity_main[has_trail_main]
                
                skip_t = (t_intensity < 0.3) | (t_factor < 0.4)
                s1_mask = ~skip_t & (np.random.rand(len(t_indices)) < 0.4)
                s1_sel = t_indices[s1_mask]
                num_s1 = len(s1_sel)
                if num_s1 > 0:
                    s1_px = self.px[s1_sel]
                    s1_py = self.py[s1_sel]
                    s1_factor = self.factor[s1_sel]
                    s1_radius = (self.radius[s1_sel] + 3.0) * s1_factor
                    sx1 = s1_px + np.random.uniform(-1.0, 1.0, num_s1) * s1_radius
                    sy1 = s1_py + np.random.uniform(-1.0, 1.0, num_s1) * s1_radius
                    
                    s1_col = color_idx[has_trail_main][s1_mask]
                    rgb_s1 = PALETTE_ARR[s1_col]
                    size_s1 = 3.0 * s1_factor
                    alpha_s1 = t_intensity[s1_mask] * 0.7 * 1.6
                    
                    chunks.append(np.column_stack((sx1, sy1, size_s1, rgb_s1, alpha_s1)))

                # Scatter 2 (8% chance of white sparks)
                s2_mask = ~skip_t & (np.random.rand(len(t_indices)) < 0.08)
                s2_sel = t_indices[s2_mask]
                num_s2 = len(s2_sel)
                if num_s2 > 0:
                    s2_px = self.px[s2_sel]
                    s2_py = self.py[s2_sel]
                    s2_factor = self.factor[s2_sel]
                    s2_radius_offset = (self.radius[s2_sel] + 3.0) * s2_factor + 2.0
                    sx2 = s2_px + np.random.uniform(-1.0, 1.0, num_s2) * s2_radius_offset
                    sy2 = s2_py + np.random.uniform(-1.0, 1.0, num_s2) * s2_radius_offset
                    
                    rgb_s2 = PALETTE_ARR[np.repeat(121, num_s2)]
                    size_s2 = 3.0 * s2_factor
                    alpha_s2 = t_intensity[s2_mask] * 0.7 * 1.6
                    
                    chunks.append(np.column_stack((sx2, sy2, size_s2, rgb_s2, alpha_s2)))

            # Glitter (40% chance of white flashes for particles with glitter)
            glitter_active = self.glitter[main_indices]
            if np.any(glitter_active):
                g_indices = main_indices[glitter_active]
                g_factor = factor_main[glitter_active]
                g_intensity = intensity_main[glitter_active]
                
                g_mask = (g_intensity >= 0.3) & (np.random.rand(len(g_indices)) < 0.4)
                g_sel = g_indices[g_mask]
                num_g = len(g_sel)
                if num_g > 0:
                    g_px = self.px[g_sel]
                    g_py = self.py[g_sel]
                    g_factor_sel = g_factor[g_mask]
                    g_intensity_sel = g_intensity[g_mask] * 1.5
                    
                    rgb_g = PALETTE_ARR[np.repeat(121, num_g)]
                    size_g = np.maximum(4.0, 8.0 * g_factor_sel)
                    
                    chunks.append(np.column_stack((g_px, g_py, size_g, rgb_g, g_intensity_sel)))

        # 2. Crackle instances
        draw_crackle = self.active & crackle_phase2
        crackle_indices = np.where(draw_crackle)[0]
        num_crackle = len(crackle_indices)
        if num_crackle > 0:
            factor_crackle = self.factor[crackle_indices]
            px_crackle = self.px[crackle_indices] + np.random.uniform(-3.0, 3.0, num_crackle)
            py_crackle = self.py[crackle_indices] + np.random.uniform(-3.0, 3.0, num_crackle)
            size_crackle = np.maximum(4.0, 8.0 * factor_crackle)
            rgb_crackle = PALETTE_ARR[np.repeat(121, num_crackle)]
            intensity_crackle = self.get_intensity_subset(crackle_indices) * 1.5

            crackle_chunk = np.column_stack(
                (px_crackle, py_crackle, size_crackle, rgb_crackle, intensity_crackle)
            )
            chunks.append(crackle_chunk)

        # 3. Trail instances
        has_trail_mask = self.active & self.has_trail
        if np.any(has_trail_mask):
            trail_indices_all = np.where(has_trail_mask)[0]
            num_trails = len(trail_indices_all)
            J = np.arange(20)[None, :]
            trail_len_all = self.trail_len[trail_indices_all]
            valid_slot = J >= (20 - trail_len_all[:, None])
            h_fact_all = self.history_factor[trail_indices_all, :]
            valid_factor = h_fact_all > 0.0

            valid_mask = valid_slot & valid_factor
            row_idx, col_idx = np.where(valid_mask)
            num_instances = len(row_idx)

            if num_instances > 0:
                sub_indices = trail_indices_all[row_idx]
                j = col_idx

                hx = self.history_x[sub_indices, j]
                hy = self.history_y[sub_indices, j]
                hfactor = self.history_factor[sub_indices, j]

                age_sub = self.age[sub_indices]
                trail_len_sub = self.trail_len[sub_indices]
                hist_len = np.minimum(age_sub, trail_len_sub)

                i = j - (20 - hist_len)
                denom = np.maximum(1.0, hist_len - 1.0)
                ratio = i / denom
                alpha_mult = 0.15 + 0.85 * ratio
                size_mult = 0.5 + 0.5 * ratio

                hfactor_adjusted = hfactor - 0.3
                shade_offset = np.clip(np.floor((1.2 - hfactor_adjusted) * 5.0).astype(np.int32) + 1, 0, 4)

                base_col_sub = self.base_color_idx[sub_indices]
                is_palm_sub = self.is_palm_tail_shell[sub_indices]

                trail_col_idx = base_col_sub + shade_offset
                trail_col_idx[base_col_sub == 121] = 121
                trail_col_idx[is_palm_sub] = 121

                rgb_trail = PALETTE_ARR[trail_col_idx]

                thickness = self.radius[sub_indices]
                size_trail = np.maximum(3.0, hfactor * thickness * 10.0 * size_mult)

                intensity_sub = self.get_intensity_subset(sub_indices)
                alpha_trail = np.minimum(1.0, intensity_sub * alpha_mult * 1.6)

                spec_type_sub = self.spec_name_type[sub_indices]
                is_comet_pearl = (spec_type_sub == 2) | (spec_type_sub == 4)
                if np.any(is_comet_pearl):
                    alpha_trail[is_comet_pearl] = np.minimum(
                        1.0, alpha_trail[is_comet_pearl] * 1.5
                    )
                    size_trail[is_comet_pearl] = size_trail[is_comet_pearl] * 1.8
                trail_chunk = np.column_stack(
                    (hx, hy, size_trail, rgb_trail, alpha_trail)
                )
                chunks.append(trail_chunk)

                # Scatter/Glitter removed from per-segment trail to run on heads instead
                pass

        if len(chunks) == 0:
            return np.empty((0, 7), dtype=np.float32)

        return np.vstack(chunks).astype(np.float32)
