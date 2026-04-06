from fastcore.all import *
from dialoghelper import *
from IPython.core.magic import register_line_magic

@register_line_magic
def w(line):
    "Run super_w on previous prompt message"
    marker = line.strip() if line.strip() else ''
    return super_w(marker=marker)

try: del w
except: pass

class _Msg(str): ...
class _Code(_Msg): ...
class _Note(_Msg): ...

def _extract_parts(output:str) -> list[_Msg]:
    ll = L(output.split('\n'))
    nn = ll.argwhere(lambda x: x.startswith("```"))
    tt = list(zip(nn[:-1:2], nn[1::2]))
    idx, parts = 0, []
    for block in tt:
        if ll[block[0]].lower().startswith("```python"):
            parts.append(_Note(f"{'\n'.join(ll[idx:block[0]])}".strip()))
            parts.append(_Code(f"{'\n'.join(ll[block[0]+1:block[1]])}".strip()))
            idx = block[1] + 1
        else:
            parts.append(_Note(f"{'\n'.join(ll[idx:block[1]+1])}".strip()))
            idx = block[1] + 2
    parts.append(_Note(f"{'\n'.join(ll[idx:])}".strip()))
    return list(filter(None, parts))
