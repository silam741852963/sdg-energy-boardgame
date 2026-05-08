from enum import Enum


class GeneratorType(Enum):
    WIND = "Wind Turbine"
    SOLAR = "Solar Panel"
    PIEZO = "Piezoelectric"
    COIL = "Coil Pipe"


CLEANBOOST_MACS = {
    "AA:BB:CC:DD:EE:01": GeneratorType.WIND,
    "AA:BB:CC:DD:EE:02": GeneratorType.SOLAR,
    "AA:BB:CC:DD:EE:03": GeneratorType.PIEZO,
    "AA:BB:CC:DD:EE:04": GeneratorType.COIL,
}

# Game Settings
MAX_ENERGY_GAUGE = 100.0  # Total energy needed to complete the task
ENERGY_PER_BEACON = 2.5  # How much gauge fills per CleanBoost signal
UI_REFRESH_RATE = 0.1  # UI updates 10 times a second
