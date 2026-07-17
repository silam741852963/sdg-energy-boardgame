#!/usr/bin/env python3
"""Generate deterministic, original firework WAV effects used by the game."""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path


RATE = 44_100
PEAK = 0.86
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "resource" / "audio"


def noise(count: int, rng: random.Random) -> list[float]:
    return [rng.uniform(-1.0, 1.0) for _ in range(count)]


def lowpass(samples: list[float], cutoff: float) -> list[float]:
    alpha = 1.0 - math.exp(-2.0 * math.pi * cutoff / RATE)
    value = 0.0
    result = []
    for sample in samples:
        value += alpha * (sample - value)
        result.append(value)
    return result


def highpass(samples: list[float], cutoff: float) -> list[float]:
    lows = lowpass(samples, cutoff)
    return [sample - low for sample, low in zip(samples, lows)]


def add_echo(samples: list[float], delay: float, gain: float) -> None:
    offset = int(delay * RATE)
    for index in range(offset, len(samples)):
        samples[index] += samples[index - offset] * gain


def normalize(samples: list[float]) -> list[float]:
    edge = min(int(0.008 * RATE), len(samples) // 2)
    for index in range(edge):
        fade = index / edge
        samples[index] *= fade
        samples[-index - 1] *= fade
    maximum = max(abs(sample) for sample in samples) or 1.0
    scale = PEAK / maximum
    return [max(-1.0, min(1.0, sample * scale)) for sample in samples]


def write_wav(name: str, samples: list[float]) -> None:
    path = OUTPUT_DIR / name
    pcm = struct.pack(f"<{len(samples)}h", *(round(s * 32767) for s in normalize(samples)))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(pcm)


def blast(rng: random.Random, large: bool, far: bool, variant: int) -> list[float]:
    duration = (2.75 if large else 1.75) + (0.45 if far else 0.0)
    count = int(duration * RATE)
    raw = noise(count, rng)
    body = lowpass(raw, 1200.0 if far else (2700.0 if large else 3600.0))
    rumble = lowpass(raw, 90.0 if large else 135.0)
    samples = []
    phase = 0.0
    base = (36.0 if large else 57.0) * (0.90, 1.0, 1.12)[variant]
    for index in range(count):
        t = index / RATE
        attack = 1.0 - math.exp(-(42.0 if far else 180.0) * t)
        decay = math.exp(-(1.65 if large else 2.75) * t)
        phase += 2.0 * math.pi * base * (1.0 - 0.2 * min(t, 1.0)) / RATE
        crack = body[index] * math.exp(-(8.5 + variant * 1.7) * t) * 1.35
        low = (0.92 * rumble[index] + 0.38 * math.sin(phase)) * decay
        samples.append(attack * (crack + low))
    add_echo(
        samples,
        (0.13 if far else 0.075) + variant * 0.013,
        0.28 if far else 0.20,
    )
    add_echo(samples, (0.29 if far else 0.17) + variant * 0.018, 0.17)
    add_echo(samples, (0.48 if far else 0.34) + variant * 0.021, 0.11)
    add_echo(samples, (0.72 if far else 0.56) + variant * 0.024, 0.065)
    return samples


def twinkle(rng: random.Random, far: bool, variant: int) -> list[float]:
    duration = (1.18 + variant * 0.12) + (0.16 if far else 0.0)
    count = int(duration * RATE)
    samples = [0.0] * count
    burst = blast(rng, large=False, far=far, variant=variant)
    for index, sample in enumerate(burst[:count]):
        samples[index] += sample * 0.38
    pop_count = (22, 29, 36)[variant]
    cluster_centers = [0.12, 0.30, 0.53, 0.78]
    for pop_index in range(pop_count):
        center = cluster_centers[pop_index % len(cluster_centers)]
        start_time = max(0.05, center + rng.gauss(0.0, 0.10 + 0.025 * variant))
        start = min(count - 1, int(start_time * RATE))
        length = min(int(rng.uniform(0.045, 0.12) * RATE), count - start)
        pop_noise = lowpass(noise(length, rng), rng.uniform(760.0, 2000.0))
        pop_frequency = rng.uniform(90.0, 205.0)
        phase = rng.uniform(0.0, 2.0 * math.pi)
        gain = rng.uniform(0.20, 0.48) * math.exp(-0.28 * start_time)
        decay = rng.uniform(32.0, 58.0)
        for offset in range(length):
            t = offset / RATE
            envelope = math.exp(-decay * t)
            thump = math.sin(phase + 2.0 * math.pi * pop_frequency * t)
            samples[start + offset] += gain * envelope * (1.2 * pop_noise[offset] + 0.45 * thump)
    add_echo(samples, 0.055 + variant * 0.009, 0.12)
    return lowpass(samples, 3800.0 if far else 6400.0)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generators = {}
    families = {
        "Firework_blast": lambda rng, variant: blast(rng, False, False, variant),
        "Firework_blast_far": lambda rng, variant: blast(rng, False, True, variant),
        "Firework_large_blast": lambda rng, variant: blast(rng, True, False, variant),
        "Firework_large_blast_far": lambda rng, variant: blast(rng, True, True, variant),
        "Firework_twinkle": lambda rng, variant: twinkle(rng, False, variant),
        "Firework_twinkle_far": lambda rng, variant: twinkle(rng, True, variant),
    }
    for stem, generator in families.items():
        for variant in range(3):
            suffix = "" if variant == 0 else f"_{variant + 1}"
            generators[f"{stem}{suffix}.wav"] = (
                lambda rng, generator=generator, variant=variant: generator(rng, variant)
            )
    for seed, (name, generator) in enumerate(generators.items(), start=7_001):
        write_wav(name, generator(random.Random(seed)))
        print(f"generated {name}")


if __name__ == "__main__":
    main()
