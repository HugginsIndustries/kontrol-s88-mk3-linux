"""
kontrol-s88-mk3-linux
----------------------
Unofficial Linux driver for the Native Instruments Kontrol S88 MK3.
Provides tempo sync and (future) full keyboard control via the
reverse-engineered HID/MessagePack protocol.

Usage:
    python -m kontrol_s88

GitHub: https://github.com/HugginsIndustries/kontrol-s88-mk3-linux
"""

from .device import S88Device
from .tempo_sync import TempoSync
import time


def main():
    device = S88Device()
    sync = TempoSync(device)

    device.start()
    sync.start()

    print("Kontrol S88 MK3 Linux Driver")
    print("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        sync.stop()
        device.stop()


if __name__ == "__main__":
    main()
