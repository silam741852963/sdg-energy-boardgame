import math
import random
import pyxel

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
    def pre_draw(self, particle):
        """Returns True if the draw is completely handled or should be skipped."""
        return False
        
    def post_draw(self, particle):
        pass

class CrackleBehavior(DrawBehavior):
    def pre_draw(self, particle):
        if particle.age > particle.life * 0.8:
            pyxel.circ(
                particle.px + random.randint(-3, 3), 
                particle.py + random.randint(-3, 3), 
                1, 121
            )
            return True
        elif particle.age > particle.life * 0.5:
            return True
        return False

class FlickerBehavior(DrawBehavior):
    def pre_draw(self, particle):
        if (pyxel.frame_count + particle.flicker_offset) % 6 < 3:
            return True
        return False

class TrailBehavior(DrawBehavior):
    def __init__(self, palm_tail=False, glitter=False, trail_len=5):
        self.palm_tail = palm_tail
        self.glitter = glitter
        self.trail_len = trail_len

    def post_draw(self, particle):
        hist_len = len(particle.history)
        if hist_len < 2:
            return
            
        # Skip expensive scatter effects for dim/distant particles
        intensity = particle.get_intensity()
        skip_scatter = intensity < 0.3 or particle.factor < 0.4
            
        thickness = int(particle.spec.radius)

        for i in range(1, hist_len):
            px1, py1, factor1 = particle.history[i - 1]
            px2, py2, factor2 = particle.history[i]

            if factor1 <= 0 or factor2 <= 0:
                continue
                
            trail_col = particle.get_shade(factor1 - 0.3)
            
            if not skip_scatter:
                scatter_radius = thickness + 3

                if random.random() < 0.4:
                    sx = px1 + random.uniform(-scatter_radius, scatter_radius)
                    sy = py1 + random.uniform(-scatter_radius, scatter_radius)
                    pyxel.pset(int(sx), int(sy), trail_col)

                if random.random() < 0.08:
                    sx = px1 + random.uniform(-scatter_radius - 2, scatter_radius + 2)
                    sy = py1 + random.uniform(-scatter_radius - 2, scatter_radius + 2)
                    pyxel.pset(int(sx), int(sy), 121)

            if self.glitter and random.random() < 0.4:
                pyxel.pset(int(px1), int(py1), 121)
            else:
                if particle.is_shell and self.palm_tail:
                    t_width = thickness + 1
                    for w in range(-t_width, t_width + 1):
                        pyxel.line(int(px1 + w), int(py1), int(px2 + w), int(py2), trail_col)
                else:
                    for w in range(-thickness, thickness + 1):
                        pyxel.line(int(px1 + w), int(py1), int(px2 + w), int(py2), trail_col)
