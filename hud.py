"""
Sleek Sci-Fi / Cyberpunk HUD (Heads-Up Display) and interactive UI.
Features translucent frosted glassmorphism panels, angular bracketed telemetry frames,
clean monospace typography, glowing minimalist status pips, and responsive controls.
STRICT REQUIREMENT: Zero emojis. Pure high-tech telemetry and geometric accents.
"""

import time
import math
import pygame
from config import (
    HUD_AUTO_HIDE_DELAY,
    HUD_FADE_SPEED,
    MIN_SENSITIVITY,
    MAX_SENSITIVITY,
    MIN_DECAY_RATE,
    MAX_DECAY_RATE,
    DEFAULT_PREAMP_GAIN,
    MIN_PREAMP_GAIN,
    MAX_PREAMP_GAIN,
    MODE_STROBE_2_0,
    MODE_RED_ONLY,
    MODE_ALBUM_ART,
    PALETTE_ALBUM_ART,
    SOLID_COLORS,
    SOLID_COLOR_NAMES,
)
from sync_manager import (
    ROLE_STANDALONE,
    ROLE_HOST,
    ROLE_CLIENT,
    BT_RFCOMM_CHANNEL,
    TCP_PORT,
)


class HUD:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.active_mon_rect = pygame.Rect(0, 0, width, height)

        # Monospace / Sci-Fi Telemetry Fonts
        pygame.font.init()
        font_stack = "Consolas, Lucida Console, Segoe UI, monospace"
        self.font_title = pygame.font.SysFont(font_stack, 15, bold=True)
        self.font_section = pygame.font.SysFont(font_stack, 11, bold=True)
        self.font_main = pygame.font.SysFont(font_stack, 11, bold=True)
        self.font_small = pygame.font.SysFont(font_stack, 10)
        self.font_tiny = pygame.font.SysFont(font_stack, 9)
        self.font_warning = pygame.font.SysFont(font_stack, 12)

        # Inactivity & visibility state
        self.visible = True
        self.alpha = 255.0
        self.last_interaction_time = time.time()
        self.manually_hidden = False

        # Modals
        self.warning_dismissed = False
        self.show_sync_modal = False

        # Direct host manual input
        self.entering_custom_host = False
        self.custom_host_input = ""

        # Active dragging state for sliders and waveform
        self.dragging_slider = None
        self.dragging_waveform = False
        self.mouse_hover_pos = None

        # Discovered host button rectangles
        self.host_item_rects = []

        # Solid color lighting controls & swatches
        self.solid_swatch_rects = []
        self.btn_solid_toggle = None
        self.solid_name_rect = None

        self._build_layout()

    def resize(self, width, height, active_mon_rect=None):
        self.width = max(100, width)
        self.height = max(100, height)
        if active_mon_rect:
            self.active_mon_rect = active_mon_rect
        else:
            self.active_mon_rect = pygame.Rect(0, 0, self.width, self.height)
        self._build_layout()

    def set_active_monitor(self, mon_rect):
        if self.active_mon_rect != mon_rect:
            self.active_mon_rect = mon_rect
            self._build_layout()

    def notify_interaction(self):
        self.last_interaction_time = time.time()
        if not self.manually_hidden:
            self.visible = True

    def toggle_hud(self):
        self.manually_hidden = not self.manually_hidden
        self.visible = not self.manually_hidden
        self.last_interaction_time = time.time()

    def toggle_sync_modal(self):
        self.show_sync_modal = not self.show_sync_modal
        self.notify_interaction()

    def handle_text_input(self, event, sync_mgr):
        """Handle typing when entering manual IP or Bluetooth MAC."""
        if not self.show_sync_modal or not self.entering_custom_host:
            return False

        if event.key == pygame.K_ESCAPE:
            self.entering_custom_host = False
            return True
        elif event.key == pygame.K_BACKSPACE:
            self.custom_host_input = self.custom_host_input[:-1]
            return True
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._submit_custom_host(sync_mgr)
            return True
        elif event.unicode and len(self.custom_host_input) < 40:
            if event.unicode.isprintable():
                self.custom_host_input += event.unicode
                return True
        return False

    def _submit_custom_host(self, sync_mgr):
        raw = self.custom_host_input.strip()
        if not raw:
            self.entering_custom_host = False
            return

        is_bt = (":" in raw and len(raw) == 17) or ("-" in raw and len(raw) == 17)
        if is_bt:
            formatted_mac = raw.replace("-", ":").upper()
            host_entry = {
                "name": f"[BT] {formatted_mac}",
                "address": formatted_mac,
                "bt_mac": formatted_mac,
                "port": sync_mgr.bt_channel,
                "type": "Bluetooth Node",
            }
        else:
            host_entry = {
                "name": f"[NET] {raw}",
                "address": raw,
                "port": sync_mgr.tcp_port,
                "bt_mac": "",
                "type": "Network Host",
            }
        sync_mgr.connect_to_host(host_entry)
        self.entering_custom_host = False

    def _build_layout(self):
        """Build sleek, compact modern HUD layout with low vertical footprint."""
        mon = self.active_mon_rect
        panel_w = min(1040, mon.width - 32)
        panel_h = 282
        panel_x = mon.x + (mon.width - panel_w) // 2
        panel_y = mon.y + mon.height - panel_h - 14

        self.panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        # Top Right: Now Playing Native Album Cover Artwork Card
        card_w = min(220, max(180, (panel_w - 60) // 4))
        card_h = 40
        card_x = panel_x + panel_w - card_w - 18
        card_y = panel_y + 28
        self.card_album_art = pygame.Rect(card_x, card_y, card_w, card_h)

        # Waveform Song Progress Bar Deck (height 80px for rich dynamic response)
        wf_x = panel_x + 18
        wf_y = panel_y + 72
        wf_w = panel_w - 36
        wf_h = 80
        self.waveform_rect = pygame.Rect(wf_x, wf_y, wf_w, wf_h)

        # Middle: 3 Sliders Side-by-Side in 1 sleek row
        pad_x = 18
        avail_w = panel_w - 2 * pad_x
        gap_sliders = 14
        col_w = (avail_w - 2 * gap_sliders) // 3
        s_y = panel_y + 158

        # Slider 1: SENS
        lbl_w1 = 34
        val_w1 = 50
        bar_w1 = max(40, col_w - lbl_w1 - val_w1 - 8)
        self.slider_sens_rect = pygame.Rect(panel_x + pad_x + lbl_w1 + 4, s_y + 3, bar_w1, 10)

        # Slider 2: GAIN
        col2_x = panel_x + pad_x + col_w + gap_sliders
        lbl_w2 = 34
        val_w2 = 50
        bar_w2 = max(40, col_w - lbl_w2 - val_w2 - 8)
        self.slider_gain_rect = pygame.Rect(col2_x + lbl_w2 + 4, s_y + 3, bar_w2, 10)

        # Slider 3: DECAY
        col3_x = col2_x + col_w + gap_sliders
        lbl_w3 = 40
        val_w3 = 42
        bar_w3 = max(40, col_w - lbl_w3 - val_w3 - 8)
        self.slider_decay_rect = pygame.Rect(col3_x + lbl_w3 + 4, s_y + 3, bar_w3, 10)

        # Solid Color Lighting Control Deck & Swatches Bar
        solid_y = panel_y + 182
        solid_h = 22
        btn_solid_w = 100
        self.btn_solid_toggle = pygame.Rect(panel_x + pad_x, solid_y, btn_solid_w, solid_h)

        name_badge_w = 76
        swatches_avail_w = avail_w - btn_solid_w - name_badge_w - 18
        num_swatches = len(SOLID_COLORS)
        swatch_gap = 3
        swatch_w = max(14, min(34, (swatches_avail_w - (num_swatches - 1) * swatch_gap) // num_swatches))
        swatch_h = 18
        swatch_y = solid_y + 2
        swatch_start_x = panel_x + pad_x + btn_solid_w + 10

        self.solid_swatch_rects = []
        for i, (c_name, c_rgb) in enumerate(SOLID_COLORS):
            sx = swatch_start_x + i * (swatch_w + swatch_gap)
            s_rect = pygame.Rect(sx, swatch_y, swatch_w, swatch_h)
            self.solid_swatch_rects.append((s_rect, i, c_name, c_rgb))

        badge_x = swatch_start_x + num_swatches * (swatch_w + swatch_gap) + 6
        self.solid_name_rect = pygame.Rect(badge_x, solid_y, name_badge_w, solid_h)

        # Bottom Command Matrix: Balanced 2-Row Arrangement
        btn_h = 24
        gap1 = 5
        bw1 = (avail_w - 6 * gap1) // 7
        by1 = panel_y + 210
        self.btn_mode = pygame.Rect(panel_x + pad_x, by1, bw1, btn_h)
        self.btn_mode_2_0 = pygame.Rect(panel_x + pad_x + (bw1 + gap1), by1, bw1, btn_h)
        self.btn_palette = pygame.Rect(panel_x + pad_x + (bw1 + gap1) * 2, by1, bw1, btn_h)
        self.btn_style = pygame.Rect(panel_x + pad_x + (bw1 + gap1) * 3, by1, bw1, btn_h)
        self.btn_album_art = pygame.Rect(panel_x + pad_x + (bw1 + gap1) * 4, by1, bw1, btn_h)
        self.btn_dualfx = pygame.Rect(panel_x + pad_x + (bw1 + gap1) * 5, by1, bw1, btn_h)
        self.btn_displays = pygame.Rect(panel_x + pad_x + (bw1 + gap1) * 6, by1, bw1, btn_h)

        # Row 2 (Engine, Hardware & Sync Controls - 7 buttons)
        gap2 = 5
        bw2 = (avail_w - 6 * gap2) // 7
        by2 = by1 + 28
        self.btn_device = pygame.Rect(panel_x + pad_x, by2, bw2, btn_h)
        self.btn_sync = pygame.Rect(panel_x + pad_x + (bw2 + gap2), by2, bw2, btn_h)
        self.btn_overdrive = pygame.Rect(panel_x + pad_x + (bw2 + gap2) * 2, by2, bw2, btn_h)
        self.btn_safe = pygame.Rect(panel_x + pad_x + (bw2 + gap2) * 3, by2, bw2, btn_h)
        self.btn_razer = pygame.Rect(panel_x + pad_x + (bw2 + gap2) * 4, by2, bw2, btn_h)
        self.btn_room_lights = pygame.Rect(panel_x + pad_x + (bw2 + gap2) * 5, by2, bw2, btn_h)
        self.btn_lenovo = pygame.Rect(panel_x + pad_x + (bw2 + gap2) * 6, by2, bw2, btn_h)

    def _get_warning_dialog_layout(self):
        """Unified hitbox and layout geometry for the photosensitivity safety modal."""
        mon = self.active_mon_rect
        dialog_w = min(640, mon.width - 40)
        dialog_h = 300
        dx = mon.x + (mon.width - dialog_w) // 2
        dy = mon.y + (mon.height - dialog_h) // 2
        dialog_rect = pygame.Rect(dx, dy, dialog_w, dialog_h)

        btn_w1 = min(270, (dialog_w - 70) // 2)
        btn_w2 = min(290, dialog_w - 70 - btn_w1)
        btn_start = pygame.Rect(dx + 30, dy + 225, btn_w1, 48)
        btn_safe = pygame.Rect(dx + 30 + btn_w1 + 10, dy + 225, btn_w2, 48)

        return dialog_rect, btn_start, btn_safe

    def _get_sync_modal_layout(self):
        """Unified hitbox and layout geometry for multi-system Bluetooth & network sync modal."""
        mon = self.active_mon_rect
        modal_w = min(680, mon.width - 40)
        modal_h = 440
        mx = mon.x + (mon.width - modal_w) // 2
        my = mon.y + (mon.height - modal_h) // 2
        modal_rect = pygame.Rect(mx, my, modal_w, modal_h)

        btn_close = pygame.Rect(mx + modal_w - 95, my + 15, 80, 28)

        tab_w = (modal_w - 60) // 3
        tab_y = my + 60
        tab_stand = pygame.Rect(mx + 20, tab_y, tab_w, 34)
        tab_host = pygame.Rect(mx + 30 + tab_w, tab_y, tab_w, 34)
        tab_client = pygame.Rect(mx + 40 + tab_w * 2, tab_y, tab_w, 34)

        content_box = pygame.Rect(mx + 20, my + 105, modal_w - 40, 315)
        action_y = content_box.y + content_box.height - 48

        btn_rescan = pygame.Rect(content_box.x + 20, action_y, 120, 32)
        btn_manual = pygame.Rect(content_box.x + 150, action_y, 190, 32)
        inp_rect = pygame.Rect(content_box.x + 150, action_y, 280, 32)
        btn_submit = pygame.Rect(content_box.x + 440, action_y, 100, 32)
        btn_disc = pygame.Rect(content_box.x + content_box.width - 140, action_y, 120, 32)

        return {
            "modal_rect": modal_rect,
            "btn_close": btn_close,
            "tab_stand": tab_stand,
            "tab_host": tab_host,
            "tab_client": tab_client,
            "content_box": content_box,
            "btn_rescan": btn_rescan,
            "btn_manual": btn_manual,
            "inp_rect": inp_rect,
            "btn_submit": btn_submit,
            "btn_disc": btn_disc,
        }

    def handle_mouse_down(self, pos, audio_mgr, visualizer, display_mgr, sync_mgr, on_display_change, razer_mgr=None, happylighting_mgr=None, lenovo_mgr=None, media_mgr=None):
        self.notify_interaction()

        # Warning Dialog
        if not self.warning_dismissed:
            dialog_rect, btn_start, btn_safe_start = self._get_warning_dialog_layout()
            if btn_start.collidepoint(pos):
                self.warning_dismissed = True
                return True
            elif btn_safe_start.collidepoint(pos):
                visualizer.safe_mode = True
                self.warning_dismissed = True
                return True
            return False

        # Sync Modal
        if self.show_sync_modal:
            layout = self._get_sync_modal_layout()
            if layout["btn_close"].collidepoint(pos):
                self.show_sync_modal = False
                self.entering_custom_host = False
                return True

            if layout["tab_stand"].collidepoint(pos):
                sync_mgr.set_role(ROLE_STANDALONE)
                self.entering_custom_host = False
                return True
            elif layout["tab_host"].collidepoint(pos):
                sync_mgr.set_role(ROLE_HOST)
                self.entering_custom_host = False
                return True
            elif layout["tab_client"].collidepoint(pos):
                sync_mgr.set_role(ROLE_CLIENT)
                return True

            if sync_mgr.role == ROLE_CLIENT:
                for r_item, host_data in self.host_item_rects:
                    if r_item.collidepoint(pos):
                        sync_mgr.connect_to_host(host_data)
                        return True

                if sync_mgr.client_sock:
                    if layout["btn_disc"].collidepoint(pos):
                        sync_mgr.disconnect_client()
                        return True
                else:
                    if layout["btn_rescan"].collidepoint(pos):
                        sync_mgr.start_client_search()
                        return True

                    if self.entering_custom_host:
                        if layout["btn_submit"].collidepoint(pos):
                            self._submit_custom_host(sync_mgr)
                            return True
                    else:
                        if layout["btn_manual"].collidepoint(pos):
                            self.entering_custom_host = True
                            return True

            return True

        if not self.visible or self.alpha < 30:
            return False

        # Waveform Progress Bar Deck Interactive Seeking
        if hasattr(self, "waveform_rect") and self.waveform_rect.collidepoint(pos):
            time_deck_w = 148
            inner_w = max(10, self.waveform_rect.width - time_deck_w - 20)
            wf_start = self.waveform_rect.x + 8
            # Only seek if click is within the waveform progress bar area
            if wf_start <= pos[0] <= wf_start + inner_w:
                rel_x = pos[0] - wf_start
                prog = max(0.0, min(1.0, rel_x / inner_w))
                self.dragging_waveform = True
                if media_mgr and hasattr(media_mgr, "seek"):
                    media_mgr.seek(prog)
            return True

        # Sliders
        if self.slider_sens_rect.inflate(10, 10).collidepoint(pos):
            self.dragging_slider = "sens"
            self._update_slider_pos(pos[0], self.slider_sens_rect, MIN_SENSITIVITY, MAX_SENSITIVITY, audio_mgr.set_sensitivity)
            return True
        elif self.slider_gain_rect.inflate(10, 10).collidepoint(pos):
            self.dragging_slider = "gain"
            self._update_slider_pos(pos[0], self.slider_gain_rect, MIN_PREAMP_GAIN, MAX_PREAMP_GAIN, audio_mgr.set_preamp_gain)
            return True
        elif self.slider_decay_rect.inflate(10, 10).collidepoint(pos):
            self.dragging_slider = "decay"
            self._update_slider_pos(pos[0], self.slider_decay_rect, MIN_DECAY_RATE, MAX_DECAY_RATE, visualizer.set_decay_rate)
            return True

        # Solid Lighting Controls
        if hasattr(self, "btn_solid_toggle") and self.btn_solid_toggle and self.btn_solid_toggle.collidepoint(pos):
            visualizer.toggle_solid_color()
            return True

        if hasattr(self, "solid_swatch_rects"):
            for s_rect, idx, s_name, s_rgb in self.solid_swatch_rects:
                if s_rect.collidepoint(pos):
                    visualizer.set_solid_color(idx, activate=True)
                    return True

        if hasattr(self, "solid_name_rect") and self.solid_name_rect and self.solid_name_rect.collidepoint(pos):
            visualizer.cycle_solid_color()
            return True

        # Action Buttons
        if self.btn_mode.collidepoint(pos):
            visualizer.cycle_mode()
            return True
        elif hasattr(self, "btn_mode_2_0") and self.btn_mode_2_0.collidepoint(pos):
            visualizer.toggle_mode_2_0()
            return True
        elif self.btn_palette.collidepoint(pos):
            visualizer.cycle_palette()
            return True
        elif hasattr(self, "btn_album_art") and self.btn_album_art.collidepoint(pos):
            visualizer.toggle_album_art_mode()
            return True
        elif hasattr(self, "card_album_art") and self.card_album_art.collidepoint(pos):
            visualizer.toggle_album_art_mode()
            return True
        elif self.btn_style.collidepoint(pos):
            visualizer.cycle_style()
            return True
        elif self.btn_dualfx.collidepoint(pos):
            visualizer.cycle_dual_scheme()
            return True
        elif self.btn_displays.collidepoint(pos):
            if display_mgr:
                display_mgr.cycle_display_mode()
            on_display_change()
            return True
        elif self.btn_device.collidepoint(pos):
            if audio_mgr:
                audio_mgr.cycle_device()
            return True
        elif self.btn_sync.collidepoint(pos):
            self.toggle_sync_modal()
            return True
        elif self.btn_overdrive.collidepoint(pos):
            visualizer.toggle_overdrive()
            if audio_mgr:
                audio_mgr.set_overdrive(visualizer.overdrive_mode)
            return True
        elif self.btn_safe.collidepoint(pos):
            visualizer.toggle_safe_mode()
            if audio_mgr:
                audio_mgr.set_overdrive(visualizer.overdrive_mode)
            return True
        elif self.btn_razer.collidepoint(pos):
            if razer_mgr is not None:
                razer_mgr.toggle_enabled()
            return True
        elif self.btn_room_lights.collidepoint(pos):
            if happylighting_mgr is not None:
                happylighting_mgr.toggle_enabled()
            return True
        elif self.btn_lenovo.collidepoint(pos):
            if lenovo_mgr is not None:
                lenovo_mgr.toggle_enabled()
            return True

        return False

    def handle_mouse_up(self):
        self.dragging_slider = None
        self.dragging_waveform = False

    def handle_mouse_motion(self, pos, audio_mgr, visualizer, display_mgr, media_mgr=None):
        self.mouse_hover_pos = pos
        if display_mgr is not None:
            mon = display_mgr.get_monitor_for_point(pos[0], pos[1])
            if mon is not None and mon.rect != self.active_mon_rect:
                self.set_active_monitor(mon.rect)

        self.notify_interaction()
        if self.dragging_slider == "sens":
            self._update_slider_pos(pos[0], self.slider_sens_rect, MIN_SENSITIVITY, MAX_SENSITIVITY, audio_mgr.set_sensitivity)
        elif self.dragging_slider == "gain":
            self._update_slider_pos(pos[0], self.slider_gain_rect, MIN_PREAMP_GAIN, MAX_PREAMP_GAIN, audio_mgr.set_preamp_gain)
        elif self.dragging_slider == "decay":
            self._update_slider_pos(pos[0], self.slider_decay_rect, MIN_DECAY_RATE, MAX_DECAY_RATE, visualizer.set_decay_rate)
        elif self.dragging_waveform and hasattr(self, "waveform_rect") and media_mgr:
            time_deck_w = 148
            inner_w = max(10, self.waveform_rect.width - time_deck_w - 20)
            wf_start = self.waveform_rect.x + 8
            rel_x = pos[0] - wf_start
            prog = max(0.0, min(1.0, rel_x / inner_w))
            media_mgr.seek(prog)

    def _update_slider_pos(self, mx, rect, min_val, max_val, setter):
        norm = max(0.0, min(1.0, (mx - rect.x) / rect.width))
        val = min_val + norm * (max_val - min_val)
        setter(val)

    def update(self, dt):
        now = time.time()
        if not self.manually_hidden and not self.show_sync_modal and (now - self.last_interaction_time > HUD_AUTO_HIDE_DELAY):
            self.visible = False

        target_alpha = 255.0 if (self.visible or self.show_sync_modal) else 0.0
        if self.alpha < target_alpha:
            self.alpha = min(255.0, self.alpha + HUD_FADE_SPEED * 255.0 * dt)
        elif self.alpha > target_alpha:
            self.alpha = max(0.0, self.alpha - HUD_FADE_SPEED * 255.0 * dt)

    def render(self, screen, audio_mgr, visualizer, display_mgr, sync_mgr, audio_state, is_dual, razer_mgr=None, happylighting_mgr=None, lenovo_mgr=None, media_mgr=None):
        if not self.warning_dismissed:
            self._render_warning_dialog(screen)
            return

        if self.show_sync_modal:
            self._render_sync_modal(screen, sync_mgr)
            return

        if self.alpha <= 1.0:
            return

        alpha_int = int(self.alpha)
        hud_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        panel = self.panel_rect

        # 1. Main Frosted Glassmorphism Panel Backing
        panel_bg = (10, 14, 24, min(238, alpha_int))
        pygame.draw.rect(hud_surf, panel_bg, panel, border_radius=6)

        # Dynamic Accent Color & Active Mode Pill
        if getattr(visualizer, "solid_color_active", False):
            accent_col = (255, 205, 50)
            c_name = visualizer.get_solid_color_name() if hasattr(visualizer, "get_solid_color_name") else "SOLID"
            pill_text = f"SOLID: {c_name.upper()}"
            pill_col = (255, 215, 70)
            pill_bg = (44, 34, 14)
        elif visualizer.is_album_art_active():
            accent_col = (0, 240, 255)
            pill_text = "ALBUM ART SYNC"
            pill_col = (0, 240, 255)
            pill_bg = (12, 38, 52)
        elif visualizer.is_mode_2_0_active():
            accent_col = (255, 60, 180)
            pill_text = "STROBE 2.0"
            pill_col = (255, 60, 180)
            pill_bg = (42, 14, 36)
        elif visualizer.mode == MODE_RED_ONLY:
            accent_col = (255, 30, 45)
            pill_text = "RED ONLY"
            pill_col = (255, 50, 65)
            pill_bg = (45, 12, 18)
        elif visualizer.overdrive_mode:
            accent_col = (255, 60, 45)
            pill_text = "OVERDRIVE"
            pill_col = (255, 80, 60)
            pill_bg = (45, 16, 20)
        elif visualizer.safe_mode:
            accent_col = (0, 240, 150)
            pill_text = "SAFE GLOW"
            pill_col = (80, 240, 160)
            pill_bg = (12, 42, 26)
        else:
            accent_col = (0, 230, 255)
            pill_text = "ACTIVE"
            pill_col = (100, 230, 255)
            pill_bg = (14, 28, 44)

        # Draw Frame & Corner Brackets (clamped within rect bounds)
        frame_col = (*accent_col, min(140, alpha_int))
        pygame.draw.rect(hud_surf, frame_col, panel, width=1, border_radius=6)
        self._draw_tech_corner_brackets(hud_surf, panel, (*accent_col, min(220, alpha_int)), bracket_len=10, width=2)

        # Top Header Divider Bar
        header_h = 24
        header_surf = pygame.Surface((panel.width, header_h), pygame.SRCALPHA)
        header_surf.fill((14, 18, 28, min(210, alpha_int)))
        hud_surf.blit(header_surf, (panel.x, panel.y))
        pygame.draw.line(hud_surf, (*accent_col, min(80, alpha_int)), (panel.x + 8, panel.y + header_h), (panel.right - 8, panel.y + header_h))

        # Title: BEAT STROBE
        t_surf = self.font_title.render("BEAT STROBE", True, (240, 245, 255))
        hud_surf.blit(t_surf, (panel.x + 14, panel.y + 4))

        # Active Mode Pill
        pill_w = self.font_tiny.size(pill_text)[0] + 12
        pill_rect = pygame.Rect(panel.x + 14 + t_surf.get_width() + 10, panel.y + 4, pill_w, 16)
        pygame.draw.rect(hud_surf, (*pill_bg, alpha_int), pill_rect, border_radius=3)
        pygame.draw.rect(hud_surf, (*pill_col, min(180, alpha_int)), pill_rect, width=1, border_radius=3)
        p_text_surf = self.font_tiny.render(pill_text, True, pill_col)
        hud_surf.blit(p_text_surf, (pill_rect.x + 6, pill_rect.y + 1))

        # Right Header Pills (Source, Hardware, Network)
        right_pills = []
        is_spotify = (audio_mgr and getattr(audio_mgr, "devices", None) and
                      len(audio_mgr.devices) > audio_mgr.current_device_index and
                      audio_mgr.devices[audio_mgr.current_device_index] == "spotify")
        if is_spotify:
            right_pills.append(("SPOTIFY", (0, 240, 160), (10, 36, 24)))
        else:
            dev_name = audio_mgr.current_device_name if audio_mgr else "DEFAULT"
            if len(dev_name) > 14:
                dev_name = dev_name[:12] + ".."
            right_pills.append((dev_name.upper(), (100, 220, 255), (14, 30, 44)))

        if razer_mgr and razer_mgr.device_count > 0 and razer_mgr.enabled:
            right_pills.append(("RAZER", (0, 255, 120), (12, 38, 22)))
        if happylighting_mgr and happylighting_mgr.enabled:
            right_pills.append(("ROOM", (0, 240, 255), (12, 36, 48)))
        if lenovo_mgr and lenovo_mgr.enabled:
            right_pills.append(("LEGION", (0, 190, 255), (14, 30, 48)))

        if sync_mgr and sync_mgr.role == ROLE_HOST:
            right_pills.append((f"HOST:{sync_mgr.client_count}", (240, 100, 255), (38, 14, 42)))
        elif sync_mgr and sync_mgr.role == ROLE_CLIENT:
            right_pills.append(("CLIENT", (100, 240, 255), (14, 32, 48)))

        rx = panel.right - 14
        for p_name, p_fg, p_bg in reversed(right_pills):
            p_tw = self.font_tiny.size(p_name)[0] + 10
            rx -= p_tw
            r_pill = pygame.Rect(rx, panel.y + 4, p_tw, 16)
            pygame.draw.rect(hud_surf, (*p_bg, alpha_int), r_pill, border_radius=3)
            pygame.draw.rect(hud_surf, (*p_fg, min(140, alpha_int)), r_pill, width=1, border_radius=3)
            hud_surf.blit(self.font_tiny.render(p_name, True, p_fg), (r_pill.x + 5, r_pill.y + 1))
            rx -= 6

        # 2. Audio & Media Deck (Top Row: Spectrum, VU, BPM, and Now Playing Card)
        spec_x = panel.x + 18
        spec_y = panel.y + 28
        avail_for_audio = max(240, self.card_album_art.x - spec_x - 30)
        spec_w = min(220, int(avail_for_audio * 0.46))
        spec_h = 38

        # Background chamber for spectrum
        spec_bg = pygame.Rect(spec_x - 4, spec_y - 2, spec_w + 8, spec_h + 4)
        pygame.draw.rect(hud_surf, (14, 18, 28, alpha_int), spec_bg, border_radius=4)
        pygame.draw.rect(hud_surf, (30, 48, 68, alpha_int), spec_bg, width=1, border_radius=4)

        spec_bars = audio_state.get("spectrum_bars", [])
        num_bars = len(spec_bars)
        if num_bars > 0:
            bw = (spec_w - (num_bars - 1) * 2) / num_bars
            for i, val in enumerate(spec_bars):
                bh = int(val * spec_h)
                bx = spec_x + i * (bw + 2)
                ratio = i / max(1, num_bars - 1)
                bar_r = int(20 + ratio * 235)
                bar_g = int(240 * (1.0 - ratio * 0.4))
                bar_b = int(255)
                bar_rect = pygame.Rect(int(bx), spec_y + spec_h - bh, max(2, int(bw)), max(2, bh))
                pygame.draw.rect(hud_surf, (bar_r, bar_g, bar_b, alpha_int), bar_rect, border_radius=1)
                if bh > 4:
                    cap_rect = pygame.Rect(int(bx), spec_y + spec_h - bh, max(2, int(bw)), 2)
                    pygame.draw.rect(hud_surf, (255, 255, 255, alpha_int), cap_rect)

        # Frequency VU Level Meters
        levels_x = spec_x + spec_w + 14
        levels_y = spec_y
        meter_w = min(96, int(avail_for_audio * 0.21))
        meter_h = 8

        b_val = audio_state.get("bass_level", 0.0)
        m_val = audio_state.get("mid_level", 0.0)
        h_val = audio_state.get("high_level", 0.0)

        hud_surf.blit(self.font_tiny.render("BAS", True, (255, 90, 130)), (levels_x, levels_y - 1))
        self._render_segmented_vu(hud_surf, levels_x + 28, levels_y + 1, meter_w, meter_h, b_val, (255, 40, 100), alpha_int)

        hud_surf.blit(self.font_tiny.render("MID", True, (60, 240, 140)), (levels_x, levels_y + 13))
        self._render_segmented_vu(hud_surf, levels_x + 28, levels_y + 15, meter_w, meter_h, m_val, (50, 240, 130), alpha_int)

        hud_surf.blit(self.font_tiny.render("HIG", True, (70, 200, 255)), (levels_x, levels_y + 27))
        self._render_segmented_vu(hud_surf, levels_x + 28, levels_y + 29, meter_w, meter_h, h_val, (60, 210, 255), alpha_int)

        # Beat Pulse Reticle & BPM
        beat_x = levels_x + 28 + meter_w + 18
        beat_y = levels_y + 18
        is_beating = visualizer.kick_intensity > 0.4

        reticle_col = (255, 40, 120) if is_beating else (45, 60, 80)
        pygame.draw.circle(hud_surf, reticle_col, (beat_x, beat_y), 11, width=1)
        if is_beating:
            pygame.draw.circle(hud_surf, (255, 50, 140, alpha_int), (beat_x, beat_y), 7)
            pygame.draw.circle(hud_surf, (255, 255, 255, alpha_int), (beat_x, beat_y), 3)
        else:
            pygame.draw.circle(hud_surf, (35, 45, 60, alpha_int), (beat_x, beat_y), 2)

        bpm = audio_state.get("bpm", 0.0)
        bpm_str = f"{int(round(bpm))} BPM" if bpm > 30 else "-- BPM"
        bpm_surf = self.font_title.render(bpm_str, True, (0, 240, 255))
        hud_surf.blit(bpm_surf, (beat_x + 18, beat_y - 12))

        pitch_name = audio_state.get("pitch_name", "C")
        sec_name = audio_state.get("section_name", "VERSE")
        pitch_badge = f"KEY:{pitch_name}"
        p_surf = self.font_tiny.render(pitch_badge, True, (255, 120, 220))
        hud_surf.blit(p_surf, (beat_x + 18, beat_y + 3))

        if sec_name == "CHORUS":
            sec_surf = self.font_tiny.render("[CHORUS]", True, (255, 60, 180))
        elif sec_name == "BUILDUP":
            sec_surf = self.font_tiny.render("[BUILDUP]", True, (255, 200, 40))
        else:
            sec_surf = self.font_tiny.render("[VERSE]", True, (0, 220, 255))
        hud_surf.blit(sec_surf, (beat_x + 18 + p_surf.get_width() + 6, beat_y + 3))

        # Now Playing Native Album Cover Artwork Card
        if media_mgr and hasattr(self, "card_album_art"):
            media_info = media_mgr.get_info()
            hud_thumb = media_mgr.get_hud_thumbnail()
            album_pal = media_mgr.get_palette()

            card_rect = self.card_album_art
            is_art_active = visualizer.is_album_art_active() if hasattr(visualizer, "is_album_art_active") else (
                visualizer.mode == MODE_ALBUM_ART or visualizer.palette_name == PALETTE_ALBUM_ART
            )
            is_paused = media_info.get("is_paused", False)
            card_bg = (14, 20, 32, alpha_int)
            card_border = (0, 240, 255) if is_art_active else (45, 65, 90)

            pygame.draw.rect(hud_surf, card_bg, card_rect, border_radius=4)
            pygame.draw.rect(hud_surf, (*card_border, alpha_int), card_rect, width=1, border_radius=4)
            self._draw_tech_corner_brackets(hud_surf, card_rect, (*card_border, alpha_int), bracket_len=6, width=1)

            if hud_thumb:
                hud_surf.blit(hud_thumb, (card_rect.x + 2, card_rect.y + 2))
            else:
                icon_rect = pygame.Rect(card_rect.x + 2, card_rect.y + 2, 36, 36)
                pygame.draw.rect(hud_surf, (22, 28, 42, alpha_int), icon_rect, border_radius=3)
                note_surf = self.font_main.render("ART", True, (0, 220, 255))
                hud_surf.blit(note_surf, (card_rect.x + 6, card_rect.y + 10))

            raw_title = media_info.get("title", "") or "No Media Playing"
            raw_artist = media_info.get("artist", "") or ("WinRT Active" if media_info.get("has_art") else "Audio Standby")

            max_char = max(11, (card_rect.width - 95) // 8)
            disp_title = (raw_title[:max_char] + "..") if len(raw_title) > max_char + 2 else raw_title
            disp_artist = (raw_artist[:max_char + 2] + "..") if len(raw_artist) > max_char + 4 else raw_artist

            t_col = (255, 255, 255) if is_art_active else (205, 215, 230)
            t_surf = self.font_small.render(disp_title, True, t_col)
            a_surf = self.font_tiny.render(disp_artist, True, (130, 145, 170))
            hud_surf.blit(t_surf, (card_rect.x + 44, card_rect.y + 2))
            hud_surf.blit(a_surf, (card_rect.x + 44, card_rect.y + 15))

            chip_y = card_rect.y + 28
            chip_w = 11
            chip_h = 7
            for ci, col in enumerate(album_pal[:5]):
                cx = card_rect.x + 44 + ci * (chip_w + 3)
                pygame.draw.rect(hud_surf, (*col, alpha_int), (cx, chip_y, chip_w, chip_h), border_radius=1)
                pygame.draw.rect(hud_surf, (0, 0, 0, alpha_int), (cx, chip_y, chip_w, chip_h), width=1)

            if is_paused:
                paused_badge = self.font_tiny.render("[PAUSED]", True, (255, 180, 40))
                hud_surf.blit(paused_badge, (card_rect.right - paused_badge.get_width() - 5, chip_y - 2))
            elif is_art_active:
                active_badge = self.font_tiny.render("[ACTIVE]", True, (0, 240, 255))
                hud_surf.blit(active_badge, (card_rect.right - active_badge.get_width() - 5, chip_y - 2))
            else:
                off_badge = self.font_tiny.render("[STANDBY]", True, (90, 110, 135))
                hud_surf.blit(off_badge, (card_rect.right - off_badge.get_width() - 5, chip_y - 2))

        # 3. Waveform Song Progress Bar Deck
        if hasattr(self, "waveform_rect"):
            wf_rect = self.waveform_rect
            if alpha_int > 0:
                pygame.draw.rect(screen, (12, 16, 26), wf_rect, border_radius=4)
            pygame.draw.rect(hud_surf, (12, 16, 26, 255), wf_rect, border_radius=4)
            pygame.draw.rect(hud_surf, (30, 48, 68, alpha_int), wf_rect, width=1, border_radius=4)
            self._draw_tech_corner_brackets(hud_surf, wf_rect, (45, 72, 100, alpha_int), bracket_len=6, width=1)

            tl_info = media_mgr.get_timeline() if media_mgr else {}
            pos_sec = tl_info.get("position", 0.0)
            dur_sec = tl_info.get("duration", 0.0)
            progress = tl_info.get("progress", 0.0)
            is_playing = tl_info.get("is_playing", False)
            is_paused = tl_info.get("is_paused", False)
            wf_arr = tl_info.get("waveform", [])
            wf_r = tl_info.get("waveform_r", [])
            num_wf = len(wf_arr)

            def _fmt_time(s):
                m = int(s) // 60
                sec = int(s) % 60
                return f"{m:02d}:{sec:02d}"

            time_deck_w = 148
            inner_w = max(40, wf_rect.width - time_deck_w - 20)
            wf_start_x = wf_rect.x + 8
            cy = wf_rect.centery
            max_half_h = max(4, (wf_rect.height - 12) // 2)

            grid_y_offsets = [
                int(max_half_h * 0.75),
                int(max_half_h * 0.40),
                -int(max_half_h * 0.40),
                -int(max_half_h * 0.75),
            ]
            for dy in grid_y_offsets:
                gy = cy + dy
                pygame.draw.line(hud_surf, (22, 32, 48, min(90, alpha_int)), (wf_start_x, gy), (wf_start_x + inner_w, gy), 1)

            pygame.draw.line(hud_surf, (32, 48, 70, alpha_int), (wf_start_x, cy), (wf_start_x + inner_w, cy), 1)

            for frac, lbl in ((0.25, "25%"), (0.50, "50%"), (0.75, "75%")):
                tx = int(wf_start_x + frac * inner_w)
                pygame.draw.line(hud_surf, (36, 56, 80, alpha_int), (tx, wf_rect.y + 2), (tx, wf_rect.y + 7), 1)
                pygame.draw.line(hud_surf, (36, 56, 80, alpha_int), (tx, wf_rect.bottom - 8), (tx, wf_rect.bottom - 3), 1)
                lbl_surf = self.font_tiny.render(lbl, True, (65, 85, 110))
                hud_surf.blit(lbl_surf, (tx - lbl_surf.get_width() // 2, wf_rect.y + 4))

            sep_time_x = wf_rect.right - time_deck_w - 8
            pygame.draw.line(hud_surf, (28, 44, 64, alpha_int), (sep_time_x, wf_rect.y + 6), (sep_time_x, wf_rect.bottom - 6), 1)

            is_mode_2_0 = visualizer.is_mode_2_0_active() if hasattr(visualizer, "is_mode_2_0_active") else False
            is_album_art = (visualizer.mode == MODE_ALBUM_ART or visualizer.palette_name == PALETTE_ALBUM_ART)
            album_pal = media_mgr.get_palette() if media_mgr else []

            if is_album_art and album_pal:
                played_col_top = album_pal[0]
                played_col_bot = album_pal[1] if len(album_pal) > 1 else album_pal[0]
            elif is_mode_2_0:
                sec_name = audio_state.get("section_name", "VERSE")
                if sec_name == "CHORUS":
                    played_col_top = (255, 45, 145)
                    played_col_bot = (255, 175, 30)
                elif sec_name == "BUILDUP":
                    played_col_top = (255, 190, 40)
                    played_col_bot = (245, 85, 35)
                else:
                    played_col_top = (0, 230, 255)
                    played_col_bot = (140, 45, 255)
            else:
                played_col_top = (0, 240, 255)
                played_col_bot = (0, 160, 235)

            unplayed_col_top = (42, 60, 84)
            unplayed_col_bot = (30, 44, 64)

            play_x = wf_start_x + progress * inner_w

            if num_wf > 0:
                bar_step = inner_w / num_wf
                for i in range(num_wf):
                    x0 = int(wf_start_x + i * bar_step)
                    x1 = int(wf_start_x + (i + 1) * bar_step)
                    bar_w = max(1, x1 - x0 - 1) if (x1 - x0 > 1) else 1
                    bx = x0

                    amp_top = float(wf_arr[i])
                    amp_bot = float(wf_r[i]) if (i < len(wf_r)) else (amp_top * 0.94)

                    top_h = max(2, int(amp_top * max_half_h))
                    bot_h = max(2, int(amp_bot * max_half_h * 0.92))

                    is_played = (progress > 0.0 and (bx + bar_w * 0.5) <= play_x)
                    c_top = played_col_top if is_played else unplayed_col_top
                    c_bot = played_col_bot if is_played else unplayed_col_bot

                    pygame.draw.rect(hud_surf, (*c_top, alpha_int), (bx, cy - top_h, bar_w, top_h), border_radius=1)
                    pygame.draw.rect(hud_surf, (*c_bot, alpha_int), (bx, cy + 1, bar_w, bot_h), border_radius=1)

                ph_x = int(play_x)
                if wf_start_x <= ph_x <= wf_start_x + inner_w:
                    pygame.draw.line(hud_surf, (*played_col_top, min(140, alpha_int)), (ph_x - 1, wf_rect.y + 2), (ph_x - 1, wf_rect.bottom - 3), 1)
                    pygame.draw.line(hud_surf, (*played_col_top, min(140, alpha_int)), (ph_x + 1, wf_rect.y + 2), (ph_x + 1, wf_rect.bottom - 3), 1)
                    pygame.draw.line(hud_surf, (255, 255, 255, alpha_int), (ph_x, wf_rect.y + 2), (ph_x, wf_rect.bottom - 3), 1)
                    pygame.draw.circle(hud_surf, (*played_col_top, alpha_int), (ph_x, cy), 5)
                    pygame.draw.circle(hud_surf, (255, 255, 255, alpha_int), (ph_x, cy), 3)

                if hasattr(self, "mouse_hover_pos") and self.mouse_hover_pos:
                    hx, hy = self.mouse_hover_pos
                    if (wf_start_x <= hx <= wf_start_x + inner_w) and (wf_rect.y <= hy <= wf_rect.bottom):
                        pygame.draw.line(hud_surf, (0, 240, 255, min(130, alpha_int)), (hx, wf_rect.y + 8), (hx, wf_rect.bottom - 9), 1)
                        h_prog = (hx - wf_start_x) / inner_w
                        h_time = h_prog * dur_sec if dur_sec > 0 else 0.0
                        h_tip = f"[{_fmt_time(h_time)}]" if dur_sec > 0 else f"[{int(h_prog * 100)}%]"
                        h_surf = self.font_tiny.render(h_tip, True, (0, 240, 255))
                        tip_x = max(wf_start_x + 4, min(wf_start_x + inner_w - h_surf.get_width() - 8, hx - h_surf.get_width() // 2))
                        tip_y = wf_rect.y + 4 if hy > cy else wf_rect.bottom - h_surf.get_height() - 6
                        tip_bg = pygame.Rect(tip_x - 3, tip_y - 1, h_surf.get_width() + 6, h_surf.get_height() + 2)
                        pygame.draw.rect(hud_surf, (8, 14, 24, min(240, alpha_int)), tip_bg, border_radius=2)
                        pygame.draw.rect(hud_surf, (0, 200, 255, min(160, alpha_int)), tip_bg, width=1, border_radius=2)
                        hud_surf.blit(h_surf, (tip_x, tip_y))
            else:
                idle_txt = self.font_tiny.render("TIMELINE STANDBY", True, (75, 95, 120))
                hud_surf.blit(idle_txt, (wf_start_x + 10, cy - idle_txt.get_height() // 2))

            # Right-side Time Deck
            if dur_sec > 0:
                badge_str = "[PAUSED]" if is_paused else ("[ACTIVE]" if is_playing else "[STOPPED]")
                badge_col = (255, 180, 50) if is_paused else ((0, 240, 255) if is_playing else (110, 130, 155))
            else:
                badge_str = "[STANDBY]"
                badge_col = (85, 105, 130)

            badge_surf = self.font_tiny.render(badge_str, True, badge_col)
            right_x = wf_rect.right - 10
            badge_y = wf_rect.y + 7
            hud_surf.blit(badge_surf, (right_x - badge_surf.get_width(), badge_y))
            pip_x = right_x - badge_surf.get_width() - 8
            pip_y = badge_y + badge_surf.get_height() // 2
            pygame.draw.circle(hud_surf, (*badge_col, alpha_int), (pip_x, pip_y), 3)

            time_str = f"{_fmt_time(pos_sec)} / {_fmt_time(dur_sec)}" if dur_sec > 0 else "--:-- / --:--"
            time_surf = self.font_small.render(time_str, True, (240, 245, 255) if is_playing else (140, 160, 185))
            hud_surf.blit(time_surf, (right_x - time_surf.get_width(), wf_rect.y + 22))

            rem_sec = max(0.0, dur_sec - pos_sec)
            pct_val = int(round(progress * 100))
            sub_str = f"-{_fmt_time(rem_sec)} [{pct_val}%]" if dur_sec > 0 else "--:-- [0%]"
            sub_surf = self.font_tiny.render(sub_str, True, (120, 145, 175))
            hud_surf.blit(sub_surf, (right_x - sub_surf.get_width(), wf_rect.y + 37))

            meter_w = time_deck_w - 24
            meter_x = right_x - meter_w
            meter_y = wf_rect.y + 53
            pygame.draw.rect(hud_surf, (18, 26, 38, alpha_int), (meter_x, meter_y, meter_w, 4), border_radius=1)
            pygame.draw.rect(hud_surf, (35, 52, 74, alpha_int), (meter_x, meter_y, meter_w, 4), width=1, border_radius=1)
            if progress > 0:
                fill_w = max(2, int(progress * meter_w))
                pygame.draw.rect(hud_surf, (*played_col_top, alpha_int), (meter_x, meter_y, fill_w, 4), border_radius=1)
                pygame.draw.rect(hud_surf, (255, 255, 255, alpha_int), (meter_x + fill_w - 1, meter_y, 1, 4))

            sec_tag = audio_state.get("section_name", "VERSE")
            fid_lbl = self.font_tiny.render(f"[{sec_tag}]", True, (90, 115, 145))
            hud_surf.blit(fid_lbl, (right_x - fid_lbl.get_width(), wf_rect.y + 65))

        # 4. Precision Sliders Deck (Side-by-Side 3 Columns)
        sens = audio_mgr.get_sensitivity() if audio_mgr else 1.0
        pre_g = audio_mgr.get_preamp_gain() if audio_mgr else 1.0
        decay = visualizer.decay_rate

        # Slider 1: SENS
        hud_surf.blit(self.font_tiny.render("SENS", True, (170, 200, 220)), (self.slider_sens_rect.x - 34, self.slider_sens_rect.y - 1))
        self._render_slider(hud_surf, self.slider_sens_rect, sens, MIN_SENSITIVITY, MAX_SENSITIVITY, (0, 220, 255), alpha_int)
        v_sens = self.font_tiny.render(f"{sens:.1f}x", True, (0, 240, 255))
        hud_surf.blit(v_sens, (self.slider_sens_rect.right + 6, self.slider_sens_rect.y - 1))

        # Slider 2: GAIN
        hud_surf.blit(self.font_tiny.render("GAIN", True, (240, 195, 120)), (self.slider_gain_rect.x - 34, self.slider_gain_rect.y - 1))
        self._render_slider(hud_surf, self.slider_gain_rect, pre_g, MIN_PREAMP_GAIN, MAX_PREAMP_GAIN, (255, 180, 50), alpha_int)
        v_gain = self.font_tiny.render(f"{pre_g:.1f}x", True, (255, 190, 60))
        hud_surf.blit(v_gain, (self.slider_gain_rect.right + 6, self.slider_gain_rect.y - 1))

        # Slider 3: DECAY
        hud_surf.blit(self.font_tiny.render("DECAY", True, (240, 140, 90)), (self.slider_decay_rect.x - 40, self.slider_decay_rect.y - 1))
        self._render_slider(hud_surf, self.slider_decay_rect, decay, MIN_DECAY_RATE, MAX_DECAY_RATE, (255, 95, 30), alpha_int)
        v_decay = self.font_tiny.render(f"{decay:.0f}", True, (255, 110, 40))
        hud_surf.blit(v_decay, (self.slider_decay_rect.right + 6, self.slider_decay_rect.y - 1))

        # 4.5 Solid Lighting Control Deck & Swatches Bar
        solid_active = visualizer.is_solid_color_active() if hasattr(visualizer, "is_solid_color_active") else False
        solid_btn_label = "[LIGHT] SOLID" if solid_active else "[LIGHT] MUSIC"
        solid_btn_bg = (48, 38, 16) if solid_active else (18, 24, 38)
        solid_btn_border = (255, 200, 40) if solid_active else (70, 95, 125)
        solid_pip_col = (255, 210, 50) if solid_active else (0, 220, 255)

        if hasattr(self, "btn_solid_toggle") and self.btn_solid_toggle:
            self._render_button(
                hud_surf,
                self.btn_solid_toggle,
                solid_btn_label,
                solid_btn_bg,
                solid_btn_border,
                alpha_int,
                has_pip=True,
                pip_active=solid_active,
                pip_col=solid_pip_col,
            )

        # Color Swatches
        active_idx = getattr(visualizer, "solid_color_index", 0)
        active_col = getattr(visualizer, "solid_color", (255, 0, 0))
        hover_pos = self.mouse_hover_pos

        if hasattr(self, "solid_swatch_rects"):
            for s_rect, idx, s_name, s_rgb in self.solid_swatch_rects:
                is_hover = bool(hover_pos and s_rect.collidepoint(hover_pos))
                is_selected = (idx == active_idx) or (s_rgb == active_col)

                pygame.draw.rect(hud_surf, (*s_rgb, alpha_int), s_rect, border_radius=2)

                if is_selected and solid_active:
                    pygame.draw.rect(hud_surf, (255, 255, 255, alpha_int), s_rect.inflate(4, 4), width=2, border_radius=3)
                    pygame.draw.circle(hud_surf, (255, 255, 255, alpha_int), s_rect.center, 2)
                elif is_selected:
                    pygame.draw.rect(hud_surf, (200, 220, 240, alpha_int), s_rect.inflate(2, 2), width=1, border_radius=2)
                elif is_hover:
                    pygame.draw.rect(hud_surf, (255, 255, 255, alpha_int), s_rect, width=1, border_radius=2)
                else:
                    pygame.draw.rect(hud_surf, (15, 20, 30, alpha_int), s_rect, width=1, border_radius=2)

        # Active Color Name Tag
        if hasattr(self, "solid_name_rect") and self.solid_name_rect:
            tag_rect = self.solid_name_rect
            tag_name = visualizer.get_solid_color_name() if hasattr(visualizer, "get_solid_color_name") else "Solid"
            tag_bg = (24, 20, 14, alpha_int) if solid_active else (14, 18, 28, alpha_int)
            tag_border = (*active_col, alpha_int) if solid_active else (45, 60, 80, alpha_int)
            pygame.draw.rect(hud_surf, tag_bg, tag_rect, border_radius=3)
            pygame.draw.rect(hud_surf, tag_border, tag_rect, width=1, border_radius=3)
            tag_text = self.font_tiny.render(f"[{tag_name}]", True, (255, 255, 255) if solid_active else (140, 160, 185))
            hud_surf.blit(tag_text, (tag_rect.x + (tag_rect.width - tag_text.get_width()) // 2, tag_rect.y + 4))

        # Section Accent Line
        sep_y = panel.y + 206
        pygame.draw.line(hud_surf, (*accent_col, min(45, alpha_int)), (panel.x + 18, sep_y), (panel.right - 18, sep_y))

        # 5. Command Matrix: 2-Row Arrangement
        # --- Row 1: Visual, Display, 2.0 & Album Controls (7 buttons) ---
        m_txt = visualizer.mode
        if m_txt.startswith("[") and "]" in m_txt:
            m_txt = m_txt.split("]", 1)[1].strip()
        if "Strobe 2.0" in m_txt:
            m_disp = "Mode: 2.0"
        elif "Psycho" in m_txt:
            m_disp = "Mode: Psycho"
        elif "Red Only" in m_txt:
            m_disp = "Mode: Red"
        elif "Bass Only" in m_txt:
            m_disp = "Mode: Bass"
        elif "Cover Art" in m_txt:
            m_disp = "Mode: Album"
        elif "Machine-Gun" in m_txt:
            m_disp = "Mode: Burst"
        elif "Strobe Blitz" in m_txt:
            m_disp = "Mode: Blitz"
        else:
            m_disp = f"Mode: {m_txt[:8]}"

        is_red = (visualizer.mode == MODE_RED_ONLY)
        btn_mode_bg = (42, 14, 18) if is_red else (18, 24, 38)
        btn_mode_border = (255, 30, 45) if is_red else (0, 200, 255)
        self._render_button(hud_surf, self.btn_mode, m_disp, btn_mode_bg, btn_mode_border, alpha_int,
                            has_pip=is_red, pip_active=is_red, pip_col=(255, 30, 45))

        mode_2_0_active = visualizer.is_mode_2_0_active()
        mode_2_0_bg = (48, 14, 38) if mode_2_0_active else (18, 24, 38)
        mode_2_0_border = (255, 40, 180) if mode_2_0_active else (85, 55, 105)
        self._render_button(hud_surf, self.btn_mode_2_0, "Strobe 2.0",
                            mode_2_0_bg, mode_2_0_border, alpha_int, has_pip=True, pip_active=mode_2_0_active, pip_col=(255, 40, 180))

        p_txt = visualizer.palette_name
        if p_txt.startswith("[") and "]" in p_txt:
            p_txt = p_txt.split("]", 1)[1].strip()
        self._render_button(hud_surf, self.btn_palette, f"Pal: {p_txt[:8]}", (26, 20, 36), (240, 40, 180), alpha_int)

        s_clean = visualizer.current_style.replace("Solid ", "").replace("Shockwave", "Wave")
        self._render_button(hud_surf, self.btn_style, f"Style: {s_clean[:7]}", (22, 22, 40), (160, 110, 255), alpha_int)

        art_active = (visualizer.mode == MODE_ALBUM_ART or visualizer.palette_name == PALETTE_ALBUM_ART)
        art_bg = (10, 45, 60) if art_active else (18, 24, 38)
        art_border = (0, 240, 255) if art_active else (60, 80, 105)
        self._render_button(hud_surf, self.btn_album_art, "Album Sync",
                            art_bg, art_border, alpha_int, has_pip=True, pip_active=art_active, pip_col=(0, 240, 255))

        dual_txt = visualizer.dual_scheme.replace("Dual ", "").replace("Alternating", "Alt").replace("Complementary ", "") if is_dual else "Single"
        self._render_button(hud_surf, self.btn_dualfx, f"Dual: {dual_txt[:7]}", (30, 24, 45), (200, 110, 255), alpha_int)

        disp_txt = getattr(display_mgr, "current_mode", "Windowed") if display_mgr else "Win"
        disp_txt = disp_txt.replace("Dual Monitor ", "").replace("Monitor ", "Mon ")
        self._render_button(hud_surf, self.btn_displays, f"Disp: {disp_txt[:7]}", (22, 30, 48), (100, 190, 255), alpha_int)

        # --- Row 2: Engine, Hardware & Sync Controls (7 buttons) ---
        is_spotify_active = (audio_mgr and getattr(audio_mgr, "devices", None) and
                             len(audio_mgr.devices) > audio_mgr.current_device_index and
                             audio_mgr.devices[audio_mgr.current_device_index] == "spotify")
        dev_btn_txt = "Spotify" if is_spotify_active else "Audio In"
        dev_btn_bg = (12, 38, 28) if is_spotify_active else (18, 28, 40)
        dev_btn_border = (0, 240, 160) if is_spotify_active else (80, 220, 190)
        self._render_button(hud_surf, self.btn_device, dev_btn_txt, dev_btn_bg, dev_btn_border, alpha_int,
                            has_pip=is_spotify_active, pip_active=is_spotify_active, pip_col=(0, 240, 160))

        if sync_mgr and sync_mgr.role == ROLE_HOST:
            sync_label = f"Sync: Host"
            sync_bg = (40, 20, 50)
            sync_border = (230, 90, 255)
        elif sync_mgr and sync_mgr.role == ROLE_CLIENT:
            c_tag = "Link" if sync_mgr.client_sock else "Scan"
            sync_label = f"Sync: {c_tag}"
            sync_bg = (15, 38, 52)
            sync_border = (0, 220, 255)
        else:
            sync_label = "Sync: BT/LAN"
            sync_bg = (18, 24, 38)
            sync_border = (90, 140, 190)
        self._render_button(hud_surf, self.btn_sync, sync_label, sync_bg, sync_border, alpha_int)

        ovr_active = visualizer.overdrive_mode
        ovr_bg = (70, 18, 22) if ovr_active else (24, 18, 24)
        ovr_border = (255, 60, 45) if ovr_active else (110, 50, 50)
        self._render_button(hud_surf, self.btn_overdrive, "Overdrive",
                            ovr_bg, ovr_border, alpha_int, has_pip=True, pip_active=ovr_active, pip_col=(255, 60, 45))

        safe_active = visualizer.safe_mode
        safe_bg = (15, 48, 30) if safe_active else (18, 24, 34)
        safe_border = (0, 240, 150) if safe_active else (60, 90, 80)
        self._render_button(hud_surf, self.btn_safe, "Safe Glow",
                            safe_bg, safe_border, alpha_int, has_pip=True, pip_active=safe_active, pip_col=(0, 240, 150))

        if razer_mgr and razer_mgr.device_count > 0:
            rz_active = razer_mgr.enabled
            rz_label = f"Razer ({razer_mgr.device_count})"
            rz_bg = (12, 48, 22) if rz_active else (18, 24, 34)
            rz_border = (0, 255, 120) if rz_active else (60, 90, 75)
        else:
            rz_active = False
            rz_label = "Razer N/A"
            rz_bg = (18, 20, 28)
            rz_border = (50, 60, 75)
        self._render_button(hud_surf, self.btn_razer, rz_label, rz_bg, rz_border, alpha_int, has_pip=True, pip_active=rz_active, pip_col=(0, 255, 120))

        if happylighting_mgr:
            if happylighting_mgr.connected:
                hl_active = happylighting_mgr.enabled
                hl_label = "Room BLE"
                hl_bg = (12, 45, 55) if hl_active else (18, 24, 34)
                hl_border = (0, 240, 255) if hl_active else (60, 80, 95)
                hl_pip = (0, 240, 255)
            elif happylighting_mgr.enabled:
                hl_active = True
                hl_label = "Room Sync"
                hl_bg = (45, 40, 18)
                hl_border = (255, 210, 0)
                hl_pip = (255, 210, 0)
            else:
                hl_active = False
                hl_label = "Room BLE"
                hl_bg = (18, 20, 28)
                hl_border = (50, 60, 75)
                hl_pip = None
        else:
            hl_active = False
            hl_label = "Room N/A"
            hl_bg = (18, 20, 28)
            hl_border = (50, 60, 75)
            hl_pip = None
        self._render_button(hud_surf, self.btn_room_lights, hl_label, hl_bg, hl_border, alpha_int, has_pip=True, pip_active=hl_active, pip_col=hl_pip)

        if lenovo_mgr and lenovo_mgr.connected:
            legion_active = lenovo_mgr.enabled
            legion_label = "Legion PC"
            legion_bg = (14, 40, 58) if legion_active else (18, 24, 34)
            legion_border = (0, 190, 255) if legion_active else (60, 80, 95)
        else:
            legion_active = False
            legion_label = "Legion N/A"
            legion_bg = (18, 20, 28)
            legion_border = (50, 60, 75)
        self._render_button(hud_surf, self.btn_lenovo, legion_label, legion_bg, legion_border, alpha_int, has_pip=True, pip_active=legion_active, pip_col=(0, 190, 255))

        # 5. Minimal Clean Footer
        hints = "ESC Exit   O Solid   R Red   1 Bass   2 Smart   X Overdrive   A Album   C Razer   L Room   K Legion   M Mode   P Palette   TAB Hide"
        hint_surf = self.font_tiny.render(hints, True, (120, 138, 165))
        hud_surf.blit(hint_surf, (panel.x + (panel.width - hint_surf.get_width()) // 2, panel.bottom - 16))

        hud_surf.set_alpha(alpha_int)
        screen.blit(hud_surf, (0, 0))

    def _render_segmented_vu(self, surf, x, y, w, h, level, active_col, alpha):
        """Render high-tech segmented VU meter bars."""
        num_segs = 8
        gap = 2
        seg_w = max(2, (w - (num_segs - 1) * gap) // num_segs)
        active_segs = int(round(level * num_segs))

        for s in range(num_segs):
            sx = x + s * (seg_w + gap)
            rect = pygame.Rect(sx, y, seg_w, h)
            if s < active_segs:
                pygame.draw.rect(surf, (*active_col, alpha), rect, border_radius=1)
            else:
                pygame.draw.rect(surf, (25, 30, 42, alpha), rect, border_radius=1)

    def _draw_tech_corner_brackets(self, surf, rect, color, bracket_len=8, width=2):
        """Draw crisp angular sci-fi corner brackets aligned precisely within rect bounds."""
        x, y = rect.x, rect.y
        r, b = rect.right - 1, rect.bottom - 1
        bl = min(bracket_len, max(2, rect.width // 3), max(2, rect.height // 3))
        # Top-Left
        pygame.draw.lines(surf, color, False, [(x, y + bl), (x, y), (x + bl, y)], width)
        # Top-Right
        pygame.draw.lines(surf, color, False, [(r - bl, y), (r, y), (r, y + bl)], width)
        # Bottom-Left
        pygame.draw.lines(surf, color, False, [(x, b - bl), (x, b), (x + bl, b)], width)
        # Bottom-Right
        pygame.draw.lines(surf, color, False, [(r - bl, b), (r, b), (r, b - bl)], width)

    def _render_slider(self, surf, rect, value, min_val, max_val, color, alpha):
        """Render sleek sci-fi telemetry slider with precision reticle cursor."""
        # Track groove
        pygame.draw.rect(surf, (16, 22, 34, alpha), rect, border_radius=3)
        pygame.draw.rect(surf, (40, 55, 78, alpha), rect, width=1, border_radius=3)

        norm = max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
        fill_w = int(rect.width * norm)
        if fill_w > 0:
            fill_rect = pygame.Rect(rect.x, rect.y, fill_w, rect.height)
            pygame.draw.rect(surf, (*color, alpha), fill_rect, border_radius=3)

        # Precision Reticle Cursor Handle
        tx = int(rect.x + fill_w)
        ty = rect.y + rect.height // 2

        # Outer reticle & inner core
        pygame.draw.circle(surf, (10, 14, 22, alpha), (tx, ty), 6)
        pygame.draw.circle(surf, (*color, alpha), (tx, ty), 6, width=1)
        pygame.draw.circle(surf, (255, 255, 255, alpha), (tx, ty), 2)

    def _render_button(self, surf, rect, text, bg_col, border_col, alpha, has_pip=False, pip_active=False, pip_col=None):
        """Render sleek sci-fi button with angular styling and non-overlapping glowing status indicator pip."""
        pygame.draw.rect(surf, (*bg_col, alpha), rect, border_radius=3)
        pygame.draw.rect(surf, (*border_col, alpha), rect, width=1, border_radius=3)

        pip_margin = 0
        if has_pip:
            pip_margin = 15
            pip_x = rect.x + 8
            pip_y = rect.y + rect.height // 2
            if pip_active:
                col = pip_col or (0, 240, 255)
                # Outer glow halo
                halo_surf = pygame.Surface((10, 10), pygame.SRCALPHA)
                pygame.draw.circle(halo_surf, (*col, min(90, alpha)), (5, 5), 4)
                surf.blit(halo_surf, (pip_x - 5, pip_y - 5))
                # Glowing core pip
                pygame.draw.circle(surf, (*col, alpha), (pip_x, pip_y), 3)
                pygame.draw.circle(surf, (255, 255, 255, alpha), (pip_x, pip_y), 1)
            else:
                pygame.draw.circle(surf, (40, 50, 65, alpha), (pip_x, pip_y), 3)

        # Available width for text
        avail_w = max(10, rect.width - pip_margin - 6)
        disp_text = text
        if self.font_small.size(disp_text)[0] > avail_w:
            while len(disp_text) > 3 and self.font_small.size(disp_text + "..")[0] > avail_w:
                disp_text = disp_text[:-1]
            disp_text = disp_text + ".."

        txt_surf = self.font_small.render(disp_text, True, (235, 242, 255))
        tx = rect.x + pip_margin + max(0, (avail_w - txt_surf.get_width()) // 2)
        ty = rect.y + (rect.height - txt_surf.get_height()) // 2
        surf.blit(txt_surf, (tx, ty))

    def _render_sync_modal(self, screen, sync_mgr):
        """Render multi-computer Bluetooth & Network Sync modal dialog with unified sci-fi geometry."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))

        layout = self._get_sync_modal_layout()
        modal_rect = layout["modal_rect"]
        mx, my = modal_rect.x, modal_rect.y

        pygame.draw.rect(overlay, (12, 16, 26), modal_rect, border_radius=6)
        pygame.draw.rect(overlay, (0, 220, 255), modal_rect, width=1, border_radius=6)
        self._draw_tech_corner_brackets(overlay, modal_rect, (0, 240, 255), bracket_len=14, width=2)

        head_txt = self.font_title.render("// MULTI-SYSTEM SYNC MATRIX [BLUETOOTH & LOCAL NETWORK]", True, (255, 255, 255))
        overlay.blit(head_txt, (mx + 20, my + 18))

        self._render_button(overlay, layout["btn_close"], "[X] CLOSE", (35, 42, 58), (140, 160, 180), 255)

        tab_stand = layout["tab_stand"]
        bg_s = (10, 80, 60) if sync_mgr.role == ROLE_STANDALONE else (20, 26, 40)
        b_s = (0, 240, 180) if sync_mgr.role == ROLE_STANDALONE else (50, 70, 95)
        self._render_button(overlay, tab_stand, "[SOLO] Standalone Node", bg_s, b_s, 255, has_pip=True, pip_active=(sync_mgr.role == ROLE_STANDALONE), pip_col=(0, 240, 180))

        tab_host = layout["tab_host"]
        bg_h = (80, 15, 55) if sync_mgr.role == ROLE_HOST else (20, 26, 40)
        b_h = (255, 40, 180) if sync_mgr.role == ROLE_HOST else (50, 70, 95)
        self._render_button(overlay, tab_host, "[HOST] Broadcast Beacon", bg_h, b_h, 255, has_pip=True, pip_active=(sync_mgr.role == ROLE_HOST), pip_col=(255, 40, 180))

        tab_client = layout["tab_client"]
        bg_c = (10, 60, 90) if sync_mgr.role == ROLE_CLIENT else (20, 26, 40)
        b_c = (0, 220, 255) if sync_mgr.role == ROLE_CLIENT else (50, 70, 95)
        self._render_button(overlay, tab_client, "[CLIENT] Remote Receiver", bg_c, b_c, 255, has_pip=True, pip_active=(sync_mgr.role == ROLE_CLIENT), pip_col=(0, 220, 255))

        content_box = layout["content_box"]
        pygame.draw.rect(overlay, (14, 18, 30), content_box, border_radius=4)
        pygame.draw.rect(overlay, (40, 55, 80), content_box, width=1, border_radius=4)
        self._draw_tech_corner_brackets(overlay, content_box, (50, 80, 120), bracket_len=8, width=1)

        cy = content_box.y + 18

        if sync_mgr.role == ROLE_STANDALONE:
            overlay.blit(self.font_main.render("// NODE CONFIGURATION: LOCAL STANDALONE", True, (255, 255, 255)), (content_box.x + 25, cy))
            lines = [
                "This node processes audio and synchronizes strobes locally.",
                "",
                "TO LINK MULTIPLE RIGS INTO A SYNCHRONIZED MESH:",
                " > Select [HOST] on the primary rig connected to DJ / audio source.",
                " > Select [CLIENT] on all satellite rigs or secondary laptops.",
                " > Clients automatically discover host beacons via Bluetooth & Local Network.",
            ]
            for i, line in enumerate(lines):
                col = (0, 220, 255) if line.startswith("TO LINK") else (180, 195, 215)
                overlay.blit(self.font_small.render(line, True, col), (content_box.x + 25, cy + 32 + i * 22))

        elif sync_mgr.role == ROLE_HOST:
            overlay.blit(self.font_main.render("[STATUS: HOST ACTIVE] Broadcasting Telemetry & Beats", True, (100, 255, 170)), (content_box.x + 25, cy))

            info_lines = [
                f"HOST IDENTIFIER:  {sync_mgr.hostname}",
                f"BLUETOOTH MAC:    {sync_mgr.local_bt_mac} (RFCOMM Channel {sync_mgr.bt_channel})",
                f"NETWORK IP:       {sync_mgr.local_ip}:{sync_mgr.tcp_port}",
                "",
                f"[SYNC_MESH] Connected Client Rigs: {sync_mgr.client_count} unit(s)",
                "",
                "CONNECTION PROTOCOL:",
                f" > Bluetooth: Pair devices or search for '{sync_mgr.hostname}' ({sync_mgr.local_bt_mac})",
                f" > Wi-Fi / LAN: Connect to same subnet or specify IP '{sync_mgr.local_ip}'",
            ]
            for i, line in enumerate(info_lines):
                col = (255, 220, 100) if "Connected Client" in line else (200, 212, 230)
                overlay.blit(self.font_small.render(line, True, col), (content_box.x + 25, cy + 28 + i * 20))

        elif sync_mgr.role == ROLE_CLIENT:
            status_col = (100, 255, 170) if sync_mgr.client_sock else (255, 200, 50)
            overlay.blit(self.font_main.render(f"CLIENT TELEMETRY: {sync_mgr.client_status}", True, status_col), (content_box.x + 25, cy))

            self.host_item_rects = []
            if sync_mgr.client_sock:
                conn_info = [
                    f"[SYNCED] Connected to Host: {sync_mgr.client_connected_host}",
                    f"LATENCY: {sync_mgr.client_latency_ms:.1f} ms [SUB-FRAME SYNCHRONIZATION]",
                    "",
                    "Local audio engine standby - slaved to live host beat packets.",
                ]
                for i, line in enumerate(conn_info):
                    overlay.blit(self.font_small.render(line, True, (220, 230, 245)), (content_box.x + 25, cy + 35 + i * 24))

                self._render_button(overlay, layout["btn_disc"], "[DISCONNECT]", (60, 22, 28), (255, 70, 70), 255)

            else:
                overlay.blit(self.font_small.render("Discovered Host Beacons & Nearby Bluetooth Nodes:", True, (160, 180, 205)), (content_box.x + 25, cy + 24))

                discovered = sync_mgr.get_all_discovered_hosts()
                item_y = cy + 46

                if not discovered:
                    overlay.blit(self.font_small.render("Scanning bus for Bluetooth hosts and network beacons...", True, (210, 190, 110)), (content_box.x + 35, item_y + 12))
                else:
                    for idx, host_entry in enumerate(discovered[:4]):
                        item_rect = pygame.Rect(content_box.x + 20, item_y, content_box.width - 40, 36)
                        pygame.draw.rect(overlay, (20, 26, 42), item_rect, border_radius=4)
                        pygame.draw.rect(overlay, (50, 70, 95), item_rect, width=1, border_radius=4)

                        name_surf = self.font_small.render(f"{host_entry['name']}", True, (255, 255, 255))
                        addr_surf = self.font_tiny.render(f"({host_entry['type']}: {host_entry['address']})", True, (140, 160, 190))
                        overlay.blit(name_surf, (item_rect.x + 12, item_rect.y + 10))
                        overlay.blit(addr_surf, (item_rect.x + 24 + name_surf.get_width(), item_rect.y + 11))

                        btn_conn = pygame.Rect(item_rect.x + item_rect.width - 95, item_rect.y + 4, 85, 28)
                        self._render_button(overlay, btn_conn, "[CONNECT]", (10, 80, 110), (0, 220, 255), 255)
                        self.host_item_rects.append((btn_conn, host_entry))

                        item_y += 40

                self._render_button(overlay, layout["btn_rescan"], "[SCAN] Rescan Bus", (25, 38, 55), (100, 200, 255), 255)

                if self.entering_custom_host:
                    inp_rect = layout["inp_rect"]
                    pygame.draw.rect(overlay, (10, 14, 24), inp_rect, border_radius=4)
                    pygame.draw.rect(overlay, (0, 240, 255), inp_rect, width=1, border_radius=4)

                    display_txt = self.custom_host_input or "Enter IP (e.g. 192.168.1.5) or BT MAC"
                    txt_col = (255, 255, 255) if self.custom_host_input else (120, 135, 155)
                    inp_surf = self.font_small.render(display_txt, True, txt_col)
                    overlay.blit(inp_surf, (inp_rect.x + 10, inp_rect.y + 8))

                    self._render_button(overlay, layout["btn_submit"], "[SUBMIT]", (10, 80, 60), (0, 255, 180), 255)
                else:
                    self._render_button(overlay, layout["btn_manual"], "[MANUAL] Enter Host IP / MAC", (25, 38, 55), (150, 180, 220), 255)

        screen.blit(overlay, (0, 0))

    def _render_warning_dialog(self, screen):
        """Render high-tech epilepsy & photosensitivity safety warning dialog."""
        dialog_rect, btn_start, btn_safe = self._get_warning_dialog_layout()
        dx, dy = dialog_rect.x, dialog_rect.y

        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))

        pygame.draw.rect(overlay, (14, 18, 30), dialog_rect, border_radius=6)
        pygame.draw.rect(overlay, (255, 60, 60), dialog_rect, width=1, border_radius=6)
        self._draw_tech_corner_brackets(overlay, dialog_rect, (255, 70, 70), bracket_len=14, width=2)

        warn_title = self.font_title.render("// SYSTEM PROTOCOL ADVISORY: PHOTOSENSITIVITY & SEIZURE RISK", True, (255, 80, 80))
        overlay.blit(warn_title, (dx + 25, dy + 22))

        lines = [
            "This application produces high-intensity strobing colors and rapid light flashes",
            "synchronized to audio telemetry in real-time across connected displays.",
            "",
            "If you or anyone in your environment has an epileptic condition or experiences",
            "light-triggered seizures, migraines, or severe eye strain, please engage",
            "Safe Mode (gentle pulsing glow) or terminate execution immediately.",
        ]
        curr_y = dy + 62
        for line in lines:
            line_surf = self.font_small.render(line, True, (215, 225, 235))
            overlay.blit(line_surf, (dx + 25, curr_y))
            curr_y += 22

        pygame.draw.rect(overlay, (80, 15, 30), btn_start, border_radius=4)
        pygame.draw.rect(overlay, (255, 40, 80), btn_start, width=1, border_radius=4)
        s_txt = self.font_main.render("ENGAGE FULL STROBE [ENTER]", True, (255, 255, 255))
        overlay.blit(s_txt, (btn_start.x + (btn_start.width - s_txt.get_width()) // 2, btn_start.y + 16))

        pygame.draw.rect(overlay, (10, 60, 40), btn_safe, border_radius=4)
        pygame.draw.rect(overlay, (0, 220, 150), btn_safe, width=1, border_radius=4)
        safe_txt = self.font_main.render("ENGAGE SAFE GLOW MODE [S]", True, (255, 255, 255))
        overlay.blit(safe_txt, (btn_safe.x + (btn_safe.width - safe_txt.get_width()) // 2, btn_safe.y + 16))

        screen.blit(overlay, (0, 0))
