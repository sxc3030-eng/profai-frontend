# -*- coding: utf-8 -*-
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join('..', 'src', 'memory_agent', 'mat9f_security_awareness_expert_v1.py')
txt = open(path, encoding='utf-8').read()
old = 'return {"status": "refused", "reason": "ambiguous_workload"}'
new = 'return {"status": "refused", "reason": "ambiguous_scenario"}'
if old in txt:
    txt = txt.replace(old, new)
    open(path, 'w', encoding='utf-8').write(txt)
    print('PATCHED ambiguous->scenario')
else:
    print('no-op (not found)')