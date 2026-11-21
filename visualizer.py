"""
Visual strobe engine and color renderer with multi-monitor support and Extreme Overdrive.
Renders fullscreen beat-synchronized strobe flashes, multi-pulse burst trains,
psycho overdrive, machine-gun multi-band triggering, screen impact shake,
and dual-monitor festival rave lighting schemes.
"""

import time
import math
import random
import colorsys
import pygame
from config import (
    PALETTES,
    PALETTE_NAMES,
    PALETTE_ALBUM_ART,
    MODE_STROBE_2_0,
    MODE_SMART_RHYTHM,
    MODE_CLASSIC_RAPID,
    MODE_PSYCHO_OVERDRIVE,
    MODE_RED_ONLY,
    MODE_BASS_ONLY,
    MODE_ALBUM_ART,
    MODE_MACHINE_GUN,
    MODE_STROBE_BLITZ,
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
    SOLID_COLORS,
    SOLID_COLOR_NAMES,
    SOLID_COLOR_MAP,
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

        # Mode state (Default to Psycho Overdrive for maximum craze!)
        self.mode_index = 0
        self.mode = STROBE_MODES[self.mode_index]

        # Solid Color Lighting State (Static continuous room & screen illumination)
        self.solid_color_active = False
        self.solid_color_index = 0
        self.solid_color = SOLID_COLORS[self.solid_color_index][1]

        # Visual style
        self.visual_styles = ["Solid Fullscreen", "Radial Shockwave", "Horizon Pulse"]
        self.style_index = 0
        self.current_style = self.visual_styles[self.style_index]

        # Dual Monitor Scheme
        self.dual_scheme_index = 0
        self.dual_scheme = DUAL_SCHEMES[self.dual_scheme_index]
        self.alternating_side = 0

        # Flash dynamics
        self.kick_intensity = 0.0
        self.snare_intensity = 0.0
        self.hihat_intensity = 0.0
        self.drop_intensity = 0.0

        self.kick_intensity_left = 0.0
        self.kick_intensity_right = 0.0

        self.decay_rate = DEFAULT_DECAY_RATE
        self.safe_mode = False

        # Overdrive / Crazy Mode (Default ON for extreme strobe intensity!)
        self.overdrive_mode = True

        # Stroboscopic Multi-Pulse Burst Train Engine (Martin Atomic Strobe simulation)
        self.burst_remaining = 0
        self.burst_timer = 0.0
        self.burst_period = 0.030   # ~33Hz strobe flash cycle
        self.burst_is_on = True

        # Screen Shake / Impact Jitter
        self.shake_x = 0
        self.shake_y = 0
        self.shake_decay = 0.0

        # Rainbow cycle hue tracker
        self.rainbow_hue = 0.0

        # Shockwave particle / wave expansion
        self.shockwave_radius = 0.0
        self.shockwave_max_radius = math.hypot(width / 2, height / 2)
        self.shockwave_active = False

        # Direct Screen Render Outputs for 100% Exact Multi-Device Synchronization
        self.last_render_rgb_0 = (0, 0, 0)
        self.last_render_rgb_1 = (0, 0, 0)
        self.last_eff_intensity_0 = 0.0
        self.last_eff_intensity_1 = 0.0

        # Peak hold timers to guarantee 100% full-brilliance rendering on beats
        self.kick_hold_timer = 0.0
        self.snare_hold_timer = 0.0
        self.hihat_hold_timer = 0.0

        # Peripheral RGB flash latch (deterministic timer for physical keyboard/mouse strobes)
        self.peripheral_flash_until = 0.0
        self.peripheral_flash_color_left = (0, 0, 0)
        self.peripheral_flash_color_right = (0, 0, 0)
        self.peripheral_flash_id = 0

        # Real-time music energy and audio silence state
        self.music_energy = 0.5
        self.is_paused = False
        self.is_audio_silent = False

        # Strobe 2.0 section and melody tracking state
        self.current_pitch_idx = 0
        self.current_pitch_name = "C"
        self.pitch_confidence = 0.0
        self.is_chorus_active = False
        self.is_buildup_active = False
        self.is_verse_active = True
        self.current_section_name = "VERSE"
        self.section_energy_val = 1.0
        self.is_808_active = False

    def resize(self, width, height):
        self.width = max(100, width)
        self.height = max(100, height)
        self.shockwave_max_radius = math.hypot(self.width / 2, self.height / 2)

    def set_palette(self, index_or_name):
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

    def set_mode(self, mode_name):
        if mode_name in STROBE_MODES:
            self.mode = mode_name
            self.mode_index = STROBE_MODES.index(mode_name)
            self.solid_color_active = False
            if self.mode in (MODE_CLASSIC_RAPID, MODE_PSYCHO_OVERDRIVE):
                self.overdrive_mode = True
                self.decay_rate = max(24.0, self.decay_rate)
            elif self.mode == MODE_STROBE_2_0:
                self.overdrive_mode = False
            elif self.mode == MODE_ALBUM_ART:
                self.set_palette(PALETTE_ALBUM_ART)
            elif self.mode == MODE_RED_ONLY:
                self.current_color = (255, 0, 0)
                self.secondary_color = (255, 0, 0)
        return self.mode

    def is_classic_rapid_active(self):
        """Return True if Classic Rapid Strobe mode (how it was before) is active."""
        return self.mode == MODE_CLASSIC_RAPID

    def is_smart_mode_active(self):
        """Return True if Smart Rhythm detection is active."""
        return (self.mode not in (MODE_CLASSIC_RAPID, MODE_PSYCHO_OVERDRIVE)) and not self.overdrive_mode

    def toggle_classic_rapid(self):
        """Toggle between Classic Rapid Mode (how it was before) and Smart mode."""
        if self.is_classic_rapid_active():
            prev_mode = getattr(self, "_prev_mode_before_classic", MODE_STROBE_2_0)
            if prev_mode == MODE_CLASSIC_RAPID:
                prev_mode = MODE_STROBE_2_0
            self.set_mode(prev_mode)
            return False
        else:
            self._prev_mode_before_classic = self.mode if self.mode != MODE_CLASSIC_RAPID else MODE_STROBE_2_0
            self.set_mode(MODE_CLASSIC_RAPID)
            return True

    def is_solid_color_active(self):
        """Return True if static solid color override lighting is currently active."""
        return self.solid_color_active

    def toggle_solid_color(self):
        """Toggle between static solid color lighting and music-reactive strobe mode."""
        self.solid_color_active = not self.solid_color_active
        return self.solid_color_active

    def set_solid_color(self, color_or_idx, activate=True):
        """
        Set static solid color by index, preset name, or (R, G, B) tuple.
        Optionally activates solid color mode.
        """
        if isinstance(color_or_idx, int):
            self.solid_color_index = color_or_idx % len(SOLID_COLORS)
            self.solid_color = SOLID_COLORS[self.solid_color_index][1]
        elif isinstance(color_or_idx, str):
            if color_or_idx in SOLID_COLOR_MAP:
                self.solid_color = SOLID_COLOR_MAP[color_or_idx]
                self.solid_color_index = SOLID_COLOR_NAMES.index(color_or_idx)
        elif isinstance(color_or_idx, (tuple, list)) and len(color_or_idx) >= 3:
            r = max(0, min(255, int(color_or_idx[0])))
            g = max(0, min(255, int(color_or_idx[1])))
            b = max(0, min(255, int(color_or_idx[2])))
            self.solid_color = (r, g, b)
            self.solid_color_index = -1
            for i, (_, col) in enumerate(SOLID_COLORS):
                if col == self.solid_color:
                    self.solid_color_index = i
                    break
        if activate:
            self.solid_color_active = True
        return self.solid_color

    def cycle_solid_color(self, step=1):
        """Cycle through preset solid colors and activate solid lighting."""
        self.solid_color_index = (self.solid_color_index + step) % len(SOLID_COLORS)
        self.solid_color = SOLID_COLORS[self.solid_color_index][1]
        self.solid_color_active = True
        return self.solid_color

    def get_solid_color_name(self):
        """Return the display name of the currently selected solid color."""
        if 0 <= self.solid_color_index < len(SOLID_COLORS):
            return SOLID_COLORS[self.solid_color_index][0]
        for name, col in SOLID_COLORS:
            if col == self.solid_color:
                return name
        return f"RGB({self.solid_color[0]},{self.solid_color[1]},{self.solid_color[2]})"

    def is_red_only_active(self):
        return self.mode == MODE_RED_ONLY

    def toggle_red_only(self):
        """Toggle between Red Only Mode and previous strobe mode."""
        if self.is_red_only_active():
            prev_mode = getattr(self, "_prev_mode_before_red", MODE_STROBE_2_0)
            if prev_mode == MODE_RED_ONLY:
                prev_mode = MODE_STROBE_2_0
            self.set_mode(prev_mode)
            return False
        else:
            self._prev_mode_before_red = self.mode if self.mode != MODE_RED_ONLY else MODE_STROBE_2_0
            self.set_mode(MODE_RED_ONLY)
            return True

    def is_album_art_active(self):
        return self.mode == MODE_ALBUM_ART or self.palette_name == PALETTE_ALBUM_ART

    def update_album_art_palette(self, new_colors):
        """Update dynamic palette extracted from current native album art."""
        if not new_colors:
            return
        PALETTES[PALETTE_ALBUM_ART] = list(new_colors)
        if self.palette_name == PALETTE_ALBUM_ART or self.mode == MODE_ALBUM_ART:
            self.palette_colors = list(new_colors)
            self.current_color = self.palette_colors[self.color_step % len(self.palette_colors)]
            sec_idx = (self.color_step + len(self.palette_colors) // 2) % len(self.palette_colors)
            self.secondary_color = self.palette_colors[sec_idx]
            if self.mode == MODE_ALBUM_ART and self.palette_name != PALETTE_ALBUM_ART:
                self.palette_name = PALETTE_ALBUM_ART
                self.palette_index = PALETTE_NAMES.index(PALETTE_ALBUM_ART)

    def is_mode_2_0_active(self):
        return self.mode == MODE_STROBE_2_0

    def is_bass_only_active(self):
        return self.mode == MODE_BASS_ONLY

    def toggle_bass_only(self):
        """Toggle between Bass Only Mode and previous strobe mode."""
        if self.is_bass_only_active():
            prev_mode = getattr(self, "_prev_mode_before_bass", MODE_STROBE_2_0)
            if prev_mode == MODE_BASS_ONLY:
                prev_mode = MODE_STROBE_2_0
            self.set_mode(prev_mode)
            return False
        else:
            self._prev_mode_before_bass = self.mode if self.mode != MODE_BASS_ONLY else MODE_STROBE_2_0
            self.set_mode(MODE_BASS_ONLY)
            return True

    def toggle_mode_2_0(self):
        """Toggle between Mode 2.0 (Smart Sync) and previous mode."""
        if self.is_mode_2_0_active():
            prev_mode = getattr(self, "_prev_mode_before_2_0", MODE_PSYCHO_OVERDRIVE)
            if prev_mode == MODE_STROBE_2_0:
                prev_mode = MODE_PSYCHO_OVERDRIVE
            self.set_mode(prev_mode)
            return False
        else:
            self._prev_mode_before_2_0 = self.mode if self.mode != MODE_STROBE_2_0 else MODE_PSYCHO_OVERDRIVE
            self.set_mode(MODE_STROBE_2_0)
            return True

    def toggle_album_art_mode(self):
        """Toggle between Album Art Mode/Palette and previous strobe mode/palette."""
        if self.is_album_art_active():
            prev_mode = getattr(self, "_prev_mode_before_art", MODE_PSYCHO_OVERDRIVE)
            if prev_mode == MODE_ALBUM_ART:
                prev_mode = MODE_PSYCHO_OVERDRIVE
            prev_pal = getattr(self, "_prev_pal_before_art", "Cyberpunk")
            if prev_pal == PALETTE_ALBUM_ART:
                prev_pal = "Cyberpunk"
            self.set_mode(prev_mode)
            self.set_palette(prev_pal)
            return False
        else:
            self._prev_mode_before_art = self.mode if self.mode != MODE_ALBUM_ART else MODE_PSYCHO_OVERDRIVE
            self._prev_pal_before_art = self.palette_name if self.palette_name != PALETTE_ALBUM_ART else "Cyberpunk"
            self.set_mode(MODE_ALBUM_ART)
            self.set_palette(PALETTE_ALBUM_ART)
            return True

    def cycle_palette(self):
        self.set_palette(self.palette_index + 1)
        return self.palette_name

    def cycle_mode(self):
        self.solid_color_active = False
        self.mode_index = (self.mode_index + 1) % len(STROBE_MODES)
        self.mode = STROBE_MODES[self.mode_index]
        if self.mode == MODE_ALBUM_ART:
            self.set_palette(PALETTE_ALBUM_ART)
        return self.mode

    def cycle_style(self):
        self.style_index = (self.style_index + 1) % len(self.visual_styles)
        self.current_style = self.visual_styles[self.style_index]
        return self.current_style

    def set_style(self, style_or_idx):
        if isinstance(style_or_idx, int):
            self.style_index = style_or_idx % len(self.visual_styles)
        elif style_or_idx in self.visual_styles:
            self.style_index = self.visual_styles.index(style_or_idx)
        self.current_style = self.visual_styles[self.style_index]
        return self.current_style

    def cycle_dual_scheme(self):
        self.dual_scheme_index = (self.dual_scheme_index + 1) % len(DUAL_SCHEMES)
        self.dual_scheme = DUAL_SCHEMES[self.dual_scheme_index]
        return self.dual_scheme

    def set_dual_scheme(self, scheme_or_idx):
        if isinstance(scheme_or_idx, int):
            self.dual_scheme_index = scheme_or_idx % len(DUAL_SCHEMES)
        elif scheme_or_idx in DUAL_SCHEMES:
            self.dual_scheme_index = DUAL_SCHEMES.index(scheme_or_idx)
        self.dual_scheme = DUAL_SCHEMES[self.dual_scheme_index]
        return self.dual_scheme

    def set_decay_rate(self, val):
        self.decay_rate = max(MIN_DECAY_RATE, min(MAX_DECAY_RATE, float(val)))

    def toggle_safe_mode(self):
        self.safe_mode = not self.safe_mode
        if self.safe_mode:
            self.overdrive_mode = False
        return self.safe_mode

    def toggle_overdrive(self):
        """Toggle Overdrive / Crazy Mode for extreme machine-gun strobe intensity."""
        self.overdrive_mode = not self.overdrive_mode
        if self.overdrive_mode:
            self.safe_mode = False
            self.decay_rate = max(30.0, self.decay_rate)
        return self.overdrive_mode

    def get_sync_packet(self, audio_state, is_beat_event=False):
        """Generate high-fidelity frame synchronization packet for connected clients."""
        spec = audio_state.get("spectrum_bars", [])
        if hasattr(spec, "tolist"):
            spec = spec.tolist()
        bars_clean = [round(float(x), 2) for x in spec[:24]]

        return {
            "type": "BEAT_SYNC" if is_beat_event else "FRAME_SYNC",
            "timestamp": time.time(),
            # Modes & Configuration
            "mode": self.mode,
            "palette": self.palette_name,
            "palette_colors": [[int(c[0]), int(c[1]), int(c[2])] for c in self.palette_colors],
            "style": self.current_style,
            "dual_scheme": self.dual_scheme,
            "safe": bool(self.safe_mode),
            "overdrive": bool(self.overdrive_mode),
            "solid_active": bool(self.solid_color_active),
            "solid_color": [int(c) for c in self.solid_color],
            "solid_color_index": int(self.solid_color_index),
            "decay": round(float(self.decay_rate), 1),
            "alternating_side": int(self.alternating_side),
            # Palette Colors
            "color": [int(c) for c in self.current_color],
            "secondary_color": [int(c) for c in self.secondary_color],
            # Exact rendered RGB colors for displays
            "final_rgb_0": [int(c) for c in self.last_render_rgb_0],
            "final_rgb_1": [int(c) for c in self.last_render_rgb_1],
            "eff_intensity_0": round(float(self.last_eff_intensity_0), 3),
            "eff_intensity_1": round(float(self.last_eff_intensity_1), 3),
            # Strobe dynamics
            "kick_intensity": round(float(self.kick_intensity), 3),
            "snare_intensity": round(float(self.snare_intensity), 3),
            "hihat_intensity": round(float(self.hihat_intensity), 3),
            "drop_intensity": round(float(self.drop_intensity), 3),
            "kick_intensity_left": round(float(self.kick_intensity_left), 3),
            "kick_intensity_right": round(float(self.kick_intensity_right), 3),
            # Multi-Pulse Machine-Gun Strobe chopping
            "burst_remaining": int(self.burst_remaining),
            "burst_is_on": bool(self.burst_is_on),
            # Screen shake & Shockwave
            "shake_x": int(self.shake_x),
            "shake_y": int(self.shake_y),
            "shockwave_active": bool(self.shockwave_active),
            "shockwave_progress": round(float(self.shockwave_radius / max(1.0, self.shockwave_max_radius)), 3),
            # Live Audio meters & Spectrum for Client HUD
            "bpm": round(float(audio_state.get("bpm", 0.0)), 1),
            "bass_level": round(float(audio_state.get("bass_level", 0.0)), 3),
            "mid_level": round(float(audio_state.get("mid_level", 0.0)), 3),
            "high_level": round(float(audio_state.get("high_level", 0.0)), 3),
            "total_level": round(float(audio_state.get("total_level", 0.0)), 3),
            "spectrum_bars": bars_clean,
            # Trigger flags
            "is_kick": bool(audio_state.get("is_kick", False)),
            "is_snare": bool(audio_state.get("is_snare", False)),
            "is_hihat": bool(audio_state.get("is_hihat", False)),
            "is_drop": bool(audio_state.get("is_drop", False)),
            "is_paused": bool(audio_state.get("is_paused", False)),
            "music_energy": round(float(self.music_energy), 3),
        }

    def apply_sync_packet(self, pkt):
        """Apply full frame synchronization packet from Host."""
        # 1. Mode, Style, Palette, Scheme
        if "mode" in pkt and pkt["mode"] != self.mode:
            self.mode = pkt["mode"]
            if self.mode in STROBE_MODES:
                self.mode_index = STROBE_MODES.index(self.mode)

        if "style" in pkt and pkt["style"] != self.current_style:
            self.current_style = pkt["style"]
            if self.current_style in self.visual_styles:
                self.style_index = self.visual_styles.index(self.current_style)

        if "palette" in pkt and pkt["palette"] != self.palette_name:
            self.set_palette(pkt["palette"])

        if "palette_colors" in pkt and isinstance(pkt["palette_colors"], list) and len(pkt["palette_colors"]) > 0:
            custom_cols = [tuple(c) for c in pkt["palette_colors"]]
            if pkt.get("palette") == PALETTE_ALBUM_ART or self.palette_name == PALETTE_ALBUM_ART:
                self.palette_colors = custom_cols
                PALETTES[PALETTE_ALBUM_ART] = custom_cols

        if "dual_scheme" in pkt and pkt["dual_scheme"] != self.dual_scheme:
            self.dual_scheme = pkt["dual_scheme"]
            if self.dual_scheme in DUAL_SCHEMES:
                self.dual_scheme_index = DUAL_SCHEMES.index(self.dual_scheme)

        # 2. Physics & Engine Flags
        if "safe" in pkt:
            self.safe_mode = bool(pkt["safe"])
        if "overdrive" in pkt:
            self.overdrive_mode = bool(pkt["overdrive"])
        if "solid_active" in pkt:
            self.solid_color_active = bool(pkt["solid_active"])
        if "solid_color" in pkt and isinstance(pkt["solid_color"], (list, tuple)) and len(pkt["solid_color"]) == 3:
            self.solid_color = tuple(int(c) for c in pkt["solid_color"])
        if "solid_color_index" in pkt:
            self.solid_color_index = int(pkt["solid_color_index"])
        if "decay" in pkt:
            self.decay_rate = float(pkt["decay"])
        if "alternating_side" in pkt:
            self.alternating_side = int(pkt["alternating_side"])

        # 3. Base Colors
        if "color" in pkt:
            self.current_color = tuple(pkt["color"])
        if "secondary_color" in pkt:
            self.secondary_color = tuple(pkt["secondary_color"])

        # 4. Exact Rendered RGBs & Effective Intensities
        if "final_rgb_0" in pkt:
            self.last_render_rgb_0 = tuple(pkt["final_rgb_0"])
        if "final_rgb_1" in pkt:
            self.last_render_rgb_1 = tuple(pkt["final_rgb_1"])
        if "eff_intensity_0" in pkt:
            self.last_eff_intensity_0 = float(pkt["eff_intensity_0"])
        if "eff_intensity_1" in pkt:
            self.last_eff_intensity_1 = float(pkt["eff_intensity_1"])

        # 5. Strobe Dynamics
        if "kick_intensity" in pkt:
            self.kick_intensity = float(pkt["kick_intensity"])
        if "snare_intensity" in pkt:
            self.snare_intensity = float(pkt["snare_intensity"])
        if "hihat_intensity" in pkt:
            self.hihat_intensity = float(pkt["hihat_intensity"])
        if "drop_intensity" in pkt:
            self.drop_intensity = float(pkt["drop_intensity"])
        if "kick_intensity_left" in pkt:
            self.kick_intensity_left = float(pkt["kick_intensity_left"])
        if "kick_intensity_right" in pkt:
            self.kick_intensity_right = float(pkt["kick_intensity_right"])

        # 6. Burst Chopping
        if "burst_remaining" in pkt:
            self.burst_remaining = int(pkt["burst_remaining"])
        if "burst_is_on" in pkt:
            self.burst_is_on = bool(pkt["burst_is_on"])

        # 7. Screen Shake & Shockwave
        if "shake_x" in pkt:
            self.shake_x = int(pkt["shake_x"])
            self.shake_y = int(pkt.get("shake_y", 0))
        if "shockwave_active" in pkt:
            self.shockwave_active = bool(pkt["shockwave_active"])
            if "shockwave_progress" in pkt:
                self.shockwave_radius = float(pkt["shockwave_progress"]) * self.shockwave_max_radius

        # 8. Music energy & silence state from Host
        total_lvl = float(pkt.get("total_level", 0.0))
        bass_lvl = float(pkt.get("bass_level", 0.0))
        mid_lvl = float(pkt.get("mid_level", 0.0))
        self.music_energy = max(total_lvl * 0.75, bass_lvl * 0.85, mid_lvl * 0.55)
        self.is_paused = bool(pkt.get("is_paused", False))
        self.is_audio_silent = (self.music_energy < 0.02) or self.is_paused

    def update_client_fallback(self, dt):
        """Smoothly decay strobe intensity if sync stream drops or pauses."""
        self.music_energy = 0.0
        self.is_audio_silent = True
        decay_multiplier = 1.6 if self.overdrive_mode else 1.0
        actual_decay = (self.decay_rate * decay_multiplier) * (0.5 if self.safe_mode or self.mode == MODE_SMOOTH_PULSE else 1.0)
        self.kick_intensity = max(0.0, self.kick_intensity - actual_decay * dt)
        self.kick_intensity_left = max(0.0, self.kick_intensity_left - actual_decay * dt)
        self.kick_intensity_right = max(0.0, self.kick_intensity_right - actual_decay * dt)
        self.snare_intensity = max(0.0, self.snare_intensity - (actual_decay * 1.5) * dt)
        self.hihat_intensity = max(0.0, self.hihat_intensity - (actual_decay * 2.2) * dt)
        self.drop_intensity = max(0.0, self.drop_intensity - (actual_decay * 0.8) * dt)

        # Decay forced RGBs down to black
        factor = max(0.0, 1.0 - (actual_decay * dt))
        self.last_render_rgb_0 = (int(self.last_render_rgb_0[0] * factor), int(self.last_render_rgb_0[1] * factor), int(self.last_render_rgb_0[2] * factor))
        self.last_render_rgb_1 = (int(self.last_render_rgb_1[0] * factor), int(self.last_render_rgb_1[1] * factor), int(self.last_render_rgb_1[2] * factor))
        self.last_eff_intensity_0 *= factor
        self.last_eff_intensity_1 *= factor

    def get_peripheral_colors(self):
        """Calculate exact synchronized peripheral RGB colors for Razer hardware.
        Returns ((r_left, g_left, b_left), (r_right, g_right, b_right), is_strobe_mode).
        When solid color mode is active, continuously output the solid color without strobe blackouts.
        In strobe modes: delivers 100% full-blast 255 peak color on beat impacts
        for exactly 80ms, followed by absolute pitch black (0, 0, 0) until the next beat.
        In smooth modes: delivers smooth pulsing rave colors.
        When silent or paused: delivers true blackout (0, 0, 0) across all peripherals.
        """
        # Static Solid Color Mode: output full solid illumination without strobe cuts
        if self.solid_color_active:
            return self.solid_color, self.solid_color, False

        # True blackout across all peripherals if audio is silent (< 0.02) or media playback is paused/stopped
        if self.is_audio_silent or self.is_paused or (self.music_energy < 0.02 and self.kick_intensity < 0.01):
            is_strobe_mode = not (self.safe_mode or self.mode == MODE_SMOOTH_PULSE or self.mode == MODE_ALBUM_ART)
            return (0, 0, 0), (0, 0, 0), is_strobe_mode

        is_strobe = not (self.safe_mode or self.mode == MODE_SMOOTH_PULSE)
        if not is_strobe:
            return self.last_render_rgb_0, self.last_render_rgb_1, False

        # Active strobe flash window
        is_flash_active = (time.perf_counter() < self.peripheral_flash_until)

        # Chopped blackout during burst train off-phases (Martin Atomic simulation)
        if self.burst_remaining > 0 and not self.burst_is_on:
            is_flash_active = False

        if is_flash_active:
            def _scale_flash(col):
                r, g, b = col
                max_c = max(r, g, b, 1)
                scale = 255.0 / max_c
                return (min(255, int(r * scale)), min(255, int(g * scale)), min(255, int(b * scale)))

            if self.mode == MODE_MONOCHROME:
                col_left = (255, 255, 255)
                col_right = (255, 255, 255)
            elif self.mode == MODE_RED_ONLY:
                col_left = (255, 0, 0)
                col_right = (255, 0, 0)
            elif self.mode == MODE_SPECTRUM:
                # Synchronize peripheral flash with the live audio reactive spectrum colors rendered on screen
                spec_0 = self.last_render_rgb_0 if max(self.last_render_rgb_0) > 0 else (255, 80, 20)
                spec_1 = self.last_render_rgb_1 if max(self.last_render_rgb_1) > 0 else spec_0
                col_left = _scale_flash(spec_0)
                col_right = _scale_flash(spec_1)
            else:
                col_left = _scale_flash(self.peripheral_flash_color_left)
                col_right = _scale_flash(self.peripheral_flash_color_right)

            # In Ping-Pong Alternating dual monitor scheme, selectively flash the active side
            if self.dual_scheme == DUAL_SCHEME_ALTERNATING:
                if self.alternating_side == 0:
                    col_right = self.last_render_rgb_1 if self.mode in (MODE_ALBUM_ART, MODE_SPECTRUM) else (0, 0, 0)
                else:
                    col_left = self.last_render_rgb_0 if self.mode in (MODE_ALBUM_ART, MODE_SPECTRUM) else (0, 0, 0)

            return col_left, col_right, True

        # In Album Art mode or Spectrum mode, preserve the vibrant ambient glow between beat flashes
        # so physical keyboard, mouse, room lights, and PC lighting remain synchronized and illuminated
        if self.mode in (MODE_ALBUM_ART, MODE_SPECTRUM):
            return self.last_render_rgb_0, self.last_render_rgb_1, False

        # Blackout between beats in extreme strobe modes (Overdrive, Hard Strobe, etc.)
        return (0, 0, 0), (0, 0, 0), True

    def trigger_kick(self):
        """Trigger kick strobe flash & advance palette color with multi-pulse train."""
        self.music_energy = max(self.music_energy, 0.5)
        self.is_audio_silent = False
        self.kick_intensity = 1.0
        self.kick_hold_timer = 0.038  # Guarantee full 100% peak brilliance for at least 38ms
        self.shockwave_radius = 0.0
        self.shockwave_active = True

        # In Overdrive, Classic Rapid, Strobe Blitz, or Album Art modes, launch machine-gun multi-flash burst
        if self.overdrive_mode or self.mode in (MODE_CLASSIC_RAPID, MODE_PSYCHO_OVERDRIVE, MODE_STROBE_BLITZ, MODE_ALBUM_ART):
            self.burst_remaining = 3  # Fire 3 rapid strobe micro-flashes per kick
            self.burst_timer = 0.0
            self.burst_is_on = True

        # Screen impact shake on heavy kicks
        if self.overdrive_mode or self.mode in (MODE_CLASSIC_RAPID, MODE_STROBE_2_0, MODE_BASS_ONLY):
            self.shake_decay = 0.16 if (self.mode == MODE_STROBE_2_0 and getattr(self, "is_chorus_active", False)) else 0.12
            self.shake_x = random.randint(-10, 10) if (self.mode == MODE_STROBE_2_0 and getattr(self, "is_chorus_active", False)) else random.randint(-8, 8)
            self.shake_y = random.randint(-8, 8) if (self.mode == MODE_STROBE_2_0 and getattr(self, "is_chorus_active", False)) else random.randint(-6, 6)

        # Ping-pong alternate between left & right monitors
        self.alternating_side = 1 - self.alternating_side
        if self.alternating_side == 0:
            self.kick_intensity_left = 1.0
        else:
            self.kick_intensity_right = 1.0

        # Advance colors with high contrast and melody pitch alignment
        if self.mode == MODE_STROBE_2_0:
            # Mode 2.0: Synchronize color selection with melody pitch and harmonic downbeat progression
            pal_len = len(self.palette_colors)
            pitch_idx = getattr(self, "current_pitch_idx", 0)
            pitch_offset = int((pitch_idx / 12.0) * pal_len)
            self.color_step = (self.color_step + 1) % pal_len
            base_idx = (self.color_step + pitch_offset) % pal_len
            self.current_color = self.palette_colors[base_idx]

            # In chorus: high-contrast complementary interval, explosive burst, and shockwave
            # In buildup: accelerating tension burst with harmonic progression
            # In verse: clean, punchy single/dual pulse
            if getattr(self, "is_chorus_active", False):
                sec_step = max(1, pal_len // 2)
                self.burst_remaining = max(self.burst_remaining, 6)
                self.shake_decay = 0.18
                self.shockwave_active = True
                self.shockwave_radius = 0.0
            elif getattr(self, "is_buildup_active", False):
                sec_step = max(1, pal_len // 3)
                self.burst_remaining = max(self.burst_remaining, 3)
                self.shake_decay = 0.12
            else:
                sec_step = 1
                self.shake_decay = 0.08

            sec_idx = (base_idx + sec_step) % pal_len
            self.secondary_color = self.palette_colors[sec_idx]
        elif self.palette_name == "Rainbow Cycle":
            step = 0.18 if self.overdrive_mode else 0.125
            self.rainbow_hue = (self.rainbow_hue + step) % 1.0
            r, g, b = colorsys.hsv_to_rgb(self.rainbow_hue, 1.0, 1.0)
            self.current_color = (int(r * 255), int(g * 255), int(b * 255))
            r2, g2, b2 = colorsys.hsv_to_rgb((self.rainbow_hue + 0.5) % 1.0, 1.0, 1.0)
            self.secondary_color = (int(r2 * 255), int(g2 * 255), int(b2 * 255))
        elif self.mode == MODE_CHAOS_BLITZ:
            choices = [c for c in self.palette_colors if c != self.current_color]
            self.current_color = random.choice(choices) if choices else random.choice(self.palette_colors)
            self.secondary_color = random.choice(self.palette_colors)
        elif self.mode == MODE_MONOCHROME:
            self.current_color = (255, 255, 255)
            self.secondary_color = (255, 255, 255)
        elif self.mode == MODE_RED_ONLY:
            self.current_color = (255, 0, 0)
            self.secondary_color = (255, 0, 0)
        elif self.mode == MODE_SPECTRUM:
            spec_col = self.last_render_rgb_0 if max(self.last_render_rgb_0) > 0 else (255, 80, 20)
            self.current_color = spec_col
            self.secondary_color = spec_col
        else:
            self.color_step = (self.color_step + 1) % len(self.palette_colors)
            self.current_color = self.palette_colors[self.color_step]
            sec_idx = (self.color_step + len(self.palette_colors) // 2) % len(self.palette_colors)
            self.secondary_color = self.palette_colors[sec_idx]

        # Arm peripheral flash for 80ms with full saturated palette color
        self.peripheral_flash_id += 1
        self.peripheral_flash_until = time.perf_counter() + 0.080
        if self.mode == MODE_MONOCHROME:
            self.peripheral_flash_color_left = (255, 255, 255)
            self.peripheral_flash_color_right = (255, 255, 255)
        elif self.mode == MODE_RED_ONLY:
            self.peripheral_flash_color_left = (255, 0, 0)
            self.peripheral_flash_color_right = (255, 0, 0)
        elif self.mode == MODE_SPECTRUM:
            spec_col = self.last_render_rgb_0 if max(self.last_render_rgb_0) > 0 else (255, 80, 20)
            self.peripheral_flash_color_left = spec_col
            self.peripheral_flash_color_right = spec_col
        else:
            self.peripheral_flash_color_left = self.current_color
            self.peripheral_flash_color_right = (
                self.secondary_color
                if self.dual_scheme in (DUAL_SCHEME_CONTRAST, DUAL_SCHEME_ALTERNATING)
                else self.current_color
            )

    def trigger_snare(self):
        """Trigger snare/clap accent flash."""
        self.music_energy = max(self.music_energy, 0.5)
        self.is_audio_silent = False
        self.snare_intensity = 1.0
        self.snare_hold_timer = 0.030
        if self.overdrive_mode:
            self.burst_remaining = max(self.burst_remaining, 2)
        # Arm peripheral and PC flash for 60ms accent if not in an active longer flash
        now = time.perf_counter()
        if now + 0.060 > self.peripheral_flash_until:
            self.peripheral_flash_id += 1
            self.peripheral_flash_until = now + 0.060
            if self.mode == MODE_MONOCHROME:
                self.peripheral_flash_color_left = (255, 255, 255)
                self.peripheral_flash_color_right = (255, 255, 255)
            elif self.mode == MODE_RED_ONLY:
                self.peripheral_flash_color_left = (255, 0, 0)
                self.peripheral_flash_color_right = (255, 0, 0)
            elif self.mode == MODE_SPECTRUM:
                spec_col = self.last_render_rgb_0 if max(self.last_render_rgb_0) > 0 else (255, 255, 255)
                self.peripheral_flash_color_left = spec_col
                self.peripheral_flash_color_right = spec_col
            else:
                self.peripheral_flash_color_left = (
                    self.secondary_color
                    if self.dual_scheme in (DUAL_SCHEME_CONTRAST, DUAL_SCHEME_ALTERNATING)
                    else self.current_color
                )
                self.peripheral_flash_color_right = self.secondary_color

    def trigger_hihat(self):
        """Trigger hi-hat rapid micro-sparkle strobe."""
        self.music_energy = max(self.music_energy, 0.5)
        self.is_audio_silent = False
        self.hihat_intensity = 1.0
        self.hihat_hold_timer = 0.020
        # Arm peripheral flash for 35ms micro-sparkle if not in an active longer kick flash
        now = time.perf_counter()
        if now + 0.035 > self.peripheral_flash_until:
            self.peripheral_flash_id += 1
            self.peripheral_flash_until = now + 0.035
            if self.mode == MODE_MONOCHROME:
                hi_col = (255, 255, 255)
            elif self.mode == MODE_RED_ONLY:
                hi_col = (255, 0, 0)
            else:
                hi_col = (200, 255, 255)
            self.peripheral_flash_color_left = hi_col
            self.peripheral_flash_color_right = hi_col

    def trigger_drop(self):
        """Trigger massive bass drop surge."""
        self.music_energy = max(self.music_energy, 0.5)
        self.is_audio_silent = False
        self.drop_intensity = 1.0
        self.kick_intensity = 1.0
        self.snare_intensity = 1.0
        self.kick_hold_timer = 0.060
        self.burst_remaining = 5  # 5-pulse machine-gun blast
        self.shockwave_active = True
        self.shockwave_radius = 0.0

        # Massive bass drop: 90ms blast
        self.peripheral_flash_id += 1
        self.peripheral_flash_until = time.perf_counter() + 0.090
        drop_col = (255, 0, 0) if self.mode == MODE_RED_ONLY else (255, 255, 255)
        self.peripheral_flash_color_left = drop_col
        self.peripheral_flash_color_right = drop_col

    def update(self, dt, audio_state):
        """Update strobe decay physics, burst pulse generator, and shake."""
        self.music_energy = max(
            audio_state.get("total_level", 0.0) * 0.75,
            audio_state.get("bass_level", 0.0) * 0.85,
            audio_state.get("mid_level", 0.0) * 0.55,
        )
        self.is_paused = bool(audio_state.get("is_paused", False)) and (self.music_energy < 0.05)
        self.is_audio_silent = (self.music_energy < 0.02) or (audio_state.get("raw_peak", 1.0) < 0.0005) or self.is_paused

        # Strobe 2.0 State Tracking (Melody Pitch & Structure: Verse, Buildup, Chorus)
        self.current_pitch_idx = int(audio_state.get("pitch_idx", 0))
        self.current_pitch_name = audio_state.get("pitch_name", "C")
        self.pitch_confidence = float(audio_state.get("pitch_confidence", 0.0))
        self.is_chorus_active = bool(audio_state.get("is_chorus", False))
        self.is_buildup_active = bool(audio_state.get("is_buildup", False))
        self.is_verse_active = bool(audio_state.get("is_verse", True))
        self.current_section_name = str(audio_state.get("section_name", "VERSE"))
        self.section_energy_val = float(audio_state.get("section_energy", 1.0))

        if self.is_audio_silent:
            # When music is off, silent, or paused, disarm bursts and peripheral flashes
            self.burst_remaining = 0
            self.shockwave_active = False
            self.peripheral_flash_until = 0.0
        else:
            if self.mode == MODE_BASS_ONLY:
                # Bass Only Mode: strictly triggers on kicks, 808s, and heavy sub-bass hits
                # All snares, hi-hats, mids, and non-bass transients are completely ignored
                if audio_state.get("is_kick", False) or audio_state.get("is_808", False):
                    self.trigger_kick()
                elif audio_state.get("is_drop", False) and audio_state.get("sub_bass_level", 0.0) > 0.40:
                    self.trigger_kick()
                self.snare_intensity = 0.0
                self.hihat_intensity = 0.0
                self.drop_intensity = 0.0
            else:
                if audio_state.get("is_drop", False):
                    self.trigger_drop()
                if audio_state.get("is_kick", False) or audio_state.get("is_808", False):
                    self.trigger_kick()
                if audio_state.get("is_snare", False):
                    self.trigger_snare()
                if audio_state.get("is_hihat", False) and self.mode != MODE_STROBE_2_0:
                    self.trigger_hihat()

        # Stroboscopic Multi-Pulse Burst Generator
        if self.burst_remaining > 0:
            self.burst_timer += dt
            if self.burst_timer >= self.burst_period:
                self.burst_timer = 0.0
                self.burst_is_on = not self.burst_is_on
                if self.burst_is_on:
                    self.peripheral_flash_id += 1
                else:
                    self.burst_remaining -= 1
                    if self.burst_remaining <= 0:
                        self.burst_is_on = True

        # Decay kick flash with peak-hold (prevents flash from decaying before render)
        if self.kick_hold_timer > 0:
            self.kick_hold_timer -= dt
        else:
            decay_multiplier = 1.2 if self.overdrive_mode else 0.8
            actual_decay = (self.decay_rate * decay_multiplier) * (0.5 if self.safe_mode or self.mode == MODE_SMOOTH_PULSE else 1.0)
            self.kick_intensity = max(0.0, self.kick_intensity - actual_decay * dt)
            self.kick_intensity_left = max(0.0, self.kick_intensity_left - actual_decay * dt)
            self.kick_intensity_right = max(0.0, self.kick_intensity_right - actual_decay * dt)

        # Decay snare and hi-hat with peak-hold
        if self.snare_hold_timer > 0:
            self.snare_hold_timer -= dt
        else:
            self.snare_intensity = max(0.0, self.snare_intensity - (self.decay_rate * 1.3) * dt)

        if self.hihat_hold_timer > 0:
            self.hihat_hold_timer -= dt
        else:
            self.hihat_intensity = max(0.0, self.hihat_intensity - (self.decay_rate * 1.8) * dt)

        self.drop_intensity = max(0.0, self.drop_intensity - (self.decay_rate * 0.7) * dt)

        # Decay screen shake
        if self.shake_decay > 0:
            self.shake_decay = max(0.0, self.shake_decay - dt)
            if self.shake_decay == 0.0:
                self.shake_x = 0
                self.shake_y = 0
            else:
                self.shake_x = random.randint(-4, 4)
                self.shake_y = random.randint(-3, 3)

        # Expand shockwave
        if self.shockwave_active:
            wave_speed = 5.0 if self.overdrive_mode else 3.5
            self.shockwave_radius += (self.shockwave_max_radius * wave_speed) * dt
            if self.shockwave_radius >= self.shockwave_max_radius:
                self.shockwave_active = False

    def _calc_color_and_intensity(self, base_col, intensity, audio_state):
        """Calculate final RGB with vibrant ambient music glow, extreme strobe contrast, burst chopping, and phosphor white flares."""
        if self.solid_color_active:
            return self.solid_color, 1.0

        is_paused = bool(audio_state.get("is_paused", False))
        if self.mode == MODE_BASS_ONLY:
            # Pure Bass Mode: energy derived strictly from low-end sub-bass and kick frequencies.
            # Mids, vocals, guitars, and highs have zero impact.
            music_energy = max(
                audio_state.get("bass_level", 0.0) * 0.90,
                audio_state.get("sub_bass_level", 0.0) * 1.0,
            )
            is_silent = (music_energy < 0.02) or (is_paused and music_energy < 0.05)
            ambient_floor = min(0.18, max(0.0, (music_energy - 0.35) * 0.40))
        else:
            music_energy = max(
                audio_state.get("total_level", 0.0) * 0.75,
                audio_state.get("bass_level", 0.0) * 0.85,
                audio_state.get("mid_level", 0.0) * 0.55,
            )
            is_silent = (music_energy < 0.02) or (is_paused and music_energy < 0.05)
            ambient_floor = min(0.32, music_energy * 0.50)

        # True pitch black blackout whenever music is off, silent, or paused
        if is_silent:
            return (0, 0, 0), 0.0

        # Sync section states from audio_state if available
        if "is_chorus" in audio_state:
            self.is_chorus_active = bool(audio_state.get("is_chorus", False))
        if "is_buildup" in audio_state:
            self.is_buildup_active = bool(audio_state.get("is_buildup", False))
        if "is_verse" in audio_state:
            self.is_verse_active = bool(audio_state.get("is_verse", True))
        if "section_energy" in audio_state:
            self.section_energy_val = float(audio_state.get("section_energy", 1.0))
        if "section_name" in audio_state:
            self.current_section_name = str(audio_state.get("section_name", "VERSE"))

        # Strobe pulse gating (chopping for stroboscopic effect)
        chopped_intensity = intensity
        if (self.overdrive_mode or self.mode in (MODE_CLASSIC_RAPID, MODE_STROBE_BLITZ, MODE_ALBUM_ART)) and not self.safe_mode:
            if self.burst_remaining > 0 and not self.burst_is_on:
                chopped_intensity = 0.0  # Instant blackout between burst micro-flashes!

        if self.safe_mode or self.mode == MODE_SMOOTH_PULSE:
            eff_intensity = math.sin(min(1.0, 0.20 + ambient_floor * 0.40 + chopped_intensity * 0.80) * (math.pi / 2))
        elif self.mode in (MODE_CLASSIC_RAPID, MODE_PSYCHO_OVERDRIVE):
            # Classic rapid / overdrive blast: explosive flash with true pitch black between beat impacts
            if chopped_intensity > 0.01:
                eff_intensity = min(1.0, chopped_intensity * 1.35)
            else:
                eff_intensity = 0.0
        elif self.mode == MODE_BASS_ONLY:
            # Pure Bass Strobe: explosive flashes strictly on bass impacts with true pitch black between hits
            if chopped_intensity > 0.01:
                eff_intensity = min(1.0, chopped_intensity * 1.30)
            else:
                eff_intensity = ambient_floor  # Pure black unless sustaining heavy sub-bass
        elif self.mode == MODE_ALBUM_ART:
            # Album art sync: explosive saturated flashes of album colors with responsive ambient music floor
            if chopped_intensity > 0.01:
                eff_intensity = min(1.0, chopped_intensity * 1.30)
            else:
                eff_intensity = ambient_floor * 0.35
        elif self.mode == MODE_HARD_STROBE:
            # Classic concert strobe: deep contrast with pitch black between beats
            if chopped_intensity > 0.01:
                eff_intensity = min(1.0, chopped_intensity * 1.20)
            else:
                eff_intensity = 0.0
        elif self.mode == MODE_SPECTRUM:
            eff_intensity = max(0.18, min(1.0, 0.22 + audio_state.get("total_level", 0.0) * 0.45 + chopped_intensity * 0.65))
        elif self.mode == MODE_STROBE_2_0:
            # Strobe 2.0: Dynamic section physics with heavy 808 and snare drum dominance
            drum_strike = max(chopped_intensity, self.snare_intensity * 0.95)
            if self.is_chorus_active:
                # Chorus: Explosive stroboscopic impact with high contrast and deep blackouts between hits
                if drum_strike > 0.02:
                    eff_intensity = min(1.0, drum_strike * 1.35)
                else:
                    eff_intensity = ambient_floor * 0.08  # Deep contrast between explosive hits
            elif self.is_buildup_active:
                # Buildup: Tension climbing! Ambient background lifts as riser ascends
                sec_lift = min(0.35, max(0.0, (self.section_energy_val - 1.0) * 0.5)) if self.section_energy_val > 1.0 else 0.10
                if drum_strike > 0.02:
                    eff_intensity = min(1.0, drum_strike * 1.15 + sec_lift)
                else:
                    eff_intensity = min(0.60, ambient_floor * 0.40 + sec_lift)
            else:
                # Verse: Clean, punchy rhythmic groove with focused dynamic contrast
                if drum_strike > 0.02:
                    eff_intensity = min(1.0, drum_strike * 1.25)
                else:
                    eff_intensity = ambient_floor * 0.12
        else:
            # Strobe Blitz, Machine Gun, Chaos Blitz, Monochrome, Dual Strobe
            if chopped_intensity > 0.01:
                eff_intensity = min(1.0, chopped_intensity * 1.25)
            else:
                eff_intensity = 0.0

        # Perceptual gamma scaling so colors stay vivid, luminous, and rich
        gamma_intensity = min(1.0, eff_intensity ** 0.72)

        # Base RGB synthesis
        if self.mode == MODE_MONOCHROME:
            val = int(255 * gamma_intensity)
            r, g, b = val, val, val
        elif self.mode == MODE_RED_ONLY:
            val = int(255 * gamma_intensity)
            r, g, b = val, 0, 0
        elif self.mode == MODE_SPECTRUM:
            bass = audio_state.get("bass_level", 0.0)
            mid = audio_state.get("mid_level", 0.0)
            high = audio_state.get("high_level", 0.0)
            r = int(min(255, (bass * 240 + mid * 80) * (0.35 + gamma_intensity * 0.65)))
            g = int(min(255, (mid * 240 + high * 70) * (0.35 + gamma_intensity * 0.65)))
            b = int(min(255, (high * 240 + bass * 130) * (0.35 + gamma_intensity * 0.65)))
        else:
            cr, cg, cb = base_col
            r = int(cr * gamma_intensity)
            g = int(cg * gamma_intensity)
            b = int(cb * gamma_intensity)

            # On high-intensity beat peaks (>0.82), add phosphor white core brilliance
            if gamma_intensity > 0.82 and not self.safe_mode:
                white_flare = int(255 * (gamma_intensity - 0.82) / 0.18 * 0.45)
                r = min(255, r + white_flare)
                g = min(255, g + white_flare)
                b = min(255, b + white_flare)

        # Snare Accent Flash (suppressed in Bass Only mode)
        if self.snare_intensity > 0.01 and self.mode != MODE_BASS_ONLY:
            if self.mode == MODE_RED_ONLY:
                # In Red Only mode: boost red channel only, zero bleed into green/blue
                snare_add = int(140 * self.snare_intensity)
                r = min(255, r + snare_add)
            elif self.mode == MODE_STROBE_2_0:
                # In Strobe 2.0: Snap snare hits to secondary contrast color instead of flat whitewashing
                sec_c = getattr(self, "secondary_color", (0, 240, 255))
                snare_ratio = min(1.0, self.snare_intensity * 0.85)
                r = int(r * (1.0 - snare_ratio * 0.5) + sec_c[0] * snare_ratio)
                g = int(g * (1.0 - snare_ratio * 0.5) + sec_c[1] * snare_ratio)
                b = int(b * (1.0 - snare_ratio * 0.5) + sec_c[2] * snare_ratio)
                if self.is_chorus_active and self.snare_intensity > 0.70:
                    edge = int(60 * self.snare_intensity)
                    r = min(255, r + edge)
                    g = min(255, g + edge)
                    b = min(255, b + edge)
            elif self.mode in (MODE_DUAL_STROBE, MODE_MACHINE_GUN, MODE_PSYCHO_OVERDRIVE):
                snare_val = int(255 * self.snare_intensity)
                r = min(255, r + snare_val)
                g = min(255, g + snare_val)
                b = min(255, b + snare_val)
            else:
                snare_add = int(140 * self.snare_intensity)
                r = min(255, r + snare_add)
                g = min(255, g + snare_add)
                b = min(255, b + snare_add)

        # Hi-Hat Sparkle Strobe (High-frequency sizzle) - disabled in Strobe 2.0 and Bass Only mode
        if self.hihat_intensity > 0.01 and not self.safe_mode and self.mode not in (MODE_STROBE_2_0, MODE_BASS_ONLY):
            if self.mode == MODE_RED_ONLY:
                r = min(255, r + int(180 * self.hihat_intensity))
            else:
                hi_val = int(180 * self.hihat_intensity)
                r = min(255, r + int(hi_val * 0.7))
                g = min(255, g + hi_val)
                b = min(255, b + hi_val)

        # Heavy Drop / Blinding White Overdrive Blast
        if self.drop_intensity > 0.05 and not self.safe_mode:
            if self.mode == MODE_RED_ONLY:
                r = min(255, r + int(255 * self.drop_intensity))
            else:
                drop_white = int(255 * self.drop_intensity)
                r = min(255, r + drop_white)
                g = min(255, g + drop_white)
        # Clamp final RGB strictly to [0, 255] integer range to prevent Pygame color ValueError
        r = max(0, min(255, int(round(r))))
        g = max(0, min(255, int(round(g))))
        b = max(0, min(255, int(round(b))))
        return (r, g, b), eff_intensity

    def render(self, screen, audio_state, monitors=None, is_dual=False, is_client_sync=False):
        """Render strobe frames across one or both monitors with shake and multi-band effects."""
        music_energy = max(
            audio_state.get("total_level", 0.0) * 0.75,
            audio_state.get("bass_level", 0.0) * 0.85,
            audio_state.get("mid_level", 0.0) * 0.55,
        )
        self.music_energy = music_energy
        self.is_paused = bool(audio_state.get("is_paused", False)) and (music_energy < 0.05)
        self.is_audio_silent = (music_energy < 0.02) or (audio_state.get("raw_peak", 1.0) < 0.0005) or self.is_paused

        # Screen shake offset (bypassed in solid color mode)
        sx = 0 if self.solid_color_active else self.shake_x
        sy = 0 if self.solid_color_active else self.shake_y

        if is_dual and monitors and len(monitors) >= 2:
            self._render_dual(screen, audio_state, monitors, sx, sy, is_client_sync=is_client_sync)
        else:
            full_rect = pygame.Rect(sx, sy, self.width, self.height)
            if is_client_sync:
                # If host is alternating, pick the active side for single monitor client
                if self.dual_scheme == DUAL_SCHEME_ALTERNATING and self.alternating_side == 1:
                    chosen_rgb = self.last_render_rgb_1
                    chosen_eff = self.last_eff_intensity_1
                else:
                    chosen_rgb = self.last_render_rgb_0
                    chosen_eff = self.last_eff_intensity_0
                self._render_single(screen, audio_state, full_rect, monitor_idx=0, forced_rgb=chosen_rgb, forced_eff=chosen_eff)
            else:
                self._render_single(screen, audio_state, full_rect, monitor_idx=0)
                self.last_render_rgb_1 = self.last_render_rgb_0
                self.last_eff_intensity_1 = self.last_eff_intensity_0

    def _render_single(self, screen, audio_state, rect, custom_col=None, custom_intensity=None, monitor_idx=0, forced_rgb=None, forced_eff=None):
        if self.solid_color_active and forced_rgb is None:
            r, g, b = self.solid_color
            screen.fill((r, g, b), rect)
            if monitor_idx == 0:
                self.last_render_rgb_0 = (r, g, b)
                self.last_eff_intensity_0 = 1.0
            else:
                self.last_render_rgb_1 = (r, g, b)
                self.last_eff_intensity_1 = 1.0
            return (r, g, b), 1.0

        if forced_rgb is not None:
            r, g, b = forced_rgb
            eff_intensity = forced_eff if forced_eff is not None else 1.0
        else:
            base_col = custom_col if custom_col is not None else self.current_color
            intensity = custom_intensity if custom_intensity is not None else self.kick_intensity
            (r, g, b), eff_intensity = self._calc_color_and_intensity(base_col, intensity, audio_state)

        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))

        if monitor_idx == 0:
            self.last_render_rgb_0 = (r, g, b)
            self.last_eff_intensity_0 = eff_intensity
        else:
            self.last_render_rgb_1 = (r, g, b)
            self.last_eff_intensity_1 = eff_intensity

        if self.current_style == "Solid Fullscreen":
            screen.fill((r, g, b), rect)

        elif self.current_style == "Radial Shockwave":
            outer_dim = 0.20 if not self.safe_mode else 0.5
            screen.fill((int(r * outer_dim), int(g * outer_dim), int(b * outer_dim)), rect)

            cx = rect.x + rect.width // 2
            cy = rect.y + rect.height // 2
            max_rad = math.hypot(rect.width / 2, rect.height / 2)

            if self.shockwave_active and self.shockwave_radius > 0:
                progress = min(1.0, self.shockwave_radius / max_rad)
                wave_alpha = int(255 * (1.0 - progress) * eff_intensity)
                if wave_alpha > 0:
                    wave_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    ring_color = (min(255, r + 70), 0, 0, wave_alpha) if self.mode == MODE_RED_ONLY else (min(255, r + 70), min(255, g + 70), min(255, b + 70), wave_alpha)
                    thickness = max(10, int(50 * (1.0 - progress)))
                    curr_rad = int(progress * max_rad)
                    pygame.draw.circle(wave_surf, ring_color, (rect.width // 2, rect.height // 2), curr_rad, thickness)
                    screen.blit(wave_surf, (rect.x, rect.y))

            center_rad = int(min(rect.width, rect.height) * 0.40 * (0.8 + eff_intensity * 0.6))
            if center_rad > 0:
                center_surf = pygame.Surface((center_rad * 2, center_rad * 2), pygame.SRCALPHA)
                for ring in range(3, 0, -1):
                    rad = int(center_rad * (ring / 3.0))
                    alpha = int((110 / ring) * eff_intensity)
                    center_col = (min(255, r + 50), 0, 0, alpha) if self.mode == MODE_RED_ONLY else (min(255, r + 50), min(255, g + 50), min(255, b + 50), alpha)
                    pygame.draw.circle(
                        center_surf,
                        center_col,
                        (center_rad, center_rad),
                        rad,
                    )
                screen.blit(center_surf, (cx - center_rad, cy - center_rad))

        elif self.current_style == "Horizon Pulse":
            screen.fill((int(r * 0.12), int(g * 0.12), int(b * 0.12)), rect)
            cy = rect.y + rect.height // 2
            beam_height = int((rect.height * 0.7) * eff_intensity)
            if beam_height > 2:
                beam_surf = pygame.Surface((rect.width, beam_height), pygame.SRCALPHA)
                beam_surf.fill((r, g, b, int(240 * eff_intensity)))
                screen.blit(beam_surf, (rect.x, cy - beam_height // 2))

        return (r, g, b), eff_intensity

    def _render_dual(self, screen, audio_state, monitors, sx, sy, is_client_sync=False):
        m0 = monitors[0].rect.move(sx, sy)
        m1 = monitors[1].rect.move(sx, sy)

        if is_client_sync:
            self._render_single(screen, audio_state, m0, monitor_idx=0, forced_rgb=self.last_render_rgb_0, forced_eff=self.last_eff_intensity_0)
            self._render_single(screen, audio_state, m1, monitor_idx=1, forced_rgb=self.last_render_rgb_1, forced_eff=self.last_eff_intensity_1)
            return

        if self.dual_scheme == DUAL_SCHEME_SYNCED:
            self._render_single(screen, audio_state, m0, self.current_color, self.kick_intensity, monitor_idx=0)
            self._render_single(screen, audio_state, m1, self.current_color, self.kick_intensity, monitor_idx=1)

        elif self.dual_scheme == DUAL_SCHEME_ALTERNATING:
            # In Overdrive, ping-pong at blistering speeds
            ambient_floor = 0.08 if not self.safe_mode else 0.25
            left_int = self.kick_intensity_left + ambient_floor
            right_int = self.kick_intensity_right + ambient_floor

            self._render_single(screen, audio_state, m0, self.current_color, min(1.0, left_int), monitor_idx=0)
            self._render_single(screen, audio_state, m1, self.secondary_color, min(1.0, right_int), monitor_idx=1)

        elif self.dual_scheme == DUAL_SCHEME_CONTRAST:
            self._render_single(screen, audio_state, m0, self.current_color, self.kick_intensity, monitor_idx=0)
            self._render_single(screen, audio_state, m1, self.secondary_color, self.kick_intensity, monitor_idx=1)

        elif self.dual_scheme == DUAL_SCHEME_PANORAMIC:
            combined_rect = pygame.Rect(sx, sy, self.width, self.height)
            self._render_single(screen, audio_state, combined_rect, self.current_color, self.kick_intensity, monitor_idx=0)
            self.last_render_rgb_1 = self.last_render_rgb_0
            self.last_eff_intensity_1 = self.last_eff_intensity_0
