"""
Configuration, color palettes, strobe modes, and constants.
"""

# Window / Display Defaults
DEFAULT_WINDOW_WIDTH = 1280
DEFAULT_WINDOW_HEIGHT = 720
FPS_CAP = 120  # High frame rate for ultra-snappy strobe sync

# Audio settings
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024  # ~23.2ms per audio chunk

# Frequency Band definitions (in Hz)
BASS_FREQ_RANGE = (30, 160)
MID_FREQ_RANGE = (160, 2400)
HIGH_FREQ_RANGE = (2400, 9000)

# Strobe Modes
MODE_HARD_STROBE = "Hard Strobe"
MODE_DUAL_STROBE = "Kick + Snare Dual"
MODE_SMOOTH_PULSE = "Smooth Rave Pulse"
MODE_SPECTRUM = "Audio Reactive Spectrum"
MODE_CHAOS_BLITZ = "Chaos Blitz"
MODE_MONOCHROME = "Monochrome Blitz"

STROBE_MODES = [
    MODE_HARD_STROBE,
    MODE_DUAL_STROBE,
    MODE_SMOOTH_PULSE,
    MODE_SPECTRUM,
    MODE_CHAOS_BLITZ,
    MODE_MONOCHROME,
]

# Color Palettes (RGB tuples)
PALETTES = {
    "Cyberpunk": [
        (255, 0, 128),   # Neon Pink / Magenta
        (0, 240, 255),   # Electric Cyan
        (157, 0, 255),   # Neon Purple
        (255, 230, 0),   # Electric Yellow
        (0, 255, 170),   # Mint Neon
    ],
    "Rave Neon": [
        (0, 255, 90),    # Toxic Neon Green
        (255, 0, 110),   # Hot Pink
        (120, 0, 255),   # Deep Neon Violet
        (255, 115, 0),   # Sunset Orange
        (0, 215, 255),   # Electric Blue
    ],
    "Rainbow Cycle": [
        (255, 0, 0),     # Red
        (255, 127, 0),   # Orange
        (255, 255, 0),   # Yellow
        (0, 255, 0),     # Green
        (0, 255, 255),   # Cyan
        (0, 100, 255),   # Blue
        (180, 0, 255),   # Purple
        (255, 0, 180),   # Hot Pink
    ],
    "Fire & Magma": [
        (255, 25, 25),   # Crimson
        (255, 110, 0),   # Molten Orange
        (255, 210, 0),   # Blazing Gold
        (255, 245, 220), # White Hot Flare
        (180, 0, 40),    # Deep Ember
    ],
    "Electric Ice": [
        (0, 80, 255),    # Deep Electric Blue
        (0, 225, 255),   # Glacial Cyan
        (90, 255, 220),  # Ice Mint
        (240, 250, 255), # Crystal White
        (70, 130, 255),  # Sky Blue
    ],
    "Acid Techno": [
        (57, 255, 20),   # Laser Lime
        (204, 255, 0),   # Acid Yellow
        (255, 255, 255), # Flash White
        (10, 255, 120),  # Bright Emerald
    ],
    "Synthwave 80s": [
        (255, 0, 128),   # Neon Fuchsia
        (114, 9, 183),   # Purple Haze
        (76, 201, 240),  # Miami Cyan
        (247, 37, 133),  # Retro Pink
        (255, 183, 3),   # Golden Sunset
    ],
    "Pastel Dream": [
        (216, 180, 248), # Soft Lavender
        (167, 243, 208), # Soft Mint
        (253, 230, 138), # Soft Peach
        (186, 230, 253), # Baby Blue
        (254, 205, 211), # Pastel Rose
    ],
    "Monochrome Blitz": [
        (255, 255, 255), # Pure White
        (190, 190, 190), # Silver
        (80, 80, 80),    # Dark Charcoal
    ]
}

PALETTE_NAMES = list(PALETTES.keys())

# Default Sensitivity & Decay values
DEFAULT_SENSITIVITY = 1.3    # Multiplier for beat detection threshold (higher = fewer beats, lower = more sensitive)
MIN_SENSITIVITY = 0.6
MAX_SENSITIVITY = 2.5

DEFAULT_DECAY_RATE = 16.0    # Flash decay speed (higher = faster snap to dark, lower = longer fade)
MIN_DECAY_RATE = 4.0
MAX_DECAY_RATE = 35.0

# Refractory period / cooldown between beats (in seconds)
KICK_COOLDOWN = 0.12        # ~500 max BPM limit for kicks
SNARE_COOLDOWN = 0.10       # ~600 max BPM limit for snares

# HUD Settings
HUD_AUTO_HIDE_DELAY = 3.5   # Seconds of mouse inactivity before HUD fades out
HUD_FADE_SPEED = 4.0        # Alpha fade speed
