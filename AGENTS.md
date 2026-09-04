# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this project is

DoKey is a **personal, actively used** keyboard remapper for **plain Windows** (no
AutoHotkey, no admin installer — just Python). It gives the keyboard modal
behaviour: a *special key* (Caps Lock) plus a Normal/Insert mode pair, so common
editing and navigation actions live on the home row instead of on arrows and
function keys.

It runs as a tray application (`main.py`), listens to the global keyboard hook via
`pynput`, decides what to do in pure-Python logic, and either swallows the
keystroke, sends different keystrokes, types text, clicks the mouse, or runs a
shell command.

**This is a working tool the owner depends on daily. Prefer small, surgical,
reversible changes. Do not restructure the app "for cleanliness" unless asked.**

## Platform constraints — read before changing anything

- **Windows only at runtime.** `os_level/` uses `ctypes.WinDLL("User32.dll")`,
  `dwmapi`, `ctypes.windll.shcore.SetProcessDpiAwareness`, the `win32_event_filter`
  hook of `pynput`, and Tk overlay windows. Importing anything from `os_level/`
  on Linux/macOS fails immediately.
- **Development often happens from WSL/Linux.** Only `app/` and `tests/` are
  importable there. Keep it that way: **never import `os_level` from `app/`.**
  The dependency direction is `main.py → os_level → app`, never the reverse.
- Deliberately **no build system, no packaging, no CI, no linter config**. Deps are
  a flat `pip_dependencies.txt`. Don't introduce `pyproject.toml`, `requirements.txt`,
  tox, poetry, GitHub Actions, or type-checking config unless explicitly asked.
- Code is formatted with **black** (it's in `pip_dependencies.txt`). Match that style.

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
  config.yaml                 the actual keymap
  mouse_config.yaml           mouse grid: key -> [x%, y%] of the active window
os_level/                     Windows-specific, not importable off Windows
  os_pynput.py                PynpytListener: global hook, suppression, key sending, mouse click
  windows_api.py              active window/process via user32 + dwmapi + psutil
  draw_on_screen.py           WinImage: Tk help overlay (per active process)
  mouse_window.py             MouseImage: Tk mouse-grid overlay + coordinate math
  diagnostic_window.py        DiagnosticWindow: Tk state overlay
assets/                       tray icons, one per mode (+ normal_first_step)
tests/                        unittest; test_playlist.yaml is a data-driven state-machine table
```

## How a keystroke flows

1. `PynpytListener.win32_event_filter(msg, data)` fires **before** press/release
   handlers. `msg`: 256/260 = key down, 257/261 = key up.
2. It short-circuits in two cases: while DoKey is itself sending keys
   (`self.is_sending`), and when **Caps Lock is toggled on**
   (`is_capslock_on()` → everything passes through untouched; this is the de-facto
   "temporarily disable DoKey" escape hatch).
3. It reads real OS modifier state via `GetAsyncKeyState` (`get_modif_state()`),
   builds an `OSEvent`, and calls `App.handle_keyboard_event`.
4. `App` delegates to `KeyProcessor.process()`, which **mutates `AppState`** and
   returns an event object.
5. `App` then performs side effects: tray icon, help/mouse/diagnostic overlays,
   and `os.popen(cmd)` for `CMDEvent`.
6. The returned event goes back to the listener, which sends keys / types text /
   clicks, and decides suppression.

**Suppression mechanism:** returning `False` from `win32_event_filter` *plus*
setting `self.listener._suppress = True` swallows the original key. `_suppress` is
a **private pynput attribute** — this is intentional and load-bearing; don't
"clean it up".

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
- `__command__<some command line>` — runs via `os.popen`
- `__write__<text>` — types the text literally

User overrides: `%HOMEPATH%\.dokey\user_config.yaml`, merged into two-step
sections only (`Config.try_load_users_config`). `%HOMEPATH%\.dokey\help.yaml`
holds the per-application help text shown by the help overlay, keyed by a
substring of the active process name.

## Gotchas that will bite you

- **Adding a new two-step first step needs two edits.** A new top-level section in
  `config.yaml` does nothing unless the key is also added to `FIRST_STEPS` in
  `app/keys.py`.
- **`Keys.from_string()` returns `None` for an unknown name** (it does not raise —
  there's a leftover `x = "xxx"` debug line there). A typo in `config.yaml` shows
  up later as a confusing `None` key, not as a parse error.
- **`user_config.yaml` can only extend first steps that already exist** in
  `config.yaml`; `try_load_users_config` does `.get(first_step)` and then `.update()`
  on the result, so a brand-new section raises `AttributeError` on startup.
- `Config.try_get_two_key_send` / `try_get_two_key_command` are **dead code**
  referencing attributes (`two_steps`, `two_steps_commands`) that no longer exist.
- `CMDEvent` runs an arbitrary string from config through `os.popen` — the config
  file is trusted input by design (there's a `TODO` marking it). Don't wire
  untrusted input into that path.
- `main.py` builds `DiagnosticWindow(None)` and never passes
  `diagnostics_interface` to `App`, so the diagnostics overlay is effectively
  disconnected; `DiagnosticsInterface` is also wired to the *mouse* image.
- Overlay windows create a **second `tk.Tk()` root** on each draw and use
  `overrideredirect` + `-topmost` + `-transparentcolor blue`. That's fragile but
  works; be careful when touching it.
- The tray app uses `icon.run_detached()`; `main.py`'s bare `except:` around
  `app.main()` is what stops it.

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

`Config.dokey_dir()` resolves the user-override directory as `%HOMEPATH%\.dokey`
on Windows and `~/.dokey` elsewhere, which is what allows the above.

## Working agreements

- Ask before changing `app/config.yaml` — it is the owner's live, hand-tuned keymap,
  not sample data.
- Keep `app/` free of Windows imports so the state machine stays testable off Windows.
- When changing key-handling behaviour, add or update a `test_playlist.yaml` row.
- Follow the global rules in `~/.claude/CLAUDE.md`: never `git commit`/`git push`
  without an explicit go-ahead.
