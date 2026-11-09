"""The Unix-socket RPC is local-only and does not open BLE for status requests."""

import asyncio
import json

import pytest

from awox_ble.daemon import handle_client
from awox_ble.service import LampController


@pytest.mark.asyncio
async def test_rpc_status_over_unix_socket(tmp_path) -> None:
    controller = LampController()
    path = tmp_path / "awox-ble.sock"
    server = await asyncio.start_unix_server(
        lambda reader, writer: handle_client(reader, writer, controller),
        path=str(path),
    )
    try:
        reader, writer = await asyncio.open_unix_connection(str(path))
        writer.write(b'{"action":"service-status"}\n')
        await writer.drain()
        response = json.loads(await asyncio.wait_for(reader.readline(), 2))
        assert response["ok"] is True
        assert response["connected"] is False
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        await server.wait_closed()
        await controller.close()


@pytest.mark.asyncio
async def test_client_disconnect_while_bluetooth_command_runs() -> None:
    """A disconnected DMS client must not crash the RPC handler."""

    class Reader:
        async def readline(self):
            return b'{"action":"brightness","value":50}\\n'.replace(b"\\n", b"\n")

    class Controller:
        async def execute(self, action, value):
            assert (action, value) == ("brightness", 50)
            return {"ok": False, "error": "Bluetooth connection unavailable"}

    class DisconnectedWriter:
        closed = False

        def write(self, payload):
            assert payload

        async def drain(self):
            raise BrokenPipeError("client disconnected")

        def close(self):
            self.closed = True

        async def wait_closed(self):
            raise ConnectionResetError("client disconnected")

    writer = DisconnectedWriter()
    await handle_client(Reader(), writer, Controller())
    assert writer.closed
