# -*- coding: utf-8 -*-
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join('..', 'src', 'memory_agent', 'mat9f_mlops_expert_v1.py')
txt = open(path, encoding='utf-8').read()
# fix dataset refusal
txt = txt.replace(
    "'\\\\bupload\\\\b|\\\\bdataset\\\\b'",
    "r'upload\\b|\\bupload dataset\\b'")
# fix email regex (single backslash escapes)
import re
txt = re.sub(
    r"'(\\\\b\[a-z0-9._%+\-]+\+@\[a-z0-9.\-]+\.[a-z]{2,}\\\\b)'",
    "r'[a-z0-9._%+-]+@[a-z0-9.-]+\\\\.[a-z]{2,}'",
    txt)
open(path, 'w', encoding='utf-8').write(txt)
print('PATCHED mlops')