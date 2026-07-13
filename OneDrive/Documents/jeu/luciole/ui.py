import pygame
import math
from constants import *


def get_font(size):
    return pygame.font.SysFont("consolas", size, bold=False)


def _fmt_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


# ── In-game HUD ───────────────────────────────────────────────────────────────

def draw_light_bar(surf, light_radius):
    ratio = max(0.0, (light_radius - LIGHT_MIN) / (LIGHT_MAX - LIGHT_MIN))
    bar_w, bar_h = 180, 14
    x, y = 20, 20

    pygame.draw.rect(surf, (30, 30, 50), (x, y, bar_w, bar_h), border_radius=6)

    fill_w = int(bar_w * ratio)
    if ratio > 0.5:
        color = (220, 200, 80)
    elif ratio > 0.25:
        color = (220, 120, 40)
    else:
        color = (200, 40, 40)
    if fill_w > 0:
        pygame.draw.rect(surf, color, (x, y, fill_w, bar_h), border_radius=6)

    pygame.draw.rect(surf, UI_TEXT, (x, y, bar_w, bar_h), 1, border_radius=6)
    surf.blit(get_font(12).render("LIGHT", True, UI_TEXT), (x, y - 16))


def draw_infection_bar(surf, infection_level):
    bar_w, bar_h = 180, 14
    x, y = 20, 52
    t = pygame.time.get_ticks() / 1000.0
    pulse = 0.5 + 0.5 * math.sin(t * 6)

    pygame.draw.rect(surf, (20, 40, 20), (x, y, bar_w, bar_h), border_radius=6)
    fill_w = int(bar_w * min(1.0, infection_level))
    if fill_w > 0:
        if infection_level > 0.75:
            r = int(60 + 80 * pulse)
            col = (r, 180, 30)
        else:
            col = (50, 160, 30)
        pygame.draw.rect(surf, col, (x, y, fill_w, bar_h), border_radius=6)
    pygame.draw.rect(surf, (80, 180, 60), (x, y, bar_w, bar_h), 1, border_radius=6)
    surf.blit(get_font(12).render("SPORES", True, (80, 180, 60)), (x, y - 16))


def draw_trapped_hud(surf, escapes_done, escapes_needed, trap_timer):
    """Pulsing prompt shown while the player is caught in a cobweb."""
    t     = pygame.time.get_ticks() / 1000.0
    pulse = 0.5 + 0.5 * math.sin(t * 10)

    # Progress dots
    dot_r   = 6
    spacing = 20
    total_w = escapes_needed * spacing
    ox      = WIDTH // 2 - total_w // 2
    oy      = HEIGHT // 2 + 96
    for i in range(escapes_needed):
        filled = i < escapes_done
        c = (220, 200, 80) if filled else (60, 55, 80)
        pygame.draw.circle(surf, c, (ox + i * spacing, oy), dot_r)
        pygame.draw.circle(surf, (150, 140, 100), (ox + i * spacing, oy), dot_r, 1)


def draw_survival_hud(surf, elapsed_seconds, decay_mult):
    """Top-right: survival time + current difficulty heat."""
    time_str = _fmt_time(elapsed_seconds)
    font_t = get_font(16)
    font_d = get_font(11)

    time_surf = font_t.render(time_str, True, UI_TEXT)
    surf.blit(time_surf, (WIDTH - time_surf.get_width() - 20, 20))

    # Difficulty bar (small, below timer)
    ratio = min(1.0, (decay_mult - 1.0) / (DIFF_MAX_MULT - 1.0))
    bw, bh = 80, 5
    bx = WIDTH - bw - 20
    by = 44
    pygame.draw.rect(surf, (30, 30, 50), (bx, by, bw, bh), border_radius=2)
    heat_col = (
        min(255, int(80  + 175 * ratio)),
        max(0,   int(120 - 100 * ratio)),
        max(0,   int(80  - 80  * ratio)),
    )
    if ratio > 0:
        pygame.draw.rect(surf, heat_col, (bx, by, int(bw * ratio), bh), border_radius=2)
    diff_label = font_d.render("DANGER", True, (100, 90, 130))
    surf.blit(diff_label, (bx, by - 13))


# ── Screens ───────────────────────────────────────────────────────────────────

def draw_start_screen(surf, selected=0):
    """
    selected: 0 = Play, 1 = Tutorial
    """
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 110))
    surf.blit(overlay, (0, 0))

    t  = pygame.time.get_ticks() / 1000
    cx = WIDTH // 2

    # Orbiting firefly dots
    for i in range(12):
        angle = t * 0.4 + i * (math.pi * 2 / 12)
        r     = 150 + math.sin(t + i) * 40
        fx    = cx + math.cos(angle) * r
        fy    = HEIGHT // 2 + math.sin(angle * 0.7) * r * 0.35
        alpha = int(180 + math.sin(t * 2 + i) * 60)
        s = pygame.Surface((16, 16), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 230, 120, alpha), (8, 8), 4)
        surf.blit(s, (fx - 8, fy - 8))

    # Title
    title_y = HEIGHT // 2 - 90
    surf.blit(get_font(54).render("LUCIOLE", True, (255, 240, 160)),
              get_font(54).render("LUCIOLE", True, (255, 240, 160))
              .get_rect(center=(cx, title_y)))
    surf.blit(get_font(17).render("a firefly in a dark forest", True, (160, 150, 200)),
              get_font(17).render("a firefly in a dark forest", True, (160, 150, 200))
              .get_rect(center=(cx, title_y + 52)))

    # Menu buttons
    ITEMS   = ["PLAY", "TUTORIAL", "SETTINGS", "QUIT"]
    btn_w   = 200
    btn_h   = 42
    btn_gap = 14
    total_h = len(ITEMS) * btn_h + (len(ITEMS)-1) * btn_gap
    btn_y0  = HEIGHT // 2 - 10

    for i, label in enumerate(ITEMS):
        bx   = cx - btn_w // 2
        by   = btn_y0 + i * (btn_h + btn_gap)
        sel  = (i == selected)
        pulse = 0.06 * math.sin(t * 3.5)

        # Button background
        bg_col  = (40, 36, 70) if sel else (18, 16, 35)
        brd_col = (180, 160, 255) if sel else (60, 55, 90)
        pygame.draw.rect(surf, bg_col,  (bx, by, btn_w, btn_h), border_radius=8)
        pygame.draw.rect(surf, brd_col, (bx, by, btn_w, btn_h), 2, border_radius=8)

        # Label
        if sel:
            r = min(255, int(255 * (1 + pulse)))
            g = min(255, int(235 * (1 + pulse)))
            b = min(255, int(120 * (1 + pulse)))
            txt_col = (r, g, b)
        else:
            txt_col = (130, 120, 170)

        lbl = get_font(20).render(label, True, txt_col)
        surf.blit(lbl, lbl.get_rect(center=(cx, by + btn_h // 2)))

        # Selection arrows
        if sel:
            arrow = get_font(20).render("›", True, txt_col)
            surf.blit(arrow, arrow.get_rect(center=(cx - 70, by + btn_h//2)))
            surf.blit(arrow, arrow.get_rect(center=(cx + 70, by + btn_h//2)))

    # Nav hint
    hint = get_font(11).render("↑ ↓  navigate     enter / space  confirm     esc  quit", True, (70, 65, 100))
    surf.blit(hint, hint.get_rect(center=(cx, btn_y0 + total_h + 30)))


def draw_game_over(surf, fade, survived_seconds, best_seconds, selected=0):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, int(200 * fade)))
    surf.blit(overlay, (0, 0))

    if fade < 0.5:
        return

    alpha = min(255, int(255 * (fade - 0.5) * 2))
    t     = pygame.time.get_ticks() / 1000.0

    def blended(font, text, color):
        s = font.render(text, True, color)
        s.set_alpha(alpha)
        return s

    cx = WIDTH // 2
    cy = HEIGHT // 2

    surf.blit(blended(get_font(46), "the light faded...", (160, 120, 200)),
              blended(get_font(46), "the light faded...", (160, 120, 200))
              .get_rect(center=(cx, cy - 88)))

    time_str = _fmt_time(survived_seconds)
    surf.blit(blended(get_font(22), f"survived  {time_str}", UI_TEXT),
              blended(get_font(22), f"survived  {time_str}", UI_TEXT)
              .get_rect(center=(cx, cy - 36)))

    best_str   = _fmt_time(best_seconds)
    best_col   = (255, 210, 80) if survived_seconds >= best_seconds else (100, 90, 130)
    best_label = "new best!" if survived_seconds >= best_seconds else f"best  {best_str}"
    surf.blit(blended(get_font(16), best_label, best_col),
              blended(get_font(16), best_label, best_col)
              .get_rect(center=(cx, cy - 4)))

    # ── Navigable buttons ──────────────────────────────────────────────────
    ITEMS   = ["TRY AGAIN", "MAIN MENU"]
    btn_w   = 210
    btn_h   = 40
    btn_gap = 14
    btn_y0  = cy + 30

    for i, label in enumerate(ITEMS):
        bx  = cx - btn_w // 2
        by  = btn_y0 + i * (btn_h + btn_gap)
        sel = (i == selected)

        pulse   = 0.06 * math.sin(t * 3.5) if sel else 0
        bg_col  = (40, 36, 70) if sel else (18, 16, 35)
        brd_col = (180, 160, 255) if sel else (60, 55, 90)

        btn_s = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
        btn_s.fill((*bg_col, alpha))
        surf.blit(btn_s, (bx, by))
        border_s = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
        pygame.draw.rect(border_s, (*brd_col, alpha), (0, 0, btn_w, btn_h), 2, border_radius=6)
        surf.blit(border_s, (bx, by))

        if sel:
            rc = min(255, int(255 * (1 + pulse)))
            gc = min(255, int(230 * (1 + pulse)))
            bc = min(255, int(110 * (1 + pulse)))
            txt_col = (rc, gc, bc)
            arrow = get_font(18).render("›", True, txt_col)
            arrow.set_alpha(alpha)
            surf.blit(arrow, arrow.get_rect(center=(cx - 70, by + btn_h // 2)))
            surf.blit(arrow, arrow.get_rect(center=(cx + 70, by + btn_h // 2)))
        else:
            txt_col = (110, 100, 150)

        lbl = get_font(18).render(label, True, txt_col)
        lbl.set_alpha(alpha)
        surf.blit(lbl, lbl.get_rect(center=(cx, by + btn_h // 2)))

    hint = get_font(11).render(
        "↑ ↓  navigate     enter  confirm     R  restart",
        True, (70, 65, 100))
    hint.set_alpha(alpha)
    surf.blit(hint, hint.get_rect(center=(cx, btn_y0 + 2 * btn_h + btn_gap + 22)))


def draw_pause_menu(surf, selected):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 155))
    surf.blit(overlay, (0, 0))

    frame_w, frame_h = 320, 230
    fx = (WIDTH  - frame_w) // 2
    fy = (HEIGHT - frame_h) // 2
    frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
    frame.fill((10, 12, 28, 200))
    surf.blit(frame, (fx, fy))
    pygame.draw.rect(surf, (80, 70, 120), (fx, fy, frame_w, frame_h), 1, border_radius=4)

    cx = WIDTH // 2
    t  = pygame.time.get_ticks() / 1000.0

    surf.blit(get_font(28).render("— paused —", True, (200, 190, 255)),
              get_font(28).render("— paused —", True, (200, 190, 255))
              .get_rect(center=(cx, fy + 36)))

    ITEMS = ["resume", "restart", "main menu"]
    item_y_start = fy + 90
    item_gap     = 44

    for i, label in enumerate(ITEMS):
        is_sel = (i == selected)
        if is_sel:
            pulse = 0.08 * math.sin(t * 4)
            color = (min(255, int(255 * (1 + pulse))),
                     min(255, int(230 * (1 + pulse))),
                     min(255, int(100 * (1 + pulse))))
            font_item = get_font(20)
            arrow = font_item.render("›", True, color)
            surf.blit(arrow, arrow.get_rect(center=(cx - 80, item_y_start + i * item_gap)))
            surf.blit(arrow, arrow.get_rect(center=(cx + 80, item_y_start + i * item_gap)))
        else:
            color = (120, 110, 160)
            font_item = get_font(20)

        txt = font_item.render(label, True, color)
        surf.blit(txt, txt.get_rect(center=(cx, item_y_start + i * item_gap)))

    surf.blit(get_font(11).render("↑ ↓  navigate     enter  confirm     p / esc  resume",
                                  True, (80, 75, 110)),
              get_font(11).render("↑ ↓  navigate     enter  confirm     p / esc  resume",
                                  True, (80, 75, 110))
              .get_rect(center=(cx, fy + frame_h - 18)))


def draw_settings_screen(surf, volume):
    """Settings overlay: volume slider controlled with ← →."""
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 140))
    surf.blit(overlay, (0, 0))

    cx = WIDTH  // 2
    cy = HEIGHT // 2
    t  = pygame.time.get_ticks() / 1000.0

    # Panel
    frame_w, frame_h = 400, 220
    fx = cx - frame_w // 2
    fy = cy - frame_h // 2
    frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
    frame.fill((10, 12, 28, 210))
    surf.blit(frame, (fx, fy))
    pygame.draw.rect(surf, (80, 70, 120), (fx, fy, frame_w, frame_h), 1, border_radius=4)

    # Title
    surf.blit(get_font(28).render("— settings —", True, (200, 190, 255)),
              get_font(28).render("— settings —", True, (200, 190, 255))
              .get_rect(center=(cx, fy + 36)))

    # Volume label + percentage
    pct_str  = f"{int(volume * 100)}%"
    vol_lbl  = get_font(16).render(f"VOLUME  {pct_str}", True, UI_TEXT)
    surf.blit(vol_lbl, vol_lbl.get_rect(center=(cx, fy + 85)))

    # Slider track
    bar_w, bar_h = 300, 16
    bx = cx - bar_w // 2
    by = fy + 108
    pygame.draw.rect(surf, (28, 28, 50), (bx, by, bar_w, bar_h), border_radius=7)
    fill_w = max(0, int(bar_w * volume))
    if fill_w > 0:
        fill_col = (
            min(255, int(80  + 175 * volume)),
            max(0,   int(160 - 80  * volume)),
            min(255, int(200 - 60  * volume)),
        )
        pygame.draw.rect(surf, fill_col, (bx, by, fill_w, bar_h), border_radius=7)
    pygame.draw.rect(surf, (90, 80, 135), (bx, by, bar_w, bar_h), 1, border_radius=7)

    # Knob
    knob_x = bx + fill_w
    pulse   = 0.5 + 0.5 * math.sin(t * 3.0)
    knob_r  = 10
    pygame.draw.circle(surf, (200, 190, 255), (knob_x, by + bar_h // 2), knob_r)
    pygame.draw.circle(surf, (min(255, int(140 + 60 * pulse)),
                               min(255, int(130 + 60 * pulse)),
                               255),
                       (knob_x, by + bar_h // 2), knob_r, 2)

    # Tick marks at 0 %, 25 %, 50 %, 75 %, 100 %
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        tx = bx + int(bar_w * frac)
        pygame.draw.line(surf, (55, 50, 85), (tx, by + bar_h + 3), (tx, by + bar_h + 8), 1)

    # Hint
    hint = get_font(11).render("← →  or  A D  adjust     space / esc  back", True, (80, 75, 110))
    surf.blit(hint, hint.get_rect(center=(cx, fy + frame_h - 20)))
