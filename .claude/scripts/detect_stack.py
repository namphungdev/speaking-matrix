#!/usr/bin/env python3
"""detect_stack — deterministic stack/module scan for np-init (CONTRACT.md §1).

Walks a repository and emits ONE JSON document on stdout describing:
  - stacks       : detected toolchains by marker files, with suggested
                   np.config.json stacks[] entries ({target} substitution ready)
  - module_candidates : directories that own project files, with layout signals
                   (layer folder names, project-file counts, messaging/api hints)
  - parent_groups: directories whose immediate children are themselves project
                   dirs (multi-project layout signal)

This script is 100% deterministic: filesystem walk + marker matching only.
NO LLM calls, no network, stdlib only. A model (the np-init skill) consumes
this JSON afterwards to classify layout families and pick reference modules.

Marker files → stack kind:
  *.sln / *.csproj                  → dotnet
  package.json                      → node (react-ts when react+typescript detected)
  pyproject.toml/requirements.txt/setup.py → python
  go.mod                            → go
  pom.xml / build.gradle(.kts)      → jvm
  Program.cs + appsettings.json     → dotnet WEAK marker (host dir without a
                                      project file — happens mid-refactor);
                                      candidate gets signals.has_project_file=false

Usage: detect_stack.py [root] [--max-depth N] [--max-candidates N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Host home dirs that may hold np.config.json, in probe order. Kept in sync
# with context_store.NP_HOME_CANDIDATES; duplicated (not imported) because
# this script is deliberately stdlib-only and standalone.
NP_HOME_CANDIDATES = (".cursor", ".claude", ".np")
NP_HOME_DEFAULT = ".claude"


def _np_home_names() -> tuple:
    forced = os.environ.get("NP_HOME", "").strip()
    return (forced,) if forced else NP_HOME_CANDIDATES

SKIP_DIRS: Set[str] = {
    ".git", ".hg", ".svn",
    "node_modules", "bin", "obj", "dist", "build", "out", "target",
    ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".cocoindex_code", ".np-runs",
    ".next", ".nuxt", ".idea", ".vs", ".vscode", "coverage",
    "TestResults", "_archive", ".terraform",
}
# NOTE: "packages" is deliberately NOT in SKIP_DIRS — JS/TS workspace
# monorepos (pnpm/yarn/npm workspaces) keep first-party modules under
# packages/*. Legacy NuGet output dirs also called packages/ are pruned
# conditionally via _is_nuget_packages_dir() instead.

PROJECT_MARKERS: Dict[str, str] = {
    # exact-name markers
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "go.mod": "go",
    "pom.xml": "jvm",
    "build.gradle": "jvm",
    "build.gradle.kts": "jvm",
}
SUFFIX_MARKERS: Dict[str, str] = {
    ".sln": "dotnet",
    ".csproj": "dotnet",
}

LAYER_DIR_NAMES: Set[str] = {
    "api", "application", "domain", "infrastructure", "controllers",
    "services", "entities", "models", "repositories", "middleware",
    "messagequeue", "dependencyinjection", "features", "functions",
    "src", "app", "components", "pages", "hooks", "lib", "utils",
    "cmd", "internal", "pkg", "handlers", "migrations", "tests", "test",
}

TEST_NAME_HINTS = (".tests", ".test", "-tests", "-test", "_tests", "_test")


def _stack_of(filename: str) -> Optional[str]:
    if filename in PROJECT_MARKERS:
        return PROJECT_MARKERS[filename]
    for suffix, kind in SUFFIX_MARKERS.items():
        if filename.endswith(suffix):
            return kind
    return None


def _refine_node_kind(dir_path: Path) -> str:
    """node → react-ts when react + typescript are present."""
    pkg = dir_path / "package.json"
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "node"
    deps: Dict[str, Any] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        block = data.get(key)
        if isinstance(block, dict):
            deps.update(block)
    has_react = "react" in deps
    has_ts = "typescript" in deps or (dir_path / "tsconfig.json").is_file()
    return "react-ts" if has_react and has_ts else "node"


def _node_test_command(dir_path: Path) -> str:
    pkg = dir_path / "package.json"
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "npm test"
    deps: Dict[str, Any] = {}
    for key in ("dependencies", "devDependencies"):
        block = data.get(key)
        if isinstance(block, dict):
            deps.update(block)
    if "vitest" in deps:
        return "npx vitest run"
    if "jest" in deps:
        return "npx jest --ci"
    return "npm test"


def _is_nuget_packages_dir(path: Path) -> bool:
    """True when a dir named 'packages' looks like a legacy NuGet output
    folder (children are Package.Version dirs holding .nupkg files) rather
    than a JS/TS workspace source dir (children hold package.json/*.csproj)."""
    try:
        child_dirs = [c for c in path.iterdir() if c.is_dir()]
    except OSError:
        return False
    for child in child_dirs[:50]:
        try:
            names = {p.name for p in child.iterdir()}
        except OSError:
            continue
        if "package.json" in names or any(n.endswith(".csproj") for n in names):
            return False  # first-party source module → keep scanning
        if any(n.endswith(".nupkg") for n in names):
            return True   # NuGet cache → prune
    # No source markers in any immediate child: treat as NuGet output only
    # when a sibling solution file exists (the classic packages/-next-to-.sln
    # layout); otherwise keep scanning — a marker-less dir adds no candidates.
    try:
        return any(p.name.endswith(".sln") for p in path.parent.iterdir())
    except OSError:
        return False


def _dir_has_named_subdir(dir_path: Path, name_ci: str, depth: int = 2) -> bool:
    """True when a subdirectory named `name_ci` (case-insensitive) exists
    within `depth` levels below dir_path."""
    frontier = [dir_path]
    for _ in range(depth):
        next_frontier: List[Path] = []
        for d in frontier:
            try:
                for child in d.iterdir():
                    if not child.is_dir() or child.name in SKIP_DIRS:
                        continue
                    if child.name.lower() == name_ci:
                        return True
                    next_frontier.append(child)
            except OSError:
                continue
        frontier = next_frontier
    return False


def scan(root: Path, max_depth: int, max_candidates: int) -> Dict[str, Any]:
    root = root.resolve()
    stack_marker_files: Dict[str, List[str]] = {}   # kind -> project-file rel paths
    candidates: Dict[str, Dict[str, Any]] = {}      # rel dir -> candidate
    notes: List[str] = []
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel_dir = current.relative_to(root).as_posix()
        depth = 0 if rel_dir == "." else rel_dir.count("/") + 1

        # prune noise + depth ("packages" only when it is NuGet output,
        # never when it is a JS/TS workspace source dir)
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
            and not (d == "packages" and _is_nuget_packages_dir(current / d))
        )
        if depth >= max_depth:
            dirnames[:] = []

        project_files: Dict[str, str] = {}  # filename -> kind
        for filename in sorted(filenames):
            kind = _stack_of(filename)
            if kind is None:
                continue
            if kind == "node" and filename == "package.json":
                kind = _refine_node_kind(current)
            if kind == "python" and rel_dir != ".":
                # requirements.txt deep in a repo is a weak signal; keep it,
                # but only as marker (still deterministic)
                pass
            project_files[filename] = kind
            rel_file = filename if rel_dir == "." else f"{rel_dir}/{filename}"
            stack_marker_files.setdefault(kind, []).append(rel_file)

        # weak dotnet marker: a host dir (Program.cs + appsettings.json) whose
        # project file is missing/elsewhere — still a real module candidate
        weak_dotnet = (
            not project_files
            and "Program.cs" in filenames
            and "appsettings.json" in filenames
        )

        if not project_files and not weak_dotnet:
            continue
        if len(candidates) >= max_candidates:
            truncated = True
            continue

        sub_dirs = []
        try:
            sub_dirs = sorted(
                d.name for d in current.iterdir()
                if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith(".")
            )
        except OSError:
            pass
        layer_dirs = [d for d in sub_dirs if d.lower() in LAYER_DIR_NAMES]
        dominant_kind = "dotnet" if weak_dotnet else _dominant_kind(project_files)
        name_lower = current.name.lower()

        candidates[rel_dir] = {
            "path": rel_dir,
            "name": current.name if rel_dir != "." else root.name,
            "stack": dominant_kind,
            "project_files": sorted(project_files.keys()),
            "project_file_count": len(project_files),
            "layer_dirs": layer_dirs,
            "sub_dirs": sub_dirs[:30],
            "signals": {
                "has_project_file": bool(project_files),
                "has_messaging_dir": _dir_has_named_subdir(current, "messagequeue"),
                "has_api_dir": any(d.lower() in ("api", "controllers") for d in sub_dirs)
                or _dir_has_named_subdir(current, "controllers"),
                "has_sln": any(f.endswith(".sln") for f in project_files),
                "is_test_project": any(name_lower.endswith(h) for h in TEST_NAME_HINTS)
                or name_lower in ("tests", "test"),
                "is_repo_root": rel_dir == ".",
            },
        }
        if weak_dotnet:
            candidates[rel_dir]["note"] = (
                "weak marker: Program.cs + appsettings.json but no project file "
                "in this dir — verify the build target before generating code"
            )

    if truncated:
        notes.append(
            f"candidate list capped at {max_candidates}; re-run with "
            f"--max-candidates to see more"
        )

    # parent groups: dirs whose immediate children are themselves candidates
    parent_groups: List[Dict[str, Any]] = []
    candidate_paths = set(candidates.keys())
    by_parent: Dict[str, List[str]] = {}
    for rel_dir in candidate_paths:
        if rel_dir == ".":
            continue
        parent = str(Path(rel_dir).parent.as_posix())
        by_parent.setdefault(parent, []).append(rel_dir)
    for parent, children in sorted(by_parent.items()):
        if len(children) >= 2:
            kinds = sorted({candidates[c]["stack"] for c in children})
            parent_groups.append({
                "path": parent,
                "child_candidates": sorted(children),
                "child_count": len(children),
                "stacks": kinds,
                "hint": (
                    "children sharing one name prefix suggest a multi-project "
                    "(one-csproj-per-layer) module; unrelated names suggest "
                    "sibling flat modules"
                ),
            })

    stacks = _summarize_stacks(root, stack_marker_files, candidates)

    return {
        "schema": "np-detect-stack/1",
        "scanned_root": str(root),
        "already_initialized": any(
            (root / home / "np.config.json").is_file() for home in _np_home_names()
        ),
        "stacks": stacks,
        "module_candidates": sorted(candidates.values(), key=lambda c: c["path"]),
        "parent_groups": parent_groups,
        "notes": notes,
    }


def _dominant_kind(project_files: Dict[str, str]) -> str:
    counts: Dict[str, int] = {}
    for kind in project_files.values():
        counts[kind] = counts.get(kind, 0) + 1
    # deterministic tie-break: count desc, then name asc
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _summarize_stacks(
    root: Path,
    marker_files: Dict[str, List[str]],
    candidates: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    stacks: List[Dict[str, Any]] = []
    for kind in sorted(marker_files.keys()):
        files = sorted(marker_files[kind])
        roots = sorted({
            f.split("/")[0] if "/" in f else "."
            for f in files
        })
        entry: Dict[str, Any] = {
            "kind": kind,
            "roots": roots,
            "marker_file_count": len(files),
            "marker_files_sample": files[:20],
            "suggested_stack_config": _suggest_config(kind, roots, root, candidates),
        }
        stacks.append(entry)
    return stacks


def _suggest_config(
    kind: str,
    roots: List[str],
    root: Path,
    candidates: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """A np.config.json stacks[] entry the init skill can adopt or adjust."""
    if kind == "dotnet":
        return {
            "kind": "dotnet",
            "roots": roots,
            "build": "dotnet build {target}",
            "test": "dotnet test {target} --logger trx",
            "error_format": "msbuild",
            "results_format": "trx",
        }
    if kind in ("react-ts", "node"):
        test_cmd = "npm test"
        for cand in candidates.values():
            if cand["stack"] == kind and "package.json" in cand["project_files"]:
                test_cmd = _node_test_command(root / cand["path"])
                break
        cfg: Dict[str, Any] = {
            "kind": kind,
            "roots": roots,
            "build": "npm run build",
            "test": test_cmd,
            "error_format": "tsc" if kind == "react-ts" else "generic",
            "results_format": "vitest" if "vitest" in test_cmd else "generic",
        }
        if kind == "react-ts":
            cfg["typecheck"] = "npx tsc --noEmit"
        return cfg
    if kind == "python":
        return {
            "kind": "python",
            "roots": roots,
            "build": "python -m compileall {target}",
            "test": "pytest {target}",
            "error_format": "generic",
            "results_format": "generic",
        }
    if kind == "go":
        return {
            "kind": "go",
            "roots": roots,
            "build": "go build ./...",
            "test": "go test ./...",
            "error_format": "go",
            "results_format": "generic",
        }
    if kind == "jvm":
        gradle = any(
            "build.gradle" in f for cand in candidates.values()
            for f in cand["project_files"] if cand["stack"] == "jvm"
        )
        if gradle:
            return {
                "kind": "jvm", "roots": roots,
                "build": "./gradlew build -x test", "test": "./gradlew test",
                "error_format": "generic", "results_format": "generic",
            }
        return {
            "kind": "jvm", "roots": roots,
            "build": "mvn -q -DskipTests package", "test": "mvn test",
            "error_format": "generic", "results_format": "generic",
        }
    return {
        "kind": kind, "roots": roots,
        "build": "", "test": "",
        "error_format": "generic", "results_format": "generic",
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="detect_stack.py",
        description="Deterministic stack/module scan for np-init (JSON on stdout)",
    )
    parser.add_argument("root", nargs="?", default=".",
                        help="repository root to scan (default: cwd)")
    parser.add_argument("--max-depth", type=int, default=6,
                        help="directory depth limit (default 6)")
    parser.add_argument("--max-candidates", type=int, default=200,
                        help="module candidate cap (default 200)")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(json.dumps({"success": False,
                          "error": f"not a directory: {args.root}"}))
        return 1
    result = scan(root, max_depth=args.max_depth, max_candidates=args.max_candidates)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
