#!/usr/bin/env python3
"""np handoff + build/test plumbing (CONTRACT.md §6, tools 6-10).

Implements:
  - np_get_handoff / np_write_handoff  — JSON handoff files in a pipeline dir
  - np_list_files                       — capped, exclude-aware listing
  - np_build_verify                     — stack build command with {target}
  - np_test_run                         — stack test command + result parsing

Build and test commands are resolved from `<np-home>/np.config.json` stacks[]
(never hardcoded). `{target}` in a command is substituted with the caller's
target argument. Commands WITHOUT a `{target}` placeholder (typical frontend
stacks: "npm run build", "npx vitest run") run from the caller's `target`
directory when it exists, else the stack's first `roots` entry — never bare
from the project root, where e.g. a web app's package.json/tsconfig would be
missing. Result parsing is best-effort per stack `results_format`
("trx", "vitest"); the raw output tail is always included so a model can
recover when parsing misses.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from context_store import ContextStoreError, load_config

BUILD_TIMEOUT_S = 900
TEST_TIMEOUT_S = 1200
LIST_FILES_CAP = 500
OUTPUT_TAIL_CHARS = 4000

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
TRX_NS = "{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}"


# ---------------------------------------------------------------------------
# Handoff files
# ---------------------------------------------------------------------------

def _resolve_dir(project_root: Path, dir_path: str) -> Path:
    p = Path(dir_path)
    return p if p.is_absolute() else (project_root / p)


def get_handoff(project_root: Path, handoff_dir: str, name: str) -> Dict[str, Any]:
    safe_name = Path(name).name
    directory = _resolve_dir(project_root, handoff_dir)
    file_path = directory / safe_name
    if not file_path.is_file():
        available = sorted(f.name for f in directory.glob("*.json")) if directory.is_dir() else []
        raise ContextStoreError(
            f"handoff file '{safe_name}' not found in {directory} "
            f"(available: {available or 'none'})"
        )
    try:
        content = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContextStoreError(f"invalid JSON in '{safe_name}': {e}")
    return {"success": True, "content": content}


def write_handoff(project_root: Path, handoff_dir: str, name: str, content: Any) -> Dict[str, Any]:
    safe_name = Path(name).name
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError as e:
            raise ContextStoreError(f"content is not valid JSON: {e}")
    directory = _resolve_dir(project_root, handoff_dir)
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / safe_name
    file_path.write_text(
        json.dumps(content, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return {"success": True, "path": str(file_path)}


# ---------------------------------------------------------------------------
# File listing
# ---------------------------------------------------------------------------

def _excluded(rel_posix: str, patterns: List[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(rel_posix, pat):
            return True
        # `**/x/**` should also match `x/...` at the top level
        if pat.startswith("**/") and fnmatch.fnmatch(rel_posix, pat[3:]):
            return True
    return False


def list_files(project_root: Path, dir_path: str, glob: str = "**/*") -> Dict[str, Any]:
    base = _resolve_dir(project_root, dir_path)
    if not base.is_dir():
        raise ContextStoreError(f"directory not found: {dir_path}")
    try:
        cfg = load_config(project_root)
        excludes = list((cfg.get("index") or {}).get("exclude") or [])
    except ContextStoreError:
        excludes = []
    files: List[str] = []
    truncated = False
    for path in sorted(base.glob(glob)):
        if not path.is_file():
            continue
        if {".git", "__pycache__"} & set(path.parts):
            continue
        try:
            rel_root = path.relative_to(project_root).as_posix()
        except ValueError:
            rel_root = path.as_posix()
        if _excluded(rel_root, excludes):
            continue
        files.append(path.relative_to(base).as_posix())
        if len(files) >= LIST_FILES_CAP:
            truncated = True
            break
    result: Dict[str, Any] = {"success": True, "files": files}
    if truncated:
        result["truncated"] = True
        result["note"] = f"capped at {LIST_FILES_CAP} files; narrow the glob"
    return result


# ---------------------------------------------------------------------------
# Stack command resolution
# ---------------------------------------------------------------------------

def _pick_stack(project_root: Path, stack_kind: Optional[str]) -> Dict[str, Any]:
    cfg = load_config(project_root)
    stacks = cfg.get("stacks") or []
    if not stacks:
        raise ContextStoreError("np.config.json has no stacks[] configured")
    if stack_kind:
        for stack in stacks:
            if stack.get("kind") == stack_kind:
                return stack
        known = [s.get("kind") for s in stacks]
        raise ContextStoreError(f"no stack with kind '{stack_kind}' (known: {known})")
    return stacks[0]


def _substitute_target(command: str, target: Optional[str]) -> str:
    if "{target}" in command:
        command = command.replace("{target}", target or "")
    # collapse doubled spaces left by an empty target
    return " ".join(command.split())


def _resolve_cwd(
    project_root: Path,
    stack: Dict[str, Any],
    command_tmpl: str,
    target: Optional[str],
) -> Path:
    """Working directory for a stack build/test command.

    A command with a `{target}` placeholder addresses its target explicitly,
    so it runs from the project root (dotnet-style). A command WITHOUT a
    placeholder (typical frontend stacks) cannot address a target at all, so
    run it from the most specific directory available:

      1. the caller's `target` when it resolves to an existing directory
         (lets callers point the run at a specific app dir),
      2. else the stack's first `roots` entry when that directory exists,
      3. else the project root.
    """
    if "{target}" in command_tmpl:
        return project_root
    if target:
        t = Path(target)
        t = t if t.is_absolute() else project_root / t
        if t.is_dir():
            return t
    roots = stack.get("roots") or []
    if roots:
        r = project_root / str(roots[0])
        if r.is_dir():
            return r
    return project_root


def _run_shell(command: str, cwd: Path, timeout: int) -> Tuple[int, str]:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ContextStoreError(f"command timed out after {timeout}s: {command}")
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output


# ---------------------------------------------------------------------------
# Build verify
# ---------------------------------------------------------------------------

def _parse_error_lines(output: str, error_format: str) -> List[str]:
    lines = [ANSI_RE.sub("", line).strip() for line in output.splitlines()]
    errors: List[str] = []
    if error_format == "msbuild":
        errors = [l for l in lines if ": error " in l]
    elif error_format == "tsc":
        errors = [l for l in lines if re.search(r"\berror TS\d+", l)]
    elif error_format == "go":
        errors = [l for l in lines if re.match(r"^\S+\.go:\d+:\d+:", l)]
    else:  # generic
        errors = [l for l in lines if re.search(r"\berror\b", l, re.IGNORECASE)]
    # de-duplicate while preserving order
    seen = set()
    unique: List[str] = []
    for line in errors:
        if line and line not in seen:
            seen.add(line)
            unique.append(line)
    return unique


def build_verify(
    project_root: Path,
    stack_kind: Optional[str] = None,
    target: Optional[str] = None,
) -> Dict[str, Any]:
    stack = _pick_stack(project_root, stack_kind)
    command_tmpl = stack.get("build")
    if not command_tmpl:
        raise ContextStoreError(f"stack '{stack.get('kind')}' has no build command")
    command = _substitute_target(command_tmpl, target)
    cwd = _resolve_cwd(project_root, stack, command_tmpl, target)
    exit_code, output = _run_shell(command, cwd, BUILD_TIMEOUT_S)
    errors = _parse_error_lines(output, str(stack.get("error_format") or "generic"))
    return {
        "success": exit_code == 0,
        "exit_code": exit_code,
        "command": command,
        "cwd": str(cwd),
        "errors": errors[:50],
        "output_tail": output[-OUTPUT_TAIL_CHARS:],
    }


# ---------------------------------------------------------------------------
# Test run
# ---------------------------------------------------------------------------

def _parse_trx(project_root: Path, target: Optional[str], started_at: float) -> Optional[Dict[str, Any]]:
    """Find the newest .trx produced by this run and parse its counters."""
    search_roots: List[Path] = []
    if target:
        t = Path(target)
        t = t if t.is_absolute() else project_root / t
        search_roots.append(t.parent if t.is_file() else t)
    search_roots.append(project_root)

    newest: Optional[Path] = None
    newest_mtime = 0.0
    skip_parts = {"node_modules", ".git", "bin", "obj"}
    for root in search_roots:
        if not root.is_dir():
            continue
        try:
            for trx in root.rglob("*.trx"):
                if skip_parts & set(trx.parts):
                    continue
                mtime = trx.stat().st_mtime
                if mtime >= started_at - 5 and mtime > newest_mtime:
                    newest, newest_mtime = trx, mtime
        except OSError:
            continue
        if newest is not None:
            break

    if newest is None:
        return None
    try:
        tree = ET.parse(str(newest))
    except ET.ParseError:
        return None
    root_el = tree.getroot()
    counters = root_el.find(f".//{TRX_NS}Counters")
    if counters is None:
        return None

    def _int(attr: str) -> int:
        try:
            return int(counters.get(attr) or 0)
        except ValueError:
            return 0

    passed = _int("passed")
    failed = _int("failed")
    skipped = _int("notExecuted") + _int("inconclusive")
    failures: List[str] = []
    for result in root_el.iter(f"{TRX_NS}UnitTestResult"):
        if (result.get("outcome") or "").lower() == "failed":
            name = result.get("testName") or "unknown-test"
            message_el = result.find(f".//{TRX_NS}Message")
            message = (message_el.text or "").strip().splitlines()[0] if message_el is not None and message_el.text else ""
            failures.append(f"{name}: {message}" if message else name)
    return {
        "summary": {"passed": passed, "failed": failed, "skipped": skipped},
        "failures": failures,
        "trx_file": str(newest),
    }


def _parse_dotnet_console(output: str) -> Optional[Dict[str, Any]]:
    m = re.search(
        r"Failed:\s*(\d+),\s*Passed:\s*(\d+),\s*Skipped:\s*(\d+)", output
    )
    if not m:
        return None
    failed, passed, skipped = (int(g) for g in m.groups())
    failures = [
        line.strip()
        for line in output.splitlines()
        if re.match(r"^\s*(Failed|✗|X)\s+\S", line)
    ]
    return {
        "summary": {"passed": passed, "failed": failed, "skipped": skipped},
        "failures": failures[:50],
    }


def _parse_vitest(output: str) -> Optional[Dict[str, Any]]:
    clean = ANSI_RE.sub("", output)
    tests_line = None
    for line in clean.splitlines():
        if re.search(r"^\s*Tests\b", line):
            tests_line = line
    if tests_line is None:
        return None

    def _count(label: str) -> int:
        m = re.search(rf"(\d+)\s+{label}", tests_line)
        return int(m.group(1)) if m else 0

    summary = {
        "passed": _count("passed"),
        "failed": _count("failed"),
        "skipped": _count("skipped") + _count("todo"),
    }
    failures = [
        line.strip()
        for line in clean.splitlines()
        if re.match(r"^\s*(×|✗|✘|FAIL\b|✖)", line.strip())
    ]
    return {"summary": summary, "failures": failures[:50]}


def test_run(
    project_root: Path,
    stack_kind: Optional[str] = None,
    target: Optional[str] = None,
) -> Dict[str, Any]:
    stack = _pick_stack(project_root, stack_kind)
    command_tmpl = stack.get("test")
    if not command_tmpl:
        raise ContextStoreError(f"stack '{stack.get('kind')}' has no test command")
    command = _substitute_target(command_tmpl, target)
    cwd = _resolve_cwd(project_root, stack, command_tmpl, target)
    started_at = time.time()
    exit_code, output = _run_shell(command, cwd, TEST_TIMEOUT_S)

    results_format = str(stack.get("results_format") or "").lower()
    parsed: Optional[Dict[str, Any]] = None
    if results_format == "trx":
        parsed = _parse_trx(project_root, target, started_at) or _parse_dotnet_console(output)
    elif results_format == "vitest":
        parsed = _parse_vitest(output)
    else:
        # best-effort: try the known parsers in order
        parsed = _parse_dotnet_console(output) or _parse_vitest(output)

    result: Dict[str, Any] = {
        "success": exit_code == 0,
        "exit_code": exit_code,
        "command": command,
        "cwd": str(cwd),
        "summary": (parsed or {}).get("summary")
        or {"passed": None, "failed": None, "skipped": None},
        "failures": (parsed or {}).get("failures") or [],
        "output_tail": output[-OUTPUT_TAIL_CHARS:],
    }
    if parsed and parsed.get("trx_file"):
        result["trx_file"] = parsed["trx_file"]
    if parsed is None:
        result["note"] = (
            f"could not parse results (results_format="
            f"{results_format or 'unset'}); see output_tail"
        )
    return result
