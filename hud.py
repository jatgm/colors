"""
Sleek Sci-Fi / Cyberpunk HUD (Heads-Up Display) and interactive UI.
Features translucent frosted glassmorphism panels, angular bracketed telemetry frames,
clean monospace typography, glowing minimalist status pips, and responsive controls.
STRICT REQUIREMENT: Zero emojis. Pure high-tech telemetry and geometric accents.
"""

import time
import math
from collections import deque
import numpy as np
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
    MODE_COLORS_2_0,
    MODE_COLORS_1_0,
    MODE_STROBE_2_0,
    MODE_CLASSIC_RAPID,
    MODE_RED_ONLY,
    MODE_ALBUM_ART,
    PALETTE_ALBUM_ART,
    SOLID_COLORS,
    SOLID_COLOR_NAMES,
    STROBE_MODES,
    PALETTES,
    PALETTE_NAMES,
)
from visualizer import DUAL_SCHEMES
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

        # Monospace / Sci-Fi Telemetry Fonts (Scaled up for comfortable readability)
        pygame.font.init()
        font_stack = "Consolas, Lucida Console, Segoe UI, monospace"
        self.font_title = pygame.font.SysFont(font_stack, 20, bold=True)
        self.font_section = pygame.font.SysFont(font_stack, 15, bold=True)
        self.font_main = pygame.font.SysFont(font_stack, 14, bold=True)
        self.font_small = pygame.font.SysFont(font_stack, 13)
        self.font_tiny = pygame.font.SysFont(font_stack, 12)
        self.font_warning = pygame.font.SysFont(font_stack, 14)

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

        # Interactive Dropdown Selectors State
        self.open_dropdown = None  # None or "mode", "palette", "device", "style", "dualfx", "display"
        self.dropdown_items = []   # list of (screen_rect, val, label, is_active, extra)
        self.dropdown_menu_rect = None
        self.hover_dropdown_item_idx = -1

        # Real-time logic & math telemetry console
        self.show_console = False
        self.badge_engine = None
        self.btn_console = None
        self.console_close_btn = None
        self.console_rect = None
        self.telemetry_history = deque(maxlen=140)
        self.spectrum_peaks = [0.0] * 24
        self.chroma_logs = deque(maxlen=40)
        self._last_chroma_log_t = 0.0

        self._build_layout()

    def resize(self, width, height, active_mon_rect=None):
        self.open_dropdown = None
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
        self.open_dropdown = None
        self.manually_hidden = not self.manually_hidden
        self.visible = not self.manually_hidden
        self.last_interaction_time = time.time()

    def toggle_sync_modal(self):
        self.open_dropdown = None
        self.show_sync_modal = not self.show_sync_modal
        self.notify_interaction()

    def toggle_console(self):
        self.show_console = not self.show_console
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
        """Build sleek, redesigned modern cyber-studio HUD layout with dropdown selectors and modular pods."""
        mon = self.active_mon_rect
        panel_w = min(1040, mon.width - 32)
        panel_h = 282
        panel_x = mon.x + (mon.width - panel_w) // 2
        panel_y = mon.y + mon.height - panel_h - 14

        self.panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        pad_x = 18
        avail_w = panel_w - 2 * pad_x

        # Top Right: Now Playing Native Album Cover Artwork Card
        card_w = min(220, max(180, (panel_w - 60) // 4))
        card_h = 38
        card_x = panel_x + panel_w - card_w - 18
        card_y = panel_y + 6
        self.card_album_art = pygame.Rect(card_x, card_y, card_w, card_h)

        # Waveform Song Progress Bar Deck (height 80px for rich dynamic response)
        wf_x = panel_x + 18
        wf_y = panel_y + 46
        wf_w = panel_w - 36
        wf_h = 80
        self.waveform_rect = pygame.Rect(wf_x, wf_y, wf_w, wf_h)

        # Middle: 3 Sliders Side-by-Side in 1 sleek row
        gap_sliders = 14
        col_w = (avail_w - 2 * gap_sliders) // 3
        s_y = panel_y + 132

        # Slider 1: SENS
        lbl_w1 = 34
        val_w1 = 48
        bar_w1 = max(40, col_w - lbl_w1 - val_w1 - 8)
        self.slider_sens_rect = pygame.Rect(panel_x + pad_x + lbl_w1 + 4, s_y + 3, bar_w1, 10)

        # Slider 2: GAIN
        col2_x = panel_x + pad_x + col_w + gap_sliders
        lbl_w2 = 34
        val_w2 = 48
        bar_w2 = max(40, col_w - lbl_w2 - val_w2 - 8)
        self.slider_gain_rect = pygame.Rect(col2_x + lbl_w2 + 4, s_y + 3, bar_w2, 10)

        # Slider 3: DECAY
        col3_x = col2_x + col_w + gap_sliders
        lbl_w3 = 40
        val_w3 = 42
        bar_w3 = max(40, col_w - lbl_w3 - val_w3 - 8)
        self.slider_decay_rect = pygame.Rect(col3_x + lbl_w3 + 4, s_y + 3, bar_w3, 10)

        # Interactive Dropdown Selectors Bar (6 Dropdowns: Mode, Palette, Device, Style, DualFX, Displays)
        drop_gap = 6
        drop_w = (avail_w - 5 * drop_gap) // 6
        drop_h = 28
        drop_y = panel_y + 154

        self.btn_mode = pygame.Rect(panel_x + pad_x, drop_y, drop_w, drop_h)
        self.btn_palette = pygame.Rect(panel_x + pad_x + (drop_w + drop_gap), drop_y, drop_w, drop_h)
        self.btn_device = pygame.Rect(panel_x + pad_x + (drop_w + drop_gap) * 2, drop_y, drop_w, drop_h)
        self.btn_style = pygame.Rect(panel_x + pad_x + (drop_w + drop_gap) * 3, drop_y, drop_w, drop_h)
        self.btn_dualfx = pygame.Rect(panel_x + pad_x + (drop_w + drop_gap) * 4, drop_y, drop_w, drop_h)
        self.btn_displays = pygame.Rect(panel_x + pad_x + (drop_w + drop_gap) * 5, drop_y, drop_w, drop_h)

        # Solid Color Lighting Control Deck & Swatches Bar
        solid_y = panel_y + 188
        solid_h = 22
        btn_solid_w = 124
        self.btn_solid_toggle = pygame.Rect(panel_x + pad_x, solid_y, btn_solid_w, solid_h)

        name_badge_w = 72
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

        # Quick Toggles & Hardware Pods (8 Buttons: 4 Engine Toggles + 4 Hardware Toggles)
        btn_h = 24
        gap_tog = 5
        bw_tog = (avail_w - 7 * gap_tog) // 8
        by_tog = panel_y + 216

        self.btn_overdrive = pygame.Rect(panel_x + pad_x, by_tog, bw_tog, btn_h)
        self.btn_engine = pygame.Rect(panel_x + pad_x + (bw_tog + gap_tog), by_tog, bw_tog, btn_h)
        self.btn_mode_2_0 = self.btn_engine
        self.btn_album_art = pygame.Rect(panel_x + pad_x + (bw_tog + gap_tog) * 2, by_tog, bw_tog, btn_h)
        self.btn_safe = pygame.Rect(panel_x + pad_x + (bw_tog + gap_tog) * 3, by_tog, bw_tog, btn_h)
        self.btn_razer = pygame.Rect(panel_x + pad_x + (bw_tog + gap_tog) * 4, by_tog, bw_tog, btn_h)
        self.btn_room_lights = pygame.Rect(panel_x + pad_x + (bw_tog + gap_tog) * 5, by_tog, bw_tog, btn_h)
        self.btn_lenovo = pygame.Rect(panel_x + pad_x + (bw_tog + gap_tog) * 6, by_tog, bw_tog, btn_h)
        self.btn_sync = pygame.Rect(panel_x + pad_x + (bw_tog + gap_tog) * 7, by_tog, bw_tog, btn_h)

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

        # Real-time logic & math telemetry console interaction (functional even when HUD panel is hidden)
        if self.show_console and hasattr(self, "console_rect") and self.console_rect and self.console_rect.collidepoint(pos):
            if hasattr(self, "console_close_btn") and self.console_close_btn and self.console_close_btn.collidepoint(pos):
                self.show_console = False
            return True

        if not self.visible or self.alpha < 30:
            return False

        # -----------------------------------------------------------------
        # 0. Active Dropdown Popover Menu Interaction
        # -----------------------------------------------------------------
        if self.open_dropdown is not None:
            # 1. Check if user clicked an item inside the open dropdown menu
            for item_rect, item_val, item_label, is_act, extra in self.dropdown_items:
                if item_rect.collidepoint(pos):
                    if self.open_dropdown == "mode" and visualizer:
                        visualizer.set_mode(item_val)
                    elif self.open_dropdown == "palette" and visualizer:
                        visualizer.set_palette(item_val)
                    elif self.open_dropdown == "device" and audio_mgr:
                        audio_mgr.select_device(item_val, manual=True)
                    elif self.open_dropdown == "style" and visualizer:
                        if hasattr(visualizer, "set_style"):
                            visualizer.set_style(item_val)
                        else:
                            visualizer.current_style = item_val
                    elif self.open_dropdown == "dualfx" and visualizer:
                        if hasattr(visualizer, "set_dual_scheme"):
                            visualizer.set_dual_scheme(item_val)
                        else:
                            visualizer.dual_scheme = item_val
                    elif self.open_dropdown == "display" and display_mgr:
                        if hasattr(display_mgr, "set_display_mode"):
                            display_mgr.set_display_mode(item_val)
                        else:
                            display_mgr.current_mode = item_val
                        if on_display_change:
                            on_display_change()

                    self.open_dropdown = None
                    return True

            # 2. Check if click is inside the dropdown menu panel
            if self.dropdown_menu_rect and self.dropdown_menu_rect.collidepoint(pos):
                return True

            # 3. Check if user clicked the toggle button of the current open dropdown to close it
            clicked_same_btn = False
            if self.open_dropdown == "mode" and self.btn_mode.collidepoint(pos):
                clicked_same_btn = True
            elif self.open_dropdown == "palette" and self.btn_palette.collidepoint(pos):
                clicked_same_btn = True
            elif self.open_dropdown == "device" and self.btn_device.collidepoint(pos):
                clicked_same_btn = True
            elif self.open_dropdown == "style" and self.btn_style.collidepoint(pos):
                clicked_same_btn = True
            elif self.open_dropdown == "dualfx" and self.btn_dualfx.collidepoint(pos):
                clicked_same_btn = True
            elif self.open_dropdown == "display" and self.btn_displays.collidepoint(pos):
                clicked_same_btn = True

            if clicked_same_btn:
                self.open_dropdown = None
                return True

            # 4. Otherwise, clicking outside closes the dropdown
            self.open_dropdown = None

        # -----------------------------------------------------------------
        # Header Controls: Obvious Engine Badge & Real-Time Console Log
        # -----------------------------------------------------------------
        if hasattr(self, "badge_engine") and self.badge_engine and self.badge_engine.collidepoint(pos):
            if visualizer:
                visualizer.toggle_engine()
            return True
        elif hasattr(self, "btn_console") and self.btn_console and self.btn_console.collidepoint(pos):
            self.toggle_console()
            return True

        # -----------------------------------------------------------------
        # 1. Waveform Progress Bar Deck Interactive Seeking
        # -----------------------------------------------------------------
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

        # -----------------------------------------------------------------
        # 2. Precision Mixer Sliders Deck
        # -----------------------------------------------------------------
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

        # -----------------------------------------------------------------
        # 3. Interactive Dropdown Selectors Triggers
        # -----------------------------------------------------------------
        if self.btn_mode.collidepoint(pos):
            self.open_dropdown = "mode" if self.open_dropdown != "mode" else None
            return True
        elif self.btn_palette.collidepoint(pos):
            self.open_dropdown = "palette" if self.open_dropdown != "palette" else None
            return True
        elif self.btn_device.collidepoint(pos):
            self.open_dropdown = "device" if self.open_dropdown != "device" else None
            return True
        elif self.btn_style.collidepoint(pos):
            self.open_dropdown = "style" if self.open_dropdown != "style" else None
            return True
        elif self.btn_dualfx.collidepoint(pos):
            self.open_dropdown = "dualfx" if self.open_dropdown != "dualfx" else None
            return True
        elif self.btn_displays.collidepoint(pos):
            self.open_dropdown = "display" if self.open_dropdown != "display" else None
            return True

        # -----------------------------------------------------------------
        # 4. Ambient Solid Lighting Controls & Swatches
        # -----------------------------------------------------------------
        if hasattr(self, "btn_solid_toggle") and self.btn_solid_toggle and self.btn_solid_toggle.collidepoint(pos):
            if visualizer:
                visualizer.toggle_solid_color()
            return True

        if hasattr(self, "solid_swatch_rects"):
            for s_rect, idx, s_name, s_rgb in self.solid_swatch_rects:
                if s_rect.collidepoint(pos):
                    if visualizer:
                        visualizer.set_solid_color(idx, activate=True)
                    return True

        if hasattr(self, "solid_name_rect") and self.solid_name_rect and self.solid_name_rect.collidepoint(pos):
            if visualizer:
                visualizer.cycle_solid_color()
            return True

        # -----------------------------------------------------------------
        # 5. Quick Toggles & Hardware Pods
        # -----------------------------------------------------------------
        if (hasattr(self, "btn_engine") and self.btn_engine.collidepoint(pos)) or (hasattr(self, "btn_mode_2_0") and self.btn_mode_2_0.collidepoint(pos)):
            if visualizer:
                visualizer.toggle_engine()
            return True
        elif hasattr(self, "btn_album_art") and self.btn_album_art.collidepoint(pos):
            if visualizer:
                visualizer.toggle_album_art_mode()
            return True
        elif hasattr(self, "card_album_art") and self.card_album_art.collidepoint(pos):
            if visualizer:
                visualizer.toggle_album_art_mode()
            return True
        elif self.btn_overdrive.collidepoint(pos):
            if visualizer:
                visualizer.toggle_overdrive()
            if audio_mgr and visualizer:
                audio_mgr.set_overdrive(visualizer.overdrive_mode)
            return True
        elif self.btn_safe.collidepoint(pos):
            if visualizer:
                visualizer.toggle_safe_mode()
            if audio_mgr and visualizer:
                audio_mgr.set_overdrive(visualizer.overdrive_mode)
            return True
        elif self.btn_sync.collidepoint(pos):
            self.toggle_sync_modal()
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

        if self.open_dropdown is not None:
            self.hover_dropdown_item_idx = -1
            for idx, (item_rect, _, _, _, _) in enumerate(self.dropdown_items):
                if item_rect.collidepoint(pos):
                    self.hover_dropdown_item_idx = idx
                    break

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
        self._update_telemetry_history(audio_state, visualizer)

        if not self.warning_dismissed:
            self._render_warning_dialog(screen)
            return

        if self.show_sync_modal:
            self._render_sync_modal(screen, sync_mgr)
            return

        if self.alpha <= 1.0:
            if self.show_console:
                self._render_console_log(screen, audio_state, visualizer, audio_mgr, razer_mgr=razer_mgr)
            return

        alpha_int = int(self.alpha)
        hud_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        panel = self.panel_rect

        # 1. Main Frosted Glassmorphism Panel Backing
        panel_bg = (10, 14, 24, min(238, alpha_int))
        pygame.draw.rect(hud_surf, panel_bg, panel, border_radius=6)

        # Dynamic Accent Color
        is_c1 = visualizer.is_colors_1_0_active() if hasattr(visualizer, "is_colors_1_0_active") else False
        is_c2 = visualizer.is_colors_2_0_active() if hasattr(visualizer, "is_colors_2_0_active") else True

        if getattr(visualizer, "solid_color_active", False):
            accent_col = (255, 205, 50)
        elif visualizer.is_album_art_active():
            accent_col = (0, 240, 255)
        elif visualizer.overdrive_mode:
            accent_col = (255, 60, 45)
        elif visualizer.safe_mode:
            accent_col = (0, 240, 150)
        elif is_c1:
            accent_col = (255, 140, 20)
        else:
            accent_col = (0, 240, 255)

        # Draw Frame & Corner Brackets (clamped within rect bounds)
        frame_col = (*accent_col, min(140, alpha_int))
        pygame.draw.rect(hud_surf, frame_col, panel, width=1, border_radius=6)
        self._draw_tech_corner_brackets(hud_surf, panel, (*accent_col, min(220, alpha_int)), bracket_len=10, width=2)

        # Top Header Divider Bar
        header_h = 42
        header_surf = pygame.Surface((panel.width, header_h), pygame.SRCALPHA)
        header_surf.fill((14, 18, 28, min(210, alpha_int)))
        hud_surf.blit(header_surf, (panel.x, panel.y))
        pygame.draw.line(hud_surf, (*accent_col, min(50, alpha_int)), (panel.x + 8, panel.y + header_h), (panel.right - 8, panel.y + header_h))

        # Title: colors
        t_surf = self.font_title.render("colors", True, (240, 245, 255))
        hud_surf.blit(t_surf, (panel.x + 14, panel.y + 9))

        # Obvious & Prominent Engine Selection Badge (Clickable, does not affect light mode)
        eng_name = "colors2.0" if is_c2 else "colors1.0"
        eng_fg = (0, 240, 255) if is_c2 else (255, 140, 20)
        eng_bg = (10, 36, 52) if is_c2 else (48, 24, 12)
        eng_tw = self.font_tiny.size(eng_name)[0] + 16
        self.badge_engine = pygame.Rect(panel.x + 14 + t_surf.get_width() + 10, panel.y + 9, eng_tw, 20)
        pygame.draw.rect(hud_surf, (*eng_bg, alpha_int), self.badge_engine, border_radius=3)
        pygame.draw.rect(hud_surf, (*eng_fg, min(220, alpha_int)), self.badge_engine, width=1, border_radius=3)
        eng_render = self.font_tiny.render(eng_name, True, eng_fg)
        hud_surf.blit(eng_render, (self.badge_engine.x + (self.badge_engine.width - eng_render.get_width()) // 2, self.badge_engine.y + (20 - eng_render.get_height()) // 2))

        cur_hdr_x = self.badge_engine.right + 8

        # Dedicated Light Mode Indicator Pill (Separate, Does Not Affect or Obscure Engine Select)
        if getattr(visualizer, "solid_color_active", False):
            c_name = visualizer.get_solid_color_name() if hasattr(visualizer, "get_solid_color_name") else "SOLID"
            light_text = f"LIGHT: {c_name.upper()}"
            light_fg = (255, 215, 70)
            light_bg = (44, 34, 14)
            l_tw = self.font_tiny.size(light_text)[0] + 14
            light_pill_rect = pygame.Rect(cur_hdr_x, panel.y + 9, l_tw, 20)
            pygame.draw.rect(hud_surf, (*light_bg, alpha_int), light_pill_rect, border_radius=3)
            pygame.draw.rect(hud_surf, (*light_fg, min(180, alpha_int)), light_pill_rect, width=1, border_radius=3)
            l_render = self.font_tiny.render(light_text, True, light_fg)
            hud_surf.blit(l_render, (light_pill_rect.x + (light_pill_rect.width - l_render.get_width()) // 2, light_pill_rect.y + (20 - l_render.get_height()) // 2))
            cur_hdr_x = light_pill_rect.right + 8

        # Status Pill for Special Visual Modes (Overdrive / Album Art / Red Only)
        special_pill = None
        if visualizer.overdrive_mode:
            special_pill = ("OVERDRIVE", (255, 80, 60), (45, 16, 20))
        elif visualizer.is_album_art_active():
            special_pill = ("ALBUM ART", (0, 240, 255), (12, 38, 52))
        elif visualizer.safe_mode:
            special_pill = ("SAFE GLOW", (80, 240, 160), (12, 42, 26))
        elif visualizer.mode == MODE_RED_ONLY:
            special_pill = ("RED ONLY", (255, 50, 65), (45, 12, 18))

        if special_pill:
            sp_txt, sp_fg, sp_bg = special_pill
            sp_tw = self.font_tiny.size(sp_txt)[0] + 14
            sp_rect = pygame.Rect(cur_hdr_x, panel.y + 9, sp_tw, 20)
            pygame.draw.rect(hud_surf, (*sp_bg, alpha_int), sp_rect, border_radius=3)
            pygame.draw.rect(hud_surf, (*sp_fg, min(180, alpha_int)), sp_rect, width=1, border_radius=3)
            sp_render = self.font_tiny.render(sp_txt, True, sp_fg)
            hud_surf.blit(sp_render, (sp_rect.x + (sp_rect.width - sp_render.get_width()) // 2, sp_rect.y + (20 - sp_render.get_height()) // 2))
            cur_hdr_x = sp_rect.right + 8

        # Real-Time Telemetry & Math Console Toggle Button
        con_text = "CONSOLE LOG [~]" if not self.show_console else "CONSOLE LOG [ACTIVE]"
        con_fg = (0, 255, 180) if self.show_console else (140, 180, 210)
        con_bg = (10, 48, 36) if self.show_console else (16, 24, 36)
        con_tw = self.font_tiny.size(con_text)[0] + 16
        self.btn_console = pygame.Rect(cur_hdr_x, panel.y + 9, con_tw, 20)
        pygame.draw.rect(hud_surf, (*con_bg, alpha_int), self.btn_console, border_radius=3)
        pygame.draw.rect(hud_surf, (*con_fg, min(180, alpha_int)), self.btn_console, width=1, border_radius=3)
        con_render = self.font_tiny.render(con_text, True, con_fg)
        hud_surf.blit(con_render, (self.btn_console.x + (self.btn_console.width - con_render.get_width()) // 2, self.btn_console.y + (20 - con_render.get_height()) // 2))

        left_hdr_end = self.btn_console.right + 14

        # Right Header Pills (Source, Hardware, Network) - anchored cleanly to left of card
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

        card_anchor_x = self.card_album_art.x if hasattr(self, "card_album_art") else (panel.right - 238)
        rx = card_anchor_x - 12
        for p_name, p_fg, p_bg in reversed(right_pills):
            p_tw = self.font_tiny.size(p_name)[0] + 12
            rx -= p_tw
            r_pill = pygame.Rect(rx, panel.y + 9, p_tw, 20)
            pygame.draw.rect(hud_surf, (*p_bg, alpha_int), r_pill, border_radius=3)
            pygame.draw.rect(hud_surf, (*p_fg, min(140, alpha_int)), r_pill, width=1, border_radius=3)
            p_render = self.font_tiny.render(p_name, True, p_fg)
            hud_surf.blit(p_render, (r_pill.x + (r_pill.width - p_render.get_width()) // 2, r_pill.y + (20 - p_render.get_height()) // 2))
            rx -= 6

        # 2. Audio & Media Deck (Center Row: Spectrum, VU, BPM bounded without clipping)
        audio_zone_right = max(left_hdr_end + 200, rx - 10)
        avail_for_audio = max(180, audio_zone_right - left_hdr_end)

        spec_x = left_hdr_end
        spec_y = panel.y + 10
        spec_w = min(130, max(50, int(avail_for_audio * 0.36)))
        spec_h = 26

        # Background chamber for spectrum
        spec_bg = pygame.Rect(spec_x - 3, spec_y - 2, spec_w + 6, spec_h + 4)
        pygame.draw.rect(hud_surf, (14, 18, 28, alpha_int), spec_bg, border_radius=3)
        pygame.draw.rect(hud_surf, (30, 48, 68, alpha_int), spec_bg, width=1, border_radius=3)

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
                if bh > 3:
                    cap_rect = pygame.Rect(int(bx), spec_y + spec_h - bh, max(2, int(bw)), 2)
                    pygame.draw.rect(hud_surf, (255, 255, 255, alpha_int), cap_rect)

        # Frequency VU Level Meters (BAS, MID, HIG - 100% visible above waveform)
        levels_x = spec_x + spec_w + 12
        levels_y = panel.y + 8
        meter_w = min(68, max(36, int(avail_for_audio * 0.20)))
        meter_h = 6

        b_val = audio_state.get("bass_level", 0.0)
        m_val = audio_state.get("mid_level", 0.0)
        h_val = audio_state.get("high_level", 0.0)

        hud_surf.blit(self.font_tiny.render("BAS", True, (255, 90, 130)), (levels_x, levels_y - 2))
        self._render_segmented_vu(hud_surf, levels_x + 28, levels_y, meter_w, meter_h, b_val, (255, 40, 100), alpha_int)

        hud_surf.blit(self.font_tiny.render("MID", True, (60, 240, 140)), (levels_x, levels_y + 10))
        self._render_segmented_vu(hud_surf, levels_x + 28, levels_y + 12, meter_w, meter_h, m_val, (50, 240, 130), alpha_int)

        hud_surf.blit(self.font_tiny.render("HIG", True, (70, 200, 255)), (levels_x, levels_y + 22))
        self._render_segmented_vu(hud_surf, levels_x + 28, levels_y + 24, meter_w, meter_h, h_val, (60, 210, 255), alpha_int)

        # Beat Pulse Reticle & BPM
        beat_x = levels_x + 28 + meter_w + 14
        beat_y = panel.y + 20
        is_beating = visualizer.kick_intensity > 0.4

        reticle_col = (255, 40, 120) if is_beating else (45, 60, 80)
        pygame.draw.circle(hud_surf, reticle_col, (beat_x, beat_y), 9, width=1)
        if is_beating:
            pygame.draw.circle(hud_surf, (255, 50, 140, alpha_int), (beat_x, beat_y), 6)
            pygame.draw.circle(hud_surf, (255, 255, 255, alpha_int), (beat_x, beat_y), 2)
        else:
            pygame.draw.circle(hud_surf, (35, 45, 60, alpha_int), (beat_x, beat_y), 2)

        bpm = audio_state.get("bpm", 0.0)
        bpm_str = f"{int(round(bpm))} BPM" if bpm > 30 else "-- BPM"
        bpm_surf = self.font_title.render(bpm_str, True, (0, 240, 255))
        hud_surf.blit(bpm_surf, (beat_x + 14, beat_y - 14))

        pitch_name = audio_state.get("pitch_name", "C")
        sec_name = audio_state.get("section_name", "VERSE")
        pitch_badge = f"KEY:{pitch_name}"
        p_surf = self.font_tiny.render(pitch_badge, True, (255, 120, 220))
        hud_surf.blit(p_surf, (beat_x + 14, beat_y + 4))

        if sec_name == "CHORUS":
            sec_surf = self.font_tiny.render("[CHORUS]", True, (255, 60, 180))
        elif sec_name == "BUILDUP":
            sec_surf = self.font_tiny.render("[BUILDUP]", True, (255, 200, 40))
        else:
            sec_surf = self.font_tiny.render("[VERSE]", True, (0, 220, 255))
        hud_surf.blit(sec_surf, (beat_x + 14 + p_surf.get_width() + 6, beat_y + 4))

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
            pygame.draw.rect(hud_surf, (12, 16, 26, alpha_int), wf_rect, border_radius=4)
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
                badge_str = "[PAUSED]" if is_paused else ("[TRACK SYNC]" if is_playing else "[STOPPED]")
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
        lbl_sens = self.font_tiny.render("SENS", True, (170, 200, 220))
        hud_surf.blit(lbl_sens, (self.slider_sens_rect.x - lbl_sens.get_width() - 5, self.slider_sens_rect.y - 1))
        self._render_slider(hud_surf, self.slider_sens_rect, sens, MIN_SENSITIVITY, MAX_SENSITIVITY, (0, 220, 255), alpha_int)
        v_sens = self.font_tiny.render(f"{sens:.1f}x", True, (0, 240, 255))
        hud_surf.blit(v_sens, (self.slider_sens_rect.right + 6, self.slider_sens_rect.y - 1))

        # Slider 2: GAIN
        lbl_gain = self.font_tiny.render("GAIN", True, (240, 195, 120))
        hud_surf.blit(lbl_gain, (self.slider_gain_rect.x - lbl_gain.get_width() - 5, self.slider_gain_rect.y - 1))
        self._render_slider(hud_surf, self.slider_gain_rect, pre_g, MIN_PREAMP_GAIN, MAX_PREAMP_GAIN, (255, 180, 50), alpha_int)
        v_gain = self.font_tiny.render(f"{pre_g:.1f}x", True, (255, 190, 60))
        hud_surf.blit(v_gain, (self.slider_gain_rect.right + 6, self.slider_gain_rect.y - 1))

        # Slider 3: DECAY
        lbl_decay = self.font_tiny.render("DECAY", True, (240, 140, 90))
        hud_surf.blit(lbl_decay, (self.slider_decay_rect.x - lbl_decay.get_width() - 5, self.slider_decay_rect.y - 1))
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
        sep_y = panel.y + 208
        pygame.draw.line(hud_surf, (*accent_col, min(45, alpha_int)), (panel.x + 18, sep_y), (panel.right - 18, sep_y))

        # 5. Interactive Dropdown Selectors Bar
        # 5.1 Mode Selector Dropdown
        m_label = visualizer.mode if visualizer else "Mode"
        self._render_dropdown_selector(
            hud_surf, self.btn_mode, "MODE", m_label, (self.open_dropdown == "mode"), alpha_int, (0, 240, 255)
        )

        # 5.2 Palette Selector Dropdown
        p_label = visualizer.palette_name if visualizer else "Palette"
        self._render_dropdown_selector(
            hud_surf, self.btn_palette, "PALETTE", p_label, (self.open_dropdown == "palette"), alpha_int, (255, 60, 180)
        )

        # 5.3 Audio Source Selector Dropdown
        is_spotify_active = (audio_mgr and getattr(audio_mgr, "devices", None) and
                             len(audio_mgr.devices) > audio_mgr.current_device_index and
                             audio_mgr.devices[audio_mgr.current_device_index] == "spotify")
        dev_label = "Spotify (ISO)" if is_spotify_active else (audio_mgr.current_device_name if audio_mgr else "Audio In")
        self._render_dropdown_selector(
            hud_surf, self.btn_device, "AUDIO IN", dev_label, (self.open_dropdown == "device"), alpha_int, (0, 255, 140)
        )

        # 5.4 Visual Style Selector Dropdown
        s_label = visualizer.current_style if visualizer else "Style"
        self._render_dropdown_selector(
            hud_surf, self.btn_style, "STYLE", s_label, (self.open_dropdown == "style"), alpha_int, (180, 100, 255)
        )

        # 5.5 Dual Monitor FX Dropdown
        dual_label = visualizer.dual_scheme if (visualizer and is_dual) else "Single Mon"
        self._render_dropdown_selector(
            hud_surf, self.btn_dualfx, "DUAL FX", dual_label, (self.open_dropdown == "dualfx"), alpha_int, (220, 120, 255)
        )

        # 5.6 Display Arrangement Dropdown
        disp_label = display_mgr.current_mode if display_mgr else "Display"
        self._render_dropdown_selector(
            hud_surf, self.btn_displays, "DISPLAY", disp_label, (self.open_dropdown == "display"), alpha_int, (100, 200, 255)
        )

        # 6. Quick Engine & Hardware Toggles Pod (8 Buttons)
        # 6.1 Crazy Overdrive Toggle
        ovr_active = visualizer.overdrive_mode if visualizer else False
        ovr_bg = (70, 18, 22) if ovr_active else (24, 18, 24)
        ovr_border = (255, 60, 45) if ovr_active else (110, 50, 50)
        self._render_button(hud_surf, self.btn_overdrive, "Overdrive",
                            ovr_bg, ovr_border, alpha_int, has_pip=True, pip_active=ovr_active, pip_col=(255, 60, 45))

        # 6.2 Active Detection Engine Indicator / Toggle
        if visualizer and visualizer.is_colors_1_0_active():
            eng_label = "ENG: colors1.0"
            eng_pip_col = (255, 140, 20)
            eng_bg = (48, 24, 12)
            eng_border = (255, 140, 20)
        else:
            eng_label = "ENG: colors2.0"
            eng_pip_col = (0, 240, 255)
            eng_bg = (12, 36, 52)
            eng_border = (0, 240, 255)

        btn_eng = getattr(self, "btn_engine", getattr(self, "btn_mode_2_0", None))
        if btn_eng:
            self._render_button(hud_surf, btn_eng, eng_label,
                                eng_bg, eng_border, alpha_int, has_pip=True, pip_active=True, pip_col=eng_pip_col)

        # 6.3 Album Cover Art Sync Toggle
        art_active = visualizer.is_album_art_active() if visualizer else False
        art_bg = (10, 45, 60) if art_active else (18, 24, 38)
        art_border = (0, 240, 255) if art_active else (60, 80, 105)
        self._render_button(hud_surf, self.btn_album_art, "Album Sync",
                            art_bg, art_border, alpha_int, has_pip=True, pip_active=art_active, pip_col=(0, 240, 255))

        # 6.4 Safe Glow Mode Toggle
        safe_active = visualizer.safe_mode if visualizer else False
        safe_bg = (15, 48, 30) if safe_active else (18, 24, 34)
        safe_border = (0, 240, 150) if safe_active else (60, 90, 80)
        self._render_button(hud_surf, self.btn_safe, "Safe Glow",
                            safe_bg, safe_border, alpha_int, has_pip=True, pip_active=safe_active, pip_col=(0, 240, 150))

        # 6.5 Razer Chroma Peripheral Lighting
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

        # 6.6 HappyLighting BLE Room Light Strips
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

        # 6.7 Lenovo Legion Gaming Desktop PC RGB
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

        # 6.8 Multi-Computer Network / BT Mesh Sync
        if sync_mgr and sync_mgr.role == ROLE_HOST:
            sync_label = "Sync: Host"
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

        # 7. Minimal Clean Footer Navigation Strip
        hints = "ESC Exit/Close   ~ / Shift+C Console Log   2 colors2.0   3 colors1.0   X Overdrive   A Album   O Light Mode   P Palette   TAB Hide HUD"
        hint_surf = self.font_tiny.render(hints, True, (120, 138, 165))
        hud_surf.blit(hint_surf, (panel.x + (panel.width - hint_surf.get_width()) // 2, panel.bottom - 16))

        hud_surf.set_alpha(alpha_int)
        screen.blit(hud_surf, (0, 0))

        # 8. Render Real-Time Logic & Math Telemetry Console
        if self.show_console:
            self._render_console_log(screen, audio_state, visualizer, audio_mgr, razer_mgr=razer_mgr)

        # 9. Render Floating Dropdown Popover Menu (on top of everything)
        if self.open_dropdown is not None:
            self._render_dropdown_menu(screen, audio_mgr, visualizer, display_mgr)

    def _render_dropdown_selector(self, surf, rect, category_label, value_str, is_open, alpha, accent_col):
        """Render modern cyber-studio dropdown selector button with category label, value, and vector chevron."""
        bg_col = (20, 36, 52) if is_open else (14, 18, 28)
        border_col = accent_col if is_open else (48, 68, 92)

        pygame.draw.rect(surf, (*bg_col, alpha), rect, border_radius=4)
        pygame.draw.rect(surf, (*border_col, alpha), rect, width=1, border_radius=4)

        if is_open:
            self._draw_tech_corner_brackets(surf, rect, (*accent_col, alpha), bracket_len=5, width=1)

        cat_surf = self.font_tiny.render(category_label, True, (130, 155, 185))
        surf.blit(cat_surf, (rect.x + 6, rect.y + 2))

        avail_w = max(10, rect.width - 20)
        clean_val = str(value_str)
        if clean_val.startswith("[") and "]" in clean_val and not clean_val.startswith("[App:"):
            clean_val = clean_val.split("]", 1)[1].strip()

        if self.font_small.size(clean_val)[0] > avail_w:
            while len(clean_val) > 3 and self.font_small.size(clean_val + "..")[0] > avail_w:
                clean_val = clean_val[:-1]
            clean_val = clean_val + ".."

        val_col = (255, 255, 255) if is_open else (230, 240, 255)
        v_surf = self.font_small.render(clean_val, True, val_col)
        surf.blit(v_surf, (rect.x + 6, rect.y + 13))

        ch_x = rect.right - 9
        ch_y = rect.y + rect.height // 2 + 3
        ch_col = accent_col if is_open else (120, 145, 175)
        if is_open:
            pygame.draw.polygon(surf, (*ch_col, alpha), [(ch_x - 4, ch_y + 2), (ch_x + 4, ch_y + 2), (ch_x, ch_y - 3)])
        else:
            pygame.draw.polygon(surf, (*ch_col, alpha), [(ch_x - 4, ch_y - 2), (ch_x + 4, ch_y - 2), (ch_x, ch_y + 3)])

    def _render_dropdown_menu(self, screen, audio_mgr, visualizer, display_mgr):
        """Render floating drop-up popover menu with interactive items, swatches, and active checkmarks."""
        if not self.open_dropdown:
            return

        hover_pos = self.mouse_hover_pos
        self.dropdown_items = []

        if self.open_dropdown == "mode":
            menu_title = "// SELECT STROBE MODE"
            accent_col = (0, 240, 255)
            target_btn = self.btn_mode
            cur_val = visualizer.mode if visualizer else ""
            raw_items = [(m, m, (m == cur_val), None) for m in STROBE_MODES]

        elif self.open_dropdown == "palette":
            menu_title = "// SELECT COLOR PALETTE"
            accent_col = (255, 60, 180)
            target_btn = self.btn_palette
            cur_val = visualizer.palette_name if visualizer else ""
            raw_items = []
            for p_name in PALETTE_NAMES:
                swatches = PALETTES.get(p_name, [])[:4]
                raw_items.append((p_name, p_name, (p_name == cur_val), swatches))

        elif self.open_dropdown == "device":
            menu_title = "// SELECT AUDIO SOURCE"
            accent_col = (0, 255, 140)
            target_btn = self.btn_device
            cur_idx = audio_mgr.current_device_index if audio_mgr else 0
            dev_names = audio_mgr.device_names if audio_mgr else ["Default Output"]
            raw_items = []
            for i, d_name in enumerate(dev_names):
                raw_items.append((i, d_name, (i == cur_idx), None))

        elif self.open_dropdown == "style":
            menu_title = "// SELECT VISUAL STYLE"
            accent_col = (180, 100, 255)
            target_btn = self.btn_style
            cur_style = visualizer.current_style if visualizer else "Solid Fullscreen"
            styles = visualizer.visual_styles if visualizer else ["Solid Fullscreen", "Radial Shockwave", "Horizon Pulse"]
            raw_items = [(i, s, (s == cur_style), None) for i, s in enumerate(styles)]

        elif self.open_dropdown == "dualfx":
            menu_title = "// SELECT DUAL MONITOR SCHEME"
            accent_col = (220, 120, 255)
            target_btn = self.btn_dualfx
            cur_scheme = visualizer.dual_scheme if visualizer else "Dual Synced"
            raw_items = [(i, sch, (sch == cur_scheme), None) for i, sch in enumerate(DUAL_SCHEMES)]

        elif self.open_dropdown == "display":
            menu_title = "// SELECT DISPLAY ARRANGEMENT"
            accent_col = (100, 200, 255)
            target_btn = self.btn_displays
            cur_mode = display_mgr.current_mode if display_mgr else "Windowed"
            modes = display_mgr.available_modes if display_mgr else ["Windowed"]
            raw_items = [(i, md, (md == cur_mode), None) for i, md in enumerate(modes)]

        else:
            return

        num_items = len(raw_items)
        use_two_cols = (num_items > 6)

        if use_two_cols:
            col_w = 176
            menu_w = col_w * 2 + 16
            num_rows = (num_items + 1) // 2
            item_h = 24
            menu_h = 30 + num_rows * item_h + 8
        else:
            col_w = max(210, target_btn.width + 20)
            menu_w = col_w + 16
            item_h = 24
            menu_h = 30 + num_items * item_h + 8

        menu_x = max(self.panel_rect.x + 8, min(self.panel_rect.right - menu_w - 8, target_btn.centerx - menu_w // 2))
        menu_y = max(10, target_btn.y - menu_h - 4)
        self.dropdown_menu_rect = pygame.Rect(menu_x, menu_y, menu_w, menu_h)

        drop_surf = pygame.Surface((menu_w, menu_h), pygame.SRCALPHA)
        drop_surf.fill((10, 15, 26, 252))

        pygame.draw.rect(drop_surf, (*accent_col, 220), pygame.Rect(0, 0, menu_w, menu_h), width=1, border_radius=6)
        self._draw_tech_corner_brackets(drop_surf, pygame.Rect(0, 0, menu_w, menu_h), (*accent_col, 255), bracket_len=8, width=2)

        header_rect = pygame.Rect(1, 1, menu_w - 2, 24)
        pygame.draw.rect(drop_surf, (16, 24, 38, 250), header_rect, border_top_left_radius=5, border_top_right_radius=5)
        pygame.draw.line(drop_surf, (*accent_col, 100), (4, 25), (menu_w - 4, 25))

        h_title_surf = self.font_tiny.render(menu_title, True, accent_col)
        drop_surf.blit(h_title_surf, (10, 6))

        close_hint = self.font_tiny.render("[ESC]", True, (110, 130, 155))
        drop_surf.blit(close_hint, (menu_w - close_hint.get_width() - 8, 6))

        for idx, (item_val, item_label, is_act, swatches) in enumerate(raw_items):
            if use_two_cols:
                col = idx % 2
                row = idx // 2
                ix = 8 + col * col_w
                iy = 28 + row * item_h
                iw = col_w - 4
            else:
                ix = 8
                iy = 28 + idx * item_h
                iw = col_w

            item_rect_local = pygame.Rect(ix, iy, iw, item_h - 2)
            item_rect_screen = pygame.Rect(menu_x + ix, menu_y + iy, iw, item_h - 2)

            is_hov = bool(hover_pos and item_rect_screen.collidepoint(hover_pos))
            self.dropdown_items.append((item_rect_screen, item_val, item_label, is_act, swatches))

            if is_act:
                bg_col = (18, 48, 68, 255)
                bdr_col = (*accent_col, 180)
            elif is_hov:
                bg_col = (28, 38, 54, 255)
                bdr_col = (75, 110, 150, 160)
            else:
                bg_col = (14, 18, 30, 200)
                bdr_col = (30, 42, 60, 100)

            pygame.draw.rect(drop_surf, bg_col, item_rect_local, border_radius=3)
            pygame.draw.rect(drop_surf, bdr_col, item_rect_local, width=1, border_radius=3)

            pip_x = ix + 8
            pip_y = iy + (item_h - 2) // 2
            if is_act:
                pygame.draw.circle(drop_surf, (*accent_col, 255), (pip_x, pip_y), 3)
                pygame.draw.circle(drop_surf, (255, 255, 255, 255), (pip_x, pip_y), 1)
            elif is_hov:
                pygame.draw.circle(drop_surf, (150, 200, 255, 255), (pip_x, pip_y), 2)
            else:
                pygame.draw.circle(drop_surf, (45, 60, 80, 255), (pip_x, pip_y), 2)

            swatch_reserve_w = 0
            if swatches:
                swatch_reserve_w = len(swatches) * 9 + 6
                sw_x = ix + iw - swatch_reserve_w
                sw_y = iy + 5
                for s_col in swatches:
                    pygame.draw.rect(drop_surf, (*s_col, 255), (sw_x, sw_y, 7, item_h - 12), border_radius=1)
                    sw_x += 9

            text_x = ix + 16
            avail_tw = max(10, iw - 20 - swatch_reserve_w)

            clean_lbl = str(item_label)
            if clean_lbl.startswith("[") and "]" in clean_lbl and not clean_lbl.startswith("[App:"):
                clean_lbl = clean_lbl.split("]", 1)[1].strip()

            if self.font_small.size(clean_lbl)[0] > avail_tw:
                while len(clean_lbl) > 3 and self.font_small.size(clean_lbl + "..")[0] > avail_tw:
                    clean_lbl = clean_lbl[:-1]
                clean_lbl = clean_lbl + ".."

            if is_act:
                txt_col = (255, 255, 255)
            elif is_hov:
                txt_col = (220, 240, 255)
            else:
                txt_col = (165, 185, 210)

            t_surf = self.font_small.render(clean_lbl, True, txt_col)
            drop_surf.blit(t_surf, (text_x, iy + 3))

        screen.blit(drop_surf, (menu_x, menu_y))

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

    def _update_telemetry_history(self, audio_state, visualizer):
        """Record real-time audio and trigger conversion telemetry frames into rolling history."""
        if not hasattr(self, "telemetry_history"):
            self.telemetry_history = deque(maxlen=140)
        if not hasattr(self, "spectrum_peaks"):
            self.spectrum_peaks = [0.0] * 24

        if not audio_state:
            audio_state = {}

        # Audio inputs & thresholds
        rms = float(audio_state.get("total_level", 0.0) or 0.0)
        peak = float(audio_state.get("peak", audio_state.get("raw_peak", 0.0)) or 0.0)
        b_flux = float(audio_state.get("bass_flux", 0.0) or 0.0)
        b_thresh = float(audio_state.get("dynamic_thresh", 0.0) or 0.0)
        h_flux = float(audio_state.get("high_flux", 0.0) or 0.0)
        h_thresh = float(audio_state.get("high_thresh", 0.0) or 0.0)
        s_flux = float(audio_state.get("sub_flux", 0.0) or 0.0)
        s_thresh = float(audio_state.get("sub_thresh", 0.0) or 0.0)

        # Transients & PLL
        grid_mult = float(audio_state.get("grid_mult", 1.0) or 1.0)
        beat_phase = float(audio_state.get("beat_phase", 0.0) or 0.0)
        is_attack = bool(audio_state.get("is_attack_transient", True))
        is_downbeat = bool(audio_state.get("is_downbeat", False))
        is_backbeat = bool(audio_state.get("is_backbeat", False))

        # Triggers / Hits
        logs = audio_state.get("telemetry_logs", [])
        last_log = logs[-1] if (logs and isinstance(logs, (list, deque))) else ""

        is_kick = bool(audio_state.get("is_kick", False)) or ("[KICK]" in last_log)
        is_snare = bool(audio_state.get("is_snare", False)) or ("[SNARE]" in last_log)
        is_808 = bool(audio_state.get("is_808", False)) or ("[808 SUB]" in last_log)
        is_hihat = bool(audio_state.get("is_hihat", False)) or ("[HIHAT]" in last_log)
        is_drop = bool(audio_state.get("is_drop", False)) or ("[DROP]" in last_log)

        # Visualizer Strobe State
        strobe_alpha = 0.0
        strobe_color = (0, 240, 255)
        if visualizer:
            strobe_alpha = float(getattr(visualizer, "last_eff_intensity_0", getattr(visualizer, "alpha", 0.0)) or 0.0)
            if strobe_alpha <= 0.0 and hasattr(visualizer, "kick_intensity"):
                strobe_alpha = max(
                    getattr(visualizer, "kick_intensity", 0.0),
                    getattr(visualizer, "snare_intensity", 0.0),
                    getattr(visualizer, "hihat_intensity", 0.0),
                )
            raw_c = getattr(visualizer, "current_color", (0, 240, 255))
            if isinstance(raw_c, (tuple, list)) and len(raw_c) >= 3:
                strobe_color = (int(raw_c[0]), int(raw_c[1]), int(raw_c[2]))

        # Update 24 spectrum peaks
        raw_bars = audio_state.get("spectrum_bars", None)
        if raw_bars is not None and len(raw_bars) > 0:
            cleaned = np.nan_to_num(np.array(raw_bars, dtype=np.float32), nan=0.0, posinf=1.0, neginf=0.0)
            if len(cleaned) == 24:
                bars_24 = cleaned
            else:
                bars_24 = np.interp(np.linspace(0, len(cleaned) - 1, 24), np.arange(len(cleaned)), cleaned)
            for idx in range(24):
                val = float(bars_24[idx])
                if val > self.spectrum_peaks[idx]:
                    self.spectrum_peaks[idx] = min(1.0, max(0.0, val))
                else:
                    self.spectrum_peaks[idx] = max(0.0, self.spectrum_peaks[idx] - 0.015)
        else:
            for idx in range(24):
                self.spectrum_peaks[idx] = max(0.0, self.spectrum_peaks[idx] - 0.015)

        self.telemetry_history.append({
            "rms": rms,
            "peak": peak,
            "b_flux": b_flux,
            "b_thresh": b_thresh,
            "h_flux": h_flux,
            "h_thresh": h_thresh,
            "s_flux": s_flux,
            "s_thresh": s_thresh,
            "grid_mult": grid_mult,
            "beat_phase": beat_phase,
            "is_attack": is_attack,
            "is_downbeat": is_downbeat,
            "is_backbeat": is_backbeat,
            "is_kick": is_kick,
            "is_snare": is_snare,
            "is_808": is_808,
            "is_hihat": is_hihat,
            "is_drop": is_drop,
            "strobe_alpha": min(1.0, max(0.0, strobe_alpha)),
            "strobe_color": strobe_color,
        })

    def _render_console_visualizer(self, c_surf, audio_state, visualizer, vis_rect, accent_col):
        """Render prominent cyber-studio engine visualizer showing real-time transients, frequency bands, and hit/strobe conversion."""
        # 1. Deck Backing and Tech Brackets
        pygame.draw.rect(c_surf, (8, 12, 20, 240), vis_rect, border_radius=5)
        pygame.draw.rect(c_surf, (24, 38, 56, 180), vis_rect, width=1, border_radius=5)
        self._draw_tech_corner_brackets(c_surf, vis_rect, (*accent_col, 180), bracket_len=8, width=1)

        # 2. Pipeline Flow Header Bar
        pipe_h = 18
        pipe_rect = pygame.Rect(vis_rect.x, vis_rect.y, vis_rect.width, pipe_h)
        pygame.draw.rect(c_surf, (14, 20, 32, 210), pipe_rect, border_top_left_radius=5, border_top_right_radius=5)
        pipe_str = "// CONVERSION PIPELINE: AUDIO INPUT -> SPECTRAL FLUX & DYNAMIC THRESHOLDS -> PLL GRID FILTER -> HIT DETONATION -> STROBE FLASH"
        c_surf.blit(self.font_tiny.render(pipe_str, True, (110, 190, 240)), (vis_rect.x + 8, vis_rect.y + 2))

        hist_len = len(self.telemetry_history)
        fps_str = f"BUFFER: {hist_len} FRAMES | LATENCY: <1.2ms"
        fps_s = self.font_tiny.render(fps_str, True, (80, 130, 175))
        c_surf.blit(fps_s, (vis_rect.right - fps_s.get_width() - 8, vis_rect.y + 2))
        pygame.draw.line(c_surf, (26, 42, 62, 160), (vis_rect.x + 4, vis_rect.y + pipe_h), (vis_rect.right - 4, vis_rect.y + pipe_h))

        # 3. Split Deck: Left Scope (64% width), Right Diagnostics (36% width)
        inner_y = vis_rect.y + pipe_h + 3
        inner_h = max(80, vis_rect.height - pipe_h - 6)
        scope_w = int((vis_rect.width - 16) * 0.64)
        scope_rect = pygame.Rect(vis_rect.x + 5, inner_y, scope_w, inner_h)

        diag_x = scope_rect.right + 6
        diag_w = vis_rect.width - (diag_x - vis_rect.x) - 5
        diag_rect = pygame.Rect(diag_x, inner_y, diag_w, inner_h)

        # -------------------------------------------------------------
        # LEFT SCOPE: Waveform, Flux Thresholds & Detonation/Flash Response
        # -------------------------------------------------------------
        pygame.draw.rect(c_surf, (5, 8, 14, 245), scope_rect, border_radius=4)
        pygame.draw.rect(c_surf, (20, 32, 48, 160), scope_rect, width=1, border_radius=4)

        det_h = 18
        scope_up_h = int((inner_h - det_h - 10) * 0.54)
        scope_up_rect = pygame.Rect(scope_rect.x + 4, scope_rect.y + 3, scope_rect.width - 8, scope_up_h)
        det_rect = pygame.Rect(scope_rect.x + 4, scope_up_rect.bottom + 2, scope_rect.width - 8, det_h)
        scope_low_rect = pygame.Rect(scope_rect.x + 4, det_rect.bottom + 2, scope_rect.width - 8, scope_rect.bottom - det_rect.bottom - 5)

        # Scope Up: Audio Waveform, Bass Flux & Dynamic Threshold Curves
        c_surf.blit(self.font_tiny.render("AUDIO INPUT: SPECTRAL FLUX (CYAN) VS DYNAMIC THRESHOLD (ORANGE) & 808 TRANSIENT", True, (90, 160, 210)), (scope_up_rect.x + 6, scope_up_rect.y + 2))

        up_base_y = scope_up_rect.bottom - 4
        up_top_y = scope_up_rect.y + 14
        up_plot_h = max(10, up_base_y - up_top_y)

        # Horizontal grid reference lines
        mid_y = up_base_y - up_plot_h // 2
        pygame.draw.line(c_surf, (20, 32, 48, 100), (scope_up_rect.x + 4, up_top_y), (scope_up_rect.right - 4, up_top_y), 1)
        pygame.draw.line(c_surf, (20, 32, 48, 80), (scope_up_rect.x + 4, mid_y), (scope_up_rect.right - 4, mid_y), 1)
        c_surf.blit(self.font_tiny.render("1.0", True, (50, 80, 110)), (scope_up_rect.right - 22, up_top_y - 5))
        c_surf.blit(self.font_tiny.render("0.5", True, (50, 80, 110)), (scope_up_rect.right - 22, mid_y - 5))

        px_left = scope_up_rect.x + 6
        px_right = scope_up_rect.right - 6
        span_w = max(10, px_right - px_left)
        max_buf = max(2, self.telemetry_history.maxlen)
        offset = max_buf - hist_len

        def get_item_x(idx):
            return px_left + int((idx + offset) * span_w / (max_buf - 1))

        # Vertical PLL Beat Grid Lines & Detonations
        if hist_len > 0:
            for i, itm in enumerate(self.telemetry_history):
                xi = get_item_x(i)
                if itm.get("is_downbeat"):
                    pygame.draw.line(c_surf, (0, 240, 255, 60), (xi, scope_up_rect.y + 2), (xi, scope_low_rect.bottom - 2), 1)
                    c_surf.blit(self.font_tiny.render("BEAT", True, (0, 240, 255, 80)), (xi - 10, scope_up_rect.y + 2))
                elif itm.get("is_backbeat"):
                    pygame.draw.line(c_surf, (255, 220, 50, 45), (xi, scope_up_rect.y + 2), (xi, scope_low_rect.bottom - 2), 1)

        # Plot curves if >= 2 points
        if hist_len >= 2:
            # 1. Shaded RMS energy contour
            poly_rms = [(get_item_x(0), up_base_y)]
            for i, itm in enumerate(self.telemetry_history):
                xi = get_item_x(i)
                yi = up_base_y - int(min(1.0, itm["rms"] * 2.2) * up_plot_h)
                poly_rms.append((xi, yi))
            poly_rms.append((get_item_x(hist_len - 1), up_base_y))
            if len(poly_rms) >= 3:
                pygame.draw.polygon(c_surf, (0, 140, 200, 32), poly_rms)

            # 2. Dynamic Threshold Line (Orange)
            pts_thresh = []
            for i, itm in enumerate(self.telemetry_history):
                xi = get_item_x(i)
                yi = up_base_y - int(min(1.0, itm["b_thresh"]) * up_plot_h)
                pts_thresh.append((xi, yi))
            if len(pts_thresh) >= 2:
                pygame.draw.lines(c_surf, (255, 145, 30), False, pts_thresh, 1)

            # 3. Bass Flux Line (Neon Cyan/Green) & Breach Highlights
            pts_flux = []
            for i, itm in enumerate(self.telemetry_history):
                xi = get_item_x(i)
                yi = up_base_y - int(min(1.2, itm["b_flux"]) * up_plot_h)
                pts_flux.append((xi, yi))

                # Highlight threshold breaches (instant where audio engine converts to trigger)
                if itm["b_flux"] >= itm["b_thresh"] and itm["b_flux"] > 0.05:
                    th_y = up_base_y - int(min(1.0, itm["b_thresh"]) * up_plot_h)
                    pygame.draw.line(c_surf, (0, 255, 180, 120), (xi, th_y), (xi, yi), 2)

                # 808 transient attack vs tail markers
                if itm.get("s_flux", 0.0) > 0.12:
                    if not itm.get("is_attack", True):
                        pygame.draw.line(c_surf, (255, 130, 60), (xi, up_base_y - 4), (xi, up_base_y), 2)
                    elif itm.get("is_808", False):
                        pygame.draw.circle(c_surf, (210, 100, 255), (xi, up_base_y - 3), 2)

            if len(pts_flux) >= 2:
                pygame.draw.lines(c_surf, (0, 255, 160), False, pts_flux, 2)

        # Detonation Conversion Track
        pygame.draw.rect(c_surf, (10, 15, 24, 230), det_rect, border_radius=2)
        pygame.draw.rect(c_surf, (24, 38, 56, 160), det_rect, width=1, border_radius=2)
        c_surf.blit(self.font_tiny.render("DETONATIONS:", True, (75, 135, 185)), (det_rect.x + 6, det_rect.y + 3))

        if hist_len > 0:
            for i, itm in enumerate(self.telemetry_history):
                xi = get_item_x(i)
                if itm.get("is_drop"):
                    pygame.draw.rect(c_surf, (255, 45, 45), (xi - 13, det_rect.y + 1, 26, 14), border_radius=2)
                    c_surf.blit(self.font_tiny.render("DROP", True, (255, 255, 255)), (xi - 11, det_rect.y + 2))
                    pygame.draw.line(c_surf, (255, 60, 60, 160), (xi, scope_up_rect.y + 2), (xi, scope_low_rect.bottom - 2), 1)
                elif itm.get("is_kick"):
                    pygame.draw.rect(c_surf, (0, 205, 110), (xi - 13, det_rect.y + 1, 26, 14), border_radius=2)
                    c_surf.blit(self.font_tiny.render("KICK", True, (8, 20, 12)), (xi - 11, det_rect.y + 2))
                    pygame.draw.line(c_surf, (0, 255, 130, 150), (xi, scope_up_rect.y + 2), (xi, scope_low_rect.bottom - 2), 1)
                elif itm.get("is_808"):
                    pygame.draw.rect(c_surf, (185, 75, 245), (xi - 11, det_rect.y + 1, 23, 14), border_radius=2)
                    c_surf.blit(self.font_tiny.render("808", True, (255, 255, 255)), (xi - 9, det_rect.y + 2))
                    pygame.draw.line(c_surf, (210, 100, 255, 150), (xi, scope_up_rect.y + 2), (xi, scope_low_rect.bottom - 2), 1)
                elif itm.get("is_snare"):
                    pygame.draw.rect(c_surf, (245, 205, 45), (xi - 15, det_rect.y + 1, 30, 14), border_radius=2)
                    c_surf.blit(self.font_tiny.render("SNARE", True, (22, 18, 5)), (xi - 13, det_rect.y + 2))
                    pygame.draw.line(c_surf, (255, 230, 60, 150), (xi, scope_up_rect.y + 2), (xi, scope_low_rect.bottom - 2), 1)
                elif itm.get("is_hihat"):
                    pygame.draw.rect(c_surf, (45, 185, 235), (xi - 11, det_rect.y + 1, 22, 14), border_radius=2)
                    c_surf.blit(self.font_tiny.render("HAT", True, (10, 20, 25)), (xi - 9, det_rect.y + 2))

        # Scope Low: Output Strobe Intensity & Decay Envelope (Screen & Hardware Response)
        c_surf.blit(self.font_tiny.render("CONVERTED STROBE OUTPUT FLASH & DECAY (SCREEN & HARDWARE LIGHTING)", True, (110, 165, 215)), (scope_low_rect.x + 6, scope_low_rect.y + 2))

        low_base_y = scope_low_rect.bottom - 4
        low_top_y = scope_low_rect.y + 14
        low_plot_h = max(10, low_base_y - low_top_y)

        if hist_len >= 2:
            poly_flash = [(get_item_x(0), low_base_y)]
            pts_flash = []
            for i, itm in enumerate(self.telemetry_history):
                xi = get_item_x(i)
                yi = low_base_y - int(itm["strobe_alpha"] * low_plot_h)
                poly_flash.append((xi, yi))
                pts_flash.append((xi, yi))
            poly_flash.append((get_item_x(hist_len - 1), low_base_y))

            last_c = self.telemetry_history[-1].get("strobe_color", (0, 240, 255))
            if len(poly_flash) >= 3:
                pygame.draw.polygon(c_surf, (*last_c, 65), poly_flash)
            if len(pts_flash) >= 2:
                pygame.draw.lines(c_surf, (*last_c, 235), False, pts_flash, 2)

        # -------------------------------------------------------------
        # RIGHT DIAGNOSTICS: 24-Band Spectrum, PLL Radar & 808 Diagnostics
        # -------------------------------------------------------------
        pygame.draw.rect(c_surf, (5, 8, 14, 245), diag_rect, border_radius=4)
        pygame.draw.rect(c_surf, (20, 32, 48, 160), diag_rect, width=1, border_radius=4)

        c_surf.blit(self.font_tiny.render("24-BAND SPECTRUM ANALYZER & PLL / 808 DIAGNOSTICS", True, (100, 210, 255)), (diag_rect.x + 8, diag_rect.y + 3))

        # 24-Band Spectrum Bars
        spec_top_y = diag_rect.y + 18
        spec_base_y = diag_rect.y + int(diag_rect.height * 0.52)
        spec_bar_h = max(10, spec_base_y - spec_top_y)
        spec_w = diag_rect.width - 16
        num_bars = 24
        bar_gap = 2
        bar_w = max(3, (spec_w - (num_bars - 1) * bar_gap) // num_bars)
        start_bx = diag_rect.x + 8 + (spec_w - (num_bars * (bar_w + bar_gap) - bar_gap)) // 2

        raw_bars = audio_state.get("spectrum_bars", None)
        bars_24 = None
        if raw_bars is not None and len(raw_bars) > 0:
            cleaned = np.nan_to_num(np.array(raw_bars, dtype=np.float32), nan=0.0, posinf=1.0, neginf=0.0)
            if len(cleaned) == 24:
                bars_24 = cleaned
            else:
                bars_24 = np.interp(np.linspace(0, len(cleaned) - 1, 24), np.arange(len(cleaned)), cleaned)

        for b in range(num_bars):
            bx = start_bx + b * (bar_w + bar_gap)
            if b < 4:
                b_col = (180, 80, 255)    # Sub-bass / 808
            elif b < 9:
                b_col = (0, 220, 255)     # Bass / Kick
            elif b < 15:
                b_col = (40, 230, 140)    # Midrange
            elif b < 20:
                b_col = (255, 215, 40)    # High-Mid / Snare
            else:
                b_col = (255, 80, 210)    # High / Air / Hi-hat

            val = float(bars_24[b]) if (bars_24 is not None and b < len(bars_24)) else 0.0
            val = min(1.0, max(0.0, val))
            bh = int(val * spec_bar_h)
            if bh > 0:
                pygame.draw.rect(c_surf, (*b_col, 210), (bx, spec_base_y - bh, bar_w, bh), border_radius=1)

            # Peak hold cap
            if hasattr(self, "spectrum_peaks") and b < len(self.spectrum_peaks):
                pv = self.spectrum_peaks[b]
                if pv > 0.03:
                    py = spec_base_y - int(pv * spec_bar_h)
                    pygame.draw.line(c_surf, (240, 250, 255), (bx, py), (bx + bar_w - 1, py), 1)

        # Zone labels below spectrum
        lbl_y = spec_base_y + 3
        c_surf.blit(self.font_tiny.render("SUB", True, (180, 80, 255)), (start_bx, lbl_y))
        c_surf.blit(self.font_tiny.render("BASS", True, (0, 220, 255)), (start_bx + 5 * (bar_w + bar_gap), lbl_y))
        c_surf.blit(self.font_tiny.render("MID", True, (40, 230, 140)), (start_bx + 11 * (bar_w + bar_gap), lbl_y))
        c_surf.blit(self.font_tiny.render("SNARE", True, (255, 215, 40)), (start_bx + 16 * (bar_w + bar_gap), lbl_y))
        c_surf.blit(self.font_tiny.render("AIR", True, (255, 80, 210)), (start_bx + 21 * (bar_w + bar_gap), lbl_y))

        # Dynamic Threshold overlay on bass & snare
        b_th = float(audio_state.get("dynamic_thresh", 0.0) or 0.0)
        if b_th > 0:
            th_y_spec = spec_base_y - int(min(1.0, b_th) * spec_bar_h)
            pygame.draw.line(c_surf, (255, 145, 30, 180), (start_bx, th_y_spec), (start_bx + 9 * (bar_w + bar_gap), th_y_spec), 1)

        # Lower Gauges: PLL Phase Runway & 808 Transient vs Tail Meter
        rem_y = lbl_y + 14
        rem_h = diag_rect.bottom - rem_y - 4

        # Gauge 1: PLL Phase Runway & Multiplier
        pll_h = min(26, rem_h // 2 - 2)
        pll_rect = pygame.Rect(diag_rect.x + 8, rem_y, diag_rect.width - 16, pll_h)
        pygame.draw.rect(c_surf, (10, 15, 24, 210), pll_rect, border_radius=3)
        pygame.draw.rect(c_surf, (24, 38, 56, 140), pll_rect, width=1, border_radius=3)

        b_phase = float(audio_state.get("beat_phase", 0.0) or 0.0)
        g_mult = float(audio_state.get("grid_mult", 1.0) or 1.0)
        on_grid = g_mult > 1.05
        g_col = (0, 255, 140) if on_grid else ((255, 150, 40) if g_mult < 0.95 else (140, 170, 200))
        g_status = "BOOST" if on_grid else ("GATED" if g_mult < 0.95 else "NORM")
        c_surf.blit(self.font_tiny.render(f"PLL PHASE [ 1 . 2 . 3 . 4 ] | MULT: {g_mult:.2f}x ({g_status})", True, g_col), (pll_rect.x + 6, pll_rect.y + 2))

        # Phase Runway track & cursor
        p_track_y = pll_rect.y + 16
        if p_track_y < pll_rect.bottom - 2:
            p_tw = pll_rect.width - 12
            pygame.draw.line(c_surf, (30, 48, 70), (pll_rect.x + 6, p_track_y), (pll_rect.x + 6 + p_tw, p_track_y), 2)
            for q in [0.0, 0.25, 0.5, 0.75, 1.0]:
                qx = pll_rect.x + 6 + int(q * p_tw)
                pygame.draw.line(c_surf, (60, 95, 135), (qx, p_track_y - 2), (qx, p_track_y + 2), 1)
            cx = pll_rect.x + 6 + int(min(1.0, max(0.0, b_phase)) * p_tw)
            pygame.draw.circle(c_surf, (0, 240, 255), (cx, p_track_y), 3)

        # Gauge 2: 808 Transient Attack vs Gated Tail
        att_h = min(26, rem_h - pll_h - 4)
        att_rect = pygame.Rect(diag_rect.x + 8, pll_rect.bottom + 3, diag_rect.width - 16, att_h)
        pygame.draw.rect(c_surf, (10, 15, 24, 210), att_rect, border_radius=3)
        pygame.draw.rect(c_surf, (24, 38, 56, 140), att_rect, width=1, border_radius=3)

        is_attack = bool(audio_state.get("is_attack_transient", True))
        s_flux = float(audio_state.get("sub_flux", 0.0) or 0.0)
        s_thresh = float(audio_state.get("sub_thresh", 0.0) or 0.0)
        if is_attack:
            att_col = (0, 255, 160)
            att_txt = "808 STATUS: ATTACK TRANSIENT [TRIGGER PASS]"
        else:
            att_col = (255, 140, 50)
            att_txt = "808 STATUS: SUSTAIN TAIL [GATED / SUPPRESSED]"
        c_surf.blit(self.font_tiny.render(att_txt, True, att_col), (att_rect.x + 6, att_rect.y + 2))

        # 808 meter bar
        att_bar_y = att_rect.y + 16
        if att_bar_y < att_rect.bottom - 2:
            a_bw = att_rect.width - 12
            pygame.draw.rect(c_surf, (18, 26, 38), (att_rect.x + 6, att_bar_y, a_bw, 5), border_radius=2)
            fill_w = int(min(1.0, s_flux / max(0.01, s_thresh * 1.5 if s_thresh > 0 else 0.5)) * a_bw)
            if fill_w > 0:
                pygame.draw.rect(c_surf, (*att_col, 210), (att_rect.x + 6, att_bar_y, fill_w, 5), border_radius=2)
            if s_thresh > 0:
                th_x = att_rect.x + 6 + int(min(1.0, s_thresh / (s_thresh * 1.5)) * a_bw)
                pygame.draw.line(c_surf, (255, 255, 255), (th_x, att_bar_y - 2), (th_x, att_bar_y + 7), 1)

    def _render_console_log(self, screen, audio_state, visualizer, audio_mgr=None, razer_mgr=None):
        """Render high-tech cyber-studio real-time logic and math telemetry console view."""
        if not audio_state:
            audio_state = {}

        if not hasattr(self, "telemetry_history") or len(self.telemetry_history) == 0:
            self._update_telemetry_history(audio_state, visualizer)

        mon = self.active_mon_rect
        c_w = min(1180, mon.width - 24)

        # Scale height based on available screen geometry
        if self.alpha > 20.0 and hasattr(self, "panel_rect"):
            avail_h = max(360, self.panel_rect.y - mon.y - 14)
            c_h = min(620, avail_h)
            c_y = max(mon.y + 10, self.panel_rect.y - c_h - 8)
        else:
            avail_h = max(360, mon.height - 40)
            c_h = min(640, avail_h)
            c_y = mon.y + (mon.height - c_h) // 2

        c_x = mon.x + (mon.width - c_w) // 2

        self.console_rect = pygame.Rect(c_x, c_y, c_w, c_h)
        c_surf = pygame.Surface((c_w, c_h), pygame.SRCALPHA)
        c_surf.fill((8, 12, 20, 246))

        is_c2 = visualizer.is_colors_2_0_active() if (visualizer and hasattr(visualizer, "is_colors_2_0_active")) else True
        accent_col = (0, 240, 255) if is_c2 else (255, 140, 20)

        # Border & Corner brackets
        pygame.draw.rect(c_surf, (*accent_col, 160), pygame.Rect(0, 0, c_w, c_h), width=1, border_radius=6)
        self._draw_tech_corner_brackets(c_surf, pygame.Rect(0, 0, c_w, c_h), (*accent_col, 220), bracket_len=12, width=2)

        # 1. Console Top Header Bar
        hdr_h = 32
        hdr_rect = pygame.Rect(0, 0, c_w, hdr_h)
        pygame.draw.rect(c_surf, (14, 20, 32, 230), hdr_rect, border_top_left_radius=6, border_top_right_radius=6)
        pygame.draw.line(c_surf, (*accent_col, 70), (8, hdr_h), (c_w - 8, hdr_h))

        # Title
        t_surf = self.font_section.render("colors // REAL-TIME LOGIC & MATH TELEMETRY CONSOLE", True, (240, 245, 255))
        c_surf.blit(t_surf, (12, 8))

        # Live dot & Engine badge
        live_dot = pygame.Rect(t_surf.get_width() + 24, 12, 7, 7)
        pygame.draw.circle(c_surf, (0, 255, 120), live_dot.center, 3)
        live_txt = self.font_tiny.render("LIVE", True, (0, 255, 120))
        c_surf.blit(live_txt, (live_dot.right + 4, 8))

        eng_str = "[ colors2.0 PLL ]" if is_c2 else "[ colors1.0 RAW ]"
        eng_s = self.font_tiny.render(eng_str, True, accent_col)
        c_surf.blit(eng_s, (live_dot.right + 34, 8))

        # Hardware & Section telemetry
        bpm = audio_state.get("bpm", 0.0)
        bpm_conf = audio_state.get("bpm_confidence", 0.0)
        sec_name = audio_state.get("section_name", audio_state.get("section", "VERSE"))
        stat_str = f"BPM: {bpm:.1f} ({int(bpm_conf*100)}% conf) | SEC: {sec_name}"
        stat_s = self.font_tiny.render(stat_str, True, (130, 160, 195))
        c_surf.blit(stat_s, (c_w - 240, 8))

        # Close button [X]
        self.console_close_btn = pygame.Rect(self.console_rect.right - 26, self.console_rect.y + 6, 20, 20)
        close_local = pygame.Rect(c_w - 26, 6, 20, 20)
        pygame.draw.rect(c_surf, (35, 18, 24, 200), close_local, border_radius=3)
        pygame.draw.rect(c_surf, (255, 70, 70, 180), close_local, width=1, border_radius=3)
        x_surf = self.font_tiny.render("X", True, (255, 100, 100))
        c_surf.blit(x_surf, (close_local.x + 6, close_local.y + 3))

        # 2. Large Visualizer Deck: Transients, Spectrum & Detonation Scope
        math_h = 88
        vis_deck_h = max(120, min(190, c_h - hdr_h - 4 - math_h - 90))
        vis_rect = pygame.Rect(12, hdr_h + 4, c_w - 24, vis_deck_h)
        self._render_console_visualizer(c_surf, audio_state, visualizer, vis_rect, accent_col)

        # 3. 4 Full Telemetry Brain Cards
        math_y = vis_rect.bottom + 6
        col_gap = 6
        col_w = (c_w - 24 - 3 * col_gap) // 4

        # Card 1: PLL Phase-Locked Loop & Rhythm Grid
        card_1 = pygame.Rect(12, math_y, col_w, math_h)
        pygame.draw.rect(c_surf, (12, 16, 26, 220), card_1, border_radius=4)
        pygame.draw.rect(c_surf, (30, 48, 70, 150), card_1, width=1, border_radius=4)
        c_surf.blit(self.font_tiny.render("PLL PHASE-LOCKED LOOP & GRID", True, (0, 240, 255)), (card_1.x + 6, card_1.y + 4))

        beat_phase = float(audio_state.get("beat_phase", 0.0) or 0.0)
        phase_err = float(audio_state.get("phase_error", 0.0) or 0.0)
        drift_ms = float(audio_state.get("phase_drift_ms", phase_err * (60.0 / max(30.0, bpm)) * 1000.0) or 0.0)
        tempo_stab = float(audio_state.get("tempo_stability", bpm_conf * 100.0) or 0.0)
        grid_mult = float(audio_state.get("grid_mult", 1.0) or 1.0)
        is_downbeat = bool(audio_state.get("is_downbeat", False))
        is_backbeat = bool(audio_state.get("is_backbeat", False))
        on_grid = grid_mult > 1.05
        pll_status = "BOOST" if on_grid else ("GATED" if grid_mult < 0.95 else "NORM")

        c_surf.blit(self.font_tiny.render(f"Phase Angle: phi {beat_phase:.2f} | Drift: {drift_ms:+.1f}ms", True, (190, 220, 245)), (card_1.x + 6, card_1.y + 19))
        c_surf.blit(self.font_tiny.render(f"Stability: {tempo_stab:.1f}% | Grid: {grid_mult:.2f}x ({pll_status})", True, (0, 255, 140) if on_grid else (170, 195, 220)), (card_1.x + 6, card_1.y + 35))
        c_surf.blit(self.font_tiny.render(f"Downbeat: {'ON-GRID [BOOST]' if is_downbeat else 'OFF-GRID'}", True, (0, 255, 140) if is_downbeat else (140, 160, 185)), (card_1.x + 6, card_1.y + 51))
        c_surf.blit(self.font_tiny.render(f"Backbeat: {'LOCKED [SNARE]' if is_backbeat else 'FLOAT'} | Lock: TRUE", True, (255, 215, 60) if is_backbeat else (120, 145, 175)), (card_1.x + 6, card_1.y + 67))

        # Card 2: Musical Pitch & 12-Tone Chroma Harmony
        card_2 = pygame.Rect(card_1.right + col_gap, math_y, col_w, math_h)
        pygame.draw.rect(c_surf, (12, 16, 26, 220), card_2, border_radius=4)
        pygame.draw.rect(c_surf, (30, 48, 70, 150), card_2, width=1, border_radius=4)
        c_surf.blit(self.font_tiny.render("MUSICAL PITCH & 12-TONE CHROMA", True, (255, 110, 220)), (card_2.x + 6, card_2.y + 4))

        pitch_name = str(audio_state.get("pitch_name", "C"))
        pitch_idx = int(audio_state.get("pitch_idx", 0) or 0)
        pitch_conf = float(audio_state.get("pitch_confidence", 0.0) or 0.0)
        sec_idx = int(audio_state.get("secondary_pitch_idx", (pitch_idx + 7) % 12) or 7)
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        sec_name_note = note_names[sec_idx] if sec_idx < len(note_names) else "G"
        harm_prog = str(audio_state.get("harmonic_progression", f"Interval ({pitch_name} -> {sec_name_note})"))

        c_surf.blit(self.font_tiny.render(f"Key Pitch: {pitch_name} (Class {pitch_idx}) | Conf: {int(pitch_conf*100)}%", True, (255, 140, 230)), (card_2.x + 6, card_2.y + 19))
        c_surf.blit(self.font_tiny.render(f"Harmonic Mod: {harm_prog}", True, (200, 180, 240)), (card_2.x + 6, card_2.y + 35))
        c_surf.blit(self.font_tiny.render(f"Secondary Accent: {sec_name_note} (Root 5th/4th)", True, (160, 185, 220)), (card_2.x + 6, card_2.y + 51))
        c_surf.blit(self.font_tiny.render(f"Palette Trigger: {'DYNAMIC ADVANCE' if is_c2 else 'STATIC PALETTE'}", True, (0, 240, 255) if is_c2 else (140, 160, 180)), (card_2.x + 6, card_2.y + 67))

        # Card 3: Macro Section Analyzer
        card_3 = pygame.Rect(card_2.right + col_gap, math_y, col_w, math_h)
        pygame.draw.rect(c_surf, (12, 16, 26, 220), card_3, border_radius=4)
        pygame.draw.rect(c_surf, (30, 48, 70, 150), card_3, width=1, border_radius=4)
        c_surf.blit(self.font_tiny.render("MACRO SECTION & ENERGY SURGE", True, (60, 230, 160)), (card_3.x + 6, card_3.y + 4))

        sec_probs = audio_state.get("section_probs", {"verse": 60, "buildup": 15, "chorus": 20, "breakdown": 5})
        pv = sec_probs.get("verse", 50)
        pb = sec_probs.get("buildup", 20)
        pc = sec_probs.get("chorus", 25)
        pbr = sec_probs.get("breakdown", 5)
        c_mult = float(audio_state.get("chorus_burst_multiplier", audio_state.get("section_energy", 1.0)) or 1.0)
        tot_lvl = float(audio_state.get("total_level", 0.0) or 0.0)
        peak_lvl = float(audio_state.get("peak", audio_state.get("raw_peak", 0.0)) or 0.0)

        c_surf.blit(self.font_tiny.render(f"Section: {sec_name} | Burst Mult: {c_mult:.2f}x", True, (255, 60, 180) if sec_name == "CHORUS" else (0, 240, 255)), (card_3.x + 6, card_3.y + 19))
        c_surf.blit(self.font_tiny.render(f"Probs: V:{pv}% B:{pb}% C:{pc}% BR:{pbr}%", True, (170, 210, 235)), (card_3.x + 6, card_3.y + 35))
        c_surf.blit(self.font_tiny.render(f"RMS Energy: {tot_lvl:.3f} | Peak: {peak_lvl:.3f}", True, (140, 175, 205)), (card_3.x + 6, card_3.y + 51))
        c_surf.blit(self.font_tiny.render(f"Surge Status: {'BURST AMPLIFIED' if c_mult > 1.15 else 'NORMAL ENERGY'}", True, (255, 200, 40) if c_mult > 1.15 else (120, 145, 175)), (card_3.x + 6, card_3.y + 67))

        # Card 4: 808 & Transient Math Engine
        card_4 = pygame.Rect(card_3.right + col_gap, math_y, col_w, math_h)
        pygame.draw.rect(c_surf, (12, 16, 26, 220), card_4, border_radius=4)
        pygame.draw.rect(c_surf, (30, 48, 70, 150), card_4, width=1, border_radius=4)
        c_surf.blit(self.font_tiny.render("808 & TRANSIENT MATH ENGINE", True, (255, 180, 50)), (card_4.x + 6, card_4.y + 4))

        b_flux = float(audio_state.get("bass_flux", 0.0) or 0.0)
        b_thresh = float(audio_state.get("dynamic_thresh", 0.0) or 0.0)
        h_flux = float(audio_state.get("high_flux", 0.0) or 0.0)
        h_thresh = float(audio_state.get("high_thresh", 0.0) or 0.0)
        s_flux = float(audio_state.get("sub_flux", 0.0) or 0.0)
        s_thresh = float(audio_state.get("sub_thresh", 0.0) or 0.0)
        is_attack = bool(audio_state.get("is_attack_transient", True))
        t_ratio = float(audio_state.get("transient_ratio", (s_flux / max(1e-4, s_thresh))) if s_thresh > 0 else 1.0)

        b_trig = b_flux >= b_thresh and b_flux > 0.05
        h_trig = h_flux >= h_thresh and h_flux > 0.05
        s_trig = s_flux >= s_thresh and s_flux > 0.05

        b_ratio = (b_flux / max(1e-4, b_thresh)) if b_thresh > 0 else 0.0
        h_ratio = (h_flux / max(1e-4, h_thresh)) if h_thresh > 0 else 0.0
        s_ratio = (s_flux / max(1e-4, s_thresh)) if s_thresh > 0 else 0.0

        c_surf.blit(self.font_tiny.render(f"Kick: {b_flux:.2f} / th {b_thresh:.2f} ({b_ratio:.1f}x) {'[TRIG]' if b_trig else ''}", True, (0, 255, 140) if b_trig else (150, 175, 200)), (card_4.x + 6, card_4.y + 19))
        c_surf.blit(self.font_tiny.render(f"808 Sub: {s_flux:.2f} / th {s_thresh:.2f} ({s_ratio:.1f}x) {'[TRIG]' if s_trig else ''}", True, (210, 120, 255) if s_trig else (150, 175, 200)), (card_4.x + 6, card_4.y + 35))
        c_surf.blit(self.font_tiny.render(f"808 Env: {'ATTACK IMPACT' if is_attack else 'TAIL GATED'} ({t_ratio:.2f}x)", True, (0, 240, 255) if is_attack else (255, 130, 80)), (card_4.x + 6, card_4.y + 51))
        c_surf.blit(self.font_tiny.render(f"Snare: {h_flux:.2f} / th {h_thresh:.2f} | Hat: {'PASS' if h_trig else 'GATE'}", True, (255, 220, 50) if h_trig else (130, 155, 180)), (card_4.x + 6, card_4.y + 67))

        # 3.5 Peripheral & Mouse Hardware Telemetry Status Strip
        hw_y = math_y + math_h + 5
        hw_h = 24
        hw_rect = pygame.Rect(12, hw_y, c_w - 24, hw_h)
        pygame.draw.rect(c_surf, (10, 16, 26, 230), hw_rect, border_radius=3)
        pygame.draw.rect(c_surf, (30, 48, 70, 160), hw_rect, width=1, border_radius=3)

        m_telem = razer_mgr.get_mouse_telemetry() if (razer_mgr and hasattr(razer_mgr, "get_mouse_telemetry")) else None
        if m_telem and m_telem.get("connected"):
            m_col = m_telem.get("color", (0, 0, 0))
            m_hex = f"#{int(m_col[0]):02X}{int(m_col[1]):02X}{int(m_col[2]):02X}"
            m_state = m_telem.get("state", "IDLE")
            m_pkts = m_telem.get("packets", 0)
            m_name = m_telem.get("name", "Razer Mouse")
            k_name = m_telem.get("kbd_name", "None")
            k_pkts = m_telem.get("kbd_packets", 0)
            is_en = m_telem.get("enabled", True)

            # Draw Mouse Color Swatch Pip
            pygame.draw.rect(c_surf, (min(255, max(0, m_col[0])), min(255, max(0, m_col[1])), min(255, max(0, m_col[2]))), (hw_rect.x + 8, hw_rect.y + 6, 12, 12), border_radius=2)
            pygame.draw.rect(c_surf, (255, 255, 255), (hw_rect.x + 8, hw_rect.y + 6, 12, 12), width=1, border_radius=2)

            en_txt = "ONLINE" if is_en else "OFF"
            m_str1 = f"MOUSE: {m_name} [{en_txt}] | State: {m_state} | Active LED: {m_hex} ({m_col[0]},{m_col[1]},{m_col[2]}) | Dispatched: {m_pkts:,} HID pkts"
            c_surf.blit(self.font_tiny.render(m_str1, True, (210, 230, 250)), (hw_rect.x + 26, hw_rect.y + 4))

            if k_name and k_name != "None":
                k_str = f"KBD: {k_name} ({k_pkts:,} pkts)"
                k_surf = self.font_tiny.render(k_str, True, (130, 175, 215))
                c_surf.blit(k_surf, (hw_rect.right - k_surf.get_width() - 8, hw_rect.y + 4))
        else:
            c_surf.blit(self.font_tiny.render("PERIPHERAL BUS: Standby / Scanning HID Controllers (Press C / Shift+C to toggle hardware)", True, (120, 145, 175)), (hw_rect.x + 8, hw_rect.y + 4))

        # 4. Live Chronological Rationale Decision Stream (Bottom section)
        term_y = hw_y + hw_h + 5
        term_h = max(40, c_h - term_y - 8)
        term_rect = pygame.Rect(12, term_y, c_w - 24, term_h)
        pygame.draw.rect(c_surf, (5, 7, 12, 245), term_rect, border_radius=4)
        pygame.draw.rect(c_surf, (24, 38, 56, 170), term_rect, width=1, border_radius=4)

        t_lbl = self.font_tiny.render("// REAL-TIME TRIGGER RATIONALE & DECISION FEED (CHRONOLOGICAL STREAM)", True, (70, 135, 190))
        c_surf.blit(t_lbl, (term_rect.x + 8, term_rect.y + 4))

        # Track Chroma volatile packet dispatches
        now_t = time.time()
        is_kick_active = bool(audio_state.get("is_kick", False))
        is_snare_active = bool(audio_state.get("is_snare", False))
        if razer_mgr and getattr(razer_mgr, "device_count", 0) > 0 and getattr(razer_mgr, "enabled", False):
            if (is_kick_active or is_snare_active or s_trig) and (now_t - getattr(self, "_last_chroma_log_t", 0.0) >= 0.12):
                self._last_chroma_log_t = now_t
                time_str = time.strftime("%H:%M:%S", time.localtime(now_t)) + f".{int((now_t % 1) * 1000):03d}"
                raw_c = getattr(visualizer, "current_color", (0, 240, 255))
                c_hex = f"#{int(raw_c[0]):02X}{int(raw_c[1]):02X}{int(raw_c[2]):02X}" if isinstance(raw_c, (tuple, list)) and len(raw_c) >= 3 else "#00F0FF"
                m_type = "beat detonation" if is_kick_active else ("snare accent" if is_snare_active else "sub-bass transient")
                self.chroma_logs.append(f"[{time_str}] [CHROMA] Dispatched Razer Viper 64-byte volatile HID packet ({m_type}) -> {c_hex}")

        raw_logs = list(audio_state.get("telemetry_logs", []))
        if hasattr(self, "chroma_logs") and self.chroma_logs:
            raw_logs.extend(list(self.chroma_logs))
            raw_logs.sort()

        line_h = 16
        max_lines = max(1, (term_h - 22) // line_h)
        display_logs = raw_logs[-max_lines:] if raw_logs else []

        if not display_logs:
            c_surf.blit(self.font_tiny.render("[Listening for live audio triggers, PLL phase anchors, and harmonic shifts...]", True, (90, 110, 135)), (term_rect.x + 10, term_rect.y + 20))
        else:
            ly = term_rect.y + 20
            for log_entry in display_logs:
                if "[PLL]" in log_entry or "[PLL SYNC]" in log_entry:
                    txt_col = (0, 240, 255)
                elif "[808 SUB]" in log_entry or "[808]" in log_entry:
                    txt_col = (210, 120, 255)
                elif "[808 TAIL GATED]" in log_entry:
                    txt_col = (255, 140, 60)
                elif "[HARMONY]" in log_entry:
                    txt_col = (255, 110, 220)
                elif "[CHROMA]" in log_entry:
                    txt_col = (0, 255, 140)
                elif "[MOUSE]" in log_entry:
                    txt_col = (0, 255, 180)
                elif "[KICK]" in log_entry:
                    txt_col = (80, 255, 150)
                elif "[SNARE]" in log_entry:
                    txt_col = (255, 230, 60)
                elif "[HIHAT]" in log_entry:
                    txt_col = (130, 220, 255)
                elif "[DROP]" in log_entry:
                    txt_col = (255, 70, 70)
                elif "[SECTION]" in log_entry:
                    txt_col = (60, 220, 240)
                elif "[ENGINE]" in log_entry:
                    txt_col = (255, 205, 50)
                else:
                    txt_col = (175, 190, 210)

                log_s = self.font_tiny.render(log_entry, True, txt_col)
                c_surf.blit(log_s, (term_rect.x + 10, ly))
                ly += line_h

        screen.blit(c_surf, (self.console_rect.x, self.console_rect.y))
