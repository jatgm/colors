"""
Visual strobe engine and color renderer with multi-monitor support.
Renders fullscreen beat-synchronized strobe flashes, color palette cycling,
dual kick/snare accenting, frequency spectrum blending, and multi-monitor schemes
(Dual Synced, Alternating Ping-Pong, Complementary Contrast, and Panoramic).
"""

import math
import random
import colorsys
import pygame
from config import (
    PALETTES,
    PALETTE_NAMES,
    MODE_HARD_STROBE,
    MODE_DUAL_STROBE,
    MODE_SMOOTH_PULSE,
    MODE_SPECTRUM,
    MODE_CHAOS_BLITZ,
    MODE_MONOCHROME,
    STROBE_MODES,
    DEFAULT_DECAY_RATE,
    MIN_DECAY_RATE,
    MAX_DECAY_RATE,
)

# Dual Monitor Display Schemes
DUAL_SCHEME_SYNCED = "Dual Synced"
DUAL_SCHEME_ALTERNATING = "Ping-Pong Alternating"
DUAL_SCHEME_CONTRAST = "Complementary Contrast"
DUAL_SCHEME_PANORAMIC = "Panoramic Ultra-Wide"

DUAL_SCHEMES = [
    DUAL_SCHEME_SYNCED,
    DUAL_SCHEME_ALTERNATING,
    DUAL_SCHEME_CONTRAST,
    DUAL_SCHEME_PANORAMIC,
]


class VisualizerEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        # Palette state
        self.palette_index = 0
        self.palette_name = PALETTE_NAMES[self.palette_index]
        self.palette_colors = PALETTES[self.palette_name]
        self.color_step = 0
        self.current_color = self.palette_colors[0]
        self.secondary_color = self.palette_colors[1 % len(self.palette_colors)]

        # Mode state
        self.mode_index = 0
        self.mode = STROBE_MODES[self.mode_index]

        # Visual style: "Solid Fullscreen", "Radial Shockwave", "Horizon Pulse"
        self.visual_styles = ["Solid Fullscreen", "Radial Shockwave", "Horizon Pulse"]
        self.style_index = 0
        self.current_style = self.visual_styles[self.style_index]

        # Dual Monitor Scheme
        self.dual_scheme_index = 0
        self.dual_scheme = DUAL_SCHEMES[self.dual_scheme_index]
        self.alternating_side = 0  # 0 = Left monitor, 1 = Right monitor

        # Flash dynamics
        self.kick_intensity = 0.0
        self.snare_intensity = 0.0
        self.kick_intensity_left = 0.0
        self.kick_intensity_right = 0.0
        self.decay_rate = DEFAULT_DECAY_RATE
        self.safe_mode = False  # Soft pulse mode

        # Rainbow cycle hue tracker
        self.rainbow_hue = 0.0

        # Shockwave particle / wave expansion
        self.shockwave_radius = 0.0
        self.shockwave_max_radius = math.hypot(width / 2, height / 2)
        self.shockwave_active = False

    def resize(self, width, height):
        self.width = max(100, width)
        self.height = max(100, height)
        self.shockwave_max_radius = math.hypot(self.width / 2, self.height / 2)

    def set_palette(self, index_or_name):
        """Set palette by name or index."""
        if isinstance(index_or_name, int):
            self.palette_index = index_or_name % len(PALETTE_NAMES)
            self.palette_name = PALETTE_NAMES[self.palette_index]
        elif index_or_name in PALETTES:
            self.palette_name = index_or_name
            self.palette_index = PALETTE_NAMES.index(index_or_name)
        self.palette_colors = PALETTES[self.palette_name]
        self.color_step = 0
        self.current_color = self.palette_colors[0]
        self.secondary_color = self.palette_colors[1 % len(self.palette_colors)]

    def cycle_palette(self):
        """Cycle to next color palette."""
        self.set_palette(self.palette_index + 1)
        return self.palette_name

    def cycle_mode(self):
        """Cycle to next strobe mode."""
        self.mode_index = (self.mode_index + 1) % len(STROBE_MODES)
        self.mode = STROBE_MODES[self.mode_index]
        return self.mode

    def cycle_style(self):
        """Cycle visual render style."""
        self.style_index = (self.style_index + 1) % len(self.visual_styles)
        self.current_style = self.visual_styles[self.style_index]
        return self.current_style

    def cycle_dual_scheme(self):
        """Cycle dual monitor strobe scheme."""
        self.dual_scheme_index = (self.dual_scheme_index + 1) % len(DUAL_SCHEMES)
        self.dual_scheme = DUAL_SCHEMES[self.dual_scheme_index]
        return self.dual_scheme

    def set_decay_rate(self, val):
        self.decay_rate = max(MIN_DECAY_RATE, min(MAX_DECAY_RATE, float(val)))

    def toggle_safe_mode(self):
        self.safe_mode = not self.safe_mode
        return self.safe_mode

    def trigger_kick(self):
        """Trigger kick strobe flash & advance palette color."""
        self.kick_intensity = 1.0
        self.shockwave_radius = 0.0
        self.shockwave_active = True

        # Ping-pong alternate between left & right monitors
        self.alternating_side = 1 - self.alternating_side
        if self.alternating_side == 0:
            self.kick_intensity_left = 1.0
        else:
            self.kick_intensity_right = 1.0

        if self.palette_name == "Rainbow Cycle":
            self.rainbow_hue = (self.rainbow_hue + 0.125) % 1.0
            r, g, b = colorsys.hsv_to_rgb(self.rainbow_hue, 1.0, 1.0)
            self.current_color = (int(r * 255), int(g * 255), int(b * 255))
            r2, g2, b2 = colorsys.hsv_to_rgb((self.rainbow_hue + 0.5) % 1.0, 1.0, 1.0)
            self.secondary_color = (int(r2 * 255), int(g2 * 255), int(b2 * 255))
        elif self.mode == MODE_CHAOS_BLITZ:
            self.current_color = random.choice(self.palette_colors)
            self.secondary_color = random.choice(self.palette_colors)
        else:
            self.color_step = (self.color_step + 1) % len(self.palette_colors)
            self.current_color = self.palette_colors[self.color_step]
            sec_idx = (self.color_step + len(self.palette_colors) // 2) % len(self.palette_colors)
            self.secondary_color = self.palette_colors[sec_idx]

    def trigger_snare(self):
        """Trigger snare/clap accent flash."""
        self.snare_intensity = 1.0

    def update(self, dt, audio_state):
        """Update strobe decay physics."""
        if audio_state.get("is_kick", False):
            self.trigger_kick()
        if audio_state.get("is_snare", False):
            self.trigger_snare()

        actual_decay = self.decay_rate * (0.6 if self.safe_mode or self.mode == MODE_SMOOTH_PULSE else 1.0)
        self.kick_intensity = max(0.0, self.kick_intensity - actual_decay * dt)
        self.kick_intensity_left = max(0.0, self.kick_intensity_left - actual_decay * dt)
        self.kick_intensity_right = max(0.0, self.kick_intensity_right - actual_decay * dt)

        self.snare_intensity = max(0.0, self.snare_intensity - (self.decay_rate * 1.5) * dt)

        if self.shockwave_active:
            self.shockwave_radius += (self.shockwave_max_radius * 3.5) * dt
            if self.shockwave_radius >= self.shockwave_max_radius:
                self.shockwave_active = False

    def _calc_color_and_intensity(self, base_col, intensity, audio_state):
        """Calculate final RGB from base color, intensity, mode, and snare accents."""
        if self.safe_mode or self.mode == MODE_SMOOTH_PULSE:
            base_floor = 0.18 + audio_state.get("bass_level", 0.0) * 0.15
            eff_intensity = base_floor + intensity * 0.82
            eff_intensity = math.sin(min(1.0, eff_intensity) * (math.pi / 2))
        elif self.mode == MODE_HARD_STROBE or self.mode == MODE_MONOCHROME:
            eff_intensity = max(0.0, min(1.0, intensity))
        elif self.mode == MODE_SPECTRUM:
            eff_intensity = max(0.1, min(1.0, 0.2 + audio_state.get("total_level", 0.0) * 0.4 + intensity * 0.6))
        else:
            eff_intensity = max(0.0, min(1.0, intensity))

        if self.mode == MODE_MONOCHROME:
            val = int(255 * eff_intensity)
            r, g, b = val, val, val
        elif self.mode == MODE_SPECTRUM:
            bass = audio_state.get("bass_level", 0.0)
            mid = audio_state.get("mid_level", 0.0)
            high = audio_state.get("high_level", 0.0)
            r = int(min(255, (bass * 230 + mid * 80) * (0.3 + eff_intensity * 0.7)))
            g = int(min(255, (mid * 240 + high * 60) * (0.3 + eff_intensity * 0.7)))
            b = int(min(255, (high * 240 + bass * 120) * (0.3 + eff_intensity * 0.7)))
        else:
            cr, cg, cb = base_col
            r = int(cr * eff_intensity)
            g = int(cg * eff_intensity)
            b = int(cb * eff_intensity)

        # Add Snare Accent Flash
        if self.snare_intensity > 0.01:
            if self.mode == MODE_DUAL_STROBE:
                snare_val = int(255 * self.snare_intensity * 0.9)
                r = min(255, r + snare_val)
                g = min(255, g + snare_val)
                b = min(255, b + snare_val)
            else:
                snare_add = int(120 * self.snare_intensity)
                r = min(255, r + snare_add)
                g = min(255, g + snare_add)
                b = min(255, b + snare_add)

        return (r, g, b), eff_intensity

    def render(self, screen, audio_state, monitors=None, is_dual=False):
        """Render strobe frames across one or both monitors."""
        if is_dual and monitors and len(monitors) >= 2:
            self._render_dual(screen, audio_state, monitors)
        else:
            self._render_single(screen, audio_state, pygame.Rect(0, 0, self.width, self.height))

    def _render_single(self, screen, audio_state, rect, custom_col=None, custom_intensity=None):
        """Render strobe visual on a single monitor viewport."""
        base_col = custom_col if custom_col is not None else self.current_color
        intensity = custom_intensity if custom_intensity is not None else self.kick_intensity
        (r, g, b), eff_intensity = self._calc_color_and_intensity(base_col, intensity, audio_state)

        if self.current_style == "Solid Fullscreen":
            screen.fill((r, g, b), rect)

        elif self.current_style == "Radial Shockwave":
            outer_dim = 0.25 if not self.safe_mode else 0.5
            screen.fill((int(r * outer_dim), int(g * outer_dim), int(b * outer_dim)), rect)

            cx = rect.x + rect.width // 2
            cy = rect.y + rect.height // 2
            max_rad = math.hypot(rect.width / 2, rect.height / 2)

            if self.shockwave_active and self.shockwave_radius > 0:
                progress = min(1.0, self.shockwave_radius / max_rad)
                wave_alpha = int(255 * (1.0 - progress) * eff_intensity)
                if wave_alpha > 0:
                    wave_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    ring_color = (min(255, r + 50), min(255, g + 50), min(255, b + 50), wave_alpha)
                    thickness = max(8, int(40 * (1.0 - progress)))
                    curr_rad = int(progress * max_rad)
                    pygame.draw.circle(wave_surf, ring_color, (rect.width // 2, rect.height // 2), curr_rad, thickness)
                    screen.blit(wave_surf, (rect.x, rect.y))

            center_rad = int(min(rect.width, rect.height) * 0.35 * (0.8 + eff_intensity * 0.5))
            if center_rad > 0:
                center_surf = pygame.Surface((center_rad * 2, center_rad * 2), pygame.SRCALPHA)
                for ring in range(3, 0, -1):
                    rad = int(center_rad * (ring / 3.0))
                    alpha = int((80 / ring) * eff_intensity)
                    pygame.draw.circle(
                        center_surf,
                        (min(255, r + 40), min(255, g + 40), min(255, b + 40), alpha),
                        (center_rad, center_rad),
                        rad,
                    )
                screen.blit(center_surf, (cx - center_rad, cy - center_rad))

        elif self.current_style == "Horizon Pulse":
            screen.fill((int(r * 0.15), int(g * 0.15), int(b * 0.15)), rect)
            cy = rect.y + rect.height // 2
            beam_height = int((rect.height * 0.6) * eff_intensity)
            if beam_height > 2:
                beam_surf = pygame.Surface((rect.width, beam_height), pygame.SRCALPHA)
                beam_surf.fill((r, g, b, int(220 * eff_intensity)))
                screen.blit(beam_surf, (rect.x, cy - beam_height // 2))

    def _render_dual(self, screen, audio_state, monitors):
        """Render synchronized or alternating strobes across both monitors."""
        m0 = monitors[0].rect
        m1 = monitors[1].rect

        if self.dual_scheme == DUAL_SCHEME_SYNCED:
            # Both monitors flash identical synchronized colors with individual centers
            self._render_single(screen, audio_state, m0, self.current_color, self.kick_intensity)
            self._render_single(screen, audio_state, m1, self.current_color, self.kick_intensity)

        elif self.dual_scheme == DUAL_SCHEME_ALTERNATING:
            # Ping-Pong alternating beats between Left and Right monitors
            # Idle monitor stays at ambient baseline or subtle pulse
            ambient_floor = 0.12 if not self.safe_mode else 0.25
            left_int = self.kick_intensity_left + ambient_floor
            right_int = self.kick_intensity_right + ambient_floor

            self._render_single(screen, audio_state, m0, self.current_color, min(1.0, left_int))
            self._render_single(screen, audio_state, m1, self.secondary_color, min(1.0, right_int))

        elif self.dual_scheme == DUAL_SCHEME_CONTRAST:
            # Left monitor flashes Color A, Right monitor flashes Color B
            self._render_single(screen, audio_state, m0, self.current_color, self.kick_intensity)
            self._render_single(screen, audio_state, m1, self.secondary_color, self.kick_intensity)

        elif self.dual_scheme == DUAL_SCHEME_PANORAMIC:
            # One massive 3840x1080 canvas
            combined_rect = pygame.Rect(0, 0, self.width, self.height)
            self._render_single(screen, audio_state, combined_rect, self.current_color, self.kick_intensity)
