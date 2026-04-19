import argparse
import ctypes
import json
import os
import shutil
import sys
from pathlib import Path


def _enable_windows_vt() -> None:
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        STD_OUTPUT_HANDLE = -11
        ENABLE_PROCESSED_OUTPUT = 0x0001
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(
                handle,
                mode.value | ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING,
            )
    except Exception:
        pass


_enable_windows_vt()
os.environ.setdefault("PROMPT_TOOLKIT_COLOR_DEPTH", "DEPTH_24_BIT")

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.output import ColorDepth, create_output
from prompt_toolkit.styles import Style

_OUTPUT = create_output(always_prefer_tty=True)


def make_app(**kwargs) -> Application:
    kwargs.setdefault("full_screen", False)
    kwargs.setdefault("style", STYLE)
    kwargs.setdefault("color_depth", ColorDepth.TRUE_COLOR)
    kwargs.setdefault("output", _OUTPUT)
    return Application(**kwargs)

PROJECTS_DIR = Path(r"C:\Users\Mauri\Documents\Python Projects")
HISTORY_FILE = Path.home() / ".pyjumpstart_history.json"

STYLE = Style.from_dict({
    "header": "bold #61afef",
    "project": "#abb2bf",
    "project.selected": "bold #e5c07b bg:#3e4451",
    "status": "italic #56b6c2",
    "error": "bold #e06c75",
    "prompt": "bold #c678dd",
})


def load_history() -> dict:
    try:
        return json.loads(HISTORY_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_history(project_name: str) -> None:
    HISTORY_FILE.write_text(json.dumps({"last": project_name}))


def get_projects() -> list[str]:
    if not PROJECTS_DIR.exists():
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        [d.name for d in PROJECTS_DIR.iterdir() if d.is_dir()],
        key=str.lower,
    )


def fuzzy_match(query: str, name: str) -> bool:
    query = query.lower()
    name_lower = name.lower()
    qi = 0
    for ch in name_lower:
        if qi < len(query) and ch == query[qi]:
            qi += 1
    return qi == len(query)


def open_terminal(project_name: str) -> None:
    path = PROJECTS_DIR / project_name
    save_history(project_name)
    os.system(f'start cmd /K "cd /d {path}"')


def open_cursor(project_name: str) -> None:
    path = PROJECTS_DIR / project_name
    save_history(project_name)
    os.system(f'start cmd /K "cd /d {path} && cursor . 2>nul"')


def action_menu(project_name: str) -> None:
    kb = KeyBindings()
    result: str | None = None

    @kb.add("t")
    def _term(event):
        nonlocal result
        result = "t"
        event.app.exit()

    @kb.add("c")
    def _cursor(event):
        nonlocal result
        result = "c"
        event.app.exit()

    @kb.add("escape")
    def _back(event):
        event.app.exit()

    @kb.add("c-c")
    def _quit(event):
        nonlocal result
        result = "quit"
        event.app.exit()

    body = FormattedTextControl(
        [
            ("class:header", f"\n  Project: {project_name}\n\n"),
            ("class:project", "    [t] "),
            ("class:status", "Open terminal\n"),
            ("class:project", "    [c] "),
            ("class:status", "Open terminal + Cursor\n\n"),
            ("class:project", "    [Esc] Back\n"),
        ]
    )
    app = make_app(
        layout=Layout(Window(body)),
        key_bindings=kb,
    )
    app.run()

    if result == "t":
        open_terminal(project_name)
        sys.exit(0)
    elif result == "c":
        open_cursor(project_name)
        sys.exit(0)
    elif result == "quit":
        sys.exit(0)


def text_input_prompt(label: str) -> str | None:
    kb = KeyBindings()
    buf = Buffer(name="input")
    confirmed: list[bool] = []

    @kb.add("enter")
    def _confirm(event):
        confirmed.append(True)
        event.app.exit()

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event):
        event.app.exit()

    app = make_app(
        layout=Layout(
            HSplit([
                Window(FormattedTextControl([("class:header", f"\n  {label}")]), height=2),
                Window(BufferControl(buffer=buf), height=1),
            ])
        ),
        key_bindings=kb,
    )
    app.run()

    if confirmed and buf.text.strip():
        return buf.text.strip()
    return None


def confirm_delete(project_name: str) -> bool:
    kb = KeyBindings()
    result = [False]

    @kb.add("y")
    def _yes(event):
        result[0] = True
        event.app.exit()

    @kb.add("n")
    @kb.add("escape")
    def _no(event):
        event.app.exit()

    @kb.add("c-c")
    def _quit(event):
        event.app.exit()

    body = FormattedTextControl([
        ("class:error", f"\n  Delete '{project_name}' permanently? [y/n] "),
    ])
    app = make_app(
        layout=Layout(Window(body)),
        key_bindings=kb,
    )
    app.run()
    return result[0]


def main_menu() -> None:
    projects = get_projects()
    selected_index = [0]
    filter_buf = Buffer(name="filter")
    status_text: list[tuple[str, str]] = []
    force_quit = [False]

    def get_filtered() -> list[str]:
        query = filter_buf.text
        if not query:
            return projects
        return [p for p in projects if fuzzy_match(query, p)]

    def get_header_text():
        return [
            ("class:header", "  ╔══════════════════════════════════════╗\n"),
            ("class:header", "  ║          P y J u m p S t a r t       ║\n"),
            ("class:header", "  ╚══════════════════════════════════════╝\n\n"),
        ]

    def get_project_list_text():
        filtered = get_filtered()
        if not filtered and not filter_buf.text:
            return [("class:status", "  No projects found. Press [n] to create one.\n")]
        if not filtered:
            return [("class:status", "  No matches.\n")]
        lines: list[tuple[str, str]] = []
        sel = selected_index[0] % len(filtered) if filtered else 0
        for i, name in enumerate(filtered):
            marker = " ▸ " if i == sel else "   "
            cls = "class:project.selected" if i == sel else "class:project"
            lines.append((cls, f"{marker}{name}\n"))
        return lines

    def get_footer_text():
        parts: list[tuple[str, str]] = [
            ("class:status", "\n  [↑↓] Navigate  [Enter] Select  [n] New  [d] Delete  [Ctrl+C] Quit\n"),
        ]
        if status_text:
            parts.append(status_text[0])
        return parts

    header_window = Window(FormattedTextControl(get_header_text), height=4)
    list_window = Window(FormattedTextControl(get_project_list_text), height=15)
    footer_window = Window(FormattedTextControl(get_footer_text), height=3)

    kb = KeyBindings()

    @kb.add("up")
    def _up(event):
        filtered = get_filtered()
        if filtered:
            selected_index[0] = (selected_index[0] - 1) % len(filtered)

    @kb.add("down")
    def _down(event):
        filtered = get_filtered()
        if filtered:
            selected_index[0] = (selected_index[0] + 1) % len(filtered)

    @kb.add("enter")
    def _select(event):
        filtered = get_filtered()
        if filtered:
            sel = selected_index[0] % len(filtered)
            event.app.exit(result=filtered[sel])

    @kb.add("c-c")
    def _quit(event):
        force_quit[0] = True
        event.app.exit()

    @kb.add("n", filter=Condition(lambda: filter_buf.text == ""))
    def _new(event):
        event.app.exit(result="__NEW__")

    @kb.add("d")
    def _delete(event):
        event.app.exit(result="__DELETE__")

    def on_text_changed(_buf):
        selected_index[0] = 0

    filter_buf.on_text_changed += on_text_changed

    layout = Layout(
        HSplit([
            header_window,
            Window(FormattedTextControl([("class:prompt", "  Filter: ")]), height=1),
            Window(BufferControl(buffer=filter_buf), height=1),
            Window(FormattedTextControl([("", "\n")]), height=1),
            list_window,
            footer_window,
        ])
    )

    while True:
        projects = get_projects()
        selected_index[0] = 0
        filter_buf.text = ""
        status_text.clear()

        app = make_app(
            layout=layout,
            key_bindings=kb,
        )

        try:
            result = app.run()
        except (EOFError, KeyboardInterrupt):
            return

        if force_quit[0]:
            return

        if result is None:
            return

        if result == "__NEW__":
            name = text_input_prompt("Project name: ")
            if name:
                new_path = PROJECTS_DIR / name
                try:
                    new_path.mkdir(parents=True, exist_ok=True)
                    status_text.append(("class:status", f"\n  Created: {name}\n"))
                except PermissionError:
                    status_text.append(("class:error", f"\n  Permission denied creating '{name}'\n"))
            continue

        if result == "__DELETE__":
            filtered = get_filtered()
            if filtered:
                sel = selected_index[0] % len(filtered)
                target = filtered[sel]
                if confirm_delete(target):
                    try:
                        shutil.rmtree(PROJECTS_DIR / target)
                        status_text.append(("class:status", f"\n  Deleted: {target}\n"))
                    except PermissionError:
                        status_text.append(("class:error", f"\n  Permission denied deleting '{target}'\n"))
            continue

        action_menu(result)


def run_last() -> None:
    history = load_history()
    last = history.get("last")
    if not last or not (PROJECTS_DIR / last).is_dir():
        print("No valid last project found. Launching menu...")
        main_menu()
        return
    action_menu(last)


def main() -> None:
    parser = argparse.ArgumentParser(description="PyJumpStart — project launcher")
    parser.add_argument("--last", action="store_true", help="Reopen the last project")
    args = parser.parse_args()

    if args.last:
        run_last()
    else:
        main_menu()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n  ERROR: {e}")
        input("\n  Press Enter to close...")
