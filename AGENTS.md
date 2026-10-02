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

- **One documented exception to the rule below:** `os_level/keyboard_window.py`
  is pure Tk and imports fine on Linux — its DPI call is guarded and it pulls in
  no other `os_level` module. That is deliberate, so `tools/keyboard_preview.py`
  can render the cheat sheet from WSL. Keep it dependency-free that way.
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
  keyboard_layout.py          ANSI cap rows + per-tab binding text for the cheat sheet
  events.py                   Event / SendEvent / WriteEvent / CMDEvent / FocusWindowEvent / DoKeyEvent / MouseEvent
  modifs.py                   Modifs: ctrl/shift/alt/win flags
  version.py                  VERSION - single source of truth
  yaml_lite.py                minimal YAML reader for the config subset
  config.yaml                 the actual keymap
  user_config.example.yaml    commented example of ~/.dokey/user_config.yaml (tracked)
  mouse_config.yaml           mouse grid: key -> [x%, y%] of the active window
os_level/                     Windows-specific, not importable off Windows
  win_keyboard.py             WindowsListener: WH_KEYBOARD_LL hook, SendInput, mouse click
  windows_api.py              active window/process via user32 + dwmapi + kernel32 (ctypes only)
  window_focus.py             focus_window(): __focus__ target lookup + SetForegroundWindow
  draw_on_screen.py           WinImage: Tk help overlay (per active process)
  mouse_window.py             MouseImage: Tk mouse-grid overlay + coordinate math
  diagnostic_window.py        DiagnosticWindow: Tk state overlay
  keyboard_window.py          KeyboardWindow: Tk tabbed cheat sheet (imports on Linux)
  tray.py                     TrayIcon: Shell_NotifyIcon tray icon + message pump
assets/                       tray icons, one per mode (+ normal_first_step)
tools/                        offline helpers; never imported by the running app
  usage_report.py             reads logs/usage-summary-*.json: what is used, what never is
  keyboard_preview.py         draws the cheat sheet with no hook; runs under WSLg
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
4. help key, diagnostics key, keyboard cheat sheet
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

**Format version 2.** The file opens with `version: 2` and has exactly three
top-level sections; anything else is a `ValueError` rather than a silent
mistake:

- `keys:` — the control keys (`special`, `help`, `diagnostic`, `keyboard`,
  `off_mode`, `change_mode`, `mouse_mode`, `exit`, `clear_screen`).
  `Config.CONTROL_KEYS` lists them **in the order `process()` reaches them**,
  and both the loader and the keyboard overlay read that one list.
- `layers:` — `special:` (special key held, Normal and Insert) and `common:`
  (single key, Normal only). Each is `{title?, bindings}`.
- `two_step:` — first steps, each `{title?, bindings}`. **The sections here
  *are* the first steps** (`Config.first_steps`); there is no second list to
  keep in step. A section with no bindings is meaningful — it keeps the key
  swallowing the next keystroke, which is what `s:` and `u:` do.

`title:` is optional everywhere and presentation only: the keyboard overlay
shows it instead of the binding kinds, so a section can read `▸16 F-KEYS`
rather than `▸16 KEYS`. Nothing dispatches on it.

**Version 1 files still load.** No `version:` key means the old flat layout,
where `special:`/`common:` are known names and *every other top-level key is a
first step*. `_load_v1` reproduces it exactly, including taking `first_steps`
from the hand-maintained `FIRST_STEPS` in `keys.py` rather than from the
sections — v1 semantics are that a section is dead unless the key is also in
that list, and changing it there would alter behaviour on existing files.

Value syntax:

- `ctrl+shift+v` — one chord
- `up, end, enter` — a sequence of chords, sent in order
- `__command__<some command line>` — launched with `subprocess.Popen(shell=True)`
- `__write__<text>` — types the text literally
- `__focus__<process.exe::title prefix>` — activates the first window (Z-order)
  whose executable matches exactly and whose title starts with the prefix, both
  case-insensitive; runs on the worker thread, never launches anything. A
  malformed value is logged and the binding dropped rather than failing startup.
  The target is never written to the usage records.

User overrides: `~/.dokey/user_config.yaml` (`Config.try_load_users_config`),
version-marked independently of `config.yaml` so the two can be migrated apart.
A v2 override file can change control keys, either layer and any two-step
section; a v1 one is two-step sections only, and still loads unchanged. A
section named there that the base config lacks becomes a new first step.

**Loading it never stops DoKey.** A parse error is logged and the shipped
keymap is kept — it used to raise straight out of `from_file` and prevent
startup. The exception's *message* is deliberately not logged: parse errors
quote the offending line, and these files hold addresses and logins.

`~/.dokey/help.yaml` holds the per-application help text shown by the help
overlay, keyed by a substring of the active process name.

`app/user_config.example.yaml` is the tracked, sanitised example of that file
and the only documentation of the override format that ships with DoKey;
`tests/test_user_config_example.py` loads it through the real code path so it
cannot rot. **The owner's real overrides are personal** — addresses, logins,
private URLs — and live only in `~/.dokey`. `.gitignore` blocks
`app/user_config.yaml` for exactly that reason: it is a safety net, not a stale
path. Never commit it, never quote its contents, and never put example values
in it that look real.

## Gotchas that will bite you

- **Adding a two-step first step is one edit now.** In v2 a new section under
  `two_step:` is a first step by virtue of existing. `FIRST_STEPS` in
  `app/keys.py` survives only as the v1 default — do not consult it anywhere
  else; ask `config.is_first_step(key)`.
- **`yaml_lite` is more permissive than YAML in one place that matters here:**
  an unquoted `": "` inside a value parses for it and fails in PyYAML, so a
  `__write__<TODO: >` binding must be quoted. `test_yaml_lite.py` compares the
  two parsers on every `*.yaml` in the repo and will catch it.
- **Never let config content into a log message.** `__write__` expansions and
  `__command__` lines hold addresses, logins and private URLs, and `dokey.log`
  keeps seven daily rotations. Three rules follow, all pinned by
  `tests/test_log_privacy.py`: `yaml_lite` parse errors name a **line number**
  and never quote the line; `Keys.from_string` names the *marker* when handed a
  `__write__`/`__command__` value instead of echoing it (config values reach it,
  not just key names); and `try_load_users_config` logs `type(error).__name__`
  rather than the message. The usage log records binding IDs and action kinds
  only, and the keyboard overlay shows `CMD`/`TEXT` rather than contents — keep
  it that way.
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
- **The cheat sheet owns ESC and the arrows only while it is open**, and ESC
  only without the special key held. `Caps+ESC` still exits DoKey; the arrows
  move between tabs and are swallowed; every other key passes through — it is a
  reference to read, not a mode. Opening it sets
  `prevent_prev_mode_on_special_up`, so it does not drop Insert mode.
- **The cheat sheet's two tabs mirror `KeyProcessor` order.** The `special` tab
  must show the control keys (help, diagnostics, cheat sheet, mode keys, exit,
  clear screen) winning over any `special:` entry on the same key, because
  `process()` reaches them first. If that order changes, `_controls()` in
  `app/keyboard_layout.py` has to change with it or the picture starts lying.
  `AppState.keyboard_tab` is an int index into `TABS`, deliberately, so
  `app_state.py` keeps no dependency on the drawing side.
- The diagnostics overlay is attached **after** `App` is constructed
  (`app.diagnostics_interface = ...`), because `DiagnosticWindow` renders the live
  `AppState` and `App` owns it.

## Running

```bash
python main.py            # tray icon + overlays
python main.py --plain    # no Tk overlays (-p); still needs Windows for the hook
python tools/keyboard_preview.py   # cheat sheet only; works under WSLg
```

Logs: `logs/dokey.log`, daily rotation, 7 days kept (gitignored).
Console handler is at INFO; set the root level to DEBUG in `init_logging()` to see
every key event.

Usage records live beside it: `usage.jsonl` (7 days) and
`usage-summary-<date>-<session>.json` (60 days). They record *which binding fired*
(`two_step.i.j`) and never what was typed - no `__write__` text, no command line.
Read them with:

```bash
python tools/usage_report.py                    # <repo>/logs
python tools/usage_report.py --logs D:/dokey/logs --days 30 --all
```

It ranks what gets used and, more usefully, lists what never does. `tools/` is
stdlib-only and stands outside the `main.py -> os_level -> app` chain: nothing in
the running app may import it.

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
