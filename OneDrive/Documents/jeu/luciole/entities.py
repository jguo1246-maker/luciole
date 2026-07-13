import pygame
import math
import random
from constants import *


# ── Shared draw helpers ───────────────────────────────────────────────────────

def _px_rect(surf, color, x, y, w, h):
    pygame.draw.rect(surf, color, (int(x), int(y), w, h))


def _glow_circle(surf, cx, cy, color, radius, alpha, layers=4):
    """Multi-layer soft glow blitted onto surf."""
    size = int(radius * 2 + layers * 6) + 4
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    sc = size // 2
    for i in range(layers):
        r = int(radius + (layers - i) * 3)
        a = max(0, alpha // layers - i * (alpha // layers // 2))
        pygame.draw.circle(s, (*color, a), (sc, sc), r)
    surf.blit(s, (int(cx) - sc, int(cy) - sc))


class Player(pygame.sprite.Sprite):
    HITBOX_W = 14
    HITBOX_H = 10

    def __init__(self, x, y):
        super().__init__()
        self.rect = pygame.Rect(x, y, self.HITBOX_W, self.HITBOX_H)
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.light_radius = float(LIGHT_MAX)
        self.alive = True
        self.facing = 1
        self.invincible = 0

        self.wing_t  = 0.0
        self.pulse_t = 0.0
        self.bob_t   = 0.0

        self.trail = []

        # Dash state
        self.dash_cooldown = 0
        self.dash_active   = 0
        self.dash_dir      = (1.0, 0.0)

        # Cobweb trap
        self.web_escapes_needed = 0   # set randomly when trapped; 0 = free
        self.web_escapes_done   = 0
        self._shift_prev        = False  # edge detection for escape dashes
        self.web_trap_timer     = 0   # counts down; hits 0 → spider spawns

        # Spore infection
        self.infected         = False
        self.infection_level  = 0.0   # 0.0 → 1.0; fills while infected

    @property
    def center(self):
        return self.rect.centerx, self.rect.centery

    @property
    def is_trapped(self):
        return self.web_escapes_done < self.web_escapes_needed

    def handle_input(self, keys):
        shift_now = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        if self.is_trapped:
            # Only allow escape attempts while the countdown is still running
            if self.web_trap_timer > 0 and shift_now and not self._shift_prev:
                self.web_escapes_done += 1  # no light cost while escaping web
            self._shift_prev = shift_now
            return  # no movement while trapped

        self._shift_prev = shift_now
        dx = dy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= 1
            self.facing = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1
            self.facing = 1
        if keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_z] or keys[pygame.K_SPACE]:
            dy -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += 1

        # Normalize so diagonal speed equals cardinal speed
        mag = math.hypot(dx, dy)
        if mag > 0:
            accel = FLY_ACCEL * (0.75 if self.infected else 1.0)
            self.vel_x += (dx / mag) * accel
            self.vel_y += (dy / mag) * accel

        if (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and self.dash_cooldown == 0:
            if dx != 0 or dy != 0:
                # Player is pressing a direction — dash that way
                dmag = math.hypot(dx, dy)
                ddx, ddy = dx / dmag, dy / dmag
            else:
                # No input — dash horizontally in the direction the player faces
                ddx, ddy = float(self.facing), 0.0
            self.dash_dir      = (ddx, ddy)
            self.dash_cooldown = DASH_COOLDOWN
            self.dash_active   = DASH_DURATION
            self.invincible    = DASH_IFRAMES
            self.light_radius  = max(LIGHT_MIN, self.light_radius - LIGHT_MAX * DASH_COST)

    def _move_and_collide(self, platforms):
        self.rect.x += int(self.vel_x)
        for p in platforms:
            if self.rect.colliderect(p):
                if self.vel_x > 0:
                    self.rect.right = p.left
                else:
                    self.rect.left = p.right
                self.vel_x *= -0.25

        self.rect.y += int(self.vel_y)
        for p in platforms:
            if self.rect.colliderect(p):
                if self.vel_y > 0:
                    self.rect.bottom = p.top
                else:
                    self.rect.top = p.bottom
                self.vel_y *= -0.25

    def update(self, platforms, decay_mult):
        if self.dash_active > 0:
            # During dash: override velocity with sustained direction each frame
            self.vel_x = self.dash_dir[0] * DASH_SPEED
            self.vel_y = self.dash_dir[1] * DASH_SPEED
        else:
            self.vel_y += FLY_GRAVITY
            self.vel_x *= FLY_DRAG
            self.vel_y *= FLY_DRAG
            self.vel_x = max(-FLY_MAX, min(FLY_MAX, self.vel_x))
            self.vel_y = max(-FLY_MAX, min(FLY_MAX, self.vel_y))

        self.trail.append((self.rect.centerx, self.rect.centery))
        if len(self.trail) > 6:
            self.trail.pop(0)

        self._move_and_collide(platforms)

        self.light_radius -= LIGHT_DECAY * decay_mult
        self.light_radius = max(LIGHT_MIN, self.light_radius)

        if self.invincible > 0:
            self.invincible -= 1
        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1
        if self.dash_active > 0:
            self.dash_active -= 1

        # Infection level: fills over ~25 seconds when infected
        if self.infected:
            self.infection_level = min(1.0, self.infection_level + 1 / (25 * 60))
        if self.is_trapped:
            self.vel_x *= 0.7
            self.vel_y *= 0.7
            if self.web_trap_timer > 0:
                self.web_trap_timer -= 1

        if self.light_radius <= LIGHT_MIN + 0.1:
            self.alive = False

        speed = math.hypot(self.vel_x, self.vel_y)
        self.wing_t  += 0.18 + speed * 0.04
        self.pulse_t += 0.05
        self.bob_t   += 0.03

    def take_damage(self):
        if self.invincible > 0:
            return False
        self.light_radius -= DAMAGE_DRAIN
        self.invincible = 90
        return True

    def collect_flower(self):
        self.light_radius = min(self.light_radius + LIGHT_RESTORE, LIGHT_MAX)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, surf, camera_offset):
        ox, oy = camera_offset
        cx = self.rect.centerx - ox
        cy = self.rect.centery - oy

        # During dash, only skip the blink if dash just started
        if self.invincible > 0 and self.dash_active == 0 and (self.invincible // 4) % 2 == 1:
            return

        bob = math.sin(self.bob_t) * 1.5

        # ── Dash streak (drawn first, behind everything) ──────────────────
        if self.dash_active > 0:
            fade = self.dash_active / DASH_DURATION
            for i in range(1, 7):
                sx = cx + int(self.dash_dir[0] * (-i * 7))
                sy = cy + int(self.dash_dir[1] * (-i * 7)) + int(bob)
                sa = max(0, int(200 * fade) - i * 32)
                if sa <= 0:
                    break
                r_s = max(1, 6 - i)
                streak = pygame.Surface((r_s * 2 + 2, r_s * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(streak, (255, 255, 180, sa),
                                   (r_s + 1, r_s + 1), r_s)
                surf.blit(streak, (sx - r_s - 1, sy - r_s - 1))

        # ── Glow trail ────────────────────────────────────────────────────
        for i, (tx, ty) in enumerate(self.trail):
            alpha = int(25 * (i / len(self.trail)))
            r_t   = 3 + i
            glow  = pygame.Surface((r_t * 2 + 2, r_t * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (190, 235, 90, alpha), (r_t + 1, r_t + 1), r_t)
            surf.blit(glow, (tx - ox - r_t - 1, ty - oy - r_t - 1))

        f    = self.facing
        bx   = cx
        by   = cy + int(bob)

        # ── Legs (drawn first so they sit behind the body) ────────────────
        # Near-side leg color, far-side (slightly darker)
        LEG_NEAR = (58, 42, 18)
        LEG_FAR  = (36, 26, 10)

        # Leg geometry per pair: (body_x_offset, knee_dx, knee_dy, tip_dx, tip_dy)
        # All dx/dy are signed so they work for both facing directions.
        leg_sway = math.sin(self.wing_t * 0.5) * 1.1
        _legs = [
            # front pair — knee angled forward, tip curls back
            (f * 5,  f * -2, 5,  f * -4, 10),
            # middle pair — straight down
            (f * 0,  f *  0, 6,  f *  1, 11),
            # rear pair — knee angled back, tip curls forward
            (f * -5, f *  2, 5,  f *  4, 10),
        ]
        for i, (bx_off, udx, udy, ldx, ldy) in enumerate(_legs):
            ax = bx + bx_off
            ay = by + 3
            sway_i = leg_sway * (0.3 + i * 0.15)

            # Far-side leg (drawn first = underneath)
            kx_f = ax + udx - f
            ky_f = ay + udy + 1 + sway_i
            tx_f = ax + ldx - f
            ty_f = ay + ldy + 1 + sway_i * 0.6
            pygame.draw.line(surf, LEG_FAR, (ax, ay), (int(kx_f), int(ky_f)), 1)
            pygame.draw.line(surf, LEG_FAR, (int(kx_f), int(ky_f)),
                             (int(tx_f), int(ty_f)), 1)

            # Near-side leg
            kx_n = ax + udx
            ky_n = ay + udy + sway_i
            tx_n = ax + ldx
            ty_n = ay + ldy + sway_i * 0.6
            pygame.draw.line(surf, LEG_NEAR, (ax, ay), (int(kx_n), int(ky_n)), 1)
            pygame.draw.line(surf, LEG_NEAR, (int(kx_n), int(ky_n)),
                             (int(tx_n), int(ty_n)), 1)

        # ── Wings ─────────────────────────────────────────────────────────
        flap_upper = math.sin(self.wing_t) * 0.55
        flap_lower = math.sin(self.wing_t + math.pi) * 0.40

        wing_surf = pygame.Surface((80, 60), pygame.SRCALPHA)
        wc = (40, 30)

        def draw_wing(angle, length, width_scale, fill_alpha, edge_alpha):
            end_x = wc[0] + math.cos(angle) * length * f
            end_y = wc[1] + math.sin(angle) * length
            mid_x = (wc[0] + end_x) / 2
            mid_y = (wc[1] + end_y) / 2
            pts = []
            for k in range(16):
                a = k * math.pi * 2 / 16
                px = mid_x + math.cos(a) * (length / 2) * math.cos(angle) \
                           - math.sin(a) * width_scale * math.sin(angle)
                py = mid_y + math.cos(a) * (length / 2) * math.sin(angle) \
                           + math.sin(a) * width_scale * math.cos(angle)
                pts.append((px, py))
            # Iridescent tint: slight green-blue shimmer on wings
            shimmer = int(math.sin(self.wing_t * 1.7) * 15)
            pygame.draw.polygon(wing_surf,
                                (190 + shimmer, 225 + shimmer, 255, fill_alpha), pts)
            pygame.draw.polygon(wing_surf,
                                (140, 200, 255, edge_alpha), pts, 1)
            # Wing venation: one faint central line
            pygame.draw.line(wing_surf, (200, 220, 255, 30),
                             wc, (int(end_x), int(end_y)), 1)

        draw_wing(-math.pi / 2 + flap_upper,         14, 5, 52, 90)
        draw_wing(-math.pi / 2 + flap_upper + 0.35,  11, 4, 38, 70)
        draw_wing( math.pi / 2 + flap_lower - 0.20,  10, 4, 42, 75)
        draw_wing( math.pi / 2 + flap_lower + 0.15,   8, 3, 28, 55)

        surf.blit(wing_surf, (cx - 40, cy - 30 + int(bob)))

        # ── Pixel-art segmented body ───────────────────────────────────────
        # Abdomen: 3 segments behind thorax, drawn as small pixel rectangles
        SEG = [
            (44, 32, 12),   # darkest at tail end
            (52, 40, 16),
            (60, 46, 20),   # lightest closest to thorax
        ]
        for si, seg_col in enumerate(SEG):
            sx = bx - f * (si * 4 + 2)
            _px_rect(surf, seg_col, sx - 3, by - 2, 5, 6)
            _px_rect(surf, tuple(min(255, c + 14) for c in seg_col), sx - 3, by - 2, 5, 1)
            _px_rect(surf, tuple(max(0, c - 10)   for c in seg_col), sx - 3, by + 3, 5, 1)

        # Thorax: slightly wider, raised
        TH = (70, 54, 24)
        _px_rect(surf, TH, bx - 3, by - 3, 7, 7)
        _px_rect(surf, (88, 70, 32), bx - 2, by - 3, 5, 2)  # highlight top
        _px_rect(surf, (50, 38, 16), bx - 3, by + 3, 7, 1)  # shadow bottom

        # Head
        head_x = bx + f * 9
        pygame.draw.circle(surf, (68, 52, 22), (int(head_x), by - 1), 4)
        _px_rect(surf, (86, 68, 30), head_x - 2, by - 4, 4, 2)  # head highlight

        # Antennae
        ax = head_x + f * 3
        pygame.draw.line(surf, (85, 68, 32),
                         (int(ax), by - 4),
                         (int(ax + f * 6), by - 11), 1)
        pygame.draw.line(surf, (85, 68, 32),
                         (int(ax), by - 4),
                         (int(ax + f * 4), by - 12), 1)
        pygame.draw.circle(surf, (130, 105, 55),
                           (int(ax + f * 6), by - 11), 1)
        pygame.draw.circle(surf, (130, 105, 55),
                           (int(ax + f * 4), by - 12), 1)

        # Eye: white ring + dark pupil + tiny specular dot
        ex = head_x + f * 1
        pygame.draw.circle(surf, (210, 240, 210), (int(ex), by - 2), 2)
        pygame.draw.circle(surf, (10, 10, 10),    (int(ex), by - 2), 1)
        _px_rect(surf, (255, 255, 255), ex + f * 0.5 - 0.5, by - 3, 1, 1)

        # ── Abdomen glow (bioluminescent tail) ────────────────────────────
        glow_pulse = (math.sin(self.pulse_t * 2.5) + 1) / 2
        low_ratio  = (self.light_radius - LIGHT_MIN) / (LIGHT_MAX - LIGHT_MIN)
        glow_r     = int(215 + glow_pulse * 40)
        glow_g     = int(195 + low_ratio * 50)
        glow_b     = int(35  + glow_pulse * 25)
        glow_alpha = int(170 + glow_pulse * 70)

        tail_x = bx - f * 12
        tail_y = by + 1

        # Multi-layer outer glow
        _glow_circle(surf, tail_x, tail_y, (glow_r, glow_g, 60),
                     6, glow_alpha // 2, layers=4)

        # Bright core pixel block (2×2 = hard pixel art look)
        _px_rect(surf, (glow_r, glow_g, glow_b), tail_x - 2, tail_y - 2, 5, 5)
        # Inner bright dot
        _px_rect(surf, (255, 255, 210),           tail_x - 1, tail_y - 1, 3, 3)


class Wasp(pygame.sprite.Sprite):
    """Fast aggressive insect that spawns from screen edges when light < 50%."""

    HITBOX_W = 18
    HITBOX_H = 12

    def __init__(self, x, y):
        super().__init__()
        self.rect  = pygame.Rect(x - self.HITBOX_W // 2, y - self.HITBOX_H // 2,
                                 self.HITBOX_W, self.HITBOX_H)
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.t     = random.uniform(0, math.pi * 2)
        self.speed = 2.6
        self.facing = 1
        self.spawn_grace = 30
        self.fleeing = False       # True once told to fly away
        self._flee_dx = 0.0       # unit vector away from player when flee started
        self._flee_dy = 0.0
        self.gone    = False       # True once offscreen and safe to remove

    def flee(self, player):
        """Tell this wasp to stop following and fly away."""
        if self.fleeing:
            return
        self.fleeing = True
        dx = self.rect.centerx - player.rect.centerx
        dy = self.rect.centery - player.rect.centery
        dist = math.hypot(dx, dy) or 1
        self._flee_dx = dx / dist
        self._flee_dy = dy / dist

    def update(self, player, platforms, camera_offset=(0, 0)):
        self.t += 0.07
        if self.spawn_grace > 0:
            self.spawn_grace -= 1

        if self.fleeing:
            # Fly away in the direction it was headed when flee started
            self.vel_x = self._flee_dx * self.speed * 1.4
            self.vel_y = self._flee_dy * self.speed * 1.4
            self.rect.x += int(self.vel_x)
            self.rect.y += int(self.vel_y)
            if self.facing != 0:
                self.facing = 1 if self._flee_dx >= 0 else -1
            # Mark gone once well offscreen
            ox, oy = camera_offset
            sx = self.rect.centerx - ox
            sy = self.rect.centery - oy
            margin = 120
            if sx < -margin or sx > WIDTH + margin or sy < -margin or sy > HEIGHT + margin:
                self.gone = True
            return

        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy) or 1
        nx, ny = dx / dist, dy / dist

        weave = math.sin(self.t * 3) * 0.45
        wx, wy = -ny * weave, nx * weave

        self.vel_x = nx * self.speed + wx
        self.vel_y = ny * self.speed + wy

        self.rect.x += int(self.vel_x)
        for p in platforms:
            if self.rect.colliderect(p):
                self.vel_x *= -1
                self.rect.x += int(self.vel_x)

        self.rect.y += int(self.vel_y)
        for p in platforms:
            if self.rect.colliderect(p):
                self.vel_y *= -1
                self.rect.y += int(self.vel_y)

        if dx != 0:
            self.facing = 1 if dx > 0 else -1

    def draw(self, surf, camera_offset):
        ox, oy = camera_offset
        cx = self.rect.centerx - ox
        cy = self.rect.centery - oy

        if self.spawn_grace > 0:
            a = int(90 * self.spawn_grace / 30)
            warn = pygame.Surface((38, 38), pygame.SRCALPHA)
            pygame.draw.circle(warn, (220, 40, 40, a), (19, 19), 18)
            surf.blit(warn, (cx - 19, cy - 19))

        bob = math.sin(self.t * 5) * 1.6
        f   = self.facing
        by  = cy + int(bob)

        # ── Legs (4 pairs, spindly) ───────────────────────────────────────
        LEG_COL  = (28, 18, 4)
        LEG_COL2 = (46, 32, 8)  # lighter far-side
        wasp_legs = [
            (f *  6, f * -4, 4, f * -6,  9),
            (f *  2, f * -1, 6, f * -1, 11),
            (f * -3, f *  2, 5, f *  4,  9),
            (f * -7, f *  4, 4, f *  6,  8),
        ]
        for bx_off, udx, udy, ldx, ldy in wasp_legs:
            ax, ay = cx + bx_off, by + 4
            k  = (int(ax + udx - f), int(ay + udy + 1))
            t2 = (int(ax + ldx - f), int(ay + ldy + 1))
            pygame.draw.line(surf, LEG_COL, (int(ax), int(ay)), k,  1)
            pygame.draw.line(surf, LEG_COL, k, t2, 1)
            k2  = (int(ax + udx), int(ay + udy))
            t2b = (int(ax + ldx), int(ay + ldy))
            pygame.draw.line(surf, LEG_COL2, (int(ax), int(ay)), k2,  1)
            pygame.draw.line(surf, LEG_COL2, k2, t2b, 1)

        # ── Wings (fast amber blur with venation) ─────────────────────────
        wing_surf = pygame.Surface((66, 50), pygame.SRCALPHA)
        wc = (33, 25)
        flap = math.sin(self.t * 9) * 0.75   # aggressive fast buzz
        for side, base_angle in [(-1, -math.pi / 2 + flap),
                                  (-1, -math.pi / 2 + flap + 0.48),
                                  ( 1,  math.pi / 2 - flap),
                                  ( 1,  math.pi / 2 - flap - 0.48)]:
            length = 16
            angle  = base_angle
            end_x  = wc[0] + math.cos(angle) * length * f * side
            end_y  = wc[1] + math.sin(angle) * length
            mid_x  = (wc[0] + end_x) / 2
            mid_y  = (wc[1] + end_y) / 2
            pts = []
            for k in range(14):
                a = k * math.pi * 2 / 14
                px = mid_x + math.cos(a) * (length / 2) * math.cos(angle) \
                           - math.sin(a) * 5 * math.sin(angle)
                py = mid_y + math.cos(a) * (length / 2) * math.sin(angle) \
                           + math.sin(a) * 5 * math.cos(angle)
                pts.append((px, py))
            pygame.draw.polygon(wing_surf, (235, 190, 95, 48), pts)
            pygame.draw.polygon(wing_surf, (200, 150, 50, 80), pts, 1)
            # Main vein
            pygame.draw.line(wing_surf, (220, 165, 55, 40),
                             wc, (int(end_x), int(end_y)), 1)
            # Secondary vein at halfway
            pygame.draw.line(wing_surf, (210, 155, 45, 25),
                             (int((wc[0] + mid_x) / 2), int((wc[1] + mid_y) / 2)),
                             (int(mid_x + (end_x - wc[0]) * 0.3),
                              int(mid_y + (end_y - wc[1]) * 0.3)), 1)
        surf.blit(wing_surf, (cx - 33, cy - 25 + int(bob)))

        # ── Tapered abdomen: 5 segments, narrowing to stinger ────────────
        for si in range(5):
            frac   = si / 4.0
            seg_w  = int(11 - frac * 5)   # tapers from 11 → 6
            seg_h  = 7
            sx     = int(cx - f * (si * 4 + 1))
            # Alternating amber / near-black
            if si % 2 == 0:
                seg_col = (215, 155, 18)
                hi_col  = (240, 185, 45)
                sh_col  = (160, 110, 10)
            else:
                seg_col = (20, 14, 4)
                hi_col  = (36, 26, 8)
                sh_col  = (12, 8, 2)
            _px_rect(surf, seg_col, sx - seg_w // 2, by - seg_h // 2, seg_w, seg_h)
            _px_rect(surf, hi_col,  sx - seg_w // 2, by - seg_h // 2, seg_w, 2)
            _px_rect(surf, sh_col,  sx - seg_w // 2, by + seg_h // 2 - 2, seg_w, 2)
            # Fuzz hairs on amber segments
            if si % 2 == 0:
                for fi in range(-seg_w // 2 + 1, seg_w // 2, 3):
                    pygame.draw.line(surf, (175, 115, 12),
                                     (sx + fi, by + seg_h // 2),
                                     (sx + fi, by + seg_h // 2 + 2 + (fi % 2)), 1)

        # ── Thorax (round, fuzzy) ─────────────────────────────────────────
        thx = cx + f * 2
        pygame.draw.circle(surf, (48, 36, 8),  (int(thx), by - 1), 6)
        pygame.draw.circle(surf, (68, 52, 14), (int(thx), by - 2), 4)
        pygame.draw.circle(surf, (86, 66, 20), (int(thx), by - 3), 2)
        # Thorax fuzz
        for fi in range(4):
            a = fi * (math.pi / 3) - math.pi / 6
            fhx = int(thx + math.cos(a) * 6)
            fhy = int(by - 1 + math.sin(a) * 6)
            pygame.draw.line(surf, (60, 46, 10), (int(thx + math.cos(a)*4),
                             int(by - 1 + math.sin(a)*4)), (fhx, fhy), 1)

        # ── Head ──────────────────────────────────────────────────────────
        head_x = cx + f * 14
        pygame.draw.circle(surf, (46, 34, 6), (int(head_x), by - 1), 5)
        _px_rect(surf, (66, 50, 14), head_x - 2, by - 5, 4, 2)

        # Antennae (elbowed wasp-style)
        ant_bx = int(head_x + f * 3)
        pygame.draw.line(surf, (36, 26, 5),
                         (ant_bx, by - 5),
                         (int(ant_bx + f * 5), by - 11), 1)
        pygame.draw.line(surf, (36, 26, 5),
                         (int(ant_bx + f * 5), by - 11),
                         (int(ant_bx + f * 3), by - 15), 1)

        # Large compound eyes (two overlapping circles for faceted look)
        for ey_dx, ey_dy in ((-2, -3), (1, 1)):
            ex = int(head_x + ey_dx * f)
            ey = by + ey_dy
            _glow_circle(surf, ex, ey, (80, 200, 40), 3, 40, layers=2)
            pygame.draw.circle(surf, (50, 150, 25), (ex, ey), 3)
            pygame.draw.circle(surf, (90, 220, 55), (ex, ey), 2)
            pygame.draw.circle(surf, (160, 255, 90), (ex, ey), 1)
            _px_rect(surf, (220, 255, 140), ex, ey - 2, 1, 1)

        # Long crossed mandibles
        for m_dy in (+3, -4):
            pygame.draw.line(surf, (28, 18, 4),
                             (int(head_x + f * 4), by + m_dy // 2),
                             (int(head_x + f * 10), by + m_dy), 2)
        # Amber tips
        pygame.draw.circle(surf, (220, 155, 18), (int(head_x + f * 10), by + 3), 1)
        pygame.draw.circle(surf, (220, 155, 18), (int(head_x + f * 10), by - 4), 1)

        # ── Stinger (long barbed tip) ─────────────────────────────────────
        sting_base = cx - f * 21
        sting_tip  = cx - f * 26
        pygame.draw.line(surf, (38, 26, 6),
                         (int(cx - f * 18), by),
                         (int(sting_base), by), 2)
        pygame.draw.line(surf, (22, 14, 3),
                         (int(sting_base), by),
                         (int(sting_tip), by), 1)
        # Barb notch
        pygame.draw.line(surf, (18, 10, 2),
                         (int(sting_tip), by),
                         (int(sting_tip - f * 2), by - 3), 1)
        # Red venom glow
        _glow_circle(surf, sting_tip, by, (210, 40, 10), 2, 60, layers=2)
        pygame.draw.circle(surf, (230, 55, 20), (int(sting_tip), by), 2)


class Flower(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.rect = pygame.Rect(x - 8, y - 8, 16, 16)
        self.t = random.uniform(0, math.pi * 2)
        self.collected = False
        self.flash_timer = 0

    def update(self):
        self.t += 0.055
        if self.flash_timer > 0:
            self.flash_timer -= 1

    @property
    def dead(self):
        return self.collected and self.flash_timer <= 0

    def collect(self):
        self.collected = True
        self.flash_timer = 22

    def draw(self, surf, camera_offset):
        if self.collected and self.flash_timer <= 0:
            return
        cx = self.rect.centerx - camera_offset[0]
        cy = self.rect.centery - camera_offset[1]

        lerp   = (math.sin(self.t) + 1) / 2
        r = int(FLOWER_PINK[0] * lerp + FLOWER_TEAL[0] * (1 - lerp))
        g = int(FLOWER_PINK[1] * lerp + FLOWER_TEAL[1] * (1 - lerp))
        b = int(FLOWER_PINK[2] * lerp + FLOWER_TEAL[2] * (1 - lerp))

        if self.collected:
            alpha = int(255 * self.flash_timer / 22)
            flash = pygame.Surface((80, 80), pygame.SRCALPHA)
            expand = int(40 * (1 - self.flash_timer / 22) + 5)
            pygame.draw.circle(flash, (255, 255, 255, alpha), (40, 40), expand)
            surf.blit(flash, (cx - 40, cy - 40))
            return

        radius = 5 + math.sin(self.t * 2) * 1.2

        # ── Layered glow ──────────────────────────────────────────────────
        glow = pygame.Surface((38, 38), pygame.SRCALPHA)
        gc = 19
        glow_layers = [(int(radius + 10), 18), (int(radius + 6), 28), (int(radius + 3), 38)]
        for gr, ga in glow_layers:
            pygame.draw.circle(glow, (r, g, b, ga), (gc, gc), gr)
        # Warm inner halo (creamy yellow)
        pygame.draw.circle(glow, (255, 240, 180, 22), (gc, gc), int(radius + 2))
        surf.blit(glow, (cx - gc, cy - gc))

        # ── Stem ──────────────────────────────────────────────────────────
        stem_col = (30, 65, 28)
        pygame.draw.line(surf, stem_col, (int(cx), int(cy + 6)), (int(cx), int(cy + 13)), 2)
        # Leaf nubs on stem
        leaf_col = (40, 80, 34)
        pygame.draw.line(surf, leaf_col,
                         (int(cx), int(cy + 9)),
                         (int(cx + 4), int(cy + 8)), 2)
        pygame.draw.line(surf, leaf_col,
                         (int(cx), int(cy + 11)),
                         (int(cx - 4), int(cy + 10)), 2)

        # ── Petals: 6 outer (pixel blocks) + 6 inner accent ──────────────
        petal_r = int(radius)
        for i in range(6):
            angle = self.t * 0.3 + i * (math.pi / 3)
            px = cx + math.cos(angle) * petal_r
            py = cy + math.sin(angle) * petal_r
            pygame.draw.rect(surf, (r, g, b), (int(px) - 1, int(py) - 1, 3, 3))
            # Petal highlight
            pygame.draw.rect(surf,
                             (min(255, r + 40), min(255, g + 40), min(255, b + 40)),
                             (int(px) - 1, int(py) - 1, 2, 2))

        # Inner ring (offset 30°)
        for i in range(6):
            angle = self.t * 0.3 + i * (math.pi / 3) + math.pi / 6
            px = cx + math.cos(angle) * max(1, petal_r - 2)
            py = cy + math.sin(angle) * max(1, petal_r - 2)
            pygame.draw.rect(surf,
                             (min(255, r + 60), min(255, g + 60), min(255, b + 80)),
                             (int(px), int(py), 2, 2))

        # ── Center ────────────────────────────────────────────────────────
        pygame.draw.rect(surf, (255, 255, 210), (int(cx) - 2, int(cy) - 2, 5, 5))
        pygame.draw.rect(surf, (255, 255, 255), (int(cx) - 1, int(cy) - 1, 3, 3))
        # Tiny cross sparkle on center
        pygame.draw.rect(surf, (255, 255, 230), (int(cx) - 3, int(cy), 7, 1))
        pygame.draw.rect(surf, (255, 255, 230), (int(cx), int(cy) - 3, 1, 7))


class Spore:
    """Tiny floating fungus spore drifting slowly through the air."""
    _COLORS = [
        (210, 200, 255),  # pale lavender
        (180, 255, 200),  # pale mint
        (255, 230, 180),  # pale amber
        (200, 240, 255),  # pale ice blue
        (230, 180, 255),  # pale violet
    ]

    def __init__(self, x, y):
        rng = random.Random(int(x * 7919 + y * 3571))
        self.x      = float(x)
        self.y      = float(y)
        self.size   = rng.randint(2, 4)
        self.color  = rng.choice(self._COLORS)
        self.phase  = rng.uniform(0, math.pi * 2)
        self.drift_x = rng.uniform(-0.5, 0.5)     # horizontal drift
        self.drift_y = rng.uniform(-0.25, 0.05)   # slow upward bias
        self.bob_amp  = rng.uniform(1.0, 2.5)      # subtle bob — not circular
        self.bob_freq = rng.uniform(0.3, 0.8)

    def update(self):
        self.x += self.drift_x
        self.y += self.drift_y

    def draw(self, surf, camera):
        ox, oy = camera
        t  = pygame.time.get_ticks() / 1000.0
        sx = int(self.x - ox)
        sy = int(self.y - oy + math.sin(t * self.bob_freq + self.phase) * self.bob_amp)
        sw, sh = surf.get_size()
        if not (-4 <= sx <= sw + 4 and -4 <= sy <= sh + 4):
            return
        # Soft glow halo
        alpha = int(110 + 60 * math.sin(t * self.bob_freq * 0.7 + self.phase))
        gs = pygame.Surface((self.size * 6 + 4, self.size * 6 + 4), pygame.SRCALPHA)
        gc = gs.get_width() // 2
        pygame.draw.circle(gs, (*self.color, alpha // 4), (gc, gc), self.size * 3)
        pygame.draw.circle(gs, (*self.color, alpha // 2), (gc, gc), self.size * 2)
        pygame.draw.circle(gs, (*self.color, alpha),      (gc, gc), self.size)
        surf.blit(gs, (sx - gc, sy - gc))
        # Bright solid core
        pygame.draw.circle(surf, (255, 255, 255), (sx, sy), max(1, self.size - 1))


class WaterDroplet:
    """A small water droplet resting on a platform that cures spore infection."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.rect     = pygame.Rect(x - 7, y - 7, 14, 14)
        self.collected = False
        self._t        = random.uniform(0, math.pi * 2)

    def update(self):
        self._t += 0.04

    def draw(self, surf, camera):
        if self.collected:
            return
        ox, oy = camera
        cx = int(self.x - ox)
        cy = int(self.y - oy + math.sin(self._t) * 1.5)
        r  = 7
        # Outer glow
        gs = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        gc = r * 2
        pygame.draw.circle(gs, (100, 190, 255, 40), (gc, gc), r * 2)
        surf.blit(gs, (cx - gc, cy - gc))
        # Bubble body — translucent fill
        bubble = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        bc = r + 1
        pygame.draw.circle(bubble, (120, 200, 255, 80),  (bc, bc), r)
        pygame.draw.circle(bubble, (180, 230, 255, 120), (bc, bc), r, 2)
        surf.blit(bubble, (cx - bc, cy - bc))
        # Glint highlights
        pygame.draw.circle(surf, (230, 245, 255), (cx - 3, cy - 3), 2)
        pygame.draw.circle(surf, (255, 255, 255),  (cx - 3, cy - 3), 1)


class Cobweb:
    """A sticky cobweb stretched between two platforms. Traps the player on contact."""

    def __init__(self, x, y, w, h):
        self.rect      = pygame.Rect(x, y, w, h)
        self.triggered = False
        self._fade     = 0
        self.dead      = False

    def trigger(self, player):
        if not self.triggered:
            self.triggered = True
            player.web_escapes_needed = random.randint(4, 10)
            player.web_escapes_done   = 0
            player.web_trap_timer     = random.randint(2, 5) * 60

    def update(self, player):
        if self.triggered and not player.is_trapped:
            self._fade += 6
            if self._fade >= 255:
                self.dead = True

    def draw(self, surf, camera):
        if self.dead:
            return
        ox, oy = camera
        rx = self.rect.x - ox
        ry = self.rect.y - oy
        rw = self.rect.width
        rh = self.rect.height
        cx = rx + rw // 2
        cy = ry + rh // 2

        alpha = max(0, 200 - self._fade)
        web   = pygame.Surface((rw + 4, rh + 4), pygame.SRCALPHA)
        wc    = (rw + 4) // 2
        hc    = (rh + 4) // 2
        col   = (220, 220, 200, alpha)
        thin  = (190, 190, 170, alpha // 2)

        # Radial spokes
        for angle_deg in range(0, 360, 30):
            angle = math.radians(angle_deg)
            ex = wc + int(math.cos(angle) * rw // 2)
            ey = hc + int(math.sin(angle) * rh // 2)
            pygame.draw.line(web, col, (wc, hc), (ex, ey), 1)

        # Concentric rings (3 rings)
        for ring in range(1, 4):
            t = ring / 3
            pts = []
            for angle_deg in range(0, 361, 30):
                angle = math.radians(angle_deg)
                px = wc + int(math.cos(angle) * rw // 2 * t)
                py = hc + int(math.sin(angle) * rh // 2 * t)
                pts.append((px, py))
            if len(pts) > 1:
                pygame.draw.lines(web, thin, False, pts, 1)

        # Anchor threads to corners (looks like it's strung between platforms)
        pygame.draw.line(web, col, (0, 0),        (wc, hc), 1)
        pygame.draw.line(web, col, (rw + 4, 0),   (wc, hc), 1)
        pygame.draw.line(web, col, (0, rh + 4),   (wc, hc), 1)
        pygame.draw.line(web, col, (rw + 4, rh + 4), (wc, hc), 1)

        surf.blit(web, (rx - 2, ry - 2))


class Spider:
    """
    Big scary spider. States: APPROACH → LUNGE → EAT → PAUSE → done.
    Spawns from above the screen, stalks the player slowly, then lunges
    and eats in under a second before triggering game over.
    """
    _APPROACH = 0
    _LUNGE    = 1
    _EAT      = 2
    _PAUSE    = 3

    _APPROACH_SPEED = 1.1
    _LUNGE_FRAMES   = 7    # swift lunge duration
    _EAT_FRAMES     = 65   # eating animation
    _PAUSE_FRAMES   = 50   # stillness before game over

    def __init__(self, x, y):
        self.x     = float(x)
        self.y     = float(y)
        self.rect  = pygame.Rect(0, 0, 48, 48)
        self.rect.center = (int(self.x), int(self.y))
        self._state   = self._APPROACH
        self._state_t = 0
        self._t       = 0.0
        self._done    = False
        # Lunge interpolation
        self._lunge_sx = self.x
        self._lunge_sy = self.y
        self._lunge_tx = self.x
        self._lunge_ty = self.y

    @property
    def is_eating(self):
        return self._state in (self._EAT, self._PAUSE)

    @property
    def flash_alpha(self):
        """White flash alpha for the lunge impact frame."""
        if self._state == self._LUNGE and self._state_t <= 4:
            return int(180 * (1.0 - self._state_t / 4))
        return 0

    def update(self, player):
        self._t      += 0.09
        self._state_t += 1

        if self._state == self._APPROACH:
            dx   = player.rect.centerx - self.x
            dy   = player.rect.centery - self.y
            dist = math.hypot(dx, dy)
            if dist <= 46:
                self._state    = self._LUNGE
                self._state_t  = 0
                self._lunge_sx = self.x
                self._lunge_sy = self.y
                self._lunge_tx = float(player.rect.centerx)
                self._lunge_ty = float(player.rect.centery)
            else:
                self.x += (dx / dist) * self._APPROACH_SPEED
                self.y += (dy / dist) * self._APPROACH_SPEED

        elif self._state == self._LUNGE:
            p = min(1.0, self._state_t / self._LUNGE_FRAMES)
            p = p * p * (3 - 2 * p)  # smooth-step easing
            self.x = self._lunge_sx + (self._lunge_tx - self._lunge_sx) * p
            self.y = self._lunge_sy + (self._lunge_ty - self._lunge_sy) * p
            if self._state_t >= self._LUNGE_FRAMES:
                self._state   = self._EAT
                self._state_t = 0

        elif self._state == self._EAT:
            if self._state_t >= self._EAT_FRAMES:
                self._state   = self._PAUSE
                self._state_t = 0

        elif self._state == self._PAUSE:
            if self._state_t >= self._PAUSE_FRAMES:
                self._done   = True
                player.alive = False

        self.rect.center = (int(self.x), int(self.y))

    # ── Drawing helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _oval(surf, cx, cy, rx, ry, col, hi_col):
        PX = 3
        for dy2 in range(-ry, ry + 1, PX):
            for dx2 in range(-rx, rx + 1, PX):
                if (dx2 / max(rx, 1)) ** 2 + (dy2 / max(ry, 1)) ** 2 <= 1.0:
                    c = hi_col if dy2 < -ry // 3 else col
                    pygame.draw.rect(surf, c, (cx + dx2, cy + dy2, PX, PX))

    def draw(self, surf, camera):
        ox, oy = camera
        cx = int(self.x) - ox
        cy = int(self.y) - oy
        t  = self._t
        st = self._state_t
        state = self._state

        if state == self._LUNGE:
            scale = 1.0 + 0.35 * max(0.0, 1.0 - st / self._LUNGE_FRAMES)
        elif state == self._EAT:
            scale = 1.0 + 0.12 * math.sin(st * 0.35)
        else:
            scale = 1.0

        def S(v):  return max(1, int(v * scale))
        def SS(v): return int(v * scale)   # signed — preserves negatives

        # Head-down: abdomen (rear) at top, cephalothorax (head) at bottom.
        ab_cy = cy - SS(14)
        ct_cy = cy + SS(14)

        # ── Ambient glow behind whole spider (makes it pop on dark bg) ──────
        glow_surf = pygame.Surface((120, 120), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (80, 10, 10, 55),  (60, 60), 58)
        pygame.draw.circle(glow_surf, (120, 20, 20, 35), (60, 60), 44)
        surf.blit(glow_surf, (cx - 60, cy - 60))

        # ── Silk thread from abdomen top ──────────────────────────────────
        if state == self._APPROACH:
            for seg in range(6, 260, 8):
                sway = int(math.sin(t * 0.7 + seg * 0.04) * 3)
                pygame.draw.line(surf, (190, 180, 165),
                                 (cx + sway, ab_cy - S(26) - seg),
                                 (cx + sway, ab_cy - S(26) - seg + 8), 1)

        # ── 8 Legs — 4 per side, all rooted on cephalothorax ─────────────
        # (root_dy_from_ct, mid_dx, mid_dy, tip_dx, tip_dy, phase)
        _P   = math.pi / 2
        amp  = 9 if state != self._EAT else 13
        LEGS = [
            (-8,  38,  28,  60,  44,  0 * _P),
            (-3,  44,  10,  68,  18,  1 * _P),
            ( 3,  44, -10,  68, -18,  2 * _P),
            ( 8,  38, -28,  60, -44,  3 * _P),
        ]
        lc1 = (60, 28, 75);  lc2 = (95, 55, 115);  lct = (140, 95, 165)

        for side in (-1, 1):
            for rdy_ct, mdx, mdy, tdx, tdy, ph in LEGS:
                w  = math.sin(t * 3.5 + ph) * amp
                w2 = math.sin(t * 3.5 + ph + 0.45) * (amp * 0.55)
                rx = cx + side * S(12);  ry = ct_cy + SS(rdy_ct)
                mx = cx + side * S(mdx); my = cy + SS(mdy) + int(w)
                tx = cx + side * S(tdx); ty = cy + SS(tdy) + int(w2)
                pygame.draw.line(surf, lc1, (rx, ry), (mx, my), 4)
                pygame.draw.line(surf, lc2, (mx, my), (tx, ty), 3)
                pygame.draw.line(surf, lct, (tx, ty), (tx + side*5, ty+4), 2)
                pygame.draw.line(surf, lct, (tx, ty), (tx + side*3, ty+7), 2)

        # ── Abdomen — large round, deep purple with red hourglass ─────────
        self._oval(surf, cx, ab_cy, S(25), S(29), (48, 18, 60), (78, 40, 95))

        hw_w = S(12);  hw_n = S(4)
        ht   = ab_cy - S(14);  hm = ab_cy;  hb = ab_cy + S(14)
        pygame.draw.polygon(surf, (210, 28, 28), [
            (cx-hw_w, ht), (cx+hw_w, ht), (cx+hw_n, hm), (cx-hw_n, hm)])
        pygame.draw.polygon(surf, (210, 28, 28), [
            (cx-hw_n, hm), (cx+hw_n, hm), (cx+hw_w, hb), (cx-hw_w, hb)])
        pygame.draw.line(surf, (255, 80, 80), (cx, ht+S(2)), (cx, hb-S(2)), 2)

        # ── Cephalothorax — smaller purple oval ───────────────────────────
        self._oval(surf, cx, ct_cy, S(14), S(15), (42, 16, 54), (72, 38, 88))

        # ── 8 Eyes across the face in two clear rows ─────────────────────
        # Head radius is S(14); spread eyes from ±12 to fill the face.
        # Row 1 (upper, near top of face): 4 eyes, widest spread.
        # Row 2 (lower, near jaw): 4 eyes, tighter cluster.
        gp = int(185 + 70 * math.sin(t * 2.5))
        eye_specs = [
            # (dx, dy_from_ct_cy, radius, large?)
            (-13, 4, 2, False),   # outer left
            ( -6, 3, 3, True),    # inner left
            (  6, 3, 3, True),    # inner right
            ( 13, 4, 2, False),   # outer right
        ]
        for edx, edy, er, large in eye_specs:
            ex   = cx    + SS(edx)
            ey   = ct_cy + SS(edy)
            er_s = S(er)
            gs   = pygame.Surface((er_s*6+6, er_s*6+6), pygame.SRCALPHA)
            gc   = gs.get_width() // 2
            pygame.draw.circle(gs, (220, 0, 0, 120 if large else 70), (gc,gc), er_s*3)
            surf.blit(gs, (ex-gc, ey-gc))
            pygame.draw.circle(surf, (5, 0, 5),                         (ex, ey), er_s+2)
            pygame.draw.circle(surf, (gp,8,8) if large else (195,12,12),(ex, ey), er_s)
            if large and er_s >= 3:
                pygame.draw.circle(surf, (255,210,210), (ex-er_s//2, ey-er_s//2), 2)

        # ── Chelicerae — thick downward hooks that curve inward ────────────
        # Real spider chelicerae: bulky basal segment pointing DOWN, then
        # fang tip curves sharply INWARD toward centre — like claws, not antennae.
        fb_y = ct_cy + S(13)
        open_amt = int(8 * abs(math.sin(st * 0.55))) if state == self._EAT else 0
        for side in (-1, 1):
            # Basal (thick) segment: starts at ±5, goes mostly straight down
            f1x, f1y = cx + side * S(5),  fb_y
            f2x, f2y = cx + side * S(7),  fb_y + S(9)
            # Fang tip: curves inward toward centre and slightly down
            f3x, f3y = cx + side * S(2 + open_amt), fb_y + S(14 + open_amt)
            # Draw thick base segment
            pygame.draw.line(surf, (75, 35, 95),  (f1x, f1y), (f2x, f2y), 6)
            pygame.draw.line(surf, (100, 58, 125),(f1x, f1y), (f2x, f2y), 3)  # highlight
            # Draw curved fang tip
            pygame.draw.line(surf, (95, 50, 120), (f2x, f2y), (f3x, f3y), 4)
            # Venom tip: bright gold dot
            pygame.draw.circle(surf, (210, 155, 0), (f3x, f3y), 3)
            pygame.draw.circle(surf, (255, 210, 50),(f3x, f3y), 1)

        # ── Eating overlay ────────────────────────────────────────────────
        if state == self._EAT:
            progress = min(1.0, st / self._EAT_FRAMES)
            drk = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
            drk.fill((50, 0, 0, int(110 * progress)))
            surf.blit(drk, (0, 0))
            rng2 = random.Random(st)
            for _ in range(8):
                sx2 = cx + rng2.randint(-26, 26)
                sy2 = cy + rng2.randint(-26, 26)
                pygame.draw.rect(surf, (155,10,10),
                                 (sx2, sy2, rng2.randint(2,5), rng2.randint(2,5)))


class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.rect = pygame.Rect(x - 12, y - 16, 24, 24)
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.t = random.uniform(0, math.pi * 2)
        self.speed = 1.2

    def update(self, player, platforms):
        self.t += 0.04
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy) or 1
        self.vel_x = (dx / dist) * self.speed
        self.vel_y += GRAVITY * 0.5
        self.vel_y = min(self.vel_y, MAX_FALL)

        self.rect.x += int(self.vel_x)
        for p in platforms:
            if self.rect.colliderect(p):
                if self.vel_x > 0:
                    self.rect.right = p.left
                elif self.vel_x < 0:
                    self.rect.left = p.right
                self.vel_x = 0

        self.rect.y += int(self.vel_y)
        for p in platforms:
            if self.rect.colliderect(p):
                if self.vel_y > 0:
                    self.rect.bottom = p.top
                    self.vel_y = 0
                elif self.vel_y < 0:
                    self.rect.top = p.bottom
                    self.vel_y = 0

    def draw(self, surf, camera_offset):
        cx = self.rect.centerx - camera_offset[0]
        cy = self.rect.centery - camera_offset[1]
        wobble = math.sin(self.t * 2) * 2

        # ── Writhing tendrils (drawn before body) ─────────────────────────
        t_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        tc = (30, 30)
        for ti in range(5):
            base_a = self.t * 0.5 + ti * (math.pi * 2 / 5)
            wag    = math.sin(self.t * 2.8 + ti * 1.1) * 0.38
            l1     = 10 + math.sin(self.t + ti) * 2
            l2     = l1 + 7 + math.sin(self.t * 1.5 + ti) * 3
            ma     = base_a + wag
            ta     = ma + math.sin(self.t * 3.5 + ti * 0.7) * 0.3
            mx = int(tc[0] + math.cos(ma) * l1)
            my = int(tc[1] + math.sin(ma) * l1)
            tx2 = int(tc[0] + math.cos(ta) * l2)
            ty2 = int(tc[1] + math.sin(ta) * l2)
            pygame.draw.line(t_surf, (*ENEMY_BODY, 100), tc, (mx, my), 2)
            pygame.draw.line(t_surf, (*ENEMY_BODY, 60), (mx, my), (tx2, ty2), 1)
            # Tendril tip — faint purple shimmer
            pygame.draw.circle(t_surf, (60, 20, 80, 55), (tx2, ty2), 2)
        surf.blit(t_surf, (cx - 30, cy - 30 + int(wobble)))

        # ── Body: layered wispy ellipses ───────────────────────────────────
        body = pygame.Surface((44, 44), pygame.SRCALPHA)
        for i in range(5):
            alpha = 200 - i * 38
            inner = tuple(max(0, c + 8) for c in ENEMY_BODY)
            pygame.draw.ellipse(body, (*inner, alpha),
                                (3 + i, 3 + i + int(wobble), 38 - i * 2, 32 - i * 2))
        # Pale purple inner core
        pygame.draw.ellipse(body, (40, 20, 55, 80), (12, 11, 20, 18))
        surf.blit(body, (cx - 22, cy - 22))

        # ── Eyes ──────────────────────────────────────────────────────────
        eye_y = cy - 4 + int(wobble)
        for ex in (cx - 6, cx + 6):
            # Outer glow
            eg = pygame.Surface((14, 14), pygame.SRCALPHA)
            pygame.draw.circle(eg, (180, 20, 20, 70), (7, 7), 6)
            surf.blit(eg, (ex - 7, eye_y - 7))
            # Iris + pupil
            pygame.draw.circle(surf, ENEMY_EYE, (ex, eye_y), 3)
            pygame.draw.circle(surf, (255, 60, 60), (ex, eye_y), 2)
            pygame.draw.circle(surf, (255, 120, 80), (ex, eye_y), 1)
            # Specular
            _px_rect(surf, (255, 200, 200), ex - 1, eye_y - 2, 1, 1)
