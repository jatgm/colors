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
    MODE_PSYCHO_OVERDRIVE,
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

    def cycle_palette(self):
        self.set_palette(self.palette_index + 1)
        return self.palette_name

    def cycle_mode(self):
        self.mode_index = (self.mode_index + 1) % len(STROBE_MODES)
        self.mode = STROBE_MODES[self.mode_index]
        return self.mode

    def cycle_style(self):
        self.style_index = (self.style_index + 1) % len(self.visual_styles)
        self.current_style = self.visual_styles[self.style_index]
        return self.current_style

    def cycle_dual_scheme(self):
        self.dual_scheme_index = (self.dual_scheme_index + 1) % len(DUAL_SCHEMES)
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
            "style": self.current_style,
            "dual_scheme": self.dual_scheme,
            "safe": bool(self.safe_mode),
            "overdrive": bool(self.overdrive_mode),
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

        if "dual_scheme" in pkt and pkt["dual_scheme"] != self.dual_scheme:
            self.dual_scheme = pkt["dual_scheme"]
            if self.dual_scheme in DUAL_SCHEMES:
                self.dual_scheme_index = DUAL_SCHEMES.index(self.dual_scheme)

        # 2. Physics & Engine Flags
        if "safe" in pkt:
            self.safe_mode = bool(pkt["safe"])
        if "overdrive" in pkt:
            self.overdrive_mode = bool(pkt["overdrive"])
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

    def update_client_fallback(self, dt):
        """Smoothly decay strobe intensity if sync stream drops or pauses."""
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
        In strobe modes: delivers 100% full-blast 255 peak color on beat impacts
        for exactly 80ms, followed by absolute pitch black (0, 0, 0) until the next beat.
        In smooth modes: delivers smooth pulsing rave colors.
        """
        is_strobe = not (self.safe_mode or self.mode == MODE_SMOOTH_PULSE)
        if not is_strobe:
            return self.last_render_rgb_0, self.last_render_rgb_1, False

        # Active strobe flash window
        if time.perf_counter() < self.peripheral_flash_until:
            def _scale_flash(col):
                r, g, b = col
                max_c = max(r, g, b, 1)
                scale = 255.0 / max_c
                return (min(255, int(r * scale)), min(255, int(g * scale)), min(255, int(b * scale)))

            col_left = _scale_flash(self.peripheral_flash_color_left)
            col_right = _scale_flash(self.peripheral_flash_color_right)
            return col_left, col_right, True

        # Blackout between beats
        return (0, 0, 0), (0, 0, 0), True

    def trigger_kick(self):
        """Trigger kick strobe flash & advance palette color with multi-pulse train."""
        self.kick_intensity = 1.0
        self.kick_hold_timer = 0.038  # Guarantee full 100% peak brilliance for at least 38ms
        self.shockwave_radius = 0.0
        self.shockwave_active = True

        # In Overdrive or Strobe Blitz modes, launch machine-gun multi-flash burst
        if self.overdrive_mode or self.mode in (MODE_PSYCHO_OVERDRIVE, MODE_STROBE_BLITZ):
            self.burst_remaining = 3  # Fire 3 rapid strobe micro-flashes per kick
            self.burst_timer = 0.0
            self.burst_is_on = True

        # Screen impact shake on heavy kicks
        if self.overdrive_mode:
            self.shake_decay = 0.12
            self.shake_x = random.randint(-8, 8)
            self.shake_y = random.randint(-6, 6)

        # Ping-pong alternate between left & right monitors
        self.alternating_side = 1 - self.alternating_side
        if self.alternating_side == 0:
            self.kick_intensity_left = 1.0
        else:
            self.kick_intensity_right = 1.0

        # Advance colors with high contrast
        if self.palette_name == "Rainbow Cycle":
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
        else:
            self.color_step = (self.color_step + 1) % len(self.palette_colors)
            self.current_color = self.palette_colors[self.color_step]
            sec_idx = (self.color_step + len(self.palette_colors) // 2) % len(self.palette_colors)
            self.secondary_color = self.palette_colors[sec_idx]

        # Arm peripheral flash for 80ms with full saturated palette color
        self.peripheral_flash_until = time.perf_counter() + 0.080
        self.peripheral_flash_color_left = self.current_color
        self.peripheral_flash_color_right = (
            self.secondary_color
            if self.dual_scheme in (DUAL_SCHEME_CONTRAST, DUAL_SCHEME_ALTERNATING)
            else self.current_color
        )

    def trigger_snare(self):
        """Trigger snare/clap accent flash."""
        self.snare_intensity = 1.0
        self.snare_hold_timer = 0.030
        if self.overdrive_mode:
            self.burst_remaining = max(self.burst_remaining, 2)

    def trigger_hihat(self):
        """Trigger hi-hat rapid micro-sparkle strobe."""
        self.hihat_intensity = 1.0
        self.hihat_hold_timer = 0.020

    def trigger_drop(self):
        """Trigger massive bass drop surge."""
        self.drop_intensity = 1.0
        self.kick_intensity = 1.0
        self.snare_intensity = 1.0
        self.kick_hold_timer = 0.060
        self.burst_remaining = 5  # 5-pulse machine-gun blast

        # Massive bass drop: 90ms phosphor white blast
        self.peripheral_flash_until = time.perf_counter() + 0.090
        self.peripheral_flash_color_left = (255, 255, 255)
        self.peripheral_flash_color_right = (255, 255, 255)

    def update(self, dt, audio_state):
        """Update strobe decay physics, burst pulse generator, and shake."""
        if audio_state.get("is_drop", False):
            self.trigger_drop()
        if audio_state.get("is_kick", False):
            self.trigger_kick()
        if audio_state.get("is_snare", False):
            self.trigger_snare()
        if audio_state.get("is_hihat", False):
            self.trigger_hihat()

        # Stroboscopic Multi-Pulse Burst Generator
        if self.burst_remaining > 0:
            self.burst_timer += dt
            if self.burst_timer >= self.burst_period:
                self.burst_timer = 0.0
                self.burst_is_on = not self.burst_is_on
                if not self.burst_is_on:
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
        # Dynamic Ambient Music Floor & Idle Breathing Pulse
        # Ensures screens and Razer peripherals are never a dead black void
        music_energy = max(
            audio_state.get("total_level", 0.0) * 0.75,
            audio_state.get("bass_level", 0.0) * 0.85,
            audio_state.get("mid_level", 0.0) * 0.55,
        )
        # Idle breathing glow: smooth 8-12% pulse so the user always sees it's active & listening
        t_now = time.time()
        idle_breath = 0.09 + 0.03 * math.sin(t_now * 2.2)
        ambient_floor = max(idle_breath, min(0.32, music_energy * 0.50))

        # Strobe pulse gating (chopping for stroboscopic effect)
        chopped_intensity = intensity
        if (self.overdrive_mode or self.mode == MODE_STROBE_BLITZ) and not self.safe_mode:
            if self.burst_remaining > 0 and not self.burst_is_on:
                chopped_intensity = 0.0  # Instant blackout between burst micro-flashes!

        if self.safe_mode or self.mode == MODE_SMOOTH_PULSE:
            eff_intensity = math.sin(min(1.0, 0.20 + ambient_floor * 0.40 + chopped_intensity * 0.80) * (math.pi / 2))
        elif self.mode == MODE_PSYCHO_OVERDRIVE:
            # Overdrive blast: explosive flash with true pitch black between beat impacts
            if chopped_intensity > 0.01:
                eff_intensity = min(1.0, chopped_intensity * 1.35)
            else:
                eff_intensity = (idle_breath * 0.35) if music_energy < 0.03 else 0.0
        elif self.mode == MODE_HARD_STROBE:
            # Classic concert strobe: deep contrast with pitch black between beats
            if chopped_intensity > 0.01:
                eff_intensity = min(1.0, chopped_intensity * 1.20)
            else:
                eff_intensity = (idle_breath * 0.25) if music_energy < 0.03 else 0.0
        elif self.mode == MODE_SPECTRUM:
            eff_intensity = max(0.18, min(1.0, 0.22 + audio_state.get("total_level", 0.0) * 0.45 + chopped_intensity * 0.65))
        else:
            # Strobe Blitz, Machine Gun, Chaos Blitz, Monochrome, Dual Strobe
            if chopped_intensity > 0.01:
                eff_intensity = min(1.0, chopped_intensity * 1.25)
            else:
                eff_intensity = (idle_breath * 0.30) if music_energy < 0.03 else 0.0

        # Perceptual gamma scaling so colors stay vivid, luminous, and rich
        gamma_intensity = min(1.0, eff_intensity ** 0.72)

        # Base RGB synthesis
        if self.mode == MODE_MONOCHROME:
            val = int(255 * gamma_intensity)
            r, g, b = val, val, val
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

        # Snare Accent Flash
        if self.snare_intensity > 0.01:
            if self.mode in (MODE_DUAL_STROBE, MODE_MACHINE_GUN, MODE_PSYCHO_OVERDRIVE):
                snare_val = int(255 * self.snare_intensity)
                r = min(255, r + snare_val)
                g = min(255, g + snare_val)
                b = min(255, b + snare_val)
            else:
                snare_add = int(140 * self.snare_intensity)
                r = min(255, r + snare_add)
                g = min(255, g + snare_add)
                b = min(255, b + snare_add)

        # Hi-Hat Sparkle Strobe (High-frequency sizzle)
        if self.hihat_intensity > 0.01 and not self.safe_mode:
            hi_val = int(180 * self.hihat_intensity)
            r = min(255, r + int(hi_val * 0.7))
            g = min(255, g + hi_val)
            b = min(255, b + hi_val)

        # Heavy Drop / Blinding White Overdrive Blast
        if self.drop_intensity > 0.05 and not self.safe_mode:
            drop_white = int(255 * self.drop_intensity)
            r = min(255, r + drop_white)
            g = min(255, g + drop_white)
            b = min(255, b + drop_white)

        return (r, g, b), eff_intensity

    def render(self, screen, audio_state, monitors=None, is_dual=False, is_client_sync=False):
        """Render strobe frames across one or both monitors with shake and multi-band effects."""
        # Screen shake offset
        sx, sy = self.shake_x, self.shake_y

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
        if forced_rgb is not None:
            r, g, b = forced_rgb
            eff_intensity = forced_eff if forced_eff is not None else 1.0
        else:
            base_col = custom_col if custom_col is not None else self.current_color
            intensity = custom_intensity if custom_intensity is not None else self.kick_intensity
            (r, g, b), eff_intensity = self._calc_color_and_intensity(base_col, intensity, audio_state)

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
                    ring_color = (min(255, r + 70), min(255, g + 70), min(255, b + 70), wave_alpha)
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
                    pygame.draw.circle(
                        center_surf,
                        (min(255, r + 50), min(255, g + 50), min(255, b + 50), alpha),
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
