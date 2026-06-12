import math
import random
import copy
from .particles import Particle
from .config import COLORS


class LaunchStrategy:
    def apply(self, manager, sx, sy, sz, vx, vy, vz, spec):
        pass


class SingleLaunch(LaunchStrategy):
    def apply(self, manager, sx, sy, sz, vx, vy, vz, spec):
        shell = Particle.create(sx, sy, sz, vx, vy, vz, spec, is_shell=True)
        manager.shells.append(shell)


class SpreadLaunch(LaunchStrategy):
    def __init__(self, num_shells=7, spread_width=30.0, arc_height=10.0, arc_mult=0.5):
        self.num_shells = num_shells
        self.spread_width = spread_width
        self.arc_height = arc_height
        self.arc_mult = arc_mult

    def apply(self, manager, sx, sy, sz, vx, vy, vz, spec):
        for i in range(self.num_shells):
            offset = -(self.spread_width / 2) + (
                i * (self.spread_width / (self.num_shells - 1))
            )
            off_vx = vx + offset
            off_vy = vy - (self.arc_height - abs(offset) * self.arc_mult)
            off_vz = vz
            shell = Particle.create(sx, sy, sz, off_vx, off_vy, off_vz, spec, is_shell=True)
            manager.shells.append(shell)


class MulticolorSpreadLaunch(LaunchStrategy):
    def __init__(self, num_shells=7, spread_width=12.0):
        self.num_shells = num_shells
        self.spread_width = spread_width

    def apply(self, manager, sx, sy, sz, vx, vy, vz, spec):
        mixed_colors = (
            random.sample(COLORS, min(spec.multicolor, len(COLORS)))
            if spec.multicolor > 1
            else [spec.base_color]
        )

        for i in range(self.num_shells):
            offset = -(self.spread_width / 2) + (
                i * (self.spread_width / (self.num_shells - 1))
            )
            off_vx = vx + offset
            off_vy = vy - 4.0
            off_vz = vz

            p_spec = copy.copy(spec)
            p_spec.base_color = mixed_colors[i % len(mixed_colors)]

            shell = Particle.create(sx, sy, sz, off_vx, off_vy, off_vz, p_spec, is_shell=True)
            shell.particle_color = p_spec.base_color
            manager.shells.append(shell)


class BurstStrategy:
    def get_velocity(self, shell, speed, spec):
        return 0, 0, 0


class SphericalBurst(BurstStrategy):
    def __init__(self, speed_min=0.8, add_shell_velocity=True):
        self.speed_min = speed_min
        self.add_shell_velocity = add_shell_velocity

    def get_velocity(self, shell, speed, spec):
        phi = random.uniform(0, math.pi * 2)
        costheta = random.uniform(-1, 1)
        theta = math.acos(costheta)
        speed = (
            random.uniform(
                spec.speed_variance * self.speed_min, spec.speed_variance * 1.6
            )
            * speed
        )

        pvx = speed * math.sin(theta) * math.cos(phi)
        pvy = speed * math.sin(theta) * math.sin(phi)
        pvz = speed * math.cos(theta)

        if self.add_shell_velocity:
            pvx += shell.vx * 0.2
            pvy += shell.vy * 0.2
            pvz += shell.vz * 0.2
            pvy -= random.uniform(0.5, 2.0)

        return pvx, pvy, pvz


class PalmBurst(BurstStrategy):
    def get_velocity(self, shell, speed, spec):
        phi = random.uniform(math.pi * 0.8, math.pi * 2.2)
        costheta = random.uniform(-1, 1)
        theta = math.acos(costheta)
        speed = (
            random.uniform(spec.speed_variance * 0.8, spec.speed_variance * 1.6) * speed
        )

        pvx = speed * math.sin(theta) * math.cos(phi)
        pvy = speed * math.sin(theta) * math.sin(phi)
        pvz = speed * math.cos(theta)

        pvx += shell.vx * 0.2
        pvy += shell.vy * 0.2
        pvz += shell.vz * 0.2
        pvy -= random.uniform(0.5, 2.0)

        return pvx, pvy, pvz


class ConeBurst(BurstStrategy):
    def get_velocity(self, shell, speed, spec):
        phi = random.uniform(0.6 * math.pi, 2.4 * math.pi)
        costheta = random.uniform(-0.95, 0.95)
        theta = math.acos(costheta)
        speed = (
            random.uniform(spec.speed_variance * 0.8, spec.speed_variance * 1.6) * speed
        )

        pvx = speed * math.sin(theta) * math.cos(phi)
        pvy = speed * math.sin(theta) * math.sin(phi)
        pvz = speed * math.cos(theta)

        mag = math.sqrt(shell.launch_vx**2 + shell.launch_vy**2 + shell.launch_vz**2)
        if mag > 0:
            nx = shell.launch_vx / mag
            ny = shell.launch_vy / mag
            nz = shell.launch_vz / mag

            pvx = (pvx * 0.7) + (nx * speed * 0.9)
            pvy = (pvy * 0.7) + (ny * speed * 0.9)
            pvz = (pvz * 0.7) + (nz * speed * 0.9)

        return pvx, pvy, pvz
