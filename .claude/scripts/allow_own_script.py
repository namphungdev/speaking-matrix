#!/usr/bin/env python3
"""PreToolUse gate: auto-approve Bash calls to np's OWN scripts, nothing else.

Why this exists: harmonize writes the project's rule, skill and memory files
through `harmonize_scan.py` rather than the Edit tool, so a run does not stop on
a per-file approval for every path under `.claude/` or `.cursor/`. Those Bash
calls would still prompt, which puts the question back. This hook answers it for
exactly the plugin's own scripts and stays silent on everything else — silence
means the host's normal permission flow decides, so this can only ever remove
prompts np itself caused.

Reads the PreToolUse payload on stdin, prints an `allow` decision on stdout when
every one of these holds, and prints nothing otherwise:

  * tool is Bash;
  * the command invokes `python3`/`python` on an absolute path that resolves to a
    script inside THIS plugin's `scripts/` directory, and is one of ALLOWED;
  * the subcommand is one the script actually has;
  * the remaining arguments carry no shell metacharacter — no chaining, no
    substitution, no redirection;
  * any heredoc is the quoted form (`<<'TAG'`), whose body the shell passes
    through verbatim: data for the script's stdin, never anything the shell runs.

Exit status is always 0. A malformed payload, an unset plugin root, or anything
unrecognised is a no-decision, never a denial.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ALLOWED = {"harmonize_scan.py": {"scan", "digest", "baseline", "upkeep", "layer", "rehash", "align"}}
# No ; & | ` $ ( ) < > newline-chaining — the heredoc marker is handled separately.
UNSAFE = re.compile(r"[;&|`$()<>\\]")
INVOCATION = re.compile(
    r"""^\s*(?:python3?|"python3?")\s+            # the interpreter, nothing exotic
         (?P<q>["']?)(?P<script>/[^"'\s]+)(?P=q)  # an absolute path to the script
         (?P<args>.*)$""", re.X)
HEREDOC = re.compile(r"<<\s*(?P<q>['\"])(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=q)\s*$")


def plugin_scripts_dir() -> Path | None:
    root = (os.environ.get("NP_PLUGIN_ROOT") or os.environ.get("CURSOR_PLUGIN_ROOT")
            or os.environ.get("CLAUDE_PLUGIN_ROOT"))
    base = Path(root) if root else Path(__file__).resolve().parent.parent
    try:
        return (base / "scripts").resolve(strict=True)
    except OSError:
        return None


def decide(payload: dict) -> str | None:
    if payload.get("tool_name") != "Bash":
        return None
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        return None

    head, _, body = command.partition("\n")
    tag = None
    m = HEREDOC.search(head)
    if m:
        tag = m.group("tag")
        head = head[:m.start()]
    elif body.strip():
        return None                       # several commands in one call — not ours to judge

    if tag is not None:
        lines = body.split("\n")
        # the body must end at its terminator: nothing after it is heredoc data
        if tag not in lines or any(line.strip() for line in lines[lines.index(tag) + 1:]):
            return None

    inv = INVOCATION.match(head)
    if not inv:
        return None
    args = inv.group("args")
    if UNSAFE.search(args):
        return None

    scripts = plugin_scripts_dir()
    if scripts is None:
        return None
    try:
        script = Path(inv.group("script")).resolve(strict=True)
    except OSError:
        return None
    if script.parent != scripts or script.name not in ALLOWED:
        return None

    words = [w.strip("\"'") for w in args.split()]
    if not words or words[0] not in ALLOWED[script.name]:
        return None
    return f"np: {script.name} {words[0]} — the plugin's own script, writing only inside its own boundary"


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        reason = decide(payload) if isinstance(payload, dict) else None
    except Exception:                     # a hook must never break the session
        reason = None
    if reason:
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "permissionDecision": "allow",
                                          "permissionDecisionReason": reason}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
