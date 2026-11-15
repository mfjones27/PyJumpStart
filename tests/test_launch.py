import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import PyJumpStart as pjs  # noqa: E402


def test_terminal_uses_cwd_not_a_shell_string(tmp_path, monkeypatch):
    monkeypatch.setattr(pjs, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(pjs, "save_history", lambda name: None)
    evil = 'proj" & calc & echo "'
    with mock.patch.object(pjs.subprocess, "Popen") as popen:
        pjs.open_terminal(evil)
        pjs.open_cursor(evil)
    for call in popen.call_args_list:
        args, kwargs = call
        assert kwargs["cwd"] == tmp_path / evil
        assert all(evil not in part for part in args[0])  # folder never lands in the command
    assert popen.call_args_list[1][0][0] == ["cmd", "/K", "cursor . 2>nul"]


def test_git_clone_url_cannot_be_an_option(tmp_path, monkeypatch):
    monkeypatch.setattr(pjs, "PROJECTS_DIR", tmp_path)
    with mock.patch.object(pjs.subprocess, "run") as run:
        pjs.clone_repo("--upload-pack=touch /tmp/pwned")
    cmd = run.call_args[0][0]
    assert cmd[:3] == ["git", "clone", "--"]


def test_finds_projects_dir_and_survives_missing_documents(tmp_path):
    docs = tmp_path / "Documents"
    assert pjs._find_projects_dir(docs) == docs  # used to crash with FileNotFoundError
    (docs / "Python Projects").mkdir(parents=True)
    assert pjs._find_projects_dir(docs) == docs / "Python Projects"
