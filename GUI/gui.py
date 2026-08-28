"""Magnetventilsteuerung — desktop GUI.

Controls 8 solenoid valves on a Raspberry Pi Pico over USB serial.
Companion firmware: Pico/main.py (line-based text protocol, see there).

Features:
    - Auto-detect of the Pico COM port (ID? handshake), auto-reconnect
    - Manual toggle per valve with live state feedback from the Pico
    - Timed switching programs stored in programs.json: per-valve open/close
      actions with wait times (relative to the previous action or absolute
      from program start), edited inline via drag & drop, shown as a timeline
    - Run log with real timestamps in run_log.txt
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

__version__ = "1.1.0"

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
RUN_LOG_FILE = BASE_DIR / "run_log.txt"

# Timing modes of a program action.
MODE_DELAY = "delay"  # time_s counts from the previous action
MODE_START = "start"  # time_s counts from program start
MODE_LABELS = {MODE_DELAY: "nach voriger Aktion", MODE_START: "ab Programmstart"}
MODE_FROM_LABEL = {v: k for k, v in MODE_LABELS.items()}

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
def steps_to_actions(steps: list[dict]) -> list[dict]:
    """Convert the legacy step format (full valve pattern + hold time) to actions."""
    actions: list[dict] = []
    state = [0] * VALVE_COUNT
    t = 0.0
    for step in steps:
        for i, v in enumerate(step.get("valves", [])):
            v = 1 if v else 0
            if v != state[i]:
                actions.append(
                    {"valve": i, "open": bool(v), "mode": MODE_START, "time_s": round(t, 3)}
                )
                state[i] = v
        t += float(step.get("duration_s", 0.0))
    # The old runner closed everything when the cycle ended — keep that timing.
    for i, v in enumerate(state):
        if v:
            actions.append(
                {"valve": i, "open": False, "mode": MODE_START, "time_s": round(t, 3)}
            )
    return actions


def compute_schedule(actions: list[dict]) -> list[float]:
    """Planned timestamp (seconds from program start) of each action."""
    times: list[float] = []
    t = 0.0
    for action in actions:
        offset = max(0.0, float(action.get("time_s", 0.0)))
        t = offset if action.get("mode") == MODE_START else t + offset
        times.append(t)
    return times


def describe_action(action: dict) -> str:
    if action.get("wait"):
        return "Warten"
    if action.get("close_all"):
        return "Alle Ventile schließen"
    verb = "öffnen" if action.get("open") else "schließen"
    return f"{VALVE_NAMES[action['valve']]} {verb}"


def action_color(action: dict) -> str:
    if action.get("wait"):
        return "#1565c0"
    if action.get("close_all"):
        return "#455a64"
    return "#2e7d32" if action.get("open") else "#c62828"


def load_programs() -> list[dict]:
    try:
        data = json.loads(PROGRAMS_FILE.read_text(encoding="utf-8"))
        programs = list(data.get("programs", []))
    except (OSError, ValueError):
        return []
    for program in programs:
        if "actions" not in program and "steps" in program:
            program["actions"] = steps_to_actions(program.pop("steps"))
    return programs


def save_programs(programs: list[dict]) -> None:
    # Stamp every action with its planned timestamp from program start.
    for program in programs:
        for action, at in zip(program.get("actions", []), compute_schedule(program.get("actions", []))):
            action["at_s"] = round(at, 3)
    PROGRAMS_FILE.write_text(
        json.dumps({"programs": programs}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_run_log(text: str) -> None:
    """Append one line with a real timestamp to the run log."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(RUN_LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"{stamp}  {text}\n")
    except OSError:
        pass  # logging must never break valve control


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
# Timeline canvas
# --------------------------------------------------------------------------- #
class TimelineCanvas(tk.Canvas):
    """Graphical switching sequence: one row per valve, bars while open,
    markers at every switch point and an optional run cursor."""

    ROW_H = 24
    NAME_W = 150
    AXIS_H = 22
    PAD_TOP = 6
    PAD_RIGHT = 14

    def __init__(self, parent: tk.Misc, width: int = 480) -> None:
        height = self.PAD_TOP + VISIBLE_VALVE_COUNT * self.ROW_H + self.AXIS_H
        super().__init__(
            parent, width=width, height=height, bg="white",
            highlightthickness=1, highlightbackground="#bbbbbb",
        )
        self._width = width
        self._actions: list[dict] = []
        self._times: list[float] = []
        self._total = 0.0
        self._cursor: float | None = None
        self._message = "Keine Aktionen"
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event: tk.Event) -> None:
        if abs(event.width - self._width) > 2:
            self._width = event.width
            self._redraw()

    def show_actions(self, actions: list[dict], message: str = "Keine Aktionen") -> None:
        self._actions = [dict(a) for a in actions]
        self._times = compute_schedule(self._actions)
        self._total = max(self._times, default=0.0)
        self._message = message
        self._redraw()

    def total_seconds(self) -> float:
        return self._total

    # -- drawing ----------------------------------------------------------
    def _plot_bounds(self) -> tuple[int, int, int]:
        left = self.NAME_W
        right = max(self._width - self.PAD_RIGHT, left + 60)
        bottom = self.PAD_TOP + VISIBLE_VALVE_COUNT * self.ROW_H
        return left, right, bottom

    def _x_for(self, t: float) -> float:
        left, right, _ = self._plot_bounds()
        span = max(self._total, 1.0)
        return left + (min(max(t, 0.0), span) / span) * (right - left)

    @staticmethod
    def _tick_step(span: float) -> float:
        for step in (0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600):
            if span / step <= 8:
                return float(step)
        return 3600.0

    def set_cursor(self, t: float | None) -> None:
        self._cursor = t
        self.delete("cursor")
        if t is None:
            return
        left, right, bottom = self._plot_bounds()
        x = self._x_for(t)
        self.create_line(x, self.PAD_TOP - 2, x, bottom + 4,
                         fill="#d32f2f", width=2, tags="cursor")

    def _redraw(self) -> None:
        self.delete("all")
        left, right, bottom = self._plot_bounds()
        span = max(self._total, 1.0)

        # Row backgrounds and valve names
        for i in range(VISIBLE_VALVE_COUNT):
            y = self.PAD_TOP + i * self.ROW_H
            mid = y + self.ROW_H // 2
            if i % 2 == 0:
                self.create_rectangle(left, y + 1, right, y + self.ROW_H - 1,
                                      fill="#f5f5f5", outline="")
            self.create_text(left - 8, mid, text=VALVE_NAMES[i], anchor="e",
                             font=("Segoe UI", 8))
            self.create_line(left, mid, right, mid, fill="#e0e0e0")

        # Time axis
        self.create_line(left, bottom, right, bottom, fill="#888888")
        step = self._tick_step(span)
        t = 0.0
        while t <= span + 1e-9:
            x = self._x_for(t)
            self.create_line(x, bottom, x, bottom + 4, fill="#888888")
            self.create_text(x, bottom + 6, text=f"{t:g}s", anchor="n",
                             font=("Segoe UI", 7), fill="#555555")
            t += step

        if not self._actions:
            self.create_text((left + right) / 2,
                             self.PAD_TOP + (bottom - self.PAD_TOP) / 2,
                             text=self._message, fill="#999999",
                             font=("Segoe UI", 9, "italic"))
            self.set_cursor(self._cursor)
            return

        # Open intervals per valve (events in time order; sequence breaks ties)
        order = sorted(range(len(self._actions)), key=lambda k: (self._times[k], k))
        open_since: dict[int, float] = {}
        bars: list[tuple[int, float, float]] = []
        for k in order:
            action = self._actions[k]
            if action.get("close_all"):
                for valve, start in open_since.items():
                    bars.append((valve, start, self._times[k]))
                open_since.clear()
                continue
            valve = action.get("valve")
            if valve is None or valve >= VISIBLE_VALVE_COUNT:
                continue  # wait actions and hidden valves draw nothing
            if action.get("open"):
                open_since.setdefault(valve, self._times[k])
            else:
                start = open_since.pop(valve, None)
                if start is not None:
                    bars.append((valve, start, self._times[k]))
        for valve, start in open_since.items():
            bars.append((valve, start, self._total))

        for valve, start, end in bars:
            y = self.PAD_TOP + valve * self.ROW_H
            x1, x2 = self._x_for(start), max(self._x_for(end), self._x_for(start) + 2)
            self.create_rectangle(x1, y + 4, x2, y + self.ROW_H - 4,
                                  fill="#7cc47f", outline="#2e7d32")

        # Switch markers
        for k in order:
            action = self._actions[k]
            x = self._x_for(self._times[k])
            if action.get("close_all"):
                self.create_line(x, self.PAD_TOP, x, bottom, dash=(3, 2),
                                 fill="#455a64", width=2)
                continue
            valve = action.get("valve")
            if valve is None or valve >= VISIBLE_VALVE_COUNT:
                continue
            mid = self.PAD_TOP + valve * self.ROW_H + self.ROW_H // 2
            color = "#2e7d32" if action.get("open") else "#c62828"
            self.create_oval(x - 3, mid - 3, x + 3, mid + 3, fill=color, outline="white")

        self.set_cursor(self._cursor)


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
        self._program_jobs: list[str] = []
        self._cursor_job: str | None = None
        self._program_started_at = 0.0
        self._program_total_s = 0.0
        self._program_cycle = 1
        # Inline program editor state
        self._edit_actions: list[dict] = []
        self._edit_index: int | None = None
        self._edit_rows: list[ttk.Frame] = []
        self._edit_at_labels: list[ttk.Label] = []
        self._edit_dirty = False
        self._drag_data: dict | None = None
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
        self._menubar = menubar
        menubar.add_command(label="Nach Update suchen", command=self._check_for_updates)
        self.config(menu=menubar)
        self.bind("<Control-f>", lambda _e: self._search_device())
        self.bind("<F5>", lambda _e: self._reconnect())

        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        # Valve grid
        valves = ttk.LabelFrame(root, text="Ventile", padding=8)
        valves.pack(fill="x", pady=(0, 8))
        self._valve_indicators: list[tk.Canvas] = []
        for i in range(VISIBLE_VALVE_COUNT):
            cell = ttk.Frame(valves, padding=4)
            cell.grid(row=i // 3, column=i % 3, padx=6, pady=4)
            ttk.Label(cell, text=VALVE_NAMES[i]).pack()
            # The lamp itself is the switch: click to open/close the valve.
            indicator = tk.Canvas(cell, width=44, height=44, highlightthickness=0,
                                  cursor="hand2")
            indicator.create_oval(4, 4, 40, 40, fill=COLOR_UNKNOWN, outline="#555",
                                  width=2, tags="lamp")
            indicator.bind("<Button-1>", lambda _e, idx=i: self._toggle_valve(idx))
            indicator.pack(pady=2)
            self._valve_indicators.append(indicator)
        ttk.Button(
            valves, text="Alle Ventile schließen", command=self._close_all_valves
        ).grid(row=2, column=0, columnspan=3, sticky="we", padx=6, pady=(6, 2))
        valves.columnconfigure(0, weight=1)
        valves.columnconfigure(1, weight=1)
        valves.columnconfigure(2, weight=1)

        # Programs — one LabelFrame with two swappable pages: browse and edit
        programs = ttk.LabelFrame(root, text="Programme", padding=8)
        programs.pack(fill="x", pady=(0, 8))

        # --- browse page ---------------------------------------------------
        browse = ttk.Frame(programs)
        self._browse_frame = browse
        browse.pack(fill="x")
        browse.columnconfigure(0, weight=1)
        self._program_list = tk.Listbox(browse, width=44, height=6, exportselection=False)
        self._program_list.grid(row=0, column=0, rowspan=3, sticky="we", padx=(0, 8))
        self._program_list.bind("<<ListboxSelect>>", lambda _e: self._refresh_timeline())
        ttk.Button(browse, text="Neu…", command=self._new_program).grid(row=0, column=1, sticky="we", pady=1)
        ttk.Button(browse, text="Bearbeiten…", command=self._edit_program).grid(row=1, column=1, sticky="we", pady=1)
        ttk.Button(browse, text="Löschen", command=self._delete_program).grid(row=2, column=1, sticky="we", pady=1)
        ttk.Label(browse, text="Schaltreihenfolge:").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self._timeline = TimelineCanvas(browse)
        self._timeline.grid(row=4, column=0, columnspan=2, sticky="we", pady=(2, 0))
        run_buttons = ttk.Frame(browse)
        run_buttons.grid(row=5, column=0, columnspan=2, sticky="we", pady=(8, 0))
        run_buttons.columnconfigure(0, weight=1)
        run_buttons.columnconfigure(1, weight=1)
        tk.Button(
            run_buttons, text="Start", font=("Segoe UI", 12, "bold"),
            bg="#2e7d32", fg="white", activebackground="#1b5e20", activeforeground="white",
            command=self._start_program,
        ).grid(row=0, column=0, sticky="we", padx=(0, 4), ipady=4)
        tk.Button(
            run_buttons, text="Stopp", font=("Segoe UI", 12, "bold"),
            bg="#546e7a", fg="white", activebackground="#37474f", activeforeground="white",
            command=self._stop_program,
        ).grid(row=0, column=1, sticky="we", padx=(4, 0), ipady=4)
        self._program_status = ttk.Label(browse, text="Kein Programm aktiv")
        self._program_status.grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # --- edit page (hidden until Neu/Bearbeiten) -----------------------
        edit = ttk.Frame(programs)
        self._edit_frame = edit
        head = ttk.Frame(edit)
        head.pack(fill="x")
        ttk.Label(head, text="Name:").pack(side="left")
        self._edit_name = ttk.Entry(head, width=26)
        self._edit_name.pack(side="left", padx=(4, 12))
        self._edit_name.bind("<KeyRelease>", lambda _e: self._mark_edit_dirty())
        ttk.Label(head, text="Wiederholungen:").pack(side="left")
        self._edit_repeat = ttk.Spinbox(head, from_=1, to=999, width=4,
                                        command=self._mark_edit_dirty)
        self._edit_repeat.pack(side="left", padx=(4, 10))
        self._edit_repeat.bind("<KeyRelease>", lambda _e: self._mark_edit_dirty())
        self._edit_loop = tk.IntVar(value=0)
        ttk.Checkbutton(head, text="Endlos", variable=self._edit_loop,
                        command=self._on_loop_toggled).pack(side="left")

        palette = ttk.LabelFrame(edit, text="Bausteine — Chips in den Ablauf ziehen", padding=6)
        palette.pack(fill="x", pady=(8, 0))
        for i in range(VISIBLE_VALVE_COUNT):
            ttk.Label(palette, text=VALVE_NAMES[i]).grid(
                row=i, column=0, sticky="w", padx=(0, 10), pady=1
            )
            self._make_palette_chip(
                palette, "öffnen", {"valve": i, "open": True}
            ).grid(row=i, column=1, padx=2, pady=1)
            self._make_palette_chip(
                palette, "schließen", {"valve": i, "open": False}
            ).grid(row=i, column=2, padx=2, pady=1)
        ttk.Label(palette, text="Wartezeit").grid(
            row=VISIBLE_VALVE_COUNT, column=0, sticky="w", padx=(0, 10), pady=(6, 1)
        )
        self._make_palette_chip(palette, "warten", {"wait": True}).grid(
            row=VISIBLE_VALVE_COUNT, column=1, columnspan=2, sticky="we", padx=2, pady=(6, 1)
        )
        ttk.Label(palette, text="Alle Ventile").grid(
            row=VISIBLE_VALVE_COUNT + 1, column=0, sticky="w", padx=(0, 10), pady=1
        )
        self._make_palette_chip(palette, "alle schließen", {"close_all": True}).grid(
            row=VISIBLE_VALVE_COUNT + 1, column=1, columnspan=2, sticky="we", padx=2, pady=1
        )

        actions_box = ttk.LabelFrame(edit, text="Ablauf", padding=6)
        actions_box.pack(fill="x", pady=(8, 0))
        self._actions_box = actions_box
        self._actions_holder = ttk.Frame(actions_box)
        self._actions_holder.pack(fill="x")
        self._drop_indicator = tk.Frame(self._actions_holder, height=2, bg="#1a73e8")
        self._edit_hint = ttk.Label(
            self._actions_holder, foreground="#777777",
            text="Noch keine Aktionen — Ventil-Chips hierher ziehen.",
        )

        ttk.Label(edit, text="Vorschau der Schaltreihenfolge:").pack(anchor="w", pady=(8, 0))
        self._edit_timeline = TimelineCanvas(edit)
        self._edit_timeline.pack(fill="x", pady=(2, 0))

        edit_buttons = ttk.Frame(edit)
        edit_buttons.pack(fill="x", pady=(8, 0))
        edit_buttons.columnconfigure(0, weight=1)
        edit_buttons.columnconfigure(1, weight=1)
        tk.Button(
            edit_buttons, text="Speichern", font=("Segoe UI", 11, "bold"),
            bg="#2e7d32", fg="white", activebackground="#1b5e20", activeforeground="white",
            command=self._save_edit,
        ).grid(row=0, column=0, sticky="we", padx=(0, 4), ipady=2)
        ttk.Button(edit_buttons, text="Abbrechen", command=self._cancel_edit).grid(
            row=0, column=1, sticky="we", padx=(4, 0)
        )

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
            self._set_status("Verbunden (VentilSteuerung)", ok=True)
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
        self._set_status("Verbunden (VentilSteuerung)", ok=True)
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
        for i, indicator in enumerate(self._valve_indicators):
            state = self._states[i]
            color = COLOR_UNKNOWN if state is None else (COLOR_OPEN if state else COLOR_CLOSED)
            indicator.itemconfig("lamp", fill=color)

    def _toggle_valve(self, index: int) -> None:
        if not self._link.connected:
            self._set_status("Nicht verbunden — Kommando nicht gesendet", ok=False)
            return
        current = self._states[index] or 0
        relay = relay_state(0 if current else 1)
        self._link.send(f"R{index + 1} {'ON' if relay else 'OFF'}")

    def _close_all_valves(self) -> None:
        if not self._link.connected:
            self._set_status("Nicht verbunden — Kommando nicht gesendet", ok=False)
            return
        self._send_states([0] * VALVE_COUNT)

    # -------------------------------------------------------- programs ----
    def _refresh_program_list(self) -> None:
        self._program_list.delete(0, "end")
        for program in self._programs:
            repeat = max(1, int(program.get("repeat", 1)))
            if program.get("loop"):
                marker = "  (Endlos)"
            elif repeat > 1:
                marker = f"  (×{repeat})"
            else:
                marker = ""
            self._program_list.insert("end", f"{program['name']}{marker}")
        self._refresh_timeline()

    def _refresh_timeline(self) -> None:
        index = self._selected_program_index()
        if index is None:
            self._timeline.show_actions([], "Kein Programm ausgewählt")
        else:
            self._timeline.show_actions(self._programs[index].get("actions", []))

    def _selected_program_index(self) -> int | None:
        selection = self._program_list.curselection()
        return selection[0] if selection else None

    def _select_program(self, index: int) -> None:
        self._program_list.selection_clear(0, "end")
        self._program_list.selection_set(index)
        self._program_list.see(index)
        self._refresh_timeline()

    def _delete_program(self) -> None:
        index = self._selected_program_index()
        if index is None:
            return
        name = self._programs[index]["name"]
        if messagebox.askyesno("Programm löschen", f"„{name}“ wirklich löschen?", parent=self):
            del self._programs[index]
            save_programs(self._programs)
            self._refresh_program_list()

    # ---------------------------------------------------- inline editor ----
    def _new_program(self) -> None:
        self._open_editor(None)

    def _edit_program(self) -> None:
        index = self._selected_program_index()
        if index is None:
            return
        self._open_editor(index)

    def _open_editor(self, index: int | None) -> None:
        program = self._programs[index] if index is not None else None
        self._edit_index = index
        self._edit_actions = [dict(a) for a in (program or {}).get("actions", [])]
        self._edit_dirty = False
        self._edit_name.delete(0, "end")
        self._edit_name.insert(0, (program or {}).get("name", ""))
        self._edit_loop.set(1 if (program or {}).get("loop") else 0)
        self._edit_repeat.set(int((program or {}).get("repeat", 1)))
        self._edit_repeat.configure(state="disabled" if self._edit_loop.get() else "normal")
        self._browse_frame.pack_forget()
        self._edit_frame.pack(fill="x")
        self._rebuild_action_rows()
        self._edit_name.focus_set()

    def _close_editor(self) -> None:
        self._edit_frame.pack_forget()
        self._browse_frame.pack(fill="x")
        self._refresh_timeline()

    def _mark_edit_dirty(self) -> None:
        self._edit_dirty = True

    def _on_loop_toggled(self) -> None:
        self._edit_dirty = True
        self._edit_repeat.configure(state="disabled" if self._edit_loop.get() else "normal")

    def _edit_repeat_count(self) -> int:
        try:
            return max(1, int(float(self._edit_repeat.get().replace(",", "."))))
        except ValueError:
            return 1

    def _cancel_edit(self) -> None:
        if self._edit_dirty and not messagebox.askyesno(
            "Änderungen verwerfen",
            "Ungespeicherte Änderungen wirklich verwerfen?",
            parent=self,
        ):
            return
        self._close_editor()

    def _save_edit(self) -> None:
        name = self._edit_name.get().strip()
        if not name:
            messagebox.showerror(
                "Ungültige Eingabe", "Bitte einen Programmnamen angeben.", parent=self
            )
            return
        if not self._edit_actions:
            messagebox.showerror(
                "Ungültige Eingabe",
                "Das Programm braucht mindestens eine Aktion.",
                parent=self,
            )
            return
        program = {
            "name": name,
            "loop": bool(self._edit_loop.get()),
            "repeat": self._edit_repeat_count(),
            "actions": [dict(a) for a in self._edit_actions],
        }
        if self._edit_index is None:
            self._programs.append(program)
            new_index = len(self._programs) - 1
        else:
            self._programs[self._edit_index] = program
            new_index = self._edit_index
        save_programs(self._programs)
        self._refresh_program_list()
        self._close_editor()
        self._select_program(new_index)

    def _make_palette_chip(self, parent: tk.Misc, text: str, payload: dict) -> tk.Label:
        chip = tk.Label(
            parent, text=text,
            bg=action_color(payload), fg="white", padx=10, pady=2, relief="raised",
            bd=1, cursor="hand2", font=("Segoe UI", 9, "bold"),
        )
        chip.bind(
            "<ButtonPress-1>",
            lambda e, p=payload: self._drag_start(e, dict(p)),
        )
        chip.bind("<B1-Motion>", self._drag_motion)
        chip.bind("<ButtonRelease-1>", self._drag_release)
        return chip

    # -- drag & drop --------------------------------------------------------
    def _drag_start(self, event: tk.Event, payload: dict,
                    from_index: int | None = None) -> None:
        ghost = tk.Toplevel(self)
        ghost.overrideredirect(True)
        ghost.attributes("-topmost", True)
        tk.Label(ghost, text=describe_action(payload), bg=action_color(payload),
                 fg="white", padx=8, pady=2, font=("Segoe UI", 9, "bold")).pack()
        self._drag_data = {"payload": payload, "ghost": ghost, "from_index": from_index}
        self._drag_motion(event)

    def _drag_motion(self, event: tk.Event) -> None:
        data = self._drag_data
        if not data:
            return
        data["ghost"].geometry(f"+{event.x_root + 12}+{event.y_root + 8}")
        self._show_drop_indicator(self._drop_index_at(event.x_root, event.y_root))

    def _drop_index_at(self, x_root: int, y_root: int) -> int | None:
        """Insertion index in the action list for a pointer position, or None."""
        box = self._actions_box
        if not (box.winfo_rootx() - 10 <= x_root <= box.winfo_rootx() + box.winfo_width() + 10
                and box.winfo_rooty() - 10 <= y_root <= box.winfo_rooty() + box.winfo_height() + 30):
            return None
        for i, row in enumerate(self._edit_rows):
            if y_root < row.winfo_rooty() + row.winfo_height() / 2:
                return i
        return len(self._edit_rows)

    def _show_drop_indicator(self, index: int | None) -> None:
        self._drop_indicator.pack_forget()
        if index is None:
            return
        if index < len(self._edit_rows):
            self._drop_indicator.pack(fill="x", before=self._edit_rows[index])
        else:
            self._drop_indicator.pack(fill="x")

    def _drag_release(self, event: tk.Event) -> None:
        data = self._drag_data
        if not data:
            return
        self._drag_data = None
        data["ghost"].destroy()
        self._drop_indicator.pack_forget()
        index = self._drop_index_at(event.x_root, event.y_root)
        if index is None:
            return
        from_index = data["from_index"]
        if from_index is None:
            action = dict(data["payload"])
            action.setdefault("mode", MODE_DELAY)
            action.setdefault("time_s", 1.0)
            self._edit_actions.insert(index, action)
        else:
            if index in (from_index, from_index + 1):
                return  # dropped back onto its own position — nothing moved
            action = self._edit_actions.pop(from_index)
            if index > from_index:
                index -= 1
            self._edit_actions.insert(index, action)
        self._edit_dirty = True
        self._rebuild_action_rows()

    # -- action rows --------------------------------------------------------
    def _rebuild_action_rows(self) -> None:
        for row in self._edit_rows:
            row.destroy()
        self._edit_rows = []
        self._edit_at_labels = []
        self._edit_hint.pack_forget()
        self._drop_indicator.pack_forget()
        if not self._edit_actions:
            self._edit_hint.pack(anchor="w", pady=4)
        for i, action in enumerate(self._edit_actions):
            row = ttk.Frame(self._actions_holder)
            row.pack(fill="x", pady=1)
            handle = tk.Label(row, text="≡", cursor="fleur", padx=4, fg="#888888")
            handle.pack(side="left")
            number = ttk.Label(row, text=f"{i + 1}.", width=3)
            number.pack(side="left")
            chip = tk.Label(row, text=describe_action(action), fg="white",
                            bg=action_color(action), padx=6, cursor="fleur",
                            font=("Segoe UI", 9))
            chip.pack(side="left", padx=(0, 6))
            for widget in (handle, number, chip):
                widget.bind(
                    "<ButtonPress-1>",
                    lambda e, idx=i: self._drag_start(
                        e, dict(self._edit_actions[idx]), from_index=idx
                    ),
                )
                widget.bind("<B1-Motion>", self._drag_motion)
                widget.bind("<ButtonRelease-1>", self._drag_release)
            combo = ttk.Combobox(row, values=list(MODE_LABELS.values()),
                                 width=17, state="readonly")
            combo.set(MODE_LABELS.get(action.get("mode", MODE_DELAY),
                                      MODE_LABELS[MODE_DELAY]))
            combo.bind(
                "<<ComboboxSelected>>",
                lambda _e, idx=i, c=combo: self._on_mode_changed(idx, c),
            )
            combo.pack(side="left")
            entry = ttk.Entry(row, width=7, justify="right")
            entry.insert(0, f"{action.get('time_s', 0):g}")
            entry.bind(
                "<KeyRelease>",
                lambda _e, idx=i, w=entry: self._on_time_changed(idx, w),
            )
            entry.pack(side="left", padx=(4, 2))
            ttk.Label(row, text="s").pack(side="left")
            at_label = ttk.Label(row, text="", foreground="#555555", width=10)
            at_label.pack(side="left", padx=(8, 0))
            self._edit_at_labels.append(at_label)
            ttk.Button(row, text="✕", width=2,
                       command=lambda idx=i: self._remove_action(idx)).pack(side="right")
            self._edit_rows.append(row)
        self._update_edit_preview()

    def _on_mode_changed(self, index: int, combo: ttk.Combobox) -> None:
        self._edit_actions[index]["mode"] = MODE_FROM_LABEL[combo.get()]
        self._edit_dirty = True
        self._update_edit_preview()

    def _on_time_changed(self, index: int, entry: ttk.Entry) -> None:
        try:
            value = float(entry.get().replace(",", "."))
        except ValueError:
            value = -1.0
        if value >= 0:
            self._edit_actions[index]["time_s"] = value
            entry.configure(foreground="black")
            self._edit_dirty = True
            self._update_edit_preview()
        else:
            entry.configure(foreground="#c62828")

    def _remove_action(self, index: int) -> None:
        del self._edit_actions[index]
        self._edit_dirty = True
        self._rebuild_action_rows()

    def _update_edit_preview(self) -> None:
        times = compute_schedule(self._edit_actions)
        for label, t in zip(self._edit_at_labels, times):
            label.configure(text=f"→ {t:g} s")
        self._edit_timeline.show_actions(
            self._edit_actions, "Noch keine Aktionen im Ablauf"
        )

    # -------------------------------------------------------- run engine ----
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
        program = self._programs[index]
        if not program.get("actions"):
            messagebox.showinfo("Leeres Programm", "Das Programm enthält keine Aktionen.", parent=self)
            return
        self._running_program = program
        self._program_cycle = 1
        self._send_states([0] * VALVE_COUNT)  # defined base state
        append_run_log(f"Programm „{program['name']}“ gestartet")
        self._schedule_cycle()
        self._tick_run_cursor()

    def _schedule_cycle(self) -> None:
        """Schedule every action of the running program plus the cycle end."""
        program = self._running_program
        if program is None:
            return
        actions = program["actions"]
        times = compute_schedule(actions)
        self._program_total_s = max(times, default=0.0)
        self._program_started_at = time.monotonic()
        # Wait actions only shift the schedule and the cycle end — nothing to send.
        self._program_jobs = [
            self.after(int(t * 1000), lambda a=action, tt=t: self._exec_action(a, tt))
            for t, action in zip(times, actions)
            if not action.get("wait")
        ]
        end_ms = int(self._program_total_s * 1000) + 20
        self._program_jobs.append(self.after(end_ms, self._end_of_cycle))

    def _exec_action(self, action: dict, planned_t: float) -> None:
        if self._running_program is None:
            return
        if action.get("close_all"):
            ok = self._send_states([0] * VALVE_COUNT)
        else:
            relay = relay_state(1 if action.get("open") else 0)
            ok = self._link.send(f"R{action['valve'] + 1} {'ON' if relay else 'OFF'}")
        append_run_log(f"t=+{planned_t:g}s  {describe_action(action)}")
        if not ok:
            self._stop_program()

    def _end_of_cycle(self) -> None:
        program = self._running_program
        if program is None:
            return
        repeat = max(1, int(program.get("repeat", 1)))
        if program.get("loop") and self._program_total_s > 0:
            append_run_log(f"Programm „{program['name']}“: Zyklus beendet — wiederhole")
            self._schedule_cycle()
        elif self._program_cycle < repeat and self._program_total_s > 0:
            self._program_cycle += 1
            append_run_log(
                f"Programm „{program['name']}“: Zyklus {self._program_cycle}/{repeat} startet"
            )
            self._schedule_cycle()
        else:
            self._finish_program()

    def _tick_run_cursor(self) -> None:
        """Move the timeline cursor and update the status line while running."""
        program = self._running_program
        if program is None:
            return
        elapsed = min(time.monotonic() - self._program_started_at, self._program_total_s)
        index = self._selected_program_index()
        if index is not None and self._programs[index] is program:
            self._timeline.set_cursor(elapsed)
        else:
            self._timeline.set_cursor(None)
        repeat = max(1, int(program.get("repeat", 1)))
        if program.get("loop"):
            cycle_info = " (Endlos)"
        elif repeat > 1:
            cycle_info = f" — Zyklus {self._program_cycle}/{repeat}"
        else:
            cycle_info = ""
        self._program_status.config(
            text=f"Läuft: {program['name']}{cycle_info} — "
                 f"t = {elapsed:.1f} s / {self._program_total_s:g} s"
        )
        self._cursor_job = self.after(100, self._tick_run_cursor)

    def _cancel_program_jobs(self) -> None:
        for job in self._program_jobs:
            self.after_cancel(job)
        self._program_jobs = []
        if self._cursor_job is not None:
            self.after_cancel(self._cursor_job)
            self._cursor_job = None
        self._timeline.set_cursor(None)

    def _finish_program(self) -> None:
        name = self._running_program["name"] if self._running_program else ""
        self._running_program = None
        self._cancel_program_jobs()
        self._send_states([0] * VALVE_COUNT)
        append_run_log(f"Programm „{name}“ beendet — alle Ventile geschlossen")
        self._program_status.config(text="Programm beendet — alle Ventile geschlossen")

    def _stop_program(self) -> None:
        if self._running_program is None:
            return
        name = self._running_program["name"]
        self._running_program = None
        self._cancel_program_jobs()
        self._send_states([0] * VALVE_COUNT)
        append_run_log(f"Programm „{name}“ gestoppt — alle Ventile geschlossen")
        self._program_status.config(text="Programm gestoppt — alle Ventile geschlossen")

    # ------------------------------------------------------- emergency ----
    def _emergency_stop(self) -> None:
        if self._running_program is not None:
            append_run_log(f"NOT-AUS während Programm „{self._running_program['name']}“")
            self._running_program = None
        self._cancel_program_jobs()
        safe_state = load_emergency_state()
        sent = self._send_states(safe_state)
        if sent:
            append_run_log("NOT-AUS ausgelöst — Sicherheitszustand gesetzt")
            self._program_status.config(text="NOT-AUS ausgelöst — Sicherheitszustand gesetzt")
        else:
            messagebox.showerror(
                "NOT-AUS nicht gesendet",
                "Keine Verbindung zum Pico — der Not-Aus-Befehl konnte nicht gesendet werden!",
                parent=self,
            )

    # ---------------------------------------------------------- updates ----
    def _set_update_check_enabled(self, enabled: bool) -> None:
        self._menubar.entryconfig(
            "Nach Update suchen", state="normal" if enabled else "disabled"
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
