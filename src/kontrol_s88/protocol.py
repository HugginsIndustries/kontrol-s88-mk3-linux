"""
NI Kontrol S88 MK3 Protocol
----------------------------
Reverse engineered HID protocol for the Native Instruments Kontrol S88 MK3.
Communication uses MessagePack-encoded messages with an 8-byte header:
  [length: 4 bytes LE] [message_type: 4 bytes] [msgpack payload...]

The keyboard operates in two modes:
  - MIDI mode: standard USB MIDI, limited functionality
  - PLUG-IN mode: full HID control, activated by sending a handshake packet
"""

import struct
import msgpack


# USB identifiers
VENDOR_ID = 0x17cc
PRODUCT_ID = 0x2120
INTERFACE = 3
ENDPOINT_OUT = 0x04

# Message type headers (4 bytes each)
HDR_HANDSHAKE  = bytes.fromhex('93024092')  # Identify software to keyboard
HDR_INIT       = bytes.fromhex('93025092')  # Initialize state
HDR_STATE      = bytes.fromhex('93025792')  # Set keyboard state (tempo, scale, arp, etc.)
HDR_LIGHTS     = bytes.fromhex('93025892')  # Light guide control

# State parameter keys
KEY_TEMPO        = 120   # float32 BPM
KEY_KEYBOARD_ID  = 121   # str, always 'NIKB00'
KEY_PARAM_122    = 122   # unknown
KEY_PARAM_123    = 123   # unknown
KEY_PARAM_124    = 124   # unknown bool
KEY_PARAM_125    = 125   # unknown bool
KEY_PARAM_126    = 126   # unknown


def _pack_float32(value: float) -> bytes:
    """Pack a float as MessagePack float32 (ca prefix)."""
    return b'\xca' + struct.pack('>f', value)


def make_packet(header: bytes, *values) -> bytes:
    """Build a framed packet with header and MessagePack payload."""
    payload = b''.join(msgpack.packb(v, use_bin_type=True) for v in values)
    length = len(payload) + 4
    return struct.pack('<I', length) + header + payload


def make_handshake_packet(name: str = 'Komplete Kontrol',
                          version: str = '3.5.3',
                          kind: str = 'standalone') -> bytes:
    """
    Identify the software to the keyboard.
    This packet switches the keyboard from MIDI mode to PLUG-IN mode.
    """
    return make_packet(
        HDR_HANDSHAKE,
        16,
        {'name': name, 'version': version, 'type': kind}
    )


def make_init_packet() -> bytes:
    """Initialize keyboard state after handshake."""
    return make_packet(HDR_INIT, 16, {256: [], 257: None})


def make_state_packet(**kwargs) -> bytes:
    """
    Build a state update packet.
    Known kwargs:
      tempo (float): BPM value
    """
    bpm = kwargs.get('tempo', 120.0)

    payload = (
        msgpack.packb(16, use_bin_type=True) +
        b'\x8d' +  # fixmap, 13 keys
        msgpack.packb(114, use_bin_type=True) + msgpack.packb(None, use_bin_type=True) +
        msgpack.packb(115, use_bin_type=True) + msgpack.packb(None, use_bin_type=True) +
        msgpack.packb(116, use_bin_type=True) + msgpack.packb('', use_bin_type=True) +
        msgpack.packb(117, use_bin_type=True) + msgpack.packb(None, use_bin_type=True) +
        msgpack.packb(118, use_bin_type=True) + msgpack.packb(None, use_bin_type=True) +
        msgpack.packb(119, use_bin_type=True) + msgpack.packb(None, use_bin_type=True) +
        msgpack.packb(KEY_TEMPO, use_bin_type=True) + _pack_float32(bpm) +
        msgpack.packb(KEY_KEYBOARD_ID, use_bin_type=True) + msgpack.packb('NIKB00', use_bin_type=True) +
        msgpack.packb(122, use_bin_type=True) + msgpack.packb(None, use_bin_type=True) +
        msgpack.packb(123, use_bin_type=True) + msgpack.packb(None, use_bin_type=True) +
        msgpack.packb(124, use_bin_type=True) + msgpack.packb(True, use_bin_type=True) +
        msgpack.packb(125, use_bin_type=True) + msgpack.packb(True, use_bin_type=True) +
        msgpack.packb(126, use_bin_type=True) + msgpack.packb(None, use_bin_type=True)
    )
    length = len(payload) + 4
    return struct.pack('<I', length) + HDR_STATE + payload
