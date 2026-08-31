# -*- coding: utf-8 -*-
import os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
files = ['mat9f_serverless_expert_v1.py','mat9f_docker_expert_v1.py','mat9f_mlops_expert_v1.py',
         'mat9f_observability_expert_v1.py','mat9f_release_management_expert_v1.py',
         'mat9f_security_awareness_expert_v1.py','mat9f_web_security_expert_v1.py']
keys = ('cloud_connected','function_invoked','deployment_performed','network_used','file_io',
        'http_called','action_performed','storage_accessed','database_used',
        'ingestion_performed','data_mutated','network','file','action')
effects = ','.join('"%s":False' % k for k in keys)
for f in files:
    path = os.path.join('..', 'src', 'memory_agent', f)
    txt = open(path, encoding='utf-8').read()
    # Replace any line that starts the advised return (possibly with malformed blob)
    newline = '    return {"status": "advised", "profile": scores[0][1], ' + effects + '}'
    pat = re.compile(r'^    return \{"status": "advised", "profile": scores\[0\]\[1\],.*$', re.M)
    if pat.search(txt):
        txt = pat.sub(newline, txt)
        open(path, 'w', encoding='utf-8').write(txt)
        print('FIXED', f)
    else:
        print('no-op', f)