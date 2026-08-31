# -*- coding: utf-8 -*-
import os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
EFFECTS = {
    'docker': ('daemon_connected','image_built','container_run','image_pushed','network_used','file_io'),
    'mlops': ('training_performed','deployment_performed','model_called','dataset_accessed','network_used','file_io'),
    'observability': ('backend_connected','query_executed','network_used','file_io','configuration_changed'),
    'release_management': ('deployment_performed','release_action_performed','network_used','file_io'),
    'web_security': ('network_used','request_sent','exploit_performed','deployment_performed','file_io'),
}
for slug, keys in EFFECTS.items():
    path = os.path.join('..', 'src', 'memory_agent', 'mat9f_%s_expert_v1.py' % slug)
    txt = open(path, encoding='utf-8').read()
    effects = ','.join('"%s":False' % k for k in keys)
    # current line: return {"status": "advised", "profile": scores[0][1], "...":False,...}
    pat = re.compile(r'^    return \{"status": "advised", "profile": scores\[0\]\[1\],.*$', re.M)
    newline = '    return {"status": "advised", "profile": scores[0][1], ' + effects + '}'
    if pat.search(txt):
        txt = pat.sub(newline, txt)
        open(path, 'w', encoding='utf-8').write(txt)
        print('PATCHED', slug, keys)
    else:
        print('no-op', slug)