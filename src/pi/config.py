from enum import Enum


class GeneratorType(Enum):
    WIND = "Wind Turbine"
    SOLAR = "Solar Panel"
    PIEZO = "Piezoelectric"
    COIL = "Coil Pipe"


CLEANBOOST_MACS = {
    "D9:44:B0:92:D4:E0": GeneratorType.WIND,  # Label: 03-02860, Minor: 2860
    "EA:32:68:B2:7F:C1": GeneratorType.SOLAR,  # Label: 03-02728, Minor: 2728
    "FC:19:F9:E9:EE:7D": GeneratorType.PIEZO,  # Label: 03-02859, Minor: 2859
    "F7:7D:0B:41:39:A8": GeneratorType.COIL,  # Label: 03-02526, Minor: 2526
}

# Game Settings
MAX_ENERGY_GAUGE = 100.0  # Total energy needed to complete the task
ENERGY_PER_BEACON = 4.25  # How much gauge fills per CleanBoost signal (scaled by 1.7 for 1.7x faster filling)
UI_REFRESH_RATE = 0.5  # UI updates 2 times a second

CLEANBOOST_TEST_MODE = True

# Energy fill amount per beacon per generator type in test mode (scaled for custom generator rates)
ENERGY_PER_BEACON_BY_TYPE = {
    GeneratorType.WIND: 6.8,
    GeneratorType.SOLAR: 10,
    GeneratorType.PIEZO: 5.1,
    GeneratorType.COIL: 5.1,
}
