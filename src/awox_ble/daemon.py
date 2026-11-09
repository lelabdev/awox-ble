"""Local daemon: one protected Unix socket, one shared BLE mesh session."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from pathlib import Path

from .service import LampController
from .settings import socket_path

LOG = logging.getLogger("awox-ble")


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    controller: LampController,
) -> None:
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        if not line or len(line) > 4096 or not line.endswith(b"\n"):
            raise ValueError("Empty or oversized request")
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise TypeError("Expected a JSON object")
        action = payload.get("action")
        if not isinstance(action, str):
            raise TypeError("Missing action")
        result = await controller.execute(action, payload.get("value"))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        result = {"ok": False, "error": str(error)}
    except Exception as error:  # noqa: BLE001 - BLE boundary reports safe errors over RPC
        LOG.warning("Bluetooth request failed: %s", type(error).__name__)
        result = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    try:
        writer.write(json.dumps(result, ensure_ascii=False).encode() + b"\n")
        await writer.drain()
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        # A UI client can disconnect while a slow Bluetooth attempt is in progress.
        # This must not become an unhandled server exception.
        LOG.debug("Client disconnected before the BLE response was delivered")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


async def serve(path: Path | None = None, controller: LampController | None = None) -> None:
    path = path or socket_path()
    controller = controller or LampController()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    if path.exists() or path.is_socket():
        try:
            _, client = await asyncio.open_unix_connection(str(path))
            client.close()
            await client.wait_closed()
        except OSError:
            # Left over from a crashed process.
            if not path.is_socket():
                raise RuntimeError(f"Not a Unix socket: {path}")
            path.unlink()
        else:
            raise RuntimeError(f"Already running: {path}")

    old_umask = os.umask(0o077)
    try:
        server = await asyncio.start_unix_server(
            lambda reader, writer: handle_client(reader, writer, controller),
            path=str(path),
        )
        path.chmod(0o600)
    finally:
        os.umask(old_umask)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop.set)
        except NotImplementedError:
            pass

    watchdog = asyncio.create_task(controller.watchdog())
    LOG.info("Local socket ready: %s", path)
    try:
        async with server:
            await stop.wait()
    finally:
        watchdog.cancel()
        try:
            await watchdog
        except asyncio.CancelledError:
            pass
        await controller.close()
        if path.is_socket():
            path.unlink()


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(serve())


if __name__ == "__main__":
    main()
