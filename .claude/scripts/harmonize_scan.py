#!/usr/bin/env python3
"""harmonize_scan — deterministic half of the np-harmonize skill.

  scan     [--root DIR]                      → JSON inventory: version gap, baseline gaps,
                                               per-file / authority candidates, digest state,
                                               upkeep gaps, reference-module evidence
  digest   [--root DIR] [--hash]             → the rendered conventions digest (or its hash)
  baseline [--root DIR] [--apply] [--allow-edited]
                                             → insert missing baseline rule sections and
                                               checklist lines into conventions.md
  upkeep   [--root DIR] [--apply]            → .gitattributes, ledger index exclude, ledger
                                               check-ignore warning
  rehash   FILE [--root DIR] [--apply]       → re-record a generated file's hash after
                                               gated edits (only if it was pristine)
  align    [--root DIR] [--apply] [--edits PATH|-]
                                             → apply decided line alignments to project
                                               rule/skill/memory files (stale-checked,
                                               idempotent, re-hashes pristine generated
                                               files); never touches plugin-owned,
                                               lessons/ or business/ files
  layer    [--root DIR] [--apply] [--skill-header PATH …]
                                             → write the always-on layer: memory-file managed
                                               block, Cursor rules, skill headers, _meta.json

Everything except `scan`/`digest` is a dry run unless --apply is given. Writes are
idempotent: a second --apply with nothing changed leaves every file byte-identical.
Judgement (which conflicts to align, amendments, reference-module switches) is the
skill's job, never this script's. Stdlib only; output is JSON on stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR / "mcp"))

from context_store import (  # noqa: E402
    ContextStoreError, NOT_INITIALIZED_ERROR, find_project_root, np_home, np_home_names,
    load_config,
)
import provenance  # noqa: E402

TEMPLATES = PLUGIN_DIR / "templates" / "project_context"
MARK_START, MARK_END = "<!-- np:managed:start -->", "<!-- np:managed:end -->"
GENERATED_FILES = ("architecture.md", "conventions.md", "stack.md", "modules.json")
RULE_HEADING = re.compile(r"^## (?P<id>[A-Z]+\d+) — (?P<title>.+?) \[(?P<sev>CRITICAL|HIGH|MEDIUM|LOW)\]\s*$")
BASELINE_ID = re.compile(r"^(B|FB)\d+$")
CHECKLIST_LINE = re.compile(r"^\s*- \[ \] (?P<id>(?:B|FB)\d+) — ")
# Generic categories only — never a project's own wording.
PER_FILE = re.compile(
    r"(in (?:its|their) own file"
    r"|one (?:\w+ )?(?:type|class|record|interface|enum|component|struct)s? per file"
    r"|\bown file\b|one per file|one file per (?:type|class|record|interface|enum|component)"
    r"|(?:each|every) (?:type|class|record|interface|enum|component) (?:in|gets|has) "
    r"(?:its|a) (?:own|separate) file)", re.I)
AUTHORITY = re.compile(
    r"(^\s*authoritative\s*:\s*true|\bauthoritative\b|\bis (?:the )?(?:single )?truth\b"
    r"|\btakes? precedence\b|\boutranks?\b|\boverrides? (?:any|all|every)\b|\b\w+ wins\b)", re.I)
# A unit's layout spelled as a list of file names: {Command.cs, Handler.cs, Validator.cs}.
SRC_EXT = (r"(?:cs|ts|tsx|js|jsx|mjs|py|go|java|kt|rb|rs|php|vue|svelte|razor|cshtml"
           r"|swift|scala|ex|exs|md|mdc|json|ya?ml|sql|proto|tmpl)")
FILE_LIST = re.compile(
    rf"[{{(\[][^}})\]]*[\w<>.-]+\.{SRC_EXT}\b[^}})\]]*,[^}})\]]*[\w<>.-]+\.{SRC_EXT}\b[^}})\]]*[}})\]]")
# A unit's layout spelled as a list of artifact KINDS — the same per-file reading
# without a single file extension: `<X>Command`, `I<X>Handler`, `<X>Validator`, …
KIND_TOKEN = re.compile(
    r"`I?[A-Z<][\w<>./-]*?(?:Command|Query|Handler|Validator|Result|Request|Response|Repository"
    r"|Reader|Writer|Service|Factory|Mapper|Operation|Constants|Dto|Entity|Controller|Component"
    r"|Hook|Store|Schema|Config)[\w<>]*`")
KIND_LIST_MIN = 3
# …and only where the same line also names a folder, so prose that merely mentions
# three types ("throw DomainException / NotFoundException / ConflictException") is
# not read as a unit layout.
PATHY = re.compile(r"`[^`]*/[^`]*`")
# Rules about documentation comments — checked against B6.
DOC_RULE = re.compile(r"(xml doc|<summary>|<param>|doc[- ]?comments?|jsdoc|javadoc|docstrings?)", re.I)
FENCE = re.compile(r"^\s*(```|~~~)")
SKIP_PARTS = {"node_modules", ".git", "bin", "obj", "dist", ".np-runs", "__pycache__"}


# --------------------------------------------------------------------------- io

def _read(path: Path) -> Tuple[str, str]:
    """(text with \\n line ends, original eol) — files from Windows checkouts keep CRLF."""
    raw = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), eol


def _write_if_changed(path: Path, text: str, eol: str, apply: bool) -> bool:
    data = text.replace("\n", eol).encode("utf-8") if eol != "\n" else text.encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return False
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return True


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _bare_version(v: Optional[str]) -> Optional[str]:
    return v.split("/", 1)[1] if v and v.startswith("np/") else v


def _git(top: Path, *args: str) -> Optional[str]:
    try:
        r = subprocess.run(["git", *args], cwd=top, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


# ---------------------------------------------------------------------- context

class Project:
    def __init__(self, root_arg: Optional[str]):
        root = find_project_root(Path(root_arg) if root_arg else None)
        if root is None:
            raise ContextStoreError(NOT_INITIALIZED_ERROR)
        self.root = root
        self.home = np_home(root)
        self.cfg = load_config(root)
        self.pc = self.home / "project_context"
        self.meta_path = self.pc / "_meta.json"
        self.meta: Dict[str, Any] = (json.loads(self.meta_path.read_text(encoding="utf-8"))
                                     if self.meta_path.is_file() else {})

    def rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(p)

    @property
    def conventions(self) -> Path:
        return self.pc / "conventions.md"

    def has_frontend(self, conv_ids: List[str]) -> bool:
        stacks = self.cfg.get("stacks") or []
        return bool(self.cfg.get("frontend")
                    or any(s.get("typecheck") for s in stacks if isinstance(s, dict))
                    or any(i.startswith(("FE", "FB")) for i in conv_ids))

    def pristine(self, name: str) -> Optional[bool]:
        """True = untouched since generation; False = hand-edited; None = unknown."""
        recorded = (self.meta.get("generated_hashes") or {}).get(name)
        p = self.pc / name
        if not recorded or not p.is_file():
            return None
        return _sha256(p.read_bytes()) == recorded


INSTALL_RECORD = ".np-install.json"


def _plugin_owned(home: Path) -> set:
    """Home-relative paths the plugin owns inside the project's np home.

    Vendored (local-mode) install: this script runs from inside the home, side by
    side with the project's own rules and skills, so enumerating our own tree would
    claim theirs too — trust the installer's record of exactly what it wrote.
    Plugin-mode install: the plugin lives outside the repo; anything of ours that
    appears in the home has the same relative path as in the plugin tree.
    """
    rec = home / INSTALL_RECORD
    try:
        vendored = PLUGIN_DIR.resolve().is_relative_to(home.resolve())
    except AttributeError:   # Python < 3.9
        vendored = str(PLUGIN_DIR.resolve()).startswith(str(home.resolve()))
    if vendored:
        if rec.is_file():
            return set(json.loads(rec.read_text(encoding="utf-8"))) | {INSTALL_RECORD}
        # Pre-record vendored install: nothing can be told apart, so the scan
        # reports this and the skill asks for the installer to be re-run first.
        return {"__unknown__"}
    owned = set()
    for sub in ("skills", "agents", "bin", "mcp", "scripts", "templates", "rules"):
        base = PLUGIN_DIR / sub
        if base.is_dir():
            owned.update(f"{sub}/{f.relative_to(base).as_posix()}"
                         for f in base.rglob("*") if f.is_file())
    cmds = PLUGIN_DIR / "commands"
    if cmds.is_dir():
        for f in cmds.glob("*.md"):
            owned.add(f"commands/{f.name}")
            owned.add(f"commands/{f.stem if f.stem.startswith('np') else 'np-' + f.stem}.md")
    # The Cursor emitter flattens agents; accept either shape.
    owned.update(f"agents/{Path(p).name}" for p in list(owned) if p.startswith("agents/"))
    return owned


# ------------------------------------------------------------------ conventions

def parse_rules(text: str) -> List[Dict[str, str]]:
    out = []
    for line in text.split("\n"):
        m = RULE_HEADING.match(line)
        if m:
            out.append(m.groupdict())
    return out


def parse_amendments(text: str) -> List[Dict[str, str]]:
    m = re.search(r"^## Amendments\s*$", text, re.M)
    if not m:
        return []
    out, cur = [], None
    for line in text[m.end():].split("\n"):
        h = re.match(r"^### (?P<date>\S+) — (?P<topic>.+?)\s*$", line)
        if h:
            cur = {"topic": h.group("topic"), "claim": ""}
            out.append(cur)
        elif cur is not None and not cur["claim"]:
            c = re.match(r"^- Claim:\s*(.+)$", line)
            if c:
                cur["claim"] = c.group(1).strip()
        elif line.startswith("## "):
            break
    return out


def template_sections() -> Tuple[List[Tuple[str, str]], List[str]]:
    """([(id, section text)], [checklist lines]) for the baseline rules in the template."""
    text, _ = _read(TEMPLATES / "conventions.md.tmpl")
    lines = text.split("\n")
    sections: List[Tuple[str, str]] = []
    i = 0
    while i < len(lines):
        m = RULE_HEADING.match(lines[i])
        if m and BASELINE_ID.match(m.group("id")):
            j, fence = i + 1, False
            while j < len(lines):
                if lines[j].startswith("```"):
                    fence = not fence
                if not fence and (lines[j].startswith("## ") or lines[j].startswith("<!--")):
                    break
                j += 1
            body = "\n".join(lines[i:j]).rstrip("\n")
            sections.append((m.group("id"), body))
            i = j
        else:
            i += 1
    checklist = [ln.strip() for ln in lines if CHECKLIST_LINE.match(ln)]
    return sections, checklist


def _section_bounds(lines: List[str], idx: int) -> int:
    """Index of the first line after the rule section that starts at idx."""
    j, fence = idx + 1, False
    while j < len(lines):
        if lines[j].startswith("```"):
            fence = not fence
        if not fence and (lines[j].startswith("## ") or lines[j].startswith("<!--")
                          or lines[j].strip() == "---"):
            break
        j += 1
    return j


def baseline_gaps(proj: Project) -> Dict[str, Any]:
    text, _ = _read(proj.conventions)
    have = [r["id"] for r in parse_rules(text)]
    sections, checklist = template_sections()
    fe = proj.has_frontend(have)
    wanted = [sid for sid, _ in sections if sid.startswith("B") or fe]
    missing = [sid for sid in wanted if sid not in have]
    missing_check = [ln for ln in checklist
                     if CHECKLIST_LINE.match(ln).group("id") in wanted
                     and not re.search(r"- \[ \] " + CHECKLIST_LINE.match(ln).group("id") + r"\b", text)]
    return {"missing_sections": missing, "missing_checklist": missing_check, "frontend": fe}


def apply_baseline(proj: Project, apply: bool, allow_edited: bool) -> Dict[str, Any]:
    gaps = baseline_gaps(proj)
    pristine = proj.pristine("conventions.md")
    if not gaps["missing_sections"] and not gaps["missing_checklist"]:
        return {"changed": False, **gaps}
    if pristine is False and not allow_edited:
        return {"changed": False, "blocked": "conventions.md was hand-edited — needs the dev's "
                "approval (re-run with --allow-edited after the gate)", **gaps}
    text, eol = _read(proj.conventions)
    lines = text.split("\n")
    sections = dict(template_sections()[0])
    order = [sid for sid, _ in template_sections()[0]]

    for sid in gaps["missing_sections"]:
        heads = {RULE_HEADING.match(l).group("id"): n for n, l in enumerate(lines)
                 if RULE_HEADING.match(l)}
        family = re.match(r"[A-Z]+", sid).group(0)
        earlier = [o for o in order[:order.index(sid)] if o in heads and o.startswith(family)
                   and re.match(r"[A-Z]+", o).group(0) == family]
        if earlier:
            at = _section_bounds(lines, heads[earlier[-1]])
        elif family == "FB":
            fe_heads = [n for i, n in heads.items() if i.startswith("FE")]
            fp = next((n for n, l in enumerate(lines) if l.startswith("## File Placement")), None)
            at = min(fe_heads) if fe_heads else (fp if fp is not None else len(lines))
            while fp is not None and at == fp and at > 0 and lines[at - 1].strip() in ("", "---"):
                at -= 1
        else:
            first = min(heads.values()) if heads else len(lines)
            at = first
        while at > 0 and lines[at - 1].strip() == "":
            at -= 1
        block = ["", *sections[sid].split("\n")]
        if at < len(lines) and lines[at].strip() != "":
            block.append("")
        lines[at:at] = block

    if gaps["missing_checklist"]:
        cl = next((n for n, l in enumerate(lines) if l.startswith("## Pre-Write Checklist")), None)
        if cl is not None:
            end = cl + 1
            last_item = None
            while end < len(lines) and not lines[end].startswith("## "):
                if lines[end].lstrip().startswith("- [ ]"):
                    last_item = end
                end += 1
            at = (last_item + 1) if last_item is not None else cl + 1
            lines[at:at] = gaps["missing_checklist"]

    new = "\n".join(lines)
    changed = _write_if_changed(proj.conventions, new, eol, apply)
    if apply and changed and pristine:
        proj.meta.setdefault("generated_hashes", {})["conventions.md"] = \
            _sha256(proj.conventions.read_bytes())
        _save_meta(proj, apply)
    return {"changed": changed, "applied": apply, "hash_updated": bool(apply and changed and pristine),
            **gaps}


# ----------------------------------------------------------------------- digest

def render_digest(proj: Project) -> str:
    text, _ = _read(proj.conventions)
    rules = [r for r in parse_rules(text) if r["sev"] in ("CRITICAL", "HIGH")]
    rule_lines = "\n".join(f"- **{r['id']}** [{r['sev']}] — {r['title']}" for r in rules)
    amends = parse_amendments(text)
    amend_block = ""
    if amends:
        amend_block = "\nAmendments (dev-confirmed, override the rule text above them):\n" + "\n".join(
            f"- **{a['topic']}** — {a['claim'] or 'see the Amendments section'}" for a in amends) + "\n"
    tmpl, _ = _read(TEMPLATES / "conventions_digest.md.tmpl")
    return (tmpl.replace("{{CONVENTIONS_PATH}}", proj.rel(proj.conventions))
                .replace("{{RULE_LINES}}", rule_lines)
                .replace("{{AMENDMENT_BLOCK}}", amend_block)).rstrip("\n")


def digest_hash(digest: str) -> str:
    return _sha256(digest.encode("utf-8"))


# ------------------------------------------------------------------------ layer

def memory_file(proj: Project) -> Path:
    """np-init Step 8's rule: one file; an existing managed block wins."""
    cands = [proj.root / "CLAUDE.md", proj.root / "AGENTS.md", proj.home / "CLAUDE.md"]
    for c in cands:
        if c.is_file() and MARK_START in c.read_text(encoding="utf-8", errors="replace"):
            return c
    for c in cands:
        if c.is_file():
            return c
    return proj.root / ("AGENTS.md" if provenance.host_name() == "cursor" else "CLAUDE.md")


def _replace_block(text: str, block: str) -> str:
    s, e = text.find(MARK_START), text.find(MARK_END)
    if s != -1 and e != -1 and e > s:
        return text[:s] + block + text[e + len(MARK_END):]
    return (text.rstrip("\n") + "\n\n" if text.strip() else "") + block + "\n"


def write_layer(proj: Project, apply: bool, skill_headers: List[str]) -> Dict[str, Any]:
    digest = render_digest(proj)
    written: List[str] = []

    mem = memory_file(proj)
    block_tmpl, _ = _read(TEMPLATES / "claude_md_block.md.tmpl")
    block = (block_tmpl.replace("{{PROJECT_NAME}}", str(proj.cfg.get("project_name") or proj.root.name))
                       .replace("{{CONVENTIONS_DIGEST}}", digest)).rstrip("\n")
    text, eol = _read(mem) if mem.is_file() else ("", "\n")
    if _write_if_changed(mem, _replace_block(text, block), eol, apply):
        written.append(proj.rel(mem))

    cursor_dir = proj.root / ".cursor"
    if cursor_dir.is_dir() or provenance.host_name() == "cursor":
        rules_dir = cursor_dir / "rules"
        want: Dict[Path, str] = {}
        mdc, _ = _read(TEMPLATES / "np-conventions.mdc.tmpl")
        want[rules_dir / "np-conventions.mdc"] = mdc.replace("{{CONVENTIONS_DIGEST}}", digest).rstrip("\n") + "\n"
        scoped, _ = _read(TEMPLATES / "np-conventions-scoped.mdc.tmpl")
        for stack in proj.cfg.get("stacks") or []:
            roots = [r.strip("/") for r in stack.get("roots") or [] if r and r.strip("/.")]
            if not roots:
                continue
            globs = ",".join(f"{r}/**" for r in roots)
            kind = re.sub(r"[^a-z0-9-]+", "-", str(stack.get("kind", "stack")).lower()).strip("-")
            want[rules_dir / f"np-conventions-{kind}.mdc"] = (
                scoped.replace("{{GLOBS}}", globs).replace("{{KIND}}", str(stack.get("kind")))
                      .replace("{{CONVENTIONS_PATH}}", proj.rel(proj.conventions)).rstrip("\n") + "\n")
        for p, body in want.items():
            if _write_if_changed(p, body, "\n", apply):
                written.append(proj.rel(p))
        if rules_dir.is_dir():   # retire scoped rules for stacks that no longer exist
            for old in rules_dir.glob("np-conventions-*.mdc"):
                if old not in want and "np:generated" in old.read_text(encoding="utf-8", errors="replace"):
                    written.append(proj.rel(old) + " (removed)")
                    if apply:
                        old.unlink()

    header_tmpl, _ = _read(TEMPLATES / "skill_header.md.tmpl")
    header = header_tmpl.replace("{{CONVENTIONS_PATH}}", proj.rel(proj.conventions)).rstrip("\n")
    for raw in skill_headers:
        p = (proj.root / raw) if not Path(raw).is_absolute() else Path(raw)
        if not p.is_file():
            continue
        text, eol = _read(p)
        if MARK_START in text:
            new = _replace_block(text, header)
        else:
            fm = re.match(r"^---\n.*?\n---\n", text, re.S)
            cut = fm.end() if fm else 0
            new = text[:cut] + ("\n" if cut else "") + header + "\n\n" + text[cut:].lstrip("\n")
        if _write_if_changed(p, new, eol, apply):
            written.append(proj.rel(p))

    proj.meta["digest_hash"] = digest_hash(digest)
    proj.meta["plugin_version"] = _bare_version(provenance.plugin_version())
    if _save_meta(proj, apply):
        written.append(proj.rel(proj.meta_path))
    return {"applied": apply, "memory_file": proj.rel(mem), "written": written,
            "digest_hash": proj.meta["digest_hash"]}


def _save_meta(proj: Project, apply: bool) -> bool:
    if not proj.meta_path.parent.is_dir():
        return False
    body = json.dumps(proj.meta, indent=2, ensure_ascii=False) + "\n"
    eol = _read(proj.meta_path)[1] if proj.meta_path.is_file() else "\n"
    return _write_if_changed(proj.meta_path, body, eol, apply)


def rehash(proj: Project, name: str, apply: bool) -> Dict[str, Any]:
    """Re-record a generated file's hash after gated harmonize edits, so a later
    re-init still regenerates it in place instead of writing a .new.md sidecar.
    The skill calls this only for files that were pristine when the run began."""
    if name not in GENERATED_FILES or not (proj.pc / name).is_file():
        return {"changed": False, "error": f"not a generated project_context file: {name}"}
    new = _sha256((proj.pc / name).read_bytes())
    old = (proj.meta.get("generated_hashes") or {}).get(name)
    if old == new:
        return {"changed": False}
    proj.meta.setdefault("generated_hashes", {})[name] = new
    return {"changed": _save_meta(proj, apply), "applied": apply, "file": name}


# ----------------------------------------------------------------------- upkeep

def upkeep(proj: Project, apply: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {"applied": apply, "changed": [], "warnings": [], "report_only": []}
    top = provenance.toplevel(proj.root) or proj.root

    ga = top / ".gitattributes"
    text, eol = _read(ga) if ga.is_file() else ("", "\n")
    line = "np-provenance.jsonl merge=union"
    if line not in text.split("\n"):
        if _write_if_changed(ga, (text.rstrip("\n") + "\n" if text.strip() else "") + line + "\n", eol, apply):
            out["changed"].append(".gitattributes")

    cfg_path = proj.home / "np.config.json"
    excl = (proj.cfg.get("index") or {}).get("exclude")
    if isinstance(excl, list) and "**/np-provenance.jsonl" not in excl:
        excl.append("**/np-provenance.jsonl")
        _, ceol = _read(cfg_path)
        if _write_if_changed(cfg_path, json.dumps(proj.cfg, indent=2, ensure_ascii=False) + "\n", ceol, apply):
            out["changed"].append(proj.rel(cfg_path))

    ledger = proj.home / provenance.LEDGER_NAME
    ign = _git(top, "check-ignore", "-v", str(ledger))
    if ign:
        out["warnings"].append(f"the provenance ledger is gitignored ({ign.strip()}) — "
                               "add a negation for it so it can be committed")

    settings = proj.root / ".cocoindex_code" / "settings.yml"
    if settings.is_file() and "np-provenance.jsonl" not in settings.read_text(encoding="utf-8", errors="replace"):
        out["report_only"].append(".cocoindex_code/settings.yml lacks the ledger exclude — "
                                  "add `- \"**/np-provenance.jsonl\"` and reindex when convenient")
    return out


# ------------------------------------------------------------------------ align

def _align_target(proj: Project, rel: str, owned: set) -> Tuple[Optional[Path], Optional[str]]:
    """(path, refusal) — the same boundary Step 6 checks, enforced before the write."""
    p = (proj.root / rel).resolve()
    try:
        p.relative_to(proj.root.resolve())
    except ValueError:
        return None, "outside the project root"
    if not p.is_file():
        return None, "no such file"
    try:
        home_rel = p.relative_to(proj.home.resolve()).as_posix()
    except ValueError:
        home_rel = None
    if home_rel and home_rel in owned:
        return None, "plugin-owned (vendored by the installer)"
    if home_rel and (home_rel.startswith("project_context/lessons/")
                     or home_rel.startswith("project_context/business/")):
        return None, "lessons/ and business/ are never touched"
    if "np:generated" in _read(p)[0]:
        return None, "np:generated — regenerated, never edited"
    return p, None


def _shape_check(old: str, new: str, category: Optional[str]) -> Optional[str]:
    """Catch the two rewrites that look done and are not: a clause appended to a
    surviving file list (the planner follows the concrete half), and a table row
    whose closing pipe moved. Deterministic, so a judgement slip cannot land."""
    o, n = old.strip(), new.strip()
    if o.startswith("|") and o.endswith("|") and not n.endswith("|"):
        return "the line is a table row — keep the clause inside the last cell, before the closing |"
    if category == "file-list-layout" and FILE_LIST.search(new):
        return "the file-name list is still there — replace it with the kinds, do not append to it"
    if category in ("file-list-layout", "kind-list-layout", "per-file-mandate") and "B7" not in new:
        return "an aligned layout rule names B7 as the thing that decides the file count"
    if category == "per-file-mandate" and PER_FILE.search(new):
        return "the per-file clause is still there — remove it, keep the rest of the rule"
    return None


def align(proj: Project, edits: List[Dict[str, Any]], apply: bool) -> Dict[str, Any]:
    """Apply decided alignments line by line. The skill judges; this writes.

    Each edit is {path, line, old, new, category?, rule?}: `old` must still be the
    exact text at `path:line` or the edit is refused as stale. Idempotent — an edit
    whose `new` is already in place reports `already-aligned` and writes nothing. A
    generated file that was pristine before the run is re-hashed afterwards, so a
    later re-init still regenerates it in place."""
    owned = _plugin_owned(proj.home)
    if owned == {"__unknown__"}:
        owned = set()
    results: List[Dict[str, Any]] = []
    buffers: Dict[Path, Tuple[List[str], str]] = {}
    pristine_before = {n: proj.pristine(n) for n in GENERATED_FILES if (proj.pc / n).is_file()}

    for i, e in enumerate(edits):
        rel, line_no = str(e.get("path", "")), e.get("line")
        old, new = e.get("old"), e.get("new")
        row: Dict[str, Any] = {"path": rel, "line": line_no, "category": e.get("category")}
        results.append(row)
        if not rel or not isinstance(line_no, int) or old is None or new is None:
            row["status"] = "refused"; row["reason"] = "needs path, line, old and new"; continue
        if not str(new).strip():
            row["status"] = "refused"; row["reason"] = "an alignment rewrites a rule, never deletes it"; continue
        shape = _shape_check(str(old), str(new), e.get("category"))
        if shape:
            row["status"] = "refused"; row["reason"] = shape; continue
        p, refusal = _align_target(proj, rel, owned)
        if refusal:
            row["status"] = "refused"; row["reason"] = refusal; continue
        if p not in buffers:
            text, eol = _read(p)
            buffers[p] = (text.split("\n"), eol)
        lines, _eol = buffers[p]
        if not 1 <= line_no <= len(lines):
            row["status"] = "refused"; row["reason"] = f"line {line_no} is past end of file"; continue
        if lines[line_no - 1] == old:
            lines[line_no - 1] = new
            row["status"] = "aligned"
        elif new in "\n".join(lines):
            row["status"] = "already-aligned"
        else:
            row["status"] = "refused"
            row["reason"] = "the line changed since the scan — re-scan and re-decide"
        row["edit_index"] = i

    changed: List[str] = []
    for p, (lines, eol) in buffers.items():
        if _write_if_changed(p, "\n".join(lines), eol, apply):
            changed.append(proj.rel(p))

    rehashed: List[str] = []
    if apply:
        for name, was_pristine in pristine_before.items():
            if was_pristine and proj.rel(proj.pc / name) in changed:
                r = rehash(proj, name, True)
                if r.get("changed"):
                    rehashed.append(name)
    return {"applied": apply, "results": results, "changed": changed, "rehashed": rehashed,
            "counts": {s: sum(1 for r in results if r.get("status") == s)
                       for s in ("aligned", "already-aligned", "refused")}}


# ------------------------------------------------------------------------- scan

def _instruction_surfaces(proj: Project) -> List[Path]:
    found: List[Path] = []
    for name in ("CLAUDE.md", "AGENTS.md", ".cursorrules"):
        if (proj.root / name).is_file():
            found.append(proj.root / name)
    listed = _git(proj.root, "ls-files", "--cached", "--others", "--exclude-standard",
                  "*CLAUDE.md", "*AGENTS.md")
    for rel in (listed or "").split("\n"):
        p = proj.root / rel
        if rel and p.is_file() and p not in found and not SKIP_PARTS & set(Path(rel).parts):
            found.append(p)
    for home_name in dict.fromkeys((*np_home_names(), ".claude", ".cursor")):
        h = proj.root / home_name
        if not h.is_dir():
            continue
        for sub in ("rules", "skills", "agents", "commands"):
            d = h / sub
            if d.is_dir():
                found.extend(f for f in sorted(d.rglob("*"))
                             if f.is_file() and f.suffix in (".md", ".mdc"))
        if (h / "CLAUDE.md").is_file():
            found.append(h / "CLAUDE.md")
    return list(dict.fromkeys(found))


DEFERS = re.compile(r"conventions\.md|\bB7\b")


def _hits(text: str) -> List[Dict[str, Any]]:
    """Candidate lines, minus np's own managed text, fenced code samples, and lines
    that already defer to the conventions file (baseline rules, or a rule aligned by
    an earlier run)."""
    hits, inside, in_b7, fenced = [], False, False, False
    for n, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if MARK_START in line:
            inside = True
        h = RULE_HEADING.match(line)
        if h:
            in_b7 = bool(BASELINE_ID.match(h.group("id")))   # the plugin's own rules
        if not inside and not in_b7 and not fenced and not DEFERS.search(line):
            for cat, rx in (("per-file-mandate", PER_FILE), ("authority-claim", AUTHORITY),
                            ("file-list-layout", FILE_LIST), ("doc-comment-rule", DOC_RULE)):
                if rx.search(line):
                    hits.append({"line": n, "category": cat, "text": line.strip()[:240]})
            if len(set(KIND_TOKEN.findall(line))) >= KIND_LIST_MIN and PATHY.search(line):
                hits.append({"line": n, "category": "kind-list-layout", "text": line.strip()[:240]})
        if MARK_END in line:
            inside = False
    return hits


def _reference_evidence(proj: Project) -> List[Dict[str, Any]]:
    mpath = proj.pc / "modules.json"
    if not mpath.is_file():
        return []
    mods = json.loads(_read(mpath)[0])
    refs = mods.get("reference_modules") or {}
    if isinstance(refs, list):
        refs = {r.get("family"): r.get("path") for r in refs if isinstance(r, dict)}
    top = provenance.toplevel(proj.root) or proj.root
    entries, _ = provenance.read_ledgers(provenance.all_ledger_paths(proj.root))
    created = {f for f, e in provenance.latest_per_file(entries).items() if e.get("action") == "created"}

    def share(path: str) -> Dict[str, Any]:
        files = [f for f in (_git(top, "ls-files", "--", path) or "").split("\n") if f]
        gen = sum(1 for f in files if f in created)
        return {"path": path, "tracked_files": len(files), "pipeline_created": gen,
                "pipeline_share": round(gen / len(files), 2) if files else None}

    out = []
    for family, ref in refs.items():
        if not ref:
            continue
        members = [m.get("path") for m in mods.get("modules") or []
                   if m.get("family") == family and m.get("path") and m.get("path") != ref]
        out.append({"family": family, "reference": share(ref),
                    "siblings": [share(p) for p in members]})
    return out


def scan(proj: Project) -> Dict[str, Any]:
    owned = _plugin_owned(proj.home)
    if owned == {"__unknown__"}:
        return {"success": False, "error": "vendored install without an install record — re-run "
                "the np installer for this project first, then harmonize"}
    surfaces = []
    for p in _instruction_surfaces(proj):
        try:
            home_rel = p.resolve().relative_to(proj.home.resolve()).as_posix()
        except ValueError:
            home_rel = None
        if home_rel and home_rel in owned:
            continue                      # vendored plugin file — the installer owns it
        if home_rel and home_rel.startswith("project_context/"):
            continue
        text, _ = _read(p)
        if "np:generated" in text:
            continue                      # written by this script — regenerated, never judged
        surfaces.append({"path": proj.rel(p), "owner": "project",
                         "managed_block": MARK_START in text, "candidates": _hits(text)})

    generated = {}
    for name in GENERATED_FILES:
        p = proj.pc / name
        if p.is_file():
            entry: Dict[str, Any] = {"pristine": proj.pristine(name)}
            if name.endswith(".md"):
                entry["candidates"] = [h for h in _hits(_read(p)[0])
                                       if h["category"] in ("per-file-mandate", "file-list-layout",
                                                            "kind-list-layout", "doc-comment-rule")]
            generated[name] = entry

    digest = render_digest(proj) if proj.conventions.is_file() else None
    user_level = [str(p) for p in (Path.home() / ".claude" / "CLAUDE.md", Path.home() / ".cursor" / "rules")
                  if p.exists()]
    return {
        "success": True,
        "project_root": str(proj.root),
        "np_home": proj.rel(proj.home),
        "version": {"project": proj.meta.get("plugin_version"),
                    "plugin": _bare_version(provenance.plugin_version())},
        "generated": generated,
        "baseline": baseline_gaps(proj) if proj.conventions.is_file() else None,
        "digest": {"recorded": proj.meta.get("digest_hash"),
                   "current": digest_hash(digest) if digest else None,
                   "stale": bool(digest) and proj.meta.get("digest_hash") != digest_hash(digest)},
        "memory_file": proj.rel(memory_file(proj)),
        "surfaces": surfaces,
        "upkeep": upkeep(proj, apply=False),
        "reference_modules": _reference_evidence(proj),
        "user_level_report_only": user_level,
    }


# ------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(prog="harmonize_scan.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "digest", "baseline", "upkeep", "layer", "rehash", "align"):
        s = sub.add_parser(name)
        s.add_argument("--root")
        if name != "scan" and name != "digest":
            s.add_argument("--apply", action="store_true")
    sub.choices["digest"].add_argument("--hash", action="store_true")
    sub.choices["baseline"].add_argument("--allow-edited", action="store_true")
    sub.choices["layer"].add_argument("--skill-header", action="append", default=[])
    sub.choices["rehash"].add_argument("file", choices=GENERATED_FILES)
    sub.choices["align"].add_argument("--edits", default="-",
                                      help="JSON file with {\"edits\": [...]}, or - for stdin")
    a = ap.parse_args()
    try:
        proj = Project(a.root)
        if a.cmd == "scan":
            out: Any = scan(proj)
        elif a.cmd == "digest":
            d = render_digest(proj)
            print(digest_hash(d) if a.hash else d)
            return 0
        elif a.cmd == "baseline":
            out = apply_baseline(proj, a.apply, a.allow_edited)
        elif a.cmd == "upkeep":
            out = upkeep(proj, a.apply)
        elif a.cmd == "rehash":
            out = rehash(proj, a.file, a.apply)
        elif a.cmd == "align":
            raw = sys.stdin.read() if a.edits == "-" else Path(a.edits).read_text(encoding="utf-8")
            payload = json.loads(raw)
            out = align(proj, payload.get("edits") if isinstance(payload, dict) else payload, a.apply)
        else:
            out = write_layer(proj, a.apply, a.skill_header)
    except (ContextStoreError, OSError, json.JSONDecodeError) as e:
        print(json.dumps({"success": False, "error": str(e)}))
        return 1
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
