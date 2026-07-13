"""
Tutorial slides — all drawn procedurally with pygame.
Each slide: illustration panel (top ~58%) + text panel (bottom ~42%).
"""
import math
import random
import pygame
from constants import (WIDTH, HEIGHT, LIGHT_MAX, LIGHT_MIN,
                       FLOWER_PINK, FLOWER_TEAL, ENEMY_BODY, ENEMY_EYE,
                       UI_TEXT, DASH_DURATION)

# ── Palette ───────────────────────────────────────────────────────────────────
PANEL_DARK = (5,   5,  15)
BORDER_COL = (55,  50,  95)
TITLE_COL  = (255, 240, 160)
BODY_COL   = (190, 185, 220)
DIM_COL    = (110, 105, 145)
KEY_FACE   = (52,  52,  78)
KEY_TOP    = (76,  76, 108)
KEY_BOT    = (26,  26,  40)
KEY_BORDER = (95,  95, 135)
KEY_TEXT   = (210, 210, 235)

SLIDE_COUNT = 6

# Seeded RNG for background elements (stable across frames)
_BG_RNG_STARS = random.Random(73)
_BG_STARS = [
    (_BG_RNG_STARS.randint(0, WIDTH - 1),
     _BG_RNG_STARS.randint(0, int(HEIGHT * 0.55)),
     _BG_RNG_STARS.uniform(0.25, 0.90))
    for _ in range(55)
]
_BG_RNG_TREES = random.Random(17)
_BG_TREES = [
    (_BG_RNG_TREES.randint(0, WIDTH - 1),
     _BG_RNG_TREES.randint(28, 72),
     _BG_RNG_TREES.randint(14, 30),
     (_BG_RNG_TREES.randint(9, 16),
      _BG_RNG_TREES.randint(13, 20),
      _BG_RNG_TREES.randint(8, 13)))
    for _ in range(44)
]


def _font(size):
    return pygame.font.SysFont("consolas", size, bold=False)


def _blit_c(surf, src, cx, cy):
    surf.blit(src, src.get_rect(center=(cx, cy)))


# ── Keyboard key ─────────────────────────────────────────────────────────────
def _key(surf, x, y, label, w=38, h=34, pressed=False, color=None):
    col = color if color else ((72, 72, 102) if pressed else KEY_FACE)
    pygame.draw.rect(surf, col,        (x, y, w, h),         border_radius=5)
    pygame.draw.rect(surf, KEY_TOP,    (x+2, y+2, w-4, 5),   border_radius=3)
    pygame.draw.rect(surf, KEY_BOT,    (x+2, y+h-5, w-4, 5), border_radius=3)
    pygame.draw.rect(surf, KEY_BORDER, (x, y, w, h), 1,      border_radius=5)
    lbl = _font(13).render(label, True, KEY_TEXT)
    surf.blit(lbl, lbl.get_rect(center=(x + w//2, y + h//2)))


# ── Atmospheric illustration background ──────────────────────────────────────
def _ill_bg(surf, ill_h, t):
    """Draw the dark starry forest background for the illustration panel."""
    # Gradient sky
    for y in range(ill_h):
        frac = y / ill_h
        r = int(5  + 9 * frac)
        g = int(4  + 7 * frac)
        b = int(18 + 14 * frac)
        pygame.draw.line(surf, (r, g, b), (0, y), (WIDTH - 1, y))

    # Twinkling stars
    for sx, sy, bri in _BG_STARS:
        tw  = bri * (0.68 + 0.32 * math.sin(t * 1.3 + sx * 0.05))
        c   = int(tw * 150)
        col = (min(255, c+14), min(255, c+24), min(255, c+65))
        pygame.draw.rect(surf, col, (sx, sy, 2, 2))
        if bri > 0.75:
            pygame.draw.rect(surf, col, (sx-1, sy, 4, 1))
            pygame.draw.rect(surf, col, (sx, sy-1, 1, 4))

    # Horizon tree silhouettes
    horizon_y = int(ill_h * 0.76)
    pygame.draw.rect(surf, (10, 16, 8), (0, horizon_y, WIDTH, ill_h - horizon_y))
    for tx, th, tw, tcol in _BG_TREES:
        pygame.draw.rect(surf, tcol, (tx - tw//2, horizon_y - th, tw, th))

    # Mist strip
    for y in range(horizon_y, ill_h):
        a = int(18 * (y - horizon_y) / max(1, ill_h - horizon_y))
        ms = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
        ms.fill((14, 22, 30, a))
        surf.blit(ms, (0, y))


# ── Light helpers ─────────────────────────────────────────────────────────────
def _light_circle(surf, cx, cy, radius, alpha_base=185):
    """Radial darkness cutout matching the in-game lighting."""
    dark = pygame.Surface((WIDTH, int(surf.get_height())), pygame.SRCALPHA)
    dark.fill((3, 5, 18, alpha_base))
    r = int(radius)
    for i in range(r, 0, -1):
        ratio = i / r
        a = int(alpha_base * ratio ** 2.2)
        pygame.draw.circle(dark, (3, 5, 18, a), (cx, cy), i)
    surf.blit(dark, (0, 0))


def _light_bar_mini(surf, x, y, w, ratio, label=""):
    h = 12
    pygame.draw.rect(surf, (22, 22, 42), (x, y, w, h), border_radius=5)
    fw = max(0, int(w * ratio))
    col = (220, 200, 80) if ratio > 0.5 else (220, 120, 40) if ratio > 0.25 else (200, 40, 40)
    if fw > 0:
        pygame.draw.rect(surf, col, (x, y, fw, h), border_radius=5)
    pygame.draw.rect(surf, (75, 70, 115), (x, y, w, h), 1, border_radius=5)
    if label:
        surf.blit(_font(11).render(label, True, DIM_COL), (x, y - 15))


# ── Entity helpers ────────────────────────────────────────────────────────────
def _firefly_dot(surf, cx, cy, r=7, dash_phase=0.0):
    """Compact firefly glow dot with optional dash streak."""
    # Outer soft halo
    for i in range(4):
        a   = max(0, 55 - i*13)
        rad = r + i*4
        s   = pygame.Surface((rad*2+2, rad*2+2), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 225, 90, a), (rad+1, rad+1), rad)
        surf.blit(s, (cx - rad-1, cy - rad-1))
    # Core
    pygame.draw.circle(surf, (255, 235, 140), (cx, cy), r)
    pygame.draw.circle(surf, (255, 255, 215), (cx, cy), max(2, r//3))
    # Dash streak overlay
    if dash_phase > 0:
        fade = dash_phase / DASH_DURATION
        for i in range(1, 5):
            sx = cx - i * 7
            sa = max(0, int(190 * fade) - i * 40)
            if sa <= 0:
                break
            rs = max(1, r - i)
            ss = pygame.Surface((rs*2+2, rs*2+2), pygame.SRCALPHA)
            pygame.draw.circle(ss, (255, 255, 180, sa), (rs+1, rs+1), rs)
            surf.blit(ss, (sx - rs-1, cy - rs-1))


def _flower(surf, cx, cy, t=0.0):
    """Flower matching the updated in-game design (with stem & leaves)."""
    lerp   = (math.sin(t) + 1) / 2
    r = int(FLOWER_PINK[0]*lerp + FLOWER_TEAL[0]*(1-lerp))
    g = int(FLOWER_PINK[1]*lerp + FLOWER_TEAL[1]*(1-lerp))
    b = int(FLOWER_PINK[2]*lerp + FLOWER_TEAL[2]*(1-lerp))
    radius = 5 + math.sin(t*2)*1.0

    # Layered glow
    glow = pygame.Surface((36, 36), pygame.SRCALPHA)
    gc   = 18
    for gr, ga in [(int(radius+9), 16), (int(radius+5), 26), (int(radius+2), 36)]:
        pygame.draw.circle(glow, (r, g, b, ga), (gc, gc), gr)
    pygame.draw.circle(glow, (255, 240, 180, 20), (gc, gc), int(radius+2))
    surf.blit(glow, (cx-gc, cy-gc))

    # Stem + leaf nubs
    pygame.draw.line(surf, (30, 65, 28), (cx, cy+5), (cx, cy+12), 2)
    pygame.draw.line(surf, (40, 80, 34), (cx, cy+8), (cx+4, cy+7), 2)
    pygame.draw.line(surf, (40, 80, 34), (cx, cy+10), (cx-4, cy+9), 2)

    # 6 petal pixel blocks
    pr = int(radius)
    for i in range(6):
        angle = t*0.3 + i*(math.pi/3)
        px = cx + math.cos(angle)*pr
        py = cy + math.sin(angle)*pr
        pygame.draw.rect(surf, (r, g, b), (int(px)-1, int(py)-1, 3, 3))
        pygame.draw.rect(surf, (min(255,r+40), min(255,g+40), min(255,b+40)),
                         (int(px)-1, int(py)-1, 2, 2))

    # Center
    pygame.draw.rect(surf, (255, 255, 210), (cx-2, cy-2, 5, 5))
    pygame.draw.rect(surf, (255, 255, 255), (cx-1, cy-1, 3, 3))


def _shadow_enemy(surf, cx, cy, t=0.0):
    """Shadow creature with tendrils."""
    wobble = math.sin(t*2)*2

    # Tendrils
    ts = pygame.Surface((60, 60), pygame.SRCALPHA)
    tc = (30, 30)
    for ti in range(5):
        base_a = t*0.5 + ti*(math.pi*2/5)
        wag    = math.sin(t*2.8 + ti*1.1)*0.36
        l1     = 9  + math.sin(t + ti)*2
        l2     = l1 + 6 + math.sin(t*1.5 + ti)*2
        ma     = base_a + wag
        ta2    = ma + math.sin(t*3.5 + ti*0.7)*0.28
        mx = int(tc[0] + math.cos(ma)*l1)
        my = int(tc[1] + math.sin(ma)*l1)
        tx2 = int(tc[0] + math.cos(ta2)*l2)
        ty2 = int(tc[1] + math.sin(ta2)*l2)
        pygame.draw.line(ts, (*ENEMY_BODY, 95), tc, (mx, my), 2)
        pygame.draw.line(ts, (*ENEMY_BODY, 55), (mx, my), (tx2, ty2), 1)
        pygame.draw.circle(ts, (55, 18, 72, 50), (tx2, ty2), 2)
    surf.blit(ts, (cx-30, cy-30+int(wobble)))

    # Body
    body = pygame.Surface((44, 44), pygame.SRCALPHA)
    for i in range(5):
        a = 200 - i*36
        pygame.draw.ellipse(body, (*ENEMY_BODY, a),
                            (3+i, 3+i+int(wobble), 38-i*2, 32-i*2))
    pygame.draw.ellipse(body, (38, 18, 52, 75), (12, 11, 20, 18))
    surf.blit(body, (cx-22, cy-22))

    # Eyes
    ey = cy - 5 + int(wobble)
    for ex in (cx-6, cx+6):
        eg = pygame.Surface((14, 14), pygame.SRCALPHA)
        pygame.draw.circle(eg, (175, 18, 18, 65), (7, 7), 6)
        surf.blit(eg, (ex-7, ey-7))
        pygame.draw.circle(surf, ENEMY_EYE,    (ex, ey), 3)
        pygame.draw.circle(surf, (255, 65, 65), (ex, ey), 2)
        pygame.draw.circle(surf, (255, 120, 80),(ex, ey), 1)


def _wasp(surf, cx, cy, t=0.0):
    """Detailed wasp matching the in-game entity."""
    bob = math.sin(t*5)*1.5
    by  = cy + int(bob)
    f   = 1  # always facing right in tutorial

    # Legs
    LC = (28, 18, 4)
    for bx_off, udx, udy, ldx, ldy in [
            (f*6, f*-4, 4, f*-6, 9), (f*2, f*-1, 6, f*-1, 11),
            (f*-3, f*2, 5, f*4, 9), (f*-7, f*4, 4, f*6, 8)]:
        ax, ay = cx+bx_off, by+4
        k  = (int(ax+udx), int(ay+udy))
        t2 = (int(ax+ldx), int(ay+ldy))
        pygame.draw.line(surf, LC, (int(ax), int(ay)), k, 1)
        pygame.draw.line(surf, LC, k, t2, 1)

    # Wings
    ws = pygame.Surface((66, 50), pygame.SRCALPHA)
    wc = (33, 25)
    flap = math.sin(t*9)*0.72
    for side, ba in [(-1, -math.pi/2+flap), (-1, -math.pi/2+flap+0.48),
                     ( 1,  math.pi/2-flap), ( 1,  math.pi/2-flap-0.48)]:
        length = 16
        ang = ba
        ex  = wc[0] + math.cos(ang)*length*f*side
        ey  = wc[1] + math.sin(ang)*length
        mx, my = (wc[0]+ex)/2, (wc[1]+ey)/2
        pts = []
        for k in range(14):
            a  = k*math.pi*2/14
            px = mx + math.cos(a)*(length/2)*math.cos(ang) - math.sin(a)*5*math.sin(ang)
            py = my + math.cos(a)*(length/2)*math.sin(ang) + math.sin(a)*5*math.cos(ang)
            pts.append((px, py))
        pygame.draw.polygon(ws, (235, 190, 95, 48), pts)
        pygame.draw.polygon(ws, (200, 150, 50, 80), pts, 1)
        pygame.draw.line(ws, (220, 165, 55, 38), wc, (int(ex), int(ey)), 1)
    surf.blit(ws, (cx-33, cy-25+int(bob)))

    # Abdomen
    for si in range(5):
        frac  = si / 4.0
        sw    = int(11 - frac*5)
        sh    = 7
        sx    = int(cx - f*(si*4+1))
        scol  = (215, 155, 18) if si%2==0 else (20, 14, 4)
        hcol  = (240, 185, 45) if si%2==0 else (36, 26, 8)
        pygame.draw.rect(surf, scol, (sx-sw//2, by-sh//2, sw, sh))
        pygame.draw.rect(surf, hcol, (sx-sw//2, by-sh//2, sw, 2))
        if si%2==0:
            for fi in range(-sw//2+1, sw//2, 3):
                pygame.draw.line(surf, (175, 115, 12),
                                 (sx+fi, by+sh//2), (sx+fi, by+sh//2+2+(fi%2)), 1)

    # Thorax
    pygame.draw.circle(surf, (48, 36, 8),  (int(cx+f*2), by-1), 6)
    pygame.draw.circle(surf, (68, 52, 14), (int(cx+f*2), by-2), 4)

    # Head
    hx = cx + f*14
    pygame.draw.circle(surf, (46, 34, 6), (int(hx), by-1), 5)
    # Antennae
    abx = int(hx + f*3)
    pygame.draw.line(surf, (36, 26, 5), (abx, by-5), (int(abx+f*5), by-11), 1)
    pygame.draw.line(surf, (36, 26, 5), (int(abx+f*5), by-11), (int(abx+f*3), by-15), 1)
    # Compound eyes
    for edy, edx in ((-3, -2), (1, 1)):
        ex2 = int(hx + edx*f)
        ey2 = by + edy
        eg  = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.circle(eg, (80, 200, 40, 38), (5, 5), 5)
        surf.blit(eg, (ex2-5, ey2-5))
        pygame.draw.circle(surf, (50, 150, 25), (ex2, ey2), 3)
        pygame.draw.circle(surf, (90, 220, 55), (ex2, ey2), 2)
    # Mandibles
    for mdy in (+3, -4):
        pygame.draw.line(surf, (28, 18, 4),
                         (int(hx+f*4), by+mdy//2),
                         (int(hx+f*10), by+mdy), 2)
    # Stinger
    pygame.draw.line(surf, (38, 26, 6),
                     (int(cx-f*18), by), (int(cx-f*22), by), 2)
    pygame.draw.line(surf, (22, 14, 3),
                     (int(cx-f*22), by), (int(cx-f*26), by), 1)
    sg = pygame.Surface((10, 10), pygame.SRCALPHA)
    pygame.draw.circle(sg, (210, 40, 10, 55), (5, 5), 5)
    surf.blit(sg, (int(cx-f*26)-5, by-5))
    pygame.draw.circle(surf, (230, 55, 20), (int(cx-f*26), by), 2)


# ── Slide chrome ─────────────────────────────────────────────────────────────
def _draw_frame(surf, slide_idx):
    t     = pygame.time.get_ticks() / 1000.0
    ill_h = int(HEIGHT * 0.58)

    # Full-screen dark base
    surf.fill(PANEL_DARK)

    # Atmospheric illustration panel
    _ill_bg(surf, ill_h, t)

    # Divider
    pygame.draw.line(surf, BORDER_COL, (0, ill_h), (WIDTH, ill_h), 1)
    # Subtle top vignette
    vign = pygame.Surface((WIDTH, 28), pygame.SRCALPHA)
    for vy in range(28):
        a = int(60 * (1 - vy/28))
        pygame.draw.line(vign, (0, 0, 10, a), (0, vy), (WIDTH-1, vy))
    surf.blit(vign, (0, 0))

    # Slide counter dots
    dot_y  = HEIGHT - 22
    gap    = 18
    start_x = WIDTH//2 - (SLIDE_COUNT-1)*gap//2
    for i in range(SLIDE_COUNT):
        col = (200, 190, 255) if i == slide_idx else (50, 46, 76)
        pygame.draw.circle(surf, col, (start_x + i*gap, dot_y),
                           4 if i == slide_idx else 3)

    # Nav arrows
    ac = (85, 80, 125)
    if slide_idx > 0:
        pygame.draw.polygon(surf, ac,
                            [(28, HEIGHT//2), (46, HEIGHT//2-14), (46, HEIGHT//2+14)])
    if slide_idx < SLIDE_COUNT - 1:
        pygame.draw.polygon(surf, ac,
                            [(WIDTH-28, HEIGHT//2), (WIDTH-46, HEIGHT//2-14),
                             (WIDTH-46, HEIGHT//2+14)])

    return ill_h, t


def _text_panel(surf, ill_h, title, lines):
    margin = 24
    y = ill_h + 12
    _blit_c(surf, _font(21).render(title, True, TITLE_COL), WIDTH//2, y + 13)
    y += 34
    for line in lines:
        lbl = _font(13).render(line, True, BODY_COL)
        _blit_c(surf, lbl, WIDTH//2, y)
        y += 20


# ══════════════════════════════════════════════════════════════════════════════
# Individual slides
# ══════════════════════════════════════════════════════════════════════════════

def _slide_controls(surf, ill_h, t):
    cx = WIDTH // 2
    iy = ill_h // 2 - 10

    # ── WASD cluster ──────────────────────────────────────────────────────
    kx, ky = cx - 255, iy - 58
    ks = 42
    _key(surf, kx+ks,   ky,    "W")
    _key(surf, kx,      ky+ks, "A")
    _key(surf, kx+ks,   ky+ks, "S")
    _key(surf, kx+ks*2, ky+ks, "D")
    _blit_c(surf, _font(11).render("WASD", True, DIM_COL),
            kx + ks + 19, ky + ks*2 + 22)

    # OR divider
    _blit_c(surf, _font(17).render("/", True, (75, 70, 108)), cx - 90, iy + 4)

    # ── Arrow keys ────────────────────────────────────────────────────────
    ax, ay = cx - 42, iy - 58
    _key(surf, ax+ks,   ay,    "↑")
    _key(surf, ax,      ay+ks, "←")
    _key(surf, ax+ks,   ay+ks, "↓")
    _key(surf, ax+ks*2, ay+ks, "→")
    _blit_c(surf, _font(11).render("ARROWS", True, DIM_COL),
            ax + ks + 19, ay + ks*2 + 22)

    # ── SHIFT key (dash) — highlighted in gold ────────────────────────────
    shift_x = cx + 110
    shift_y = iy - 20
    dash_pulse = 0.5 + 0.5*math.sin(t * 3.0)
    sr = int(255 * (0.7 + 0.3*dash_pulse))
    sg = int(200 * (0.7 + 0.3*dash_pulse))
    shift_border_col = (sr, sg, 30)
    _key(surf, shift_x, shift_y, "SHIFT", w=72, h=34, color=(38, 34, 58))
    # Glow border on top of key
    pygame.draw.rect(surf, shift_border_col, (shift_x, shift_y, 72, 34), 2, border_radius=5)
    lbl_dash = _font(11).render("DASH", True, (sr, sg, 60))
    surf.blit(lbl_dash, lbl_dash.get_rect(center=(shift_x+36, shift_y+48)))

    # ── P / ESC keys ──────────────────────────────────────────────────────
    _key(surf, cx + 110, iy + 26, "P",   w=34, h=30)
    _key(surf, cx + 152, iy + 26, "ESC", w=50, h=30)
    _blit_c(surf, _font(11).render("pause", True, DIM_COL), cx+127, iy+68)
    _blit_c(surf, _font(11).render("quit",  True, DIM_COL), cx+177, iy+68)

    # ── Animated firefly: moves, then dashes ─────────────────────────────
    phase   = t * 0.9
    fly_x   = cx - 70 + int(math.sin(phase) * 80)
    fly_y   = iy + 85
    # Dash streak fires once per cycle when nearing the right side
    dash_ph = max(0, math.sin(phase) * DASH_DURATION)
    _firefly_dot(surf, fly_x, fly_y, r=6, dash_phase=dash_ph)

    # Direction arrow
    dx_dir = math.cos(phase) * 80
    if abs(dx_dir) > 5:
        arrow_col = (160, 200, 255)
        sign = 1 if dx_dir > 0 else -1
        ax2 = fly_x + sign * 22
        pygame.draw.polygon(surf, arrow_col,
                            [(ax2, fly_y),
                             (ax2 - sign*8, fly_y-5),
                             (ax2 - sign*8, fly_y+5)])

    _text_panel(surf, ill_h, "CONTROLS",
                ["WASD  or  ARROW KEYS  to fly in any direction",
                 "SHIFT  to dash — burst of speed + brief invincibility",
                 "P  pauses the game            ESC  quits"])


def _slide_light(surf, ill_h, t):
    cx, cy = WIDTH//2, ill_h//2 - 5

    radius = 75 + int(math.sin(t * 0.65) * 22)

    # Background already drawn by _ill_bg; now punch light circle
    _light_circle(surf, cx, cy, radius, alpha_base=188)

    # Firefly at centre
    _firefly_dot(surf, cx, cy, r=7)

    # Light bar
    ratio = 0.28 + 0.42 * ((math.sin(t*0.65)+1)/2)
    _light_bar_mini(surf, cx-90, cy + radius + 12, 180, ratio, "LIGHT")

    # Animated caption
    if math.sin(t * 0.65) < 0:
        cap_col  = (210, 80, 80)
        caption  = "slowly shrinking..."
    else:
        cap_col  = (80, 210, 100)
        caption  = "flower collected — restored!"
    _blit_c(surf, _font(13).render(caption, True, cap_col),
            cx, cy + radius + 38)

    # Annotate radius with a dim line
    end_x = cx + int(radius * 0.72)
    pygame.draw.line(surf, (100, 90, 140), (cx, cy), (end_x, cy), 1)
    ann = _font(11).render("light radius", True, (100, 90, 140))
    surf.blit(ann, (end_x + 4, cy - 8))

    _text_panel(surf, ill_h, "YOUR LIGHT",
                ["The glowing ring around you is your life bar",
                 "It shrinks continuously — faster as time passes",
                 "Reach zero and the darkness takes you forever"])


def _slide_flowers(surf, ill_h, t):
    cx, cy = WIDTH//2, ill_h//2 - 10

    # Before bar (low)
    _light_bar_mini(surf, cx-200, cy-12, 120, 0.24, "before")

    # Central flower
    _flower(surf, cx, cy, t)

    # After bar (fuller)
    _light_bar_mini(surf, cx+82,  cy-12, 120, 0.62, "after")

    # Arrows flanking the flower
    for dx in [-1, 1]:
        base = cx + dx * 55
        pygame.draw.polygon(surf, (220, 200, 80),
                            [(base, cy), (base-dx*14, cy-8), (base-dx*14, cy+8)])

    # Floating +LIGHT label
    pl = _font(16).render("+LIGHT", True, (190, 240, 150))
    _blit_c(surf, pl, cx, cy - 52 + int(math.sin(t*2)*5))

    # Scattered background flowers (fewer = rarer feel)
    for i, (fx, fy) in enumerate([(cx-170, cy+30), (cx+150, cy+30),
                                   (cx-85,  cy-58), (cx+80,  cy-58)]):
        _flower(surf, fx, fy, t + i*1.2)

    # Firefly drifting toward the nearest flower
    path_t = (t * 0.5) % 1.0
    ffx = int(cx - 130 + path_t * 100)
    ffy = cy + 30 - int(path_t * 20)
    _firefly_dot(surf, ffx, ffy, r=5)

    _text_panel(surf, ill_h, "GLOWING FLOWERS",
                ["Rare glowing flowers are scattered across the forest",
                 "Flying into one instantly restores a burst of light",
                 "Explore widely — they are worth seeking out"])


def _slide_shadows(surf, ill_h, t):
    cx, cy = WIDTH//2, ill_h//2 - 10

    # Player light in centre
    _light_circle(surf, cx, cy, 62, alpha_base=195)
    _firefly_dot(surf, cx, cy, r=8)

    # Enemies converging
    positions = [(-210, -25), (195, -45), (-160, 58), (185, 65), (5, -88)]
    for i, (dx, dy) in enumerate(positions):
        ex = cx + dx + int(math.sin(t*0.8 + i)*5)
        ey = cy + dy + int(math.cos(t*0.7 + i)*4)
        _shadow_enemy(surf, ex, ey, t + i*0.5)
        # Arrow toward player
        ddx, ddy = cx - ex, cy - ey
        dist = math.hypot(ddx, ddy) or 1
        ax2  = ex + (ddx/dist)*22
        ay2  = ey + (ddy/dist)*22
        pygame.draw.line(surf, (90, 16, 16), (ex, ey), (int(ax2), int(ay2)), 1)
        ah = 6
        perpx, perpy = -ddy/dist*ah, ddx/dist*ah
        pygame.draw.polygon(surf, (120, 22, 22),
                            [(int(ax2), int(ay2)),
                             (int(ax2 - ddx/dist*8 + perpx),
                              int(ay2 - ddy/dist*8 + perpy)),
                             (int(ax2 - ddx/dist*8 - perpx),
                              int(ay2 - ddy/dist*8 - perpy))])

    # Hit flash
    if int(t*2) % 5 == 0:
        flash = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(flash, (255, 55, 55, 75), (12, 12), 12)
        surf.blit(flash, (cx-12, cy-12))

    _text_panel(surf, ill_h, "SHADOW CREATURES",
                ["Dark beings that home toward your light",
                 "Contact drains your light — brief invincibility after each hit",
                 "Use SHIFT to dash through them — they grow more numerous over time"])


def _slide_wasps(surf, ill_h, t):
    cx, cy = WIDTH//2, ill_h//2 - 12

    # Light bar at 42% — below threshold
    bar_w = 280
    bar_x = cx - bar_w//2
    bar_y = cy - 72
    _light_bar_mini(surf, bar_x, bar_y, bar_w, 0.42)

    # 50% threshold line
    th_x = bar_x + int(bar_w * 0.50)
    pygame.draw.line(surf, (220, 70, 70), (th_x, bar_y-7), (th_x, bar_y+19), 2)
    mk = _font(11).render("50%", True, (220, 70, 70))
    surf.blit(mk, (th_x - mk.get_width()//2, bar_y - 21))

    # Wasps circling / approaching
    wasp_data = [(1, cy+8), (-1, cy-12), (1, cy+44)]
    for i, (side, base_y) in enumerate(wasp_data):
        wax = cx + side*(115 - int(math.sin(t*1.2 + i*1.1)*28))
        way = base_y + int(math.cos(t*1.5 + i)*10)
        _wasp(surf, wax, way, t + i*0.8)

    # Player
    _light_circle(surf, cx, cy+8, 46, alpha_base=195)
    _firefly_dot(surf, cx, cy+8, r=7)

    # Red warning pulse
    wa = max(0, int(85 * math.sin(t*3)))
    if wa > 0:
        ws = pygame.Surface((WIDTH, ill_h), pygame.SRCALPHA)
        ws.fill((75, 0, 0, wa // 7))
        surf.blit(ws, (0, 0))

    _text_panel(surf, ill_h, "WASPS",
                ["When your light drops below 50%, wasps emerge",
                 "Faster than shadows — they fly directly and sting hard",
                 "Dash through them to escape, and restore light to stop spawning"])


def _slide_difficulty(surf, ill_h, t):
    cx, cy = WIDTH//2, ill_h//2 - 8

    # Timeline
    lx0, lx1 = cx-195, cx+195
    ly       = cy + 28
    pygame.draw.line(surf, (55, 50, 88), (lx0, ly), (lx1, ly), 2)

    ticks = [("0:00", 0.0), ("1:00", 0.33), ("2:00", 0.66), ("3:00+", 1.0)]
    for label, frac in ticks:
        tx = int(lx0 + (lx1-lx0)*frac)
        pygame.draw.line(surf, (75, 70, 118), (tx, ly-5), (tx, ly+5), 2)
        surf.blit(_font(11).render(label, True, DIM_COL),
                  _font(11).render(label, True, DIM_COL).get_rect(center=(tx, ly+18)))

    # Animated heat bar along timeline
    progress = min(1.0, (math.sin(t*0.42)+1)/2)
    bar_top  = cy - 58
    bar_w_px = int((lx1-lx0) * progress)
    for i in range(bar_w_px):
        frac = i / (lx1-lx0)
        r2 = min(255, int(78  + 177*frac))
        g2 = max(0,   int(118 - 102*frac))
        b2 = max(0,   int(78  -  78*frac))
        pygame.draw.line(surf, (r2, g2, b2),
                         (lx0+i, bar_top), (lx0+i, ly-3))

    dl = _font(13).render("DANGER LEVEL", True, (165, 78, 78))
    _blit_c(surf, dl, cx, bar_top - 13)

    # Shrinking fireflies (fast decay = smaller size)
    for i, (fx, fy, fr) in enumerate([(cx-160, cy-52, 9), (cx-55, cy-44, 7),
                                       (cx+55,  cy-36, 5), (cx+158, cy-24, 3)]):
        _firefly_dot(surf, fx, fy + int(math.sin(t+i)*4), fr)
        lbl = _font(10).render(f"×{i+1}", True, (120, 115, 155))
        surf.blit(lbl, lbl.get_rect(center=(fx, fy+fr+12)))

    # Decay speed arrow
    arr_pts = [(cx-182, cy+48), (cx-60, cy+42), (cx+62, cy+34), (cx+182, cy+22)]
    pygame.draw.lines(surf, (195, 75, 75), False, arr_pts, 2)
    ah = arr_pts[-1]
    pygame.draw.polygon(surf, (195, 75, 75),
                        [(ah[0]+8, ah[1]),
                         (ah[0]-4, ah[1]-6),
                         (ah[0]-4, ah[1]+6)])
    _blit_c(surf, _font(11).render("light fades faster  →", True, (195, 75, 75)),
            cx, cy+62)

    _text_panel(surf, ill_h, "SURVIVAL",
                ["The longer you survive, the faster your light fades",
                 "Watch the  DANGER  bar in the top-right corner",
                 "Dash to flowers, dodge enemies, outlast the darkness"])


# ── Public entry point ────────────────────────────────────────────────────────
_SLIDES = [_slide_controls, _slide_light, _slide_flowers,
           _slide_shadows, _slide_wasps, _slide_difficulty]
_TITLES = ["Controls", "Your Light", "Flowers", "Shadows", "Wasps", "Survival"]


def draw_tutorial(surf, slide_idx):
    ill_h, t = _draw_frame(surf, slide_idx)
    _SLIDES[slide_idx](surf, ill_h, t)

    # Top breadcrumb
    if slide_idx == 0:
        crumb = f"  {_TITLES[slide_idx]}  →  "
    elif slide_idx == SLIDE_COUNT - 1:
        crumb = f"  ←  {_TITLES[slide_idx]}  "
    else:
        crumb = f"  ←  {_TITLES[slide_idx]}  →  "
    _blit_c(surf, _font(12).render(crumb, True, DIM_COL), WIDTH//2, 14)

    hint = _font(11).render("← →  or  A D  navigate      SPACE / ESC  back to menu",
                            True, (62, 58, 92))
    _blit_c(surf, hint, WIDTH//2, HEIGHT - 40)
