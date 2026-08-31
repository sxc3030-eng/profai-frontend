# -*- coding: utf-8 -*-
"""Make action/unsafe refusal patterns word-boundary precise."""
import os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# slug -> list of (old_pattern, new_pattern) replacements
REPL = {
    'docker': [
        ('docker run|run container|deploy', r'\\bdocker run\\b|\\brun container\\b|\\bdeploy\\b'),
    ],
    'mlops': [
        ('deploy|production model', r'\\bdeploy\\b|\\bproduction model\\b'),
        ('upload|dataset', r'\\bupload\\b|\\bdataset\\b'),
    ],
    'observability': [
        ('connect', r'\\bconnect\\b'),
        ('alert threshold|set alert', r'\\balert threshold\\b|\\bset alert\\b'),
        ('instrument.*span|span', r'\\binstrument\\b.*\\bspan\\b|\\bspan\\b'),
    ],
    'web_security': [
        ('attack|payload|exploit', r'\\battack\\b|\\bpayload\\b|\\bexploit\\b'),
    ],
}
for slug, reps in REPL.items():
    path = os.path.join('..', 'src', 'memory_agent', 'mat9f_%s_expert_v1.py' % slug)
    txt = open(path, encoding='utf-8').read()
    changed = 0
    for old, new in reps:
        # replace occurrences inside the refusals list literal string
        cnt = txt.count('"%s"' % old)
        if cnt:
            txt = txt.replace('"%s"' % old, '"%s"' % new)
            changed += cnt
    open(path, 'w', encoding='utf-8').write(txt)
    print('PATCHED', slug, 'replacements', changed)