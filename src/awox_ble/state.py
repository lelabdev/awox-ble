"""Decode AwoX Bluetooth status advertisements with fresh-state confirmation."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from bleak import BleakScanner

# BlueZ and the bulb can briefly repeat stale status after a BLE disconnect.
# Require matching broadcasts received at different times, not the first full frame.
MIN_CONFIRM_AGE = 12.0
MIN_REPEAT_GAP = 2.0


@dataclass(frozen=True)
class LampState:
    mesh_id: int
    is_on: bool
    brightness: int
    temperature_kelvin: int | None


@dataclass(frozen=True)
class ScanObservation:
    """A full reading is only confirmed after matching, spaced broadcasts."""

    state: LampState | None
    seen: bool
    confirmed: bool = False
    frames: int = 0


def decode_advert(company: int, data: bytes) -> LampState | None:
    if company != 0x0160 or len(data) < 17 or (data[6], data[7]) not in ((3, 0), (2, 2)):
        return None
    connect_c = (data[6], data[7]) == (2, 2)
    is_color = bool(data[11] & 2)
    maximum = (100 if is_color else 127) if connect_c else 254
    brightness = round(min(data[12], maximum) * 100 / maximum)
    raw_temp = (data[13] | (data[14] << 8)) if not connect_c else data[13]
    temperature = round(1_000_000 / raw_temp) if 153 <= raw_temp <= 500 else None
    return LampState(
        mesh_id=data[9] | (data[10] << 8),
        is_on=bool(data[11] & 1),
        brightness=brightness,
        temperature_kelvin=temperature,
    )


class StatusAccumulator:
    """Tracks independent full frames, excluding the first possibly stale value."""

    def __init__(self, started: float) -> None:
        self.started = started
        self.candidate: LampState | None = None
        self.last_observed: LampState | None = None
        self.seen = False
        self.confirmed = False
        self.frames = 0
        self.candidate_at = started

    def observe(self, data: bytes, now: float) -> bool:
        self.seen = True
        state = decode_advert(0x0160, data)
        if state is None:
            return False
        self.frames += 1
        self.last_observed = state
        if state != self.candidate:
            self.candidate = state
            self.candidate_at = now
            self.confirmed = False
            return False
        if now - self.started >= MIN_CONFIRM_AGE and now - self.candidate_at >= MIN_REPEAT_GAP:
            self.confirmed = True
        return self.confirmed

    def result(self) -> ScanObservation:
        return ScanObservation(self.last_observed, self.seen, self.confirmed, self.frames)


async def scan_state(mac: str, timeout: float = 12) -> ScanObservation:
    """Wait for a confirmed state, or return the last observed value unconfirmed."""
    stable = asyncio.Event()
    accumulator = StatusAccumulator(time.monotonic())

    def callback(device, advert) -> None:
        if device.address.upper() != mac.upper():
            return
        data = advert.manufacturer_data.get(0x0160, b"")
        if accumulator.observe(data, time.monotonic()):
            stable.set()

    async with BleakScanner(detection_callback=callback):
        try:
            await asyncio.wait_for(stable.wait(), timeout)
        except TimeoutError:
            pass
    return accumulator.result()


async def read_state(mac: str, timeout: float = 12) -> LampState | None:
    """Compatibility helper: return only confirmed readings."""
    observation = await scan_state(mac, timeout)
    return observation.state if observation.confirmed else None
