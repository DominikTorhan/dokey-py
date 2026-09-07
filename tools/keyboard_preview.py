"""Open the keyboard cheat sheet on its own, with no keyboard hook.

The overlay is the one piece of DoKey you have to *look at* to judge, and the
keyboard hook only exists on Windows. This entrypoint draws the real config in
a plain window that ESC closes, so the layout can be iterated on from WSL:

    python tools/keyboard_preview.py
    python tools/keyboard_preview.py --config app/config.yaml --overlay

Left and Right switch tabs, ESC closes, exactly as in the running app - except
that here Tk delivers those keys, where DoKey delivers them from its hook.

--overlay reproduces what DoKey actually shows: a borderless, always-on-top
panel that does not take focus. Being unfocusable it receives no keys at all,
so neither the arrows nor ESC work there - it is for checking appearance only,
and the plain window is the default.

Needs a display. Under WSL that means WSLg (DISPLAY is set for you); over plain
SSH it means X forwarding.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # runnable as a script, not just as a module
    sys.path.insert(0, str(ROOT))

from app.config import Config
from app.keyboard_layout import TABS, build, unplaced_controls
from os_level.keyboard_window import KeyboardWindow


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="keyboard_preview",
        description="Draw the DoKey keyboard cheat sheet without running DoKey.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "app" / "config.yaml",
        help="keymap to render (default: app/config.yaml)",
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="borderless always-on-top panel, as the running app shows it",
    )
    parser.add_argument(
        "--tab",
        choices=TABS,
        default=TABS[0],
        help=f"tab to open on (default: {TABS[0]}); arrows switch tabs",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=0,
        help="close automatically after N seconds (for smoke tests)",
    )
    args = parser.parse_args(argv)

    if not args.config.is_file():
        parser.error(f"no such config: {args.config}")

    config = Config.from_file(args.config)
    window = KeyboardWindow(
        lambda tab: build(config, tab),
        footer_notes=lambda: unplaced_controls(config),
        overlay=args.overlay,
    )

    if args.seconds:
        window.show(args.tab)
        if not window.root:
            return 1
        window.root.after(int(args.seconds * 1000), window.root.destroy)
        window.root.mainloop()
        return 0

    return 0 if window.run_standalone(args.tab) else 1


if __name__ == "__main__":
    raise SystemExit(main())
