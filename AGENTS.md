# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this project is

DoKey is a **personal, actively used** keyboard remapper for **plain Windows** (no
AutoHotkey, no admin installer — just Python). It gives the keyboard modal
behaviour: a *special key* (Caps Lock) plus a Normal/Insert mode pair, so common
editing and navigation actions live on the home row instead of on arrows and
function keys.

It runs as a tray application (`main.py`), installs a low-level Windows keyboard
hook, decides what to do in pure-Python logic, and either swallows the keystroke,
sends different keystrokes, types text, clicks the mouse, or runs a shell command.
It has **no runtime dependencies** — everything below `app/` is stdlib plus
`ctypes`.

**This is a working tool the owner depends on daily. Prefer small, surgical,
reversible changes. Do not restructure the app "for cleanliness" unless asked.**

## Platform constraints — read before changing anything

- **Windows only at runtime.** `os_level/` uses `ctypes.WinDLL("User32.dll")`,
  `dwmapi`, `ctypes.windll.shcore.SetProcessDpiAwareness`, the `win32_event_filter`
  `SetWindowsHookExW`/`SendInput`, and Tk overlay windows. Importing anything from `os_level/`
  on Linux/macOS fails immediately.
- **Development often happens from WSL/Linux.** Only `app/` and `tests/` are
  importable there. Keep it that way: **never import `os_level` from `app/`.**
  The dependency direction is `main.py → os_level → app`, never the reverse.
- Deliberately **no build system, no packaging, no CI, no linter config, and no
  dependency file**. Don't introduce `pyproject.toml`, `requirements.txt`,
  tox, poetry, GitHub Actions, or type-checking config unless explicitly asked.
- **DoKey has zero dependencies**, runtime or dev, and that is a feature: it runs
  on a stock Python install with no venv and no `pip`. Everything it needs is
  implemented directly on `ctypes` and the standard library — the tray icon
  (`os_level/tray.py`, was pystray + Pillow), the process-name lookup
  (`windows_api.py`, was psutil), YAML reading (`app/yaml_lite.py`, was PyYAML)
  and the keyboard hook itself (`os_level/win_keyboard.py`, was pynput).
  **Don't add a dependency of any kind without asking.**
- Code follows **black**'s style — 4-space indent, double quotes, 88-column lines,
  magic trailing comma. black itself is not installed; match the style by hand.

## Layout

```
main.py                       entrypoint: logging, tray icon, wiring, --plain flag
app/                          pure logic, no Windows API — this is the testable core
  app.py                      App: orchestrates processor + UI side effects; ListenerABC, OSEvent
  key_processor.py            KeyProcessor.process(): the state machine (mutates AppState)
  app_state.py                AppState + mode constants OFF=0 NORMAL=1 INSERT=2 MOUSE=3
  config.py                   Config.from_file(): parses config.yaml + user overrides
  mouse_config.py             MouseConfig.from_file(): mouse grid positions
  keys.py                     Keys enum (values are Windows VK codes), name↔key map, FIRST_STEPS
  events.py                   Event / SendEvent / WriteEvent / CMDEvent / DoKeyEvent / MouseEvent
  modifs.py                   Modifs: ctrl/shift/alt/win flags
  version.py                  VERSION - single source of truth
  yaml_lite.py                minimal YAML reader for the config subset
  config.yaml                 the actual keymap
  mouse_config.yaml           mouse grid: key -> [x%, y%] of the active window
os_level/                     Windows-specific, not importable off Windows
  win_keyboard.py             WindowsListener: WH_KEYBOARD_LL hook, SendInput, mouse click
  windows_api.py              active window/process via user32 + dwmapi + kernel32 (ctypes only)
  draw_on_screen.py           WinImage: Tk help overlay (per active process)
  mouse_window.py             MouseImage: Tk mouse-grid overlay + coordinate math
  diagnostic_window.py        DiagnosticWindow: Tk state overlay
  tray.py                     TrayIcon: Shell_NotifyIcon tray icon + message pump
assets/                       tray icons, one per mode (+ normal_first_step)
tests/                        unittest; test_playlist.yaml is a data-driven state-machine table
```

## How a keystroke flows

1. `WindowsListener._on_key` is the `WH_KEYBOARD_LL` callback. `wParam` is
   `WM_KEYDOWN`/`WM_SYSKEYDOWN` (256/260) or `WM_KEYUP`/`WM_SYSKEYUP` (257/261),
   `lParam` points at a `KBDLLHOOKSTRUCT`.
2. It short-circuits in two cases: keystrokes DoKey injected itself
   (`dwExtraInfo == DOKEY_EXTRA_INFO`), and when **Caps Lock is toggled on**
   (`is_capslock_on()` → everything passes through untouched; this is the de-facto
   "temporarily disable DoKey" escape hatch).
3. It reads real OS modifier state via `GetAsyncKeyState` (`get_modif_state()`),
   builds an `OSEvent`, and calls `App.handle_keyboard_event`.
4. `App` delegates to `KeyProcessor.process()`, which **mutates `AppState`** and
   returns an event object.
5. `App` logs, then **queues** the slow side effects (tray icon, overlays,
   launching a `__command__`) for its worker thread, and returns the event
   immediately.
6. Back in the callback, `_perform()` does the fast part — `SendInput` for keys
   and text, the mouse click — and reports whether the key is swallowed.

**Suppression mechanism:** returning `1` from the hook callback swallows the key;
anything else falls through to `CallNextHookEx`. This is the documented mechanism
— there is no private-attribute hack any more.

**Recursion:** every input DoKey injects carries `DOKEY_EXTRA_INFO` in
`dwExtraInfo`, and the callback drops those on sight. That is what stops sent keys
from being re-processed; it replaces an older `is_sending` boolean, which could
not tell our own echo from a real key pressed at the same moment.

**The callback must stay fast.** Windows silently unhooks a low-level hook whose
callback overruns `LowLevelHooksTimeout` (300 ms by default,
`HKCU\Control Panel\Desktop`) — DoKey keeps running but stops remapping, with
nothing in the log. That is why `App._defer_side_effects` exists: creating a Tk
overlay or spawning a command is far too slow to do inline. **Never add slow work
to `handle_keyboard_event` or to `_perform`** — put it on the queue. The decision
itself must stay synchronous, because the return value determines suppression.
`tests/test_side_effects.py` pins both halves of that.

## KeyProcessor: order matters

`KeyProcessor.process()` is a fixed sequence of early-returns. Inserting a step in
the wrong place silently changes the whole keymap. Current order:

1. special key (Caps Lock) down/up → mode restore, `is_special_down`
2. real modifier keys → update `Modifs`
3. sync modifiers from OS (`_try_update_modifs_by_os` — needed because `Win+L`
   locks the machine and the Win key-up event is never delivered)
4. help key, diagnostics key
5. key-up → nothing further
6. mode change (`off_mode_key`, `change_mode_key`, `mouse_mode_key`, all with special held)
7. mouse click (in MOUSE mode)
8. single step (NORMAL mode, no first step pending)
9. two-step (a first step is pending)
10. DoKey commands (`exit_key`, `clear_screen_key`, with special held)
11. special + key → `special:` section of config

`prevent_prev_mode_on_special_up` exists so that using the special key as a
*modifier* in Insert mode (e.g. Caps+H = Backspace) does not fall back to Normal
mode when Caps is released.

## config.yaml

Top level:

- `special_key`, `change_mode_key`, `off_mode_key`, `mouse_mode_key`,
  `clear_screen_key`, `exit_key`, `help_key`, `diagnostic_key`
- `special:` — mappings for *special key held* (works in Normal and Insert)
- `common:` — single-key mappings, Normal mode only (hjkl arrows, etc.)
- **every other top-level key is a two-step first step** (`f:`, `i:`, `d:`, `q:`,
  `w:`, `e:`, `r:`, `t:`, `g:`, `b:`, `a:` …)

Value syntax:

- `ctrl+shift+v` — one chord
- `up, end, enter` — a sequence of chords, sent in order
- `__command__<some command line>` — launched with `subprocess.Popen(shell=True)`
- `__write__<text>` — types the text literally

User overrides: `~/.dokey/user_config.yaml`, merged into two-step
sections only (`Config.try_load_users_config`). `~/.dokey/help.yaml`
holds the per-application help text shown by the help overlay, keyed by a
substring of the active process name.

## Gotchas that will bite you

- **Adding a new two-step first step needs two edits.** A new top-level section in
  `config.yaml` does nothing unless the key is also added to `FIRST_STEPS` in
  `app/keys.py`.
- **`Keys.from_string()` returns `None` for an unknown name**; it does not raise.
  A typo in `config.yaml` still produces a `None` key that can never match, so the
  binding silently does nothing — but it is now logged at error level. `Keys.NONE`
  would be worse: it would fold the typo into the "no first step" section.
- `CMDEvent` runs a string from config through a shell. **The config file is
  trusted input by design** — it is the owner's own keymap. Don't wire anything
  untrusted into that path, and keep `dokey_dir()` anchored to `Path.home()`
  rather than a bare env var.
- Overlay windows create a **second `tk.Tk()` root** on each draw and use
  `overrideredirect` + `-topmost` + `-transparentcolor blue`. That's fragile but
  works; be careful when touching it.
- **Nothing outside a `__main__` block may `print()`.** Under `pythonw.exe`
  `sys.stdout` is `None` and `print()` raises `AttributeError`; several of these
  used to sit on the help-overlay draw path. Log instead.
- The diagnostics overlay is attached **after** `App` is constructed
  (`app.diagnostics_interface = ...`), because `DiagnosticWindow` renders the live
  `AppState` and `App` owns it.

## Running

```bash
python main.py            # tray icon + overlays
python main.py --plain    # no Tk overlays (-p); still needs Windows for the hook
```

Logs: `logs/dokey.log`, daily rotation, 7 days kept (gitignored).
Console handler is at INFO; set the root level to DEBUG in `init_logging()` to see
every key event.

## Tests

```bash
python -m unittest
```

- `tests/test_key_processor.py` drives `KeyProcessor` from
  `tests/test_playlist.yaml`, a compact table of
  `input: "{mode},{firstStep},{modifs} {key} {up|down}"` →
  `output: "mode|firstStep|modifs|*|send|preventKeyProcess"`. **Adding a case here
  is the cheapest way to pin down state-machine behaviour** — prefer it over new
  Python test code.
- `tests/test_app.py` replays scripted key sequences through the real `App` with a
  fake `ListenerABC`.

The suite is green and runs **on Linux/WSL as well as Windows** — `app/` has no
platform imports, so the state machine is testable off Windows. Keep it that way:
if a change to `app/` makes `python3 -m unittest` fail to *import* on Linux, the
change is in the wrong layer.

`Config.dokey_dir()` resolves the user-override directory as `Path.home() /
".dokey"`, which is what allows the above. Deliberately *not* `%HOMEPATH%`: that
variable is drive-relative on Windows, so reading it directly would resolve
against whatever drive is current and could load a different user config.

## Versioning

`app/version.py` holds the single source of truth (`VERSION`). It is logged as the
first line of every run, so a `logs/dokey.log` always identifies the build that
produced it:

```
DoKey 1.2.1
init logging!
```

Releases are marked by tagging the merge commit on `main` with a matching `v`
prefix — bump `VERSION`, merge, then tag the merge commit `v<VERSION>`.
Keep the tag and `VERSION` in step.

## yaml_lite

`app/yaml_lite.py` reads the YAML subset the configs actually use: block mappings,
block sequences, flow sequences and mappings, quoted scalars, comments, and bare
integers. It deliberately does **not** support anchors, multi-line scalars, tags,
bool/float/null coercion, or a block mapping opened on a `-` line — those raise
`ValueError` rather than quietly producing a different structure.

`tests/test_yaml_lite.py` pins it against PyYAML on every YAML file in the repo,
plus the `~/.dokey` shapes that aren't in the repo. Those comparison tests skip
themselves when PyYAML isn't installed, so they keep working either way. **If you
extend the config format, add a case there first.**

## Working agreements

- Ask before changing `app/config.yaml` — it is the owner's live, hand-tuned keymap,
  not sample data.
- Keep `app/` free of Windows imports so the state machine stays testable off Windows.
- When changing key-handling behaviour, add or update a `test_playlist.yaml` row.
- Follow the global rules in `~/.claude/CLAUDE.md`: never `git commit`/`git push`
  without an explicit go-ahead.
