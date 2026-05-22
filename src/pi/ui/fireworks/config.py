SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080  # True 1080p
FULLSCREEN = True

# Scaled up for 1080p so the fireworks don't look tiny in the distance
FOV = 600
VIEWER_DISTANCE = 600


def generate_palette():
    # 7 Colors x 2 Variants = 14 Base Hex Codes
    base_hexes = [
        0xFF0000,
        0xFF3366,  # Red
        0xFF7F00,
        0xFFB266,  # Orange
        0xFFFF00,
        0xFFFF66,  # Yellow
        0x00FF00,
        0x66FF66,  # Green
        0x0000FF,
        0x6666FF,  # Blue
        0x4B0082,
        0x8A2BE2,  # Indigo
        0x9400D3,
        0xEE82EE,  # Violet
    ]

    palette = [0x000000]  # Index 0: Black

    for base in base_hexes:
        r = (base >> 16) & 0xFF
        g = (base >> 8) & 0xFF
        b = base & 0xFF

        for i in range(5):
            factor = 1.0 - (i * 0.20)
            nr = int(r * factor)
            ng = int(g * factor)
            nb = int(b * factor)
            palette.append((nr << 16) | (ng << 8) | nb)

    palette.append(0xFFFFFF)  # Index 71: Pure White/Silver
    return palette


CUSTOM_PALETTE = generate_palette()

COLOR_MAP = {
    "red": 1,
    "orange": 11,
    "yellow": 21,
    "green": 31,
    "blue": 41,
    "indigo": 51,
    "violet": 61,
    "silver": 71,
}
