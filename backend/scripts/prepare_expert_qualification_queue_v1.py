"""Build deterministic, non-activating qualification batches from consolidation."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/"reports"/"mat9f-expert-status-consolidation-v1.json";OUT=ROOT/"reports"/"expert-qualification-queue-v1.json"
def main():
 data=json.loads(SOURCE.read_text(encoding="utf-8"));rows=[]
 for x in data["rows"]:
  if x["status"]=="ACTIVE_PASS_PILOT" or x["issues"]:continue
  slug=x["module"].removeprefix("mat9f_").removesuffix("_expert_v1");script=ROOT/"scripts"/f"qualify_mat_nexus_{slug}_v1.py"
  rows.append({"source_index":x["source_index"],"expert_id":x["expert_id"],"module":x["module"],"prior_status":x["status"],"qualifier":str(script) if script.is_file() else None,"queue_status":"PENDING"})
 rows.sort(key=lambda x:({"REWORK":0,"INCONCLUSIVE":1,"UNTESTED":2}.get(x["prior_status"],9),x["source_index"],x["expert_id"]))
 batches=[{"batch":i//25+1,"items":rows[i:i+25]} for i in range(0,len(rows),25)]
 report={"schema_version":"mat9f-expert-qualification-queue-v1","batch_size":25,"counts":{"experts":len(rows),"batches":len(batches),"with_qualifier":sum(bool(x["qualifier"]) for x in rows)},"batches":batches,"activation_performed":False,"hf_used":False}
 report["sha256"]=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest();OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps(report["counts"],sort_keys=True))
if __name__=="__main__":main()
