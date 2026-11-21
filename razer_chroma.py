"""
Razer Chroma Peripheral Lighting Synchronization.
Supports Razer Keyboards, Mice, Mousepads, and Headsets on Windows
via direct USB HID Feature Reports (zero-dependency, no Synapse required)
and Razer Chroma REST API.
"""

import sys
import time
import math
import random
import queue
import threading
import ctypes
import numpy as np
try:
    from ctypes import wintypes
except ImportError:
    wintypes = None


RAZER_VID = 0x1532
CONTROL_FEATURE_LEN = 91


def _create_razer_report(command_class, command_id, data_size, arguments, txn=0x3F):
    """Generate 90-byte Razer control report with XOR checksum."""
    r = bytearray(90)
    r[1] = txn
    r[5] = data_size
    r[6] = command_class
    r[7] = command_id
    r[8:8 + len(arguments)] = arguments
    crc = 0
    for i in range(2, 88):
        crc ^= r[i]
    r[88] = crc
    return bytes(r)


class RazerDevice:
    def __init__(self, name, device_type, path, pid, handle):
        self.name = name
        self.device_type = device_type
        self.path = path
        self.pid = pid
        self.handle = handle
        self.has_scroll_wheel = False

        # Assign correct primary hardware LED ID based on Razer specification:
        # Keyboards: 0x05 (BACKLIGHT_LED - illuminates full key matrix)
        # Mice: 0x04 (LOGO_LED - illuminates palm/chassis logo)
        # Mousepads: 0x05 (BACKLIGHT_LED / border lighting)
        # Headsets: 0x04 (LOGO_LED / earcups)
        if device_type == "keyboard":
            self.led_id = 0x05
        elif device_type == "mouse":
            self.led_id = 0x04
        elif device_type == "mousepad":
            self.led_id = 0x05
        elif device_type == "headset":
            self.led_id = 0x04
        else:
            self.led_id = 0x05

    def __repr__(self):
        return f"<RazerDevice {self.name} ({self.device_type}) PID=0x{self.pid:04X} LED=0x{self.led_id:02X}>"


class KeyboardMatrixEngine:
    """
    High-performance per-key and per-row RGB matrix animation engine for Razer Chroma keyboards.
    Computes a 6-row by 22-column RGB grid with sub-millisecond overhead.
    Features:
      - Row 0: 22-Key Real-Time Live Frequency Spectrum VU Equalizer (Esc, F1-F12, PrtSc, Pause, Media)
      - Radial Kick / 808 Shockwaves radiating outward across keycaps from Spacebar (Row 5, Col 8)
      - Lateral Snare / Clap Accent Wave across typing rows (Rows 2, 3, 4)
      - Hi-Hat Micro-Sparkles across number and QWERTY rows (Rows 1, 2)
      - Spatial Stereo Spread: Columns 0-10 track Left Monitor, Columns 11-21 track Right Monitor
      - Instant Zero-Lag Hardware Blackout cut synchronized with display strobe cuts
      - Static Solid Color override illumination matching HUD solid color presets
    """

    ROWS = 6
    COLS = 22

    def __init__(self):
        self.matrix = np.zeros((self.ROWS, self.COLS, 3), dtype=np.uint8)
        self.last_matrix = np.zeros((self.ROWS, self.COLS, 3), dtype=np.uint8)

        # Precompute radial Euclidean distances from epicenter (Spacebar: row 5, col 8)
        # Vertical distance is scaled by 2.2 to account for keycap aspect ratio
        self.D_radial = np.zeros((self.ROWS, self.COLS), dtype=np.float32)
        for r in range(self.ROWS):
            for c in range(self.COLS):
                self.D_radial[r, c] = math.sqrt((c - 8.0) ** 2 + ((5 - r) * 2.2) ** 2)

        # Precompute lateral distances from keyboard center (col 10.5)
        self.D_lateral = np.zeros((self.ROWS, self.COLS), dtype=np.float32)
        for r in range(self.ROWS):
            for c in range(self.COLS):
                self.D_lateral[r, c] = abs(c - 10.5)

        self.shockwaves = []
        self.snare_radius = 0.0
        self.snare_intensity = 0.0
        self.snare_color = (255, 255, 255)
        self.sparkles = []
        self.last_kick_time = 0.0
        self.last_snare_time = 0.0
        self.last_hihat_time = 0.0

    def generate_matrix(self, dt, col_left, col_right, strobe_cut, audio_state=None, is_dual=False, vis_state=None):
        """
        Generate 6x22 RGB matrix based on audio state, monitor colors, and visualizer events.
        Returns (matrix: np.ndarray (6, 22, 3) uint8, is_blackout: bool).
        """
        # 1. Solid Color Mode Override
        if vis_state and vis_state.get("solid_color_active"):
            solid_rgb = vis_state.get("solid_color", (255, 0, 0))
            self.matrix[:, :] = solid_rgb
            return self.matrix, False

        now = time.time()

        # 2. Process beat events from audio_state
        if audio_state:
            is_kick = audio_state.get("is_kick", False) or audio_state.get("is_drop", False)
            kick_int = vis_state.get("kick_intensity", 0.0) if vis_state else 0.0
            if is_kick or kick_int > 0.65:
                if (now - self.last_kick_time) >= 0.075:
                    self.last_kick_time = now
                    # Derive high-energy shockwave color
                    base_k = col_left if max(col_left) > 40 else (0, 240, 255)
                    max_k = max(base_k) or 1
                    scale_k = 255.0 / max_k
                    k_col = (
                        min(255, int(base_k[0] * scale_k)),
                        min(255, int(base_k[1] * scale_k)),
                        min(255, int(base_k[2] * scale_k)),
                    )
                    if len(self.shockwaves) < 3:
                        self.shockwaves.append({
                            "radius": 0.0,
                            "speed": 48.0,
                            "max_radius": 24.0,
                            "color": k_col,
                            "intensity": 1.0,
                            "decay": 3.4,
                        })

            is_snare = audio_state.get("is_snare", False)
            snare_int = vis_state.get("snare_intensity", 0.0) if vis_state else 0.0
            if is_snare or snare_int > 0.60:
                if (now - self.last_snare_time) >= 0.09:
                    self.last_snare_time = now
                    sec_col = col_right if max(col_right) > 40 else (255, 80, 200)
                    self.snare_radius = 0.0
                    self.snare_intensity = 1.0
                    self.snare_color = (
                        min(255, sec_col[0] + 50),
                        min(255, sec_col[1] + 50),
                        min(255, sec_col[2] + 50),
                    )

            is_hihat = audio_state.get("is_hihat", False)
            if is_hihat and (now - self.last_hihat_time) >= 0.05:
                self.last_hihat_time = now
                for _ in range(3):
                    r = random.randint(1, 3)
                    c = random.randint(1, 20)
                    self.sparkles.append([r, c, (255, 255, 255), 0.06])

        # 3. Base Monitor Matching (Rows 1..5)
        self.matrix.fill(0)
        has_screen_color = (max(col_left) > 0 or max(col_right) > 0)

        if has_screen_color:
            if is_dual:
                self.matrix[1:, :10] = col_left
                self.matrix[1:, 12:] = col_right
                blend_c = [int((col_left[i] + col_right[i]) * 0.5) for i in range(3)]
                self.matrix[1:, 10:12] = blend_c
            else:
                self.matrix[1:, :] = col_left

        # 4. Row 0: 22-Key Live Frequency Spectrum VU Meter
        bars = audio_state.get("spectrum_bars", None) if audio_state else None
        if bars is not None and len(bars) > 0:
            bands_22 = np.interp(np.linspace(0, len(bars) - 1, self.COLS), np.arange(len(bars)), bars)
            for c in range(self.COLS):
                v = float(bands_22[c])
                if v > 0.02:
                    if c < 5:
                        base_c = col_left if max(col_left) > 40 else (0, 240, 255)
                    elif c < 12:
                        base_c = col_right if max(col_right) > 40 else (255, 60, 200)
                    else:
                        base_c = (190, 240, 255)
                    v_scale = min(1.0, v * 1.5)
                    self.matrix[0, c] = [
                        min(255, int(base_c[0] * v_scale)),
                        min(255, int(base_c[1] * v_scale)),
                        min(255, int(base_c[2] * v_scale)),
                    ]
        elif has_screen_color:
            self.matrix[0, :] = col_left

        # 5. Radial Kick & 808 Shockwave Waves (Rows 1..5)
        active_sw = []
        for sw in self.shockwaves:
            sw["radius"] += sw["speed"] * dt
            sw["intensity"] -= sw["decay"] * dt
            if sw["radius"] < sw["max_radius"] and sw["intensity"] > 0.0:
                active_sw.append(sw)
                diff = np.abs(self.D_radial[1:] - sw["radius"])
                mask = (diff < 2.4)
                if np.any(mask):
                    crest_int = (1.0 - diff[mask] / 2.4) * sw["intensity"]
                    cur = self.matrix[1:][mask].astype(np.float32)
                    for i in range(3):
                        cur[:, i] = np.clip(cur[:, i] + sw["color"][i] * crest_int, 0, 255)
                    self.matrix[1:][mask] = cur.astype(np.uint8)

                # Trailing afterglow
                trail_mask = (self.D_radial[1:] < sw["radius"]) & (~mask)
                if np.any(trail_mask):
                    trail_int = (self.D_radial[1:][trail_mask] / max(1.0, sw["radius"])) * sw["intensity"] * 0.35
                    cur = self.matrix[1:][trail_mask].astype(np.float32)
                    for i in range(3):
                        cur[:, i] = np.clip(cur[:, i] + sw["color"][i] * trail_int, 0, 255)
                    self.matrix[1:][trail_mask] = cur.astype(np.uint8)
        self.shockwaves = active_sw

        # 6. Snare Lateral Horizontal Wave (Rows 2, 3, 4)
        if self.snare_intensity > 0.0:
            self.snare_radius += 68.0 * dt
            self.snare_intensity -= 7.5 * dt
            if self.snare_intensity > 0.0 and self.snare_radius < 14.0:
                diff_lat = np.abs(self.D_lateral[2:5] - self.snare_radius)
                s_mask = (diff_lat < 2.2)
                if np.any(s_mask):
                    s_int = (1.0 - diff_lat[s_mask] / 2.2) * self.snare_intensity
                    cur = self.matrix[2:5][s_mask].astype(np.float32)
                    for i in range(3):
                        cur[:, i] = np.clip(cur[:, i] + self.snare_color[i] * s_int, 0, 255)
                    self.matrix[2:5][s_mask] = cur.astype(np.uint8)

        # 7. Hi-Hat Micro-Sparkles
        active_sp = []
        for sp in self.sparkles:
            r, c, col, life = sp
            life -= dt
            if life > 0.0 and 0 <= r < self.ROWS and 0 <= c < self.COLS:
                active_sp.append([r, c, col, life])
                self.matrix[r, c] = [255, 255, 255]
        self.sparkles = active_sp

        # 8. Check if entirely pitch black
        is_blackout = bool(np.all(self.matrix == 0))
        return self.matrix, is_blackout


class RazerChromaManager:
    """Synchronizes screen strobe colors with connected Razer peripherals in real time."""

    def __init__(self):
        self.enabled = True
        self.devices = []
        self.device_names = []
        self.device_count = 0
        self.active_mode = "NONE"
        self.matrix_engine = KeyboardMatrixEngine()

        self.color_queue = queue.Queue(maxsize=2)
        self.running = True
        self.lock = threading.Lock()

        # Win32 API handles
        self.setupapi = None
        self.hid = None
        self.kernel32 = None

        if sys.platform == "win32":
            self._init_win32_api()
            self.refresh_devices()

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _init_win32_api(self):
        try:
            self.setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
            self.hid = ctypes.WinDLL("hid", use_last_error=True)
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            self.kernel32.CreateFileW.restype = wintypes.HANDLE
            self.kernel32.CreateFileW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
            ]
            self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

            self.hid.HidD_SetFeature.restype = wintypes.BOOL
            self.hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
            self.hid.HidD_GetFeature.restype = wintypes.BOOL
            self.hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
            self.hid.HidD_GetAttributes.restype = wintypes.BOOL
            self.hid.HidD_GetProductString.restype = wintypes.BOOL
            self.hid.HidD_GetProductString.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
        except Exception:
            pass

    def refresh_devices(self):
        """Discover all connected Razer peripherals with 91-byte control endpoints."""
        if not self.setupapi or not self.hid or not self.kernel32:
            return

        with self.lock:
            # Close existing handles
            for d in self.devices:
                try:
                    self.kernel32.CloseHandle(d.handle)
                except Exception:
                    pass
            self.devices = []
            self.device_names = []

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                        ("Flags", wintypes.DWORD), ("Reserved", ctypes.c_void_p)]

        class HIDD_ATTRIBUTES(ctypes.Structure):
            _fields_ = [("Size", wintypes.ULONG), ("VendorID", wintypes.USHORT),
                        ("ProductID", wintypes.USHORT), ("VersionNumber", wintypes.USHORT)]

        class HIDP_CAPS(ctypes.Structure):
            _fields_ = ([("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT),
                         ("InputReportByteLength", wintypes.USHORT),
                         ("OutputReportByteLength", wintypes.USHORT),
                         ("FeatureReportByteLength", wintypes.USHORT),
                         ("Reserved", wintypes.USHORT * 17)] +
                        [(f, wintypes.USHORT) for f in (
                            "NumberLinkCollectionNodes", "NumberInputButtonCaps",
                            "NumberInputValueCaps", "NumberInputDataIndices",
                            "NumberOutputButtonCaps", "NumberOutputValueCaps",
                            "NumberOutputDataIndices", "NumberFeatureButtonCaps",
                            "NumberFeatureValueCaps", "NumberFeatureDataIndices")])

        self.setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
        self.setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
        self.setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
        self.setupapi.SetupDiEnumDeviceInterfaces.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
        self.setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
        self.setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [wintypes.HANDLE, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]

        self.hid.HidD_GetPreparsedData.restype = wintypes.BOOL
        self.hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
        self.hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
        self.hid.HidP_GetCaps.restype = wintypes.LONG
        self.hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]

        guid = GUID()
        self.hid.HidD_GetHidGuid(ctypes.byref(guid))
        hdev = self.setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)

        cb = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        idx = 0
        iface = SP_DEVICE_INTERFACE_DATA()
        iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
        found = []

        while self.setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(guid), idx, ctypes.byref(iface)):
            idx += 1
            req = wintypes.DWORD(0)
            self.setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(iface), None, 0, ctypes.byref(req), None)
            if not req.value:
                continue
            buf = ctypes.create_string_buffer(req.value)
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = cb
            if not self.setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(iface), buf, req.value, None, None):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)

            # Open with 0 access and share R/W to bypass exclusive keyboard/mouse lock
            h = self.kernel32.CreateFileW(path, 0, 3, None, 3, 0, None)
            if h in (None, 0, -1, 0xFFFFFFFF, ctypes.c_void_p(-1).value):
                continue

            try:
                attrs = HIDD_ATTRIBUTES()
                attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
                if not self.hid.HidD_GetAttributes(h, ctypes.byref(attrs)) or attrs.VendorID != RAZER_VID:
                    self.kernel32.CloseHandle(h)
                    continue

                feat_len = 0
                pp = ctypes.c_void_p()
                if self.hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
                    caps = HIDP_CAPS()
                    if self.hid.HidP_GetCaps(pp, ctypes.byref(caps)) == 0x00110000:
                        feat_len = caps.FeatureReportByteLength
                    self.hid.HidD_FreePreparsedData(pp)

                # Razer Chroma Control collection is exactly 91 bytes
                if feat_len == CONTROL_FEATURE_LEN:
                    # Query USB Product String
                    prod_buf = ctypes.create_unicode_buffer(128)
                    self.hid.HidD_GetProductString(h, prod_buf, 256)
                    p_name = prod_buf.value.strip() or f"Razer Device (0x{attrs.ProductID:04X})"

                    # Classify device type
                    lower_name = p_name.lower()
                    if any(k in lower_name for k in ("mouse", "viper", "deathadder", "basilisk", "naga", "cobra", "mamba")):
                        dev_type = "mouse"
                    elif any(k in lower_name for k in ("keyboard", "ornata", "blackwidow", "huntsman", "cynosa", "deathstalker")):
                        dev_type = "keyboard"
                    elif any(k in lower_name for k in ("firefly", "goliathus", "mat", "pad")):
                        dev_type = "mousepad"
                    elif any(k in lower_name for k in ("headset", "kraken", "blackshark", "nommo")):
                        dev_type = "headset"
                    else:
                        dev_type = "peripheral"

                    dev_obj = RazerDevice(p_name, dev_type, path, attrs.ProductID, h)
                    if attrs.ProductID == 0x0078:
                        dev_obj.has_scroll_wheel = False
                    found.append(dev_obj)
                else:
                    self.kernel32.CloseHandle(h)

            except Exception:
                try:
                    self.kernel32.CloseHandle(h)
                except Exception:
                    pass

        self.setupapi.SetupDiDestroyDeviceInfoList(hdev)

        with self.lock:
            self.devices = found
            self.device_names = [d.name for d in found]
            self.device_count = len(found)
            if self.devices:
                self.active_mode = "DIRECT_HID"
            else:
                self.active_mode = "NONE"

        if self.devices:
            self._configure_devices()

    def _configure_devices(self):
        """Set all Razer devices to Normal Mode (0x00), maximum hardware brightness, and initial blackout."""
        if not self.hid:
            return
        # 1. Normal Mode (0x00, 0x00): Ensures physical volume wheel and media keys (Play/Pause/Skip)
        # function as native Windows system volume & media keys instead of scrolling
        rep_mode = _create_razer_report(0x00, 0x04, 0x02, [0x00, 0x00], txn=0x3F)
        buf_mode = bytearray(91)
        buf_mode[1:] = rep_mode
        cbuf_mode = (ctypes.c_char * 91).from_buffer(buf_mode)

        # 2. Maximum Brightness:
        # Keyboard backlight brightness (0x0F, 0x04, 0x03) with txn 0x1F (BACKLIGHT_LED = 0x05)
        rep_kbd_bright = _create_razer_report(0x0F, 0x04, 0x03, [0x01, 0x05, 0xFF], txn=0x1F)
        buf_kbd_bright = bytearray(91); buf_kbd_bright[1:] = rep_kbd_bright
        cbuf_kbd_bright = (ctypes.c_char * 91).from_buffer(buf_kbd_bright)

        # Mouse logo brightness (0x0F, 0x04, 0x03) with txn 0x3F (LOGO_LED = 0x04)
        rep_mouse_bright = _create_razer_report(0x0F, 0x04, 0x03, [0x01, 0x04, 0xFF], txn=0x3F)
        buf_mouse_bright = bytearray(91); buf_mouse_bright[1:] = rep_mouse_bright
        cbuf_mouse_bright = (ctypes.c_char * 91).from_buffer(buf_mouse_bright)

        # Mouse scroll wheel brightness (0x0F, 0x04, 0x03) with txn 0x3F (SCROLL_WHEEL_LED = 0x01)
        rep_sw_bright = _create_razer_report(0x0F, 0x04, 0x03, [0x01, 0x01, 0xFF], txn=0x3F)
        buf_sw_bright = bytearray(91); buf_sw_bright[1:] = rep_sw_bright
        cbuf_sw_bright = (ctypes.c_char * 91).from_buffer(buf_sw_bright)

        # Legacy fallback brightness
        rep_leg_bright = _create_razer_report(0x03, 0x03, 0x03, [0x00, 0x00, 0xFF], txn=0x3F)
        buf_leg_bright = bytearray(91); buf_leg_bright[1:] = rep_leg_bright
        cbuf_leg_bright = (ctypes.c_char * 91).from_buffer(buf_leg_bright)

        # 3. Initial Hardware Blackout using EFFECT_NONE (0x0F, 0x02, 0x06) and STATIC (0,0,0) (0x0F, 0x02, 0x09)
        # Prevents mouse from falling back to default onboard breathing or spectrum cycling
        rep_black_kbd = _create_razer_report(0x0F, 0x02, 0x06, [0x00, 0x05, 0x00, 0x00, 0x00, 0x00], txn=0x1F)
        buf_black_kbd = bytearray(91); buf_black_kbd[1:] = rep_black_kbd
        cbuf_black_kbd = (ctypes.c_char * 91).from_buffer(buf_black_kbd)

        rep_black_mouse = _create_razer_report(0x0F, 0x02, 0x06, [0x00, 0x04, 0x00, 0x00, 0x00, 0x00], txn=0x3F)
        buf_black_mouse = bytearray(91); buf_black_mouse[1:] = rep_black_mouse
        cbuf_black_mouse = (ctypes.c_char * 91).from_buffer(buf_black_mouse)

        rep_mouse_static_black = _create_razer_report(0x0F, 0x02, 0x09, [0x00, 0x04, 0x01, 0x00, 0x00, 0x01, 0, 0, 0], txn=0x3F)
        buf_mouse_static_black = bytearray(91); buf_mouse_static_black[1:] = rep_mouse_static_black
        cbuf_mouse_static_black = (ctypes.c_char * 91).from_buffer(buf_mouse_static_black)

        rep_black_sw = _create_razer_report(0x0F, 0x02, 0x06, [0x00, 0x01, 0x00, 0x00, 0x00, 0x00], txn=0x3F)
        buf_black_sw = bytearray(91); buf_black_sw[1:] = rep_black_sw
        cbuf_black_sw = (ctypes.c_char * 91).from_buffer(buf_black_sw)

        rep_sw_static_black = _create_razer_report(0x0F, 0x02, 0x09, [0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0, 0, 0], txn=0x3F)
        buf_sw_static_black = bytearray(91); buf_sw_static_black[1:] = rep_sw_static_black
        cbuf_sw_static_black = (ctypes.c_char * 91).from_buffer(buf_sw_static_black)

        with self.lock:
            devs = list(self.devices)

        for dev in devs:
            try:
                self.hid.HidD_SetFeature(dev.handle, cbuf_mode, 91)
                self.hid.HidD_SetFeature(dev.handle, cbuf_leg_bright, 91)
                if dev.device_type == "keyboard":
                    self.hid.HidD_SetFeature(dev.handle, cbuf_kbd_bright, 91)
                    self.hid.HidD_SetFeature(dev.handle, cbuf_black_kbd, 91)
                elif dev.device_type == "mouse":
                    self.hid.HidD_SetFeature(dev.handle, cbuf_mouse_bright, 91)
                    self.hid.HidD_SetFeature(dev.handle, cbuf_mouse_static_black, 91)
                    self.hid.HidD_SetFeature(dev.handle, cbuf_black_mouse, 91)
                    if dev.pid == 0x0078:
                        dev.has_scroll_wheel = False
                    elif getattr(dev, "has_scroll_wheel", False):
                        self.hid.HidD_SetFeature(dev.handle, cbuf_sw_bright, 91)
                        self.hid.HidD_SetFeature(dev.handle, cbuf_sw_static_black, 91)
                        self.hid.HidD_SetFeature(dev.handle, cbuf_black_sw, 91)
                    else:
                        # Probe if mouse supports scroll wheel LED
                        rep_sw = _create_razer_report(0x0F, 0x02, 0x09, [0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0, 0, 0], txn=0x3F)
                        buf_sw = bytearray(91); buf_sw[1:] = rep_sw
                        if self.hid.HidD_SetFeature(dev.handle, (ctypes.c_char * 91).from_buffer(buf_sw), 91):
                            rbuf = bytearray(91)
                            if self.hid.HidD_GetFeature(dev.handle, (ctypes.c_char * 91).from_buffer(rbuf), 91):
                                dev.has_scroll_wheel = (rbuf[1] == 0x02)
                else:
                    self.hid.HidD_SetFeature(dev.handle, cbuf_kbd_bright, 91)
                    self.hid.HidD_SetFeature(dev.handle, cbuf_black_kbd, 91)
            except Exception:
                pass

    def _boost_peripheral_color(self, rgb, strobe_cut=False):
        """Color booster for physical Razer RGB LEDs during smooth rave modes."""
        r, g, b = rgb
        max_c = max(r, g, b)
        if max_c <= 0:
            return (0, 0, 0)
        norm = max_c / 255.0
        target_max = 60 + int(norm * 195)
        scale = target_max / max(1, max_c)
        return (min(255, int(r * scale)), min(255, int(g * scale)), min(255, int(b * scale)))

    def set_colors(self, rgb_left, rgb_right=None, strobe_cut=True, audio_state=None, is_dual=False, visualizer=None):
        """Push target colors, audio spectrum, and beat dynamics to Razer hardware (non-blocking)."""
        if not self.enabled or not self.devices:
            return

        c_left = tuple(max(0, min(255, int(v))) for v in rgb_left[:3])
        c_right = tuple(max(0, min(255, int(v))) for v in (rgb_right or rgb_left)[:3])

        vis_state = None
        if visualizer:
            vis_state = {
                "kick_intensity": getattr(visualizer, "kick_intensity", 0.0),
                "snare_intensity": getattr(visualizer, "snare_intensity", 0.0),
                "palette_colors": list(getattr(visualizer, "palette_colors", [])),
                "solid_color_active": getattr(visualizer, "solid_color_active", False),
                "solid_color": getattr(visualizer, "solid_color", (255, 0, 0)),
                "overdrive_mode": getattr(visualizer, "overdrive_mode", False),
                "safe_mode": getattr(visualizer, "safe_mode", False),
                "mode": getattr(visualizer, "mode", ""),
            }

        # Drain any backlog so the queue only ever holds the newest frame (zero latency)
        try:
            while not self.color_queue.empty():
                self.color_queue.get_nowait()
        except Exception:
            pass

        try:
            self.color_queue.put_nowait((c_left, c_right, strobe_cut, audio_state, is_dual, vis_state))
        except Exception:
            pass

    def _worker_loop(self):
        """Asynchronous worker loop sending 91-byte USB HID feature reports with zero lag."""
        last_sent_mouse_color = None
        last_sent_row_bytes = [None] * 6
        last_refresh_time = time.time()
        last_loop_time = time.perf_counter()
        was_kbd_blackout = False
        was_mouse_blackout = False

        # Pre-allocate static draw frame command for keyboard matrix (0x0F, 0x02, 0x0C, effect=0x08)
        buf_draw = bytearray(91)
        draw_args = bytearray(12)
        draw_args[2] = 0x08  # Draw LED Matrix Frame
        buf_draw[1:] = _create_razer_report(0x0F, 0x02, 0x0C, draw_args, txn=0x1F)
        cbuf_draw = (ctypes.c_char * 91).from_buffer(buf_draw)

        # Pre-allocate blackout buffers using true EFFECT_NONE (0x0F, 0x02, 0x06) with NO_SAVE (0x00)
        buf_kbd_off = bytearray(91)
        buf_kbd_off[1:] = _create_razer_report(0x0F, 0x02, 0x06, [0x00, 0x05, 0x00, 0x00, 0x00, 0x00], txn=0x1F)
        cbuf_kbd_off = (ctypes.c_char * 91).from_buffer(buf_kbd_off)

        buf_mouse_off = bytearray(91)
        buf_mouse_off[1:] = _create_razer_report(0x0F, 0x02, 0x06, [0x00, 0x04, 0x00, 0x00, 0x00, 0x00], txn=0x3F)
        cbuf_mouse_off = (ctypes.c_char * 91).from_buffer(buf_mouse_off)

        # Pre-allocate mouse static blackout command (0x0F, 0x02, 0x09) on LOGO (0x04)
        # Prevents mouse firmware from reverting to onboard profile (breathing/rainbow)
        buf_mouse_static_black = bytearray(91)
        buf_mouse_static_black[1:] = _create_razer_report(0x0F, 0x02, 0x09, [0x00, 0x04, 0x01, 0x00, 0x00, 0x01, 0, 0, 0], txn=0x3F)
        cbuf_mouse_static_black = (ctypes.c_char * 91).from_buffer(buf_mouse_static_black)

        buf_sw_off = bytearray(91)
        buf_sw_off[1:] = _create_razer_report(0x0F, 0x02, 0x06, [0x00, 0x01, 0x00, 0x00, 0x00, 0x00], txn=0x3F)
        cbuf_sw_off = (ctypes.c_char * 91).from_buffer(buf_sw_off)

        # Pre-allocate mouse scroll wheel static blackout command (0x0F, 0x02, 0x09) on SCROLL (0x01)
        buf_sw_static_black = bytearray(91)
        buf_sw_static_black[1:] = _create_razer_report(0x0F, 0x02, 0x09, [0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0, 0, 0], txn=0x3F)
        cbuf_sw_static_black = (ctypes.c_char * 91).from_buffer(buf_sw_static_black)

        # Pre-allocate 6 matrix row buffers with zero runtime memory allocations
        row_bufs = []
        cbuf_rows = []
        for r in range(6):
            buf = bytearray(91)
            buf[1] = 0
            buf[2] = 0x1F
            buf[6] = 0x47
            buf[7] = 0x0F
            buf[8] = 0x03
            buf[11] = r
            buf[12] = 0
            buf[13] = 21
            row_bufs.append(buf)
            cbuf_rows.append((ctypes.c_char * 91).from_buffer(buf))

        # Pre-allocate mouse logo and scroll wheel illuminated buffers
        buf_mouse_logo = bytearray(91)
        cbuf_mouse_logo = (ctypes.c_char * 91).from_buffer(buf_mouse_logo)
        buf_sw = bytearray(91)
        cbuf_sw = (ctypes.c_char * 91).from_buffer(buf_sw)

        while self.running:
            now_perf = time.perf_counter()
            dt = max(0.005, min(0.05, now_perf - last_loop_time))
            last_loop_time = now_perf

            try:
                item = self.color_queue.get(timeout=0.010)
            except queue.Empty:
                # Periodic keep-alive refresh during prolonged blackout (every 1.5s)
                # Guarantees mouse and keyboard never reset to onboard default profile during extended silence
                now_t = time.time()
                if (now_t - last_refresh_time >= 1.5) and was_kbd_blackout and was_mouse_blackout:
                    last_refresh_time = now_t
                    with self.lock:
                        devs = list(self.devices)
                    for dev in devs:
                        try:
                            if dev.device_type == "keyboard":
                                self.hid.HidD_SetFeature(dev.handle, cbuf_kbd_off, 91)
                            elif dev.device_type == "mouse":
                                self.hid.HidD_SetFeature(dev.handle, cbuf_mouse_static_black, 91)
                                self.hid.HidD_SetFeature(dev.handle, cbuf_mouse_off, 91)
                                if getattr(dev, "has_scroll_wheel", False):
                                    self.hid.HidD_SetFeature(dev.handle, cbuf_sw_static_black, 91)
                                    self.hid.HidD_SetFeature(dev.handle, cbuf_sw_off, 91)
                        except Exception:
                            pass
                continue

            last_refresh_time = time.time()
            if len(item) == 6:
                c_left, c_right, strobe_cut, audio_state, is_dual, vis_state = item
            else:
                c_left, c_right, strobe_cut = item[:3]
                audio_state, is_dual, vis_state = None, False, None

            if strobe_cut:
                b_left, b_right = c_left, c_right
            else:
                # Smooth rave pulsing mode (Safe Mode or Smooth Rave Pulse)
                b_left = self._boost_peripheral_color(c_left, strobe_cut=False)
                b_right = self._boost_peripheral_color(c_right, strobe_cut=False)

            with self.lock:
                devs = list(self.devices)

            if not devs or not self.enabled:
                continue

            # 1. Update Keyboard Matrix (Per-key / per-row dynamic lighting)
            has_keyboard = any(d.device_type == "keyboard" for d in devs)
            if has_keyboard:
                matrix, is_kbd_blackout = self.matrix_engine.generate_matrix(
                    dt, b_left, b_right, strobe_cut, audio_state=audio_state, is_dual=is_dual, vis_state=vis_state
                )

                for dev in devs:
                    if dev.device_type != "keyboard":
                        continue
                    try:
                        if is_kbd_blackout:
                            if not was_kbd_blackout:
                                self.hid.HidD_SetFeature(dev.handle, cbuf_kbd_off, 91)
                                was_kbd_blackout = True
                                last_sent_row_bytes = [None] * 6
                        else:
                            was_kbd_blackout = False
                            has_drawn = False
                            for r in range(6):
                                r_bytes = matrix[r].tobytes()
                                if r_bytes != last_sent_row_bytes[r]:
                                    last_sent_row_bytes[r] = r_bytes
                                    buf_r = row_bufs[r]
                                    buf_r[14:80] = r_bytes
                                    crc = 0
                                    for i in range(3, 89):
                                        crc ^= buf_r[i]
                                    buf_r[89] = crc
                                    self.hid.HidD_SetFeature(dev.handle, cbuf_rows[r], 91)
                                    has_drawn = True
                            if has_drawn:
                                self.hid.HidD_SetFeature(dev.handle, cbuf_draw, 91)
                    except Exception:
                        pass

            # 2. Update Mouse & Other Peripherals
            is_mouse_blackout = (b_right == (0, 0, 0))
            for dev in devs:
                if dev.device_type == "keyboard":
                    continue
                try:
                    if dev.device_type == "mouse":
                        if is_mouse_blackout:
                            if not was_mouse_blackout:
                                self.hid.HidD_SetFeature(dev.handle, cbuf_mouse_static_black, 91)
                                self.hid.HidD_SetFeature(dev.handle, cbuf_mouse_off, 91)
                                if getattr(dev, "has_scroll_wheel", False):
                                    self.hid.HidD_SetFeature(dev.handle, cbuf_sw_static_black, 91)
                                    self.hid.HidD_SetFeature(dev.handle, cbuf_sw_off, 91)
                                was_mouse_blackout = True
                                last_sent_mouse_color = (0, 0, 0)
                        else:
                            was_mouse_blackout = False
                            if b_right != last_sent_mouse_color:
                                last_sent_mouse_color = b_right
                                rep_ml = _create_razer_report(0x0F, 0x02, 0x09, [0x00, 0x04, 0x01, 0x00, 0x00, 0x01, b_right[0], b_right[1], b_right[2]], txn=0x3F)
                                buf_mouse_logo[1:] = rep_ml
                                self.hid.HidD_SetFeature(dev.handle, cbuf_mouse_logo, 91)

                                if getattr(dev, "has_scroll_wheel", False):
                                    rep_sw = _create_razer_report(0x0F, 0x02, 0x09, [0x00, 0x01, 0x01, 0x00, 0x00, 0x01, b_right[0], b_right[1], b_right[2]], txn=0x3F)
                                    buf_sw[1:] = rep_sw
                                    self.hid.HidD_SetFeature(dev.handle, cbuf_sw, 91)
                    else:
                        # Mousepad / Headset generic fallback
                        if is_kbd_blackout:
                            self.hid.HidD_SetFeature(dev.handle, cbuf_kbd_off, 91)
                        else:
                            args_gen = bytearray([0x00, getattr(dev, "led_id", 0x05), 0x01, 0x00, 0x00, 0x01, b_left[0], b_left[1], b_left[2]])
                            rep_gen = _create_razer_report(0x0F, 0x02, 0x09, args_gen, txn=0x3F)
                            buf_gen = bytearray(91); buf_gen[1:] = rep_gen
                            self.hid.HidD_SetFeature(dev.handle, (ctypes.c_char * 91).from_buffer(buf_gen), 91)
                except Exception:
                    pass

    def toggle_enabled(self):
        """Toggle Razer hardware lighting on/off."""
        self.enabled = not self.enabled
        if self.enabled:
            self._configure_devices()
        else:
            # Turn LEDs off (blackout)
            self.set_colors((0, 0, 0), (0, 0, 0))
        return self.enabled

    def stop(self):
        """Gracefully release hardware handles and stop worker thread."""
        self.running = False
        try:
            self.set_colors((0, 0, 0), (0, 0, 0))
            time.sleep(0.04)
        except Exception:
            pass

        with self.lock:
            for d in self.devices:
                try:
                    if self.hid:
                        # Turn off LEDs cleanly with STATIC BLACK and EFFECT_NONE
                        txn_off = 0x1F if d.device_type == "keyboard" else 0x3F
                        rep_sblack = _create_razer_report(0x0F, 0x02, 0x09, [0x00, getattr(d, 'led_id', 0x04), 0x01, 0x00, 0x00, 0x01, 0, 0, 0], txn=txn_off)
                        buf_sblack = bytearray(91); buf_sblack[1:] = rep_sblack
                        self.hid.HidD_SetFeature(d.handle, (ctypes.c_char * 91).from_buffer(buf_sblack), 91)

                        rep_off = _create_razer_report(0x0F, 0x02, 0x06, [0x00, getattr(d, 'led_id', 0x05), 0x00, 0x00, 0x00, 0x00], txn=txn_off)
                        buf_off = bytearray(91); buf_off[1:] = rep_off
                        self.hid.HidD_SetFeature(d.handle, (ctypes.c_char * 91).from_buffer(buf_off), 91)

                        # Restore hardware Normal Mode (0x00) for media keys / volume roller
                        rep_mode = _create_razer_report(0x00, 0x04, 0x02, [0x00, 0x00], txn=0x3F)
                        buf_mode = bytearray(91); buf_mode[1:] = rep_mode
                        self.hid.HidD_SetFeature(d.handle, (ctypes.c_char * 91).from_buffer(buf_mode), 91)
                    if self.kernel32:
                        self.kernel32.CloseHandle(d.handle)
                except Exception:
                    pass
            self.devices = []
            self.device_count = 0
