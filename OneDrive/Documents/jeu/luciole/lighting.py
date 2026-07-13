import pygame
import math


def build_darkness(screen_size, light_pos, light_radius, low_pulse_t=None):
    """Return a dark overlay surface with a radial light cutout."""
    w, h = screen_size
    dark = pygame.Surface((w, h), pygame.SRCALPHA)

    # Base darkness — dark midnight-blue tint instead of pure black, and
    # noticeably lighter (alpha 165) so the forest is still visible outside
    # the light zone rather than being a solid wall of black.
    BASE_ALPHA = 165
    dark.fill((3, 5, 18, BASE_ALPHA))

    lx, ly = int(light_pos[0]), int(light_pos[1])
    r = int(light_radius)

    steps = max(r, 20)
    for i in range(steps, 0, -1):
        ratio = i / steps
        alpha = int(BASE_ALPHA * (ratio ** 2.2))
        radius = int(r * (i / steps))
        pygame.draw.circle(dark, (3, 5, 18, alpha), (lx, ly), radius)

    # Pulse red tint when light is low
    if low_pulse_t is not None:
        pulse_alpha = int((math.sin(low_pulse_t * 4) * 0.5 + 0.5) * 40)
        dark.fill((80, 0, 0, pulse_alpha), special_flags=pygame.BLEND_RGBA_ADD)

    return dark
