"""
Razer Chroma Peripheral Lighting Synchronization.
Supports Razer Keyboards, Mice, Mousepads, and Headsets on Windows
via direct USB HID Feature Reports (zero-dependency, no Synapse required)
and Razer Chroma REST API.
"""

import sys
import time
import queue
import threading
import ctypes
from ctypes import wintypes


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


class RazerChromaManager:
    """Synchronizes screen strobe colors with connected Razer peripherals in real time."""

    def __init__(self):
        self.enabled = True
        self.devices = []
        self.device_names = []
        self.device_count = 0
        self.active_mode = "NONE"

        self.color_queue = queue.Queue(maxsize=3)
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

                    found.append(RazerDevice(p_name, dev_type, path, attrs.ProductID, h))
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
        """Set all Razer devices to Normal Mode (0x00) and 100% hardware brightness (0xFF)."""
        if not self.hid:
            return
        # 1. Normal Mode (0x00, 0x00): Ensures physical volume wheel and media keys (Play/Pause/Skip)
        # function as native Windows system volume & media keys instead of scrolling
        rep_mode = _create_razer_report(0x00, 0x04, 0x02, [0x00, 0x00], txn=0x3F)
        buf_mode = bytearray(91)
        buf_mode[1:] = rep_mode
        cbuf_mode = (ctypes.c_char * 91).from_buffer(buf_mode)

        # 2. Maximum Brightness: Extended matrix brightness (0x0F, 0x04) + Legacy fallback (0x03, 0x03)
        rep_ext_bright = _create_razer_report(0x0F, 0x04, 0x03, [0x00, 0x00, 0xFF], txn=0x3F)
        buf_ext_bright = bytearray(91)
        buf_ext_bright[1:] = rep_ext_bright
        cbuf_ext_bright = (ctypes.c_char * 91).from_buffer(buf_ext_bright)

        rep_leg_bright = _create_razer_report(0x03, 0x03, 0x03, [0x00, 0x00, 0xFF], txn=0x3F)
        buf_leg_bright = bytearray(91)
        buf_leg_bright[1:] = rep_leg_bright
        cbuf_leg_bright = (ctypes.c_char * 91).from_buffer(buf_leg_bright)

        with self.lock:
            devs = list(self.devices)

        for dev in devs:
            try:
                self.hid.HidD_SetFeature(dev.handle, cbuf_mode, 91)
                self.hid.HidD_SetFeature(dev.handle, cbuf_ext_bright, 91)
                self.hid.HidD_SetFeature(dev.handle, cbuf_leg_bright, 91)

                # Check if mouse supports scroll wheel LED
                if dev.device_type == "mouse":
                    rep_sw = _create_razer_report(0x0F, 0x02, 0x09, [0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0, 0, 0], txn=0x3F)
                    buf_sw = bytearray(91); buf_sw[1:] = rep_sw
                    if self.hid.HidD_SetFeature(dev.handle, (ctypes.c_char * 91).from_buffer(buf_sw), 91):
                        rbuf = bytearray(91)
                        if self.hid.HidD_GetFeature(dev.handle, (ctypes.c_char * 91).from_buffer(rbuf), 91):
                            dev.has_scroll_wheel = (rbuf[1] == 0x02)
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

    def set_colors(self, rgb_left, rgb_right=None, strobe_cut=True):
        """Push target colors to Razer hardware (non-blocking, freshest frame only)."""
        if not self.enabled or not self.devices:
            return

        c_left = tuple(max(0, min(255, int(v))) for v in rgb_left[:3])
        c_right = tuple(max(0, min(255, int(v))) for v in (rgb_right or rgb_left)[:3])

        # Drain any backlog so the queue only ever holds the newest frame (zero latency)
        try:
            while True:
                self.color_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            self.color_queue.put_nowait((c_left, c_right, strobe_cut))
        except queue.Full:
            pass

    def _worker_loop(self):
        """Asynchronous worker loop sending 91-byte USB HID feature reports."""
        last_sent_left = None
        last_sent_right = None
        flash_until_time = 0.0

        while self.running:
            try:
                item = self.color_queue.get(timeout=0.015)
            except queue.Empty:
                # If timeout occurred while holding a flash, check if hold timer expired
                if flash_until_time > 0 and time.perf_counter() >= flash_until_time:
                    flash_until_time = 0.0
                    b_left, b_right = (0, 0, 0), (0, 0, 0)
                else:
                    continue
            else:
                c_left, c_right, strobe_cut = item
                now = time.perf_counter()

                if strobe_cut:
                    is_flash = (c_left != (0, 0, 0) or c_right != (0, 0, 0))
                    if is_flash:
                        if now >= flash_until_time:
                            # Latch fresh peak flash for 70ms for maximum retinal brilliance
                            flash_until_time = now + 0.070
                            b_left, b_right = c_left, c_right
                        else:
                            # Keep holding current flash peak
                            continue
                    else:
                        if now < flash_until_time:
                            # Keep holding flash peak until hold duration elapses
                            continue
                        flash_until_time = 0.0
                        b_left, b_right = (0, 0, 0), (0, 0, 0)
                else:
                    # Smooth rave pulsing mode (Safe Mode or Smooth Rave Pulse)
                    flash_until_time = 0.0
                    b_left = self._boost_peripheral_color(c_left, strobe_cut=False)
                    b_right = self._boost_peripheral_color(c_right, strobe_cut=False)

            if b_left == last_sent_left and b_right == last_sent_right:
                continue
            last_sent_left = b_left
            last_sent_right = b_right

            with self.lock:
                devs = list(self.devices)

            if not devs or not self.enabled:
                continue

            # Pre-build packet buffers using VARSTORE (0x01):
            # cmd 0x0F / 0x02: Extended matrix static color
            # Keyboard backlight (0x05) uses txn 0x1F
            args_kbd = bytearray([0x01, 0x05, 0x01, 0x00, 0x00, 0x01, b_left[0], b_left[1], b_left[2]])
            rep_kbd = _create_razer_report(0x0F, 0x02, 0x09, args_kbd, txn=0x1F)
            buf_kbd = bytearray(91)
            buf_kbd[1:] = rep_kbd
            cbuf_kbd = (ctypes.c_char * 91).from_buffer(buf_kbd)

            # Mouse logo (0x04) uses txn 0x3F
            args_mouse_logo = bytearray([0x01, 0x04, 0x01, 0x00, 0x00, 0x01, b_right[0], b_right[1], b_right[2]])
            rep_mouse_logo = _create_razer_report(0x0F, 0x02, 0x09, args_mouse_logo, txn=0x3F)
            buf_mouse_logo = bytearray(91)
            buf_mouse_logo[1:] = rep_mouse_logo
            cbuf_mouse_logo = (ctypes.c_char * 91).from_buffer(buf_mouse_logo)

            cbuf_mouse_wheel = None

            # Send to hardware
            for dev in devs:
                try:
                    if dev.device_type == "keyboard":
                        self.hid.HidD_SetFeature(dev.handle, cbuf_kbd, 91)
                    elif dev.device_type == "mouse":
                        self.hid.HidD_SetFeature(dev.handle, cbuf_mouse_logo, 91)
                        if getattr(dev, "has_scroll_wheel", False):
                            if cbuf_mouse_wheel is None:
                                args_sw = bytearray([0x01, 0x01, 0x01, 0x00, 0x00, 0x01, b_right[0], b_right[1], b_right[2]])
                                rep_sw = _create_razer_report(0x0F, 0x02, 0x09, args_sw, txn=0x3F)
                                buf_sw = bytearray(91)
                                buf_sw[1:] = rep_sw
                                cbuf_mouse_wheel = (ctypes.c_char * 91).from_buffer(buf_sw)
                            self.hid.HidD_SetFeature(dev.handle, cbuf_mouse_wheel, 91)
                    else:
                        cbuf = cbuf_mouse_logo if getattr(dev, "led_id", 0x05) == 0x04 else cbuf_kbd
                        self.hid.HidD_SetFeature(dev.handle, cbuf, 91)
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
        # Restore hardware Normal Mode (0x00) and fade out
        try:
            self.set_colors((0, 0, 0), (0, 0, 0))
            time.sleep(0.04)
        except Exception:
            pass

        with self.lock:
            for d in self.devices:
                try:
                    if self.hid:
                        rep_mode = _create_razer_report(0x00, 0x04, 0x02, [0x00, 0x00], txn=0x3F)
                        buf_mode = bytearray(91)
                        buf_mode[1:] = rep_mode
                        self.hid.HidD_SetFeature(d.handle, (ctypes.c_char * 91).from_buffer(buf_mode), 91)
                    self.kernel32.CloseHandle(d.handle)
                except Exception:
                    pass
            self.devices = []
            self.device_count = 0
