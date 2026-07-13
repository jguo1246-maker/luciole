import os, sys

def resource_path(relative):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)

# Window
WIDTH, HEIGHT = 960, 540
FPS  = 60
TITLE = "Luciole"

# Colors
BG_COLOR     = (10, 10, 26)
PLATFORM_COLOR = (28, 48, 28)
PLATFORM_EDGE  = (40, 70, 40)
PLAYER_CORE  = (255, 240, 160)
PLAYER_HALO  = (255, 200, 80, 60)
FLOWER_PINK  = (255, 120, 200)
FLOWER_TEAL  = (80, 220, 200)
ENEMY_BODY   = (20, 10, 30)
ENEMY_EYE    = (180, 20, 20)
UI_TEXT      = (220, 210, 255)
LIGHT_COLOR  = (255, 230, 140)

# Flight physics (player)
FLY_ACCEL    = 0.75
FLY_DRAG     = 0.86
FLY_MAX      = 7.0
FLY_GRAVITY  = 0.08

# Dash
DASH_SPEED    = 14.0   # sustained velocity during dash (pixels/frame)
DASH_DURATION = 18     # frames the dash lasts (streak trail + sustained speed)
DASH_COOLDOWN = 52     # frames before re-dash (~0.87 s at 60 fps)
DASH_IFRAMES  = 14     # invincibility during dash
DASH_COST     = 0.10   # fraction of LIGHT_MAX consumed per dash

# World physics (enemies)
GRAVITY      = 0.65
MAX_FALL     = 18

# Light
LIGHT_MAX    = 160
LIGHT_MIN    = 20
LIGHT_DECAY  = 0.04   # base decay per frame — scaled by difficulty
LIGHT_RESTORE = 40
DAMAGE_DRAIN  = 25

# Difficulty scaling over time
# decay_mult = 1 + elapsed_seconds / DIFF_RAMP_SECS  (capped at DIFF_MAX_MULT)
DIFF_RAMP_SECS = 120   # seconds to ramp from mult 1 → 2
DIFF_MAX_MULT  = 4.0   # absolute ceiling

# Wasps
WASP_SPAWN_THRESHOLD   = 0.5   # wasps start spawning below this light ratio
WASP_DESPAWN_THRESHOLD = 0.8   # all wasps flee above this light ratio
WASP_SPAWN_INTERVAL  = 280
WASP_MAX             = 8     # higher cap for survival mode
WASP_DAMAGE          = 20

# World floor
WORLD_FLOOR_Y = 900    # Y coordinate of the grass ground

# Screenshake
SHAKE_FRAMES = 14
SHAKE_MAG    = 6

# Starting area — small fixed platform cluster near spawn
SPAWN_POS = (80, 440)

SPAWN_PLATFORMS = [
    (0,   480, 960, 40),   # ground
    (120, 390, 160, 18),
    (360, 330, 180, 18),
    (600, 270, 160, 18),
    (780, 350, 160, 18),
    (220, 210, 140, 18),
    (500, 160, 150, 18),
]

SPAWN_FLOWERS = [
    (160, 362), (420, 302), (650, 242), (820, 322),
]

SPAWN_ENEMIES = [
    (480, 450), (730, 450),
]
