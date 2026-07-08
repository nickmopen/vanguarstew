"""Tests for benchmark.runner.load_solve error handling (#1048, #1051).

Every failure mode must raise a clean RuntimeError instead of leaking a raw builtin
exception/traceback, since scripts/run_eval.py only catches (RuntimeError, RepoSetError).
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["VANGUARSTEW_OFFLINE"] = "1"

from benchmark.runner import load_solve  # noqa: E402


def _write(dir_path: str, name: str, content: str) -> str:
    path = os.path.join(dir_path, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_missing_file_raises_clean_runtime_error(tmp_path):
    missing = str(tmp_path / "does-not-exist.py")
    with pytest.raises(RuntimeError, match="agent file not found"):
        load_solve(missing)


def test_directory_path_raises_clean_runtime_error(tmp_path):
    directory = tmp_path / "a-directory"
    directory.mkdir()
    with pytest.raises(RuntimeError, match="not a regular file"):
        load_solve(str(directory))


def test_syntax_error_raises_clean_runtime_error(tmp_path):
    bad = _write(str(tmp_path), "bad.py", "def solve(\n")
    with pytest.raises(RuntimeError, match="cannot load agent file"):
        load_solve(bad)


def test_runtime_error_on_import_chains_the_original_exception(tmp_path):
    bad = _write(str(tmp_path), "bad_import.py", "import this_module_does_not_exist\n")
    with pytest.raises(RuntimeError) as excinfo:
        load_solve(bad)
    assert isinstance(excinfo.value.__cause__, ModuleNotFoundError)


def test_missing_solve_attribute_raises_clean_runtime_error(tmp_path):
    no_solve = _write(str(tmp_path), "no_solve.py", "x = 1\n")
    with pytest.raises(RuntimeError, match="does not define a callable 'solve'"):
        load_solve(no_solve)


def test_noncallable_solve_raises_clean_runtime_error(tmp_path):
    bad_solve = _write(str(tmp_path), "bad_solve.py", "solve = 42\n")
    with pytest.raises(RuntimeError, match="does not define a callable 'solve'"):
        load_solve(bad_solve)


def test_valid_agent_file_returns_callable_solve(tmp_path):
    good = _write(str(tmp_path), "good.py", "def solve(*a, **k):\n    return {}\n")
    solve = load_solve(good)
    assert callable(solve)
    assert solve() == {}


def test_no_exception_leaks_as_non_runtime_error(tmp_path):
    """Every failure mode must surface as RuntimeError, never a raw builtin exception."""
    directory = tmp_path / "a-directory"
    directory.mkdir()
    cases = [
        str(tmp_path / "missing.py"),
        str(directory),
        _write(str(tmp_path), "syntax.py", "def solve(\n"),
        _write(str(tmp_path), "nosolve.py", "x = 1\n"),
        _write(str(tmp_path), "noncallable.py", "solve = None\n"),
    ]
    for path in cases:
        try:
            load_solve(path)
        except RuntimeError:
            continue
        except Exception as exc:  # pragma: no cover - failure path under test
            pytest.fail(f"load_solve({path!r}) leaked {type(exc).__name__} instead of RuntimeError: {exc}")
