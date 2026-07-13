"""
Procedural sound generation for Luciole.
All sounds are synthesised at startup from sine waves, noise and envelopes —
no external audio files are needed.

Call sounds.init() BEFORE pygame.init() so pre_init takes effect.
Then call sounds.load() once pygame is ready to build the Sound objects.
"""
import array
import math
import os
import random

import pygame

SR = 44100   # sample rate


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _make(frames, vol=1.0):
    """Convert a list of float samples [-1..1] to a stereo 16-bit pygame Sound."""
    buf = array.array('h')
    for f in frames:
        v = int(max(-1.0, min(1.0, f * vol)) * 32767)
        buf.append(v)   # left
        buf.append(v)   # right
    return pygame.mixer.Sound(buffer=buf.tobytes())


def _adsr(frames, a=0.01, d=0.05, sl=0.8, r=0.08):
    """Apply a simple ADSR envelope to a list of float samples."""
    n  = len(frames)
    an = int(a * SR);  dn = int(d * SR);  rn = int(r * SR)
    sn = max(0, n - an - dn - rn)
    out = []
    for i, f in enumerate(frames):
        if i < an:
            e = i / max(an, 1)
        elif i < an + dn:
            e = 1.0 - (1.0 - sl) * (i - an) / max(dn, 1)
        elif i < an + dn + sn:
            e = sl
        else:
            t = (i - an - dn - sn) / max(rn, 1)
            e = sl * max(0.0, 1.0 - t)
        out.append(f * e)
    return out


def _sine(freq, n):
    return [math.sin(2 * math.pi * freq * i / SR) for i in range(n)]


def _noise(n):
    return [random.uniform(-1.0, 1.0) for _ in range(n)]


def _mix(lists):
    """Sum multiple frame lists, no clipping (let _make handle that)."""
    n = max(len(l) for l in lists)
    out = [0.0] * n
    for lst in lists:
        for i, v in enumerate(lst):
            out[i] += v
    return out


# ── Sound factories ───────────────────────────────────────────────────────────

def _build_fly():
    """
    Gentle warm hum: 180 Hz fundamental (a low, soft tone) with a slow 8 Hz
    flutter envelope — sounds like a large insect gliding, not a grating buzz.
    Both 180 and 8 complete whole-number cycles in 1 s (integer Hz) so the
    1-second loop is click-free.
    """
    n = SR
    frames = []
    for i in range(n):
        t = i / SR
        # 8 Hz gentle flutter (slow enough to feel like wing-beats, not a buzz)
        flutter = 0.45 + 0.55 * ((math.sin(2 * math.pi * 8 * t) + 1) / 2) ** 1.8
        # Warm harmonic stack centred on 180 Hz
        s = (math.sin(2 * math.pi * 180 * t) * 0.55 +
             math.sin(2 * math.pi * 360 * t) * 0.22 +
             math.sin(2 * math.pi * 270 * t) * 0.12 +
             math.sin(2 * math.pi *  90 * t) * 0.11)
        frames.append(s * flutter * 0.13)
    return _make(frames, vol=1.0)


def _build_flower():
    """
    Ascending bell chime: C5 → E5 → G5 → C6, staggered 70 ms apart.
    Each note uses additive harmonics + exponential decay for a bell timbre.
    """
    total = int(0.55 * SR)
    out   = [0.0] * total
    notes = [(523.25, 0.00), (659.25, 0.07), (783.99, 0.14), (1046.50, 0.21)]
    for freq, t_start in notes:
        offset = int(t_start * SR)
        dur_n  = int(0.35 * SR)
        for i in range(dur_n):
            t = i / SR
            s = (math.sin(2*math.pi*freq*t)      * 0.70 +
                 math.sin(2*math.pi*freq*2*t)    * 0.18 +
                 math.sin(2*math.pi*freq*3*t)    * 0.08 +
                 math.sin(2*math.pi*freq*0.5*t)  * 0.04)
            env = math.exp(-t * 9.0)
            idx = offset + i
            if idx < total:
                out[idx] += s * env * 0.45
    return _make(out, vol=0.42)


def _build_hit_shadow():
    """
    Dark, low-frequency thud with filtered noise — like running into a shadow.
    Pitch drops rapidly from ~110 Hz to silence.
    """
    n = int(0.35 * SR)
    frames = []
    phase  = 0.0
    for i in range(n):
        t    = i / SR
        freq = 110.0 * math.exp(-t * 8.0)          # pitch drops fast
        phase += 2 * math.pi * freq / SR
        tone  = math.sin(phase)
        nz    = random.uniform(-1.0, 1.0) * 0.35
        env   = math.exp(-t * 11.0)
        frames.append((tone * 0.65 + nz) * env)
    return _make(_adsr(frames, a=0.002, d=0.08, sl=0.5, r=0.12), vol=0.45)


def _build_hit_wasp():
    """
    Sharp, buzzy sting: a rapid frequency sweep 700 → 200 Hz with a
    square-ish harmonic stack to give that wasp-like buzz.
    """
    n = int(0.22 * SR)
    frames = []
    phase  = 0.0
    for i in range(n):
        t    = i / SR
        freq = 700.0 * math.exp(-t * 12.0) + 200.0
        phase += 2 * math.pi * freq / SR
        # Odd harmonics → square-wave buzz
        s = (math.sin(phase)         * 0.5 +
             math.sin(phase * 3) * 0.25 +
             math.sin(phase * 5) * 0.15)
        nz  = random.uniform(-1.0, 1.0) * 0.15
        env = math.exp(-t * 16.0)
        frames.append((s + nz) * env)
    return _make(_adsr(frames, a=0.001, d=0.04, sl=0.6, r=0.08), vol=0.45)


def _build_wasp_buzz():
    """
    Harsh wasp BZZZ: ~200 Hz near-square wave (many odd harmonics) with a
    fast 35 Hz wing-beat amplitude modulation. Two slightly detuned oscillators
    (200 Hz + 203 Hz) create a natural beating. All integer Hz for a click-free
    1-second loop.
    """
    n = SR
    frames = []
    for i in range(n):
        t = i / SR
        # Near-square wave via many odd harmonics — very harsh, insect-like
        def sq(f):
            return (math.sin(2*math.pi*f*t)       * 1.00 +
                    math.sin(2*math.pi*f*3*t)      * 0.33 +
                    math.sin(2*math.pi*f*5*t)      * 0.20 +
                    math.sin(2*math.pi*f*7*t)      * 0.14 +
                    math.sin(2*math.pi*f*9*t)      * 0.11 +
                    math.sin(2*math.pi*f*11*t)     * 0.09)
        # Two detuned oscillators for natural beating
        s = sq(200) * 0.55 + sq(203) * 0.45
        # 35 Hz wing-beat AM — gives that rapid bzzz-bzzz pulse
        am = 0.35 + 0.65 * abs(math.sin(math.pi * 35 * t))
        frames.append(s * am * 0.55)
    return _make(frames, vol=1.0)


def _build_spore_hit():
    """Eerie organic puff — detuned drones + noise burst."""
    n = int(0.45 * SR)
    frames = []
    for i in range(n):
        t = i / SR
        # Three slightly detuned low drones → unsettling cluster
        s = (math.sin(2*math.pi*110*t) * 0.4 +
             math.sin(2*math.pi*113*t) * 0.35 +
             math.sin(2*math.pi*155*t) * 0.25)
        # Noise puff at attack
        nz = random.uniform(-1.0, 1.0) * math.exp(-t * 18.0) * 0.5
        env = math.exp(-t * 5.5)
        frames.append((s * env + nz) * 0.55)
    return _make(frames, vol=0.45)


def _build_droplet():
    """Clean water-drop ping — two descending sine tones."""
    n = int(0.30 * SR)
    out = [0.0] * n
    for freq, t_start in [(1800.0, 0.00), (1200.0, 0.06)]:
        offset = int(t_start * SR)
        dur_n  = int(0.22 * SR)
        for i in range(dur_n):
            t = i / SR
            s   = math.sin(2*math.pi*freq*t)
            env = math.exp(-t * 14.0)
            idx = offset + i
            if idx < n:
                out[idx] += s * env * 0.6
    return _make(out, vol=0.45)


def _build_menu_nav():
    """
    Tiny, soft ping — a quick sinc-like blip at ~700 Hz for cursor movement.
    """
    n = int(0.07 * SR)
    frames = _adsr(_sine(700, n), a=0.003, d=0.015, sl=0.4, r=0.04)
    return _make(frames, vol=0.40)


def _build_menu_confirm():
    """
    Pleasant two-note rising chime (A4 → E5) for confirming a selection.
    """
    total = int(0.28 * SR)
    out   = [0.0] * total
    for freq, t_start in [(440.0, 0.00), (659.25, 0.09)]:
        offset = int(t_start * SR)
        dur_n  = int(0.18 * SR)
        for i in range(dur_n):
            t = i / SR
            s = (math.sin(2*math.pi*freq*t)   * 0.70 +
                 math.sin(2*math.pi*freq*2*t) * 0.20 +
                 math.sin(2*math.pi*freq*3*t) * 0.10)
            env = math.exp(-t * 10.0)
            idx = offset + i
            if idx < total:
                out[idx] += s * env * 0.45
    return _make(out, vol=0.50)


def _build_menu_open():
    """
    Soft upward whoosh — used when opening the tutorial or pause menu.
    """
    n = int(0.20 * SR)
    frames = []
    phase  = 0.0
    for i in range(n):
        t    = i / SR
        freq = 300.0 + t * 800.0           # sweep up
        phase += 2 * math.pi * freq / SR
        s    = math.sin(phase) * 0.55
        nz   = random.uniform(-1.0, 1.0) * 0.10
        env  = math.exp(-t * 6.0) * (t / 0.02 if t < 0.02 else 1.0)
        frames.append((s + nz) * env)
    return _make(frames, vol=0.55)


# ── Manager ───────────────────────────────────────────────────────────────────

class _SoundManager:
    def __init__(self):
        pygame.mixer.set_num_channels(16)

        self._snd_fly        = _build_fly()
        self._snd_flower     = _build_flower()
        self._snd_shadow     = _build_hit_shadow()
        self._snd_wasp       = _build_hit_wasp()
        _buzz_path = os.path.join(os.path.dirname(__file__), 'wasp_buzz.mp3')
        if os.path.exists(_buzz_path):
            self._snd_wasp_buzz = pygame.mixer.Sound(_buzz_path)
        else:
            self._snd_wasp_buzz = _build_wasp_buzz()
        self._snd_nav        = _build_menu_nav()
        self._snd_confirm    = _build_menu_confirm()
        self._snd_open       = _build_menu_open()
        self._snd_spore      = _build_spore_hit()
        self._snd_droplet    = _build_droplet()

        def _load(name):
            p = os.path.join(os.path.dirname(__file__), name)
            return pygame.mixer.Sound(p) if os.path.exists(p) else None

        self._snd_spider_walk   = _load('spider_walk.mp3')
        self._snd_spider_attack = _load('spider_attack.mp3')

        # Channel 0: player wing flutter loop
        self._fly_ch   = pygame.mixer.Channel(0)
        self._fly_vol  = 0.0
        # Channel 1: ambient wasp buzz loop
        self._wasp_ch  = pygame.mixer.Channel(1)
        self._wasp_vol = 0.0
        # Channel 2: spider walk loop
        self._spider_ch      = pygame.mixer.Channel(2)
        self._spider_walking = False

        self._master_vol = 1.0

    # ── Per-frame call ────────────────────────────────────────────────────────
    def update_fly(self, player):
        """Smoothly fade the wing buzz in/out with player speed."""
        speed  = math.hypot(player.vel_x, player.vel_y)
        target = min(1.0, speed / 2.5) * 0.28
        self._fly_vol += (target - self._fly_vol) * 0.08

        if self._fly_vol > 0.005:
            if not self._fly_ch.get_busy():
                self._fly_ch.play(self._snd_fly, loops=-1)
            self._fly_ch.set_volume(self._fly_vol * self._master_vol)
        else:
            if self._fly_ch.get_busy():
                self._fly_ch.fadeout(80)

    def stop_fly(self):
        self._fly_ch.stop()
        self._fly_vol = 0.0

    # ── Master volume ─────────────────────────────────────────────────────
    def set_master_volume(self, vol):
        self._master_vol = max(0.0, min(1.0, vol))
        mv = self._master_vol
        self._snd_flower.set_volume(mv)
        self._snd_shadow.set_volume(mv)
        self._snd_wasp.set_volume(mv)
        self._snd_nav.set_volume(mv)
        self._snd_confirm.set_volume(mv)
        self._snd_open.set_volume(mv)
        self._snd_spore.set_volume(mv)
        self._snd_droplet.set_volume(mv)
        # Looping sounds (_snd_fly, _snd_wasp_buzz) are volume-controlled via
        # their channel in update_fly / update_wasp_buzz — don't touch them here
        # or master volume gets applied twice (Sound.vol × Channel.vol).

    # ── Wasp ambient buzz ─────────────────────────────────────────────────
    def update_wasp_buzz(self, proximity):
        """
        Fade wasp drone based on proximity (0.0 = no wasps / far, 1.0 = very close).
        Level.py passes the closest-wasp proximity factor.
        """
        target = proximity * 0.72
        self._wasp_vol += (target - self._wasp_vol) * 0.05

        if self._wasp_vol > 0.005:
            if not self._wasp_ch.get_busy():
                self._wasp_ch.play(self._snd_wasp_buzz, loops=-1)
            self._wasp_ch.set_volume(min(1.0, self._wasp_vol * self._master_vol))
        else:
            if self._wasp_ch.get_busy():
                self._wasp_ch.fadeout(200)

    def stop_wasp_buzz(self):
        self._wasp_ch.stop()
        self._wasp_vol = 0.0

    # ── Spider sounds ─────────────────────────────────────────────────────
    def start_spider_walk(self):
        if self._snd_spider_walk and not self._spider_walking:
            self._spider_walking = True
            self._spider_ch.play(self._snd_spider_walk, loops=-1)
            self._spider_ch.set_volume(0.85 * self._master_vol)

    def stop_spider_walk(self):
        if self._spider_walking:
            self._spider_walking = False
            self._spider_ch.fadeout(200)

    def play_spider_attack(self):
        if self._snd_spider_attack:
            self._snd_spider_attack.set_volume(self._master_vol)
            self._snd_spider_attack.play()

    # ── One-shots ─────────────────────────────────────────────────────────────
    def play_spore(self):
        self._snd_spore.play()

    def play_droplet(self):
        self._snd_droplet.play()

    def play_flower(self):
        self._snd_flower.play()

    def play_hit_shadow(self):
        self._snd_shadow.play()

    def play_hit_wasp(self):
        self._snd_wasp.play()

    def play_menu_nav(self):
        self._snd_nav.play()

    def play_menu_confirm(self):
        self._snd_confirm.play()

    def play_menu_open(self):
        self._snd_open.play()


# ── Singleton access ──────────────────────────────────────────────────────────

_instance: _SoundManager | None = None


def init():
    """Call before pygame.init() to configure the mixer."""
    pygame.mixer.pre_init(SR, -16, 2, 512)


def load():
    """Call after pygame.init() to build all Sound objects."""
    global _instance
    _instance = _SoundManager()


def get() -> _SoundManager:
    return _instance
