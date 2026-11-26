#!/usr/bin/env python3
"""np-workspace MCP server (CONTRACT.md §6).

Stdio MCP server exposing 12 tools:

  Context (context_store.py):
    context_add_entry, context_supersede, context_get, context_list, context_sync
  Plumbing (handoff.py):
    np_get_handoff, np_write_handoff, np_list_files,
    np_build_verify, np_test_run
  Provenance (provenance.py):
    np_record_provenance, np_verify_provenance

Conventions:
  - Every tool returns JSON text.
  - Any failure returns {"success": false, "error": "<message>"}.
  - The project is located by walking up from cwd to the nearest
    `<np-home>/np.config.json`, where <np-home> is `.claude` (Claude Code)
    or `.cursor` (Cursor) — see context_store.np_home_names(). When absent
    every tool returns
    {"success": false, "error": "np not initialized — run <init command>"}.

Launched via bin/np-mcp.sh (self-bootstrapping venv). Never run this file
with a system python that lacks the `mcp` package.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

import handoff as handoff_mod
import provenance as provenance_mod
from context_store import (
    NOT_INITIALIZED_ERROR,
    ContextStore,
    ContextStoreError,
    find_project_root,
)

app = Server("np-workspace")


# ---------------------------------------------------------------------------
# Tool declarations
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="context_add_entry",
            description=(
                "Add a knowledge entry to the target project's project_context/ tree. "
                "kind=lesson|error-solution writes lessons/<id>.md; kind=business appends an "
                "anchored section to business/<domain>.md. When `supersedes` is given the old "
                "entry is superseded in the same call. Returns {success, id, path}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["lesson", "error-solution", "business"],
                        "description": "Entry kind (decides prefix LL/ES/BC and storage location)",
                    },
                    "title": {"type": "string", "description": "One-line title"},
                    "body_md": {"type": "string", "description": "Markdown body of the entry"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional kebab-case tags",
                    },
                    "modules": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional module names this entry applies to",
                    },
                    "supersedes": {
                        "type": "string",
                        "description": "Optional id of an existing entry this one replaces",
                    },
                    "source": {
                        "type": "string",
                        "description": (
                            "Origin: init|planning|implementation|test|pr-review|feedback|manual "
                            "(default manual)"
                        ),
                    },
                    "domain": {
                        "type": "string",
                        "description": "business kind only: domain file stem (default 'general')",
                    },
                },
                "required": ["kind", "title", "body_md"],
            },
        ),
        Tool(
            name="context_supersede",
            description=(
                "Mark an entry superseded: flips status, sets superseded_by, truncates the body "
                "to one line. Never deletes. Returns {success, id, path}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Entry id (LL-/ES-/BC-...)"},
                    "superseded_by": {
                        "type": "string",
                        "description": "Optional id of the replacing entry",
                    },
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="context_get",
            description=(
                "Fetch one entry (frontmatter + body) by id, including archived entries. "
                "Returns {success, entry:{...,body}}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Entry id (LL-/ES-/BC-...)"}
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="context_list",
            description=(
                "List entries (lessons + business), excluding lessons/_archive/. Filter by "
                "kind, status (default active; 'all' disables the filter), and module. "
                "Returns {success, entries:[{id,type,title,status,updated,tags,modules,path}]}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["lesson", "error-solution", "business"],
                        "description": "Optional kind filter",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "superseded", "all"],
                        "description": "Status filter (default active)",
                    },
                    "module": {
                        "type": "string",
                        "description": "Optional module-name filter (case-insensitive)",
                    },
                },
            },
        ),
        Tool(
            name="context_sync",
            description=(
                "Re-index the project: runs `ccc index` via the plugin's bin/ccc-wrapper.sh "
                "in the project root. Returns {success, output}."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="np_get_handoff",
            description=(
                "Read a JSON handoff file from a pipeline handoff directory "
                "(absolute, or relative to the project root). Returns "
                "{success, content:<parsed json>}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "handoff_dir": {
                        "type": "string",
                        "description": "Handoff directory, e.g. '.np-runs/run-1/.codegen-handoff'",
                    },
                    "name": {
                        "type": "string",
                        "description": "Handoff file name, e.g. '00-request.json'",
                    },
                },
                "required": ["handoff_dir", "name"],
            },
        ),
        Tool(
            name="np_write_handoff",
            description=(
                "Write a JSON handoff file into a pipeline handoff directory (created if "
                "missing). `content` may be a JSON object or a JSON-encoded string. "
                "Returns {success, path}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "handoff_dir": {
                        "type": "string",
                        "description": "Handoff directory, e.g. '.np-runs/run-1/.codegen-handoff'",
                    },
                    "name": {
                        "type": "string",
                        "description": "Handoff file name, e.g. 'phase-1-result.json'",
                    },
                    "content": {
                        "anyOf": [
                            {"type": "object"},
                            {"type": "array"},
                            {"type": "string"},
                        ],
                        "description": "JSON object/array, or a string containing JSON",
                    },
                },
                "required": ["handoff_dir", "name", "content"],
            },
        ),
        Tool(
            name="np_list_files",
            description=(
                "List files under a directory (absolute, or relative to the project root) "
                "with an optional glob (default '**/*'). Skips np.config.json index.exclude "
                "patterns and caps at 500 results. Returns {success, files:[relative paths]}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dir": {"type": "string", "description": "Directory to list"},
                    "glob": {
                        "type": "string",
                        "description": "Glob pattern relative to dir (default '**/*')",
                    },
                },
                "required": ["dir"],
            },
        ),
        Tool(
            name="np_build_verify",
            description=(
                "Run the configured build command for a stack from np.config.json "
                "(default: first stack), substituting {target}. Commands without a "
                "{target} placeholder run from the target directory (when target is "
                "an existing dir) or the stack's first roots entry. Returns "
                "{success, exit_code, errors:[first 50 error lines], output_tail}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "stack_kind": {
                        "type": "string",
                        "description": "stacks[].kind to use (default: first stack)",
                    },
                    "target": {
                        "type": "string",
                        "description": (
                            "Substituted into {target} in the build command; when the "
                            "command has no {target} placeholder and this is an "
                            "existing directory, it becomes the working directory"
                        ),
                    },
                },
            },
        ),
        Tool(
            name="np_test_run",
            description=(
                "Run the configured test command for a stack from np.config.json "
                "(default: first stack), substituting {target}. Commands without a "
                "{target} placeholder run from the target directory (when target is "
                "an existing dir) or the stack's first roots entry. Parses results per "
                "the stack's results_format (trx/vitest, best-effort). Returns {success, "
                "exit_code, summary:{passed,failed,skipped}, failures:[...], output_tail}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "stack_kind": {
                        "type": "string",
                        "description": "stacks[].kind to use (default: first stack)",
                    },
                    "target": {
                        "type": "string",
                        "description": (
                            "Substituted into {target} in the test command; when the "
                            "command has no {target} placeholder and this is an "
                            "existing directory, it becomes the working directory"
                        ),
                    },
                },
            },
        ),
        Tool(
            name="np_record_provenance",
            description=(
                "Record which files a run touched, into the committed ledger "
                "<np-home>/np-provenance.jsonl. Touched set = git changes since the run's "
                "baseline_commit ∪ untracked files, minus preexisting_dirty (handoff file lists "
                "are a secondary source). Hashes are git blob ids, so /np:pr-review can verify "
                "against GitHub's per-file sha with no downloads. Append-only and idempotent. "
                "Call once per generating stage, right before the summary. Returns {success, "
                "run_id, ledger, baseline_status, recorded, unchanged, skipped, warnings, trailer}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "handoff_dir": {
                        "type": "string",
                        "description": "The run's handoff dir holding 00-request.json",
                    },
                    "stage": {
                        "type": "string",
                        "enum": ["implement", "patch", "frontend", "test"],
                        "description": "Which generating stage is recording",
                    },
                },
                "required": ["handoff_dir", "stage"],
            },
        ),
        Tool(
            name="np_verify_provenance",
            description=(
                "Classify files against the provenance ledger(s): generated-unmodified, "
                "generated-edited, np-modified-unmodified, np-modified-edited, no-record, "
                "unverifiable, deleted. Latest ledger entry per file wins (by recorded_at). "
                "For a remote PR review pass `blobs` (GitHub's pulls/N/files sha map) and "
                "`ledgers` (the PR-side ledger); `root` points at materialized copies. "
                "Returns {success, files:[{file,status,run_id,stage,...}], counts, summary}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Toplevel-relative paths (default: every file the ledger knows)",
                    },
                    "root": {
                        "type": "string",
                        "description": "Directory holding the files to hash (default: the repo)",
                    },
                    "ledgers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ledger files to read (default: every existing <home>/ledger)",
                    },
                    "blobs": {
                        "type": "object",
                        "description": "{file: blob sha} already known, e.g. from GitHub",
                    },
                },
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _json_content(payload: Dict[str, Any]) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]


def _error(message: str) -> List[TextContent]:
    return _json_content({"success": False, "error": message})


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    arguments = arguments or {}
    try:
        project_root = find_project_root()
        if project_root is None:
            return _error(NOT_INITIALIZED_ERROR)
        store = ContextStore(project_root)
        result = await asyncio.to_thread(
            _dispatch_sync, name, arguments, store
        )
        return _json_content(result)
    except ContextStoreError as e:
        return _error(str(e))
    except Exception as e:  # last-resort: never crash the server on a tool call
        return _error(f"{type(e).__name__}: {e}")


def _dispatch_sync(name: str, args: Dict[str, Any], store: ContextStore) -> Dict[str, Any]:
    root = store.project_root
    if name == "context_add_entry":
        return store.add_entry(
            kind=args["kind"],
            title=args["title"],
            body_md=args["body_md"],
            tags=args.get("tags"),
            modules=args.get("modules"),
            supersedes=args.get("supersedes"),
            source=args.get("source") or "manual",
            domain=args.get("domain") or "general",
        )
    if name == "context_supersede":
        return store.supersede(args["id"], args.get("superseded_by"))
    if name == "context_get":
        return store.get(args["id"])
    if name == "context_list":
        return store.list_entries(
            kind=args.get("kind"),
            status=args.get("status") or "active",
            module=args.get("module"),
        )
    if name == "context_sync":
        return store.sync()
    if name == "np_get_handoff":
        return handoff_mod.get_handoff(root, args["handoff_dir"], args["name"])
    if name == "np_write_handoff":
        return handoff_mod.write_handoff(
            root, args["handoff_dir"], args["name"], args["content"]
        )
    if name == "np_list_files":
        return handoff_mod.list_files(root, args["dir"], args.get("glob") or "**/*")
    if name == "np_build_verify":
        return handoff_mod.build_verify(
            root, args.get("stack_kind"), args.get("target")
        )
    if name == "np_test_run":
        return handoff_mod.test_run(
            root, args.get("stack_kind"), args.get("target")
        )
    if name == "np_record_provenance":
        return provenance_mod.record(root, args["handoff_dir"], args["stage"])
    if name == "np_verify_provenance":
        return provenance_mod.verify(
            root, files=args.get("files"), root=args.get("root"),
            ledgers=args.get("ledgers"), blobs=args.get("blobs"),
        )
    raise ContextStoreError(f"unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
