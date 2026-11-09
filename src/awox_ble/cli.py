"""Command-line client for the local AwoX BLE controller."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .settings import load_mesh_config, socket_path
from .state import read_state


async def request(action: str, value: int | None = None) -> dict:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(socket_path())), timeout=2
        )
    except (OSError, TimeoutError) as error:
        raise RuntimeError(
            "awox-ble service unavailable. Start it with: "
            "systemctl --user start awox-ble.service"
        ) from error
    try:
        writer.write(json.dumps({"action": action, "value": value}).encode() + b"\n")
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=125)
        if not line:
            raise RuntimeError("The daemon did not respond")
        return json.loads(line)
    finally:
        writer.close()
        await writer.wait_closed()


async def main_async(action: str, value: int | None) -> int:
    if action == "status":
        state = await read_state(load_mesh_config().mac)
        if state is None:
            print("Light not found or no complete advertisement received.", file=sys.stderr)
            return 2
        print(f"EGLO: {'on' if state.is_on else 'off'}")
        print(f"Brightness: {state.brightness}%")
        print(f"Mesh ID: 0x{state.mesh_id:04X}")
        if state.temperature_kelvin is not None:
            print(f"Color temperature: approximately {state.temperature_kelvin} K")
        return 0

    data = await request(action, value)
    if not data.get("ok"):
        print(f"Error: {data.get('error', 'command not executed')}", file=sys.stderr)
        return 1
    print(data.get("message", "OK"))
    if action == "service-status":
        print(f"Idle disconnect after: {data['idle_seconds']:g} seconds")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="light", description="Control an AwoX / EGLO BLE light")
    parser.add_argument(
        "action", nargs="?", default="status",
        choices=[
            "status", "service-status", "bright", "dim", "on", "off",
            "brightness", "temperature", "release",
        ],
    )
    parser.add_argument("value", nargs="?", type=int)
    args = parser.parse_args()
    if args.action in ("brightness", "temperature"):
        if args.value is None or not 0 <= args.value <= 100:
            parser.error("Value must be between 0 and 100")
    elif args.value is not None:
        parser.error("This action does not take a value")

    try:
        return asyncio.run(main_async(args.action, args.value))
    except (RuntimeError, OSError, TimeoutError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
