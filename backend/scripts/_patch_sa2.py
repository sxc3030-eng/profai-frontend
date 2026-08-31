# -*- coding: utf-8 -*-
import os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
slug = 'security_awareness'
path = os.path.join('..', 'src', 'memory_agent', 'mat9f_%s_expert_v1.py' % slug)
txt = open(path, encoding='utf-8').read()
keys = ('credential_collected','message_sent','action_performed','network_used','file_io')
extra = 'not_legal_advice'
effects = ','.join('"%s":False' % k for k in keys) + ',"%s":True' % extra
pat = re.compile(r'^    return \{"status": "advised", "profile": scores\[0\]\[1\],.*$', re.M)
newline = '    return {"status": "advised", "profile": scores[0][1], ' + effects + '}'
if pat.search(txt):
    txt = pat.sub(newline, txt)
    open(path, 'w', encoding='utf-8').write(txt)
    print('PATCHED', slug)
else:
    print('no-op')