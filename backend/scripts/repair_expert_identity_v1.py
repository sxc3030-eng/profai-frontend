#!/usr/bin/env python3
"""Repair connectivity: make SOURCE_INDEX and EXPERT_ID unique across all experts."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "memory_agent"
RESERVED = frozenset({25, 27, 33, 43, 47, 117, 118, 119, 120, 121, 129, 130, 135, 143, 147, 151, 156, 161, 165, 166, 167, 168, 176, 183, 188, 195, 202, 207})


def read_expert_ids():
    rows = []
    for path in sorted(SRC.glob("mat9f_*_expert_v1.py")):
        text = path.read_text(encoding="utf-8")
        ms = re.search(r"SOURCE_INDEX\s*=\s*(\d+)", text)
        me = re.search(r'EXPERT_ID\s*=\s*"([^"]+)"', text)
        if ms and me:
            rows.append({"path": path, "source_index": int(ms.group(1)), "expert_id": me.group(1)})
    return rows


def free_indices(rows):
    used = set(r["source_index"] for r in rows)
    return [i for i in range(1, 1001) if i not in used and i not in RESERVED]


def set_index(path, new_idx):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"SOURCE_INDEX\s*=\s*\d+", "SOURCE_INDEX = %d" % new_idx, text, count=1)
    path.write_text(text, encoding="utf-8")


def set_expert_id(path, new_id):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'EXPERT_ID\s*=\s*"[^"]*"', 'EXPERT_ID = "%s"' % new_id, text, count=1)
    path.write_text(text, encoding="utf-8")


def main():
    dry = "--dry-run" in sys.argv
    rows = read_expert_ids()
    print("total with identity:", len(rows))
    free = free_indices(rows)
    fi = iter(free)

    by_src = {}
    for r in rows:
        by_src.setdefault(r["source_index"], []).append(r)
    changed_src = []
    for idx, group in by_src.items():
        if idx in RESERVED:
            continue
        if len(group) > 1:
            for extra in group[1:]:
                new_idx = next(fi)
                if not dry:
                    set_index(extra["path"], new_idx)
                changed_src.append((extra["path"].name, idx, new_idx))
    print("source_index reassigned:", len(changed_src))
    for c in changed_src:
        print("  ", c)

    rows = read_expert_ids()
    by_id = {}
    for r in rows:
        by_id.setdefault(r["expert_id"], []).append(r)
    changed_id = []
    for eid, members in by_id.items():
        if len(members) > 1:
            # keep eid prefix (family + first part), derive a unique compact id
            family = eid.split(".")[0]
            for extra in members[1:]:
                eslug = extra["path"].stem.removeprefix("mat9f_").removesuffix("_expert_v1")
                # strip redundant api_security_/api_ framing inside the slug
                parts = eslug.replace("_", ".")
                for prefix in ("api.security.", "security.api.", "api."):
                    if parts.startswith(prefix) and len(parts) > len(prefix) + 1:
                        parts = parts[len(prefix):]
                        break
                new_id = "%s.%s" % (family, parts)
                if not dry:
                    set_expert_id(extra["path"], new_id)
                changed_id.append((extra["path"].name, eid, new_id))
    print("expert_id renamed:", len(changed_id))
    for c in changed_id:
        print("  ", c)


if __name__ == "__main__":
    main()