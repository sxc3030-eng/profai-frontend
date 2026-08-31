# -*- coding: utf-8 -*-
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
files = ['mat9f_serverless_expert_v1.py','mat9f_docker_expert_v1.py','mat9f_mlops_expert_v1.py',
         'mat9f_observability_expert_v1.py','mat9f_release_management_expert_v1.py',
         'mat9f_security_awareness_expert_v1.py','mat9f_web_security_expert_v1.py']
keys = ('cloud_connected','function_invoked','deployment_performed','network_used','file_io',
        'http_called','action_performed','storage_accessed','database_used',
        'ingestion_performed','data_mutated','network','file','action')
effects = ','.join('"%s":False' % k for k in keys)
# old newline form (with quotes for base dict)
import re
for f in files:
    path = os.path.join('..', 'src', 'memory_agent', f)
    txt = open(path, encoding='utf-8').read()
    # find unquoted cloud_connected=False introduced earlier, remove that trailing blob
    m = re.search(r'\}, cloud_connected=False,.*?action=False\}', txt)
    if m:
        txt = txt.replace(m.group(0), '}')
    old = '    return {"status": "advised", "profile": scores[0][1]}'
    new = '    return {"status": "advised", "profile": scores[0][1], ' + effects + '}'
    if old in txt:
        txt = txt.replace(old, new)
        open(path, 'w', encoding='utf-8').write(txt)
        print('FIXED', f)
    else:
        print('no-op', f, '| has old base?', old in txt)