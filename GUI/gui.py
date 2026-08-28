"""Magnetventilsteuerung — desktop GUI.

Controls 8 solenoid valves on a Raspberry Pi Pico over USB serial.
Companion firmware: Pico/main.py (line-based text protocol, see there).

Features:
    - Auto-detect of the Pico COM port (ID? handshake), auto-reconnect
    - Manual toggle per valve with live state feedback from the Pico
    - Timed sequence programs stored in programs.json (create/edit/run)
    - Emergency stop button applying the safe state from emergency.json

Run with:  python GUI/gui.py
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
from pathlib import Path
from tkinter import messagebox, ttk

import serial
import serial.tools.list_ports

__version__ = "1.0.0"

VALVE_COUNT = 8
# Display names per valve channel; valves 6-8 are unused and hidden in the UI.
VALVE_NAMES = [
    "Vakuum",
    "Ausgang NMR-Röhrchen",
    "Para H2",
    "Argon",
    "Auslass NMR-Röhrchen",
    "Ventil 6",
    "Ventil 7",
    "Ventil 8",
]
VISIBLE_VALVE_COUNT = 5
BAUDRATE = 115200
POLL_INTERVAL_MS = 1000
RECONNECT_INTERVAL_MS = 3000

# GitHub repository whose releases serve as the update channel.
UPDATE_REPO = "chriscodego/Ventilsteuerung"

if getattr(sys, "frozen", False):  # running as a PyInstaller bundle
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
PROGRAMS_FILE = BASE_DIR / "programs.json"
EMERGENCY_FILE = BASE_DIR / "emergency.json"

COLOR_OPEN = "#2e9e44"
COLOR_CLOSED = "#9a9a9a"
COLOR_UNKNOWN = "#d0d0d0"

# On this hardware relay ON = valve CLOSED (verified 2026-08-28). The GUI and
# the JSON files think in valve states (1 = open); this flag maps them to
# relay commands. Set to True if the wiring ever changes to ON = open.
RELAY_ON_MEANS_OPEN = False


def relay_state(valve_open: int) -> int:
    """Map a logical valve state to a relay state (and back — symmetric)."""
    return valve_open if RELAY_ON_MEANS_OPEN else 1 - valve_open


# --------------------------------------------------------------------------- #
# Serial link
# --------------------------------------------------------------------------- #
class SerialLink:
    """Owns the serial port and a reader thread; thread-safe writes."""

    def __init__(self, incoming: queue.Queue[str]) -> None:
        self._incoming = incoming
        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None

    @property
    def connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def port_name(self) -> str:
        return self._serial.port if self._serial else ""

    @staticmethod
    def list_ports() -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    @staticmethod
    def probe(port: str) -> bool:
        """Check whether the valve/relay firmware answers on this port.

        The installed relay firmware knows no ID command, but answers every
        line with OK/ERR — a harmless PING therefore yields "ERR FORMAT".
        Our own Pico/main.py replies "ID VENTILSTEUERUNG"; both count.
        """
        try:
            with serial.Serial(port, BAUDRATE, timeout=1) as test:
                time.sleep(0.3)
                test.reset_input_buffer()
                test.write(b"PING\n")
                deadline = time.time() + 1.5
                while time.time() < deadline:
                    line = test.readline().decode("ascii", "ignore").strip()
                    if line.startswith(("ERR", "OK", "ID VENTILSTEUERUNG")):
                        return True
        except (OSError, serial.SerialException):
            pass
        return False

    def connect(self, port: str) -> None:
        self.disconnect()
        self._serial = serial.Serial(port, BAUDRATE, timeout=0.2)
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def disconnect(self) -> None:
        ser, self._serial = self._serial, None
        if ser is not None:
            try:
                ser.close()
            except (OSError, serial.SerialException):
                pass

    def send(self, command: str) -> bool:
        with self._lock:
            ser = self._serial
            if ser is None or not ser.is_open:
                return False
            try:
                ser.write((command + "\n").encode("ascii"))
                return True
            except (OSError, serial.SerialException):
                self.disconnect()
                return False

    def _read_loop(self) -> None:
        ser = self._serial
        buffer = b""
        while ser is not None and ser is self._serial:
            try:
                chunk = ser.read(64)
            except (OSError, serial.SerialException, TypeError):
                break
            if chunk:
                buffer += chunk
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    line = raw.decode("ascii", "ignore").strip()
                    if line:
                        self._incoming.put(line)
        self._incoming.put("__DISCONNECTED__")


# --------------------------------------------------------------------------- #
# JSON persistence
# --------------------------------------------------------------------------- #
def load_programs() -> list[dict]:
    try:
        data = json.loads(PROGRAMS_FILE.read_text(encoding="utf-8"))
        return list(data.get("programs", []))
    except (OSError, ValueError):
        return []


def save_programs(programs: list[dict]) -> None:
    PROGRAMS_FILE.write_text(
        json.dumps({"programs": programs}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_emergency_state() -> list[int]:
    try:
        data = json.loads(EMERGENCY_FILE.read_text(encoding="utf-8"))
        valves = [1 if v else 0 for v in data.get("valves", [])]
        if len(valves) == VALVE_COUNT:
            return valves
    except (OSError, ValueError):
        pass
    return [0] * VALVE_COUNT


# --------------------------------------------------------------------------- #
# Update check (GitHub releases)
# --------------------------------------------------------------------------- #
def parse_version(text: str) -> tuple[int, ...]:
    parts: list[int] = []
    for token in text.strip().lstrip("vV").split("."):
        digits = "".join(c for c in token if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def fetch_latest_release() -> tuple[str, str | None]:
    """Return (version, installer_url) of the newest GitHub release."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest",
        headers={"User-Agent": "Ventilsteuerung-Updater",
                 "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.load(response)
    version = str(data.get("tag_name", "")).lstrip("vV")
    installer_url = next(
        (asset["browser_download_url"] for asset in data.get("assets", [])
         if asset.get("name", "").lower().endswith(".exe")),
        None,
    )
    return version, installer_url


def download_file(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Ventilsteuerung-Updater"})
    with urllib.request.urlopen(request, timeout=60) as response, open(target, "wb") as out:
        while chunk := response.read(65536):
            out.write(chunk)


# --------------------------------------------------------------------------- #
# Step editor dialog
# --------------------------------------------------------------------------- #
class StepDialog(tk.Toplevel):
    """Edit one program step: valve states plus duration."""

    def __init__(self, parent: tk.Misc, step: dict | None = None) -> None:
        super().__init__(parent)
        self.title("Schritt bearbeiten")
        self.resizable(False, False)
        self.result: dict | None = None

        valves = (step or {}).get("valves", [0] * VALVE_COUNT)
        duration = (step or {}).get("duration_s", 1.0)

        self._vars = [tk.IntVar(value=valves[i]) for i in range(VALVE_COUNT)]
        grid = ttk.Frame(self, padding=10)
        grid.pack(fill="both", expand=True)
        ttk.Label(grid, text="Offene Ventile:").grid(row=0, column=0, columnspan=2, sticky="w")
        for i in range(VISIBLE_VALVE_COUNT):
            ttk.Checkbutton(grid, text=VALVE_NAMES[i], variable=self._vars[i]).grid(
                row=1 + i, column=0, columnspan=2, sticky="w", padx=4, pady=2
            )
        duration_row = 1 + VISIBLE_VALVE_COUNT
        ttk.Label(grid, text="Dauer (Sekunden):").grid(row=duration_row, column=0, sticky="w", pady=(8, 0))
        self._duration = ttk.Entry(grid, width=8)
        self._duration.insert(0, str(duration))
        self._duration.grid(row=duration_row, column=1, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(grid)
        buttons.grid(row=duration_row + 1, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(buttons, text="OK", command=self._accept).pack(side="left", padx=4)
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side="left", padx=4)

        self.grab_set()
        self.transient(parent)

    def _accept(self) -> None:
        try:
            duration = float(self._duration.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Ungültige Eingabe", "Die Dauer muss eine Zahl sein.", parent=self)
            return
        if duration <= 0:
            messagebox.showerror("Ungültige Eingabe", "Die Dauer muss größer als 0 sein.", parent=self)
            return
        self.result = {"valves": [v.get() for v in self._vars], "duration_s": duration}
        self.destroy()


# --------------------------------------------------------------------------- #
# Program editor dialog
# --------------------------------------------------------------------------- #
class ProgramDialog(tk.Toplevel):
    """Create or edit a timed program (name, loop flag, step list)."""

    def __init__(self, parent: tk.Misc, program: dict | None = None) -> None:
        super().__init__(parent)
        self.title("Programm bearbeiten")
        self.resizable(False, False)
        self.result: dict | None = None
        self._steps: list[dict] = [dict(s) for s in (program or {}).get("steps", [])]

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky="w")
        self._name = ttk.Entry(frame, width=32)
        self._name.insert(0, (program or {}).get("name", ""))
        self._name.grid(row=0, column=1, columnspan=2, sticky="we", pady=2)

        self._loop = tk.IntVar(value=1 if (program or {}).get("loop") else 0)
        ttk.Checkbutton(frame, text="Endlos wiederholen", variable=self._loop).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=2
        )

        self._listbox = tk.Listbox(frame, width=52, height=10)
        self._listbox.grid(row=2, column=0, columnspan=3, pady=6)

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=3)
        ttk.Button(buttons, text="Schritt hinzufügen", command=self._add_step).pack(side="left", padx=2)
        ttk.Button(buttons, text="Bearbeiten", command=self._edit_step).pack(side="left", padx=2)
        ttk.Button(buttons, text="Entfernen", command=self._remove_step).pack(side="left", padx=2)

        confirm = ttk.Frame(frame)
        confirm.grid(row=4, column=0, columnspan=3, pady=(10, 0))
        ttk.Button(confirm, text="Speichern", command=self._accept).pack(side="left", padx=4)
        ttk.Button(confirm, text="Abbrechen", command=self.destroy).pack(side="left", padx=4)

        self._refresh()
        self.grab_set()
        self.transient(parent)

    @staticmethod
    def _describe(step: dict) -> str:
        open_valves = [VALVE_NAMES[i] for i, v in enumerate(step["valves"]) if v]
        label = ", ".join(open_valves) if open_valves else "alle zu"
        return f"Ventile offen: {label}  —  {step['duration_s']:g} s"

    def _refresh(self) -> None:
        self._listbox.delete(0, "end")
        for i, step in enumerate(self._steps, 1):
            self._listbox.insert("end", f"{i}. {self._describe(step)}")

    def _selected_index(self) -> int | None:
        selection = self._listbox.curselection()
        return selection[0] if selection else None

    def _add_step(self) -> None:
        dialog = StepDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            self._steps.append(dialog.result)
            self._refresh()

    def _edit_step(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        dialog = StepDialog(self, self._steps[index])
        self.wait_window(dialog)
        if dialog.result:
            self._steps[index] = dialog.result
            self._refresh()

    def _remove_step(self) -> None:
        index = self._selected_index()
        if index is not None:
            del self._steps[index]
            self._refresh()

    def _accept(self) -> None:
        name = self._name.get().strip()
        if not name:
            messagebox.showerror("Ungültige Eingabe", "Bitte einen Programmnamen angeben.", parent=self)
            return
        if not self._steps:
            messagebox.showerror("Ungültige Eingabe", "Das Programm braucht mindestens einen Schritt.", parent=self)
            return
        self.result = {"name": name, "loop": bool(self._loop.get()), "steps": self._steps}
        self.destroy()


# --------------------------------------------------------------------------- #
# Main application
# --------------------------------------------------------------------------- #
class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Magnetventilsteuerung v{__version__}")
        self.resizable(False, False)

        self._incoming: queue.Queue[str] = queue.Queue()
        self._link = SerialLink(self._incoming)
        self._states: list[int | None] = [None] * VALVE_COUNT
        self._programs = load_programs()
        self._running_program: dict | None = None
        self._program_step_index = 0
        self._program_job: str | None = None
        self._auto_reconnect = True
        self._connecting = False
        self._last_port: str | None = None
        self._expect_disconnect = False

        self._build_ui()
        self._refresh_program_list()
        self.after(100, self._process_incoming)
        self.after(POLL_INTERVAL_MS, self._poll_state)
        self.after(500, self._try_autoconnect)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        # Menu bar
        menubar = tk.Menu(self)
        self._connection_menu = tk.Menu(menubar, tearoff=0)
        self._connection_menu.add_command(
            label="Gerät suchen …", accelerator="Strg+F", command=self._search_device
        )
        self._connection_menu.add_command(
            label="Erneut verbinden", accelerator="F5", command=self._reconnect, state="disabled"
        )
        self._connection_menu.add_command(
            label="Verbindung trennen", command=self._disconnect_clicked, state="disabled"
        )
        self._connection_menu.add_separator()
        self._connection_menu.add_command(label="Beenden", command=self._on_close)
        menubar.add_cascade(label="Verbindung", menu=self._connection_menu)
        self._help_menu = tk.Menu(menubar, tearoff=0)
        self._help_menu.add_command(label="Nach Updates suchen …", command=self._check_for_updates)
        menubar.add_cascade(label="Hilfe", menu=self._help_menu)
        self.config(menu=menubar)
        self.bind("<Control-f>", lambda _e: self._search_device())
        self.bind("<F5>", lambda _e: self._reconnect())

        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        # Valve grid
        valves = ttk.LabelFrame(root, text="Ventile", padding=8)
        valves.pack(fill="x", pady=(0, 8))
        self._valve_indicators: list[tk.Canvas] = []
        self._valve_buttons: list[ttk.Button] = []
        for i in range(VISIBLE_VALVE_COUNT):
            cell = ttk.Frame(valves, padding=4)
            cell.grid(row=i // 3, column=i % 3, padx=6, pady=4)
            ttk.Label(cell, text=VALVE_NAMES[i]).pack()
            indicator = tk.Canvas(cell, width=26, height=26, highlightthickness=0)
            indicator.create_oval(3, 3, 23, 23, fill=COLOR_UNKNOWN, outline="#555", tags="lamp")
            indicator.pack(pady=2)
            button = ttk.Button(cell, text="Öffnen", width=10,
                                command=lambda idx=i: self._toggle_valve(idx))
            button.pack()
            self._valve_indicators.append(indicator)
            self._valve_buttons.append(button)

        # Programs
        programs = ttk.LabelFrame(root, text="Programme (programs.json)", padding=8)
        programs.pack(fill="x", pady=(0, 8))
        self._program_list = tk.Listbox(programs, width=44, height=6, exportselection=False)
        self._program_list.grid(row=0, column=0, rowspan=5, padx=(0, 8))
        ttk.Button(programs, text="Start", command=self._start_program).grid(row=0, column=1, sticky="we", pady=1)
        ttk.Button(programs, text="Stopp", command=self._stop_program).grid(row=1, column=1, sticky="we", pady=1)
        ttk.Button(programs, text="Neu…", command=self._new_program).grid(row=2, column=1, sticky="we", pady=1)
        ttk.Button(programs, text="Bearbeiten…", command=self._edit_program).grid(row=3, column=1, sticky="we", pady=1)
        ttk.Button(programs, text="Löschen", command=self._delete_program).grid(row=4, column=1, sticky="we", pady=1)
        self._program_status = ttk.Label(programs, text="Kein Programm aktiv")
        self._program_status.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # Emergency stop
        self._emergency_button = tk.Button(
            root, text="NOT-AUS", font=("Segoe UI", 16, "bold"),
            bg="#c62828", fg="white", activebackground="#a11212", activeforeground="white",
            command=self._emergency_stop, height=2,
        )
        self._emergency_button.pack(fill="x")

        # Status bar
        self._status_label = ttk.Label(
            root, text="Nicht verbunden", foreground="#b00000", anchor="w"
        )
        self._status_label.pack(fill="x", pady=(8, 0))

    # ------------------------------------------------------- connection ----
    def _set_status(self, text: str, ok: bool) -> None:
        self._status_label.config(text=text, foreground="#1a7a1a" if ok else "#b00000")

    def _update_menu_state(self) -> None:
        connected = self._link.connected
        self._connection_menu.entryconfig(
            "Erneut verbinden",
            state="normal" if (self._last_port and not connected) else "disabled",
        )
        self._connection_menu.entryconfig(
            "Verbindung trennen", state="normal" if connected else "disabled"
        )

    def _search_device(self) -> None:
        self._auto_reconnect = True
        if self._link.connected:
            self._set_status(f"Verbunden ({self._link.port_name})", ok=True)
            return
        self._try_autoconnect()

    def _reconnect(self) -> None:
        if self._link.connected or not self._last_port:
            return
        self._auto_reconnect = True
        self._connect_to(self._last_port)

    def _disconnect_clicked(self) -> None:
        if not self._link.connected:
            return
        self._auto_reconnect = False
        self._expect_disconnect = True
        self._link.disconnect()
        self._on_disconnected("Getrennt")

    def _connect_to(self, port: str) -> None:
        try:
            self._link.connect(port)
        except (OSError, serial.SerialException) as exc:
            self._set_status(f"Fehler an {port}: {exc}", ok=False)
            self._update_menu_state()
            return
        self._last_port = port
        self._update_menu_state()
        self._set_status(f"Verbunden ({port})", ok=True)
        # The relay firmware has no state query — establish a defined state.
        self._send_states([0] * VALVE_COUNT)
        self._program_status.config(text="Verbunden — Grundzustand gesetzt (alle Ventile zu)")

    def _try_autoconnect(self) -> None:
        """Scan all ports for the firmware in a background thread."""
        if self._link.connected or self._connecting or not self._auto_reconnect:
            return
        self._connecting = True
        self._set_status("Suche Pico…", ok=False)

        def worker() -> None:
            found = next((p for p in SerialLink.list_ports() if SerialLink.probe(p)), None)
            self.after(0, lambda: self._autoconnect_done(found))

        threading.Thread(target=worker, daemon=True).start()

    def _autoconnect_done(self, port: str | None) -> None:
        self._connecting = False
        if self._link.connected:
            return
        if port:
            self._connect_to(port)
        else:
            self._set_status("Pico nicht gefunden — Verbindung wird weiter gesucht", ok=False)
            if self._auto_reconnect:
                self.after(RECONNECT_INTERVAL_MS, self._try_autoconnect)

    def _on_disconnected(self, reason: str) -> None:
        self._update_menu_state()
        self._set_status(reason, ok=False)
        self._states = [None] * VALVE_COUNT
        self._update_valve_widgets()
        if self._running_program:
            self._stop_program()
            messagebox.showwarning(
                "Verbindung verloren",
                "Die Verbindung zum Pico wurde unterbrochen.\nDas laufende Programm wurde gestoppt.",
                parent=self,
            )
        if self._auto_reconnect:
            self.after(RECONNECT_INTERVAL_MS, self._try_autoconnect)

    # -------------------------------------------------------- incoming ----
    def _process_incoming(self) -> None:
        try:
            while True:
                line = self._incoming.get_nowait()
                if line == "__DISCONNECTED__":
                    if self._link.connected:
                        continue  # stale reader of a previous connection
                    if self._expect_disconnect:
                        self._expect_disconnect = False  # user chose Trennen
                        continue
                    self._on_disconnected("Verbindung verloren")
                elif line.startswith("OK "):
                    self._handle_ack(line.split()[1:])
                elif line.startswith("STATE "):
                    # Relay states from Pico/main.py — map to valve states.
                    bits = line.split(" ", 1)[1].strip()
                    if len(bits) == VALVE_COUNT and set(bits) <= {"0", "1"}:
                        self._states = [relay_state(int(c)) for c in bits]
                        self._update_valve_widgets()
                elif line == "ERR FORMAT":
                    pass  # relay firmware answering our STATE? keepalive
                elif line.startswith("ERR"):
                    self._set_status(line, ok=False)
        except queue.Empty:
            pass
        self.after(100, self._process_incoming)

    def _poll_state(self) -> None:
        # Keepalive; doubles as a state query once Pico/main.py is flashed.
        if self._link.connected:
            self._link.send("STATE?")
        self.after(POLL_INTERVAL_MS, self._poll_state)

    # ---------------------------------------------------------- valves ----
    def _handle_ack(self, parts: list[str]) -> None:
        """Track valve states from 'OK <target> <ON|OFF>' acknowledgements."""
        if len(parts) != 2 or parts[1] not in ("ON", "OFF"):
            return
        valve_state = relay_state(1 if parts[1] == "ON" else 0)
        if parts[0] == "ALL":
            self._states = [valve_state] * VALVE_COUNT
        elif parts[0].startswith("R") and parts[0][1:].isdigit():
            index = int(parts[0][1:]) - 1
            if 0 <= index < VALVE_COUNT:
                self._states[index] = valve_state
        self._update_valve_widgets()

    def _send_states(self, target_states: list[int]) -> bool:
        """Send the full valve pattern (logical states), using ALL where possible."""
        relay_states = [relay_state(v) for v in target_states]
        if all(r == 0 for r in relay_states):
            return self._link.send("ALL OFF")
        if all(r == 1 for r in relay_states):
            return self._link.send("ALL ON")
        return all(
            self._link.send(f"R{i + 1} {'ON' if r else 'OFF'}")
            for i, r in enumerate(relay_states)
        )

    def _update_valve_widgets(self) -> None:
        # Only the visible valves have widgets; hidden channels keep state silently.
        for i in range(len(self._valve_buttons)):
            state = self._states[i]
            color = COLOR_UNKNOWN if state is None else (COLOR_OPEN if state else COLOR_CLOSED)
            self._valve_indicators[i].itemconfig("lamp", fill=color)
            self._valve_buttons[i].config(text="Schließen" if state else "Öffnen")

    def _toggle_valve(self, index: int) -> None:
        if not self._link.connected:
            self._set_status("Nicht verbunden — Kommando nicht gesendet", ok=False)
            return
        current = self._states[index] or 0
        relay = relay_state(0 if current else 1)
        self._link.send(f"R{index + 1} {'ON' if relay else 'OFF'}")

    # -------------------------------------------------------- programs ----
    def _refresh_program_list(self) -> None:
        self._program_list.delete(0, "end")
        for program in self._programs:
            loop_marker = "  (Endlos)" if program.get("loop") else ""
            self._program_list.insert("end", f"{program['name']}{loop_marker}")

    def _selected_program_index(self) -> int | None:
        selection = self._program_list.curselection()
        return selection[0] if selection else None

    def _new_program(self) -> None:
        dialog = ProgramDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            self._programs.append(dialog.result)
            save_programs(self._programs)
            self._refresh_program_list()

    def _edit_program(self) -> None:
        index = self._selected_program_index()
        if index is None:
            return
        dialog = ProgramDialog(self, self._programs[index])
        self.wait_window(dialog)
        if dialog.result:
            self._programs[index] = dialog.result
            save_programs(self._programs)
            self._refresh_program_list()

    def _delete_program(self) -> None:
        index = self._selected_program_index()
        if index is None:
            return
        name = self._programs[index]["name"]
        if messagebox.askyesno("Programm löschen", f"„{name}“ wirklich löschen?", parent=self):
            del self._programs[index]
            save_programs(self._programs)
            self._refresh_program_list()

    def _start_program(self) -> None:
        if self._running_program:
            messagebox.showinfo("Programm aktiv", "Es läuft bereits ein Programm — erst stoppen.", parent=self)
            return
        index = self._selected_program_index()
        if index is None:
            messagebox.showinfo("Kein Programm gewählt", "Bitte ein Programm aus der Liste auswählen.", parent=self)
            return
        if not self._link.connected:
            messagebox.showwarning("Nicht verbunden", "Keine Verbindung zum Pico.", parent=self)
            return
        self._running_program = self._programs[index]
        self._program_step_index = 0
        self._run_step()

    def _run_step(self) -> None:
        program = self._running_program
        if program is None:
            return
        steps = program["steps"]
        if self._program_step_index >= len(steps):
            if program.get("loop"):
                self._program_step_index = 0
            else:
                self._finish_program()
                return
        step = steps[self._program_step_index]
        if not self._send_states(step["valves"]):
            self._stop_program()
            return
        self._program_status.config(
            text=f"Läuft: {program['name']} — Schritt {self._program_step_index + 1}/{len(steps)}"
        )
        self._program_step_index += 1
        self._program_job = self.after(int(step["duration_s"] * 1000), self._run_step)

    def _finish_program(self) -> None:
        self._send_states([0] * VALVE_COUNT)
        self._running_program = None
        self._program_job = None
        self._program_status.config(text="Programm beendet — alle Ventile geschlossen")

    def _stop_program(self) -> None:
        if self._program_job is not None:
            self.after_cancel(self._program_job)
            self._program_job = None
        if self._running_program is not None:
            self._running_program = None
            self._send_states([0] * VALVE_COUNT)
            self._program_status.config(text="Programm gestoppt — alle Ventile geschlossen")

    # ------------------------------------------------------- emergency ----
    def _emergency_stop(self) -> None:
        if self._program_job is not None:
            self.after_cancel(self._program_job)
            self._program_job = None
        self._running_program = None
        safe_state = load_emergency_state()
        sent = self._send_states(safe_state)
        if sent:
            self._program_status.config(text="NOT-AUS ausgelöst — Sicherheitszustand gesetzt")
        else:
            messagebox.showerror(
                "NOT-AUS nicht gesendet",
                "Keine Verbindung zum Pico — der Not-Aus-Befehl konnte nicht gesendet werden!",
                parent=self,
            )

    # ---------------------------------------------------------- updates ----
    def _set_update_check_enabled(self, enabled: bool) -> None:
        self._help_menu.entryconfig(
            "Nach Updates suchen …", state="normal" if enabled else "disabled"
        )

    def _check_for_updates(self) -> None:
        self._set_update_check_enabled(False)
        self._program_status.config(text="Suche nach Updates…")

        def worker() -> None:
            try:
                version, url = fetch_latest_release()
            except Exception as exc:  # noqa: BLE001 - network errors of any kind
                error = str(exc)
                self.after(0, lambda: self._update_check_done(error=error))
                return
            self.after(0, lambda: self._update_check_done(version=version, url=url))

        threading.Thread(target=worker, daemon=True).start()

    def _update_check_done(self, version: str = "", url: str | None = None,
                           error: str | None = None) -> None:
        self._set_update_check_enabled(True)
        self._program_status.config(text="Kein Programm aktiv")
        if error is not None:
            messagebox.showerror(
                "Update-Prüfung fehlgeschlagen",
                f"Konnte nicht nach Updates suchen:\n{error}", parent=self,
            )
            return
        if not version:
            messagebox.showinfo(
                "Keine Updates", "Es wurde noch kein Release veröffentlicht.", parent=self,
            )
            return
        if parse_version(version) <= parse_version(__version__):
            messagebox.showinfo(
                "Kein Update",
                f"Du hast bereits die aktuellste Version (v{__version__}).", parent=self,
            )
            return
        if url is None:
            messagebox.showwarning(
                "Update verfügbar",
                f"Version v{version} ist verfügbar, enthält aber keinen Installer.\n"
                f"Bitte manuell aktualisieren:\nhttps://github.com/{UPDATE_REPO}/releases",
                parent=self,
            )
            return
        if messagebox.askyesno(
            "Update verfügbar",
            f"Version v{version} ist verfügbar (installiert: v{__version__}).\n\n"
            "Jetzt herunterladen und installieren?\n"
            "Die Anwendung wird dazu beendet und automatisch neu gestartet.",
            parent=self,
        ):
            self._download_and_install(version, url)

    def _download_and_install(self, version: str, url: str) -> None:
        self._set_update_check_enabled(False)
        self._program_status.config(text=f"Update v{version} wird heruntergeladen…")

        def worker() -> None:
            target = Path(tempfile.gettempdir()) / f"Ventilsteuerung-Setup-{version}.exe"
            try:
                download_file(url, target)
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                self.after(0, lambda: self._download_failed(error))
                return
            self.after(0, lambda: self._run_installer(target))

        threading.Thread(target=worker, daemon=True).start()

    def _download_failed(self, error: str) -> None:
        self._set_update_check_enabled(True)
        self._program_status.config(text="Kein Programm aktiv")
        messagebox.showerror("Download fehlgeschlagen", error, parent=self)

    def _run_installer(self, installer: Path) -> None:
        subprocess.Popen([str(installer), "/SILENT", "/CLOSEAPPLICATIONS"])
        self._on_close()

    # ----------------------------------------------------------- close ----
    def _on_close(self) -> None:
        self._auto_reconnect = False
        if self._running_program:
            self._stop_program()
        self._link.disconnect()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
