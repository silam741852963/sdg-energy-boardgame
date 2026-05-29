SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080  # True 1080p Baseline
FULLSCREEN = True

# Dynamic Scaling Ratios
SCALE_X = SCREEN_WIDTH / 1920.0
SCALE_Y = SCREEN_HEIGHT / 1080.0

FOV = 600 * SCALE_Y
VIEWER_DISTANCE = 600 * SCALE_Y


def generate_palette():
    # 12 Colors x 2 Variants = 24 Base Hex Codes for realistic fireworks
    base_hexes = [
        0xFF0000,
        0xFF3333,  # Red (Strontium)
        0xFF7F00,
        0xFF9933,  # Orange (Calcium)
        0xFFD700,
        0xFFC000,  # Gold (Iron/Carbon)
        0xFFFF00,
        0xFFFF66,  # Yellow (Sodium)
        0x80FF00,
        0xA0FF33,  # Lime (Barium blend)
        0x00FF00,
        0x33FF33,  # Green (Barium)
        0x00FFFF,
        0x33FFFF,  # Cyan (Copper blend)
        0x0000FF,
        0x3333FF,  # Blue (Copper)
        0x4B0082,
        0x660099,  # Indigo
        0x9400D3,
        0xB233EE,  # Violet (Potassium/Rubidium)
        0xFF00FF,
        0xFF33FF,  # Magenta
        0xFF1493,
        0xFF66B2,  # Pink
    ]

    palette = [0x000000]  # Index 0: Black

    for base in base_hexes:
        r = (base >> 16) & 0xFF
        g = (base >> 8) & 0xFF
        b = base & 0xFF

        # 5 shades: 100%, 80%, 60%, 40%, 20% brightness
        for i in range(5):
            factor = 1.0 - (i * 0.20)
            nr = int(r * factor)
            ng = int(g * factor)
            nb = int(b * factor)
            palette.append((nr << 16) | (ng << 8) | nb)

    # 12 colors * 2 variants * 5 shades = 120 colors. +1 Black = 121.
    palette.append(0xFFFFFF)  # Index 121: Pure White
    palette.append(0xAAAAAA)  # Index 122: UI Light Gray
    palette.append(0x555555)  # Index 123: UI Dark Gray
    return palette


CUSTOM_PALETTE = generate_palette()

COLOR_MAP = {
    "red": 1,
    "orange": 11,
    "gold": 21,
    "yellow": 31,
    "lime": 41,
    "green": 51,
    "cyan": 61,
    "blue": 71,
    "indigo": 81,
    "violet": 91,
    "magenta": 101,
    "pink": 111,
    "silver": 121,
}
