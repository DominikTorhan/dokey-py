"""Text formatting for the experimental window inventory overlay."""


def format_inventory(data):
    lines = ["OPEN WINDOWS", ""]
    windows = data.get("windows", [])
    if not windows:
        lines.append("No task windows found.")
    for index, window in enumerate(windows, 1):
        marker = ">" if window.get("foreground") else " "
        left, top, right, bottom = window["bounds"]
        lines.extend(
            [
                f"{marker} {index:02d}  {window['title']}",
                (
                    f"     {window['process']}  pid={window['pid']}  "
                    f"hwnd=0x{window['hwnd']:X}  class={window['class']}"
                ),
                (
                    f"     {window['state']}  {right - left}x{bottom - top}  "
                    f"at {left},{top}"
                ),
                "",
            ]
        )

    lines.extend(["BROWSER TABS (CHROMIUM DEVTOOLS)", ""])
    tabs = data.get("browser_tabs", [])
    if not tabs:
        lines.extend(
            [
                "Unavailable. Start Chrome/Edge with --remote-debugging-port=9222",
                "or set DOKEY_CDP_PORTS to the enabled local port(s).",
                "",
            ]
        )
    for tab in tabs:
        lines.extend(
            [
                f"  [{tab['port']}] {tab['title']}",
                f"     {tab['url']}",
                f"     type={tab['type']}  id={tab['id']}",
                "",
            ]
        )

    lines.extend(["WEZTERM TABS / PANES", ""])
    panes = data.get("wezterm_panes", [])
    if not panes:
        lines.extend(["Unavailable (no running WezTerm CLI mux server found).", ""])
    for pane in panes:
        lines.extend(
            [
                (
                    f"  window={pane.get('window_id', '?')}  "
                    f"tab={pane.get('tab_id', '?')}  pane={pane.get('pane_id', '?')}  "
                    f"{pane.get('title', '')}"
                ),
                (
                    f"     workspace={pane.get('workspace', '')}  "
                    f"cwd={pane.get('cwd', '')}"
                ),
                "",
            ]
        )
    return "\n".join(lines)
