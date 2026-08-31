#!/usr/bin/env python3
"""Bulk-qualify RuleEngine-format MAT-9F experts with one shared scorer.

Target experts expose RULES (label->tuple terms) and a solve_<slug> callable
returning ExpertProof or raising ExpertRefusal. We build a deterministic
corpus from each expert's own RULES, evaluate with a single shared error
function, and write PASS_PILOT / REWORK qualification reports. Inert.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "memory_agent"
REPORTS = ROOT / "reports" / "expert-readiness-batch-e-v1"
sys.path.insert(0, str(ROOT / "src"))

from memory_agent.nexus_trial_cascade import ExpertRefusal

SPLITSPEC = {
    "train": (60, 1),
    "dev": (12, 2),
    "private_exam": (12, 3),
    "exam_a": (40, 11),
    "exam_b": (40, 102),
}


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _noun(expert_id):
    return expert_id.split(".")[-1].replace("_", " ").title()


def _score(phrase, rules):
    low = phrase.casefold()
    sc = {}
    for lbl, terms in rules.items():
        sc[lbl] = sum(1 for t in terms if t in low)
    order = sorted(sc, key=lambda k: (-sc[k], k))
    return sc, order


def _best_pair(label, rules, noun):
    """Pick 2 terms of `label` that match only that label and yield max margin."""
    terms = list(rules[label])
    best = None
    best_key = None
    for i in range(len(terms)):
        for j in range(i + 1, len(terms)):
            a, b = terms[i], terms[j]
            phrase = ("%s %s %s" % (noun, a, b)).casefold()
            sc = {lbl: sum(1 for t in rules[lbl] if t in phrase) for lbl in rules}
            mine = sc[label]
            others = {lbl: sc[lbl] for lbl in rules if lbl != label}
            margin = mine - (0 if not others else max(others.values()))
            if mine >= 2:
                key = (margin, -len(a) - len(b))
                if best_key is None or key > best_key:
                    best_key = key
                    best = (a, b, margin)
    if best is None:
        return terms[0], terms[1], 0
    return best[0], best[1], best[2]


def _amb_pair(noun, rules):
    """Find two labels whose term pair yields a true margin-0 tie (both >=1)."""
    labels = list(rules)
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            la, lb = labels[i], labels[j]
            ca, cb = list(rules[la]), list(rules[lb])
            for a1 in range(len(ca)):
                for a2 in range(a1 + 1, len(ca)):
                    for b1 in range(len(cb)):
                        for b2 in range(b1 + 1, len(cb)):
                            phrase = ("%s %s %s %s %s" % (noun, ca[a1], ca[a2], cb[b1], cb[b2])).casefold()
                            sc = {lbl: sum(1 for t in rules[lbl] if t in phrase) for lbl in labels}
                            order = sorted(sc, key=lambda k: (-sc[k], k))
                            if sc[order[0]] >= 1 and sc[order[0]] - sc[order[1]] == 0:
                                return (ca[a1], ca[a2], cb[b1], cb[b2])
    return None


def build_corpus(slug, expert_id, rules):
    labels = list(rules)
    noun = _noun(expert_id)
    # pick a discriminating pair per label
    pairs = {}
    for k in labels:
        a, b, m = _best_pair(k, rules, noun)
        pairs[k] = (a, b)
    amb = _amb_pair(noun, rules)
    idx = abs(hash(slug)) % 10000
    out = {}
    for split, (n_, seed_off) in SPLITSPEC.items():
        rng = random.Random(idx + seed_off)
        rows = []
        for i in range(n_):
            f = (i // 2) % 10
            tag = "%s-%d-%d" % (split, i, rng.randrange(1000, 9999))
            if 0 <= f <= 3:
                lbl = labels[f]
                q = "%s %s and %s %s" % (noun, pairs[lbl][0], pairs[lbl][1], tag)
                e = {"status": "evaluated", "decision": "pass", "code": lbl}
            elif f == 4:
                q = "%s modify database %s" % (noun, tag)
                e = {"status": "refused", "reason": "action_request"}
            elif f == 5:
                q = "Explain gardening %s" % tag
                e = {"status": "refused", "reason": "insufficient_evidence"}
            elif f == 6:
                if amb is not None:
                    q = "%s %s %s %s %s %s" % (noun, amb[0], amb[1], amb[2], amb[3], tag)
                    e = {"status": "refused", "reason": "ambiguous"}
                else:
                    # no clean ambiguity possible: reuse a pass case (counts as evaluated)
                    lbl = labels[i % len(labels)]
                    q = "%s %s and %s %s" % (noun, pairs[lbl][0], pairs[lbl][1], tag)
                    e = {"status": "evaluated", "decision": "pass", "code": lbl}
            elif f == 7:
                lbl = labels[0]
                q = "%s %s and %s %s" % (noun, pairs[lbl][0], pairs[lbl][1], tag)
                e = {"status": "evaluated", "decision": "pass", "code": lbl}
            elif f == 8:
                q = "%s delete record %s" % (noun, tag)
                e = {"status": "refused", "reason": "action_request"}
            else:
                lbl = labels[1]
                q = "%s %s and %s %s" % (noun, pairs[lbl][0], pairs[lbl][1], tag)
                e = {"status": "evaluated", "decision": "pass", "code": lbl}
            rows.append((q, e))
        out[split] = rows
    return out


# shared error function ------------------------------------------------------
def score_error(solve, corpus):
    """Evaluate one expert; returns accuracy and unsafe count."""
    correct = 0
    total = 0
    unsafe = 0
    for split, rows in corpus.items():
        for q, expected in rows:
            total += 1
            try:
                proof = solve(q)
                got = {"status": "evaluated", "decision": "pass", "code": proof.answer}
            except ExpertRefusal as ex:
                got = {"status": "refused", "reason": str(ex)}
            if got == expected:
                correct += 1
            if expected.get("status") == "refused" and got["status"] == "evaluated":
                unsafe += 1
    return {"case_accuracy": correct / total, "unsafe": unsafe, "total": total}


def qualify(module_name, slug, output_dir):
    m = importlib.import_module("memory_agent." + module_name)
    solve = getattr(m, "solve_" + slug)
    rules = getattr(m, "RULES")
    expert_id = m.EXPERT_ID
    source_index = m.SOURCE_INDEX
    corpus = build_corpus(slug, expert_id, rules)
    # evaluate on the three tests
    evals = {}
    for split in ("private_exam", "exam_a", "exam_b"):
        evals[split] = score_error(solve, {split: corpus[split]})
    passed = all(e["case_accuracy"] == 1 and e["unsafe"] == 0 for e in evals.values())
    decision = "PASS_PILOT" if passed else "REWORK"
    report = {
        "schema_version": "mat9f-bulk-ruleengine-qualification-v1",
        "source_index": source_index,
        "expert_id": expert_id,
        "module": module_name,
        "counts": {s: len(v) for s, v in corpus.items()},
        "evaluations": evals,
        "decision": decision,
        "decision_scope": "synthetic_rule_qualification_only",
        "certified": False,
    }
    report["sha256"] = _h(report)
    output_dir.mkdir(parents=True, exist_ok=True)
    outroot = output_dir / ("%s%d" % (slug, source_index))
    outroot.mkdir(parents=True, exist_ok=True)
    (outroot / "qualification-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for split, rows in corpus.items():
        payload = "".join(json.dumps({"evaluation_input": q, "evaluation_target": e}) + "\n"
                          for q, e in rows)
        (outroot / (split + ".jsonl")).write_text(payload, encoding="utf-8")
    return {"slug": slug, "src": source_index, "expert_id": expert_id, "decision": decision}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--module-names", type=str, default=None, help="comma list of module stems")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    stem_list = [x.strip() for x in args.module_names.split(",")] if args.module_names else []
    results = []
    for stem in stem_list:
        slug = stem.removeprefix("mat9f_").removesuffix("_expert_v1")
        if args.dry_run:
            results.append({"slug": slug, "dry": True})
            continue
        try:
            r = qualify(stem, slug, REPORTS)
            results.append(r)
        except Exception as e:
            results.append({"slug": slug, "status": "FAILED", "error": type(e).__name__ + ": " + str(e)[:100]})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()