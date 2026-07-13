import math
import random
import pygame
from constants import *
from entities import Player, Flower, Enemy, Wasp, Spider, WaterDroplet
from world import ChunkManager, ENEMY_CULL
import sounds

# ── Platform art ──────────────────────────────────────────────────────────────
_PX = 3

_LEAF_COLS = [
    (22,  58, 24),
    (28,  72, 30),
    (18,  50, 20),
    (35,  80, 36),
    (14,  44, 16),
]
_BRANCH_COL  = (52, 34, 14)
_BRANCH_EDGE = (70, 48, 20)


def _draw_leaf_platform(surf, rect, ox, oy):
    rng = random.Random((rect.x * 73856093) ^ (rect.y * 19349663))
    rx = rect.x - ox
    ry = rect.y - oy
    rw = rect.width
    rh = rect.height

    branch_h = max(_PX * 2, rh // 2)
    by = ry + rh - branch_h
    pygame.draw.rect(surf, _BRANCH_COL,  (rx, by, rw, branch_h))
    pygame.draw.rect(surf, _BRANCH_EDGE, (rx, by, rw, _PX))
    for bx in range(rx + _PX * 3, rx + rw - _PX * 2, _PX * 6):
        dh = rng.randint(_PX, branch_h - _PX)
        pygame.draw.rect(surf, (38, 24, 8), (bx, by + _PX, _PX, dh))

    x_cursor = rx
    while x_cursor < rx + rw:
        step   = rng.randint(_PX * 3, _PX * 6)
        blob_w = rng.randint(_PX * 4, _PX * 8)
        blob_h = rng.randint(_PX * 3, _PX * 5)
        blob_y = ry + rng.randint(0, max(1, rh - branch_h - blob_h))
        col    = rng.choice(_LEAF_COLS)
        hi_col = tuple(min(255, c + 18) for c in col)
        sh_col = tuple(max(0,   c - 12) for c in col)
        bx2 = (x_cursor // _PX) * _PX
        by2 = (blob_y    // _PX) * _PX
        pygame.draw.rect(surf, col,    (bx2, by2, blob_w, blob_h))
        pygame.draw.rect(surf, hi_col, (bx2, by2, blob_w, _PX))
        pygame.draw.rect(surf, sh_col, (bx2, by2 + blob_h - _PX, blob_w, _PX))
        pygame.draw.rect(surf, (min(255, hi_col[0] + 20),
                                min(255, hi_col[1] + 20),
                                min(255, hi_col[2] + 20)),
                         (bx2 + _PX, by2 + _PX, _PX, _PX))
        x_cursor += step + blob_w - _PX * 2


class Level:
    # Wide rect used purely for player collision with the world floor
    _FLOOR_RECT = pygame.Rect(-50000, WORLD_FLOOR_Y, 100000, 2000)

    def __init__(self):
        self.fixed_platforms = [pygame.Rect(*p) for p in SPAWN_PLATFORMS]
        self.fixed_flowers   = [Flower(*pos)    for pos in SPAWN_FLOWERS]
        self.enemies         = [Enemy(*pos)     for pos in SPAWN_ENEMIES]
        self.wasps           = []
        self.spiders         = []

        self.player = Player(*SPAWN_POS)

        # Procedural infinite world
        self.chunk_mgr      = ChunkManager(seed=42)
        self.proc_flowers   = []
        self.proc_platforms = []
        self.proc_enemies   = []
        self.proc_cobwebs   = []
        self.proc_spores    = []
        self.proc_droplets  = []

        # Survival timer
        self.elapsed_frames = 0

        # Droplet spawner when infected
        self._droplet_spawn_timer = 0

        # Wasp spawn timer
        self._wasp_timer = WASP_SPAWN_INTERVAL
        # How long player has been above WASP_DESPAWN_THRESHOLD (frames)
        self._wasp_flee_timer = 0

    @property
    def elapsed_seconds(self):
        return self.elapsed_frames / FPS

    @property
    def decay_mult(self):
        """Difficulty ramp: starts at 1, climbs to DIFF_MAX_MULT over DIFF_RAMP_SECS."""
        raw = 1.0 + self.elapsed_seconds / DIFF_RAMP_SECS
        return min(raw, DIFF_MAX_MULT)

    @property
    def platforms(self):
        return self.fixed_platforms + self.proc_platforms + [self._FLOOR_RECT]

    # ── Wasp spawning ─────────────────────────────────────────────────────────
    def _try_spawn_wasp(self):
        if len(self.wasps) >= WASP_MAX:
            return
        edge = random.randint(0, 3)
        margin = 40
        px, py = self.player.rect.centerx, self.player.rect.centery
        if edge == 0:
            x, y = random.randint(px - WIDTH // 2, px + WIDTH // 2), py - HEIGHT // 2 - margin
        elif edge == 1:
            x, y = random.randint(px - WIDTH // 2, px + WIDTH // 2), py + HEIGHT // 2 + margin
        elif edge == 2:
            x, y = px - WIDTH // 2 - margin, random.randint(py - 200, py + 200)
        else:
            x, y = px + WIDTH // 2 + margin, random.randint(py - 200, py + 200)
        self.wasps.append(Wasp(x, y))

    # ── Update ────────────────────────────────────────────────────────────────
    def update(self):
        self.elapsed_frames += 1

        keys = pygame.key.get_pressed()
        self.player.handle_input(keys)
        self.player.update(self.platforms, self.decay_mult)

        # Fixed flowers
        snd = sounds.get()
        for flower in self.fixed_flowers[:]:
            flower.update()
            if not flower.collected and self.player.rect.colliderect(flower.rect):
                flower.collect()
                self.player.collect_flower()
                if snd: snd.play_flower()
        self.fixed_flowers = [f for f in self.fixed_flowers if not f.dead]

        # Chunk management
        new_f, new_p, new_e, new_c, new_s, new_d, gone_f, gone_p, gone_e, gone_c, gone_s, gone_d = self.chunk_mgr.tick(
            self.player.rect.centerx, self.player.rect.centery
        )
        self.proc_flowers.extend(new_f)
        self.proc_platforms.extend(new_p)
        self.proc_enemies.extend(new_e)
        self.proc_cobwebs.extend(new_c)
        self.proc_spores.extend(new_s)
        self.proc_droplets.extend(new_d)

        gone_f_ids = {id(f) for f in gone_f}
        gone_p_ids = {id(p) for p in gone_p}
        gone_e_ids = {id(e) for e in gone_e}
        gone_c_ids = {id(c) for c in gone_c}
        gone_s_ids = {id(s) for s in gone_s}
        gone_d_ids = {id(d) for d in gone_d}
        self.proc_flowers   = [f for f in self.proc_flowers   if id(f) not in gone_f_ids]
        self.proc_platforms = [p for p in self.proc_platforms if id(p) not in gone_p_ids]
        self.proc_enemies   = [e for e in self.proc_enemies   if id(e) not in gone_e_ids]
        self.proc_cobwebs   = [c for c in self.proc_cobwebs   if id(c) not in gone_c_ids]
        self.proc_spores    = [s for s in self.proc_spores    if id(s) not in gone_s_ids]
        self.proc_droplets  = [d for d in self.proc_droplets  if id(d) not in gone_d_ids]
        self.proc_enemies   = [
            e for e in self.proc_enemies
            if abs(e.rect.centerx - self.player.rect.centerx) < ENEMY_CULL
            and abs(e.rect.centery - self.player.rect.centery) < ENEMY_CULL
        ]

        # Procedural flowers
        for flower in self.proc_flowers[:]:
            flower.update()
            if not flower.collected and self.player.rect.colliderect(flower.rect):
                flower.collect()
                self.chunk_mgr.flower_collected(flower)
                self.player.collect_flower()
                if snd: snd.play_flower()
        self.proc_flowers = [f for f in self.proc_flowers if not f.dead]

        # Fixed enemies
        for enemy in self.enemies:
            enemy.update(self.player, self.platforms)
            if self.player.rect.colliderect(enemy.rect):
                if self.player.take_damage():
                    if snd: snd.play_hit_shadow()

        # Procedural enemies
        for enemy in self.proc_enemies:
            enemy.update(self.player, self.platforms)
            if self.player.rect.colliderect(enemy.rect):
                if self.player.take_damage():
                    if snd: snd.play_hit_shadow()

        # Wasps
        light_ratio = self.player.light_radius / LIGHT_MAX
        cam_x = self.player.rect.centerx - WIDTH  // 2
        cam_y = self.player.rect.centery - HEIGHT // 2

        # Count how long player stays above despawn threshold
        if light_ratio >= WASP_DESPAWN_THRESHOLD:
            self._wasp_flee_timer += 1
        else:
            self._wasp_flee_timer = 0

        # After 10 seconds above threshold, tell active wasps to flee
        FLEE_DELAY = FPS * 10
        if self._wasp_flee_timer >= FLEE_DELAY:
            for wasp in self.wasps:
                if not wasp.fleeing:
                    wasp.flee(self.player)

        if light_ratio < WASP_SPAWN_THRESHOLD:
            self._wasp_timer -= 1
            urgency = 1.0 + (WASP_SPAWN_THRESHOLD - light_ratio) * 4
            if self._wasp_timer <= 0:
                self._try_spawn_wasp()
                self._wasp_timer = int(WASP_SPAWN_INTERVAL / urgency)
        else:
            self._wasp_timer = min(self._wasp_timer + 1, WASP_SPAWN_INTERVAL)

        for wasp in self.wasps:
            wasp.update(self.player, self.platforms, camera_offset=(cam_x, cam_y))
            if not wasp.fleeing and wasp.spawn_grace == 0 and self.player.rect.colliderect(wasp.rect):
                if self.player.invincible == 0:
                    self.player.light_radius -= WASP_DAMAGE
                    self.player.invincible = 90
                    if snd: snd.play_hit_wasp()

        self.wasps = [w for w in self.wasps if not w.gone]
        if not self.wasps:
            self._wasp_flee_timer = 0

        # Spores — update and check infection
        player_rect = self.player.rect
        for spore in self.proc_spores:
            spore.update()
            if not self.player.infected:
                sr = pygame.Rect(int(spore.x) - spore.size, int(spore.y) - spore.size,
                                 spore.size * 2, spore.size * 2)
                if player_rect.colliderect(sr):
                    self.player.infected = True
                    if snd: snd.play_spore()

        # Water droplets — update and check cure
        for droplet in self.proc_droplets:
            droplet.update()
            if not droplet.collected and player_rect.colliderect(droplet.rect):
                droplet.collected = True
                self.player.infected = False
                self.player.infection_level = 0.0
                if snd: snd.play_droplet()
        self.proc_droplets = [d for d in self.proc_droplets if not d.collected]

        # While infected, periodically spawn bonus droplets on nearby platforms
        if self.player.infected:
            self._droplet_spawn_timer -= 1
            if self._droplet_spawn_timer <= 0:
                self._droplet_spawn_timer = 300  # every 5 seconds
                nearby = [p for p in self.platforms
                          if abs(p.centerx - player_rect.centerx) < 500
                          and abs(p.centery - player_rect.centery) < 400
                          and p.width > 20]
                if nearby:
                    p = random.choice(nearby)
                    dx = p.x + random.randint(10, max(11, p.width - 10))
                    self.proc_droplets.append(WaterDroplet(dx, p.top))
        else:
            self._droplet_spawn_timer = 0

        # Cobwebs
        for cobweb in self.proc_cobwebs:
            cobweb.update(self.player)
            if not cobweb.triggered and self.player.rect.colliderect(cobweb.rect):
                cobweb.trigger(self.player)
            # Timer expired → spawn spider above the web
            if (cobweb.triggered and self.player.is_trapped
                    and self.player.web_trap_timer == 0
                    and not self.spiders):
                # Drop from just above the visible screen edge
                sx = self.player.rect.centerx + random.randint(-20, 20)
                sy = self.player.rect.centery - HEIGHT // 2 - 20
                self.spiders.append(Spider(sx, sy))
        self.proc_cobwebs = [c for c in self.proc_cobwebs if not c.dead]

        # Spiders
        for spider in self.spiders:
            prev_state = spider._state
            spider.update(self.player)
            if snd:
                # Start walk sound when spider first appears
                if prev_state == spider._APPROACH and spider._state == spider._APPROACH:
                    snd.start_spider_walk()
                # Stop walk, play attack on lunge
                if prev_state == spider._APPROACH and spider._state == spider._LUNGE:
                    snd.stop_spider_walk()
                    snd.play_spider_attack()
        self.spiders = [s for s in self.spiders if not s._done]

        if snd:
            if self.wasps:
                px, py = self.player.rect.centerx, self.player.rect.centery
                # Closest wasp distance → proximity 0..1 (full volume within 120px)
                min_dist = min(
                    math.hypot(w.rect.centerx - px, w.rect.centery - py)
                    for w in self.wasps
                )
                NEAR = 120.0
                FAR  = 600.0
                proximity = max(0.0, 1.0 - (min_dist - NEAR) / (FAR - NEAR))
            else:
                proximity = 0.0
            snd.update_wasp_buzz(proximity)

    # ── Grass floor — call AFTER the darkness overlay ─────────────────────────
    def draw_floor(self, surf, camera_offset, shake):
        ox = camera_offset[0] + shake[0]
        oy = camera_offset[1] + shake[1]
        floor_screen_y = WORLD_FLOOR_Y - oy
        if floor_screen_y > surf.get_height():
            return
        sw = surf.get_width()
        sh = surf.get_height()
        dirt_top = max(0, floor_screen_y + 6)
        pygame.draw.rect(surf, (72, 44, 18), (0, dirt_top, sw, sh - dirt_top))
        STEP = 12
        wx = (ox // STEP) * STEP - STEP
        while wx - ox < sw + STEP:
            brng = random.Random(int(wx) ^ 0xBEEF)
            bw   = brng.randint(8, 20)
            bh   = brng.randint(6, 13)
            col  = brng.choice([(34, 80, 26), (42, 96, 33), (28, 70, 21), (48, 108, 38)])
            sx   = wx - ox
            by   = floor_screen_y - bh + 4
            pygame.draw.rect(surf, col, (sx, by, bw, bh + 6))
            hi = tuple(min(255, c + 18) for c in col)
            pygame.draw.rect(surf, hi, (sx, by, bw, 3))
            if brng.random() < 0.3:
                pygame.draw.rect(surf, (18, 48, 12),
                                 (sx + brng.randint(1, max(1, bw - 2)), by + 3, 1, bh - 2))
            wx += STEP
        DSTEP = 20
        dwx = (ox // DSTEP) * DSTEP - DSTEP
        while dwx - ox < sw + DSTEP:
            drng = random.Random(int(dwx) ^ 0xCAFE)
            dx2  = dwx - ox + drng.randint(0, DSTEP)
            dy2  = floor_screen_y + drng.randint(10, 45)
            if 0 <= dy2 < sh:
                dc = drng.choice([(95, 58, 24), (80, 48, 18), (108, 68, 30)])
                pygame.draw.rect(surf, dc, (dx2, dy2, drng.randint(3, 9), drng.randint(2, 5)))
            dwx += DSTEP

    # ── Draw ──────────────────────────────────────────────────────────────────
    def draw(self, surf, camera_offset, shake):
        ox = camera_offset[0] + shake[0]
        oy = camera_offset[1] + shake[1]

        # Draw floor here so the darkness overlay covers it naturally
        self.draw_floor(surf, camera_offset, shake)

        for p in self.fixed_platforms:
            _draw_leaf_platform(surf, p, ox, oy)
        for p in self.proc_platforms:
            _draw_leaf_platform(surf, p, ox, oy)

        for spore in self.proc_spores:
            spore.draw(surf, (ox, oy))
        for droplet in self.proc_droplets:
            droplet.draw(surf, (ox, oy))

        for flower in self.fixed_flowers:
            flower.draw(surf, (ox, oy))
        for flower in self.proc_flowers:
            flower.draw(surf, (ox, oy))

        for enemy in self.enemies:
            enemy.draw(surf, (ox, oy))
        for enemy in self.proc_enemies:
            enemy.draw(surf, (ox, oy))
        for cobweb in self.proc_cobwebs:
            cobweb.draw(surf, (ox, oy))

        for wasp in self.wasps:
            wasp.draw(surf, (ox, oy))

        # Draw player only if not currently being eaten
        eating = any(s.is_eating for s in self.spiders)
        if not eating:
            self.player.draw(surf, (ox, oy))

        # Spider drawn on top so it covers the player during eat
        for spider in self.spiders:
            spider.draw(surf, (ox, oy))
