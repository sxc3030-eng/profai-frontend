"""Consolidate local MAT-9F expert status evidence without activating experts."""
from __future__ import annotations
import ast, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESERVED=frozenset({25,27,33,43,47,117,118,119,120,121,129,130,135,143,147,151,156,161,165,166,167,168,176,183,188,195,202,207})
DECISIONS=frozenset({"PASS_PILOT","FAIL_PILOT","INCONCLUSIVE","REWORK","RETRAIN","REJECT","CERTIFICATION_CANDIDATE"})

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def literals(path):
 t=ast.parse(path.read_text(encoding="utf-8"),filename=str(path));out={}
 for n in t.body:
  if not isinstance(n,(ast.Assign,ast.AnnAssign)):continue
  targets=n.targets if isinstance(n,ast.Assign) else [n.target]
  try:v=ast.literal_eval(n.value)
  except Exception:continue
  for x in targets:
   if isinstance(x,ast.Name) and x.id in ("SOURCE_INDEX","EXPERT_ID"):out[x.id]=v
 return out
def modules(root=ROOT):
 rows=[]
 for p in sorted((root/"src"/"memory_agent").glob("mat9f_*_expert_v1.py")):
  try:x=literals(p)
  except Exception as e:rows.append({"module":p.stem,"path":str(p),"source_index":None,"expert_id":None,"parse_error":type(e).__name__});continue
  rows.append({"module":p.stem,"path":str(p),"source_index":x.get("SOURCE_INDEX"),"expert_id":x.get("EXPERT_ID"),"parse_error":None})
 return rows
def evidence(root=ROOT):
 rows=[]
 for base in (root/"reports",root/"autonomous-expert-factory"/"runs"):
  if not base.exists():continue
  for p in base.rglob("*.json"):
   if "qualification" not in p.name and p.name!="report.json":continue
   try:j=json.loads(p.read_text(encoding="utf-8"))
   except Exception:continue
   d=j.get("decision");s=j.get("source_index");e=j.get("expert_id")
   if d not in DECISIONS or not isinstance(s,int):continue
   rows.append({"path":str(p),"mtime_ns":p.stat().st_mtime_ns,"source_index":s,"expert_id":e,"decision":d,"certified":j.get("certified") is True})
 return rows
def consolidate(root=ROOT):
 ms=modules(root);ev=evidence(root);by_source={};by_id={}
 for m in ms:
  if isinstance(m["source_index"],int):by_source.setdefault(m["source_index"],[]).append(m["module"])
  if isinstance(m["expert_id"],str):by_id.setdefault(m["expert_id"],[]).append(m["module"])
 dup_s={k:v for k,v in by_source.items() if len(v)>1};dup_i={k:v for k,v in by_id.items() if len(v)>1}
 rows=[];excluded=[]
 for m in ms:
  s=m["source_index"];eid=m["expert_id"]
  if s in RESERVED:excluded.append({**m,"reason":"reserved_source"});continue
  issues=[]
  if not isinstance(s,int) or not isinstance(eid,str) or not eid:issues.append("identity_missing")
  if s in dup_s:issues.append("duplicate_source_index")
  if eid in dup_i:issues.append("duplicate_expert_id")
  related=[x for x in ev if x["source_index"]==s]
  matching=[x for x in related if x["expert_id"] in (None,eid)]
  mismatched=[x for x in related if x["expert_id"] not in (None,eid)]
  latest=max(matching,key=lambda x:(x["mtime_ns"],x["path"])) if matching else None
  if issues:status="REWORK"
  elif latest:
   if latest["decision"]=="PASS_PILOT":status="ACTIVE_PASS_PILOT"
   elif latest["decision"] in ("FAIL_PILOT","REWORK","RETRAIN","REJECT"):status="REWORK"
   else:status="INCONCLUSIVE"
  elif related or mismatched:status="INCONCLUSIVE"
  else:status="UNTESTED"
  rows.append({**m,"status":status,"issues":issues,"latest_valid_result":latest,"mismatched_evidence_count":len(mismatched)})
 counts={k:sum(r["status"]==k for r in rows) for k in ("ACTIVE_PASS_PILOT","REWORK","INCONCLUSIVE","UNTESTED")}
 report={"schema_version":"mat9f-expert-status-consolidation-v1","created_at":datetime.now(timezone.utc).isoformat(),"module_files_seen":len(ms),"eligible_modules":len(rows),"reserved_excluded":len(excluded),"reserved_source_indexes":sorted(RESERVED),"counts":counts,"duplicate_source_indexes":{str(k):v for k,v in sorted(dup_s.items()) if k not in RESERVED},"duplicate_expert_ids":dup_i,"rows":rows,"excluded":excluded,"activation_performed":False,"hf_used":False,"publication_performed":False,"certified_automatically":False}
 report["sha256"]=hashlib.sha256(canonical(report).encode()).hexdigest();return report
def main():
 r=consolidate();p=ROOT/"reports"/"mat9f-expert-status-consolidation-v1.json";p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(canonical({k:r[k] for k in ("module_files_seen","eligible_modules","reserved_excluded","counts","sha256")}))
if __name__=="__main__":main()
