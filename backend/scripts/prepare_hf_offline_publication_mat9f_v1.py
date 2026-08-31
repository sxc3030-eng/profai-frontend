#!/usr/bin/env python3
"""Prepare a MAT-9F Hugging Face package locally; never uploads or logs in."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from memory_agent.mat9f_hf_offline_publication_gate_v1 import (  # noqa: E402
    PublicationEvidence, PublicationGateError, build_offline_package, evaluate_gate)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tests-300",type=Path,required=True);p.add_argument("--benchmark",type=Path,required=True)
    p.add_argument("--certification",type=Path,required=True);p.add_argument("--model-id",required=True)
    p.add_argument("--artifact",type=Path,action="append",default=[]);p.add_argument("--output-dir",type=Path)
    p.add_argument("--check-only",action="store_true");a=p.parse_args(argv)
    evidence=PublicationEvidence(a.tests_300,a.benchmark,a.certification)
    try:
        if a.check_only:
            result=evaluate_gate(evidence).receipt
        else:
            if a.output_dir is None: p.error("--output-dir est requis hors --check-only")
            result=build_offline_package(output_dir=a.output_dir,model_id=a.model_id,
                                         artifacts=a.artifact,evidence=evidence)
    except PublicationGateError as error:
        sys.stderr.write(json.dumps({"ok":False,"error":str(error)},sort_keys=True)+"\n");return 2
    sys.stdout.write(json.dumps({"ok":True,"result":result},sort_keys=True)+"\n");return 0
if __name__=="__main__": raise SystemExit(main())
