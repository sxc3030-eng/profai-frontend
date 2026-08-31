# -*- coding: utf-8 -*-
import os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
PATCHES = [
    ('data_lake', 'analyzed', 'storage_accessed,file_io,database_used,network_used,ingestion_performed,data_mutated'),
    ('database_replication', 'analyzed', 'database_connected,sql_executed,network_used,failover_performed,data_mutated,file_io'),
    ('data_serialization', 'inspected', 'code_executed,file_io,network_used,object_instantiated'),
    ('contract_testing', 'compared', 'network_used,service_invoked,file_io'),
]
for slug, status, keys in PATCHES:
    path = os.path.join('..', 'src', 'memory_agent', 'mat9f_%s_expert_v1.py' % slug)
    txt = open(path, encoding='utf-8').read()
    effects = ','.join('"%s":False' % k for k in keys.split(','))
    # find the return with that status at the end of the analyzer function
    # general: any line starting with '    return {"status": "%s"' indentation 4
    pat = re.compile(r'^    return \{"status": "%s".*$' % status, re.M)
    newline = '    return {"status": "%s"' % status
    # easier: append effects into the existing return's closing
    # We'll rewrite the specific return lines per analyzer.
    if slug == 'data_lake':
        old = '    return {"status": "analyzed", "object_count": len(objs), "total_bytes": total,\n            "unknown_formats": unknown, "findings": findings}'
        new = '    return {"status": "analyzed", "object_count": len(objs), "total_bytes": total,\n            "unknown_formats": unknown, "findings": findings, ' + effects + '}'
    elif slug == 'database_replication':
        old = '    return {"status": "analyzed", "replica_count": len(reps),\n            "max_lag_seconds": float(max_lag), "findings": findings}'
        new = '    return {"status": "analyzed", "replica_count": len(reps),\n            "max_lag_seconds": float(max_lag), "findings": findings, ' + effects + '}'
    elif slug == 'data_serialization':
        old = '    return {"status": "inspected", "operation": op, "canonical": canonical}'
        new = '    return {"status": "inspected", "operation": op, "canonical": canonical, ' + effects + '}'
    elif slug == 'contract_testing':
        old = '    return {"status": "compared", "verdict": "fail" if viol else "pass",\n            "violations": viol}'
        new = '    return {"status": "compared", "verdict": "fail" if viol else "pass",\n            "violations": viol, ' + effects + '}'
    if old in txt:
        txt = txt.replace(old, new)
        open(path, 'w', encoding='utf-8').write(txt)
        print('PATCHED', slug)
    else:
        print('no-op', slug, '| old not found')