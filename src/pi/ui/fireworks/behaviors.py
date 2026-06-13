import math
import random
from . import palette

class UpdateBehavior:
    def update(self, particle):
        pass

class SwimBehavior(UpdateBehavior):
    def update(self, particle):
        particle.vx += random.uniform(-3.0, 3.0)
        particle.vz += random.uniform(-3.0, 3.0)
        particle.vy += random.uniform(-1.0, 1.0)

class SpinBehavior(UpdateBehavior):
    def update(self, particle):
        particle.spin_angle += 1.2
        particle.vx += math.cos(particle.spin_angle) * 2.5
        particle.vz += math.sin(particle.spin_angle) * 2.5
        particle.vy += random.uniform(-0.5, 0.5)

class WaterfallBehavior(UpdateBehavior):
    def update(self, particle):
        particle.gravity = min(0.3, particle.gravity + 0.005)


class DrawBehavior:
    def pre_draw_gpu(self, particle, instance_data, frame_count):
        """Returns True if the draw is completely handled or should be skipped."""
        return False
        
    def post_draw_gpu(self, particle, instance_data, frame_count):
        pass

class CrackleBehavior(DrawBehavior):
    def pre_draw_gpu(self, particle, instance_data, frame_count):
        if particle.age > particle.life * 0.8:
            cx = particle.px + random.randint(-3, 3)
            cy = particle.py + random.randint(-3, 3)
            color = palette.get_color(121)
            instance_data.append((
                cx, cy, 3.0 * particle.factor, 
                color[0], color[1], color[2], 
                particle.get_intensity()
            ))
            return True
        elif particle.age > particle.life * 0.5:
            return True
        return False

class FlickerBehavior(DrawBehavior):
    def pre_draw_gpu(self, particle, instance_data, frame_count):
        if (frame_count + particle.flicker_offset) % 6 < 3:
            return True
        return False

class TrailBehavior(DrawBehavior):
    def __init__(self, palm_tail=False, glitter=False, trail_len=5):
        self.palm_tail = palm_tail
        self.glitter = glitter
        self.trail_len = trail_len

    def post_draw_gpu(self, particle, instance_data, frame_count):
        hist_len = len(particle.history)
        if hist_len < 2:
            return
            
        # Skip expensive scatter effects for dim/distant particles
        intensity = particle.get_intensity()
        skip_scatter = intensity < 0.3 or particle.factor < 0.4
            
        thickness = particle.spec.radius

        for i in range(hist_len):
            hx, hy, hfactor = particle.history[i]
            if hfactor <= 0:
                continue
                
            # Fades out towards the tail (earlier elements are at index 0)
            alpha_mult = 0.15 + 0.85 * (i / (hist_len - 1 if hist_len > 1 else 1))
            size_mult = 0.5 + 0.5 * (i / (hist_len - 1 if hist_len > 1 else 1))
            
            trail_col_idx = 121 if particle.is_palm_tail_shell else particle.get_shade(hfactor - 0.3)
            color = palette.get_color(trail_col_idx)
            
            size = max(2.0, hfactor * thickness * 8.0 * size_mult)
            alpha = intensity * alpha_mult
            
            instance_data.append((hx, hy, size, color[0], color[1], color[2], alpha))
            
            if not skip_scatter:
                scatter_radius = (thickness + 3) * hfactor

                if random.random() < 0.4:
                    sx = hx + random.uniform(-scatter_radius, scatter_radius)
                    sy = hy + random.uniform(-scatter_radius, scatter_radius)
                    c = palette.get_color(trail_col_idx)
                    instance_data.append((sx, sy, 3.0 * hfactor, c[0], c[1], c[2], alpha * 0.7))

                if random.random() < 0.08:
                    sx = hx + random.uniform(-scatter_radius - 2, scatter_radius + 2)
                    sy = hy + random.uniform(-scatter_radius - 2, scatter_radius + 2)
                    c = palette.get_color(121)
                    instance_data.append((sx, sy, 3.0 * hfactor, c[0], c[1], c[2], alpha * 0.7))

            if self.glitter and random.random() < 0.4:
                c = palette.get_color(121)
                instance_data.append((hx, hy, 3.0 * hfactor, c[0], c[1], c[2], alpha))
