# Audio assets

`Space_ambient_airy.ogg` is the looped space ambience used by the attract,
charging, launch, and return presentation. It is **Airy** by SRG774 from the
[Dark Sci-Fi Audio Pack](https://opengameart.org/content/dark-sci-fi-audio-pack).
It is dedicated to the public domain under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The original
loopable MP3 was converted to Ogg Vorbis for reliable offline playback.

The `Firework_*.wav` files provide near/far blast, large-blast, and twinkle
roles. Each role has three prerecorded variants; the firework audio system
chooses among them during playback.

Interface, generator selection/removal, fill, rocket, return, and cockpit sounds
are synthesized once by `AudioSystem` at application startup. The cockpit set
includes the Earth-approach zoom, power failure, looping alarm, target lock, and
impact cues. These generated effects are not stored as resource files.
