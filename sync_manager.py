"""
Multi-computer Bluetooth and Network synchronization manager.
Provides Host (Server) and Client roles to synchronize screen strobes
across multiple computers over Bluetooth RFCOMM and Local Network.
"""

import sys
import time
import json
import socket
import select
import threading
import subprocess
import re
import numpy as np

# Default ports and channels
BT_RFCOMM_CHANNEL = 4
TCP_PORT = 42424
UDP_BEACON_PORT = 42425

# Roles
ROLE_STANDALONE = "Standalone"
ROLE_HOST = "Host"
ROLE_CLIENT = "Client"


class BluetoothScanner:
    """Discovers nearby/remembered Bluetooth devices on Windows."""

    def __init__(self):
        self.devices = []
        self.is_scanning = False
        self.lock = threading.Lock()

    def start_scan(self):
        if self.is_scanning:
            return
        self.is_scanning = True
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        found = []
        try:
            if sys.platform == "win32":
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName, InstanceId",
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                for line in res.stdout.splitlines():
                    m = re.search(r"DEV_([0-9A-Fa-f]{12})", line)
                    if m:
                        raw_mac = m.group(1).upper()
                        formatted_mac = ":".join(raw_mac[i:i + 2] for i in range(0, 12, 2))
                        raw_name = line[:m.start()].strip()
                        clean_name = raw_name.split("BTHENUM")[0].strip()
                        if not clean_name:
                            clean_name = "Bluetooth Host"
                        if not any(d["mac"] == formatted_mac for d in found):
                            found.append({
                                "name": clean_name,
                                "mac": formatted_mac,
                                "type": "Bluetooth",
                            })
            elif sys.platform == "darwin":
                cmd = ["system_profiler", "-json", "SPBluetoothDataType"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout)
                    for item in data.get("SPBluetoothDataType", []):
                        for section in ("device_connected", "device_not_connected"):
                            for dev_dict in item.get(section, []):
                                for name, props in dev_dict.items():
                                    addr = props.get("device_address")
                                    if addr and not any(d["mac"] == addr for d in found):
                                        found.append({
                                            "name": name,
                                            "mac": addr,
                                            "type": "Bluetooth",
                                        })
        except Exception:
            pass

        with self.lock:
            self.devices = found
            self.is_scanning = False

    def get_devices(self):
        with self.lock:
            return list(self.devices)


class SyncManager:
    """Coordinates multi-computer synchronization over Bluetooth and LAN."""

    def __init__(self):
        self.role = ROLE_STANDALONE

        # Ports and channels
        self.bt_channel = BT_RFCOMM_CHANNEL
        self.tcp_port = TCP_PORT
        self.udp_beacon_port = UDP_BEACON_PORT

        # Local system info
        self.hostname = socket.gethostname()
        try:
            self.local_ip = socket.gethostbyname(self.hostname)
        except Exception:
            self.local_ip = "127.0.0.1"

        self.local_bt_mac = self._detect_local_bt_mac()

        # Scanner & Auto-Discovery
        self.bt_scanner = BluetoothScanner()
        self.discovered_hosts = []
        self.lock = threading.Lock()

        # Host state
        self.host_running = False
        self.host_bt_sock = None
        self.host_tcp_sock = None
        self.connected_clients = []
        self.client_count = 0

        # Client state
        self.client_running = False
        self.client_sock = None
        self.client_status = "Disconnected"
        self.client_connected_host = None
        self.client_latency_ms = 0.0

        # Received remote beat state
        self.incoming_beat_queue = []
        self.threads = []

    def _detect_local_bt_mac(self):
        """Detect local Bluetooth MAC address using RFCOMM bind or system profiler."""
        if hasattr(socket, "AF_BLUETOOTH") and hasattr(socket, "BTPROTO_RFCOMM"):
            try:
                s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                s.bind((socket.BDADDR_ANY, BT_RFCOMM_CHANNEL))
                mac = s.getsockname()[0]
                s.close()
                return mac
            except Exception:
                pass

        if sys.platform == "darwin":
            try:
                cmd = ["system_profiler", "-json", "SPBluetoothDataType"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout)
                    for item in data.get("SPBluetoothDataType", []):
                        addr = item.get("controller_properties", {}).get("controller_address")
                        if addr:
                            return addr
            except Exception:
                pass

        return "Bluetooth Available"

    def set_role(self, new_role):
        """Switch sync role between Standalone, Host, and Client."""
        if new_role == self.role:
            return
        self.stop()
        self.role = new_role
        if self.role == ROLE_HOST:
            self.start_host()
        elif self.role == ROLE_CLIENT:
            self.start_client_search()

    def start_host(self):
        """Start Bluetooth RFCOMM and TCP servers to broadcast beats."""
        self.role = ROLE_HOST
        self.host_running = True
        self.connected_clients = []
        self.client_count = 0

        # 1. Start Bluetooth RFCOMM Server if supported on this OS
        if hasattr(socket, "AF_BLUETOOTH") and hasattr(socket, "BTPROTO_RFCOMM"):
            try:
                self.host_bt_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                bound = False
                for ch in [BT_RFCOMM_CHANNEL, 1, 2, 3, 5, 6, 7]:
                    try:
                        self.host_bt_sock.bind((socket.BDADDR_ANY, ch))
                        self.bt_channel = ch
                        bound = True
                        break
                    except Exception:
                        continue
                if bound:
                    self.host_bt_sock.listen(5)
                    t_bt = threading.Thread(target=self._host_bt_accept_worker, daemon=True)
                    t_bt.start()
                    self.threads.append(t_bt)
                else:
                    self.host_bt_sock.close()
                    self.host_bt_sock = None
            except Exception:
                self.host_bt_sock = None
        else:
            self.host_bt_sock = None

        # 2. Start TCP Server (for LAN and fallback)
        try:
            self.host_tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.host_tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.host_tcp_sock.bind(("0.0.0.0", self.tcp_port))
            self.host_tcp_sock.listen(5)
            t_tcp = threading.Thread(target=self._host_tcp_accept_worker, daemon=True)
            t_tcp.start()
            self.threads.append(t_tcp)
        except Exception:
            self.host_tcp_sock = None

        # 3. Start UDP Beacon Broadcaster
        t_beacon = threading.Thread(target=self._host_beacon_worker, daemon=True)
        t_beacon.start()
        self.threads.append(t_beacon)

    def _host_bt_accept_worker(self):
        while self.host_running and self.host_bt_sock:
            try:
                conn, addr = self.host_bt_sock.accept()
                try:
                    conn.setblocking(False)
                except Exception:
                    pass
                with self.lock:
                    self.connected_clients.append(conn)
                    self.client_count = len(self.connected_clients)
                t_cli = threading.Thread(target=self._host_client_reader_worker, args=(conn,), daemon=True)
                t_cli.start()
                self.threads.append(t_cli)
            except Exception:
                break

    def _host_tcp_accept_worker(self):
        while self.host_running and self.host_tcp_sock:
            try:
                conn, addr = self.host_tcp_sock.accept()
                try:
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    conn.setblocking(False)
                except Exception:
                    pass
                with self.lock:
                    self.connected_clients.append(conn)
                    self.client_count = len(self.connected_clients)
                t_cli = threading.Thread(target=self._host_client_reader_worker, args=(conn,), daemon=True)
                t_cli.start()
                self.threads.append(t_cli)
            except Exception:
                break

    def _host_client_reader_worker(self, client_sock):
        """Read incoming ping/pong requests and detect client disconnection."""
        buf = b""
        while self.host_running:
            try:
                r, _, _ = select.select([client_sock], [], [], 2.0)
                if not r:
                    continue
                data = client_sock.recv(1024)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        try:
                            pkt = json.loads(line.decode("utf-8"))
                            if pkt.get("type") == "PING":
                                pong = json.dumps({"type": "PONG", "t": pkt.get("t", 0.0)}).encode("utf-8") + b"\n"
                                client_sock.sendall(pong)
                        except Exception:
                            pass
            except Exception:
                break

        with self.lock:
            if client_sock in self.connected_clients:
                self.connected_clients.remove(client_sock)
                self.client_count = len(self.connected_clients)
        try:
            client_sock.close()
        except Exception:
            pass

    def _host_beacon_worker(self):
        """Periodically broadcast UDP discovery packets on local subnet."""
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass

        while self.host_running:
            try:
                beacon_data = json.dumps({
                    "type": "BEAT_STROBE_HOST",
                    "hostname": self.hostname,
                    "bt_mac": self.local_bt_mac,
                    "ip": self.local_ip,
                    "port": self.tcp_port,
                    "rfcomm": self.bt_channel,
                }).encode("utf-8")
                udp_sock.sendto(beacon_data, ("<broadcast>", self.udp_beacon_port))
            except Exception:
                pass
            time.sleep(1.5)
        udp_sock.close()

    def broadcast_beat(self, packet_dict):
        """Broadcast frame synchronization packet to all connected clients."""
        if not self.host_running or not self.connected_clients:
            return

        try:
            if "timestamp" not in packet_dict:
                packet_dict["timestamp"] = time.time()

            # Clean convert numpy arrays, floats, integers
            cleaned = {}
            for k, v in packet_dict.items():
                if hasattr(v, "tolist"):
                    v = v.tolist()
                if isinstance(v, (np.floating, float)):
                    cleaned[k] = round(float(v), 3)
                elif isinstance(v, (np.integer, int)):
                    cleaned[k] = int(v)
                elif isinstance(v, (list, tuple)):
                    cleaned[k] = [
                        int(x) if isinstance(x, (np.integer, int))
                        else round(float(x), 3) if isinstance(x, (np.floating, float))
                        else x for x in v
                    ]
                else:
                    cleaned[k] = v

            raw_msg = json.dumps(cleaned).encode("utf-8") + b"\n"

            dead = []
            with self.lock:
                for client in self.connected_clients:
                    try:
                        client.sendall(raw_msg)
                    except (BlockingIOError, socket.error):
                        # Non-blocking buffer full - skip frame to prevent render stutter
                        pass
                    except Exception:
                        dead.append(client)
                for d in dead:
                    if d in self.connected_clients:
                        self.connected_clients.remove(d)
                self.client_count = len(self.connected_clients)
        except Exception:
            pass

    def start_client_search(self):
        """Start searching for Bluetooth devices and LAN Host beacons."""
        self.role = ROLE_CLIENT
        self.client_running = True
        self.client_status = "Searching for Hosts..."
        self.discovered_hosts = []

        self.bt_scanner.start_scan()

        t_listener = threading.Thread(target=self._client_beacon_listener, daemon=True)
        t_listener.start()
        self.threads.append(t_listener)

    def _client_beacon_listener(self):
        """Listen for UDP beacons from Hosts."""
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.bind(("", self.udp_beacon_port))
            udp.settimeout(1.0)
        except Exception:
            return

        while self.client_running and self.client_sock is None:
            try:
                data, addr = udp.recvfrom(2048)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("type") == "BEAT_STROBE_HOST":
                    host_info = {
                        "name": msg.get("hostname", "Host PC"),
                        "bt_mac": msg.get("bt_mac", ""),
                        "ip": addr[0],
                        "port": msg.get("port", self.tcp_port),
                        "rfcomm": msg.get("rfcomm", self.bt_channel),
                        "type": "LAN / Bluetooth",
                    }
                    with self.lock:
                        if not any(h["ip"] == host_info["ip"] for h in self.discovered_hosts):
                            self.discovered_hosts.append(host_info)
            except socket.timeout:
                continue
            except Exception:
                pass
        udp.close()

    def get_all_discovered_hosts(self):
        """Return combined list of discovered Bluetooth devices and LAN hosts."""
        hosts = []
        with self.lock:
            for h in self.discovered_hosts:
                hosts.append({
                    "name": f"⚡ {h['name']}",
                    "address": h["ip"],
                    "port": h["port"],
                    "bt_mac": h["bt_mac"],
                    "type": "Network Host",
                })
        bt_devs = self.bt_scanner.get_devices()
        for b in bt_devs:
            hosts.append({
                "name": f"🔵 {b['name']}",
                "address": b["mac"],
                "port": self.bt_channel,
                "bt_mac": b["mac"],
                "type": "Bluetooth Device",
            })
        return hosts

    def connect_to_host(self, host_entry):
        self.role = ROLE_CLIENT
        self.client_running = True
        threading.Thread(target=self._client_connect_worker, args=(host_entry,), daemon=True).start()

    def _client_connect_worker(self, host_entry):
        self.role = ROLE_CLIENT
        self.client_running = True
        self.client_status = f"Connecting to {host_entry['name']}..."
        self.disconnect_client()

        addr_type = host_entry.get("type", "")
        sock = None

        if "Bluetooth" in addr_type:
            if not hasattr(socket, "AF_BLUETOOTH"):
                self.client_status = "Bluetooth sockets unavailable on macOS (use LAN/WiFi)"
                return
            try:
                sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                sock.settimeout(8.0)
                mac = host_entry.get("bt_mac") or host_entry.get("address")
                channel = host_entry.get("port", self.bt_channel)
                sock.connect((mac, channel))
            except Exception as e:
                self.client_status = f"Bluetooth Error: {str(e)[:30]}"
                if sock:
                    sock.close()
                return
        else:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(6.0)
                ip = host_entry.get("address")
                port = host_entry.get("port", self.tcp_port)
                sock.connect((ip, port))
                try:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception:
                    pass
            except Exception as e:
                self.client_status = f"Network Error: {str(e)[:30]}"
                if sock:
                    sock.close()
                return

        sock.settimeout(None)
        self.client_sock = sock
        self.client_connected_host = host_entry["name"]
        self.client_status = f"Connected to {host_entry['name']}"

        threading.Thread(target=self._client_reader_worker, daemon=True).start()

    def _client_reader_worker(self):
        buf = b""
        last_ping_time = time.time()
        while self.client_running and self.client_sock:
            try:
                # Periodic Ping to Host for exact RTT calculation
                now = time.time()
                if now - last_ping_time >= 1.5:
                    last_ping_time = now
                    try:
                        ping_msg = json.dumps({"type": "PING", "t": now}).encode("utf-8") + b"\n"
                        self.client_sock.sendall(ping_msg)
                    except Exception:
                        pass

                data = self.client_sock.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        packet = json.loads(line.decode("utf-8"))
                        if packet.get("type") == "PONG":
                            recv_t = time.time()
                            sent_t = packet.get("t", recv_t)
                            self.client_latency_ms = max(0.5, (recv_t - sent_t) * 500)
                        else:
                            with self.lock:
                                # Bound queue so client always tracks live host frame
                                if len(self.incoming_beat_queue) > 6:
                                    self.incoming_beat_queue = self.incoming_beat_queue[-3:]
                                self.incoming_beat_queue.append(packet)
            except Exception:
                break

        self.client_status = "Disconnected from Host"
        self.disconnect_client()

    def get_incoming_beats(self):
        with self.lock:
            beats = list(self.incoming_beat_queue)
            self.incoming_beat_queue.clear()
            return beats

    def disconnect_client(self):
        if self.client_sock:
            try:
                self.client_sock.close()
            except Exception:
                pass
            self.client_sock = None
        self.client_connected_host = None

    def stop(self):
        """Stop all host and client network services."""
        self.host_running = False
        self.client_running = False

        if self.host_bt_sock:
            try:
                self.host_bt_sock.close()
            except Exception:
                pass
            self.host_bt_sock = None

        if self.host_tcp_sock:
            try:
                self.host_tcp_sock.close()
            except Exception:
                pass
            self.host_tcp_sock = None

        with self.lock:
            for c in self.connected_clients:
                try:
                    c.close()
                except Exception:
                    pass
            self.connected_clients.clear()
            self.client_count = 0

        self.disconnect_client()
