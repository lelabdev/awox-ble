"""The first full BLE advertisement is not necessarily fresh."""

from awox_ble.state import StatusAccumulator


def advert(brightness: int) -> bytes:
    # Fake Connect-Z manufacturer data; no real hardware identifiers.
    value = bytearray(27)
    value[6:8] = bytes([3, 0])
    value[9:11] = bytes([0x34, 0x12])
    value[11] = 1
    value[12] = brightness
    value[13:15] = bytes([0xC6, 0x01])
    return bytes(value)


def test_first_full_frame_is_not_accepted() -> None:
    acc = StatusAccumulator(started=100)
    assert not acc.observe(advert(65), 100.5)
    assert acc.result().state.brightness == 26
    assert not acc.result().confirmed
    assert acc.result().frames == 1


def test_changed_state_resets_candidate_and_confirms_new() -> None:
    acc = StatusAccumulator(started=100)
    assert not acc.observe(advert(65), 101)
    assert not acc.observe(advert(204), 108)
    assert not acc.observe(advert(204), 109)
    assert acc.observe(advert(204), 121)
    assert acc.result().confirmed
    assert acc.result().state.brightness == 80


def test_duplicate_too_soon_cannot_confirm() -> None:
    acc = StatusAccumulator(started=100)
    assert not acc.observe(advert(204), 100)
    assert not acc.observe(advert(204), 100.5)
    assert not acc.observe(advert(204), 111)
    assert acc.observe(advert(204), 113)


def test_short_frames_are_not_a_status() -> None:
    acc = StatusAccumulator(started=100)
    assert not acc.observe(advert(204)[:6], 102)
    assert acc.result().seen
    assert acc.result().state is None
    assert acc.result().frames == 0
