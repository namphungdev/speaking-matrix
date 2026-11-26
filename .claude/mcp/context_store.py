#!/usr/bin/env python3
"""np context store — entry CRUD over <np-home>/project_context/.

<np-home> is `.claude` (Claude Code) or `.cursor` (Cursor), resolved by
np_home_names(); see NP_HOME_CANDIDATES.

Storage model (CONTRACT.md §2, §3):
  - lessons/ holds one file per entry: <id>.md with YAML frontmatter.
  - business/<domain>.md holds anchored H2 sections, one per business entry.
  - IDs: LL-YYYYMMDD-xxxx (lesson), ES-YYYYMMDD-xxxx (error-solution),
    BC-YYYYMMDD-xxxx (business); xxxx = 4 lowercase hex chars.
  - Supersede: flip status to superseded, set superseded_by, truncate body to
    ONE line ("Superseded by <id>: <new title>"). Never delete.
  - lessons/_archive/ is excluded from listings and from the ccc index.

No third-party imports are required at runtime: frontmatter is emitted
deterministically by this module and parsed with a minimal stdlib parser
(PyYAML is used opportunistically when available in the venv).
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # optional — present in the plugin venv, absent on bare system python
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KIND_PREFIX: Dict[str, str] = {
    "lesson": "LL",
    "error-solution": "ES",
    "business": "BC",
}
PREFIX_KIND: Dict[str, str] = {v: k for k, v in KIND_PREFIX.items()}

ENTRY_ID_RE = re.compile(r"^(LL|ES|BC)-\d{8}-[0-9a-f]{4}$")
BUSINESS_HEADING_RE = re.compile(
    r"^##\s+(?P<title>.*?)\s*\{#(?P<id>(?:LL|ES|BC)-\d{8}-[0-9a-f]{4})\}\s*$"
)
NP_ENTRY_COMMENT_RE = re.compile(r"<!--\s*np:entry\s+(?P<attrs>[^>]*?)\s*-->")

FRONTMATTER_KEYS = [
    "id", "type", "title", "status", "created", "updated",
    "source", "tags", "modules", "supersedes", "superseded_by",
]

INIT_CMD = os.environ.get("NP_INIT_CMD", "/np:np-init")
NOT_INITIALIZED_ERROR = f"np not initialized — run {INIT_CMD}"

# Home dirs that may hold np.config.json + project_context/, in probe order.
#
# Two separate concepts, deliberately:
#   * the PROBE list — always searched, so a repo initialized from any editor
#     resolves in every other editor. A Cursor teammate opening a repo that a
#     Claude Code teammate initialized shares that knowledge base instead of
#     silently starting a second, divergent one.
#   * the CREATION default (NP_HOME_DEFAULT) — used only when NOTHING is
#     initialized yet. Cursor installs set it to `.cursor`; Claude Code leaves
#     it at `.claude`. This is what makes "mirror into .cursor/" apply to new
#     repos without forking existing ones.
# NP_HOME overrides both (forces one dir, skips the probe).
NP_HOME_CANDIDATES = (".cursor", ".claude", ".np")
NP_HOME_DEFAULT = ".claude"


class ContextStoreError(Exception):
    """Raised for any store-level failure; message is user-facing."""


# ---------------------------------------------------------------------------
# Project discovery
# ---------------------------------------------------------------------------

def np_home_names() -> tuple:
    """Home dirnames to probe, honouring an explicit NP_HOME override."""
    forced = os.environ.get("NP_HOME", "").strip()
    return (forced,) if forced else NP_HOME_CANDIDATES


def find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from `start` (default cwd) to the nearest dir containing
    <home>/np.config.json for any home in np_home_names(). Returns None
    when not found."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        for name in np_home_names():
            if (candidate / name / "np.config.json").is_file():
                return candidate
    return None


def np_home(project_root: Path) -> Path:
    """The initialized home dir inside `project_root`.

    An existing base always wins, whichever editor created it. Only when the
    project has none do we fall back to this host's creation default.
    """
    root = Path(project_root)
    for name in np_home_names():
        if (root / name / "np.config.json").is_file():
            return root / name
    forced = os.environ.get("NP_HOME", "").strip()
    return root / (forced or os.environ.get("NP_HOME_DEFAULT", "").strip()
                   or NP_HOME_DEFAULT)


def load_config(project_root: Path) -> Dict[str, Any]:
    cfg_path = np_home(project_root) / "np.config.json"
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ContextStoreError(NOT_INITIALIZED_ERROR)
    except json.JSONDecodeError as e:
        raise ContextStoreError(f"invalid np.config.json: {e}")


# ---------------------------------------------------------------------------
# Frontmatter serialization (deterministic, contract §3 shape)
# ---------------------------------------------------------------------------

def _fm_scalar(value: Any) -> str:
    if value is None:
        return "null"
    text = str(value)
    # Quote when YAML would misparse the scalar.
    if text == "" or re.search(r'[:#\[\]{}"\']|^\s|\s$|^[->|&*?%@`!]', text):
        return json.dumps(text)
    return text


def _fm_list(values: Optional[List[str]]) -> str:
    items = [str(v) for v in (values or [])]
    return "[" + ", ".join(_fm_scalar(v) for v in items) + "]"


def emit_frontmatter(meta: Dict[str, Any]) -> str:
    lines = ["---"]
    for key in FRONTMATTER_KEYS:
        value = meta.get(key)
        if key in ("tags", "modules"):
            lines.append(f"{key}: {_fm_list(value)}")
        else:
            lines.append(f"{key}: {_fm_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def _parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw in ("null", "~", ""):
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        try:
            if raw[0] == '"':
                return json.loads(raw)
            return raw[1:-1]
        except Exception:
            return raw[1:-1]
    return raw


def _parse_list(raw: str) -> List[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    items: List[str] = []
    # split on commas outside quotes
    buf, quote = "", ""
    for ch in raw:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        items.append(buf)
    return [str(_parse_scalar(i)) for i in items if _parse_scalar(i) is not None]


def parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """Return (frontmatter dict, body). Empty dict when no frontmatter."""
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:])

    meta: Dict[str, Any] = {}
    if yaml is not None:
        try:
            loaded = yaml.safe_load(fm_text)
            if isinstance(loaded, dict):
                meta = loaded
        except Exception:
            meta = {}
    if not meta:
        for line in fm_text.split("\n"):
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            if key in ("tags", "modules"):
                meta[key] = _parse_list(value)
            else:
                meta[key] = _parse_scalar(value)
    # normalize dates that yaml may have parsed into date objects
    for k in ("created", "updated"):
        v = meta.get(k)
        if isinstance(v, (date, datetime)):
            meta[k] = v.strftime("%Y-%m-%d")
        elif v is not None:
            meta[k] = str(v)
    for k in ("tags", "modules"):
        v = meta.get(k)
        if v is None:
            meta[k] = []
        elif not isinstance(v, list):
            meta[k] = [str(v)]
        else:
            meta[k] = [str(i) for i in v]
    return meta, body


# ---------------------------------------------------------------------------
# Entry model
# ---------------------------------------------------------------------------

@dataclass
class Entry:
    id: str
    type: str
    title: str
    status: str
    created: Optional[str]
    updated: Optional[str]
    source: Optional[str]
    tags: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    body: str = ""
    path: str = ""
    domain: Optional[str] = None  # business entries only

    def summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "updated": self.updated,
            "tags": self.tags,
            "modules": self.modules,
            "path": self.path,
        }

    def full(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "created": self.created,
            "updated": self.updated,
            "source": self.source,
            "tags": self.tags,
            "modules": self.modules,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "body": self.body,
            "path": self.path,
        }
        if self.domain:
            data["domain"] = self.domain
        return data


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class ContextStore:
    """CRUD over a target project's <np-home>/project_context/ tree."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.context_dir = np_home(self.project_root) / "project_context"
        self.lessons_dir = self.context_dir / "lessons"
        self.archive_dir = self.lessons_dir / "_archive"
        self.business_dir = self.context_dir / "business"

    # -- id minting ---------------------------------------------------------

    def mint_id(self, kind: str) -> str:
        prefix = KIND_PREFIX.get(kind)
        if not prefix:
            raise ContextStoreError(
                f"unknown kind '{kind}' (expected lesson | error-solution | business)"
            )
        existing = self._existing_ids()
        stamp = date.today().strftime("%Y%m%d")
        for _ in range(32):
            candidate = f"{prefix}-{stamp}-{secrets.token_hex(2)}"
            if candidate not in existing:
                return candidate
        raise ContextStoreError("could not mint a unique entry id after 32 attempts")

    def _existing_ids(self) -> set:
        ids = set()
        for entry in self._iter_all_entries(include_archive=True):
            ids.add(entry.id)
        return ids

    # -- add ----------------------------------------------------------------

    def add_entry(
        self,
        kind: str,
        title: str,
        body_md: str,
        tags: Optional[List[str]] = None,
        modules: Optional[List[str]] = None,
        supersedes: Optional[str] = None,
        source: str = "manual",
        domain: str = "general",
    ) -> Dict[str, Any]:
        if kind not in KIND_PREFIX:
            raise ContextStoreError(
                f"unknown kind '{kind}' (expected lesson | error-solution | business)"
            )
        title = " ".join((title or "").split())
        if not title:
            raise ContextStoreError("title must not be empty")
        if supersedes:
            old = self._find_entry(supersedes)
            if old is None:
                raise ContextStoreError(f"supersedes target '{supersedes}' not found")

        entry_id = self.mint_id(kind)
        today = date.today().isoformat()

        if kind == "business":
            path = self._add_business_entry(
                entry_id, title, body_md, tags or [], modules or [],
                source, domain, today, supersedes,
            )
        else:
            self.lessons_dir.mkdir(parents=True, exist_ok=True)
            meta = {
                "id": entry_id,
                "type": kind,
                "title": title,
                "status": "active",
                "created": today,
                "updated": today,
                "source": source or "manual",
                "tags": tags or [],
                "modules": modules or [],
                "supersedes": supersedes,
                "superseded_by": None,
            }
            path = self.lessons_dir / f"{entry_id}.md"
            path.write_text(
                emit_frontmatter(meta) + "\n" + (body_md or "").rstrip() + "\n",
                encoding="utf-8",
            )

        if supersedes:
            self._apply_supersede(supersedes, superseded_by=entry_id, new_title=title)

        return {"success": True, "id": entry_id, "path": str(path)}

    def _add_business_entry(
        self,
        entry_id: str,
        title: str,
        body_md: str,
        tags: List[str],
        modules: List[str],
        source: str,
        domain: str,
        today: str,
        supersedes: Optional[str],
    ) -> Path:
        domain = re.sub(r"[^a-z0-9_-]", "-", (domain or "general").strip().lower()) or "general"
        self.business_dir.mkdir(parents=True, exist_ok=True)
        domain_file = self.business_dir / f"{domain}.md"
        if not domain_file.exists():
            pretty = domain.replace("-", " ").replace("_", " ").title()
            domain_file.write_text(f"# {pretty} — Business Context\n", encoding="utf-8")
        attrs = [
            f"id={entry_id}",
            "status=active",
            f"updated={today}",
            f"source={source or 'manual'}",
        ]
        if tags:
            attrs.append("tags=" + ",".join(tags))
        if modules:
            attrs.append("modules=" + ",".join(modules))
        if supersedes:
            attrs.append(f"supersedes={supersedes}")
        section = (
            f"\n## {title} {{#{entry_id}}}\n"
            f"<!-- np:entry {' '.join(attrs)} -->\n"
            f"{(body_md or '').rstrip()}\n"
        )
        with domain_file.open("a", encoding="utf-8") as f:
            f.write(section)
        self._register_domain_in_index(domain)
        return domain_file

    def _register_domain_in_index(self, domain: str) -> None:
        index_file = self.business_dir / "_index.md"
        link = f"{domain}.md"
        if not index_file.exists():
            return  # np-init owns creating _index.md; don't invent one here
        content = index_file.read_text(encoding="utf-8")
        if link in content:
            return
        pretty = domain.replace("-", " ").replace("_", " ").title()
        if not content.endswith("\n"):
            content += "\n"
        content += f"- [{pretty}]({link})\n"
        index_file.write_text(content, encoding="utf-8")

    # -- supersede ----------------------------------------------------------

    def supersede(self, entry_id: str, superseded_by: Optional[str] = None) -> Dict[str, Any]:
        entry = self._find_entry(entry_id)
        if entry is None:
            raise ContextStoreError(f"entry '{entry_id}' not found")
        new_title = None
        if superseded_by:
            new_entry = self._find_entry(superseded_by)
            if new_entry is not None:
                new_title = new_entry.title
        path = self._apply_supersede(entry_id, superseded_by=superseded_by, new_title=new_title)
        return {"success": True, "id": entry_id, "path": str(path)}

    def _supersede_line(self, superseded_by: Optional[str], new_title: Optional[str]) -> str:
        if superseded_by and new_title:
            return f"Superseded by {superseded_by}: {new_title}"
        if superseded_by:
            return f"Superseded by {superseded_by}."
        return "Superseded (no replacement recorded)."

    def _apply_supersede(
        self,
        entry_id: str,
        superseded_by: Optional[str],
        new_title: Optional[str],
    ) -> Path:
        entry = self._find_entry(entry_id)
        if entry is None:
            raise ContextStoreError(f"entry '{entry_id}' not found")
        today = date.today().isoformat()
        one_liner = self._supersede_line(superseded_by, new_title)

        path = Path(entry.path)
        if entry.domain is not None:
            # business entry: rewrite its section inside the domain file
            self._rewrite_business_section(
                path, entry_id,
                status="superseded", superseded_by=superseded_by,
                updated=today, body=one_liner,
            )
        else:
            meta, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
            meta["id"] = entry.id
            meta["status"] = "superseded"
            meta["updated"] = today
            meta["superseded_by"] = superseded_by
            path.write_text(
                emit_frontmatter(meta) + "\n" + one_liner + "\n", encoding="utf-8"
            )
        return path

    def _rewrite_business_section(
        self,
        domain_file: Path,
        entry_id: str,
        status: str,
        superseded_by: Optional[str],
        updated: str,
        body: str,
    ) -> None:
        text = domain_file.read_text(encoding="utf-8")
        lines = text.split("\n")
        out: List[str] = []
        i = 0
        replaced = False
        while i < len(lines):
            m = BUSINESS_HEADING_RE.match(lines[i])
            if m and m.group("id") == entry_id:
                # collect the section (heading .. before next H2 / EOF)
                j = i + 1
                while j < len(lines) and not lines[j].startswith("## "):
                    j += 1
                section = lines[i:j]
                comment_attrs: Dict[str, str] = {}
                for line in section[1:]:
                    cm = NP_ENTRY_COMMENT_RE.search(line)
                    if cm:
                        comment_attrs = _parse_entry_attrs(cm.group("attrs"))
                        break
                comment_attrs["id"] = entry_id
                comment_attrs["status"] = status
                comment_attrs["updated"] = updated
                if superseded_by:
                    comment_attrs["superseded_by"] = superseded_by
                attr_order = ["id", "status", "updated", "source", "tags",
                              "modules", "supersedes", "superseded_by"]
                attr_str = " ".join(
                    f"{k}={comment_attrs[k]}" for k in attr_order if comment_attrs.get(k)
                )
                out.append(section[0])
                out.append(f"<!-- np:entry {attr_str} -->")
                out.append(body)
                # keep exactly one blank line before the next section
                if j < len(lines):
                    out.append("")
                i = j
                replaced = True
                # skip trailing blank lines that belonged to the old section
                continue
            out.append(lines[i])
            i += 1
        if not replaced:
            raise ContextStoreError(f"business entry '{entry_id}' not found in {domain_file}")
        domain_file.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")

    # -- get / list ---------------------------------------------------------

    def get(self, entry_id: str) -> Dict[str, Any]:
        entry = self._find_entry(entry_id, include_archive=True)
        if entry is None:
            raise ContextStoreError(f"entry '{entry_id}' not found")
        return {"success": True, "entry": entry.full()}

    def list_entries(
        self,
        kind: Optional[str] = None,
        status: str = "active",
        module: Optional[str] = None,
    ) -> Dict[str, Any]:
        if kind is not None and kind not in KIND_PREFIX:
            raise ContextStoreError(
                f"unknown kind '{kind}' (expected lesson | error-solution | business)"
            )
        results: List[Dict[str, Any]] = []
        for entry in self._iter_all_entries(include_archive=False):
            if kind and entry.type != kind:
                continue
            if status and status != "all" and entry.status != status:
                continue
            if module and module.lower() not in [m.lower() for m in entry.modules]:
                continue
            results.append(entry.summary())
        results.sort(key=lambda e: (e.get("updated") or "", e["id"]), reverse=True)
        return {"success": True, "entries": results}

    # -- prune --------------------------------------------------------------

    def prune_archive(self, days: int = 30) -> Dict[str, Any]:
        """Move lessons-dir entries superseded more than `days` ago into
        lessons/_archive/. Business entries live inside domain files and are
        not moved (their bodies are already one-line tombstones)."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        archived: List[str] = []
        if self.lessons_dir.is_dir():
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted(self.lessons_dir.glob("*.md")):
                meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
                if meta.get("status") != "superseded":
                    continue
                updated = str(meta.get("updated") or "")
                # strict: archive only entries superseded MORE than `days` ago
                # (contract §3) — an entry superseded exactly `days` ago stays.
                if updated and updated < cutoff:
                    shutil.move(str(path), str(self.archive_dir / path.name))
                    archived.append(str(meta.get("id") or path.stem))
        return {"success": True, "archived": archived, "count": len(archived)}

    # -- sync (ccc index) ---------------------------------------------------

    def sync(self, timeout: int = 900) -> Dict[str, Any]:
        wrapper = _find_ccc_wrapper()
        if wrapper is None:
            raise ContextStoreError(
                "bin/ccc-wrapper.sh not found (set NP_PLUGIN_ROOT or run from the plugin tree)"
            )
        try:
            proc = subprocess.run(
                ["bash", str(wrapper), "index"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise ContextStoreError(f"ccc index timed out after {timeout}s")
        output = ((proc.stdout or "") + (proc.stderr or ""))[-4000:]
        if proc.returncode != 0:
            raise ContextStoreError(f"ccc index failed (exit {proc.returncode}): {output}")
        return {"success": True, "output": output}

    # -- internals ----------------------------------------------------------

    def _iter_all_entries(self, include_archive: bool = False):
        dirs = [self.lessons_dir]
        if include_archive:
            dirs.append(self.archive_dir)
        for directory in dirs:
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.md")):
                entry = self._load_lesson_file(path)
                if entry is not None:
                    yield entry
        if self.business_dir.is_dir():
            for path in sorted(self.business_dir.glob("*.md")):
                if path.name == "_index.md":
                    continue
                yield from self._load_business_file(path)

    def _load_lesson_file(self, path: Path) -> Optional[Entry]:
        try:
            meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            return None
        entry_id = str(meta.get("id") or "")
        if not ENTRY_ID_RE.match(entry_id):
            return None
        etype = str(meta.get("type") or PREFIX_KIND.get(entry_id[:2], "lesson"))
        return Entry(
            id=entry_id,
            type=etype,
            title=str(meta.get("title") or ""),
            status=str(meta.get("status") or "active"),
            created=meta.get("created"),
            updated=meta.get("updated"),
            source=meta.get("source"),
            tags=list(meta.get("tags") or []),
            modules=list(meta.get("modules") or []),
            supersedes=meta.get("supersedes"),
            superseded_by=meta.get("superseded_by"),
            body=body.strip("\n"),
            path=str(path),
        )

    def _load_business_file(self, path: Path):
        try:
            lines = path.read_text(encoding="utf-8").split("\n")
        except OSError:
            return
        i = 0
        while i < len(lines):
            m = BUSINESS_HEADING_RE.match(lines[i])
            if not m:
                i += 1
                continue
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            section = lines[i + 1:j]
            attrs: Dict[str, str] = {}
            body_lines: List[str] = []
            for line in section:
                cm = NP_ENTRY_COMMENT_RE.search(line)
                if cm and not attrs:
                    attrs = _parse_entry_attrs(cm.group("attrs"))
                    continue
                body_lines.append(line)
            yield Entry(
                id=m.group("id"),
                type="business",
                title=m.group("title"),
                status=attrs.get("status", "active"),
                created=attrs.get("created"),
                updated=attrs.get("updated"),
                source=attrs.get("source"),
                tags=[t for t in attrs.get("tags", "").split(",") if t],
                modules=[t for t in attrs.get("modules", "").split(",") if t],
                supersedes=attrs.get("supersedes"),
                superseded_by=attrs.get("superseded_by"),
                body="\n".join(body_lines).strip("\n"),
                path=str(path),
                domain=path.stem,
            )
            i = j

    def _find_entry(self, entry_id: str, include_archive: bool = True) -> Optional[Entry]:
        # fast path for lessons: filename == id
        for directory in (self.lessons_dir, self.archive_dir if include_archive else None):
            if directory is None or not directory.is_dir():
                continue
            candidate = directory / f"{entry_id}.md"
            if candidate.is_file():
                loaded = self._load_lesson_file(candidate)
                if loaded is not None:
                    return loaded
        for entry in self._iter_all_entries(include_archive=include_archive):
            if entry.id == entry_id:
                return entry
        return None


def _parse_entry_attrs(raw: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for token in raw.split():
        if "=" in token:
            key, _, value = token.partition("=")
            attrs[key.strip()] = value.strip()
    return attrs


def _find_ccc_wrapper() -> Optional[Path]:
    candidates = []
    for env_var in ("NP_PLUGIN_ROOT", "CURSOR_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        root = os.environ.get(env_var)
        if root:
            candidates.append(Path(root) / "bin" / "ccc-wrapper.sh")
    candidates.append(Path(__file__).resolve().parent.parent / "bin" / "ccc-wrapper.sh")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def open_store(start: Optional[Path] = None) -> ContextStore:
    """Locate the project (walk-up) and return a store, or raise the
    standard not-initialized error."""
    root = find_project_root(start)
    if root is None:
        raise ContextStoreError(NOT_INITIALIZED_ERROR)
    return ContextStore(root)
