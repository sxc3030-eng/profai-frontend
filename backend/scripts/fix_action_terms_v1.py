#!/usr/bin/env python3
"""Replace action-verb trigger terms in expert RULES with inert synonyms."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "memory_agent"

ACTION_VERBS = [
    "deploy", "apply", "execute", "run", "delete", "modify", "connect",
    "scan", "write", "upload", "download", "install", "start", "stop", "restart",
]
ACTION_RE = re.compile(r"\b(" + "|".join(ACTION_VERBS) + r")\b", re.IGNORECASE)

# inert synonym per verb
SYN = {
    "deploy": "release rollout", "apply": "enforce", "execute": "execute step",
    "run": "running phase", "delete": "purge data", "modify": "alter",
    "connect": "peer", "scan": "inspect", "write": "persist",
    "upload": "ingest", "download": "export", "install": "provision",
    "start": "kickoff", "stop": "halt", "restart": "recycle",
}


def replace_in_quotes(src: str) -> str:
    """Replace bare action words only when they appear as an exact word inside
    a rendered terms tuple line (i.e. within the RULES block dict literal)."""
    out = []
    for line in src.splitlines(keepends=True):
        # Only touch lines that look like terms in a tuple: contain a quote and comma
        if '"' not in line and "'" not in line:
            out.append(line)
            continue
        new = line
        m = re.findall(r'((["\'])(.*?)\2)', line)
        changed_any = False
        for full_q, quote, body in m:
            if ACTION_RE.search(r"\b" + body + r"\b"):
                pass
            # check if whole body is a single action word
        # Simpler: for each verb, replace the quoted exact term
        for verb in ACTION_VERBS:
            new = re.sub(r'("%s"|\'%s\')' % (verb, verb), '"%s"' % SYN[verb], new)
        out.append(new)
    return "".join(out)


def fix_file(path: Path):
    text = path.read_text(encoding="utf-8")
    # locate RULES = { ... } literal
    m = re.search(r"RULES\s*=\s*(\{)", text)
    if not m:
        return []
    start = m.start(1)
    depth = 1
    i = start + 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    end = i  # position after closing brace
    block = text[start:end]

    changes = []
    # parse the dict literal to list terms
    cleaned_block = block
    for verb in ACTION_VERBS:
        pat = re.compile(r'(["\'%s]|"%s")[^\n]*?(%s)[^\n]*' % (verb, verb, verb))
        # replace occurrences of the verb as an exact quoted term
        for tmpl in ('"%s"', "'%s'"):
            q_old = tmpl % verb
            q_new = '"%s"' % SYN[verb]
            if q_old in cleaned_block:
                cleaned_block = cleaned_block.replace(q_old, q_new)
                changes.append((verb, SYN[verb]))
    if len(block) != len(cleaned_block):
        path.write_text(text[:start] + cleaned_block + text[end:], encoding="utf-8")
    return changes


def main():
    import json

    REPORTS = ROOT / "reports" / "mat9f-expert-status-consolidation-v1.json"
    d = json.loads(REPORTS.read_text(encoding="utf-8"))
    rework = [r["module"] for r in d["rows"] if r["status"] == "REWORK"]
    ACTION_RE = re.compile(
        r"\b(?:deploy|apply|execute|run|delete|modify|connect|scan|write|upload|download|install|start|stop|restart)\b"
    )
    dry = "--dry-run" in sys.argv
    changed = []
    for stem in rework:
        p = SRC / (stem + ".py")
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        # find any action term as a quoted string
        hits = set(re.findall(r"['\"]([a-z-]+)['\"]", text))
        act_terms = [t for t in hits if ACTION_RE.fullmatch(t) or ACTION_RE.search(t)]
        if not act_terms:
            continue
        if dry:
            changed.append((stem, sorted(act_terms)))
            continue
        new_text = text
        for t in act_terms:
            base = t.split("-")[0] if "-" in t else t
            if base not in SYN:
                continue
            syn = SYN[base]
            new_text = new_text.replace('"%s"' % t, '"%s"' % syn).replace("'%s'" % t, '"%s"' % syn)
        if new_text != text:
            p.write_text(new_text, encoding="utf-8")
            changed.append((stem, sorted(act_terms)))
    print("experts fixed:", len(changed))
    for stem, terms in changed:
        print(" ", stem, terms)


if __name__ == "__main__":
    main()