"""
USB device connection manager for the NI Kontrol S88 MK3.
Handles connection, disconnection, and automatic reconnection.
"""

import usb1
import time
import threading
from .protocol import (
    VENDOR_ID, PRODUCT_ID, INTERFACE, ENDPOINT_OUT,
    make_handshake_packet, make_init_packet, make_state_packet
)


class S88Device:
    """
    Manages the USB connection to the NI Kontrol S88 MK3.
    Automatically reconnects if the keyboard is unplugged and replugged.
    """

    def __init__(self, on_connect=None, on_disconnect=None):
        self._handle = None
        self._ctx = None
        self._lock = threading.Lock()
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._reconnect_thread = None
        self._running = False

    def connect(self) -> bool:
        """Attempt to connect to the S88. Returns True on success."""
        try:
            self._ctx = usb1.USBContext()
            self._handle = self._ctx.openByVendorIDAndProductID(VENDOR_ID, PRODUCT_ID)
            if self._handle is None:
                return False
            try:
                self._handle.detachKernelDriver(INTERFACE)
            except Exception:
                pass
            self._handle.claimInterface(INTERFACE)
            self._handle.bulkWrite(ENDPOINT_OUT, make_handshake_packet())
            self._handle.bulkWrite(ENDPOINT_OUT, make_init_packet())
            print("Connected to Kontrol S88 MK3")
            if self._on_connect:
                self._on_connect()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self._handle = None
            return False

    def disconnect(self):
        """Release the USB interface."""
        try:
            if self._handle:
                self._handle.releaseInterface(INTERFACE)
                self._handle = None
            if self._ctx:
                self._ctx = None
        except Exception:
            pass
        if self._on_disconnect:
            self._on_disconnect()

    def send_state(self, **kwargs) -> bool:
        """Send a state update packet. Returns True on success."""
        with self._lock:
            if self._handle is None:
                return False
            try:
                self._handle.bulkWrite(ENDPOINT_OUT, make_state_packet(**kwargs))
                return True
            except Exception as e:
                print(f"Send failed: {e}")
                self._handle = None
                self._start_reconnect()
                return False

    def set_tempo(self, bpm: float) -> bool:
        """Set the arpeggiator tempo in BPM."""
        return self.send_state(tempo=bpm)

    def _start_reconnect(self):
        """Start background reconnection thread."""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
        self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self._reconnect_thread.start()

    def _reconnect_loop(self):
        """Keep trying to reconnect every 2 seconds."""
        print("Disconnected. Attempting to reconnect...")
        while self._running and self._handle is None:
            time.sleep(2)
            self.connect()

    def start(self):
        """Connect and begin managing the device."""
        self._running = True
        if not self.connect():
            self._start_reconnect()

    def stop(self):
        """Stop the device manager and disconnect."""
        self._running = False
        self.disconnect()

    @property
    def connected(self) -> bool:
        return self._handle is not None
