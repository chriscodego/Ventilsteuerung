"""Solenoid valve controller firmware for the Raspberry Pi Pico (MicroPython).

Implements the SAME line protocol as the relay firmware already installed on
the board (verified against the real device on 2026-08-28), so this file can
be flashed as a drop-in replacement without touching the GUI:

    PC -> Pico (one command per line, <target> <command>):
        R<n> ON|OFF     switch channel n (1-8)
        ALL ON|OFF      switch all channels at once
    Pico -> PC:
        OK <target> <command>   command executed
        ERR FORMAT              line is not exactly two tokens
        ERR CMD                 second token is not ON/OFF
        ERR TARGET              first token is not R1..R8 or ALL

Extensions beyond the original firmware (single-token commands the original
answers with ERR FORMAT, which the GUI tolerates):
        ID?      -> ID VENTILSTEUERUNG 1.0
        STATE?   -> STATE <bbbbbbbb>   (live state feedback for the GUI)

On boot all channels are off. On connection loss the outputs keep their last
commanded state; the GUI is responsible for warning the user.

NOTE on wiring (verified 2026-08-28): relay ON = valve CLOSED, relay OFF =
valve OPEN. The protocol and this firmware speak in relay states; the GUI
(GUI/gui.py, RELAY_ON_MEANS_OPEN) maps them to logical valve states.
"""

import sys
import uselect
from machine import Pin

VERSION = "1.0"

# GPIO pins driving the 8 valve outputs (via MOSFET/relay driver, active high).
VALVE_PINS = [2, 3, 4, 5, 6, 7, 8, 9]

# Onboard LED: on = at least one channel on, off = all off.
try:
    led = Pin("LED", Pin.OUT)
except TypeError:
    led = Pin(25, Pin.OUT)

valves = [Pin(n, Pin.OUT, value=0) for n in VALVE_PINS]
states = [0] * len(valves)

VALID_TARGETS = {"R%d" % (i + 1): i for i in range(len(valves))}


def send(line):
    sys.stdout.write(line + "\r\n")


def send_state():
    send("STATE " + "".join(str(s) for s in states))


def set_channel(index, value):
    states[index] = value
    valves[index].value(value)
    led.value(1 if any(states) else 0)


def handle_line(line):
    parts = line.strip().split()
    if len(parts) == 1:
        # Extensions for the GUI; the original firmware replies ERR FORMAT here.
        word = parts[0].upper()
        if word == "ID?":
            send("ID VENTILSTEUERUNG " + VERSION)
        elif word == "STATE?":
            send_state()
        else:
            send("ERR FORMAT")
        return
    if len(parts) != 2:
        send("ERR FORMAT")
        return

    target, command = parts[0].upper(), parts[1].upper()
    if command not in ("ON", "OFF"):
        send("ERR CMD")
        return
    value = 1 if command == "ON" else 0

    if target == "ALL":
        for i in range(len(valves)):
            set_channel(i, value)
        send("OK ALL " + command)
    elif target in VALID_TARGETS:
        set_channel(VALID_TARGETS[target], value)
        send("OK " + target + " " + command)
    else:
        send("ERR TARGET")


def main():
    for i in range(len(valves)):  # safe state on boot
        set_channel(i, 0)

    poller = uselect.poll()
    poller.register(sys.stdin, uselect.POLLIN)
    buffer = ""

    while True:
        if poller.poll(100):
            char = sys.stdin.read(1)
            if char is None:
                continue
            if char in ("\n", "\r"):
                if buffer:
                    handle_line(buffer)
                    buffer = ""
            else:
                buffer += char
                if len(buffer) > 128:  # guard against garbage input
                    buffer = ""


main()
