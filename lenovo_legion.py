"""
Lenovo Legion Gaming Desktop RGB Synchronization.
Supports Lenovo Legion PCs (e.g. Legion T5 28IMB05 / T550, T730, T530, etc.)
equipped with ITE 8297 / IT8233 USB RGB controllers (VID 0x17EF / 0x048D, PID 0xC955 / 0x8297)
via direct Win32 USB HID Feature Reports (zero external dependencies).

Native Lenovo Vantage Protocol:
- Zone 1: Front Legion "Y" Logo (Monochromatic Blue)
- Zone 2: Front Bezel / Accents (Monochromatic Blue)
- Zone 3: CPU Cooler Fan / ARGB Header (Full RGB)
- Zone 4: Rear Exhaust Fan / Front Intake (Full RGB)
- Zone 5: Front Upper ARGB Fan / Header (Full RGB)
- Zone 6: Front Lower ARGB Fan / Header (Full RGB)

On beat flashes:
- Fans reflect dynamic RGB strobe colors at full brightness (scale 4).
- Monochromatic blue zones (logo and accents) illuminate in OEM Lenovo Vantage Blue (21, 141, 255)
  at full brightness so they flash synchronously with the beat impacts.
On blackout:
- All zones switch to effect 0, brightness 0, RGB (0, 0, 0) for true blackout cuts.
"""

import sys
import time
import queue
import threading
import ctypes

try:
    from ctypes import wintypes, Structure, c_uint8, c_uint, c_ushort
except ImportError:
    wintypes = None


# USB identifiers for Lenovo Legion / ITE 8297 RGB controllers
LENOVO_VID = 0x17EF
ITE_VID = 0x048D
KNOWN_PIDS = (0xC955, 0x8297, 0x5702, 0xC968, 0xC977, 0xC978, 0xC987, 0xC988)

# HID Usages for ITE 8297 lighting feature report
RGB_USAGE_PAGE = 0xFF89
RGB_USAGE = 0x00CC
REPORT_ID = 0xCC
REPORT_LEN = 64

# Native Lenovo / ITE Commands
CMD_INIT = 0x60
CMD_APPLY_PRIMARY = 0x28
CMD_APPLY_SECONDARY = 0x2D

# Effect Commands
EFFECT_OFF = 0
EFFECT_STATIC = 1
EFFECT_BREATHING = 2

# Native Lenovo Motherboard Zones
ZONE_LOGO = 0x01           # Front Legion "Y" Logo (Monochromatic Blue)
ZONE_FRONT_BEZEL = 0x02    # Front Bezel / Accents (Monochromatic Blue)
ZONE_FRONT_ACCENT = 0x10   # Front Bezel Accent / Logo (Alternate address)
ZONE_REAR_FAN = 0x11       # Rear Exhaust Fan (Secondary RGB / Monochromatic)
ZONE_CPU_COOLER = 0x12     # CPU Cooler Fan / ARGB Header (Primary RGB)
ZONE_FRONT_UPPER = 0x13    # Front Upper Intake Fan (Primary RGB / Monochromatic)
ZONE_FRONT_LOWER = 0x14    # Front Lower Intake Fan (Secondary RGB / Monochromatic)

ALL_NATIVE_ZONES = (
    ZONE_LOGO,
    ZONE_FRONT_BEZEL,
    ZONE_FRONT_ACCENT,
    ZONE_REAR_FAN,
    ZONE_CPU_COOLER,
    ZONE_FRONT_UPPER,
    ZONE_FRONT_LOWER,
)

MONOCHROME_BLUE_ZONES = (ZONE_LOGO, ZONE_FRONT_BEZEL, ZONE_FRONT_ACCENT)
FAN_ARGB_ZONES = (ZONE_CPU_COOLER, ZONE_REAR_FAN, ZONE_FRONT_UPPER, ZONE_FRONT_LOWER)

# Lenovo Vantage OEM Blue (with blue pinned to 255 for max monochromatic LED luminance)
LENOVO_LOGO_BLUE = (21, 141, 255)



if wintypes:
    class GUID(Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_byte * 8),
        ]

    class SP_DEVICE_INTERFACE_DATA(Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("InterfaceClassGuid", GUID),
            ("Flags", wintypes.DWORD),
            ("Reserved", ctypes.c_size_t),
        ]

    class HIDD_ATTRIBUTES(Structure):
        _fields_ = [
            ("Size", wintypes.DWORD),
            ("VendorID", wintypes.WORD),
            ("ProductID", wintypes.WORD),
            ("VersionNumber", wintypes.WORD),
        ]

    class HIDP_CAPS(Structure):
        _fields_ = [
            ("Usage", ctypes.c_ushort),
            ("UsagePage", ctypes.c_ushort),
            ("InputReportByteLength", ctypes.c_ushort),
            ("OutputReportByteLength", ctypes.c_ushort),
            ("FeatureReportByteLength", ctypes.c_ushort),
            ("Reserved", ctypes.c_ushort * 17),
            ("NumberLinkCollectionNodes", ctypes.c_ushort),
            ("NumberInputButtonCaps", ctypes.c_ushort),
            ("NumberInputValueCaps", ctypes.c_ushort),
            ("NumberInputDataIndices", ctypes.c_ushort),
            ("NumberOutputButtonCaps", ctypes.c_ushort),
            ("NumberOutputValueCaps", ctypes.c_ushort),
            ("NumberOutputDataIndices", ctypes.c_ushort),
            ("NumberFeatureButtonCaps", ctypes.c_ushort),
            ("NumberFeatureValueCaps", ctypes.c_ushort),
            ("NumberFeatureDataIndices", ctypes.c_ushort),
        ]

    class PktLenovoZone(Structure):
        """Native Lenovo Vantage Desktop 64-byte zone feature report."""
        _pack_ = 1
        _fields_ = [
            ("report_id", c_uint8),    # Byte 0: 0xCC
            ("zone_id", c_uint8),      # Byte 1: zone (0x12, 0x11, 0x10, 0x13, 0x14)
            ("effect_cmd", c_uint8),   # Byte 2: mode (0=Off, 1=Static, 2=Sparkle, 3=Breathing)
            ("speed", c_uint8),        # Byte 3: 1..4 (default 1)
            ("brightness", c_uint8),   # Byte 4: 0..4 (0=Off, 4=Full 100%)
            ("red", c_uint8),          # Byte 5: 0..255
            ("green", c_uint8),        # Byte 6: 0..255
            ("blue", c_uint8),         # Byte 7: 0..255
            ("padding", c_uint8 * 56), # Bytes 8..63: 0
        ]

    class PktLenovoCommit(Structure):
        """Native Lenovo Vantage Desktop 64-byte commit feature report."""
        _pack_ = 1
        _fields_ = [
            ("report_id", c_uint8),       # Byte 0: 0xCC
            ("cmd_apply", c_uint8),       # Byte 1: 0x28
            ("sub_cmd", c_uint8),         # Byte 2: 0x06
            ("pad_before", c_uint8 * 30), # Bytes 3..32
            ("zone_id", c_uint8),         # Byte 33: zone
            ("effect_cmd", c_uint8),      # Byte 34: mode
            ("speed", c_uint8),           # Byte 35: speed
            ("brightness", c_uint8),      # Byte 36: brightness
            ("red", c_uint8),             # Byte 37: red
            ("green", c_uint8),           # Byte 38: green
            ("blue", c_uint8),            # Byte 39: blue
            ("padding", c_uint8 * 24),    # Bytes 40..63
        ]

    class PktEffect(Structure):
        """ITE 8297 / Gigabyte compatibility 64-byte feature report."""
        _pack_ = 1
        _fields_ = [
            ("report_id", c_uint8),
            ("header", c_uint8),
            ("zone0", c_uint),
            ("zone1", c_uint),
            ("reserved0", c_uint8),
            ("effect_type", c_uint8),
            ("max_brightness", c_uint8),
            ("min_brightness", c_uint8),
            ("color0", c_uint),
            ("color1", c_uint),
            ("period0", c_ushort),
            ("period1", c_ushort),
            ("period2", c_ushort),
            ("period3", c_ushort),
            ("param0", c_uint8),
            ("param1", c_uint8),
            ("param2", c_uint8),
            ("param3", c_uint8),
            ("padding0", c_uint8 * 30),
        ]


class LenovoLegionManager:
    """Manages Lenovo Legion desktop motherboard, fans, cooler, and case RGB lighting."""

    def __init__(self):
        self.enabled = True
        self.connected = False
        self.device_name = "Lenovo Legion RGB"
        self.device_path = None
        self.handle = None

        self.color_queue = queue.Queue(maxsize=3)
        self.running = True
        self.lock = threading.Lock()

        # Win32 API
        self.setupapi = None
        self.hid = None
        self.kernel32 = None

        # Pre-allocated Native Lenovo buffers & structs (Zones 1, 2, 0x10, 0x11, 0x12, 0x13, 0x14)
        self.native_pkts = {}
        self.apply_primary_buf = None
        self.apply_secondary_buf = None

        if sys.platform == "win32" and wintypes:
            self._init_win32_api()
            self._connect()

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

            self.setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
            self.setupapi.SetupDiGetClassDevsW.argtypes = [
                ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD
            ]
            self.setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
            self.setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
                wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD,
                ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)
            ]
            self.setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
            self.setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p,
                wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
            ]
            self.setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]

            self.hid.HidD_GetPreparsedData.restype = wintypes.BOOL
            self.hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
            self.hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
            self.hid.HidP_GetCaps.restype = wintypes.LONG
            self.hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
            self.hid.HidD_GetAttributes.restype = wintypes.BOOL
            self.hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
            self.hid.HidD_SetFeature.restype = wintypes.BOOL
            self.hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
            self.hid.HidD_GetFeature.restype = wintypes.BOOL
            self.hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
        except Exception:
            pass

    def _connect(self):
        """Find and open the ITE 8297 RGB USB HID lighting controller."""
        if not self.setupapi or not self.hid:
            return

        guid = GUID()
        self.hid.HidD_GetHidGuid(ctypes.byref(guid))
        hdev = self.setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)

        cb = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        idx = 0
        iface = SP_DEVICE_INTERFACE_DATA()
        iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)

        found_path = None

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

            # Query device attributes
            h = self.kernel32.CreateFileW(path, 0, 3, None, 3, 0, None)
            if h in (None, 0, -1, 0xFFFFFFFF, ctypes.c_void_p(-1).value):
                continue

            try:
                attrs = HIDD_ATTRIBUTES()
                attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
                if self.hid.HidD_GetAttributes(h, ctypes.byref(attrs)):
                    vid = attrs.VendorID
                    pid = attrs.ProductID

                    if (vid in (LENOVO_VID, ITE_VID)) and (pid in KNOWN_PIDS):
                        pp = ctypes.c_void_p()
                        caps = HIDP_CAPS()
                        if self.hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
                            if self.hid.HidP_GetCaps(pp, ctypes.byref(caps)) == 0x00110000:
                                # Look for the 64-byte lighting collection (UsagePage 0xFF89, Usage 0xCC)
                                if caps.UsagePage == RGB_USAGE_PAGE and caps.Usage == RGB_USAGE:
                                    found_path = path
                            self.hid.HidD_FreePreparsedData(pp)
            except Exception:
                pass
            finally:
                self.kernel32.CloseHandle(h)

            if found_path:
                break

        self.setupapi.SetupDiDestroyDeviceInfoList(hdev)

        if not found_path:
            return

        # Open for Read/Write shared access
        h_rw = self.kernel32.CreateFileW(found_path, 0xC0000000, 3, None, 3, 0, None)
        if h_rw in (None, 0, -1, 0xFFFFFFFF, ctypes.c_void_p(-1).value):
            # Fallback to query access if RW is claimed
            h_rw = self.kernel32.CreateFileW(found_path, 0, 3, None, 3, 0, None)

        if h_rw in (None, 0, -1, 0xFFFFFFFF, ctypes.c_void_p(-1).value):
            return

        self.handle = h_rw
        self.device_path = found_path
        self.connected = True

        # Send controller initialization report
        init_buf = (c_uint8 * REPORT_LEN)()
        init_buf[0] = REPORT_ID
        init_buf[1] = CMD_INIT
        self.hid.HidD_SetFeature(self.handle, ctypes.byref(init_buf), REPORT_LEN)

        get_buf = (c_uint8 * REPORT_LEN)()
        get_buf[0] = REPORT_ID
        if self.hid.HidD_GetFeature(self.handle, ctypes.byref(get_buf), REPORT_LEN):
            try:
                raw_bytes = bytes(get_buf)
                null = raw_bytes.find(0, 12)
                null = null if null != -1 else len(raw_bytes)
                dev_str = raw_bytes[12:null].decode("ascii", errors="replace").strip()
                if dev_str:
                    self.device_name = f"Lenovo PC ({dev_str})"
            except Exception:
                pass

        # 1. Pre-allocate Native Lenovo Zone Packets (Zones 1, 2, 0x10, 0x11, 0x12, 0x13, 0x14)
        self.native_pkts = {}
        for z in ALL_NATIVE_ZONES:
            pz = PktLenovoZone()
            pz.report_id = REPORT_ID
            pz.zone_id = z
            pz.effect_cmd = EFFECT_OFF
            pz.speed = 1
            pz.brightness = 0
            pz.red = 0
            pz.green = 0
            pz.blue = 0
            self.native_pkts[z] = pz

        # 2. Native Lenovo Primary & Secondary Apply Packets (verified from Lenovo Vantage driver)
        # Primary apply: [0xCC, 0x28, 0x0F, ...]
        self.apply_primary_buf = (c_uint8 * REPORT_LEN)()
        self.apply_primary_buf[0] = REPORT_ID
        self.apply_primary_buf[1] = CMD_APPLY_PRIMARY
        self.apply_primary_buf[2] = 0x0F

        # Secondary apply: [0xCC, 0x2D, 0x07, ...]
        self.apply_secondary_buf = (c_uint8 * REPORT_LEN)()
        self.apply_secondary_buf[0] = REPORT_ID
        self.apply_secondary_buf[1] = CMD_APPLY_SECONDARY
        self.apply_secondary_buf[2] = 0x07

    def _boost_color(self, rgb):
        """Color booster for smooth rave transitions."""
        r, g, b = rgb
        max_c = max(r, g, b)
        if max_c <= 0:
            return (0, 0, 0)
        norm = max_c / 255.0
        target_max = 60 + int(norm * 195)
        scale = target_max / max(1, max_c)
        return (min(255, int(r * scale)), min(255, int(g * scale)), min(255, int(b * scale)))

    def set_colors(self, rgb, secondary_rgb=None, strobe_cut=True):
        """Push target colors to Lenovo Legion PC lighting (non-blocking).

        Args:
            rgb: Primary (r, g, b) color tuple for fans and chassis.
            secondary_rgb: Optional secondary (r, g, b) color tuple for dual-zone fan effects.
                           If a boolean is passed here, it is treated as strobe_cut for backward compatibility.
            strobe_cut: True for hard beat flash & blackout cuts; False for boosted smooth transitions.
        """
        if not self.enabled or not self.connected:
            return

        if isinstance(secondary_rgb, bool):
            strobe_cut = secondary_rgb
            secondary_rgb = None

        c1 = tuple(max(0, min(255, int(v))) for v in rgb[:3])
        c2 = tuple(max(0, min(255, int(v))) for v in secondary_rgb[:3]) if secondary_rgb is not None else c1

        # Drain backlog so queue only ever holds the newest frame
        try:
            while True:
                self.color_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            self.color_queue.put_nowait((c1, c2, strobe_cut))
        except queue.Full:
            pass

    def _send_blackout(self):
        """Immediately transmit blackout / power-off feature reports to all controller zones."""
        with self.lock:
            h = self.handle
            if not h or not self.hid:
                return

            try:
                # 1. Native Lenovo motherboard zones blackout
                for z, pz in self.native_pkts.items():
                    pz.effect_cmd = EFFECT_OFF
                    pz.brightness = 0
                    pz.red = 0
                    pz.green = 0
                    pz.blue = 0
                    self.hid.HidD_SetFeature(h, ctypes.byref(pz), REPORT_LEN)

                # Commit changes on controller (Primary 0x28 + Secondary 0x2D)
                if self.apply_primary_buf:
                    self.hid.HidD_SetFeature(h, ctypes.byref(self.apply_primary_buf), REPORT_LEN)
                if self.apply_secondary_buf:
                    self.hid.HidD_SetFeature(h, ctypes.byref(self.apply_secondary_buf), REPORT_LEN)
            except Exception:
                pass

    def _worker_loop(self):
        """Dedicated background worker thread writing to the USB HID controller."""
        last_sent = None

        while self.running:
            try:
                item = self.color_queue.get(timeout=0.030)
            except queue.Empty:
                continue

            c1, c2, strobe_cut = item

            if strobe_cut:
                target_rgb1 = c1
                target_rgb2 = c2
            else:
                target_rgb1 = self._boost_color(c1)
                target_rgb2 = self._boost_color(c2)

            state_key = (target_rgb1, target_rgb2, strobe_cut)
            if state_key == last_sent:
                continue
            last_sent = state_key

            with self.lock:
                h = self.handle
                is_on = self.enabled and self.connected

            if not h or not is_on:
                continue

            r1, g1, b1 = target_rgb1
            r2, g2, b2 = target_rgb2
            is_blackout = (max(r1, g1, b1) == 0 and max(r2, g2, b2) == 0)

            try:
                if is_blackout:
                    # 1. True blackout across all native zones: completely shut off LEDs
                    for z, pz in self.native_pkts.items():
                        pz.effect_cmd = EFFECT_OFF
                        pz.brightness = 0
                        pz.red = 0
                        pz.green = 0
                        pz.blue = 0
                        self.hid.HidD_SetFeature(h, ctypes.byref(pz), REPORT_LEN)

                    if self.apply_primary_buf:
                        self.hid.HidD_SetFeature(h, ctypes.byref(self.apply_primary_buf), REPORT_LEN)
                    if self.apply_secondary_buf:
                        self.hid.HidD_SetFeature(h, ctypes.byref(self.apply_secondary_buf), REPORT_LEN)
                else:
                    # 2. Dynamic illumination across native motherboard zones
                    if strobe_cut:
                        # Hard beat strobe flash: 100% full brightness (scale 4)
                        # Monochromatic zones (Logo 1, Bezel 2, Accent 0x10) flash in punchy OEM Blue
                        # Fan / ARGB zones reflect strobe colors with full blue power for monochromatic LEDs
                        for z, pz in self.native_pkts.items():
                            if z in MONOCHROME_BLUE_ZONES:
                                zr, zg, zb = LENOVO_LOGO_BLUE
                            elif z in (ZONE_CPU_COOLER, ZONE_FRONT_UPPER):
                                zr, zg, zb = (r1, g1, max(b1, 255))
                            else:
                                zr, zg, zb = (r2, g2, max(b2, 255))

                            pz.effect_cmd = EFFECT_STATIC
                            pz.brightness = 4  # 100% full brilliance
                            pz.speed = 1
                            pz.red = zr
                            pz.green = zg
                            pz.blue = zb
                            self.hid.HidD_SetFeature(h, ctypes.byref(pz), REPORT_LEN)
                    else:
                        # Smooth rave pulsation: scale brightness proportionally
                        max_lum = max(r1, g1, b1, r2, g2, b2)
                        scale = max_lum / 255.0
                        bright = max(1, min(4, int(scale * 4) + (1 if scale > 0.05 else 0)))

                        for z, pz in self.native_pkts.items():
                            if z in MONOCHROME_BLUE_ZONES:
                                zr = int(LENOVO_LOGO_BLUE[0] * scale)
                                zg = int(LENOVO_LOGO_BLUE[1] * scale)
                                zb = int(LENOVO_LOGO_BLUE[2] * scale)
                            elif z in (ZONE_CPU_COOLER, ZONE_FRONT_UPPER):
                                zr, zg, zb = r1, g1, b1
                            else:
                                zr, zg, zb = r2, g2, b2

                            pz.effect_cmd = EFFECT_STATIC
                            pz.brightness = bright
                            pz.speed = 1
                            pz.red = zr
                            pz.green = zg
                            pz.blue = zb
                            self.hid.HidD_SetFeature(h, ctypes.byref(pz), REPORT_LEN)

                    if self.apply_primary_buf:
                        self.hid.HidD_SetFeature(h, ctypes.byref(self.apply_primary_buf), REPORT_LEN)
                    if self.apply_secondary_buf:
                        self.hid.HidD_SetFeature(h, ctypes.byref(self.apply_secondary_buf), REPORT_LEN)

            except Exception:
                pass

    def toggle_enabled(self):
        """Toggle Lenovo Legion PC RGB lighting on/off."""
        with self.lock:
            self.enabled = not self.enabled
            is_enabled = self.enabled

        if not is_enabled:
            self._send_blackout()
        return is_enabled

    def stop(self):
        """Shutdown worker thread, blackout LEDs, and release USB handle."""
        self.running = False
        try:
            while not self.color_queue.empty():
                try:
                    self.color_queue.get_nowait()
                except queue.Empty:
                    break
        except Exception:
            pass

        self._send_blackout()

        if hasattr(self, "worker_thread") and self.worker_thread.is_alive():
            try:
                self.worker_thread.join(timeout=0.25)
            except Exception:
                pass

        with self.lock:
            if self.handle and self.kernel32:
                try:
                    self.kernel32.CloseHandle(self.handle)
                except Exception:
                    pass
                self.handle = None
                self.connected = False


if __name__ == "__main__":
    print("Testing Lenovo Legion Desktop RGB Controller...")
    mgr = LenovoLegionManager()
    print(f"Connected: {mgr.connected} | Device: {mgr.device_name}")

    if mgr.connected:
        print("\nSimulating beat flash cycles (Colored fans + Blue Logo / Blackout cuts)...")
        test_sequence = [
            ((255, 0, 50), (0, 220, 255)),   # Red fans, Cyan fans, Blue logo
            ((0, 255, 100), (255, 180, 0)),  # Green fans, Gold fans, Blue logo
            ((255, 0, 255), (0, 150, 255)),  # Magenta fans, Ice Blue fans, Blue logo
        ]
        for idx, (c1, c2) in enumerate(test_sequence, 1):
            print(f"Beat {idx}: FLASH -> Fans {c1} & {c2}, Logo {LENOVO_LOGO_BLUE}")
            mgr.set_colors(c1, c2, strobe_cut=True)
            time.sleep(0.12)
            print(f"Beat {idx}: BLACKOUT -> True Blackout (0, 0, 0)")
            mgr.set_colors((0, 0, 0), (0, 0, 0), strobe_cut=True)
            time.sleep(0.18)

        print("\nTesting blackout and teardown...")
        mgr.stop()
        print("Teardown complete. All LEDs dark.")
    else:
        print("No Lenovo Legion RGB hardware detected.")
