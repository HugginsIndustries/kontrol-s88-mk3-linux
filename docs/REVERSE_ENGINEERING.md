# Reverse Engineering Guide: NI Kontrol S88 MK3 on Linux

This document explains the reverse engineering process used to discover the NI Kontrol S88 MK3's HID protocol, and provides a methodology for discovering and implementing new features. It is intended for future contributors — human or AI.

---

## Background

Native Instruments does not support Linux. The S88 MK3 operates in two modes:

- **MIDI mode** — standard USB class-compliant MIDI. Notes, velocity, pitchbend, and mod wheel work. The arpeggiator runs but cannot be synced to external clock. NI explicitly confirmed this is intentional.
- **PLUG-IN mode** — activated by a software handshake. All advanced features become available: arpeggiator control, scale mode, light guide, display, etc. This is the mode Komplete Kontrol uses.

Our goal is to replicate the Komplete Kontrol handshake from Linux so we can control the keyboard fully without NI's software.

---

## Hardware / USB Profile

```
Vendor ID:  0x17cc  (Native Instruments)
Product ID: 0x2120  (Kontrol S88 MK3)
Bus:        USB 3 (may vary)
```

### Relevant Endpoints

| Endpoint | Direction | Type      | Size   | Purpose                        |
|----------|-----------|-----------|--------|-------------------------------|
| EP 1     | IN/OUT    | Bulk      | 512B   | Audio streaming                |
| EP 2     | IN/OUT    | Interrupt | 64B    | MIDI data                      |
| EP 3     | IN/OUT    | Bulk      | 512B   | HID control (interface 3)      |
| EP 4     | OUT       | Bulk      | 512B   | HID control output (interface 3) |
| EP 5     | IN/OUT    | Bulk/Int  | varies | Unknown                        |

**Interface 3, Endpoint 4 OUT (0x04)** is where all Komplete Kontrol communication happens.

---

## Protocol Overview

All messages to/from the keyboard use a simple framing format:

```
[length: uint32 LE] [message_type: 4 bytes] [MessagePack payload...]
```

- `length` = number of bytes after the first 4 (i.e. includes the 4 message_type bytes + payload)
- `message_type` = 4-byte identifier for the message category
- payload = one or more **MessagePack**-encoded values

### Known Message Types

| Header (hex) | Name        | Direction   | Purpose                              |
|--------------|-------------|-------------|--------------------------------------|
| `93024092`   | HANDSHAKE   | host → kbd  | Identify software, activate PLUG-IN mode |
| `93025092`   | INIT        | host → kbd  | Initialize state after handshake     |
| `93025792`   | STATE       | host → kbd  | Set keyboard parameters (tempo, etc.)|
| `93025892`   | LIGHTS      | host → kbd  | Light guide control                  |

### Activation Sequence

To put the keyboard into PLUG-IN mode, send these three packets in order:

1. **HANDSHAKE** — identifies the software:
   ```
   payload: 16, {"name": "Komplete Kontrol", "version": "3.5.3", "type": "standalone"}
   ```

2. **INIT** — initializes state:
   ```
   payload: 16, {256: [], 257: None}
   ```

3. **STATE** — sets initial parameters (including tempo):
   ```
   payload: 16, {114: None, 115: None, 116: '', 117: None, 118: None,
                 119: None, 120: <BPM float32>, 121: 'NIKB00',
                 122: None, 123: None, 124: True, 125: True, 126: None}
   ```

Once the HANDSHAKE packet is received, the keyboard switches to PLUG-IN mode and the BROWSER/PLUG-IN buttons light up.

### State Packet Notes

- Key `120` = BPM, encoded as **MessagePack float32** (`\xca` prefix + big-endian IEEE 754)
- Key `121` = keyboard identifier string, always `'NIKB00'`
- Keys `114–119`, `122–126` = unknown parameters, safe to send as `None`/`True` (values observed from Komplete Kontrol captures)
- Integer keys in the map require `strict_map_key=False` when decoding with python-msgpack

---

## Reverse Engineering Methodology

This section describes the exact process used to discover the protocol. Follow these steps to discover new features.

### Tools Required

- **Wireshark** with usbmon: `sudo pacman -S wireshark-qt && sudo modprobe usbmon`
- **Windows VM** via virt-manager/QEMU with USB passthrough
- **Komplete Kontrol** installed in the Windows VM (free download from NI)
- **Python** with `python-msgpack` and `python-libusb1`

### Step 1: Set Up USB Capture

Find which USB bus the S88 is on:
```bash
lsusb | grep -i native
# Example output: Bus 003 Device 004: ID 17cc:2120 Native Instruments KONTROL S88 MK3
```

Open Wireshark and capture on `usbmon3` (replace 3 with your bus number).

### Step 2: Filter Out Noise

The S88 constantly streams audio and MIDI data that drowns out the interesting control packets. Use this Wireshark filter to show only meaningful traffic:

```
usb.device_address == 4
  && !(usb.dst == "3.4.4" && frame.len == 462)
  && !(usb.src == "3.4.4" && frame.len == 64)
  && !(usb.dst == "3.4.1" && frame.len == 68)
  && !(usb.src == "3.4.1" && frame.len == 64)
  && !(usb.src == "3.4.1" && frame.len == 68)
  && !(usb.dst == "3.4.1" && frame.len == 64)
  && !(usb.dst == "3.4.3" && frame.len == 72)
  && !(usb.src == "3.4.3" && frame.len == 64)
```

Replace `3.4.x` with `<bus>.<device>.<endpoint>` for your setup.

For capturing only tempo-related messages:
```
usb.transfer_type == 0x03 && usb.dst == "3.4.4" && frame.len == 110
```

### Step 3: Capture a Feature

1. Start a fresh Wireshark capture with the noise filter active
2. In the Windows VM, open Komplete Kontrol and connect the S88
3. Perform the action you want to reverse engineer (e.g. change arp rate, change scale, etc.)
4. Stop the capture
5. Right-click **Leftover Capture Data** on interesting packets → **Copy → As Hex Dump**

### Step 4: Decode the Packets

Use this Python snippet to decode captured packets:

```python
import msgpack
import struct

def decode_messages(raw: bytes):
    offset = 0
    while offset < len(raw):
        if offset + 8 > len(raw):
            break
        length = struct.unpack_from('<I', raw, offset)[0]
        header = raw[offset+4:offset+8]
        payload = raw[offset+8:offset+4+length]
        decoded = []
        unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
        unpacker.feed(payload)
        for item in unpacker:
            decoded.append(item)
        print(f"Offset {offset:04x}: header={header.hex()} len={length}")
        for item in decoded:
            print(f"  {item}")
        offset += 4 + length

# Paste your hex dump here
raw = bytes.fromhex("YOUR_HEX_HERE")
decode_messages(raw)
```

### Step 5: Find the Changing Bytes

To isolate which bytes control a parameter:
1. Capture the same action at multiple values (e.g. different arp rates, different scales)
2. Decode each capture
3. Compare the decoded dicts — the key whose value changes is your parameter

For numeric values that aren't obviously decoded, try:
```python
import struct
data = bytes([0x42, 0xf0, 0x00, 0x00])
print(struct.unpack('>f', data))   # big-endian float32
print(struct.unpack('<f', data))   # little-endian float32
print(struct.unpack('>I', data))   # big-endian uint32
```

### Step 6: Implement in Python

Once you know which key controls the feature, add it to `make_state_packet()` in `src/kontrol_s88/protocol.py`:

```python
def make_state_packet(**kwargs) -> bytes:
    bpm = kwargs.get('tempo', 120.0)
    my_param = kwargs.get('my_param', default_value)
    # add the key to the msgpack map
```

---

## What We Know So Far

### Confirmed Working
- Handshake / PLUG-IN mode activation
- Tempo (key `120`, float32 BPM)

### Unknown Parameters in STATE packet

These keys were observed in Komplete Kontrol captures but not yet decoded:

| Key | Observed Values | Likely Purpose        |
|-----|----------------|-----------------------|
| 114 | None           | Unknown               |
| 115 | None           | Unknown               |
| 116 | `''` (empty string) | Unknown          |
| 117 | None           | Unknown               |
| 118 | None           | Unknown               |
| 119 | None           | Unknown               |
| 122 | None           | Unknown               |
| 123 | None           | Unknown               |
| 124 | True/False     | Unknown bool          |
| 125 | True/False     | Unknown bool          |
| 126 | None           | Unknown               |

### The Big Packet (packet 179 / HDR `93025892`)

During initialization, Komplete Kontrol sends a large packet (~256+ bytes) on the LIGHTS header (`93025892`). This likely controls the light guide initialization and possibly scale/arp defaults. This packet has not been fully decoded yet and is a priority for future work.

### Keepalive

Every ~8 seconds, a 72-byte packet is sent to endpoint 3. This is likely a keepalive/heartbeat. Its contents have not been analyzed.

---

## Suggested Next Features to Reverse Engineer

1. **Scale mode** — change the scale (Major, Minor, Chromatic, etc.) and root note
2. **Arp rate** — change the arpeggiator note division (1/4, 1/8, 1/16, etc.)
3. **Arp pattern** — Up, Down, Up-Down, etc.
4. **Light guide** — set individual key colors
5. **Display** — send text/graphics to the keyboard screen

To reverse engineer any of these, follow the methodology above: use Komplete Kontrol in the Windows VM, change the parameter, capture the traffic, decode the packets, find the changing key.

---

## Code Structure

```
src/kontrol_s88/
├── __init__.py      # Entry point and main() function
├── __main__.py      # Allows python -m kontrol_s88
├── protocol.py      # Packet construction (all reverse-engineered protocol knowledge lives here)
├── device.py        # USB connection management with auto-reconnect
└── tempo_sync.py    # MIDI pitchbend → BPM → S88 tempo sync daemon
```

---

## Running the Driver

```bash
# Install dependencies (Arch/CachyOS)
sudo pacman -S python-libusb1 python-msgpack python-rtmidi

# udev rule for non-root USB access
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="17cc", ATTRS{idProduct}=="2120", MODE="0666"' \
  | sudo tee /etc/udev/rules.d/99-ni-s88.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# Run
cd kontrol-s88-mk3-linux
PYTHONPATH=src python -m kontrol_s88
```

---

## Resources

- [NI Community thread: Receiving DIN MIDI clock on Kontrol S MK3](https://community.native-instruments.com/discussion/49953)
- [NI Community thread: Kontrol S-Series Mk3 Midi Sync in?](https://community.native-instruments.com/discussion/50167)
- [MessagePack spec](https://msgpack.org/index.html)
- [libusb1 Python docs](https://github.com/vpelletier/python-libusb1)
- [python-rtmidi docs](https://spotlightkid.github.io/python-rtmidi/)
