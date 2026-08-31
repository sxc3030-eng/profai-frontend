# -*- coding: utf-8 -*-
import os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# slug -> exact ood refusal string expected by the qualify script
OOD = {
    'serverless': 'out_of_domain:explicit_serverless_design_required',
    'docker': 'out_of_domain:explicit_docker_review_required',
    'mlops': 'out_of_domain:explicit_mlops_design_required',
    'observability': 'out_of_domain:explicit_observability_architecture_required',
    'release_management': 'out_of_domain:explicit_release_governance_request_required',
    'security_awareness': 'out_of_domain:explicit_security_awareness_request_required',
    'web_security': 'out_of_domain:explicit_defensive_web_review_required',
}
for slug, ood in OOD.items():
    path = os.path.join('..', 'src', 'memory_agent', 'mat9f_%s_expert_v1.py' % slug)
    txt = open(path, encoding='utf-8').read()
    old = 'ood = None or ("out_of_domain:explicit_%s_request_required" %% "%s")' % (slug, slug)
    new = 'ood = "%s"' % ood
    if old in txt:
        txt = txt.replace(old, new)
        open(path, 'w', encoding='utf-8').write(txt)
        print('FIXED', slug)
    else:
        # try regex fallback for the generic form
        pat = re.compile(r'ood = None or \([^)]*\)')
        if pat.search(txt):
            txt = pat.sub('ood = "%s"' % ood, txt)
            open(path, 'w', encoding='utf-8').write(txt)
            print('REGEX_FIXED', slug)
        else:
            print('no-op', slug)