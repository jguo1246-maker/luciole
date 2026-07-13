"""
Luciole — infinite survival firefly game
Run:  python main.py
Pack: pyinstaller --onefile --noconsole main.py
"""
import sys
import math
import random
import pygame

from constants import WIDTH, HEIGHT, FPS, TITLE, BG_COLOR, LIGHT_MAX, SHAKE_FRAMES, SHAKE_MAG, WORLD_FLOOR_Y
from level import Level
from lighting import build_darkness
from background import Background
from ui import (draw_light_bar, draw_survival_hud, draw_trapped_hud,
                draw_infection_bar, draw_start_screen, draw_game_over,
                draw_pause_menu, draw_settings_screen)
from tutorial import draw_tutorial, SLIDE_COUNT
import sounds

STATE_START    = "start"
STATE_TUTORIAL = "tutorial"
STATE_PLAY     = "play"
STATE_PAUSE    = "pause"
STATE_DEAD     = "dead"
STATE_SETTINGS = "settings"


class Game:
    def __init__(self):
        sounds.init()       # must be before pygame.init()
        pygame.init()
        sounds.load()       # build Sound objects after pygame is ready

        info = pygame.display.Info()
        self.native_w = info.current_w
        self.native_h = info.current_h
        self.screen = pygame.display.set_mode(
            (self.native_w, self.native_h),
            pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF,
        )
        pygame.display.set_caption(TITLE)
        pygame.mouse.set_visible(False)

        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.background = Background(seed=7)

        scale = min(self.native_w / WIDTH, self.native_h / HEIGHT)
        self.scaled_w = int(WIDTH  * scale)
        self.scaled_h = int(HEIGHT * scale)
        self.offset_x = (self.native_w - self.scaled_w) // 2
        self.offset_y = (self.native_h - self.scaled_h) // 2

        # Pre-allocated surfaces for infection blur (avoids per-frame allocation)
        # Go canvas → half-size → screen directly (2 scales instead of 3)
        self._blur_small  = pygame.Surface((WIDTH // 2, HEIGHT // 2))
        self._blur_scaled = pygame.Surface((self.scaled_w, self.scaled_h))
        self._tint_surf   = pygame.Surface((self.scaled_w, self.scaled_h), pygame.SRCALPHA)

        self.clock = pygame.time.Clock()
        self.state = STATE_START
        self.level = None

        self.shake_timer = 0

        self.dead_fade            = 0.0
        self.dead_light           = float(LIGHT_MAX)
        self.dead_time            = 0.0
        self.best_time            = 0.0
        self.dead_infection_level = 0.0

        self.pause_selected  = 0
        self._pause_snapshot = None
        self._death_snapshot = None

        # Main-menu selection (0=Play, 1=Tutorial)
        self.menu_selected  = 0
        # Tutorial slide
        self.tutorial_slide = 0
        # Game-over selection (0=Try Again, 1=Main Menu)
        self.dead_selected  = 0
        # Master volume (0.0 – 1.0)
        self.master_volume  = 1.0

    # ── Helpers ──────────────────────────────────────────────────────────────

    def start_game(self):
        self.level            = Level()
        self.shake_timer      = 0
        self._death_snapshot  = None
        self.state            = STATE_PLAY

    def trigger_shake(self):
        self.shake_timer = SHAKE_FRAMES

    def get_shake(self):
        if self.shake_timer > 0:
            self.shake_timer -= 1
            mag = int(SHAKE_MAG * (self.shake_timer / SHAKE_FRAMES))
            return (random.randint(-mag, mag), random.randint(-mag, mag))
        return (0, 0)

    def present(self):
        scaled = pygame.transform.scale(self.canvas, (self.scaled_w, self.scaled_h))
        self.screen.fill((0, 0, 0))

        # Keep blur active in early death transition if player was infected
        dying_infected = (self.state == STATE_DEAD
                          and self.dead_infection_level > 0
                          and self.dead_fade < 0.5)
        infected = dying_infected or (self.state == STATE_PLAY
                                      and self.level is not None
                                      and self.level.player.infected)

        if infected:
            t = pygame.time.get_ticks() / 1000.0
            blur_strength = max(0.0, 1.0 - self.dead_fade / 0.5) if dying_infected else 1.0

            # Blur: scale canvas down to half, then straight to screen size (2 ops not 3)
            pygame.transform.scale(self.canvas, self._blur_small.get_size(), self._blur_small)
            pygame.transform.scale(self._blur_small, (self.scaled_w, self.scaled_h), self._blur_scaled)

            # Single whole-frame blit with a horizontal wave offset — very cheap
            wave_x = int(math.sin(t * 1.2) * blur_strength)
            self.screen.blit(self._blur_scaled, (self.offset_x + wave_x, self.offset_y))

            # Sickly green tint using pre-allocated surface
            tint_alpha = int((40 + 18 * math.sin(t * 2.2)) * blur_strength)
            if tint_alpha > 0:
                self._tint_surf.fill((20, 70, 10, tint_alpha))
                self.screen.blit(self._tint_surf, (self.offset_x, self.offset_y))

            # Re-overlay HUD regions unblurred so UI stays readable
            sw = self.scaled_w
            sf = sw / WIDTH
            hud_rects = [
                pygame.Rect(0, 0, int(310 * sf), int(105 * sf)),
                pygame.Rect(int(650 * sf), 0, int(310 * sf), int(55 * sf)),
            ]
            for r in hud_rects:
                self.screen.blit(scaled.subsurface(r),
                                 (self.offset_x + r.x, self.offset_y + r.y))
        else:
            self.screen.blit(scaled, (self.offset_x, self.offset_y))

        pygame.display.flip()

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self):
        while True:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    k   = event.key
                    snd = sounds.get()

                    if self.state == STATE_START:
                        prev = self.menu_selected
                        if k in (pygame.K_UP, pygame.K_w, pygame.K_z):
                            self.menu_selected = (self.menu_selected - 1) % 4
                        elif k in (pygame.K_DOWN, pygame.K_s):
                            self.menu_selected = (self.menu_selected + 1) % 4
                        if self.menu_selected != prev:
                            if snd: snd.play_menu_nav()
                        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                            if self.menu_selected == 0:
                                if snd: snd.play_menu_confirm()
                                self.start_game()
                            elif self.menu_selected == 1:
                                if snd: snd.play_menu_open()
                                self.tutorial_slide = 0
                                self.state = STATE_TUTORIAL
                            elif self.menu_selected == 2:
                                if snd: snd.play_menu_open()
                                self.state = STATE_SETTINGS
                            else:
                                pygame.quit()
                                sys.exit()
                        elif k == pygame.K_ESCAPE:
                            pygame.quit()
                            sys.exit()

                    elif self.state == STATE_TUTORIAL:
                        prev = self.tutorial_slide
                        if k in (pygame.K_RIGHT, pygame.K_d):
                            self.tutorial_slide = min(self.tutorial_slide + 1, SLIDE_COUNT - 1)
                        elif k in (pygame.K_LEFT, pygame.K_a):
                            self.tutorial_slide = max(self.tutorial_slide - 1, 0)
                        if self.tutorial_slide != prev:
                            if snd: snd.play_menu_nav()
                        elif k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE,
                                   pygame.K_KP_ENTER):
                            if snd: snd.play_menu_confirm()
                            self.state = STATE_START

                    elif self.state == STATE_SETTINGS:
                        step = 0.05
                        if k in (pygame.K_LEFT, pygame.K_a):
                            self.master_volume = max(0.0, round(self.master_volume - step, 2))
                            if snd: snd.set_master_volume(self.master_volume)
                            if snd: snd.play_menu_nav()
                        elif k in (pygame.K_RIGHT, pygame.K_d):
                            self.master_volume = min(1.0, round(self.master_volume + step, 2))
                            if snd: snd.set_master_volume(self.master_volume)
                            if snd: snd.play_menu_nav()
                        elif k in (pygame.K_ESCAPE, pygame.K_SPACE,
                                   pygame.K_RETURN, pygame.K_KP_ENTER):
                            if snd: snd.play_menu_confirm()
                            self.state = STATE_START

                    elif self.state == STATE_PLAY:
                        if k in (pygame.K_p, pygame.K_ESCAPE):
                            if snd: snd.play_menu_open()
                            if snd: snd.stop_fly()
                            if snd: snd.stop_wasp_buzz()
                            if snd: snd.stop_spider_walk()
                            self._pause_snapshot = self.canvas.copy()
                            self.pause_selected  = 0
                            self.state = STATE_PAUSE

                    elif self.state == STATE_PAUSE:
                        prev = self.pause_selected
                        if k == pygame.K_p:
                            if snd: snd.play_menu_confirm()
                            self.state = STATE_PLAY
                        elif k in (pygame.K_UP, pygame.K_w, pygame.K_z):
                            self.pause_selected = (self.pause_selected - 1) % 3
                        elif k in (pygame.K_DOWN, pygame.K_s):
                            self.pause_selected = (self.pause_selected + 1) % 3
                        if self.pause_selected != prev:
                            if snd: snd.play_menu_nav()
                        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                            if snd: snd.play_menu_confirm()
                            if self.pause_selected == 0:
                                self.state = STATE_PLAY
                            elif self.pause_selected == 1:
                                self.start_game()
                            else:
                                if snd: snd.stop_wasp_buzz()
                                self.level = None
                                self.state = STATE_START

                    elif self.state == STATE_DEAD:
                        prev = self.dead_selected
                        if k in (pygame.K_UP, pygame.K_w, pygame.K_z):
                            self.dead_selected = (self.dead_selected - 1) % 2
                        elif k in (pygame.K_DOWN, pygame.K_s):
                            self.dead_selected = (self.dead_selected + 1) % 2
                        if self.dead_selected != prev:
                            if snd: snd.play_menu_nav()
                        elif k == pygame.K_r:
                            # R always fast-restarts regardless of selection
                            if snd: snd.play_menu_confirm()
                            self.dead_selected = 0
                            self.start_game()
                            self.dead_fade = 0.0
                        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                            if snd: snd.play_menu_confirm()
                            if self.dead_selected == 0:
                                self.dead_selected = 0
                                self.start_game()
                                self.dead_fade = 0.0
                            else:
                                if snd: snd.stop_wasp_buzz()
                                self.dead_selected = 0
                                self.level = None
                                self.state = STATE_START
                        elif k == pygame.K_ESCAPE:
                            pygame.quit()
                            sys.exit()

            # ── Update ───────────────────────────────────────────────────────
            if self.state == STATE_PLAY:
                prev_inv = self.level.player.invincible
                self.level.update()
                player = self.level.player

                snd = sounds.get()
                if snd: snd.update_fly(player)

                if player.invincible > 0 and prev_inv == 0 and player.dash_active == 0:
                    self.trigger_shake()

                if player.infection_level >= 1.0:
                    player.alive = False

                if not player.alive:
                    survived = self.level.elapsed_seconds
                    self.dead_time            = survived
                    self.best_time            = max(self.best_time, survived)
                    self.dead_fade            = 0.0
                    self.dead_light           = player.light_radius
                    self.dead_infection_level = player.infection_level
                    self.dead_selected        = 0
                    # _death_snapshot already holds the last rendered play frame
                    if snd: snd.stop_fly()
                    if snd: snd.stop_wasp_buzz()
                    if snd: snd.stop_spider_walk()
                    self.state = STATE_DEAD

            if self.state == STATE_DEAD:
                self.dead_fade  = min(self.dead_fade + 0.008, 1.0)
                self.dead_light = max(self.dead_light - 0.5, 0)

            # ── Draw ─────────────────────────────────────────────────────────
            shake = self.get_shake()
            self.canvas.fill(BG_COLOR)

            if self.state == STATE_START:
                self.background.draw(self.canvas, 0, 0)
                draw_start_screen(self.canvas, self.menu_selected)

            elif self.state == STATE_TUTORIAL:
                self.background.draw(self.canvas, 0, 0)
                draw_tutorial(self.canvas, self.tutorial_slide)

            elif self.state == STATE_PLAY:
                self._draw_play(shake)
                self._death_snapshot = self.canvas.copy()  # always keep last play frame

            elif self.state == STATE_PAUSE:
                if self._pause_snapshot is not None:
                    self.canvas.blit(self._pause_snapshot, (0, 0))
                draw_pause_menu(self.canvas, self.pause_selected)

            elif self.state == STATE_SETTINGS:
                self.background.draw(self.canvas, 0, 0)
                draw_settings_screen(self.canvas, self.master_volume)

            elif self.state == STATE_DEAD:
                self._draw_dead(shake)

            self.present()

    # ── Draw helpers ─────────────────────────────────────────────────────────

    def _camera_offset(self):
        player = self.level.player
        cx = player.rect.centerx - WIDTH  // 2
        cy = player.rect.centery - HEIGHT // 2
        # Stop camera so just the grass strip is visible at the bottom
        cy = min(cy, WORLD_FLOOR_Y - HEIGHT + 30)
        return (cx, cy)

    def _draw_play(self, shake):
        player = self.level.player
        cam    = self._camera_offset()
        self.background.draw(self.canvas, cam[0], cam[1])
        self.level.draw(self.canvas, cam, shake)

        scx = player.rect.centerx - cam[0] - shake[0]
        scy = player.rect.centery - cam[1] - shake[1]

        low_pulse = None
        if player.light_radius < LIGHT_MAX * 0.3:
            low_pulse = pygame.time.get_ticks() / 1000.0

        self.canvas.blit(
            build_darkness((WIDTH, HEIGHT), (scx, scy), player.light_radius, low_pulse),
            (0, 0)
        )

        # Lunge flash — drawn on top of darkness so it's always visible
        for spider in self.level.spiders:
            fa = spider.flash_alpha
            if fa > 0:
                fl = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                fl.fill((255, 255, 255, fa))
                self.canvas.blit(fl, (0, 0))

        # Green screen fill as infection approaches max
        if player.infection_level > 0.6:
            alpha = int(255 * ((player.infection_level - 0.6) / 0.4))
            green = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            green.fill((10, 80, 10, alpha))
            self.canvas.blit(green, (0, 0))

        if not self.level.spiders:
            draw_light_bar(self.canvas, player.light_radius)
            if player.infected or player.infection_level > 0:
                draw_infection_bar(self.canvas, player.infection_level)
            draw_survival_hud(self.canvas, self.level.elapsed_seconds, self.level.decay_mult)
            if player.is_trapped:
                draw_trapped_hud(self.canvas, player.web_escapes_done,
                                 player.web_escapes_needed, player.web_trap_timer)

    def _draw_dead(self, shake):
        BLACK_FULL = 0.5  # dead_fade when black overlay is fully opaque

        if self.dead_fade < BLACK_FULL:
            # Blit the death snapshot as the frozen starting frame
            if self._death_snapshot is not None:
                self.canvas.blit(self._death_snapshot, (0, 0))
            # Fade to black on top
            black_alpha = min(255, int((self.dead_fade / BLACK_FULL) * 255))
            blk = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            blk.fill((0, 0, 0, black_alpha))
            self.canvas.blit(blk, (0, 0))
        else:
            self.canvas.fill((0, 0, 0))

        # Game over text fades in after black is mostly there
        go_fade = max(0.0, (self.dead_fade - 0.4) / 0.6)
        if go_fade > 0:
            draw_game_over(self.canvas, go_fade, self.dead_time, self.best_time, self.dead_selected)


if __name__ == "__main__":
    Game().run()
