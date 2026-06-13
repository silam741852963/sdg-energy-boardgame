def generate_rgb_palette():
    # 12 Colors x 2 Variants = 24 Base Hex Codes for realistic fireworks
    base_hexes = [
        0xFF0000, 0xFF3333,  # Red (Strontium)
        0xFF7F00, 0xFF9933,  # Orange (Calcium)
        0xFFD700, 0xFFC000,  # Gold (Iron/Carbon)
        0xFFFF00, 0xFFFF66,  # Yellow (Sodium)
        0x80FF00, 0xA0FF33,  # Lime (Barium blend)
        0x00FF00, 0x33FF33,  # Green (Barium)
        0x00FFFF, 0x33FFFF,  # Cyan (Copper blend)
        0x0000FF, 0x3333FF,  # Blue (Copper)
        0x4B0082, 0x660099,  # Indigo
        0x9400D3, 0xB233EE,  # Violet (Potassium/Rubidium)
        0xFF00FF, 0xFF33FF,  # Magenta
        0xFF1493, 0xFF66B2,  # Pink
    ]

    palette = [(0.0, 0.0, 0.0)]  # Index 0: Black

    for base in base_hexes:
        r = ((base >> 16) & 0xFF) / 255.0
        g = ((base >> 8) & 0xFF) / 255.0
        b = (base & 0xFF) / 255.0

        # 5 shades: 100%, 80%, 60%, 40%, 20% brightness
        for i in range(5):
            factor = 1.0 - (i * 0.20)
            palette.append((r * factor, g * factor, b * factor))

    palette.append((1.0, 1.0, 1.0))  # Index 121: Pure White
    palette.append((170.0 / 255.0, 170.0 / 255.0, 170.0 / 255.0))  # Index 122: UI Light Gray (0xAAAAAA)
    palette.append((85.0 / 255.0, 85.0 / 255.0, 85.0 / 255.0))      # Index 123: UI Dark Gray (0x555555)
    return palette

RGB_PALETTE = generate_rgb_palette()

def get_color(index) -> tuple[float, float, float]:
    if 0 <= index < len(RGB_PALETTE):
        return RGB_PALETTE[index]
    return (1.0, 1.0, 1.0) # Default to white
