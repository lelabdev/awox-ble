"""Command-line client for the local AwoX BLE controller."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .settings import load_mesh_config, socket_path
from .state import ScanObservation, scan_state


async def request(action: str, value: int | None = None) -> dict:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(socket_path())), timeout=2
        )
    except (OSError, TimeoutError) as error:
        raise RuntimeError(
            "awox-ble service unavailable. Start it with: systemctl --user start awox-ble.service"
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


def show_observation(observation: ScanObservation, timeout: float) -> int:
    state = observation.state
    if state is None:
        if observation.seen:
            print(
                f"Light detected, but no complete status frame in {timeout:g}s. "
                "Try 'light scan' for a longer scan.",
                file=sys.stderr,
            )
            return 3
        print(
            f"Light not detected within {timeout:g}s. "
            "Check power, range, or another active Bluetooth connection.",
            file=sys.stderr,
        )
        return 2
    print(f"EGLO: {'on' if state.is_on else 'off'}")
    print(f"Brightness: {state.brightness}%")
    print(f"Mesh ID: 0x{state.mesh_id:04X}")
    if state.temperature_kelvin is not None:
        print(f"Color temperature: approximately {state.temperature_kelvin} K")
    return 0


async def read_advertised_status(*, timeout: float, release: bool) -> int:
    if release:
        try:
            await request("release")
        except (RuntimeError, OSError):
            # The daemon is optional for passive scanning.
            pass
    return show_observation(await scan_state(load_mesh_config().mac, timeout), timeout)


async def main_async(action: str, value: int | None) -> int:
    if action == "status":
        # While paired, Connect-Z mostly stops its full status advertisements.
        # Avoid 35 seconds of futile scanning and do not invent verified state.
        try:
            session = await request("service-status")
        except (RuntimeError, OSError):
            session = {}
        if session.get("connected"):
            print("BLE connected; the lamp does not advertise full status during this session.")
            last = session.get("last_command")
            if last:
                label = last["action"]
                if last.get("value") is not None:
                    label += f" {last['value']}"
                print(f"Last requested command: {label} (not independently verified)")
            else:
                print("No independently verified lamp state available.")
            print("Use 'light scan' to release the connection and read a fresh advertisement.")
            return 0
        return await read_advertised_status(timeout=12, release=False)

    if action == "scan":
        # A deliberate fresh scan may take >35 s because full beacons are sparse.
        return await read_advertised_status(timeout=70, release=True)

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
        "action",
        nargs="?",
        default="status",
        choices=[
            "status",
            "scan",
            "service-status",
            "bright",
            "dim",
            "on",
            "off",
            "brightness",
            "temperature",
            "release",
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
