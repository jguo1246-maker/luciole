"""
Infinite procedural world generator.

The world is divided into CHUNK_SIZE×CHUNK_SIZE cells.
Each cell deterministically generates flowers, a platform, and occasionally
an enemy based on its coordinates + a level seed.

Level.update() calls ChunkManager.tick() every frame; tick() returns
lists of new objects to add and old objects to remove.
"""
import random
import pygame
from constants import WIDTH, HEIGHT
from entities import Flower, Enemy, Cobweb, Spore, WaterDroplet

CHUNK_SIZE  = 240
LOAD_RADIUS = 3
ENEMY_CULL  = CHUNK_SIZE * (LOAD_RADIUS + 1)

# Survival-mode tuning (fixed — difficulty is handled by Level.decay_mult)
_FLOWERS_PER_CHUNK = 0.5
_ENEMY_CHANCE      = 0.22
_PLAT_CHANCE       = 0.50
_COBWEB_CHANCE     = 0.75   # chance a chunk spawns a cobweb


class ChunkManager:
    def __init__(self, seed=42):
        self._flowers_per_chunk = _FLOWERS_PER_CHUNK
        self._enemy_chance      = _ENEMY_CHANCE
        self._plat_chance       = _PLAT_CHANCE
        self._seed      = seed & 0xFFFFFFFF
        self._loaded    = {}
        self._collected = set()

    # ── Deterministic RNG for a chunk ─────────────────────────────────────────
    def _rng(self, cx, cy):
        s = (self._seed
             ^ ((cx & 0xFFFF) * 2654435761)
             ^ ((cy & 0xFFFF) * 2246822519)) & 0xFFFFFFFF
        return random.Random(s)

    # ── Build content for one chunk ────────────────────────────────────────────
    def _make_chunk(self, cx, cy):
        rng  = self._rng(cx, cy)
        key  = (cx, cy)
        wx   = cx * CHUNK_SIZE
        wy   = cy * CHUNK_SIZE

        # Flowers
        flowers = []
        # Rare: ~50% chance of 0, ~42% chance of 1, ~8% chance of 2
        n_flowers = rng.choices([0, 1, 2],
                                weights=[1.0 - self._flowers_per_chunk,
                                         self._flowers_per_chunk * 0.84,
                                         self._flowers_per_chunk * 0.16])[0]
        for idx in range(n_flowers):
            if (key, idx) in self._collected:
                continue
            fx = wx + rng.randint(20, CHUNK_SIZE - 20)
            fy = wy + rng.randint(20, CHUNK_SIZE - 20)
            f = Flower(fx, fy)
            f._ck  = key   # back-reference so level can mark collection
            f._idx = idx
            flowers.append(f)

        # 1-2 platforms per chunk
        platforms = []
        n_plat = rng.choices([0, 1, 2], weights=[1 - self._plat_chance,
                                                   self._plat_chance * 0.65,
                                                   self._plat_chance * 0.35])[0]
        for _ in range(n_plat):
            pw = rng.randint(55, 145)
            px = wx + rng.randint(8, max(9, CHUNK_SIZE - pw - 8))
            py = wy + rng.randint(12, CHUNK_SIZE - 12)
            h  = rng.randint(12, 18)   # slightly varied thickness
            platforms.append(pygame.Rect(px, py, pw, h))

        # Enemies
        enemies = []
        if rng.random() < self._enemy_chance:
            ex = wx + rng.randint(20, CHUNK_SIZE - 20)
            ey = wy + rng.randint(20, CHUNK_SIZE - 20)
            enemies.append(Enemy(ex, ey))

        # Cobwebs — only spawn when anchored to 2–6 platforms
        cobwebs = []
        if len(platforms) >= 2 and rng.random() < _COBWEB_CHANCE:
            n_anchors = min(rng.randint(2, 6), len(platforms))
            anchors   = rng.sample(platforms, n_anchors)
            left  = min(p.left  for p in anchors)
            right = max(p.right for p in anchors)
            top   = min(p.top   for p in anchors)
            bot   = max(p.top   for p in anchors)
            if right - left > 20:
                mid_y = (top + bot) // 2
                web_h = max(30, bot - top + rng.randint(20, 40))
                cobwebs.append(Cobweb(left, mid_y - web_h // 2, right - left, web_h))

        # Water droplets — rare, one per platform, ~18% chance
        droplets = []
        for plat in platforms:
            if rng.random() < 0.18:
                dx = plat.x + rng.randint(10, max(11, plat.width - 10))
                droplets.append(WaterDroplet(dx, plat.top))

        # Spores — 6-14 tiny floating particles per chunk
        spores = []
        for _ in range(rng.randint(0, 1)):
            sx = wx + rng.randint(0, CHUNK_SIZE)
            sy = wy + rng.randint(0, CHUNK_SIZE)
            spores.append(Spore(sx, sy))

        self._loaded[key] = {'flowers': flowers, 'platforms': platforms,
                             'enemies': enemies, 'cobwebs': cobwebs,
                             'spores': spores, 'droplets': droplets}
        return flowers, platforms, enemies, cobwebs, spores, droplets

    # ── Called every frame by Level.update() ──────────────────────────────────
    def tick(self, player_x, player_y):
        """
        Returns (new_flowers, new_platforms, new_enemies, gone_flowers, gone_platforms, gone_enemies).
        'new_*'  → just entered the load radius, add to level lists.
        'gone_*' → just left the load radius, remove from level lists.
        """
        r   = LOAD_RADIUS
        pcx = int(player_x // CHUNK_SIZE)
        pcy = int(player_y // CHUNK_SIZE)

        needed = {(pcx + dx, pcy + dy)
                  for dx in range(-r, r + 1)
                  for dy in range(-r, r + 1)}

        new_flowers, new_plats, new_enemies, new_cobwebs, new_spores, new_drops = [], [], [], [], [], []
        gone_flowers, gone_plats, gone_enemies, gone_cobwebs, gone_spores, gone_drops = [], [], [], [], [], []

        # Load chunks that just entered range
        for key in needed - set(self._loaded.keys()):
            f, p, e, c, s, d = self._make_chunk(*key)
            new_flowers.extend(f)
            new_plats.extend(p)
            new_enemies.extend(e)
            new_cobwebs.extend(c)
            new_spores.extend(s)
            new_drops.extend(d)

        # Unload chunks that left range
        for key in list(self._loaded.keys()):
            if key not in needed:
                chunk = self._loaded.pop(key)
                gone_flowers.extend(chunk['flowers'])
                gone_plats.extend(chunk['platforms'])
                gone_enemies.extend(chunk['enemies'])
                gone_cobwebs.extend(chunk.get('cobwebs', []))
                gone_spores.extend(chunk.get('spores', []))
                gone_drops.extend(chunk.get('droplets', []))

        return (new_flowers, new_plats, new_enemies, new_cobwebs, new_spores, new_drops,
                gone_flowers, gone_plats, gone_enemies, gone_cobwebs, gone_spores, gone_drops)

    def flower_collected(self, flower):
        """Call when a procedural flower is picked up so it never re-spawns."""
        self._collected.add((flower._ck, flower._idx))
        key = flower._ck
        if key in self._loaded:
            self._loaded[key]['flowers'] = [
                f for f in self._loaded[key]['flowers'] if f is not flower
            ]
