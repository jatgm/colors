"""
Modern cyberpunk HUD (Heads-Up Display) and interactive UI.
Supports dynamic multi-monitor positioning, spectrum visualizer,
controls, and a full-featured Multi-Computer Bluetooth/Network Sync Panel.
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
)
from sync_manager import ROLE_STANDALONE, ROLE_HOST, ROLE_CLIENT


class HUD:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.active_mon_rect = pygame.Rect(0, 0, width, height)

        # Fonts
        pygame.font.init()
        self.font_title = pygame.font.SysFont("Segoe UI, Arial", 20, bold=True)
        self.font_main = pygame.font.SysFont("Segoe UI, Arial", 14, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI, Arial", 12)
        self.font_warning = pygame.font.SysFont("Segoe UI, Arial", 15)

        # Inactivity & visibility state
        self.visible = True
        self.alpha = 255.0
        self.last_interaction_time = time.time()
        self.manually_hidden = False

        # Modals
        self.warning_dismissed = False
        self.show_sync_modal = False

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

    def _build_layout(self):
        mon = self.active_mon_rect
        panel_w = min(780, mon.width - 40)
        panel_h = 320
        panel_x = mon.x + (mon.width - panel_w) // 2
        panel_y = mon.y + mon.height - panel_h - 20

        self.panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        # Button row 1 (Mode, Palette, Style, Device)
        bw = (panel_w - 50) // 4
        by = panel_y + 160
        self.btn_mode = pygame.Rect(panel_x + 10, by, bw, 32)
        self.btn_palette = pygame.Rect(panel_x + 20 + bw, by, bw, 32)
        self.btn_style = pygame.Rect(panel_x + 30 + bw * 2, by, bw, 32)
        self.btn_device = pygame.Rect(panel_x + 40 + bw * 3, by, bw, 32)

        # Button row 2 (Displays, Dual FX, Sync Panel, Safe Mode)
        by2 = by + 38
        self.btn_displays = pygame.Rect(panel_x + 10, by2, bw, 32)
        self.btn_dualfx = pygame.Rect(panel_x + 20 + bw, by2, bw, 32)
        self.btn_sync = pygame.Rect(panel_x + 30 + bw * 2, by2, bw, 32)
        self.btn_safe = pygame.Rect(panel_x + 40 + bw * 3, by2, bw, 32)

        # Slider track rectangles
        slider_w = panel_w - 240
        self.slider_sens_rect = pygame.Rect(panel_x + 130, panel_y + 98, slider_w, 14)
        self.slider_decay_rect = pygame.Rect(panel_x + 130, panel_y + 124, slider_w, 14)

    def handle_mouse_down(self, pos, audio_mgr, visualizer, display_mgr, sync_mgr, on_display_change):
        self.notify_interaction()

        # Warning Dialog
        if not self.warning_dismissed:
            mon = self.active_mon_rect
            dialog_w = min(620, mon.width - 40)
            dialog_h = 290
            dx = mon.x + (mon.width - dialog_w) // 2
            dy = mon.y + (mon.height - dialog_h) // 2

            btn_start = pygame.Rect(dx + 30, dy + 215, 260, 48)
            btn_safe_start = pygame.Rect(dx + 310, dy + 215, 280, 48)

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
            mon = self.active_mon_rect
            modal_w = min(680, mon.width - 40)
            modal_h = 440
            mx = mon.x + (mon.width - modal_w) // 2
            my = mon.y + (mon.height - modal_h) // 2

            # Close button
            btn_close = pygame.Rect(mx + modal_w - 90, my + 15, 75, 28)
            if btn_close.collidepoint(pos):
                self.show_sync_modal = False
                return True

            # Tab buttons: Standalone, Host, Client
            tab_w = (modal_w - 60) // 3
            tab_y = my + 60
            tab_stand = pygame.Rect(mx + 20, tab_y, tab_w, 34)
            tab_host = pygame.Rect(mx + 30 + tab_w, tab_y, tab_w, 34)
            tab_client = pygame.Rect(mx + 40 + tab_w * 2, tab_y, tab_w, 34)

            if tab_stand.collidepoint(pos):
                sync_mgr.set_role(ROLE_STANDALONE)
                return True
            elif tab_host.collidepoint(pos):
                sync_mgr.set_role(ROLE_HOST)
                return True
            elif tab_client.collidepoint(pos):
                sync_mgr.set_role(ROLE_CLIENT)
                return True

            # In Client Tab: Click on discovered host to connect
            if sync_mgr.role == ROLE_CLIENT:
                for r_item, host_data in self.host_item_rects:
                    if r_item.collidepoint(pos):
                        sync_mgr.connect_to_host(host_data)
                        return True

                # Disconnect button if connected
                if sync_mgr.client_sock:
                    btn_disc = pygame.Rect(mx + modal_w - 140, my + 380, 110, 32)
                    if btn_disc.collidepoint(pos):
                        sync_mgr.disconnect_client()
                        return True

                # Rescan button
                btn_rescan = pygame.Rect(mx + 30, my + 380, 140, 32)
                if btn_rescan.collidepoint(pos):
                    sync_mgr.start_client_search()
                    return True

            return True

        if not self.visible or self.alpha < 30:
            return False

        # Sliders
        if self.slider_sens_rect.inflate(10, 10).collidepoint(pos):
            self.dragging_slider = "sens"
            self._update_slider_pos(pos[0], self.slider_sens_rect, MIN_SENSITIVITY, MAX_SENSITIVITY, audio_mgr.set_sensitivity)
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
        elif self.btn_style.collidepoint(pos):
            visualizer.cycle_style()
            return True
        elif self.btn_device.collidepoint(pos):
            audio_mgr.cycle_device()
            return True
        elif self.btn_displays.collidepoint(pos):
            display_mgr.cycle_display_mode()
            on_display_change()
            return True
        elif self.btn_dualfx.collidepoint(pos):
            visualizer.cycle_dual_scheme()
            return True
        elif self.btn_sync.collidepoint(pos):
            self.toggle_sync_modal()
            return True
        elif self.btn_safe.collidepoint(pos):
            visualizer.toggle_safe_mode()
            return True

        return False

    def handle_mouse_up(self):
        self.dragging_slider = None

    def handle_mouse_motion(self, pos, audio_mgr, visualizer, display_mgr):
        mon = display_mgr.get_monitor_for_point(pos[0], pos[1])
        if mon.rect != self.active_mon_rect:
            self.set_active_monitor(mon.rect)

        self.notify_interaction()
        if self.dragging_slider == "sens":
            self._update_slider_pos(pos[0], self.slider_sens_rect, MIN_SENSITIVITY, MAX_SENSITIVITY, audio_mgr.set_sensitivity)
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

    def render(self, screen, audio_mgr, visualizer, display_mgr, sync_mgr, audio_state, is_dual):
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
        pygame.draw.rect(hud_surf, (15, 17, 26, min(235, alpha_int)), panel, border_radius=14)

        border_col = (0, 240, 255, min(180, alpha_int)) if not visualizer.safe_mode else (80, 220, 150, min(180, alpha_int))
        pygame.draw.rect(hud_surf, border_col, panel, width=2, border_radius=14)

        # Title
        title_surf = self.font_title.render("⚡ BEAT STROBE FX [DUAL MONITOR READY]", True, (255, 255, 255))
        hud_surf.blit(title_surf, (panel.x + 20, panel.y + 12))

        # Audio source tag
        if sync_mgr.role == ROLE_CLIENT:
            dev_tag = f"[Client Synced] {sync_mgr.client_connected_host or 'Connecting'}"
            dev_col = (100, 240, 255)
        else:
            dev_tag = audio_mgr.current_device_name
            dev_col = (100, 255, 150) if not audio_mgr.demo_mode else (255, 180, 50)
        dev_surf = self.font_small.render(f"Source: {dev_tag}", True, dev_col)
        hud_surf.blit(dev_surf, (panel.x + panel.width - dev_surf.get_width() - 20, panel.y + 16))

        # 24-Band Spectrum Analyzer
        spec_x = panel.x + 20
        spec_y = panel.y + 44
        spec_w = 260
        spec_h = 42
        spec_bars = audio_state.get("spectrum_bars", [])
        num_bars = len(spec_bars)
        if num_bars > 0:
            bw = (spec_w - (num_bars - 1) * 2) / num_bars
            for i, val in enumerate(spec_bars):
                bh = int(val * spec_h)
                bx = spec_x + i * (bw + 2)
                ratio = i / max(1, num_bars - 1)
                bar_r = int(0 + ratio * 255)
                bar_g = int(240 * (1.0 - ratio * 0.5))
                bar_b = int(255)
                bar_rect = pygame.Rect(int(bx), spec_y + spec_h - bh, max(2, int(bw)), max(2, bh))
                pygame.draw.rect(hud_surf, (bar_r, bar_g, bar_b, alpha_int), bar_rect, border_radius=1)

        # Frequency Level Bars
        levels_x = spec_x + spec_w + 24
        levels_y = spec_y
        meter_w = 120
        meter_h = 10

        b_val = audio_state.get("bass_level", 0.0)
        hud_surf.blit(self.font_small.render("BASS", True, (255, 80, 120)), (levels_x, levels_y - 2))
        pygame.draw.rect(hud_surf, (40, 40, 50, alpha_int), (levels_x + 40, levels_y, meter_w, meter_h), border_radius=3)
        pygame.draw.rect(hud_surf, (255, 50, 100, alpha_int), (levels_x + 40, levels_y, int(meter_w * b_val), meter_h), border_radius=3)

        m_val = audio_state.get("mid_level", 0.0)
        hud_surf.blit(self.font_small.render("MID", True, (80, 240, 120)), (levels_x, levels_y + 15))
        pygame.draw.rect(hud_surf, (40, 40, 50, alpha_int), (levels_x + 40, levels_y + 17, meter_w, meter_h), border_radius=3)
        pygame.draw.rect(hud_surf, (80, 240, 120, alpha_int), (levels_x + 40, levels_y + 17, int(meter_w * m_val), meter_h), border_radius=3)

        h_val = audio_state.get("high_level", 0.0)
        hud_surf.blit(self.font_small.render("HIGH", True, (80, 180, 255)), (levels_x, levels_y + 32))
        pygame.draw.rect(hud_surf, (40, 40, 50, alpha_int), (levels_x + 40, levels_y + 34, meter_w, meter_h), border_radius=3)
        pygame.draw.rect(hud_surf, (80, 180, 255, alpha_int), (levels_x + 40, levels_y + 34, int(meter_w * h_val), meter_h), border_radius=3)

        # Beat Pulse LED & BPM
        beat_x = levels_x + meter_w + 65
        beat_y = levels_y + 20

        is_beating = visualizer.kick_intensity > 0.4
        led_color = (255, 0, 120) if is_beating else (60, 60, 75)
        pygame.draw.circle(hud_surf, led_color, (beat_x, beat_y), 13)
        if is_beating:
            pygame.draw.circle(hud_surf, (255, 255, 255, 200), (beat_x, beat_y), 6)

        hud_surf.blit(self.font_small.render("BEAT", True, (200, 200, 200)), (beat_x - 14, beat_y + 18))

        bpm = audio_state.get("bpm", 0.0)
        bpm_str = f"{int(round(bpm))} BPM" if bpm > 30 else "-- BPM"
        bpm_surf = self.font_title.render(bpm_str, True, (0, 240, 255))
        hud_surf.blit(bpm_surf, (beat_x + 35, beat_y - 12))

        # Sliders: Sensitivity & Decay
        sens = audio_mgr.get_sensitivity()
        decay = visualizer.decay_rate

        sens_label = self.font_small.render(f"Sensitivity: {sens:.1f}x", True, (220, 220, 220))
        hud_surf.blit(sens_label, (panel.x + 20, self.slider_sens_rect.y - 1))
        self._render_slider(hud_surf, self.slider_sens_rect, sens, MIN_SENSITIVITY, MAX_SENSITIVITY, (0, 220, 255), alpha_int)

        decay_label = self.font_small.render(f"Decay Speed: {decay:.0f}", True, (220, 220, 220))
        hud_surf.blit(decay_label, (panel.x + 20, self.slider_decay_rect.y - 1))
        self._render_slider(hud_surf, self.slider_decay_rect, decay, MIN_DECAY_RATE, MAX_DECAY_RATE, (255, 120, 0), alpha_int)

        # Action Buttons Row 1
        self._render_button(hud_surf, self.btn_mode, f"Mode: {visualizer.mode}", (30, 35, 55), (0, 200, 255), alpha_int)
        self._render_button(hud_surf, self.btn_palette, f"Palette: {visualizer.palette_name}", (30, 35, 55), (255, 0, 180), alpha_int)
        self._render_button(hud_surf, self.btn_style, f"Style: {visualizer.current_style}", (30, 35, 55), (180, 100, 255), alpha_int)
        self._render_button(hud_surf, self.btn_device, "Audio: [Switch]", (30, 35, 55), (100, 255, 180), alpha_int)

        # Action Buttons Row 2
        disp_txt = display_mgr.current_mode
        if len(disp_txt) > 18:
            disp_txt = disp_txt[:16] + ".."
        self._render_button(hud_surf, self.btn_displays, f"Display: {disp_txt}", (35, 45, 70), (120, 200, 255), alpha_int)

        dual_txt = visualizer.dual_scheme if is_dual else "N/A (Single)"
        self._render_button(hud_surf, self.btn_dualfx, f"Dual FX: {dual_txt}", (45, 35, 65), (220, 120, 255), alpha_int)

        # Sync button with current role status
        if sync_mgr.role == ROLE_HOST:
            sync_label = f"Sync: [Host ({sync_mgr.client_count})]"
            sync_bg = (40, 25, 60)
            sync_border = (220, 100, 255)
        elif sync_mgr.role == ROLE_CLIENT:
            c_tag = "Connected" if sync_mgr.client_sock else "Searching"
            sync_label = f"Sync: [Client {c_tag}]"
            sync_bg = (20, 45, 60)
            sync_border = (0, 220, 255)
        else:
            sync_label = "Sync: [BT / Network]"
            sync_bg = (30, 35, 55)
            sync_border = (120, 180, 240)
        self._render_button(hud_surf, self.btn_sync, sync_label, sync_bg, sync_border, alpha_int)

        safe_tag = "[Safe Mode: ON]" if visualizer.safe_mode else "[Safe Mode: OFF]"
        safe_bg = (20, 60, 40) if visualizer.safe_mode else (30, 35, 55)
        self._render_button(hud_surf, self.btn_safe, safe_tag, safe_bg, (100, 255, 150), alpha_int)

        # Hotkey Footer
        hints = "Hotkeys: [ESC] Exit  [F/F11] Displays  [B] Dual FX  [N] Bluetooth Sync  [M] Mode  [P] Palette  [S] Safe  [H] Hide"
        hint_surf = self.font_small.render(hints, True, (140, 145, 165))
        hud_surf.blit(hint_surf, (panel.x + (panel.width - hint_surf.get_width()) // 2, panel.y + panel.height - 24))

        hud_surf.set_alpha(alpha_int)
        screen.blit(hud_surf, (0, 0))

    def _render_sync_modal(self, screen, sync_mgr):
        """Render multi-computer Bluetooth & Network Sync modal dialog."""
        mon = self.active_mon_rect
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))

        modal_w = min(680, mon.width - 40)
        modal_h = 440
        mx = mon.x + (mon.width - modal_w) // 2
        my = mon.y + (mon.height - modal_h) // 2
        modal_rect = pygame.Rect(mx, my, modal_w, modal_h)

        pygame.draw.rect(overlay, (20, 24, 38), modal_rect, border_radius=14)
        pygame.draw.rect(overlay, (0, 220, 255), modal_rect, width=2, border_radius=14)

        # Header
        head_txt = self.font_title.render("📡 MULTI-COMPUTER SYNC (BLUETOOTH & NETWORK)", True, (255, 255, 255))
        overlay.blit(head_txt, (mx + 25, my + 18))

        # Close button
        btn_close = pygame.Rect(mx + modal_w - 90, my + 15, 75, 28)
        self._render_button(overlay, btn_close, "Close [N]", (40, 45, 60), (160, 160, 160), 255)

        # Tabs: Standalone, Host, Client
        tab_w = (modal_w - 60) // 3
        tab_y = my + 60

        tab_stand = pygame.Rect(mx + 20, tab_y, tab_w, 34)
        bg_s = (0, 180, 140) if sync_mgr.role == ROLE_STANDALONE else (30, 35, 55)
        self._render_button(overlay, tab_stand, "💻 Standalone (Solo)", bg_s, (0, 220, 180), 255)

        tab_host = pygame.Rect(mx + 30 + tab_w, tab_y, tab_w, 34)
        bg_h = (180, 0, 120) if sync_mgr.role == ROLE_HOST else (30, 35, 55)
        self._render_button(overlay, tab_host, "📡 Host (Broadcast)", bg_h, (255, 0, 180), 255)

        tab_client = pygame.Rect(mx + 40 + tab_w * 2, tab_y, tab_w, 34)
        bg_c = (0, 140, 220) if sync_mgr.role == ROLE_CLIENT else (30, 35, 55)
        self._render_button(overlay, tab_client, "📲 Client (Sync to Host)", bg_c, (0, 200, 255), 255)

        # Content Area
        content_box = pygame.Rect(mx + 20, my + 105, modal_w - 40, 315)
        pygame.draw.rect(overlay, (14, 17, 28), content_box, border_radius=10)
        pygame.draw.rect(overlay, (45, 50, 70), content_box, width=1, border_radius=10)

        cy = content_box.y + 20

        if sync_mgr.role == ROLE_STANDALONE:
            overlay.blit(self.font_main.render("Current Role: Standalone Computer", True, (255, 255, 255)), (content_box.x + 25, cy))
            lines = [
                "This computer processes audio and controls its own screen strobes locally.",
                "",
                "To synchronize multiple computers together:",
                " • Select 'Host' on the computer playing music (or connected to audio/DJ).",
                " • Select 'Client' on all other computers / laptops.",
                " • Clients will search and discover the Host via Bluetooth & Local Network.",
            ]
            for i, line in enumerate(lines):
                overlay.blit(self.font_small.render(line, True, (180, 185, 205)), (content_box.x + 25, cy + 35 + i * 22))

        elif sync_mgr.role == ROLE_HOST:
            overlay.blit(self.font_main.render("🟢 HOST MODE ACTIVE (Broadcasting Beats)", True, (100, 255, 150)), (content_box.x + 25, cy))

            info_lines = [
                f"Computer Hostname:  {sync_mgr.hostname}",
                f"Bluetooth Address:  {sync_mgr.local_bt_mac} (RFCOMM Channel {BT_RFCOMM_CHANNEL})",
                f"Local Network IP:   {sync_mgr.local_ip}:{TCP_PORT}",
                "",
                f"⚡ Connected Synced Clients: {sync_mgr.client_count} computer(s)",
                "",
                "Instructions for other computers:",
                " 1. Download/open Beat Strobe on the other computer(s).",
                " 2. Switch to 'Client' mode and search for this host.",
                " 3. Click Connect to strobe all screens together in perfect unison!",
            ]
            for i, line in enumerate(info_lines):
                col = (255, 220, 100) if "Connected Synced" in line else (200, 205, 220)
                overlay.blit(self.font_small.render(line, True, col), (content_box.x + 25, cy + 30 + i * 20))

        elif sync_mgr.role == ROLE_CLIENT:
            status_col = (100, 255, 150) if sync_mgr.client_sock else (255, 200, 50)
            overlay.blit(self.font_main.render(f"Client Status: {sync_mgr.client_status}", True, status_col), (content_box.x + 25, cy))

            self.host_item_rects = []
            if sync_mgr.client_sock:
                # Connected View
                conn_info = [
                    f"✓ Synchronized to Host: {sync_mgr.client_connected_host}",
                    f"Latency: {sync_mgr.client_latency_ms:.1f} ms (Real-time sub-frame sync)",
                    "",
                    "Local audio capture is paused while receiving live beat signals from host.",
                ]
                for i, line in enumerate(conn_info):
                    overlay.blit(self.font_small.render(line, True, (220, 225, 240)), (content_box.x + 25, cy + 35 + i * 24))

                btn_disc = pygame.Rect(content_box.x + content_box.width - 150, content_box.y + content_box.height - 48, 120, 32)
                self._render_button(overlay, btn_disc, "Disconnect", (60, 25, 30), (255, 80, 80), 255)

            else:
                # Discovered Hosts List
                overlay.blit(self.font_small.render("Discovered Hosts & Nearby Bluetooth Devices:", True, (160, 165, 185)), (content_box.x + 25, cy + 28))

                discovered = sync_mgr.get_all_discovered_hosts()
                item_y = cy + 52

                if not discovered:
                    overlay.blit(self.font_small.render("Searching for nearby Bluetooth hosts & network beacons...", True, (200, 180, 100)), (content_box.x + 35, item_y + 15))
                else:
                    for idx, host_entry in enumerate(discovered[:5]):
                        item_rect = pygame.Rect(content_box.x + 20, item_y, content_box.width - 40, 38)
                        pygame.draw.rect(overlay, (24, 28, 44), item_rect, border_radius=6)
                        pygame.draw.rect(overlay, (60, 70, 95), item_rect, width=1, border_radius=6)

                        name_surf = self.font_small.render(f"{host_entry['name']}", True, (255, 255, 255))
                        addr_surf = self.font_small.render(f"({host_entry['type']}: {host_entry['address']})", True, (140, 150, 180))
                        overlay.blit(name_surf, (item_rect.x + 12, item_rect.y + 10))
                        overlay.blit(addr_surf, (item_rect.x + 24 + name_surf.get_width(), item_rect.y + 10))

                        btn_conn = pygame.Rect(item_rect.x + item_rect.width - 100, item_rect.y + 5, 88, 28)
                        self._render_button(overlay, btn_conn, "Connect", (0, 140, 180), (0, 220, 255), 255)
                        self.host_item_rects.append((btn_conn, host_entry))

                        item_y += 44

                btn_rescan = pygame.Rect(content_box.x + 25, content_box.y + content_box.height - 48, 140, 32)
                self._render_button(overlay, btn_rescan, "🔄 Scan Again", (35, 45, 65), (100, 200, 255), 255)

        screen.blit(overlay, (0, 0))

    def _render_slider(self, surf, rect, value, min_val, max_val, color, alpha):
        pygame.draw.rect(surf, (40, 45, 60, alpha), rect, border_radius=7)
        norm = max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
        fill_w = int(rect.width * norm)
        if fill_w > 0:
            pygame.draw.rect(surf, (*color, alpha), pygame.Rect(rect.x, rect.y, fill_w, rect.height), border_radius=7)
        tx = int(rect.x + fill_w)
        ty = rect.y + rect.height // 2
        pygame.draw.circle(surf, (255, 255, 255, alpha), (tx, ty), 8)
        pygame.draw.circle(surf, (*color, alpha), (tx, ty), 5)

    def _render_button(self, surf, rect, text, bg_col, border_col, alpha):
        pygame.draw.rect(surf, (*bg_col, alpha), rect, border_radius=6)
        pygame.draw.rect(surf, (*border_col, alpha), rect, width=1, border_radius=6)
        txt_surf = self.font_small.render(text, True, (240, 240, 240))
        tx = rect.x + (rect.width - txt_surf.get_width()) // 2
        ty = rect.y + (rect.height - txt_surf.get_height()) // 2
        surf.blit(txt_surf, (tx, ty))

    def _render_warning_dialog(self, screen):
        mon = self.active_mon_rect
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))

        dialog_w = min(640, mon.width - 40)
        dialog_h = 300
        dx = mon.x + (mon.width - dialog_w) // 2
        dy = mon.y + (mon.height - dialog_h) // 2
        dialog_rect = pygame.Rect(dx, dy, dialog_w, dialog_h)

        pygame.draw.rect(overlay, (20, 24, 36), dialog_rect, border_radius=14)
        pygame.draw.rect(overlay, (255, 60, 60), dialog_rect, width=2, border_radius=14)

        warn_title = self.font_title.render("⚠ PHOTOSENSITIVITY & EPILEPSY WARNING", True, (255, 75, 75))
        overlay.blit(warn_title, (dx + 25, dy + 22))

        lines = [
            "This application produces high-intensity strobing colors and rapid light flashes",
            "synchronized to your audio in real-time across your monitors.",
            "",
            "If you or anyone in your household has an epileptic condition or experiences",
            "light-triggered seizures, migraines, or severe eye strain, please use",
            "Safe Mode (gentle pulsing glow) or exit immediately.",
        ]
        curr_y = dy + 62
        for line in lines:
            line_surf = self.font_warning.render(line, True, (220, 220, 225))
            overlay.blit(line_surf, (dx + 25, curr_y))
            curr_y += 22

        btn_start = pygame.Rect(dx + 30, dy + 225, 270, 48)
        pygame.draw.rect(overlay, (255, 0, 100), btn_start, border_radius=8)
        s_txt = self.font_main.render("START FULL STROBE [ENTER]", True, (255, 255, 255))
        overlay.blit(s_txt, (btn_start.x + (btn_start.width - s_txt.get_width()) // 2, btn_start.y + 14))

        btn_safe = pygame.Rect(dx + 320, dy + 225, 290, 48)
        pygame.draw.rect(overlay, (0, 180, 120), btn_safe, border_radius=8)
        safe_txt = self.font_main.render("START IN SAFE GLOW MODE [S]", True, (255, 255, 255))
        overlay.blit(safe_txt, (btn_safe.x + (btn_safe.width - safe_txt.get_width()) // 2, btn_safe.y + 14))

        screen.blit(overlay, (0, 0))
