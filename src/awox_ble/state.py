"""Read unencrypted status advertisements without opening a mesh session."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bleak import BleakScanner


@dataclass(frozen=True)
class LampState:
    mesh_id: int
    is_on: bool
    brightness: int
    temperature_kelvin: int | None


def decode_advert(company: int, data: bytes) -> LampState | None:
    if company != 0x0160 or len(data) < 17 or (data[6], data[7]) not in ((3, 0), (2, 2)):
        return None
    # CONNECT-Z and CONNECT-C have different brightness value ranges.
    connect_c = (data[6], data[7]) == (2, 2)
    is_color = bool(data[11] & 2)
    maximum = (100 if is_color else 127) if connect_c else 254
    brightness = round(min(data[12], maximum) * 100 / maximum)
    raw_temp = (data[13] | (data[14] << 8)) if not connect_c else data[13]
    temp = round(1_000_000 / raw_temp) if 153 <= raw_temp <= 500 else None
    return LampState(
        mesh_id=data[9] | (data[10] << 8),
        is_on=bool(data[11] & 1),
        brightness=brightness,
        temperature_kelvin=temp,
    )


async def read_state(mac: str, timeout: float = 35) -> LampState | None:
    found = asyncio.Event()
    state: LampState | None = None

    def callback(device, advert) -> None:
        nonlocal state
        if device.address.upper() != mac.upper():
            return
        data = advert.manufacturer_data.get(0x0160, b"")
        state = decode_advert(0x0160, data) or state
        if state is not None:
            found.set()

    async with BleakScanner(detection_callback=callback):
        try:
            await asyncio.wait_for(found.wait(), timeout)
        except TimeoutError:
            pass
    return state
