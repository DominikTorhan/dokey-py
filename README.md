# DoKey

DoKey is a keyboard mapping utility for Windows written in Python. It captures
keyboard events with a low-level Windows hook and translates them into actions
defined in YAML configuration files. A system tray icon reflects the current mode and optional
Tkinter windows provide help overlays, mouse navigation graphics and diagnostic
information.

## Features

- **Multiple modes** – Normal, Insert, Mouse and Off.
- **Single and two step mappings** described in `config.yaml`.
- **Mouse navigation** using positions from `mouse_config.yaml`.
- **Tray integration** with icons showing the active mode.
- **Logging** to `logs/dokey.log` via `TimedRotatingFileHandler`.

## Installation

DoKey has **no dependencies at all** — nothing to install, no venv, no `pip`.
With Python installed, just run it: the keyboard hook, tray icon, YAML reading
and window lookups are all implemented directly on `ctypes` and the standard
library.

Any Python 3 works, including 3.14. The only standard-library piece that isn't
always present is `tkinter`, used by the help, mouse and diagnostic overlays —
the python.org Windows installer includes it by default. Check with:

```bash
python -c "import tkinter"
```

## Running

Start the application from the repository root:

```bash
python main.py
```

Use `--plain` to run without GUI overlays. The tray icon will appear and you can
switch modes using the special key (Caps Lock by default).

## Configuration

- `app/config.yaml` – keyboard mappings and custom commands.
- `app/mouse_config.yaml` – coordinates for the mouse mode.
- Optional user overrides can be placed in `~/.dokey/user_config.yaml`.

## Local usage logs

DoKey writes local diagnostics and usage data under `logs/`. It sends no telemetry.

- `dokey.log`: timestamped diagnostics with a process session ID; seven daily
  rotations are kept. Unsupported virtual keys are reported once per key per
  session, while usage data still counts every press.
- `usage.jsonl`: one JSON object per usage event, including UTC timestamp,
  session ID, app version, and the effective configuration's SHA-256 fingerprint.
  Seven daily rotations are kept.
- `usage-summary-YYYY-MM-DD-<session>.json`: cumulative counts for one UTC day
  and process session. These are retained for 60 days. Sum counts across session
  files to get daily totals; each file is a snapshot, not an incremental batch.

Binding IDs identify the branch that actually handled the key: `common.j`,
`special.h`, `two_step.e.s`, `mouse.j`, or `control.help`, for example. Key names
are canonical enum names in lowercase (`d1`, `comma`, `equal`, etc.). Prefix
selections (`prefix.e`) and unsuccessful mappings have distinct action types;
exclude those when counting completed shortcut decisions.

Each binding event has a `repeat` flag inferred from physical down/up events.
Use `repeat: false` counts to compare deliberate presses, and `repeat: true`
counts to see held-key activity. Missed key-up events (for example around a
session lock) can affect that inference. Physical shortcuts and ordinary typing
that DoKey passes through are not recorded. Caps Lock bypass also isn't measured.

Session records and summaries contain the configured binding IDs and their
action types, plus which overlays are enabled. The fingerprint includes loaded
user overrides and mouse positions, but its source data is not written out.
Text-expansion contents and command lines are never included in usage records.

Other events record mode changes (`0` Off, `1` Normal, `2` Insert, `3` Mouse),
overlay visibility changes after their UI callbacks return, and command launch
results. Binding counts measure decisions, not proof that the target application
accepted the action. A successful command launch means the shell process started,
not that the command inside it succeeded. Overlay timestamps reflect deferred UI
work, so they can follow the triggering key by a short delay.

Summary snapshots are replaced atomically once per minute of activity, on day
changes, and on normal shutdown. A forced termination can lose counts since the
last snapshot; recent detailed records may still be available. A
`session_ended: false` summary is not proof of a crash (it can describe a running
session or a day before that session ended). All disk I/O runs on the logging
worker, with final flushing during shutdown.

## Tests

Run the unit tests with:

```bash
python -m unittest
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for
details.
