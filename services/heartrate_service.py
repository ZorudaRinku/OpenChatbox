"""Shared BLE heart-rate service – one connection per device address.

All BLE work runs on a single module-level asyncio loop hosted in a daemon
thread. bleak caches a dbus_fast ``MessageBus`` per event loop; reusing one
loop means one system-bus connection for the app's lifetime instead of one
per ``start()``/scan, which would otherwise leak ``AddMatch`` subscribers
and exhaust dbus-broker's per-UID quota (crashing every Chromium-based app).
"""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import logging
import re
import threading
import time

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    BleakClient = None
    BleakScanner = None

logger = logging.getLogger(__name__)

HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
MAX_CONNECT_RETRIES = 3
_MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$")


def _parse_hr(data: bytearray) -> int | None:
    if len(data) < 2:
        return None
    flags = data[0]
    if flags & 0x01:
        return int.from_bytes(data[1:3], byteorder="little") if len(data) >= 3 else None
    return data[1]


# Persistent BLE loop

_lock = threading.Lock()
_ble_thread: threading.Thread | None = None
_ble_loop: asyncio.AbstractEventLoop | None = None
_ble_loop_ready = threading.Event()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """Start (once) a daemon thread running a persistent asyncio loop."""
    global _ble_thread, _ble_loop
    with _lock:
        if _ble_loop is not None and _ble_thread is not None and _ble_thread.is_alive():
            return _ble_loop

        _ble_loop_ready.clear()

        def _run():
            global _ble_loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _ble_loop = loop
            _ble_loop_ready.set()
            try:
                loop.run_forever()
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()

        _ble_thread = threading.Thread(target=_run, daemon=True, name="BLE-loop")
        _ble_thread.start()

    if not _ble_loop_ready.wait(timeout=5):
        raise RuntimeError("BLE loop thread failed to start within 5s")
    assert _ble_loop is not None
    return _ble_loop


def shutdown():
    """Stop all services, join the BLE loop thread. Idempotent."""
    global _ble_thread, _ble_loop, _scanner

    with _lock:
        services = list(_services.values())
        scanner = _scanner
        _services.clear()
        _scanner = None

    for svc in services:
        svc.stop(blocking=True)
    if scanner is not None:
        scanner.stop(blocking=True)

    with _lock:
        loop = _ble_loop
        thread = _ble_thread

    if loop is not None and loop.is_running():
        loop.call_soon_threadsafe(loop.stop)
    if thread is not None:
        thread.join(timeout=3)

    with _lock:
        _ble_loop = None
        _ble_thread = None
        _ble_loop_ready.clear()


atexit.register(shutdown)


# Service


class BLEService:
    """BLE heart rate monitor via bleak."""

    def __init__(self, device_address: str):
        self._device_address = device_address
        self._bpm: int | None = None
        self._last_valid_bpm: int | None = None
        self._zero_since: float | None = None
        self._status: str = ""
        self._stop_event = threading.Event()
        self._task: concurrent.futures.Future | None = None
        self._scan_task: concurrent.futures.Future | None = None
        self.scan_results: list[tuple[str, str, int, bool]] | None = None
        self.scan_status: str = ""
        self.scanning: bool = False
        self.gave_up: bool = False
        self._ref_count: int = 0

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self):
        if self.is_running():
            return
        self._stop_event.clear()
        loop = _ensure_loop()
        self._task = asyncio.run_coroutine_threadsafe(self._ble_loop(), loop)

    def stop(self, blocking: bool = True):
        self._stop_event.set()
        fut = self._task
        if fut is not None and not fut.done():
            fut.cancel()
            if blocking:
                try:
                    fut.result(timeout=3)
                except Exception as exc:
                    logger.debug("BLE task ended: %s", exc)
        self._task = None
        self._bpm = None
        self._status = ""
        self.gave_up = False

    def get_bpm(self) -> int | None:
        bpm = self._bpm
        if bpm is None:
            return None
        if bpm == 0:
            if self._zero_since is None:
                self._zero_since = time.time()
            if self._last_valid_bpm is not None and time.time() - self._zero_since < 30:
                return self._last_valid_bpm
            return 0
        self._last_valid_bpm = bpm
        self._zero_since = None
        return bpm

    @property
    def status(self) -> str:
        return self._status

    def scan(self):
        if self.scanning:
            return
        if self._scan_task is not None and not self._scan_task.done():
            return
        # Flip state synchronously: a busy BLE loop can defer _do_scan past the 200ms UI poll.
        self.scanning = True
        self.scan_status = "Scanning..."
        self.scan_results = None
        loop = _ensure_loop()
        self._scan_task = asyncio.run_coroutine_threadsafe(self._do_scan(), loop)

    async def _do_scan(self):
        if BleakScanner is None:
            self.scan_results = []
            self.scan_status = "bleak not installed"
            self.scanning = False
            return

        try:
            devices = await BleakScanner.discover(timeout=8, return_adv=True)
            results = []
            for device, adv in devices.values():
                name = device.name or ""
                rssi = adv.rssi or -999
                has_hr = HR_SERVICE_UUID in (adv.service_uuids or [])
                results.append((device.address, name, rssi, has_hr))
            results.sort(key=lambda x: (not x[3], -x[2]))
            self.scan_results = results
            if not results:
                self.scan_status = "No devices found"
            else:
                hr_count = sum(1 for r in results if r[3])
                if hr_count:
                    self.scan_status = f"Found {len(results)} device(s), {hr_count} HR"
                else:
                    self.scan_status = f"Found {len(results)} device(s)"
        except Exception as exc:
            logger.warning("BLE scan failed: %s", exc)
            self.scan_results = []
            self.scan_status = f"Scan failed: {exc}"
        finally:
            self.scanning = False

    async def _find_device(self):
        if _MAC_PATTERN.match(self._device_address):
            return self._device_address

        self._status = "Scanning..."
        logger.info("Scanning for BLE device named '%s'...", self._device_address)
        devices = await BleakScanner.discover(timeout=10, return_adv=True)
        for device, adv in devices.values():
            if device.name and self._device_address.lower() in device.name.lower():
                logger.info("Found '%s' at %s", device.name, device.address)
                return device.address

        hr_devices = await BleakScanner.discover(timeout=10, service_uuids=[HR_SERVICE_UUID])
        for device in hr_devices:
            if device.name and self._device_address.lower() in device.name.lower():
                logger.info("Found '%s' at %s (HR service)", device.name, device.address)
                return device.address

        return None

    async def _ble_loop(self):
        if BleakClient is None:
            self._status = "bleak not installed"
            logger.error("bleak package not installed - pip install bleak")
            return

        backoff = 1
        retries = 0
        while not self._stop_event.is_set():
            try:
                self._status = "Scanning..."
                address = await self._find_device()
                if not address:
                    retries += 1
                    if retries >= MAX_CONNECT_RETRIES:
                        self._status = "Device not found - gave up"
                        self.gave_up = True
                        logger.warning("BLE device '%s' not found after %d attempts - giving up",
                                       self._device_address, retries)
                        return
                    self._status = "Device not found"
                    logger.warning("BLE device '%s' not found - retrying in %ds (%d/%d)",
                                   self._device_address, backoff, retries, MAX_CONNECT_RETRIES)
                    await asyncio.sleep(min(backoff, 30))
                    backoff = min(backoff * 2, 30)
                    continue

                self._status = f"Connecting to {address}..."
                async with BleakClient(address) as client:
                    logger.info("BLE connected to %s", address)
                    backoff = 1
                    retries = 0

                    service_uuids = [str(s.uuid) for s in client.services]
                    if HR_SERVICE_UUID not in service_uuids:
                        # Reconnecting won't add an HR service; give up so the message stays visible. reconnect() retries on field re-edit.
                        self._status = ("No HR service on device. "
                                        "Try a broadcaster app (e.g. Heart Rate for Bluetooth)")
                        self.gave_up = True
                        logger.warning("Device %s connected but does not expose Heart Rate Service. "
                                       "Available services: %s - giving up",
                                       address, service_uuids)
                        return

                    self._status = "Waiting for data..."

                    def on_notify(_sender, data: bytearray):
                        bpm = _parse_hr(data)
                        if bpm is not None:
                            self._bpm = bpm
                            self._status = "Connected"

                    await client.start_notify(HR_MEASUREMENT_UUID, on_notify)
                    while not self._stop_event.is_set() and client.is_connected:
                        await asyncio.sleep(1)

                self._status = "Disconnected"
            except asyncio.CancelledError:
                self._status = "Disconnected"
                raise
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                retries += 1
                if retries >= MAX_CONNECT_RETRIES:
                    self._status = f"Connection failed - gave up ({exc})"
                    self.gave_up = True
                    logger.warning("BLE connection to '%s' failed after %d attempts - giving up: %s",
                                   self._device_address, retries, exc)
                    return
                self._status = f"Error: {exc}"
                logger.warning("BLE connection error: %s - retrying in %ds (%d/%d)",
                               exc, backoff, retries, MAX_CONNECT_RETRIES)
                await asyncio.sleep(min(backoff, 30))
                backoff = min(backoff * 2, 30)


# Registry

_services: dict[str, BLEService] = {}
_scanner: BLEService | None = None


def acquire(address: str) -> BLEService:
    """Get or create a BLE service for *address*, incrementing its ref count."""
    key = address.strip()
    with _lock:
        if key in _services:
            _services[key]._ref_count += 1
            return _services[key]
        svc = BLEService(address)
        svc._ref_count = 1
        _services[key] = svc
        return svc


def release(address: str, blocking: bool = True):
    """Decrement ref count; stop and remove when it reaches zero."""
    key = address.strip()
    with _lock:
        svc = _services.get(key)
        if not svc:
            return
        svc._ref_count = max(0, svc._ref_count - 1)
        if svc._ref_count == 0:
            del _services[key]
        else:
            return
    svc.stop(blocking=blocking)


def get_scanner() -> BLEService:
    """Return a shared scanner instance (no device connection)."""
    global _scanner
    with _lock:
        if _scanner is None:
            _scanner = BLEService("")
        return _scanner


def get_active_bpm() -> int | None:
    """Return the BPM from the first active service with data."""
    with _lock:
        for svc in _services.values():
            bpm = svc.get_bpm()
            if bpm is not None:
                return bpm
    return None
