import math
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, FOV, VIEWER_DISTANCE


def project_3d_to_2d(x, y, z):
    """Projects 3D coordinates to a 2D screen using perspective divide."""
    factor = FOV / (VIEWER_DISTANCE + z)
    x_proj = x * factor + (SCREEN_WIDTH / 2)
    y_proj = y * factor + (SCREEN_HEIGHT / 2)
    return x_proj, y_proj, factor


def calculate_launch_velocity(start, target, gravity):
    """
    Calculates the exact X, Y, Z velocities needed to reach target_y at the apex of the arc.
    """
    sx, sy, sz = start
    tx, ty, tz = target

    dist_y = ty - sy
    # Target must be above start (in Pyxel, lower Y is higher on screen)
    if dist_y >= 0:
        dist_y = -10

    # v^2 = u^2 + 2as -> at apex v=0 -> u = sqrt(-2 * a * s)
    vy = -math.sqrt(2 * gravity * abs(dist_y))

    # Time to reach apex: t = (v - u) / a
    time_to_apex = abs(vy / gravity)

    # Constant velocity on X and Z axis
    vx = (tx - sx) / time_to_apex
    vz = (tz - sz) / time_to_apex

    return vx, vy, vz
