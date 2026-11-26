#!/usr/bin/env python3
"""np provenance — a committed ledger of which files each run generated.

The plugin never commits; the dev does. So by the time a PR exists nothing
distinguishes a np-written hunk from a hand-written one. This module records,
at the end of each generating stage, the git blob hash of every file the run
touched, into `<np-home>/np-provenance.jsonl` (committed, next to
np.config.json). A reviewer then verifies a PR's files against it: the blob
hash GitHub reports for a file either matches the ledger — this exact content
came from run X, untouched — or it does not.

Design points (each was a pressure-test finding):
  * The touched set comes from GIT, not from handoff `files_*` lists: those are
    scattered across ~10 result files with three different path roots. Git's
    view is exact and toplevel-relative, which is also what GitHub reports.
  * Hashes are git blob ids (`git hash-object`, clean filters applied) so they
    equal GitHub's `pulls/N/files[].sha` with no content download and no
    CRLF drift. sha256 of raw bytes is the fallback when git cannot hash.
  * Append-only JSONL with `merge=union`; "latest entry per file" is decided
    by (recorded_at, run_id), never by line position, because union
    interleaves. The reader tolerates conflict markers and bad lines.
  * No per-agent attribution: a verifier or fixer routinely touches another
    agent's file, so any agent claim would be wrong. `stage` is the honest
    granularity.
  * A missing ledger entry is `no-record`, never "hand-written" — an absent
    entry cannot assert authorship (the dev may simply not have committed
    the ledger).

Stdlib only. All git calls run with cwd = the repository toplevel.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from context_store import (
    ContextStoreError,
    np_home,
    np_home_names,
    load_config,
)

LEDGER_NAME = "np-provenance.jsonl"
# Build/cache noise that git may report as changed but which no run "generated".
# `__pycache__` is the common one: the vendored MCP server byte-compiles itself
# on first use, and in local mode <np-home>/ is committed.
NOISE_PARTS = {"__pycache__", ".git", ".cocoindex_code", "node_modules"}
NOISE_SUFFIXES = (".pyc", ".pyo")
# In local/vendored installs the plugin's own runtime lives inside <np-home>/
# and is committed, so installing or upgrading it dirties the tree. Those files
# are the tool, not something a run generated — never attribute them.
# `project_context/` and `np.config.json` are deliberately NOT here: those are
# project artifacts np really does produce.
PLUGIN_RUNTIME_DIRS = {"bin", "mcp", "scripts", "templates", "skills", "agents",
                       "commands", "rules", "hooks", ".claude-plugin", ".cursor-plugin",
                       ".np-install-backup"}
PLUGIN_RUNTIME_FILES = {"settings.json", ".mcp.json", "mcp.json", "hooks.json",
                        "THIRD-PARTY-NOTICES.md", ".np-generated", ".np-install.json"}
HANDOFF_LIST_KEYS_CREATED = ("files_created", "file_created", "files_generated",
                             "test_files_generated")
HANDOFF_LIST_KEYS_MODIFIED = ("files_modified", "step_files_modified")
CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")
GIT_TIMEOUT_S = 60


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _git(cwd: Path, *args: str, input_text: Optional[str] = None,
         check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), input=input_text, text=True,
        capture_output=True, timeout=GIT_TIMEOUT_S, check=check,
    )


def toplevel(start: Path) -> Optional[Path]:
    """Repository toplevel for `start`, or None outside a git work tree."""
    try:
        r = _git(start, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return Path(r.stdout.strip()).resolve()


def plugin_version() -> str:
    """'np/<version>' from the plugin manifest, 'np/unknown' when unresolvable.

    Candidate roots mirror context_store._find_ccc_wrapper; the Cursor build
    carries .cursor-plugin/plugin.json instead of .claude-plugin/plugin.json.
    """
    roots: List[Path] = []
    for env_var in ("NP_PLUGIN_ROOT", "CURSOR_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        v = os.environ.get(env_var)
        if v:
            roots.append(Path(v))
    roots.append(Path(__file__).resolve().parent.parent)
    for root in roots:
        for manifest in (".claude-plugin/plugin.json", ".cursor-plugin/plugin.json"):
            p = root / manifest
            if p.is_file():
                try:
                    v = json.loads(p.read_text(encoding="utf-8")).get("version")
                    if v:
                        return f"np/{v}"
                except (OSError, json.JSONDecodeError):
                    continue
    return "np/unknown"


def host_name() -> str:
    return os.environ.get("NP_HOST", "claude")


def enabled(cfg: Dict[str, Any]) -> bool:
    # Absent means enabled: re-init never rewrites np.config.json, so upgraded
    # repos will not carry the key.
    return bool((cfg.get("provenance") or {}).get("enabled", True))


def ledger_path(project_root: Path) -> Path:
    return np_home(project_root) / LEDGER_NAME


def all_ledger_paths(project_root: Path) -> List[Path]:
    """Every existing ledger across the probe homes — a repo initialized from
    two editors may carry two."""
    root = Path(project_root)
    found = []
    for name in np_home_names():
        p = root / name / LEDGER_NAME
        if p.is_file():
            found.append(p)
    return found


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel_to(top: Path, path: Path) -> Optional[str]:
    try:
        return path.resolve().relative_to(top).as_posix()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Touched-file discovery
# ---------------------------------------------------------------------------

def _is_plugin_runtime(rel: str, home_rel: Optional[str]) -> bool:
    """True for the plugin's own vendored files inside <np-home>/ — the tool
    itself, which an install or upgrade dirties. Not a run's output."""
    if not home_rel:
        return False
    prefix = home_rel.rstrip("/") + "/"
    if not rel.startswith(prefix):
        return False
    tail = rel[len(prefix):]
    head = tail.split("/", 1)[0]
    return head in PLUGIN_RUNTIME_DIRS or tail in PLUGIN_RUNTIME_FILES


def _under_any(rel: str, prefixes: Iterable[str]) -> bool:
    """Prefix-aware match: `preexisting_dirty` may hold `dir/` entries."""
    for d in prefixes:
        d = d.strip()
        if not d:
            continue
        if rel == d.rstrip("/"):
            return True
        if rel.startswith(d.rstrip("/") + "/"):
            return True
    return False


def git_changed_since(top: Path, baseline: str) -> Dict[str, str]:
    """Tracked files changed between `baseline` and the work tree.

    --no-renames so a rename is D-old + A-new (we never list D, so the new
    path shows as created — consistent with GitHub's `renamed` filename).
    T (typechange) counts as modified. Deletions are excluded by the filter.
    """
    r = _git(top, "diff", "--name-status", "-z", "--no-renames",
             "--diff-filter=ACMTUXB", baseline, "--")
    if r.returncode != 0:
        raise ContextStoreError(f"git diff failed: {r.stderr.strip()}")
    parts = r.stdout.split("\0")
    out: Dict[str, str] = {}
    i = 0
    while i + 1 < len(parts):
        status, path = parts[i], parts[i + 1]
        i += 2
        if not path:
            continue
        out[path] = "created" if status.startswith("A") else "modified"
    return out


def git_untracked(top: Path) -> List[str]:
    """Untracked FILES (directories expanded), .gitignore honoured."""
    r = _git(top, "ls-files", "--others", "--exclude-standard", "-z")
    if r.returncode != 0:
        raise ContextStoreError(f"git ls-files failed: {r.stderr.strip()}")
    return [p for p in r.stdout.split("\0") if p]


def _exists_in_commit(top: Path, commit: str, rel: str) -> bool:
    return _git(top, "cat-file", "-e", f"{commit}:{rel}").returncode == 0


def _commit_reachable(top: Path, commit: Optional[str]) -> bool:
    if not commit:
        return False
    return _git(top, "cat-file", "-e", f"{commit}^{{commit}}").returncode == 0


def _iter_handoff_lists(handoff_dir: Path) -> Tuple[List[str], List[str]]:
    """Every path any result handoff claims to have created / modified."""
    created: List[str] = []
    modified: List[str] = []
    if not handoff_dir.is_dir():
        return created, modified
    for f in sorted(handoff_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key in HANDOFF_LIST_KEYS_CREATED:
            v = data.get(key)
            if isinstance(v, str):
                created.append(v)
            elif isinstance(v, list):
                created.extend(x for x in v if isinstance(x, str))
        for key in HANDOFF_LIST_KEYS_MODIFIED:
            v = data.get(key)
            if isinstance(v, list):
                modified.extend(x for x in v if isinstance(x, str))
        fixes = data.get("fixes_applied")
        if isinstance(fixes, list):
            modified.extend(x.get("file") for x in fixes
                            if isinstance(x, dict) and isinstance(x.get("file"), str))
    return created, modified


def _resolve_handoff_path(raw: str, bases: List[Path], top: Path) -> Optional[str]:
    """A handoff path may be toplevel-, project-, app- or module-relative.
    Return the toplevel-relative posix path of the first base it exists under."""
    if not raw or raw.startswith("{"):
        return None
    p = Path(raw)
    candidates = [p] if p.is_absolute() else [b / p for b in bases]
    for c in candidates:
        if c.is_file():
            return _rel_to(top, c)
    return None


def _resolution_bases(top: Path, project_root: Path, handoff_dir: Path,
                      cfg: Dict[str, Any]) -> List[Path]:
    bases: List[Path] = [top, project_root]
    # frontend_path from any request handoff (app-relative frontend paths)
    for name in ("frontend-00-request.json", "00-request.json"):
        f = handoff_dir / name
        if f.is_file():
            try:
                fp = json.loads(f.read_text(encoding="utf-8")).get("frontend_path")
                if isinstance(fp, str) and fp:
                    fpp = Path(fp)
                    bases.append(fpp if fpp.is_absolute() else project_root / fpp)
            except (OSError, json.JSONDecodeError):
                pass
    # stack roots (module-relative backend paths)
    for stack in cfg.get("stacks") or []:
        for r in (stack.get("roots") or []) if isinstance(stack, dict) else []:
            if isinstance(r, str):
                bases.append(project_root / r)
    seen, out = set(), []
    for b in bases:
        key = str(b)
        if key not in seen:
            seen.add(key)
            out.append(b)
    return out


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _blob_of_bytes(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def blob_hashes(top: Path, rel_paths: List[str], use_git: bool = True
                ) -> Dict[str, Tuple[str, str]]:
    """rel path -> (hash, kind). kind is 'blob' (git object id) or 'sha256'.

    Symlinks: git stores the link target string, not the pointed-to file, so
    hash that. Regular files: ONE `git hash-object --stdin-paths` applies the
    per-path clean filters exactly as `git add` would — equal to GitHub's
    blob sha. If the batch fails (e.g. an LFS filter with git-lfs missing),
    retry per file so one bad filter cannot poison the batch; a file that
    still fails gets sha256 of its raw bytes, flagged by kind.
    """
    out: Dict[str, Tuple[str, str]] = {}
    regular: List[str] = []
    for rel in rel_paths:
        p = top / rel
        if p.is_symlink():
            out[rel] = (_blob_of_bytes(os.readlink(p).encode()), "blob")
        elif p.is_file():
            regular.append(rel)
    if not regular:
        return out
    if use_git:
        r = _git(top, "hash-object", "--stdin-paths",
                 input_text="\n".join(regular) + "\n")
        if r.returncode == 0:
            hashes = r.stdout.split()
            if len(hashes) == len(regular):
                for rel, h in zip(regular, hashes):
                    out[rel] = (h, "blob")
                return out
        for rel in regular:
            r1 = _git(top, "hash-object", "--", rel)
            if r1.returncode == 0 and r1.stdout.strip():
                out[rel] = (r1.stdout.strip(), "blob")
            else:
                out[rel] = (_sha256_file(top / rel), "sha256")
        return out
    for rel in regular:
        # no git at all: an unfiltered in-process blob id still matches GitHub
        # for files without clean filters, and is exact for local verify
        out[rel] = (_blob_of_bytes((top / rel).read_bytes()), "blob")
    return out


# ---------------------------------------------------------------------------
# Ledger I/O
# ---------------------------------------------------------------------------

def read_ledgers(paths: Iterable[Path]) -> Tuple[List[Dict[str, Any]], int]:
    """All entries across the given ledger files, plus a malformed-line count.
    Tolerates blank lines, merge-conflict markers, and bad JSON."""
    entries: List[Dict[str, Any]] = []
    malformed = 0
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith(CONFLICT_MARKERS):
                if s.startswith(CONFLICT_MARKERS):
                    malformed += 1
                continue
            try:
                e = json.loads(s)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if isinstance(e, dict) and isinstance(e.get("file"), str):
                entries.append(e)
            else:
                malformed += 1
    return entries, malformed


def latest_per_file(entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Newest entry per file by (recorded_at, run_id) — never by position."""
    latest: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        key = (str(e.get("recorded_at", "")), str(e.get("run_id", "")))
        cur = latest.get(e["file"])
        if cur is None or key > (str(cur.get("recorded_at", "")), str(cur.get("run_id", ""))):
            latest[e["file"]] = e
    return latest


def _append_lines(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = ("\n".join(lines) + "\n").encode("utf-8")
    # union merges and stray appends can leave a file without a final newline;
    # never glue two objects onto one line
    if path.exists() and path.stat().st_size and path.read_bytes()[-1:] != b"\n":
        buf = b"\n" + buf
    with open(path, "ab") as fh:
        fh.write(buf)


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

def record(project_root: Path, handoff_dir: str, stage: str) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    cfg = load_config(project_root)
    if not enabled(cfg):
        return {"success": True, "recorded": [], "unchanged": [], "skipped": [],
                "warnings": [], "note": "provenance.enabled is false in np.config.json"}

    hdir = Path(handoff_dir)
    hdir = hdir if hdir.is_absolute() else project_root / hdir
    req_file = hdir / "00-request.json"
    if not req_file.is_file():
        req_file = hdir / "frontend-00-request.json"
    if not req_file.is_file():
        raise ContextStoreError(f"no 00-request.json in {hdir}")
    try:
        req = json.loads(req_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContextStoreError(f"invalid 00-request.json: {e}")

    run_dir = req.get("run_dir") or str(hdir.parent)
    run_id = Path(str(run_dir)).name
    baseline = req.get("baseline_commit")
    preexisting = [p for p in (req.get("preexisting_dirty") or []) if isinstance(p, str)]
    runs_root = str((cfg.get("harness") or {}).get("runs_root") or ".np-runs")

    top = toplevel(project_root)
    warnings: List[str] = []
    use_git = top is not None
    if top is None:
        top = project_root
        baseline_status = "none"
    elif not baseline:
        baseline_status = "none"
    elif not _commit_reachable(top, baseline):
        baseline_status = "unreachable"
        warnings.append(f"baseline_commit {baseline} is not reachable in this repository — "
                        "touched files were taken from the run's handoffs and untracked files")
    else:
        baseline_status = "ok"

    ledger = ledger_path(project_root)
    ledger_rel = _rel_to(top, ledger) or ledger.name
    home_rel = _rel_to(top, np_home(project_root))
    if use_git and _git(top, "check-ignore", "-q", ledger_rel).returncode == 0:
        rule = _git(top, "check-ignore", "-v", ledger_rel).stdout.strip()
        return {"success": False,
                "error": f"the provenance ledger is gitignored ({rule or ledger_rel}) — "
                         "it cannot be committed with the change; fix .gitignore first",
                "ledger": str(ledger)}

    # -- touched set ----------------------------------------------------------
    touched: Dict[str, Tuple[str, str]] = {}   # rel -> (action, source)
    if baseline_status == "ok":
        for rel, action in git_changed_since(top, baseline).items():
            touched[rel] = (action, "git")
        for rel in git_untracked(top):
            touched.setdefault(rel, ("created", "git"))
    elif use_git:
        for rel in git_untracked(top):
            touched.setdefault(rel, ("created", "git"))

    created_raw, modified_raw = _iter_handoff_lists(hdir)
    bases = _resolution_bases(top, project_root, hdir, cfg)
    for raw, default_action in [(p, "created") for p in created_raw] + \
                               [(p, "modified") for p in modified_raw]:
        rel = _resolve_handoff_path(raw, bases, top)
        if rel is None:
            continue
        if rel in touched:
            action, _ = touched[rel]
            touched[rel] = (action, "both")
        else:
            action = default_action
            if use_git and baseline_status == "ok":
                action = "modified" if _exists_in_commit(top, baseline, rel) else "created"
            elif use_git:
                action = "modified" if _exists_in_commit(top, "HEAD", rel) else "created"
            touched[rel] = (action, "handoff")

    # -- exclusions ------------------------------------------------------------
    run_root_rel = _rel_to(top, project_root / runs_root) or runs_root
    skipped: List[Dict[str, str]] = []
    keep: Dict[str, Tuple[str, str]] = {}
    for rel, (action, source) in touched.items():
        if rel == ledger_rel or rel.endswith("/" + LEDGER_NAME):
            continue
        if _under_any(rel, [run_root_rel]):
            continue
        if NOISE_PARTS & set(Path(rel).parts) or rel.endswith(NOISE_SUFFIXES):
            continue
        if _is_plugin_runtime(rel, home_rel):
            continue
        if _under_any(rel, preexisting):
            skipped.append({"file": rel, "reason": "preexisting_dirty"})
            continue
        if not (top / rel).exists():
            skipped.append({"file": rel, "reason": "missing"})
            continue
        keep[rel] = (action, source)

    # -- hash + idempotent append ---------------------------------------------
    hashes = blob_hashes(top, sorted(keep), use_git=use_git)
    existing, _ = read_ledgers([ledger])
    latest = latest_per_file(existing)
    now = _now_iso()
    plugin = plugin_version()
    host = host_name()
    recorded: List[Dict[str, str]] = []
    unchanged: List[str] = []
    lines: List[str] = []
    for rel in sorted(keep):
        if rel not in hashes:
            skipped.append({"file": rel, "reason": "unhashable"})
            continue
        h, kind = hashes[rel]
        action, source = keep[rel]
        prev = latest.get(rel)
        if prev and prev.get("run_id") == run_id and prev.get("stage") == stage \
                and prev.get("blob") == h:
            unchanged.append(rel)
            continue
        entry = {
            "action": action, "blob": h, "file": rel, "hash": kind, "host": host,
            "plugin": plugin, "recorded_at": now, "run_id": run_id,
            "source": source, "stage": stage,
        }
        lines.append(json.dumps(entry, sort_keys=True, ensure_ascii=False))
        recorded.append({"file": rel, "action": action, "hash": h, "kind": kind})
    if lines:
        _append_lines(ledger, lines)

    return {
        "success": True, "run_id": run_id, "stage": stage, "ledger": str(ledger),
        "ledger_rel": ledger_rel, "baseline_status": baseline_status,
        "plugin": plugin, "host": host,
        "recorded": recorded, "unchanged": unchanged, "skipped": skipped,
        "warnings": warnings,
        "trailer": f"Generated-By: {plugin} run={run_id}",
    }


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def verify(project_root: Optional[Path], files: Optional[List[str]] = None,
           root: Optional[str] = None, ledgers: Optional[List[str]] = None,
           blobs: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Classify files against the ledger.

    files   : toplevel-relative paths (default: every file the ledgers know)
    root    : directory holding the files to hash (default: the repo); pass
              the materialized PR copies for a remote review
    ledgers : ledger files to read (default: every existing <home>/ledger)
    blobs   : {file: blob sha} already known (e.g. GitHub's pulls/N/files);
              when given, no hashing is needed for those files
    """
    if ledgers:
        ledger_files = [Path(l) for l in ledgers]
    elif project_root is not None:
        ledger_files = all_ledger_paths(Path(project_root))
    else:
        ledger_files = []
    entries, malformed = read_ledgers(ledger_files)
    latest = latest_per_file(entries)

    top: Optional[Path] = None
    use_git = False
    if root:
        top = Path(root).resolve()
    elif project_root is not None:
        top = toplevel(Path(project_root)) or Path(project_root).resolve()
        use_git = toplevel(Path(project_root)) is not None
    blobs = dict(blobs or {})

    targets = list(files) if files else sorted(latest)
    need_hash = [f for f in targets if f not in blobs and top is not None
                 and (top / f).exists()]
    hashed = blob_hashes(top, need_hash, use_git=use_git) if (top and need_hash) else {}

    rows: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for f in targets:
        e = latest.get(f)
        if e is None:
            status = "no-record"
            row: Dict[str, Any] = {"file": f, "status": status}
        else:
            base = "generated" if e.get("action") == "created" else "np-modified"
            if f in blobs:
                cur, kind = blobs[f], "blob"
            elif f in hashed:
                cur, kind = hashed[f]
            elif top is not None and not (top / f).exists():
                cur, kind = None, None
            else:
                cur, kind = None, None
            if cur is None:
                status = "deleted" if (top is not None and not (top / f).exists()) else "unverifiable"
            elif e.get("hash", "blob") != kind:
                status = "unverifiable"
            else:
                status = f"{base}-unmodified" if cur == e.get("blob") else f"{base}-edited"
            row = {"file": f, "status": status, "run_id": e.get("run_id"),
                   "stage": e.get("stage"), "recorded_at": e.get("recorded_at"),
                   "plugin": e.get("plugin"), "host": e.get("host")}
        rows.append(row)
        counts[status] = counts.get(status, 0) + 1

    np_touched = sum(v for k, v in counts.items() if k != "no-record")
    unmodified = sum(v for k, v in counts.items() if k.endswith("-unmodified"))
    runs = sorted({r["run_id"] for r in rows if r.get("run_id")})
    return {
        "success": True, "ledgers": [str(p) for p in ledger_files],
        "files": rows, "counts": counts, "malformed": malformed,
        "summary": {"checked": len(rows), "np_touched": np_touched,
                    "unmodified": unmodified, "runs": runs},
    }
