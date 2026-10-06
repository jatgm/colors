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
CHAR_WRITE_UUID = "0000ffd9-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY_UUID = "0000ffd4-0000-1000-8000-00805f9b34fb"

# Protocol command packets
CMD_TURN_ON = bytearray([0xCC, 0x23, 0x33])
CMD_TURN_OFF = bytearray([0xCC, 0x24, 0x33])

def make_color_packet(r: int, g: int, b: int) -> bytearray:
    """Construct Triones/HappyLighting RGB packet: 56 R G B 00 F0 AA."""
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return bytearray([0x56, r, g, b, 0x00, 0xF0, 0xAA])


class HappyLightingManager:
    """Manages asynchronous BLE connection and packet dispatch for room LED lights."""

    def __init__(self, target_address: str = "36:46:40:25:08:2F", auto_discover: bool = True):
        self.target_address = target_address
        self.auto_discover = auto_discover
        self.enabled = True
        self.connected = False
        self.device_name = "Room LED"
        self.color_queue = queue.Queue(maxsize=2)
        self.running = True
        self.lock = threading.Lock()

        if not BLEAK_AVAILABLE:
            _LOGGER.warning("bleak is not installed. HappyLighting control disabled.")
            self.enabled = False
            return

        self._thread = threading.Thread(target=self._worker_thread_main, daemon=True, name="HappyLightingWorker")
        self._thread.start()

    def set_colors(self, rgb, strobe_cut=True):
        """Push target RGB color from visualizer to room light (non-blocking, freshest frame only)."""
        if not self.enabled or not self.running:
            return

        c = tuple(max(0, min(255, int(v))) for v in rgb[:3])

        # Drain previous queued item to ensure zero latency
        try:
            while True:
                self.color_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            self.color_queue.put_nowait((c, strobe_cut))
        except queue.Full:
            pass

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

    def _worker_thread_main(self):
        """Entry point for background daemon thread running an asyncio event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_connect_and_stream())
        finally:
            loop.close()

    async def _async_connect_and_stream(self):
        """Persistent connection loop with automatic reconnection and queue polling."""
        last_sent_color = (0, 0, 0)
        last_send_time = 0.0

        while self.running:
            device = None

            # 1. Locate device by known address first (fastest)
            if self.target_address:
                try:
                    device = await BleakScanner.find_device_by_address(self.target_address, timeout=4.0)
                except Exception:
                    pass

            # 2. If not found by address, scan for HappyLighting / QHM / ST51 broadcast names
            if not device and self.auto_discover and self.running:
                try:
                    devs = await BleakScanner.discover(timeout=5.0)
                    for d in devs:
                        n = (d.name or "").upper()
                        if any(k in n for k in ("QHM", "ST51", "HAPPY", "TRIONES", "LEDBLE")):
                            device = d
                            self.target_address = d.address
                            break
                except Exception:
                    pass

            if not device:
                # Retry in 2 seconds
                await asyncio.sleep(2.0)
                continue

            with self.lock:
                self.device_name = device.name or "Room Lights (QHM)"

            # 3. Connect to BLE device
            try:
                async with BleakClient(device, timeout=12.0) as client:
                    with self.lock:
                        self.connected = True

                    # Send turn-on packet
                    try:
                        await client.write_gatt_char(CHAR_WRITE_UUID, CMD_TURN_ON, response=False)
                    except Exception:
                        pass

                    await asyncio.sleep(0.08)
                    last_sent_color = (0, 0, 0)

                    # 4. Active streaming loop
                    while self.running and client.is_connected:
                        try:
                            # Pull from queue without blocking the event loop
                            try:
                                item = self.color_queue.get_nowait()
                            except queue.Empty:
                                await asyncio.sleep(0.008)
                                continue

                            color, strobe_cut = item
                            now = time.perf_counter()

                            # In strobe mode: only send when color state changes (edge triggered)
                            # In smooth mode: rate-limit to ~25Hz to avoid saturating BLE bandwidth
                            if strobe_cut:
                                if color == last_sent_color:
                                    continue
                            else:
                                if color == last_sent_color or (now - last_send_time < 0.040):
                                    continue

                            last_sent_color = color
                            last_send_time = now

                            pkt = make_color_packet(*color)
                            await client.write_gatt_char(CHAR_WRITE_UUID, pkt, response=False)

                        except Exception:
                            break

            except Exception:
                pass

            with self.lock:
                self.connected = False

            if self.running:
                await asyncio.sleep(1.5)
