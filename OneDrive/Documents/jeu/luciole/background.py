"""
Pixel art night forest background with three parallax layers.
Everything is baked into surfaces at init time; drawing is just blits.
"""
import math
import random
import pygame
from constants import WIDTH, HEIGHT

# ── Palette ───────────────────────────────────────────────────────────────────
SKY_TOP      = (4,   4,  16)
SKY_BOT      = (10,  6,  28)
STAR_C       = (200, 215, 255)
MOON_C       = (218, 212, 178)
MOON_SHADE   = (175, 170, 138)

TREE_FAR     = (38,  44,  72)
TREE_MID     = (28,  62,  40)
TREE_NEAR    = (20,  44,  26)
GROUND_FAR   = (28,  40,  28)
GROUND_MID   = (20,  35,  22)
GROUND_NEAR  = (14,  28,  16)
GRASS_NEAR   = (20,  42,  22)

PX = 3   # pixel art block size — one "pixel" = 3×3 screen pixels


def _snap(v):
    return int(v // PX) * PX


def _px_circle(surf, color, cx, cy, r):
    """Draw a filled circle in PX-sized blocks (pixel art look)."""
    for dy in range(-r, r + 1, PX):
        for dx in range(-r, r + 1, PX):
            if dx * dx + dy * dy <= r * r:
                pygame.draw.rect(surf, color, (_snap(cx + dx), _snap(cy + dy), PX, PX))


def _draw_pine(surf, x, y, h, base_color):
    """
    Blocky pixel art pine/fir tree.
    x, y  — base centre (ground level)
    h     — total height in pixels
    """
    x = _snap(x)
    trunk_h = max(PX * 2, _snap(h // 5))
    trunk_w = PX * 2
    trunk_col = tuple(max(0, c - 12) for c in base_color)

    # Trunk
    pygame.draw.rect(surf, trunk_col,
                     (x - trunk_w // 2, y - trunk_h, trunk_w, trunk_h))

    # Canopy — 4 stacked triangular layers
    crown_h = h - trunk_h
    n = 4
    for i in range(n):
        t = i / max(n - 1, 1)                     # 0 at top layer, 1 at bottom
        lw = _snap(int((0.25 + 0.75 * t) * h * 0.52))
        lw = max(PX * 3, lw)
        lh = _snap(crown_h // n) + PX
        ly = (y - trunk_h) - (n - i) * _snap(crown_h // n)
        shade = tuple(min(255, c + i * 3) for c in base_color)
        pygame.draw.rect(surf, shade, (x - lw // 2, ly, lw, lh))

        # Highlight on top edge (one px row, lighter)
        hi = tuple(min(255, c + 8) for c in shade)
        pygame.draw.rect(surf, hi, (x - lw // 2, ly, lw, PX))


def _build_sky():
    surf = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / HEIGHT
        col = tuple(int(SKY_TOP[i] + (SKY_BOT[i] - SKY_TOP[i]) * t) for i in range(3))
        pygame.draw.line(surf, col, (0, y), (WIDTH - 1, y))
    return surf


def _build_moon(r):
    size = (r + PX) * 2 + PX * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    _px_circle(surf, MOON_C, c, c, r)
    # Craters
    for cdx, cdy, cr in [(-r // 3, -r // 4, r // 5),
                          ( r // 4,  r // 3, r // 7),
                          (-r // 6,  r // 5, r // 9)]:
        _px_circle(surf, MOON_SHADE, c + cdx, c + cdy, max(PX, cr))
    # Soft outer glow (one semi-transparent ring)
    glow = pygame.Surface((size + PX * 4, size + PX * 4), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*MOON_C, 18),
                       (glow.get_width() // 2, glow.get_height() // 2), r + PX * 2)
    return surf, glow


# ── Layer spec ────────────────────────────────────────────────────────────────
# (parallax_x, tree_col, ground_col, tree_h_range, trees_per_screen, ground_y_frac)
_LAYER_SPECS = [
    (0.06, TREE_FAR,  GROUND_FAR,  (24, 44),  22, 0.80),
    (0.18, TREE_MID,  GROUND_MID,  (44, 72),  15, 0.87),
    (0.40, TREE_NEAR, GROUND_NEAR, (64, 98),  10, 0.93),
]


class Background:
    def __init__(self, seed=0):
        rng = random.Random(seed)
        LAYER_W = WIDTH * 8   # wide enough for any level + parallax scroll

        self._sky  = _build_sky()
        self._moon, self._moon_glow = _build_moon(18)
        self._moon_x = int(WIDTH * 0.74)
        self._moon_y = int(HEIGHT * 0.17)

        # Stars: (x in 0..WIDTH*4, y, half-size 1|2, base_brightness)
        self._stars = [
            (rng.randint(0, WIDTH * 4),
             rng.randint(0, int(HEIGHT * 0.72)),
             rng.choice([1, 1, 1, 2]),
             rng.uniform(0.45, 1.0))
            for _ in range(220)
        ]

        # Pre-render parallax layers
        self._layers = []
        for px_f, tcol, gcol, (th_min, th_max), cps, gy_frac in _LAYER_SPECS:
            surf = pygame.Surface((LAYER_W, HEIGHT), pygame.SRCALPHA)
            ground_y = _snap(int(HEIGHT * gy_frac))

            # Ground fill (extra +PX to eliminate any sub-pixel gap at bottom edge)
            pygame.draw.rect(surf, gcol, (0, ground_y, LAYER_W, HEIGHT - ground_y + PX))

            # Bumpy top edge
            for gx in range(0, LAYER_W, PX * 5):
                bump = rng.randint(0, PX * 4)
                pygame.draw.rect(surf, gcol, (gx, ground_y - bump, PX * 5, bump + PX))

            # Grass tufts (near/mid layers)
            if gy_frac > 0.85:
                for gx in range(0, LAYER_W, PX * 5):
                    if rng.random() < 0.45:
                        gh = rng.randint(PX, PX * 4)
                        gc = tuple(min(255, c + 10) for c in gcol)
                        pygame.draw.rect(surf, gc, (_snap(gx), ground_y - gh, PX * 2, gh))
                        # Second blade offset
                        if rng.random() < 0.5:
                            pygame.draw.rect(surf, gc,
                                             (_snap(gx) + PX * 2, ground_y - gh + PX,
                                              PX * 2, gh - PX))

            # Trees
            total = cps * (LAYER_W // WIDTH)
            xs = sorted(rng.randint(PX * 3, LAYER_W - PX * 3) for _ in range(total))
            for tx in xs:
                th = _snap(rng.randint(th_min, th_max))
                _draw_pine(surf, tx, ground_y, th, tcol)

            self._layers.append((surf, px_f, LAYER_W))

        # Mist strip baked once (slightly richer: two-tone blue-green gradient)
        self._mist = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        mist_y = int(HEIGHT * 0.75)
        for y in range(mist_y, HEIGHT):
            frac = (y - mist_y) / (HEIGHT - mist_y)
            a = int(28 * frac)
            col = (int(14 + 8 * frac), int(22 + 10 * frac), int(32 + 8 * frac), a)
            pygame.draw.line(self._mist, col, (0, y), (WIDTH - 1, y))

        # Ambient background fireflies (slow drifting dots — drawn each frame)
        rng2 = random.Random(seed + 99)
        self._ambient = [
            {
                'x':     rng2.uniform(0, WIDTH),
                'y':     rng2.uniform(HEIGHT * 0.20, HEIGHT * 0.85),
                'vx':    rng2.uniform(-0.18, 0.18),
                'vy':    rng2.uniform(-0.10, -0.04),  # drift slowly upward
                'phase': rng2.uniform(0, math.pi * 2),
                'bri':   rng2.uniform(0.4, 0.9),
            }
            for _ in range(18)
        ]

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf, camera_x, camera_y):
        surf.blit(self._sky, (0, 0))

        t = pygame.time.get_ticks() / 1000.0

        # Stars — drawn as PX-sized blocks, twinkle via color brightness
        for sx, sy, sr, bri in self._stars:
            tw = bri * (0.72 + 0.28 * math.sin(t * 1.3 + sx * 0.07))
            c  = int(tw * 200)
            col = (min(255, c + 15), min(255, c + 25), min(255, c + 70))
            ox  = int(sx - camera_x * 0.012) % WIDTH
            size = PX * sr
            pygame.draw.rect(surf, col, (ox, sy, size, size))
            # Cross sparkle on bright stars
            if bri > 0.8:
                pygame.draw.rect(surf, col, (ox - PX, sy + size // 2 - 1, size + PX * 2, 2))
                pygame.draw.rect(surf, col, (ox + size // 2 - 1, sy - PX, 2, size + PX * 2))

        # Moon
        mx = (self._moon_x - int(camera_x * 0.018)) % (WIDTH + 80) - 40
        my = self._moon_y
        mgw = self._moon_glow.get_width()
        surf.blit(self._moon_glow, (mx - mgw // 2, my - mgw // 2))
        mw = self._moon.get_width()
        surf.blit(self._moon, (mx - mw // 2, my - mw // 2))

        # Parallax tree layers (each is two blits for seamless wrap)
        for layer_surf, px_f, layer_w in self._layers:
            scroll = int(camera_x * px_f) % layer_w
            surf.blit(layer_surf, (-scroll, 0))
            if scroll > 0:
                surf.blit(layer_surf, (layer_w - scroll, 0))

        # Atmospheric mist
        surf.blit(self._mist, (0, 0))

        # Ambient background fireflies — distant, very dim, drift upward
        for p in self._ambient:
            p['x'] = (p['x'] + p['vx']) % WIDTH
            p['y'] += p['vy']
            if p['y'] < HEIGHT * 0.10:
                p['y'] = HEIGHT * 0.88
            glow_val = p['bri'] * (0.55 + 0.45 * math.sin(t * 1.8 + p['phase']))
            a = int(glow_val * 55)   # very faint — clearly background
            if a < 4:
                continue
            gs = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(gs, (200, 240, 100, a // 3), (5, 5), 4)
            pygame.draw.circle(gs, (220, 250, 140, a),      (5, 5), 1)
            surf.blit(gs, (int(p['x']) - 5, int(p['y']) - 5))
