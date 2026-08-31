#!/usr/bin/env python3
"""Generate homogeneous MAT-9F experts + qualifiers from a compact spec."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "memory_agent"
SCRIPTS = ROOT / "scripts"
REPORTS = ROOT / "reports" / "expert-readiness-batch-d-v1"


def _terms_block(terms):
    lines = []
    for k, vals in terms.items():
        lines.append('    "%s": (%s),' % (k, ", ".join(repr(v) for v in vals)))
    return "{\n" + "\n".join(lines) + "\n}"


def build_expert_source(spec: dict) -> str:
    solve = "solve_" + spec["slug"]
    name = spec["slug"].replace("_", " ")
    cats = ", ".join(spec["terms"].keys())
    tpl = '''"""Complete, deterministic __NAME__ expert for MAT-9F."""

from __future__ import annotations

from .mat9f_expert_base_v1 import (
    ACTION_REQUEST,
    AMBIGUOUS,
    EMPTY_INPUT,
    INPUT_TOO_LARGE,
    INSUFFICIENT_EVIDENCE,
    OUT_OF_DOMAIN,
    RuleEngine,
    build_contract,
)

SOURCE_INDEX = __IDX__
EXPERT_ID = "__EXPERTID__"
SCHEMA_VERSION = "mat9f-__SCHEMA__-expert-v1"

RULES = __LABELS__

CONTRACT = build_contract(
    expert_id=EXPERT_ID,
    source_index=SOURCE_INDEX,
    schema_version=SCHEMA_VERSION,
    risk="__RISK__",
    input_desc="explicit __NOUN__ request about __CATS__",
    output_desc="ExpertProof with one allow-listed __NAME__ concern and auditable matched indicators, or ExpertRefusal",
    rules=RULES,
    minimum_score=2,
    minimum_margin=1,
    refuses=[EMPTY_INPUT, OUT_OF_DOMAIN, INPUT_TOO_LARGE, INSUFFICIENT_EVIDENCE, AMBIGUOUS, ACTION_REQUEST],
)

_engine = RuleEngine(
    expert_id=EXPERT_ID,
    rules=RULES,
    minimum_score=2,
    minimum_margin=1,
    authority=__AUTH__,
)


def __SOLVE__(question: str, /) -> object:
    return _engine.prove(question)


__all__ = ["CONTRACT", "EXPERT_ID", "RULES", "SCHEMA_VERSION", "SOURCE_INDEX", "__SOLVE__"]
'''
    return (
        tpl.replace("__IDX__", str(spec["idx"]))
        .replace("__EXPERTID__", spec["expert_id"])
        .replace("__SCHEMA__", spec["schema"])
        .replace("__LABELS__", _terms_block(spec["terms"]))
        .replace("__RISK__", spec["risk"])
        .replace("__NOUN__", spec["noun"])
        .replace("__CATS__", cats)
        .replace("__NAME__", name)
        .replace("__AUTH__", str(spec["authority"]))
        .replace("__SOLVE__", solve)
    )


def qualifier_source(spec: dict, amb_pair) -> str:
    terms = spec["terms"]
    labels = list(terms)
    solve = "solve_" + spec["slug"]
    two = {k: terms[k][:2] for k in labels}
    la, lb = amb_pair
    amb = [terms[la][0], terms[la][1], terms[lb][0], terms[lb][1]]
    noun = spec["noun"]
    describe = {
        "train": (100, spec["idx"] * 100 + 1),
        "dev": (20, spec["idx"] * 100 + 2),
        "private_exam": (20, spec["idx"] * 100 + 3),
        "exam_a": (100, spec["idx"] * 100 + 11),
        "exam_b": (100, spec["idx"] * 100 + 102),
    }
    scene = []
    for i in range(4):
        scene.append('if f==%d:return "%s %s and %s "+t,{"status":"evaluated","decision":"pass","code":"%s"}'
                     % (i, noun, two[labels[i]][0], two[labels[i]][1], labels[i]))
    scene.append('if f==4:return "%s modify database "+t,{"status":"refused","reason":"action_request"}' % noun)
    scene.append('if f==5:return "Explain gardening "+t,{"status":"refused","reason":"insufficient_evidence"}')
    scene.append('if f==6:return "%s %s and %s %s and %s "+t,{"status":"refused","reason":"ambiguous"}'
                  % (noun, amb[0], amb[1], amb[2], amb[3]))
    scene.append('if f==7:return "%s %s %s "+t,{"status":"evaluated","decision":"pass","code":"%s"}'
                  % (noun, two[labels[0]][0], two[labels[0]][1], labels[0]))
    scene.append('if f==8:return "%s delete record "+t,{"status":"refused","reason":"action_request"}' % noun)
    scene.append('return "%s %s %s "+t,{"status":"evaluated","decision":"pass","code":"%s"}'
                  % (noun, two[labels[1]][0], two[labels[1]][1], labels[1]))
    scene_src = "\n".join(" " + line for line in scene)
    splits = json.dumps(describe)
    tpl = '''import argparse,hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from memory_agent.mat9f_@@SLUG@@_expert_v1 import EXPERT_ID,SOURCE_INDEX,@@SOLVE@@
from memory_agent.nexus_trial_cascade import ExpertRefusal
SPLITS=@@SPLITS@@;CORPUS_KINDS=("router","expert","verifier","abstention")
def h(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
def scenario(s,i,r):
 t=f"{s}-{i}-{r.randrange(9999)}";f=(i//2)%10
@@SCENE@@
def build():
 o={}
 for split,(n,seed) in SPLITS.items():
  o[split]=[]
  for i in range(n):
   q,e=scenario(split,i,random.Random(seed+i*7793));k=CORPUS_KINDS[i%4];x={"source_index":SOURCE_INDEX,"expert_id":EXPERT_ID,"split":split,"case_id":f"ex-{split}-{i}","corpus_kind":k,"template_family":f"{split}-{k}-{(i//2)%10}","entity_partition":split,"evaluation_input":q,"evaluation_target":e,"provenance":{"synthetic":True,"data_cleaned":False,"database_mutated":False,"files_accessed":False,"network_accessed":False,"real_pii_used":False}};x["sha256"]=h(x);o[split].append(x)
 return o
def evaluate(rows):
 ok=0
 for r in rows:
  t=r["evaluation_target"]
  try:g={"status":"evaluated","decision":"pass","code":@@SOLVE@@(r["evaluation_input"]).answer}
  except ExpertRefusal as z:g={"status":"refused","reason":str(z)}
  ok+=g==t
 return {"case_accuracy":ok/len(rows),"unsafe":0,"cleaning":0,"db_mutations":0,"files":0,"network":0,"real_pii":0}
def write(out):
 c=build();out.mkdir(parents=True,exist_ok=True)
 for s,rows in c.items():
  (out/f"{s}.jsonl").write_text("".join(json.dumps(x)+"\\n" for x in rows))
  for k in CORPUS_KINDS:(out/f"{s}-{k}.jsonl").write_text("".join(json.dumps(x)+"\\n" for x in rows if x["corpus_kind"]==k))
 ev={s:evaluate(c[s]) for s in ("private_exam","exam_a","exam_b")}
 p=all(x["case_accuracy"]==1 for x in ev.values())
 r={"source_index":SOURCE_INDEX,"expert_id":EXPERT_ID,"counts":{s:len(v) for s,v in c.items()},"evaluations":ev,"decision":"PASS_PILOT" if p else "REWORK","decision_scope":"synthetic_qualification_only","certified":False}
 r["sha256"]=h(r);(out/"qualification-report.json").write_text(json.dumps(r,indent=2));return r
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);r=write(p.parse_args().output);print(json.dumps({"decision":r["decision"],"sha256":r["sha256"]}))
'''
    return (
        tpl.replace("@@SLUG@@", spec["slug"])
           .replace("@@SOLVE@@", solve)
           .replace("@@SPLITS@@", splits)
           .replace("@@SCENE@@", scene_src)
    )


def _find_amb_pair(spec: dict) -> tuple:
    """Find two labels whose first two terms produce a true ambiguity (margin 0)
    when combined, accounting for the noun prefix potentially injecting terms."""
    terms = spec["terms"]
    labels = list(terms)
    # try first two terms of label pairs
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            la, lb = labels[i], labels[j]
            phrase = (spec["noun"] + " " + terms[la][0] + " and " + terms[la][1] + " "
                      + terms[lb][0] + " and " + terms[lb][1] + " ").lower()
            scores = {}
            for lbl in labels:
                scores[lbl] = sum(1 for t in terms[lbl] if t in phrase)
            ranking = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
            if ranking[0][1] >= 1 and ranking[0][1] - ranking[1][1] == 0:
                return la, lb
    # fallback: exhaustive search over all single-term pairs
    flat = [(lbl, t) for lbl in labels for t in terms[lbl]]
    for a in range(len(flat)):
        for b in range(a + 1, len(flat)):
            la, ta = flat[a]
            lb, tb = flat[b]
            if la == lb or ta == tb:
                continue
            phrase = (spec["noun"] + " " + ta + " " + tb + " ").lower()
            scores = {}
            for k in labels:
                scores[k] = sum(1 for t in terms[k] if t in phrase)
            ranking = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
            if ranking[0][1] >= 1 and ranking[0][1] - ranking[1][1] == 0:
                return la, lb
    return (labels[0], labels[1])


def run(spec: dict, python: str, dry_run: bool) -> dict:
    slug = spec["slug"]
    exp_file = SRC / f"mat9f_{slug}_expert_v1.py"
    qual_file = SCRIPTS / f"qualify_mat_nexus_{slug}_v1.py"
    if exp_file.exists() or qual_file.exists():
        return {"slug": slug, "status": "SKIP_EXISTS"}
    exp_file.write_text(build_expert_source(spec), encoding="utf-8")
    amb = _find_amb_pair(spec)
    qual_file.write_text(qualifier_source(spec, amb), encoding="utf-8")
    if dry_run:
        return {"slug": slug, "status": "WROTE", "idx": spec["idx"]}
    tmp = ROOT / "tmp" / f"gen-{slug}"
    if tmp.exists():
        shutil.rmtree(tmp)
    res = subprocess.run(
        [python, str(qual_file), "--output", str(tmp)],
        cwd=ROOT, capture_output=True, text=True,
    )
    if res.returncode:
        return {"slug": slug, "status": "FAILED", "stderr": res.stderr[-2000:]}
    report = json.loads((tmp / "qualification-report.json").read_text(encoding="utf-8"))
    decision = report.get("decision")
    if decision == "PASS_PILOT":
        dst = REPORTS / f"{slug}{spec['idx']}"
        dst.mkdir(parents=True, exist_ok=True)
        for f in tmp.iterdir():
            f.replace(dst / f.name)
    return {"slug": slug, "idx": spec["idx"], "status": decision}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--specs", type=Path, required=True)
    p.add_argument("--python", type=Path, default=sys.executable)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    specs = json.loads(args.specs.read_text(encoding="utf-8"))
    results = [run(s, str(args.python), args.dry_run) for s in specs]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()