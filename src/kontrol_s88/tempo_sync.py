"""
MIDI-based tempo sync for the NI Kontrol S88 MK3.
Listens on a virtual MIDI port for pitchbend messages from VCV Rack
and syncs the S88 arpeggiator tempo in real time.

VCV Rack setup:
  1. Add a CV-MIDI module
  2. Set driver to JACK, device to 'S88 Tempo Sync'
  3. Connect Clocked's BPM CV output to the PW (pitchbend) input
"""

import rtmidi
import math
from .device import S88Device


VIRTUAL_PORT_NAME = "S88 Tempo Sync"
BPM_MIN = 20.0
BPM_MAX = 999.0


def pitchbend_to_bpm(pb: int) -> float:
    """
    Convert a 14-bit pitchbend value to BPM.
    VCV Rack CV-MIDI maps -5V..+5V to pitchbend 0..16383.
    Clocked's BPM CV output uses V/OCT scaling: BPM = 120 * 2^voltage
    """
    voltage = (pb / 16383.0 * 10.0) - 5.0
    bpm = 120.0 * (2.0 ** voltage)
    return max(BPM_MIN, min(BPM_MAX, bpm))


class TempoSync:
    """
    Listens for pitchbend MIDI messages and syncs S88 arpeggiator tempo.
    """

    def __init__(self, device: S88Device):
        self._device = device
        self._last_bpm = None
        self._midi_in = None

    def _on_midi(self, message, timestamp):
        msg = message[0]
        status = msg[0] & 0xF0

        if status == 0xE0:  # Pitchbend
            pb = msg[1] | (msg[2] << 7)
            bpm = round(pitchbend_to_bpm(pb))
            if bpm != self._last_bpm:
                self._last_bpm = bpm
                if self._device.connected:
                    self._device.set_tempo(float(bpm))
                    print(f"BPM: {bpm}")

    def start(self):
        """Open virtual MIDI port and start listening."""
        self._midi_in = rtmidi.MidiIn()
        self._midi_in.open_virtual_port(VIRTUAL_PORT_NAME)
        self._midi_in.set_callback(self._on_midi)
        self._midi_in.ignore_types(sysex=True, timing=True, active_sense=True)
        print(f"Listening on virtual MIDI port '{VIRTUAL_PORT_NAME}'")

    def stop(self):
        """Close the MIDI port."""
        if self._midi_in:
            self._midi_in.close_port()
            self._midi_in = None
