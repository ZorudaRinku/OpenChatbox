from __future__ import annotations

import logging
from services.text_processor import FieldDef
from services import heartrate_service

logger = logging.getLogger(__name__)


class HeartrateToken:
    """Template token for heart rate monitors via BLE."""
    tag = "heartrate"
    field_defs = [
        FieldDef("device_address", "Device", "", field_type="ble_scan"),
        FieldDef("suffix", "Suffix", "BPM"),
        FieldDef("fallback", "Fallback", "-- BPM"),
    ]

    def __init__(self):
        self._service: heartrate_service.BLEService | None = None
        self._active_key: str | None = None
        self._scanner = heartrate_service.get_scanner()

    @property
    def scanning(self) -> bool:
        return self._scanner.scanning

    @property
    def scan_results(self) -> list[tuple[str, str, int, bool]] | None:
        return self._scanner.scan_results

    def scan(self):
        self._scanner.scan()

    def reconnect(self):
        if self._service and self._service.gave_up:
            self._service.stop()
            self._service.start()

    def _start_service(self):
        addr = self.fields.get("device_address", "")
        if not addr:
            return
        if self._service and self._active_key == addr:
            if self._service.gave_up:
                return
            return
        if self._service and self._active_key:
            heartrate_service.release(self._active_key)
            self._service = None

        try:
            self._service = heartrate_service.acquire(addr)
            self._active_key = addr
            self._service.start()
            logger.info("Started BLE heart rate service")
        except Exception:
            logger.exception("Failed to start BLE heart rate service")
            self._service = None

    @property
    def status(self) -> str:
        if self._service:
            return self._service.status
        return ""

    def resolve(self) -> str:
        self._start_service()
        if self._service:
            bpm = self._service.get_bpm()
            if bpm is not None:
                return f"{bpm} {self.fields['suffix']}"
        return self.fields["fallback"]

    def stop(self, blocking: bool = True):
        if self._service and self._active_key:
            heartrate_service.release(self._active_key, blocking=blocking)
            self._service = None
            self._active_key = None
