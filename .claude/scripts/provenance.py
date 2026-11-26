#!/usr/bin/env python3
"""provenance — CLI twin of the np-workspace provenance tools (CONTRACT.md §6).

  record <handoff_dir> --stage <implement|patch|frontend|test>
      → np_record_provenance: append the run's touched files (git blob hashes)
        to <np-home>/np-provenance.jsonl
  verify [file …] [--root DIR] [--ledger PATH …] [--blobs JSON]
      → np_verify_provenance: classify files against the ledger(s)

All output is JSON on stdout. Failures print {"success": false, "error": ...}
and exit 1. Runs on plain python3 (no third-party deps required).

Examples:
  python3 provenance.py record .np-runs/20260922-101530-add-order-cancellation/.codegen-handoff --stage implement
  python3 provenance.py verify src/Orders/OrderService.cs
  python3 provenance.py verify --root .np-runs/pr-123/files --ledger .np-runs/pr-123/ledger.jsonl \\
      --blobs '{"src/a.cs":"9a3c…"}' src/a.cs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

from context_store import ContextStoreError, find_project_root  # noqa: E402
import provenance  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="provenance.py",
        description="CLI twin of the np-workspace provenance tools",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_rec = sub.add_parser("record", help="record the run's touched files into the ledger")
    p_rec.add_argument("handoff_dir")
    p_rec.add_argument("--stage", required=True,
                       choices=["implement", "patch", "frontend", "test"])

    p_ver = sub.add_parser("verify", help="classify files against the ledger")
    p_ver.add_argument("files", nargs="*")
    p_ver.add_argument("--root", help="directory holding the files to hash (default: repo)")
    p_ver.add_argument("--ledger", action="append", dest="ledgers",
                       help="ledger file to read (repeatable; default: every <home>/ledger)")
    p_ver.add_argument("--blobs", help="JSON object {file: blob sha} of already-known hashes")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = find_project_root()
        if args.command == "record":
            if root is None:
                raise ContextStoreError("np not initialized — no np.config.json found")
            result = provenance.record(root, args.handoff_dir, args.stage)
        elif args.command == "verify":
            blobs = json.loads(args.blobs) if args.blobs else None
            if root is None and not args.ledgers:
                raise ContextStoreError("no np project found — pass --ledger explicitly")
            result = provenance.verify(root, files=args.files or None, root=args.root,
                                       ledgers=args.ledgers, blobs=blobs)
        else:  # pragma: no cover
            raise ContextStoreError(f"unknown command: {args.command}")
    except ContextStoreError as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        return 1
    except Exception as e:  # noqa: BLE001 — CLI boundary
        print(json.dumps({"success": False, "error": f"{type(e).__name__}: {e}"}, indent=2))
        return 1
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
    return 0 if result.get("success", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
