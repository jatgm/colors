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
    MODE_ALBUM_ART,
    PALETTE_ALBUM_ART,
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

        # Active dragging state for sliders
        self.dragging_slider = None

        # Discovered host button rectangles
        self.host_item_rects = []

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
        """Build responsive sci-fi telemetry HUD layout with balanced proportions."""
        mon = self.active_mon_rect
        panel_w = min(880, mon.width - 40)
        panel_h = 276
        panel_x = mon.x + (mon.width - panel_w) // 2
        panel_y = mon.y + mon.height - panel_h - 16

        self.panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        # Top Right: Now Playing Native Album Cover Artwork Card
        card_w = min(220, max(180, (panel_w - 60) // 4))
        card_h = 44
        card_x = panel_x + panel_w - card_w - 20
        card_y = panel_y + 38
        self.card_album_art = pygame.Rect(card_x, card_y, card_w, card_h)

        # Middle: Telemetry Sliders (Sensitivity, Pre-Amp Boost, Decay Speed)
        slider_label_w = 110
        slider_x = panel_x + 20 + slider_label_w
        slider_val_w = 64
        slider_w = panel_w - 40 - slider_label_w - slider_val_w
        self.slider_sens_rect = pygame.Rect(slider_x, panel_y + 92, slider_w, 12)
        self.slider_gain_rect = pygame.Rect(slider_x, panel_y + 112, slider_w, 12)
        self.slider_decay_rect = pygame.Rect(slider_x, panel_y + 132, slider_w, 12)

        # Bottom Command Matrix: Balanced 2-Row Arrangement
        pad_x = 18
        avail_w = panel_w - 2 * pad_x
        btn_h = 30

        # Row 1 (Visual, Display & Album Controls - 6 buttons)
        gap1 = 8
        bw1 = (avail_w - 5 * gap1) // 6
        by1 = panel_y + 158
        self.btn_mode = pygame.Rect(panel_x + pad_x, by1, bw1, btn_h)
        self.btn_palette = pygame.Rect(panel_x + pad_x + (bw1 + gap1), by1, bw1, btn_h)
        self.btn_style = pygame.Rect(panel_x + pad_x + (bw1 + gap1) * 2, by1, bw1, btn_h)
        self.btn_album_art = pygame.Rect(panel_x + pad_x + (bw1 + gap1) * 3, by1, bw1, btn_h)
        self.btn_dualfx = pygame.Rect(panel_x + pad_x + (bw1 + gap1) * 4, by1, bw1, btn_h)
        self.btn_displays = pygame.Rect(panel_x + pad_x + (bw1 + gap1) * 5, by1, bw1, btn_h)

        # Row 2 (Engine, Hardware & Sync Controls - 7 buttons)
        gap2 = 6
        bw2 = (avail_w - 6 * gap2) // 7
        by2 = by1 + 36
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

        # Action Buttons
        if self.btn_mode.collidepoint(pos):
            visualizer.cycle_mode()
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

    def handle_mouse_motion(self, pos, audio_mgr, visualizer, display_mgr):
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

        # Dynamic Sci-Fi Border & Corner Brackets Color
        if visualizer.overdrive_mode:
            accent_col = (255, 60, 45)
            title_text = "// SYS_TELEMETRY: OVERDRIVE_ENGAGED"
            title_col = (255, 80, 60)
        elif visualizer.safe_mode:
            accent_col = (0, 240, 150)
            title_text = "// SYS_TELEMETRY: SAFE_GLOW_PROTOCOL"
            title_col = (80, 240, 160)
        else:
            accent_col = (0, 230, 255)
            title_text = "// SYS_TELEMETRY: DUAL_CORE_ACTIVE"
            title_col = (210, 240, 255)

        # Draw Frame & Corner Brackets (clamped within rect bounds)
        frame_col = (*accent_col, min(140, alpha_int))
        pygame.draw.rect(hud_surf, frame_col, panel, width=1, border_radius=6)
        self._draw_tech_corner_brackets(hud_surf, panel, (*accent_col, min(230, alpha_int)), bracket_len=12, width=2)

        # Top Header Divider Bar
        header_h = 28
        header_surf = pygame.Surface((panel.width, header_h), pygame.SRCALPHA)
        header_surf.fill((16, 22, 36, min(200, alpha_int)))
        hud_surf.blit(header_surf, (panel.x, panel.y))
        pygame.draw.line(hud_surf, (*accent_col, min(100, alpha_int)), (panel.x + 10, panel.y + header_h), (panel.right - 10, panel.y + header_h))

        # Title Telemetry Tag
        t_surf = self.font_title.render(title_text, True, title_col)
        hud_surf.blit(t_surf, (panel.x + 14, panel.y + 6))

        # Audio source tag & Hardware Diagnostic badging (ZERO emojis)
        raw_p = audio_state.get("raw_peak", 0.0)
        agc_g = audio_state.get("agc_gain", 1.0)

        hw_tags = []
        if razer_mgr and razer_mgr.device_count > 0:
            hw_tags.append(f"[RZ:{razer_mgr.device_count}]" if razer_mgr.enabled else "[RZ:OFF]")
        if happylighting_mgr:
            if happylighting_mgr.connected:
                hw_tags.append("[RM:ON]" if happylighting_mgr.enabled else "[RM:OFF]")
            elif happylighting_mgr.enabled:
                hw_tags.append("[RM:SYNC]")
        if lenovo_mgr and lenovo_mgr.connected:
            hw_tags.append("[LG:ON]" if lenovo_mgr.enabled else "[LG:OFF]")

        hw_str = " " + " ".join(hw_tags) if hw_tags else ""
        diag_str = f"PK:{int(raw_p * 100)}% AGC:{agc_g:.1f}x{hw_str}"

        if sync_mgr.role == ROLE_CLIENT:
            lat = sync_mgr.client_latency_ms
            lat_str = f" {lat:.0f}ms" if lat > 0 else ""
            dev_tag = f"[SLAVE] {sync_mgr.client_connected_host or 'SEARCH'}{lat_str}"
            dev_col = (100, 240, 255)
        elif sync_mgr.role == ROLE_HOST:
            dev_tag = f"[HOST] {diag_str} // NODES:{sync_mgr.client_count}"
            dev_col = (255, 120, 220)
        else:
            dev_name = audio_mgr.current_device_name if audio_mgr else "DEFAULT_IN"
            if len(dev_name) > 18:
                dev_name = dev_name[:16] + ".."
            dev_tag = f"[SRC] {dev_name} // {diag_str}"
            dev_col = (100, 255, 170) if (audio_mgr and not audio_mgr.demo_mode) else (255, 180, 50)

        # Dynamic truncation to strictly prevent header text collision
        max_right_w = panel.width - t_surf.get_width() - 36
        if max_right_w > 60:
            if self.font_small.size(dev_tag)[0] > max_right_w:
                while len(dev_tag) > 6 and self.font_small.size(dev_tag + "..")[0] > max_right_w:
                    dev_tag = dev_tag[:-1]
                dev_tag = dev_tag + ".."
            dev_surf = self.font_small.render(dev_tag, True, dev_col)
            hud_surf.blit(dev_surf, (panel.right - dev_surf.get_width() - 14, panel.y + 8))

        # 2. Audio Telemetry Deck (Top Row: 24-Band Spectrum, VU Meters, Reticle BPM, Album Card)
        spec_x = panel.x + 20
        spec_y = panel.y + 36
        avail_for_audio = max(240, self.card_album_art.x - spec_x - 30)
        spec_w = min(220, int(avail_for_audio * 0.46))
        spec_h = 44

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
                # Glowing peak cap
                if bh > 4:
                    cap_rect = pygame.Rect(int(bx), spec_y + spec_h - bh, max(2, int(bw)), 2)
                    pygame.draw.rect(hud_surf, (255, 255, 255, alpha_int), cap_rect)

        # Frequency VU Level Meters (Segmented sci-fi telemetry bars)
        levels_x = spec_x + spec_w + 14
        levels_y = spec_y
        meter_w = min(96, int(avail_for_audio * 0.21))
        meter_h = 10

        b_val = audio_state.get("bass_level", 0.0)
        m_val = audio_state.get("mid_level", 0.0)
        h_val = audio_state.get("high_level", 0.0)

        # [BASS]
        hud_surf.blit(self.font_tiny.render("[BASS]", True, (255, 90, 130)), (levels_x, levels_y - 1))
        self._render_segmented_vu(hud_surf, levels_x + 36, levels_y + 1, meter_w, meter_h, b_val, (255, 40, 100), alpha_int)

        # [MID]
        hud_surf.blit(self.font_tiny.render("[MID]", True, (60, 240, 140)), (levels_x, levels_y + 15))
        self._render_segmented_vu(hud_surf, levels_x + 36, levels_y + 17, meter_w, meter_h, m_val, (50, 240, 130), alpha_int)

        # [HIGH]
        hud_surf.blit(self.font_tiny.render("[HIGH]", True, (70, 200, 255)), (levels_x, levels_y + 31))
        self._render_segmented_vu(hud_surf, levels_x + 36, levels_y + 33, meter_w, meter_h, h_val, (60, 210, 255), alpha_int)

        # Beat Pulse Reticle & BPM
        beat_x = levels_x + 36 + meter_w + 22
        beat_y = levels_y + 20
        is_beating = visualizer.kick_intensity > 0.4

        # Sci-Fi Circular Crosshair Reticle
        reticle_col = (255, 40, 120) if is_beating else (45, 60, 80)
        pygame.draw.circle(hud_surf, reticle_col, (beat_x, beat_y), 13, width=1)
        # Tick marks on reticle
        pygame.draw.line(hud_surf, reticle_col, (beat_x - 16, beat_y), (beat_x - 11, beat_y))
        pygame.draw.line(hud_surf, reticle_col, (beat_x + 11, beat_y), (beat_x + 16, beat_y))
        pygame.draw.line(hud_surf, reticle_col, (beat_x, beat_y - 16), (beat_x, beat_y - 11))
        pygame.draw.line(hud_surf, reticle_col, (beat_x, beat_y + 11), (beat_x, beat_y + 16))

        if is_beating:
            pygame.draw.circle(hud_surf, (255, 50, 140, alpha_int), (beat_x, beat_y), 8)
            pygame.draw.circle(hud_surf, (255, 255, 255, alpha_int), (beat_x, beat_y), 4)
        else:
            pygame.draw.circle(hud_surf, (35, 45, 60, alpha_int), (beat_x, beat_y), 3)

        hud_surf.blit(self.font_tiny.render("BEAT", True, (140, 160, 185)), (beat_x - 11, beat_y + 18))

        bpm = audio_state.get("bpm", 0.0)
        bpm_str = f"{int(round(bpm))} BPM" if bpm > 30 else "-- BPM"
        bpm_surf = self.font_title.render(bpm_str, True, (0, 240, 255))
        hud_surf.blit(bpm_surf, (beat_x + 22, beat_y - 10))

        # Now Playing Native Album Cover Artwork Card (Sci-Fi Media Terminal)
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

            # Thumbnail or Tech Art Icon
            if hud_thumb:
                hud_surf.blit(hud_thumb, (card_rect.x + 2, card_rect.y + 2))
            else:
                icon_rect = pygame.Rect(card_rect.x + 2, card_rect.y + 2, 40, 40)
                pygame.draw.rect(hud_surf, (22, 28, 42, alpha_int), icon_rect, border_radius=3)
                note_surf = self.font_main.render("ART", True, (0, 220, 255))
                hud_surf.blit(note_surf, (card_rect.x + 8, card_rect.y + 12))

            raw_title = media_info.get("title", "") or "No Media Playing"
            raw_artist = media_info.get("artist", "") or ("WinRT Active" if media_info.get("has_art") else "Audio Standby")

            max_char = max(11, (card_rect.width - 95) // 8)
            disp_title = (raw_title[:max_char] + "..") if len(raw_title) > max_char + 2 else raw_title
            disp_artist = (raw_artist[:max_char + 2] + "..") if len(raw_artist) > max_char + 4 else raw_artist

            t_col = (255, 255, 255) if is_art_active else (205, 215, 230)
            t_surf = self.font_small.render(disp_title, True, t_col)
            a_surf = self.font_tiny.render(disp_artist, True, (130, 145, 170))
            hud_surf.blit(t_surf, (card_rect.x + 46, card_rect.y + 3))
            hud_surf.blit(a_surf, (card_rect.x + 46, card_rect.y + 17))

            # Extracted Palette Color Swatch Chips
            chip_y = card_rect.y + 31
            chip_w = 11
            chip_h = 7
            for ci, col in enumerate(album_pal[:5]):
                cx = card_rect.x + 46 + ci * (chip_w + 3)
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

        # 3. Precision Telemetry Sliders (Sensitivity, Pre-Amp Boost, Decay Speed)
        sens = audio_mgr.get_sensitivity() if audio_mgr else 1.0
        pre_g = audio_mgr.get_preamp_gain() if audio_mgr else 1.0
        decay = visualizer.decay_rate

        # Slider 1: Sensitivity
        hud_surf.blit(self.font_small.render("// SENSITIVITY", True, (180, 210, 230)), (panel.x + 20, self.slider_sens_rect.y - 1))
        self._render_slider(hud_surf, self.slider_sens_rect, sens, MIN_SENSITIVITY, MAX_SENSITIVITY, (0, 220, 255), alpha_int)
        v_sens = self.font_small.render(f"[ {sens:.1f}x ]", True, (0, 240, 255))
        hud_surf.blit(v_sens, (self.slider_sens_rect.right + 10, self.slider_sens_rect.y - 1))

        # Slider 2: Pre-Amp Boost
        hud_surf.blit(self.font_small.render("// PREAMP_BOOST", True, (255, 205, 120)), (panel.x + 20, self.slider_gain_rect.y - 1))
        self._render_slider(hud_surf, self.slider_gain_rect, pre_g, MIN_PREAMP_GAIN, MAX_PREAMP_GAIN, (255, 180, 50), alpha_int)
        v_gain = self.font_small.render(f"[ {pre_g:.1f}x ]", True, (255, 190, 60))
        hud_surf.blit(v_gain, (self.slider_gain_rect.right + 10, self.slider_gain_rect.y - 1))

        # Slider 3: Decay Speed
        hud_surf.blit(self.font_small.render("// DECAY_RATE", True, (255, 140, 90)), (panel.x + 20, self.slider_decay_rect.y - 1))
        self._render_slider(hud_surf, self.slider_decay_rect, decay, MIN_DECAY_RATE, MAX_DECAY_RATE, (255, 95, 30), alpha_int)
        v_decay = self.font_small.render(f"[ {decay:.0f} ]", True, (255, 110, 40))
        hud_surf.blit(v_decay, (self.slider_decay_rect.right + 10, self.slider_decay_rect.y - 1))

        # Section Accent Line
        sep_y = panel.y + 150
        pygame.draw.line(hud_surf, (*accent_col, min(45, alpha_int)), (panel.x + 18, sep_y), (panel.right - 18, sep_y))

        # 4. Command Matrix: Balanced 2-Row Arrangement
        # --- Row 1: Visual, Display & Album Controls (6 buttons) ---
        m_txt = visualizer.mode
        if m_txt.startswith("[") and "]" in m_txt:
            m_txt = m_txt.split("]", 1)[1].strip()
        self._render_button(hud_surf, self.btn_mode, f"[MODE] {m_txt}", (18, 24, 38), (0, 200, 255), alpha_int)

        p_txt = visualizer.palette_name
        if p_txt.startswith("[") and "]" in p_txt:
            p_txt = p_txt.split("]", 1)[1].strip()
        self._render_button(hud_surf, self.btn_palette, f"[PAL] {p_txt}", (26, 20, 36), (240, 40, 180), alpha_int)

        self._render_button(hud_surf, self.btn_style, f"[STYLE] {visualizer.current_style}", (22, 22, 40), (160, 110, 255), alpha_int)

        art_active = (visualizer.mode == MODE_ALBUM_ART or visualizer.palette_name == PALETTE_ALBUM_ART)
        art_bg = (10, 45, 60) if art_active else (18, 24, 38)
        art_border = (0, 240, 255) if art_active else (60, 80, 105)
        self._render_button(hud_surf, self.btn_album_art, "[ALBUM] SYNC",
                            art_bg, art_border, alpha_int, has_pip=True, pip_active=art_active, pip_col=(0, 240, 255))

        dual_txt = visualizer.dual_scheme if is_dual else "SINGLE"
        self._render_button(hud_surf, self.btn_dualfx, f"[DUAL] {dual_txt}", (30, 24, 45), (200, 110, 255), alpha_int)

        disp_txt = getattr(display_mgr, "current_mode", "Windowed") if display_mgr else "Win"
        self._render_button(hud_surf, self.btn_displays, f"[DISP] {disp_txt}", (22, 30, 48), (100, 190, 255), alpha_int)

        # --- Row 2: Engine, Hardware & Sync Controls (7 buttons) ---
        self._render_button(hud_surf, self.btn_device, "[DEV] AUDIO IN", (18, 28, 40), (80, 220, 190), alpha_int)

        if sync_mgr.role == ROLE_HOST:
            sync_label = f"[SYNC] HOST ({sync_mgr.client_count})"
            sync_bg = (40, 20, 50)
            sync_border = (230, 90, 255)
        elif sync_mgr.role == ROLE_CLIENT:
            c_tag = "LINK" if sync_mgr.client_sock else "SCAN"
            sync_label = f"[SYNC] {c_tag}"
            sync_bg = (15, 38, 52)
            sync_border = (0, 220, 255)
        else:
            sync_label = "[SYNC] BT/LAN"
            sync_bg = (18, 24, 38)
            sync_border = (90, 140, 190)
        self._render_button(hud_surf, self.btn_sync, sync_label, sync_bg, sync_border, alpha_int)

        # Overdrive [OVR]
        ovr_active = visualizer.overdrive_mode
        ovr_bg = (70, 18, 22) if ovr_active else (24, 18, 24)
        ovr_border = (255, 60, 45) if ovr_active else (110, 50, 50)
        self._render_button(hud_surf, self.btn_overdrive, "[OVR] CRAZY",
                            ovr_bg, ovr_border, alpha_int, has_pip=True, pip_active=ovr_active, pip_col=(255, 60, 45))

        # Safe Mode [SAFE]
        safe_active = visualizer.safe_mode
        safe_bg = (15, 48, 30) if safe_active else (18, 24, 34)
        safe_border = (0, 240, 150) if safe_active else (60, 90, 80)
        self._render_button(hud_surf, self.btn_safe, "[SAFE] GLOW",
                            safe_bg, safe_border, alpha_int, has_pip=True, pip_active=safe_active, pip_col=(0, 240, 150))

        # Razer Chroma [RAZER]
        if razer_mgr and razer_mgr.device_count > 0:
            rz_active = razer_mgr.enabled
            rz_label = f"[RAZER] ({razer_mgr.device_count})"
            rz_bg = (12, 48, 22) if rz_active else (18, 24, 34)
            rz_border = (0, 255, 120) if rz_active else (60, 90, 75)
        else:
            rz_active = False
            rz_label = "[RAZER] N/A"
            rz_bg = (18, 20, 28)
            rz_border = (50, 60, 75)
        self._render_button(hud_surf, self.btn_razer, rz_label, rz_bg, rz_border, alpha_int, has_pip=True, pip_active=rz_active, pip_col=(0, 255, 120))

        # Room Lighting [ROOM]
        if happylighting_mgr:
            if happylighting_mgr.connected:
                hl_active = happylighting_mgr.enabled
                hl_label = "[ROOM] BLE"
                hl_bg = (12, 45, 55) if hl_active else (18, 24, 34)
                hl_border = (0, 240, 255) if hl_active else (60, 80, 95)
                hl_pip = (0, 240, 255)
            elif happylighting_mgr.enabled:
                hl_active = True
                hl_label = "[ROOM] SYNC"
                hl_bg = (45, 40, 18)
                hl_border = (255, 210, 0)
                hl_pip = (255, 210, 0)
            else:
                hl_active = False
                hl_label = "[ROOM] BLE"
                hl_bg = (18, 20, 28)
                hl_border = (50, 60, 75)
                hl_pip = None
        else:
            hl_active = False
            hl_label = "[ROOM] N/A"
            hl_bg = (18, 20, 28)
            hl_border = (50, 60, 75)
            hl_pip = None
        self._render_button(hud_surf, self.btn_room_lights, hl_label, hl_bg, hl_border, alpha_int, has_pip=True, pip_active=hl_active, pip_col=hl_pip)

        # Lenovo Legion [LEGION]
        if lenovo_mgr and lenovo_mgr.connected:
            legion_active = lenovo_mgr.enabled
            legion_label = "[LEGION] PC"
            legion_bg = (14, 40, 58) if legion_active else (18, 24, 34)
            legion_border = (0, 190, 255) if legion_active else (60, 80, 95)
        else:
            legion_active = False
            legion_label = "[LEGION] N/A"
            legion_bg = (18, 20, 28)
            legion_border = (50, 60, 75)
        self._render_button(hud_surf, self.btn_lenovo, legion_label, legion_bg, legion_border, alpha_int, has_pip=True, pip_active=legion_active, pip_col=(0, 190, 255))

        # 5. Hotkey & System Telemetry Footer
        hints = "// HOTKEYS: [ESC] Exit  [X] Overdrive  [A] AlbumArt  [C] Razer  [L] Room  [K] Legion  [F] Displays  [B] DualFX  [N] Sync  [M] Mode  [P] Palette  [S] Safe  [H] ToggleHUD"
        hint_surf = self.font_tiny.render(hints, True, (130, 145, 170))
        hud_surf.blit(hint_surf, (panel.x + (panel.width - hint_surf.get_width()) // 2, panel.bottom - 20))

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
