"""
Lenovo Legion Gaming Desktop RGB Synchronization.
Supports Lenovo Legion PCs (e.g. Legion T5 28IMB05, T730, T530, etc.)
equipped with ITE 8297 / IT8297BX USB RGB controllers (VID 0x17EF / 0x048D, PID 0xC955 / 0x8297)
via direct Win32 USB HID Feature Reports (zero external dependencies).
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

# Commands
CMD_INIT = 0x60
CMD_APPLY = 0x28
EFFECT_OFF = 0
EFFECT_STATIC = 1


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

    class PktEffect(Structure):
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

        # Pre-allocated packets for 8 hardware channels (0x20..0x27)
        self.packets = []
        self.cbuf_packets = []
        self.exec_buf = None
        self.cbuf_exec = None

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
        init_buf = bytearray(64)
        init_buf[0] = REPORT_ID
        init_buf[1] = CMD_INIT
        self.hid.HidD_SetFeature(self.handle, (ctypes.c_char * 64).from_buffer(init_buf), 64)

        get_buf = bytearray(64)
        get_buf[0] = REPORT_ID
        if self.hid.HidD_GetFeature(self.handle, (ctypes.c_char * 64).from_buffer(get_buf), 64):
            try:
                null = get_buf.index(0, 12)
                dev_str = get_buf[12:null].decode("ascii", errors="replace").strip()
                if dev_str:
                    self.device_name = f"Lenovo PC ({dev_str})"
            except Exception:
                pass

        # Pre-allocate 8 zone packets (headers 0x20..0x27)
        self.packets = []
        self.cbuf_packets = []
        for i in range(8):
            pkt = PktEffect()
            pkt.report_id = REPORT_ID
            pkt.header = 0x20 + i
            pkt.zone0 = (1 << i)
            pkt.zone1 = 0
            pkt.reserved0 = 0
            pkt.effect_type = EFFECT_OFF
            pkt.max_brightness = 0
            pkt.min_brightness = 0
            pkt.color0 = 0
            pkt.color1 = 0
            pkt.period0 = 0
            pkt.period1 = 0
            pkt.period2 = 0
            pkt.period3 = 0
            pkt.param0 = 7
            pkt.param1 = 1
            pkt.param2 = 0
            pkt.param3 = 0
            cbuf = (ctypes.c_char * 64).from_buffer(pkt)
            self.packets.append(pkt)
            self.cbuf_packets.append(cbuf)

        # Pre-allocate execute buffer
        self.exec_buf = bytearray(64)
        self.exec_buf[0] = REPORT_ID
        self.exec_buf[1] = CMD_APPLY
        self.exec_buf[2] = 0xFF
        self.cbuf_exec = (ctypes.c_char * 64).from_buffer(self.exec_buf)

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

    def set_colors(self, rgb, strobe_cut=True):
        """Push target colors to Lenovo Legion PC lighting (non-blocking)."""
        if not self.enabled or not self.connected:
            return

        c = tuple(max(0, min(255, int(v))) for v in rgb[:3])

        # Drain backlog so queue only ever holds the newest frame
        try:
            while True:
                self.color_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            self.color_queue.put_nowait((c, strobe_cut))
        except queue.Full:
            pass

    def _worker_loop(self):
        """Dedicated background worker thread writing to the USB HID controller."""
        last_sent = (0, 0, 0)

        while self.running:
            try:
                item = self.color_queue.get(timeout=0.030)
            except queue.Empty:
                continue

            color, strobe_cut = item

            if strobe_cut:
                target_rgb = color
            else:
                target_rgb = self._boost_color(color)

            if target_rgb == last_sent:
                continue
            last_sent = target_rgb

            with self.lock:
                h = self.handle
                is_on = self.enabled and self.connected

            if not h or not is_on:
                continue

            r, g, b = target_rgb
            is_blackout = (r == 0 and g == 0 and b == 0)

            # Packed RGB integer
            col_int = (r << 16) | (g << 8) | b
            eff_type = EFFECT_OFF if is_blackout else EFFECT_STATIC
            bright = 0 if is_blackout else 100

            try:
                # Update all 8 motherboard / fan / cooler / strip headers
                for i in range(8):
                    pkt = self.packets[i]
                    pkt.effect_type = eff_type
                    pkt.max_brightness = bright
                    pkt.color0 = 0 if is_blackout else col_int
                    self.hid.HidD_SetFeature(h, self.cbuf_packets[i], 64)

                # Commit changes instantly
                self.hid.HidD_SetFeature(h, self.cbuf_exec, 64)
            except Exception:
                pass

    def toggle_enabled(self):
        """Toggle Lenovo Legion PC RGB lighting on/off."""
        self.enabled = not self.enabled
        if not self.enabled:
            self.set_colors((0, 0, 0))
        return self.enabled

    def stop(self):
        """Shutdown worker thread, blackout LEDs, and release USB handle."""
        self.running = False
        try:
            self.set_colors((0, 0, 0))
            time.sleep(0.04)
        except Exception:
            pass

        with self.lock:
            if self.handle and self.hid:
                try:
                    for i in range(8):
                        if self.packets and self.cbuf_packets:
                            pkt = self.packets[i]
                            pkt.effect_type = EFFECT_OFF
                            pkt.max_brightness = 0
                            pkt.color0 = 0
                            self.hid.HidD_SetFeature(self.handle, self.cbuf_packets[i], 64)
                    if self.cbuf_exec:
                        self.hid.HidD_SetFeature(self.handle, self.cbuf_exec, 64)
                except Exception:
                    pass

            if self.handle and self.kernel32:
                try:
                    self.kernel32.CloseHandle(self.handle)
                except Exception:
                    pass
                self.handle = None
                self.connected = False
