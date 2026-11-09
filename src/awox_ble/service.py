"""Serialized mesh access; a warm session is reused for subsequent commands."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from awox_mesh import protocol
from awox_mesh.connection import create

from .settings import idle_seconds, load_mesh_config, preset_delay

ACTIONS = {"bright", "dim", "on", "off", "brightness", "temperature"}
PRESETS = {"bright": (100, 50), "dim": (25, 100)}  # brightness, warm-white percentage


class LampController:
    def __init__(self, *, idle: float | None = None, delay: float | None = None) -> None:
        self.idle = idle if idle is not None else idle_seconds()
        self.delay = delay if delay is not None else preset_delay()
        self._lock = asyncio.Lock()
        self._mesh: Any | None = None
        self._last_used = 0.0

    @property
    def connected(self) -> bool:
        return bool(self._mesh is not None and self._mesh.is_connected)

    async def _disconnect(self) -> None:
        mesh, self._mesh = self._mesh, None
        if mesh is not None:
            await mesh.stop()

    async def _send(self, builder) -> None:
        if self._mesh is None:
            self._mesh = create(load_mesh_config())
        try:
            await self._mesh.send(builder)
        except Exception:
            await self._disconnect()
            raise

    async def execute(self, action: str, value: int | None = None) -> dict[str, Any]:
        started = time.monotonic()
        async with self._lock:
            if action == "service-status":
                return {
                    "ok": True,
                    "connected": self.connected,
                    "idle_seconds": self.idle,
                    "message": "Connected" if self.connected else "Disconnected",
                }
            if action == "release":
                await self._disconnect()
                return {"ok": True, "connected": False, "message": "Bluetooth connection released"}
            if action not in ACTIONS:
                raise ValueError(f"Unknown action: {action}")
            if action in ("brightness", "temperature") and (
                type(value) is not int or not 0 <= value <= 100
            ):
                raise ValueError("Value must be an integer from 0 to 100")
            if action == "on":
                await self._send(lambda key, mid: protocol.set_power(key, mid, True))
            elif action == "off":
                await self._send(lambda key, mid: protocol.set_power(key, mid, False))
            elif action == "brightness":
                await self._send(lambda key, mid: protocol.set_brightness(key, mid, value))
            elif action == "temperature":
                await self._send(lambda key, mid: protocol.set_white_temperature(key, mid, value))
            else:
                brightness, temperature = PRESETS[action]
                # Brightness first: it has a visible effect as quickly as possible.
                await self._send(
                    lambda key, mid: protocol.set_brightness(key, mid, brightness)
                )
                # Firmware 3.0.2 drops tightly-spaced writes; keep a configurable gap.
                await asyncio.sleep(self.delay)
                await self._send(
                    lambda key, mid: protocol.set_white_temperature(key, mid, temperature)
                )
            self._last_used = time.monotonic()
            return {
                "ok": True,
                "connected": self.connected,
                "elapsed_ms": round((self._last_used - started) * 1000),
                "verified": False,
                "message": "Command sent (final state not verified)",
            }

    async def watchdog(self) -> None:
        while True:
            await asyncio.sleep(2)
            if self._mesh is None:
                continue
            async with self._lock:
                if self._mesh is not None and self._last_used and (
                    time.monotonic() - self._last_used >= self.idle
                ):
                    await self._disconnect()

    async def close(self) -> None:
        async with self._lock:
            await self._disconnect()
