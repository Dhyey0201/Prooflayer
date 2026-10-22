from __future__ import annotations

import json

import pytest

from prooflayer_api.agent.actions import (
    MAX_WRITE_BYTES,
    Finish,
    InvalidActionError,
    ListFiles,
    ReadFile,
    RunCheck,
    WriteFile,
    parse_action,
)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"action": "list_files"}, ListFiles),
        ({"action": "read_file", "path": "src/auth.py"}, ReadFile),
        ({"action": "write_file", "path": "src/auth.py", "content": "x = 1\n"}, WriteFile),
        ({"action": "run_check", "check_id": "pytest-smoke"}, RunCheck),
        ({"action": "finish", "summary": "done", "tests_passed": False}, Finish),
        ({"action": "read_file", "path": ".env.production", "rationale": "why"}, ReadFile),
    ],
)
def test_valid_actions(payload: dict, expected: type) -> None:
    assert isinstance(parse_action(json.dumps(payload)), expected)


def test_markdown_fenced_json_is_accepted() -> None:
    action = parse_action('```json\n{"action": "list_files"}\n```')
    assert isinstance(action, ListFiles)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("I will read the file now.", "invalid_json"),
        ('{"action": "list_files"} trailing', "invalid_json"),
        ('[{"action": "list_files"}]', "invalid_json"),
        ('"list_files"', "invalid_json"),
        ("", "invalid_json"),
        ('{"action": "shell", "command": "cat /etc/passwd"}', "schema_violation"),
        ('{"action": "run_check", "check_id": "rm -rf /"}', "schema_violation"),
        ('{"action": "run_check", "check_id": "pytest-smoke", "argv": ["sh"]}', "schema_violation"),
        ('{"action": "read_file"}', "schema_violation"),
        ('{"action": "finish", "summary": "", "tests_passed": true}', "schema_violation"),
        ('{"action": "finish", "summary": "ok", "tests_passed": "yes"}', "schema_violation"),
    ],
)
def test_invalid_output_is_rejected(text: str, code: str) -> None:
    with pytest.raises(InvalidActionError) as exc:
        parse_action(text)
    assert exc.value.code == code


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "../outside.py",
        "src/../../etc/passwd",
        "src//auth.py",
        "./src/auth.py",
        "src/auth.py/",
        "-rf",
        "src/$(id).py",
        "src/a;b.py",
        "src/a b.py",
        "src/`id`.py",
        "x" * 201,
    ],
)
def test_unsafe_paths_are_rejected(path: str) -> None:
    for action in ("read_file", "write_file"):
        payload = {"action": action, "path": path, "content": ""}
        if action == "read_file":
            payload.pop("content")
        with pytest.raises(InvalidActionError, match="path"):
            parse_action(json.dumps(payload))


def test_oversized_write_is_rejected() -> None:
    payload = {
        "action": "write_file",
        "path": "src/a.py",
        "content": "é" * (MAX_WRITE_BYTES // 2 + 1),
    }
    with pytest.raises(InvalidActionError, match="content"):
        parse_action(json.dumps(payload))


def test_rejection_detail_never_echoes_input_values() -> None:
    with pytest.raises(InvalidActionError) as exc:
        parse_action('{"action": "read_file", "path": "/SECRET-MARKER"}')
    assert "SECRET-MARKER" not in exc.value.detail
