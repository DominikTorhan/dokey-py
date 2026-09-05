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

## Tests

Run the unit tests with:

```bash
python -m unittest
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for
details.
