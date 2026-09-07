"""Read the local usage summaries and say which bindings earn their keys.

DoKey records what it decided, never what was typed: a binding ID like
"two_step.i.j" and an action kind. That is enough to answer the question the
logging was added for - which of the 450 configured bindings are actually used,
and which are dead weight - without the log ever holding a keystroke.

    python tools/usage_report.py
    python tools/usage_report.py --logs logs/logs --days 30

Reads "usage-summary-<date>-<session>.json" (60 days retained), not
"usage.jsonl" (7 days). Each summary is a snapshot of one UTC day of one
process, so totals come from summing across files, per the format's own rule.

Stdlib only, like the rest of DoKey. Nothing here writes or transmits anything.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

# Action kinds that mean "the user completed a shortcut". Selecting a first step
# is not a decision yet, and the other three are chords that resolved to nothing.
INCOMPLETE_ACTIONS = {"prefix", "missing_binding", "mouse_cancel", "unmapped_special"}

MODE_NAMES = {0: "off", 1: "normal", 2: "insert", 3: "mouse"}


def load_summaries(directory: Path, days: int):
    """Every summary in the window, newest last. Unreadable files are skipped.

    A truncated or half-written snapshot should cost its own day of statistics,
    not the whole report.
    """
    cutoff = date.today() - timedelta(days=days - 1) if days else None
    found = []
    for path in sorted(directory.glob("usage-summary-????-??-??-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            when = date.fromisoformat(data["date"])
        except (OSError, ValueError, KeyError, TypeError):
            print(f"warning: skipping unreadable summary {path.name}", file=sys.stderr)
            continue
        if cutoff and when < cutoff:
            continue
        found.append((when, data))
    found.sort(key=lambda item: (item[0], item[1].get("first_record") or ""))
    return found


def tally(summaries):
    """Fold every snapshot into one set of counters."""
    totals = Counter()  # binding -> presses, repeats included
    deliberate = Counter()  # binding -> presses with repeat=false
    repeats = Counter()  # binding -> presses with repeat=true
    actions = {}  # binding -> action kind last seen
    modes = Counter()  # mode number -> times switched into it
    launches = Counter()  # (binding, success) -> count
    unsupported = Counter()  # raw vk -> count
    for _, data in summaries:
        for entry in data.get("counts", []):
            count = entry.get("count", 0)
            event = entry.get("event")
            if event == "binding":
                name = entry.get("binding")
                if not name:
                    continue
                actions[name] = entry.get("action")
                totals[name] += count
                if entry.get("repeat"):
                    repeats[name] += count
                else:
                    deliberate[name] += count
            elif event == "mode":
                modes[entry.get("current")] += count
            elif event == "command_launch":
                launches[(entry.get("binding"), bool(entry.get("success")))] += count
            elif event == "unsupported_key":
                unsupported[entry.get("vk")] += count
    return totals, deliberate, repeats, actions, modes, launches, unsupported


def section_of(binding: str) -> str:
    """"two_step.i.j" -> "two_step.i"; "common.j" -> "common"."""
    parts = binding.split(".")
    return ".".join(parts[:2]) if parts[0] == "two_step" else parts[0]


def leaf_of(binding: str) -> str:
    return binding.split(".")[-1]


def bar(value: int, peak: int, width: int = 24) -> str:
    return "#" * max(1, round(value * width / peak)) if value and peak else ""


def report(summaries, top: int, show_all: bool):
    totals, deliberate, repeats, actions, modes, launches, unsupported = tally(
        summaries
    )
    latest = summaries[-1][1]
    manifest = latest.get("bindings", {})
    days = sorted({when for when, _ in summaries})
    fingerprints = {data.get("config") for _, data in summaries}
    versions = sorted({data.get("version") for _, data in summaries})

    used_presses = sum(
        count
        for name, count in totals.items()
        if actions.get(name) not in INCOMPLETE_ACTIONS
    )

    print("DoKey usage report")
    print(f"  window     {days[0]} .. {days[-1]}  ({len(days)} day(s))")
    seen = ", ".join(v for v in versions if v)
    print(f"  sessions   {len(summaries)}   versions {seen}")
    print(
        f"  presses    {sum(totals.values())} recorded"
        f"  ({sum(deliberate.values())} deliberate, {sum(repeats.values())} repeat)"
    )
    print(f"  shortcuts  {used_presses} completed")
    if len(fingerprints) > 1:
        print(
            f"  config     {len(fingerprints)} different fingerprints in this window -"
            " the keymap changed, so 'never used' may be stale"
        )
    else:
        print(f"  config     {latest.get('config', '?')[:16]} (stable)")

    # --- what gets used -----------------------------------------------------
    ranked = [
        (count, name)
        for name, count in deliberate.items()
        if actions.get(name) not in INCOMPLETE_ACTIONS
    ]
    ranked.sort(reverse=True)
    print("\nMost used  (deliberate presses, held-key repeats excluded)")
    if not ranked:
        print("  nothing recorded yet")
    peak = ranked[0][0] if ranked else 0
    for count, name in ranked[:top]:
        held = repeats.get(name, 0)
        extra = f"  +{held} repeat" if held else ""
        print(f"  {count:5d}  {name:<28} {bar(count, peak)}{extra}")

    # --- what does not ------------------------------------------------------
    configured = {name for name in manifest if not name.startswith("prefix.")}
    unused = sorted(name for name in configured if not totals.get(name))
    print(
        f"\nNever used  {len(unused)} of {len(configured)} configured bindings"
        f"  ({len(unused) * 100 // max(1, len(configured))}%)"
    )
    by_section = defaultdict(list)
    for name in unused:
        by_section[section_of(name)].append(leaf_of(name))
    defined = defaultdict(int)
    for name in configured:
        defined[section_of(name)] += 1

    dead, partial = [], []
    for name, missing in sorted(by_section.items()):
        (dead if len(missing) == defined[name] else partial).append((name, missing))

    if dead:
        print("\n  entirely unused sections - the whole prefix is free:")
        for name, missing in sorted(dead, key=lambda item: -len(item[1])):
            selected = totals.get("prefix." + name.split(".")[-1], 0)
            note = f", prefix pressed {selected}x" if selected else ""
            print(f"    {name:<16} {len(missing):3d} bindings, none used{note}")
    if partial:
        print("\n  partly used sections:")
        for name, missing in sorted(partial, key=lambda item: -len(item[1])):
            total = defined[name]
            used = total - len(missing)
            shown = missing if show_all else missing[:12]
            hidden = len(missing) - len(shown)
            tail = f" (+{hidden} more)" if hidden else ""
            names = " ".join(shown)
            print(f"    {name:<16} {used}/{total} used, unused: {names}{tail}")

    # --- friction -----------------------------------------------------------
    resolved_to_nothing = INCOMPLETE_ACTIONS - {"prefix"}
    misfires = [
        (count, name)
        for name, count in totals.items()
        if actions.get(name) in resolved_to_nothing
    ]
    if misfires:
        print("\nChords that resolved to nothing")
        for count, name in sorted(misfires, reverse=True)[:top]:
            print(f"  {count:5d}  {name:<28} ({actions.get(name)})")

    failed = {b: c for (b, ok), c in launches.items() if not ok}
    if failed:
        print("\nCommands that failed to launch")
        for name, count in sorted(failed.items(), key=lambda kv: -kv[1]):
            print(f"  {count:5d}  {name}")

    if modes:
        print("\nMode switches")
        peak_mode = max(modes.values())
        for mode, count in sorted(modes.items(), key=lambda kv: -kv[1]):
            label = MODE_NAMES.get(mode, str(mode))
            print(f"  {count:5d}  into {label:<8} {bar(count, peak_mode)}")

    if unsupported:
        print("\nKeys DoKey does not know (raw virtual key codes)")
        for vk, count in sorted(unsupported.items(), key=lambda kv: -kv[1])[:top]:
            print(f"  {count:5d}  vk={vk}")

    if len(days) < 7:
        print(
            f"\nOnly {len(days)} day(s) of data - treat 'never used' as provisional"
            " until the window covers a normal working week."
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="usage_report",
        description="Summarise DoKey usage from the local summary snapshots.",
    )
    parser.add_argument(
        "--logs",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "logs",
        help="directory holding usage-summary-*.json (default: <repo>/logs)",
    )
    parser.add_argument(
        "--days", type=int, default=60, help="only days within the last N (0 = all)"
    )
    parser.add_argument("--top", type=int, default=20, help="rows per ranked list")
    parser.add_argument(
        "--all", action="store_true", help="list every unused binding, no truncation"
    )
    args = parser.parse_args(argv)

    if not args.logs.is_dir():
        parser.error(f"no such directory: {args.logs}")
    summaries = load_summaries(args.logs, args.days)
    if not summaries:
        print(
            f"No usage summaries in {args.logs}."
            " Run DoKey for a while, or point --logs at the machine that does.",
            file=sys.stderr,
        )
        return 1
    report(summaries, top=args.top, show_all=args.all)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
