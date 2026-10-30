"""Pure-Python client for the ZYC Simpo 5000 WiFi dongle local TCP protocol.

Reverse-engineered proprietary protocol on port 8888 (no external deps).

  Request : F2 03 <addr> <cmd> 00 01 <len16_BE>  + CRC16/Modbus (LE on wire)
  Response: same 8-byte header + <len> data bytes + CRC16/Modbus (LE)

  <addr> selects the battery module (1..N); each module answers separately.
  cmd 0x40 (len 32) -> module serial (ASCII, NUL padded)
  cmd 0xc0 (len 91) -> per-module realtime telemetry block

All multi-byte numeric fields are little-endian. Field map calibrated against
a Victron Cerbo GX on an 8-module bank.
"""
from __future__ import annotations

import socket
import struct

DEFAULT_PORT = 8888
MAX_MODULES = 16  # upper bound when auto-discovering the bank size
DISCOVERY_TIMEOUT = 2.0  # per-address probe timeout (absent modules time out)
DISCOVERY_GAP_LIMIT = 3  # stop after this many consecutive empty addresses
DISCOVERY_RETRIES = 2  # extra tries for an interior gap (transient miss)
POLL_TIMEOUT = 3.0  # per-read timeout during a poll (bounds stalls on a down module)


class ZycError(Exception):
    """Communication or protocol error talking to the dongle."""


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _s16(b: bytes, i: int) -> int:
    return struct.unpack_from("<h", b, i)[0]


def _u16(b: bytes, i: int) -> int:
    return struct.unpack_from("<H", b, i)[0]


def _decode_module(p: bytes) -> dict:
    """Decode a 91-byte 0xc0 per-module block into physical values."""
    full_ah = _u16(p, 49) * 0.01
    remaining_ah = _u16(p, 28) * 0.1
    voltage = _s16(p, 25) * 0.1
    # Raw current is negative while charging; expose the Victron/Cerbo
    # convention instead: positive = charging, negative = discharging.
    current = -_s16(p, 32) * 0.1
    return {
        "voltage_v": round(voltage, 1),
        "current_a": round(current, 1),
        "power_w": round(voltage * current),
        "temp_c": p[18],
        "remaining_ah": round(remaining_ah, 1),
        "full_ah": round(full_ah, 2),
        # Direct per-module SOC register (0xc0[74]); matches the Cerbo reading.
        "soc_pct": round(_u16(p, 74) * 0.1, 1),
        "soh_pct": round(_u16(p, 30) * 0.1, 1),
        # Cell extremes (mV) for imbalance monitoring (matches portal Vmax/Vmin).
        "cell_v_max": _u16(p, 35),
        "cell_v_min": _u16(p, 37),
        "cell_v_delta": _u16(p, 35) - _u16(p, 37),
        # BMS limits (match the ZYC portal's CVL/CCL/DVL/DCL fields)
        "charge_voltage_limit_v": round(_u16(p, 70) * 0.1, 1),
        "charge_current_limit_a": round(_u16(p, 72) * 0.1, 1),
        "discharge_voltage_limit_v": round(_u16(p, 77) * 0.1, 1),
        "discharge_current_limit_a": round(_u16(p, 79) * 0.1, 1),
    }


class ZycClient:
    """One short-lived connection per poll; modules read sequentially.

    The dongle keeps a single connection open and expects frames back-to-back;
    rapid reconnects time out, so we reuse one socket for the whole poll.
    """

    def __init__(self, host: str, port: int = DEFAULT_PORT, timeout: float = 6.0):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._serials: dict[int, str] = {}  # addr -> serial, cached (static)
        self._firmware: dict[int, str] = {}  # addr -> firmware, cached (static)

    def serials(self) -> dict[int, str]:
        """Return the cached addr -> serial map (serial is static per module)."""
        return dict(self._serials)

    def seed_serial(self, addr: int, serial: str) -> None:
        """Pre-seed a cached serial (e.g. from persisted storage)."""
        self._serials[addr] = serial

    def _read_frame(self, sock: socket.socket, addr: int, cmd: int, length: int) -> tuple[bytes, bool]:
        req = bytes([0xF2, 0x03, addr, cmd, 0x00, 0x01]) + struct.pack(">H", length)
        sock.sendall(req + struct.pack("<H", _crc16(req)))
        buf = b""
        while len(buf) < 8:
            chunk = sock.recv(8 - len(buf))
            if not chunk:
                raise ZycError("connection closed while reading header")
            buf += chunk
        ln = struct.unpack(">H", buf[6:8])[0]
        while len(buf) < 8 + ln + 2:
            chunk = sock.recv(8 + ln + 2 - len(buf))
            if not chunk:
                raise ZycError("connection closed while reading payload")
            buf += chunk
        payload = buf[8:8 + ln]
        crc_ok = struct.unpack("<H", buf[8 + ln:10 + ln])[0] == _crc16(buf[:8 + ln])
        return payload, crc_ok

    def _read_serial(self, sock: socket.socket, addr: int) -> str | None:
        try:
            ser, _ = self._read_frame(sock, addr, 0x40, 32)
        except (OSError, ZycError):
            return None
        return ser.split(b"\x00", 1)[0].decode("ascii", "replace").strip()

    def _read_firmware(self, sock: socket.socket, addr: int) -> str | None:
        """Decode the module firmware version from the 0x04 block.

        0x04 = [fw_minor, fw_major, aux_minor, aux_major, build, fw_patch],
        i.e. two "minor, major" version pairs. The FIRST pair (b[0], b[1]) is
        the firmware the ZYC portal reports and is uniform across the bank
        (e.g. 2.32.0). The second pair (b[2], b[3]) is a separate version that
        tracks the master/slave role (the master module reads one minor higher),
        not the user-facing firmware -- decoding it here was the original bug.
        """
        try:
            b, ok = self._read_frame(sock, addr, 0x04, 6)
        except (OSError, ZycError):
            return None
        if not ok or len(b) < 6:
            return None
        return f"{b[1]}.{b[0]}.{b[5]}"

    def _read_block(self, sock: socket.socket, addr: int) -> dict | None:
        """Read the 0xC0 realtime block for one module (serial from cache)."""
        try:
            blk, ok = self._read_frame(sock, addr, 0xC0, 91)
        except (OSError, ZycError):
            return None
        if not ok or len(blk) < 51:
            return None
        data = _decode_module(blk)
        data["serial"] = self._serials.get(addr)
        data["firmware"] = self._firmware.get(addr)
        return data

    def _read_cells(self, sock: socket.socket, addr: int) -> list[int] | None:
        """Read the 16 individual cell voltages (mV) from the 0x44 block."""
        try:
            blk, ok = self._read_frame(sock, addr, 0x44, 32)
        except (OSError, ZycError):
            return None
        if not ok or len(blk) < 32:
            return None
        return [_u16(blk, 2 * k) for k in range(16)]

    def _read_module(self, sock: socket.socket, addr: int) -> dict | None:
        """Read serial + firmware + telemetry for one module (None if silent)."""
        serial = self._read_serial(sock, addr)
        if serial is None:
            return None
        self._serials[addr] = serial
        firmware = self._read_firmware(sock, addr)
        if firmware is not None:
            self._firmware[addr] = firmware
        return self._read_block(sock, addr)

    def discover(self) -> list[int]:
        """Probe module addresses and return every one that responds.

        Scans the full range so a removed module in the middle of the bank
        (a gap in the addresses) does not hide the modules after it. An absent
        address just times out; the shared connection survives the gap. To keep
        startup quick, the scan stops once it has seen at least one module and
        then hits DISCOVERY_GAP_LIMIT consecutive empty addresses.
        """
        found: list[int] = []
        misses = 0
        with self._connect() as sock:
            sock.settimeout(DISCOVERY_TIMEOUT)
            for addr in range(1, MAX_MODULES + 1):
                if self._read_module(sock, addr) is not None:
                    found.append(addr)
                    misses = 0
                else:
                    misses += 1
                    if found and misses >= DISCOVERY_GAP_LIMIT:
                        break
            # Retry interior gaps: a module between two responders that missed
            # once is almost certainly a transient miss, not an empty slot.
            if found:
                for addr in range(1, max(found)):
                    if addr in found:
                        continue
                    for _ in range(DISCOVERY_RETRIES):
                        if self._read_module(sock, addr) is not None:
                            found.append(addr)
                            break
        if not found:
            raise ZycError("no battery modules responded")
        return sorted(found)

    def poll(self, addrs: list[int]) -> dict:
        """Read all given modules over one connection and compute aggregates."""
        modules: dict[int, dict] = {}
        pack_soc: float | None = None
        with self._connect() as sock:
            sock.settimeout(POLL_TIMEOUT)
            for addr in addrs:
                # Serial is static and cached at discovery, so a normal poll is
                # one round trip per module; retry once to ride out a transient
                # miss before marking the module unavailable.
                if addr not in self._serials:
                    serial = self._read_serial(sock, addr)
                    if serial:
                        self._serials[addr] = serial
                m = self._read_block(sock, addr) or self._read_block(sock, addr)
                if m is not None:
                    cells = self._read_cells(sock, addr)
                    if cells:
                        m["cells"] = cells
                        m["cell_v_max"] = max(cells)
                        m["cell_v_min"] = min(cells)
                        m["cell_v_delta"] = max(cells) - min(cells)
                    modules[addr] = m
            # Pack-level block (0x80): [28] is the pack SOC the BMS reports to
            # the inverter/Cerbo. Read via the master address.
            try:
                p80, ok80 = self._read_frame(sock, addrs[0], 0x80, 103)
                if ok80 and len(p80) >= 30:
                    pack_soc = round(_u16(p80, 28) * 0.1, 1)
            except (OSError, ZycError):
                pack_soc = None
        if not modules:
            raise ZycError("no telemetry returned")

        vals = list(modules.values())
        socs = [m["soc_pct"] for m in vals if m["soc_pct"] is not None]
        sohs = [m["soh_pct"] for m in vals if m["soh_pct"] is not None]
        # Prefer the BMS's own pack SOC (matches Cerbo); fall back to the mean
        # of the per-module SOCs if the pack block didn't answer this cycle.
        pack_soc_value = pack_soc
        if pack_soc_value is None and socs:
            pack_soc_value = round(sum(socs) / len(socs), 1)
        aggregate = {
            "current_a_sum": round(sum(m["current_a"] for m in vals), 1),
            "power_w_sum": round(sum(m["power_w"] for m in vals)),
            "voltage_v_avg": round(sum(m["voltage_v"] for m in vals) / len(vals), 1),
            "temp_c_avg": round(sum(m["temp_c"] for m in vals) / len(vals), 1),
            "soc_pct_avg": pack_soc_value,
            "soh_pct_avg": round(sum(sohs) / len(sohs), 1) if sohs else None,
            "soh_pct_min": round(min(sohs), 1) if sohs else None,
            # Bank-wide cell extremes: worst imbalance across all modules.
            "cell_v_max": max(m["cell_v_max"] for m in vals),
            "cell_v_min": min(m["cell_v_min"] for m in vals),
            "cell_v_delta": (
                max(m["cell_v_max"] for m in vals)
                - min(m["cell_v_min"] for m in vals)
            ),
            "remaining_ah_sum": round(sum(m["remaining_ah"] for m in vals), 1),
            "full_ah_sum": round(sum(m["full_ah"] for m in vals), 1),
            "module_count": len(vals),
        }
        return {"modules": modules, "aggregate": aggregate}

    def _connect(self) -> socket.socket:
        try:
            sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        except OSError as err:
            raise ZycError(f"cannot connect to {self._host}:{self._port}: {err}") from err
        sock.settimeout(self._timeout)
        return sock
