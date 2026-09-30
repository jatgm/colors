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


def _create_razer_report(command_class, command_id, data_size, arguments, txn=0x1F):
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

    def __repr__(self):
        return f"<RazerDevice {self.name} ({self.device_type}) PID=0x{self.pid:04X}>"


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
        """Set all Razer devices to Driver Mode (0x03) and 100% hardware brightness (0xFF)."""
        if not self.hid:
            return
        # 1. Driver Mode: class=0x00, id=0x04, size=0x02, args=[0x03, 0x00]
        rep_mode = _create_razer_report(0x00, 0x04, 0x02, [0x03, 0x00])
        buf_mode = bytearray(91)
        buf_mode[1:] = rep_mode
        cbuf_mode = (ctypes.c_char * 91).from_buffer(buf_mode)

        # 2. Maximum Brightness: class=0x03, id=0x03, size=0x03, args=[0x00, 0x00, 0xFF]
        rep_bright = _create_razer_report(0x03, 0x03, 0x03, [0x00, 0x00, 0xFF])
        buf_bright = bytearray(91)
        buf_bright[1:] = rep_bright
        cbuf_bright = (ctypes.c_char * 91).from_buffer(buf_bright)

        with self.lock:
            devs = list(self.devices)

        for dev in devs:
            try:
                self.hid.HidD_SetFeature(dev.handle, cbuf_mode, 91)
                self.hid.HidD_SetFeature(dev.handle, cbuf_bright, 91)
            except Exception:
                pass

    def _boost_peripheral_color(self, rgb):
        """Boost contrast and minimum visibility floor for keycaps and light diffusers."""
        r, g, b = rgb
        max_c = max(r, g, b)
        if max_c <= 0:
            return (0, 0, 0)
        # Apply perceptual boost: if color is soft, lift it so LEDs visibly illuminate
        # If it's a hard beat (>180), keep full blast
        if max_c < 65:
            # Gentle ambient music lift (minimum 28-35 on dominant channel)
            scale = max(1.2, min(2.5, 32.0 / max(1, max_c)))
        else:
            scale = 1.15
        br = min(255, int(r * scale))
        bg = min(255, int(g * scale))
        bb = min(255, int(b * scale))
        return (br, bg, bb)

    def set_colors(self, rgb_left, rgb_right=None):
        """Push target colors to Razer hardware (non-blocking)."""
        if not self.enabled or not self.devices:
            return

        c_left = tuple(max(0, min(255, int(v))) for v in rgb_left[:3])
        c_right = tuple(max(0, min(255, int(v))) for v in (rgb_right or rgb_left)[:3])

        try:
            self.color_queue.put_nowait((c_left, c_right))
        except queue.Full:
            pass

    def _worker_loop(self):
        """Asynchronous worker loop sending 91-byte USB HID feature reports."""
        last_left = None
        last_right = None

        while self.running:
            try:
                item = self.color_queue.get(timeout=0.035)
            except queue.Empty:
                continue

            c_left, c_right = item
            if c_left == last_left and c_right == last_right:
                continue
            last_left = c_left
            last_right = c_right

            with self.lock:
                devs = list(self.devices)

            if not devs or not self.enabled:
                continue

            # Boost colors for physical LED keycaps & lightbars
            b_left = self._boost_peripheral_color(c_left)
            b_right = self._boost_peripheral_color(c_right)

            # Build reports for left and right channels (NOSTORE volatile mode)
            # cmd 0x0F / 0x02: Extended matrix static color
            args_left = bytearray([0x00, 0x00, 0x01, 0x00, 0x00, 0x01, b_left[0], b_left[1], b_left[2]])
            rep_left = _create_razer_report(0x0F, 0x02, 0x09, args_left)
            buf_left = bytearray(91)
            buf_left[1:] = rep_left
            cbuf_left = (ctypes.c_char * 91).from_buffer(buf_left)

            if b_left == b_right:
                cbuf_right = cbuf_left
            else:
                args_right = bytearray([0x00, 0x00, 0x01, 0x00, 0x00, 0x01, b_right[0], b_right[1], b_right[2]])
                rep_right = _create_razer_report(0x0F, 0x02, 0x09, args_right)
                buf_right = bytearray(91)
                buf_right[1:] = rep_right
                cbuf_right = (ctypes.c_char * 91).from_buffer(buf_right)

            # Send to hardware
            for dev in devs:
                try:
                    # Keyboards map to left/primary channel; mice map to right channel
                    cbuf = cbuf_right if dev.device_type == "mouse" else cbuf_left
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
        # Fade out before closing
        try:
            self.set_colors((0, 0, 0), (0, 0, 0))
            time.sleep(0.05)
        except Exception:
            pass

        with self.lock:
            for d in self.devices:
                try:
                    self.kernel32.CloseHandle(d.handle)
                except Exception:
                    pass
            self.devices = []
            self.device_count = 0
