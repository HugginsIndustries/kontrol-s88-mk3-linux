# kontrol-s88-mk3-linux

Unofficial Linux driver for the **Native Instruments Kontrol S88 MK3**.

NI does not support Linux and intentionally limits MIDI mode functionality (no external clock sync, no arp control). This project reverse engineers the proprietary HID/MessagePack protocol used by Komplete Kontrol to enable full keyboard control on Linux.

## Current Features

- **Tempo sync** — syncs the S88 arpeggiator BPM to VCV Rack (or any DAW) in real time via MIDI pitchbend

## Planned Features

- Scale mode control
- Arp pattern/rate control
- Light guide control
- Full standalone daemon with config file

## How It Works

The S88 MK3 operates in two modes:
- **MIDI mode** — standard USB MIDI, limited functionality (NI intentionally blocks clock sync and arp control)
- **PLUG-IN mode** — full HID control activated by sending a handshake packet over USB bulk endpoint 4

Communication uses **MessagePack**-encoded messages with an 8-byte header:
```
[length: 4 bytes LE] [message_type: 4 bytes] [msgpack payload...]
```

The protocol was reverse engineered using Wireshark + usbmon to capture traffic between Komplete Kontrol (running in a Windows VM) and the keyboard.

## Requirements

- Python 3.10+
- CachyOS / Arch Linux (other distros should work too)
- `python-libusb1` — `sudo pacman -S python-libusb1`
- `python-msgpack` — `sudo pacman -S python-msgpack`
- `python-rtmidi` — `sudo pacman -S python-rtmidi`

## Installation

### 1. udev rule (required for non-root USB access)
```bash
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="17cc", ATTRS{idProduct}=="2120", MODE="0666"' | sudo tee /etc/udev/rules.d/99-ni-s88.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 2. Clone and run
```bash
git clone https://github.com/HugginsIndustries/kontrol-s88-mk3-linux.git
cd kontrol-s88-mk3-linux
python -m kontrol_s88
```

## VCV Rack Setup (Tempo Sync)

1. Add a **CV-MIDI** module to your patch
2. Set driver to **JACK**, device to **S88 Tempo Sync**
3. Connect **Clocked's BPM CV output** to the **PW (pitchbend)** input on CV-MIDI
4. Run the daemon — the S88 arpeggiator will now follow your VCV Rack tempo in real time

## Contributing

This is an early-stage project. If you have an S88 MK3 (or S49/S61 MK3 — likely same protocol) and want to help reverse engineer more features, open an issue or PR!

## Disclaimer

This project is not affiliated with or endorsed by Native Instruments. Use at your own risk.

## License

MIT
