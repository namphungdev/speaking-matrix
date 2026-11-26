#!/usr/bin/env python3
"""ctx_tool — CLI twin of the np-workspace context tools (CONTRACT.md §6).

Subcommands mirror the five context tools for shell use and testing:

  add        → context_add_entry
  supersede  → context_supersede
  get        → context_get
  list       → context_list
  sync       → context_sync
  prune      → (extra) archive entries superseded > N days ago
               (used by the np reindex command with --prune)

All output is JSON on stdout. Failures print {"success": false, "error": ...}
and exit 1. Runs on plain python3 (no third-party deps required).

Examples:
  python3 ctx_tool.py add --kind lesson --title "Vitest needs jsdom" \\
      --body "Install jsdom for component tests." --tags testing,vitest --modules web
  python3 ctx_tool.py list --kind lesson --status active
  python3 ctx_tool.py get LL-20260721-a3f2
  python3 ctx_tool.py supersede LL-20260721-a3f2 --by LL-20260722-9c1d
  python3 ctx_tool.py sync
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# context_store lives in the sibling mcp/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

from context_store import ContextStoreError, open_store  # noqa: E402


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _read_body(args: argparse.Namespace) -> str:
    if args.body is not None:
        return args.body
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        body = sys.stdin.read()
        # non-interactive stdin may be /dev/null (scripted use) — an empty
        # body means nothing was actually piped, so treat it as missing
        if body.strip():
            return body
    raise ContextStoreError("provide --body, --body-file, or pipe the body on stdin")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctx_tool.py",
        description="CLI twin of the np-workspace context tools",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add a lesson / error-solution / business entry")
    p_add.add_argument("--kind", required=True,
                       choices=["lesson", "error-solution", "business"])
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--body", help="entry body markdown (inline)")
    p_add.add_argument("--body-file", help="read the body from this file")
    p_add.add_argument("--tags", help="comma-separated kebab-case tags")
    p_add.add_argument("--modules", help="comma-separated module names")
    p_add.add_argument("--supersedes", help="id of the entry this one replaces")
    p_add.add_argument("--source", default="manual",
                       help="init|planning|implementation|test|pr-review|feedback|manual")
    p_add.add_argument("--domain", default="general",
                       help="business kind only: domain file stem")

    p_sup = sub.add_parser("supersede", help="mark an entry superseded")
    p_sup.add_argument("id")
    p_sup.add_argument("--by", dest="superseded_by",
                       help="id of the replacing entry")

    p_get = sub.add_parser("get", help="fetch one entry by id")
    p_get.add_argument("id")

    p_list = sub.add_parser("list", help="list entries")
    p_list.add_argument("--kind", choices=["lesson", "error-solution", "business"])
    p_list.add_argument("--status", default="active",
                        choices=["active", "superseded", "all"])
    p_list.add_argument("--module")

    sub.add_parser("sync", help="run `ccc index` via bin/ccc-wrapper.sh")

    p_prune = sub.add_parser(
        "prune", help="archive lessons superseded more than --days ago"
    )
    p_prune.add_argument("--days", type=int, default=30)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = open_store()
        if args.command == "add":
            result = store.add_entry(
                kind=args.kind,
                title=args.title,
                body_md=_read_body(args),
                tags=_split_csv(args.tags),
                modules=_split_csv(args.modules),
                supersedes=args.supersedes,
                source=args.source,
                domain=args.domain,
            )
        elif args.command == "supersede":
            result = store.supersede(args.id, args.superseded_by)
        elif args.command == "get":
            result = store.get(args.id)
        elif args.command == "list":
            result = store.list_entries(
                kind=args.kind, status=args.status, module=args.module
            )
        elif args.command == "sync":
            result = store.sync()
        elif args.command == "prune":
            result = store.prune_archive(days=args.days)
        else:  # pragma: no cover — argparse enforces choices
            raise ContextStoreError(f"unknown command: {args.command}")
    except ContextStoreError as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        return 1
    except Exception as e:  # noqa: BLE001 — CLI boundary
        print(json.dumps({"success": False, "error": f"{type(e).__name__}: {e}"}, indent=2))
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
