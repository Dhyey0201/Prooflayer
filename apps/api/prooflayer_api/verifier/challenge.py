"""Proof challenges: a model proposes one extra pytest test; only the verifier runs it.

The proposal is untrusted model output. It must match the canonical schema
(``contracts/schemas.json``) exactly, then pass static validation here before it
is ever executed. Static validation narrows what a test can *say*; it is not
the security boundary (docs/02 step 7). The boundary is the verifier container:
no network, read-only root, no capabilities, non-root, CPU/memory/PID/time caps.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAX_TEST_SOURCE_CHARS = 10_000
MAX_TEST_FUNCTIONS = 20
CHALLENGE_TEST_PATH = "tests/test_prooflayer_challenge.py"

# Modules a challenge test may import. Everything else (os, sys, socket,
# subprocess, importlib, pathlib, shutil, ctypes, ...) is rejected.
ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "__future__",
        "pytest",
        "src",
        "re",
        "math",
        "dataclasses",
        "itertools",
        "functools",
        "collections",
        "datetime",
        "decimal",
        "fractions",
    }
)
BANNED_NAMES = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "breakpoint",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "memoryview",
        "exit",
        "quit",
        "help",
        "__builtins__",
        # pytest helpers that import modules by name or reach the test session.
        "importorskip",
        "import_module",
    }
)
# Fixtures that patch arbitrary dotted paths or expose pytest internals.
BANNED_FIXTURES = frozenset({"monkeypatch", "request", "pytester", "testdir", "pytestconfig"})
_DUNDER = re.compile(r"^__\w+__$")
_FENCE = re.compile(r"^```(?:json)?\s*\n(?P<body>.*)\n```$", re.DOTALL)


class ChallengeProposal(BaseModel):
    """Mirror of contracts/schemas.json (checked by tests/test_challenges.py)."""

    model_config = ConfigDict(extra="forbid")

    requirement_id: str = Field(max_length=100)
    challenge_type: Literal["pytest_case"]
    test_source: str = Field(max_length=MAX_TEST_SOURCE_CHARS)
    rationale: str = Field(max_length=1000)


class ChallengeRejectedError(ValueError):
    """``code`` is a short safe reason; the rejected source is never echoed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def parse_proposal(text: str) -> ChallengeProposal:
    body = text.strip()
    fenced = _FENCE.match(body)
    if fenced:
        body = fenced.group("body").strip()
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, RecursionError):
        raise ChallengeRejectedError("invalid_json") from None
    if not isinstance(data, dict):
        raise ChallengeRejectedError("invalid_json")
    try:
        return ChallengeProposal.model_validate(data)
    except ValidationError:
        raise ChallengeRejectedError("schema_violation") from None


@dataclass(frozen=True)
class ValidatedTest:
    source: str
    sha256: str
    test_count: int

    @property
    def size(self) -> int:
        return len(self.source.encode())


def _import_root(name: str) -> str:
    return name.split(".", 1)[0]


def validate_test_source(source: str) -> ValidatedTest:
    """Reject anything outside a small, declarative subset of pytest test code."""
    if not source.strip() or len(source) > MAX_TEST_SOURCE_CHARS:
        raise ChallengeRejectedError("size_limit")
    try:
        tree = ast.parse(source, filename=CHALLENGE_TEST_PATH)
    except (SyntaxError, ValueError, RecursionError):
        raise ChallengeRejectedError("syntax_error") from None

    tests = 0
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            tests += node.name.startswith("test_")
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # docstring
        elif not isinstance(
            node, ast.Import | ast.ImportFrom | ast.ClassDef | ast.Assign | ast.AnnAssign
        ):
            # Module-level code runs at import time; keep it declarative.
            raise ChallengeRejectedError("module_level_statement")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_import_root(a.name) not in ALLOWED_IMPORT_ROOTS for a in node.names):
                raise ChallengeRejectedError("banned_import")
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                raise ChallengeRejectedError("relative_import")
            if _import_root(node.module) not in ALLOWED_IMPORT_ROOTS:
                raise ChallengeRejectedError("banned_import")
            if node.module == "__future__":
                continue
            if any(a.name == "*" for a in node.names):
                raise ChallengeRejectedError("wildcard_import")
        elif isinstance(node, ast.Name) and (node.id in BANNED_NAMES or _DUNDER.match(node.id)):
            raise ChallengeRejectedError("banned_name")
        elif isinstance(node, ast.Attribute) and (
            node.attr in BANNED_NAMES or _DUNDER.match(node.attr)
        ):
            raise ChallengeRejectedError("banned_attribute")
        elif isinstance(node, ast.AsyncFunctionDef | ast.Await | ast.Global | ast.Nonlocal):
            raise ChallengeRejectedError("unsupported_construct")
        elif isinstance(node, ast.alias) and _DUNDER.match(node.asname or ""):
            raise ChallengeRejectedError("banned_name")
        elif isinstance(node, ast.arg) and node.arg in BANNED_FIXTURES:
            raise ChallengeRejectedError("banned_fixture")

    if tests == 0:
        raise ChallengeRejectedError("no_test_function")
    if tests > MAX_TEST_FUNCTIONS:
        raise ChallengeRejectedError("too_many_tests")
    return ValidatedTest(source, hashlib.sha256(source.encode()).hexdigest(), tests)
