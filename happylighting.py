"""
HappyLighting / QHM Bluetooth Low Energy (BLE) Room Lights Manager.
Provides non-blocking, zero-latency synchronization between the Beat Strobe
Visualizer Engine and HappyLighting-compatible Bluetooth LED strip lights
(KSIPZE ST51_K2430, QHM-S082, Triones controllers).
"""

import asyncio
import logging
import queue
import threading
import time

try:
    from bleak import BleakClient, BleakScanner
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False

_LOGGER = logging.getLogger("HappyLighting")

# HappyLighting / QHM / Triones GATT Characteristic UUIDs
CHAR_TRIONES_WRITE_UUID = "0000ffd9-0000-1000-8000-00805f9b34fb"
CHAR_TRIONES_NOTIFY_UUID = "0000ffd4-0000-1000-8000-00805f9b34fb"
CHAR_WRITE_UUID = CHAR_TRIONES_WRITE_UUID  # Backwards compatibility

# Govee H5082 / H61xx / ihoment GATT Characteristic UUIDs
CHAR_GOVEE_WRITE_UUID = "00010203-0405-0607-0809-0a0b0c0d2b11"

# Protocol command packets
CMD_TURN_ON = bytearray([0xCC, 0x23, 0x33])
CMD_TURN_OFF = bytearray([0xCC, 0x24, 0x33])

def make_color_packet(r: int, g: int, b: int) -> bytearray:
    """Construct Triones/HappyLighting RGB packet: 56 R G B 00 F0 AA."""
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return bytearray([0x56, r, g, b, 0x00, 0xF0, 0xAA])

def make_govee_color_packet(r: int, g: int, b: int) -> bytearray:
    """Construct Govee H5082/H61xx 20-byte RGB packet with XOR checksum."""
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    pkt = [0x33, 0x05, 0x02, r, g, b]
    pkt += [0] * (19 - len(pkt))
    checksum = 0
    for x in pkt:
        checksum ^= x
    pkt.append(checksum)
    return bytearray(pkt)

def make_govee_power_packet(on: bool = True) -> bytearray:
    """Construct Govee power on/off 20-byte packet."""
    pkt = [0x33, 0x01, 0x01 if on else 0x00]
    pkt += [0] * (19 - len(pkt))
    checksum = 0
    for x in pkt:
        checksum ^= x
    pkt.append(checksum)
    return bytearray(pkt)


class HappyLightingManager:
    """Manages asynchronous BLE connection and packet dispatch for room LED lights."""

    def __init__(self, target_address: str = "36:46:40:25:08:2F", auto_discover: bool = True):
        self.target_address = target_address
        self.auto_discover = auto_discover
        self.enabled = True
        self.connected = False
        self.device_name = "Room LED"
        self.color_queue = queue.Queue(maxsize=16)
        self.running = True
        self.lock = threading.Lock()

        # State tracking for instant event dispatch and guaranteed strobe edge triggers
        self._target_color = (0, 0, 0)
        self._target_strobe = True
        self._flash_trigger_id = 0
        self._last_cmd_color = (0, 0, 0)
        self._last_cmd_strobe = True
        self._last_input_flash_id = -1
        self._contrast_toggle = 0

        # Async event loop and trigger event reference
        self._loop = None
        self._event = None

        if not BLEAK_AVAILABLE:
            _LOGGER.warning("bleak is not installed. HappyLighting control disabled.")
            self.enabled = False
            return

        self._thread = threading.Thread(target=self._worker_thread_main, daemon=True, name="HappyLightingWorker")
        self._thread.start()

    def set_colors(self, rgb, secondary_rgb=None, strobe_cut=True, flash_id=None):
        """Push target RGB color from visualizer to room light (non-blocking, freshest frame only).
        Supports dual-zone colors for multi-monitor alternating sync: dynamically tracks
        the active flashing side with zero latency and alternates saturated contrast colors.
        """
        if not self.enabled or not self.running:
            return

        # Backward compatibility if secondary_rgb was passed as a boolean (strobe_cut)
        if isinstance(secondary_rgb, bool):
            strobe_cut = secondary_rgb
            secondary_rgb = None

        # Multi-monitor / alternating dual-scheme support: select active flashing channel
        if secondary_rgb is not None:
            max_left = max(rgb[:3])
            max_right = max(secondary_rgb[:3])
            if max_left > 0 and max_right == 0:
                active_rgb = rgb
            elif max_right > 0 and max_left == 0:
                active_rgb = secondary_rgb
            elif max_right > max_left:
                active_rgb = secondary_rgb
            elif max_left > max_right:
                active_rgb = rgb
            else:
                # Both non-zero and equal (e.g. dual contrast mode where both monitors flash at max 255)
                # Alternate between channels across beats so both screen colors are visible on the strip
                if rgb != secondary_rgb and strobe_cut:
                    self._contrast_toggle = 1 - getattr(self, "_contrast_toggle", 0)
                    active_rgb = secondary_rgb if self._contrast_toggle == 1 else rgb
                else:
                    active_rgb = rgb
        else:
            active_rgb = rgb

        c = tuple(max(0, min(255, int(v))) for v in active_rgb[:3])

        # Perceptual vibrance and forward-voltage boost for smooth/ambient LED lighting
        if not strobe_cut and max(c) > 0:
            max_c = max(c)
            norm = max_c / 255.0
            target_max = 60 + int(norm * 195)
            scale = target_max / max(1, max_c)
            c = (min(255, int(c[0] * scale)), min(255, int(c[1] * scale)), min(255, int(c[2] * scale)))

        with self.lock:
            # Trigger ID edge tracking
            is_new_flash = False
            if flash_id is not None and flash_id != getattr(self, "_last_input_flash_id", -1):
                self._last_input_flash_id = flash_id
                if c != (0, 0, 0):
                    is_new_flash = True
            elif c != (0, 0, 0) and self._last_cmd_color == (0, 0, 0):
                is_new_flash = True
            elif c != (0, 0, 0) and strobe_cut and c != self._last_cmd_color:
                is_new_flash = True
            elif c != (0, 0, 0) and strobe_cut and not getattr(self, "_last_cmd_strobe", True):
                is_new_flash = True

            if is_new_flash:
                self._flash_trigger_id += 1

            self._last_cmd_color = c
            self._last_cmd_strobe = strobe_cut
            self._target_color = c
            self._target_strobe = strobe_cut

        # Keep color_queue populated for backwards compatibility with test assertions
        try:
            while not self.color_queue.empty():
                self.color_queue.get_nowait()
        except Exception:
            pass
        try:
            self.color_queue.put_nowait((c, strobe_cut))
        except Exception:
            pass

        # Zero-latency event wake-up to eliminate polling delay
        if self._loop and self._event and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._event.set)

    def toggle_enabled(self):
        """Toggle room lighting on or off."""
        self.enabled = not self.enabled
        if not self.enabled:
            # Cut to black
            self.set_colors((0, 0, 0), strobe_cut=True)
        return self.enabled

    def stop(self):
        """Shut down background thread and cut LEDs to black."""
        self.running = False
        try:
            self.set_colors((0, 0, 0), strobe_cut=True)
        except Exception:
            pass
        if self._loop and self._event and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._event.set)

    def _worker_thread_main(self):
        """Entry point for background daemon thread running an asyncio event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._async_connect_and_stream())
        finally:
            loop.close()

    async def _async_connect_and_stream(self):
        """Persistent connection loop targeting HappyLighting / QHM / Triones / ELK room LED strips."""
        self._event = asyncio.Event()

        while self.running:
            device = None

            # 1. Locate primary room device by known address first (fastest)
            if self.target_address:
                try:
                    device = await BleakScanner.find_device_by_address(self.target_address, timeout=4.0)
                except Exception:
                    pass

            # 2. If not found by address, scan for HappyLighting / QHM / ST51 / Triones / ELK broadcast names
            if not device and self.auto_discover and self.running:
                try:
                    devs = await BleakScanner.discover(timeout=4.0, return_adv=True)
                    candidates = []
                    for d, adv in devs.values():
                        n = (d.name or "").upper()
                        if any(k in n for k in ("QHM", "ST51", "HAPPY", "TRIONES", "LEDBLE", "ELK-BLEDOM", "MELK")):
                            candidates.append((adv.rssi, d))

                    if candidates:
                        candidates.sort(key=lambda x: x[0], reverse=True)
                        _, device = candidates[0]
                except Exception:
                    pass

            if not device:
                await asyncio.sleep(2.0)
                continue

            with self.lock:
                self.device_name = device.name or "Room LED (QHM)"

            # 3. Connect to BLE device
            try:
                async with BleakClient(device, timeout=10.0) as client:
                    with self.lock:
                        self.connected = True

                    # Detect characteristic: Triones/QHM (ffd9) vs ELK/MELK (fff3)
                    write_uuid = CHAR_TRIONES_WRITE_UUID
                    make_pkt = make_color_packet
                    turn_on_cmd = CMD_TURN_ON

                    for s in client.services:
                        for c in s.characteristics:
                            u = c.uuid.lower()
                            if "ffd9" in u:
                                write_uuid = c.uuid
                                make_pkt = make_color_packet
                                turn_on_cmd = CMD_TURN_ON
                                break
                            elif "fff3" in u:
                                write_uuid = c.uuid
                                make_pkt = lambda r, g, b: bytearray([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])
                                turn_on_cmd = bytearray([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF])
                                break

                    try:
                        await client.write_gatt_char(write_uuid, turn_on_cmd, response=False)
                    except Exception:
                        pass

                    await asyncio.sleep(0.04)
                    last_sent_color = (0, 0, 0)
                    last_handled_flash_id = -1
                    last_write_time = time.perf_counter()
                    flash_end_time = 0.0

                    # 4. Active streaming loop
                    while self.running and client.is_connected:
                        now = time.perf_counter()

                        # Determine timeout until next strobe cut or event
                        wait_timeout = 0.050
                        if flash_end_time > now:
                            wait_timeout = max(0.002, flash_end_time - now)

                        try:
                            await asyncio.wait_for(self._event.wait(), timeout=wait_timeout)
                            self._event.clear()
                        except asyncio.TimeoutError:
                            pass

                        if not self.running or not client.is_connected:
                            break

                        now = time.perf_counter()

                        with self.lock:
                            target_color = self._target_color
                            target_strobe = self._target_strobe
                            flash_id = self._flash_trigger_id

                        to_send = None

                        # Check 1: New beat flash strike triggered (zero latency)
                        if target_strobe and target_color != (0, 0, 0) and flash_id != last_handled_flash_id:
                            to_send = target_color
                            last_handled_flash_id = flash_id
                            flash_end_time = now + 0.080  # 80ms peak strobe duration matches screen

                        # Check 2: Active strobe flash window expired -> cut to blackout
                        elif target_strobe and flash_end_time > 0 and now >= flash_end_time:
                            if last_sent_color != (0, 0, 0):
                                to_send = (0, 0, 0)
                            flash_end_time = 0.0

                        # Check 3: Explicit blackout command received from visualizer
                        elif target_color == (0, 0, 0) and last_sent_color != (0, 0, 0):
                            to_send = (0, 0, 0)
                            flash_end_time = 0.0

                        # Check 4: Smooth rave mode or ambient color returned between beat flashes
                        elif not target_strobe:
                            if target_color != last_sent_color and (now - last_write_time >= 0.025):
                                to_send = target_color
                                flash_end_time = 0.0

                        if to_send is not None:
                            # BLE HCI pacing: prevent packet collisions / buffer overflow
                            elapsed = now - last_write_time
                            if elapsed < 0.012:
                                await asyncio.sleep(0.012 - elapsed)

                            pkt = make_pkt(to_send[0], to_send[1], to_send[2])
                            try:
                                await client.write_gatt_char(write_uuid, pkt, response=False)
                                last_sent_color = to_send
                                last_write_time = time.perf_counter()
                            except Exception as write_err:
                                _LOGGER.debug("BLE write transient error: %s", write_err)
                                if not client.is_connected:
                                    break
                                await asyncio.sleep(0.020)

            except Exception as conn_err:
                _LOGGER.debug("BLE connection loop error: %s", conn_err)

            with self.lock:
                self.connected = False

            if self.running:
                await asyncio.sleep(1.5)
