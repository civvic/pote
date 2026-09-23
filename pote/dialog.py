"""Provide message and dialog introspection, and import/export utilities for solveit dialogs.

## Dialog toolkit overview

`pote.dialog` is a toolkit for working with Solveit dialogs as structured collections of messages. It helps inspect message metadata and dialog state, map section structure, select relevant messages, disclose notes and code deterministically, serialize digests, and transfer messages between dialogs.

Main helper families:

- **Content utilities** — `count_tokens`, `split_md_blocks` to split Markdown blocks; use `header_preview`, `clamp_note` to progressively disclose note content.
- **Message & dialog utilities** — use `get_msg_id`, `get_output`, `format_output`, `nb_path`, `dlg_module`, `dlg_export`, `get_dialog_link`, `get_msg_id`, `format_output`, `get_output` to locate, export, link, and inspect dialogs and messages.
- **Dialog structure** — use `heading_msgs`, `fmt_sections`, `details_sections`, and `section_map` to build and render a dialog outline.
- **Disclosure** — use `disclose` for Python source, `disclose_msgs` for copied message lists, and `disclose_dialog` or `disclose_nb` for a whole dialog/notebook.
- **Selection and digests** — use `filter_msgs_v2` to scope and filter messages, then `exportmsgs` to serialize them as Markdown, XML, or JSON.
- **Cross-dialog transfer** — use `importdlg` to insert selected messages into another dialog.

The usual flow is: inspect dialog structure, select messages, optionally disclose notes and code, then serialize or transfer the selected messages. Selection preserves dialog order.

---

## content utils

`count_tokens()` measures how much LLM context a piece of text uses.

```python
count_tokens("Hello world!")
# 3
```

`first_para()` extracts the first meaningful paragraph from Markdown content, ignoring headings, lists, and code blocks.

```python
first_para('# Title\n\nFirst sentence. Second sentence.\n\nSecond paragraph.')
# 'First sentence. Second sentence.'
```

`first_sent()` extracts the first sentence of that paragraph.

```python
first_sent('First sentence. Second sentence.')
# 'First sentence.'
```

`split_md_blocks(md, para=False)`
Splits a markdown string into its constituent blocks, separating fenced code blocks from surrounding prose, so callers can process or transform each block type independently.

`atx_heading_levels()` finds the minimum and maximum levels of real ATX headings.

`shift_heading_levels()` raises or lowers those heading levels by a fixed amount, leaving the source unchanged when the shift would produce an invalid level outside 1–6.

---

## note disclosure

`header_preview` returns a compact preview only for Markdown content beginning with a heading. `clamp_note` provides the same heading-based levels, plus paragraph and line-based excerpts.

| Level | Returns |
|---|---|
| `'header'` | The leading heading only |
| `'header+'` | Heading + first sentence of the immediately following Markdown paragraph |
| `'header++'` | Heading + the immediately following Markdown paragraph |
| `'first_para'` | First Markdown paragraph anywhere in the content |
| `int` | First *n* source lines after trimming outer whitespace |

For `'header+'` and `'header++'`, the first block after the heading must be a paragraph. A subheading, list, block quote, code fence, missing block, unsupported level, or missing leading heading returns `''`. `'header'` needs no following paragraph.

Both functions accept `max_chars` to cap the complete returned excerpt. When truncation is needed, they append `suffix` (default: `'…'`); `max_chars=0` returns `''`. Integer excerpts preserve blank lines within the selected lines.

```python
header_preview('# Title\n\nIntro. More detail.', 'header+')
# '# Title\nIntro.'

header_preview('# Title\n\n## Later section\n\nIntro.', 'header++')
# ''

clamp_note('# Title\n\nIntro. More detail.', 'first_para', max_chars=10)
# 'Intro. Mo…'

clamp_note('One\n\nTwo\nThree', 3)
# 'One\n\nTwo'
```

---

## Dialog section navigation

Use these helpers to turn a dialog’s heading notes into a navigable outline.

```python
secs = await heading_msgs()
```

Returns ordered `(id, level, title, summary)` records for Markdown headings.

```python
Markdown(fmt_sections(secs))
```

Renders a compact Markdown outline, with hierarchy and `#_<id>` message links.

```python
details_sections(secs)
```

Renders the same structure as a nested, collapsible HTML tree.

Use `heading_msgs(dname)` for another dialog; omit `dname` for the current one.

### Common workflows

Inspect a dialog’s conceptual structure:

```python
secs = await heading_msgs('/prj/pote/nbs/01_dialog')
```

Select non-hidden exported material from one section, preserving dialog order:

```python
msgs = await filter_msgs_v2(section='## distill', metadata=['exported', '!hidden'])
```

Create a compact handoff-style Markdown digest from an already selected list:

```python
md = exportmsgs(disclose_msgs(msgs, note_level='header++', code_level=2), fmt='md', hdr_clamp='full', output=False)
```

Import the latest defining message for a symbol from another dialog:

```python
new_ids = await importdlg('/prj/pote/nbs/01_dialog', syms=['filter_msgs_v2'], header=True)
```

Use `doc()` on the relevant function before calling it: the module overview identifies a helper family, while function documentation supplies its exact contract.

### Preferred message-selection workflow

Use `filter_msgs_v2` for high-level selection. It first scopes messages by `ids` and/or `section`, then filters within that scope by message type, metadata, and an optional content pattern. Positive filter terms are unioned; `!`-prefixed terms are removed from the scoped result; returned messages retain dialog order.

`filter_msgs_v1` remains available as an exploratory union-based query model, but `filter_msgs_v2` is normally the clearer choice for scoped work.

### Digest workflow

A digest has three independent stages: select messages with `filter_msgs_v2` or a supplied list; optionally create copied, progressively disclosed messages with `disclose_msgs`; then serialize with `exportmsgs` as Markdown, XML, or JSON. `exportmsgs` serializes selected messages; it does not decide which messages are relevant.

Disclosure is deterministic: `clamp_note` reduces note detail and `disclose` reduces code detail without modifying originals. Digest and chunk strings are transient artifacts; materialize them into dialog messages or files when they must remain available as durable context.

Docs: https://civvic.github.io/pote/dialog.html.md"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_dialog.ipynb.

# %% auto #0
__all__ = ['get_ids', 'show_ids', 'count_tokens', 'first_para', 'first_sent', 'atx_heading_levels', 'shift_heading_levels',
           'split_md_blocks', 'clamp_note', 'header_preview', 'get_msg_id', 'get_output', 'format_output', 'expand',
           'expand_replace', 'nb_path', 'dlg_module', 'dlg_export', 'get_dialog_link', 'heading_msgs', 'fmt_sections',
           'details_sections', 'disclose', 'exportmsgs', 'section_map', 'filter_msgs_v2', 'disclose_msgs', 'importdlg']

# %% ../nbs/01_dialog.ipynb #1e28a183
import re, json, ast, warnings, copy, asttokens
from html import escape
from pathlib import Path
from typing import TypeAlias
from IPython import get_ipython
from mdhtml import to_md, blocks
from fasthtml.components import A, Details, P, Summary, Li, Ul
from fastcore.foundation import patch, AttrDict as AD
from fastcore.meta import delegates
from fastcore.nbio import mk_cell
from fastcore.py2pyi import functypes
from dialoghelper.core import add_msg, read_msg, find_msgs, msg_idx, run_msg, toggle_header, find_dname, update_msg
from dialoghelper.utils import ast_py
from .dutil import in_dialog

# %% ../nbs/01_dialog.ipynb #7e7a6f23
Msg: TypeAlias = AD

# %% ../nbs/01_dialog.ipynb #5bc6f162
class MsgX(Msg): ...

# %% ../nbs/01_dialog.ipynb #fa0e5b45
def msgx(msg:Msg) -> MsgX:
    "Cast `msg` to MsgX in place and return it."
    msg.__class__ = MsgX
    return msg

# %% ../nbs/01_dialog.ipynb #bb3e6b75
@delegates(find_msgs)
async def find_msgs_x(*args, **kwargs) -> list[MsgX]:
    "find_msgs returning MsgX instances."
    ms = await find_msgs(*args, **kwargs)
    for m in ms: m.__class__ = MsgX
    return ms

# %% ../nbs/01_dialog.ipynb #e923ee5a
async def get_ids(n=1):
    "Return ids for the previous `n` messages"
    if (n:=int(n)) < 0: n = 0
    return tuple([(await read_msg(i)).id for i in range(-n, 0)])

# %% ../nbs/01_dialog.ipynb #c2b52393
async def show_ids(n=3, template='Expanded into {}.'):
    "Show a list of ids."
    print(template.format(' · '.join(f"#_{_}" for _ in await get_ids(n))))

# %% ../nbs/01_dialog.ipynb #dba09e40
def count_tokens(src, model='cl100k_base'):
    "Count tokens in `src` using `model` encoding"
    import tiktoken
    return len(tiktoken.get_encoding(model).encode(src))

# %% ../nbs/01_dialog.ipynb #c32dfee4
def _text_blocks(src):
    "Return top-level Markdown blocks with spans replaced by source text."
    src = to_md(src)
    ls = src.splitlines()
    return [AD(**{k:v for k,v in b.items() if k not in ('start','end')}, _src='\n'.join(ls[b['start']:b['end']])) for b in blocks(src)]

# %% ../nbs/01_dialog.ipynb #79162b43
def _quote_para(src):
    "Return the first direct paragraph from blockquote source, or `''`."
    src = re.sub(r'^> ?', '', src, flags=re.M)
    bs = _text_blocks(src)
    if not bs or bs[0].type != 'paragraph': return ''
    return bs[0]._src

# %% ../nbs/01_dialog.ipynb #477415ba
def first_para(src, allowed_before=('heading',), allow_blockquote=False):
    "Return the first top-level prose block, optionally after one allowed lead-in block, or `''`."
    bs = _text_blocks(src)
    if bs and bs[0].type in allowed_before: bs = bs[1:]
    if not bs: return ''
    b = bs[0]
    if b.type == 'paragraph': return b._src
    if not allow_blockquote or b.type != 'block_quote': return ''
    bs = _text_blocks(re.sub(r'^> ?', '', b._src, flags=re.M))
    return bs[0]._src if bs and bs[0].type == 'paragraph' else ''

# %% ../nbs/01_dialog.ipynb #271136e5
@delegates(first_para)
def first_sent(src, **kwargs):
    "Return first sentence of first Markdown paragraph in `src`."
    src = first_para(src, **kwargs).strip()
    m = re.search(r'''(?s).*?[.!?][*_`)\]]*(?=\s|$)''', src)
    return m.group() if m else src

# %% ../nbs/01_dialog.ipynb #e36c7286
_atx_re = re.compile(r' {0,3}(#{1,6})(?:[ \t]+|$)')

# %% ../nbs/01_dialog.ipynb #a5dab079
def _heading_lines(src):
    "Return `(line_index, level)` pairs for top-level ATX headings."
    ls = src.splitlines()
    return [(b['start'], len(m.group(1))) for b in blocks(src) if b['type'] == 'heading' and (m := _atx_re.match(ls[b['start']]))]

def atx_heading_levels(src):
    "Return minimum and maximum top-level ATX heading levels in `src`."
    lvls = [lvl for _,lvl in _heading_lines(src)]
    return (min(lvls), max(lvls)) if lvls else (0, 0)

def shift_heading_levels(src:str, change:int):
    "Shift top-level ATX heading levels by `change`."
    lvls = {i:lvl + change for i,lvl in _heading_lines(src)}
    if not all(1 <= lvl <= 6 for lvl in lvls.values()): return src
    lines = src.splitlines(keepends=True)
    for i,lvl in lvls.items(): lines[i] = re.sub(r'^(\s{0,3})#{1,6}(?=[ \t\r\n]|$)', lambda m: m[1] + '#' * lvl, lines[i], count=1)
    return ''.join(lines)

# %% ../nbs/01_dialog.ipynb #318b4cde
def split_md_blocks(md, all_blocks=False):
    "Split Markdown around nonempty fenced code, optionally separating top-level blocks"
    def fenced(o): return o.type == 'code_block' and bool(re.match(r' {0,3}(?:`{3,}|~{3,})', o._src))
    bs = [o for o in _text_blocks(md) if o._src.strip()]
    bs = [o for o in bs if not (fenced(o) and not o.get('text', '').strip())]
    if all_blocks: return [o._src+'\n' for o in bs]
    res,buf = [],[]
    for o in bs:
        if fenced(o):
            if buf: res.append('\n\n'.join(buf)+'\n'); buf = []
            res.append(o._src+'\n')
        else: buf.append(o._src)
    if buf: res.append('\n\n'.join(buf)+'\n')
    return res

# %% ../nbs/01_dialog.ipynb #ee41d557
def _clamp_chars(src,
    max_chars:int=None, # Maximum characters in returned excerpt
    suffix:str='…' # Suffix to append when truncating
):
    if max_chars is None or len(src) <= max_chars: return src
    return src[:max_chars-len(suffix)] + suffix if max_chars else ''

# %% ../nbs/01_dialog.ipynb #45a0e97f
_ATX_hdr_pat = r'''\A {0,3}#{1,6}(?:[ \t]+|$)'''
_ATX_hdr = re.compile(_ATX_hdr_pat)

# %% ../nbs/01_dialog.ipynb #428b9004
@delegates(_clamp_chars)
def clamp_note(
    src:str, # Markdown content
    level:str|int='header', # Disclosure level: header level, 'first_para', or int for max lines
    **kwargs
) -> str:
    "Return a progressively disclosed excerpt of Markdown `src`."
    if not (src := src.strip()): return ''
    excerpt = '\n'.join(src.splitlines()[:level]) if isinstance(level, int) else first_para(src) if level == 'first_para' else header_preview(src, level)
    return _clamp_chars(excerpt, **kwargs)

# %% ../nbs/01_dialog.ipynb #a5b27dcb
@delegates(_clamp_chars)
def header_preview(
    src:str,
    level:str='header',
    **kwargs
) -> str:
    "Return a heading, or a heading-led preview when the next block is a paragraph."
    if level not in ('header', 'header+', 'header++') or not _ATX_hdr.match(src): return ''
    hdr,_,rest = src.strip().partition('\n')
    if level == 'header': return _clamp_chars(hdr, **kwargs)
    bs = _text_blocks(rest.strip())
    if not bs or bs[0].type != 'paragraph': return ''
    para = bs[0]._src
    excerpt = first_sent(para) if level == 'header+' else para
    return _clamp_chars(f'{hdr}\n{excerpt}', **kwargs)

# %% ../nbs/01_dialog.ipynb #084ce165
_exports = {'exporti', 'exports', 'exportd', 'export'}
_hidden = {'hide', 'include'}
_echo = {'echo', 'echo:'}

# %% ../nbs/01_dialog.ipynb #8e71d4cb
def is_exported(m:Msg, msg_types={'code', 'note'}) -> bool:
    "Is message exported with solveit metadata or nbdev directive?"
    return m.get('exported') or (m.msg_type in msg_types and bool(mk_cell(m.content).directives.keys() & _exports))

def is_hidden(m:Msg) -> bool:
    "Is message hidden by a nbdev directive (only for doc generation, not AI visibility)?"
    return m.msg_type == 'code' and bool(mk_cell(m.content).directives.keys() & _hidden)

def is_echo(m:Msg) -> bool:
    "Does message have an echo directive that isn't false?"
    if m.msg_type != 'code': return False
    d = {k:v for k,v in mk_cell(m.content).directives.items() if k in _echo}
    return bool(d) and all('false' not in v for v in d.values())

def is_header(m:Msg) -> bool:
    "Does note message content start by a markdown header?"
    return m.msg_type == 'note' and m.content.startswith('#')

def is_skipped(m:Msg) -> bool: return bool(m.get('skipped'))

# %% ../nbs/01_dialog.ipynb #4c78172c
def is_msg_(msg, param='exported', **kwargs) -> bool:
    "Check message has property selected by `param`."
    assert param in {'exported','hidden','echo','header','skipped'}
    return dict(exported=is_exported, hidden=is_hidden, echo=is_echo, header=is_header, skipped=is_skipped)[param](msg, **kwargs)

# %% ../nbs/01_dialog.ipynb #953d3651
@patch(as_prop=True)
def exported_x(self:MsgX) -> bool: return is_exported(self)
@patch(as_prop=True)
def hidden_x(self:MsgX) -> bool: return is_hidden(self)
@patch(as_prop=True)
def echo_x(self:MsgX) -> bool: return is_echo(self)
@patch(as_prop=True)
def header_x(self:MsgX) -> bool: return is_header(self)

# %% ../nbs/01_dialog.ipynb #447130b0
async def get_msg_id():
    "Get current message id."
    return (await read_msg(0)).id

# %% ../nbs/01_dialog.ipynb #096bafac
@delegates(read_msg)
async def get_output(id:str=None, **kwargs) -> str:
    "Return rendered output for message `id` or the current message."
    msg = await read_msg(0, id=id, **kwargs)
    return msg.output

# %% ../nbs/01_dialog.ipynb #a42b6587
_format = get_ipython().display_formatter.format if in_dialog() else None

# %% ../nbs/01_dialog.ipynb #abcf61d2
_format = get_ipython().display_formatter.format if in_dialog() else None

# %% ../nbs/01_dialog.ipynb #233bc0e2
@delegates(_format)
def format_output(o, **kwargs):
  d, md = _format(o, **kwargs) if _format else ('', {})
  return json.dumps([{"data": d, "metadata": md, "output_type": "display_data"}])

# %% ../nbs/01_dialog.ipynb #b85dd3ed
_fence_re = re.compile(r' {0,3}(?:`{3,}|~{3,})')

def _expand_block(b):
    "Return `(content, msg_type)` for block `b`, or `None` for an empty fence."
    if b.type != 'code_block' or not _fence_re.match(b._src): return b._src, 'note'
    if not (src := b.text.rstrip('\r\n')).strip(): return
    if b.lang == 'python': return src, 'code'
    return (f'%%{b.lang}\n{src}' if b.lang else src), 'raw'

# %% ../nbs/01_dialog.ipynb #952f6ed5
def _usage_block(b):
    "Is `b` a JSON usage fence?"
    return b.type == 'code_block' and b.lang == 'json' and bool(re.search(r'(?<![\w-])\.usage(?![\w-])', b.get('info', '')))

# %% ../nbs/01_dialog.ipynb #3f4ef633
def _expand_blocks(md, all_blocks=True, usage=False):
    "Return `(content, msg_type)` pairs from rendered Markdown."
    res = []
    for src in split_md_blocks(md, all_blocks=all_blocks):
        bs = _text_blocks(src)
        if len(bs) == 1 and not usage and _usage_block(bs[0]): continue
        expanded = _expand_block(bs[0]) if len(bs) == 1 else (src.rstrip('\r\n'), 'note')
        if expanded is not None: res.append(expanded)
    return res

# %% ../nbs/01_dialog.ipynb #523b23b0
@delegates(_expand_blocks)
async def expand(id:str=None, dname:str='', before:str|None=None, **kwargs):
    "Expand a message's rendered output into messages and return their ids."
    msg = await read_msg(-1 if id is None else 0, id=id, dname=dname)
    anchor,placement = (msg.id, 'add_after') if before is None else (before, 'add_before')
    ids = []
    for content,msg_type in _expand_blocks(msg.get('output') or '', **kwargs):
        anchor = await add_msg(content, msg_type=msg_type, placement=placement, id=anchor, dname=dname)
        ids.append(anchor)
        placement = 'add_after'
    return ids

@delegates(expand)
async def expand_replace(id:str=None, dname:str='', before:str|None=None, template='Expanded into {}.', **kwargs):
    "Expand rendered output and replace prompt output with links to the new messages."
    msg = await read_msg(-1 if id is None else 0, id=id, dname=dname)
    ids = await expand(msg.id, dname=dname, before=before, **kwargs)
    if msg.msg_type == 'prompt':
        links = ' · '.join(f'#_{o}' for o in ids)
        await update_msg(msg.id, dname=dname, output=template.format(links))
    return ids

# %% ../nbs/01_dialog.ipynb #65ab1d8a
def nb_path(dname:str=''):
    "Return filesystem `.ipynb` path backing dialog `dname`."
    dname = find_dname() if not dname else find_dname(dname)
    return (Path.home()/dname.removeprefix('/')).with_suffix('.ipynb')

# %% ../nbs/01_dialog.ipynb #7419f2b9
_exp_pat =r'^\s*#\s*\|\s*default_exp\s+(\w+)'
async def dlg_module(dname:str='', solo_nb:bool=False):
    "Return nbdev module name for `dname`, or its notebook stem for solo/non-nbdev dialogs."
    from nbdev.config import is_nbdev
    if not is_nbdev(p := nb_path(dname)) or solo_nb: return p.stem
    msgs = await find_msgs(_exp_pat, dname=(dname or find_dname()), context=0, limit=1, include_output=False, include_meta=False)
    if msgs: return msgs[0].content.strip().split()[-1]

# %% ../nbs/01_dialog.ipynb #0872c7b7
async def dlg_export(
    dname:str='', # Dialog name: '' for current; otherwise dialoghelper-relative or /-root-relative; omit `.ipynb`
    solo_nb:bool=False # Export as standalone `.py` beside the notebook instead of using the nbdev project module path?
):
    "Export dialog to Python and return whether its generated module exists; non-nbdev dialogs export standalone automatically."
    from nbdev.export import nb_export
    from nbdev.config import get_config, is_nbdev
    p = nb_path(dname)
    if not (_is := is_nbdev(p)): solo_nb = True
    mod = await dlg_module(dname, solo_nb=solo_nb)
    lib_path = p.parent if solo_nb else get_config(p).lib_path if _is else Path('.')
    if solo_nb: nb_export(p, lib_path=lib_path, name=mod, solo_nb=solo_nb)
    else: nb_export(p)
    return (lib_path/f"{mod}.py").exists()

# %% ../nbs/01_dialog.ipynb #d11979a8
def get_dialog_link(
    path:str # Path to dialog (e.g. '/aai-ws/dialoghelper/nbs/00_core')
) -> str:
    "Return an HTML link to open a dialog in Solveit."
    from dialoghelper.core import dialog_link
    return dialog_link(path).data

# %% ../nbs/01_dialog.ipynb #e7525b46
def empty_dialog_nb() -> str:
    "Return a minimal dialog notebook json"
    return '''
{
"cells": [],
"metadata": {
"solveit_dialog_mode": "learning",
"solveit_ver": 2
},
"nbformat": 4,
"nbformat_minor": 5
}
'''

# %% ../nbs/01_dialog.ipynb #3b99a030
async def heading_msgs(dname=''):
    "Return `(id, level, title, summary)` records for heading notes in dialog order."
    msgs = await find_msgs(_ATX_hdr_pat, msg_type='note', include_output=False, context=0, dname=dname)
    return [(o.id, len(s:=o.content.splitlines()[0])-len(s.lstrip('#')), s.lstrip('#').lstrip(), first_sent(o.content, allow_blockquote=True)) for o in msgs]

# %% ../nbs/01_dialog.ipynb #268eafea
def fmt_sections(secs, template='{indent}**{title}** — {sent} #_{id}'):
    "Render heading records as an indented Markdown outline with message links."
    return '\n\n'.join(template.format(id=id, level=lvl, title=title, sent=sent or '', indent='&nbsp;'*4*(lvl-1)) for id,lvl,title,sent in secs)

# %% ../nbs/01_dialog.ipynb #31ed145d
def details_sections(secs, open=False):
    "Render heading records as a nested collapsible HTML section tree."
    root = []
    stack = [(0,root)]
    for id,lvl,title,sent in secs:
        node = [id,title,sent,[]]
        while stack[-1][0] >= lvl: stack.pop()
        stack[-1][1].append(node)
        stack.append((lvl,node[3]))
    def fmt(nodes, lvl=1):
        return Ul(*[
            Li(Details(open=open and lvl==1, cls='json')(
                Summary(A(title, href=f'#_{id}')),
                *([P(sent)] if sent else []),
                *([fmt(kids, lvl+1)] if kids else [])
            ))
            for id,title,sent,kids in nodes
        ])
    return fmt(root)

# %% ../nbs/01_dialog.ipynb #81a301e3
def _is_docstring(n): return isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)

def _reindent(src, n): return '\n'.join(' '*n + l for l in src.splitlines())

def _postprocess(s):
    "Collapse triple+ blank lines and hoist lone `...` body onto the signature line"
    s = re.sub(r'\n{3,}', '\n\n', s)
    return re.sub(r':\n[ \t]+\.\.\.', ': ...', s)

_compound_types = ast.If,ast.For,ast.While,ast.With,ast.Try,ast.TryStar,ast.Match

# %% ../nbs/01_dialog.ipynb #2e4f5500
def _strip_private(tree):
    "Remove private (underscore-prefixed) top-level nodes and class methods from `tree` in-place"
    is_priv = lambda n: getattr(n, 'name', '').startswith('_')
    tree.body = [n for n in tree.body if not is_priv(n)]
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            node.body = [n for n in node.body if not is_priv(n)]
    return tree

# %% ../nbs/01_dialog.ipynb #86befa71
def stub_fn(atok, fn, level=1):
    "Return stubbed source for function `fn` at disclosure `level`"
    if level == 3: return atok.get_text(fn)
    start_line = fn.decorator_list[0].lineno if fn.decorator_list else fn.lineno
    body_start = fn.body[0].lineno - start_line
    if level == 1 or body_start == 0:
        n = copy.deepcopy(fn)
        n.body = [ast.Expr(ast.Constant(...))]
        return _reindent(ast.unparse(n), fn.col_offset)
    indent = ' ' * fn.body[0].col_offset
    lines = atok.get_text(fn).splitlines()
    if _is_docstring(fn.body[0]):
        doc_end = fn.body[0].end_lineno - start_line + 1
        return '\n'.join(lines[:body_start] + lines[body_start:doc_end] + [f'{indent}...'])
    return '\n'.join(lines[:body_start] + [f'{indent}...'])

# %% ../nbs/01_dialog.ipynb #0ccc3c61
def _class_chunk(atok, node, level):
    "Return disclosed source for class `node` at `level`"
    if level == 3: return atok.get_text(node)
    start_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
    body_start = node.body[0].lineno - start_line
    if body_start == 0: return atok.get_text(node)
    lines = atok.get_text(node).splitlines()
    hdr = '\n'.join(lines[:body_start])
    body = []
    for i,n in enumerate(node.body):
        if isinstance(n, functypes): body.append(stub_fn(atok, n, level))
        elif isinstance(n, ast.Expr):
            if i == 0 and _is_docstring(n) and level >= 2: body.append(' '*n.col_offset + atok.get_text(n))
        else: body.append(' '*n.col_offset + atok.get_text(n))
    return hdr + '\n' + '\n'.join(body)

def _compound_chunk(atok, node, level):
    "Return disclosed source for compound statement `node` at `level`"
    if level == 3: return atok.get_text(node)
    text = atok.get_text(node)
    fns = sorted([n for n in ast.walk(node) if n is not node and isinstance(n, (*functypes, ast.ClassDef))],
                 key=lambda n: (n.lineno, n.col_offset), reverse=True)
    for n in fns:
        stub = stub_fn(atok, n, level) if isinstance(n, functypes) else _class_chunk(atok, n, level)
        lines = stub.splitlines()
        if lines[0].startswith(' ' * n.col_offset): lines[0] = lines[0][n.col_offset:]
        text = text.replace(atok.get_text(n), '\n'.join(lines), 1)
    return text

# %% ../nbs/01_dialog.ipynb #d27baedb
def disclose(src:str, level=1, strip_private=False) -> str:
    "Return valid Python disclosed at level 1=sigs, 2=sigs+docs+docments, or 3=full source."
    if not src.strip(): return ''
    try:
        atok = asttokens.ASTTokens(src, parse=True)
        if strip_private: _strip_private(atok.tree)
        chunks = []
        for i,node in enumerate(atok.tree.body):
            if isinstance(node, functypes): chunks.append(stub_fn(atok, node, level))
            elif isinstance(node, ast.ClassDef): chunks.append(_class_chunk(atok, node, level))
            elif isinstance(node, _compound_types): chunks.append(_compound_chunk(atok, node, level))
            elif isinstance(node, ast.Expr) and not (i == 0 and _is_docstring(node) and level >= 2): pass
            elif isinstance(node, (ast.Import, ast.ImportFrom)) and level == 1: pass
            else: chunks.append(atok.get_text(node))
        return _postprocess('\n\n'.join(chunks))
    except SyntaxError as e:
        warnings.warn(f'Syntax error in source, returning raw: {e}')
        return src

# %% ../nbs/01_dialog.ipynb #20fca012
_include_filter = dict(
    exported=lambda m: is_exported(m),
    echo=lambda m: is_exported(m) or is_echo(m),
    all=lambda m: True)

def _compact(s): return re.sub(r'\n{2,}', '\n', s).strip()

def _xml_cell(content, **attrs):
    attr_str = ''.join(f' {k}="{v}"' for k,v in attrs.items())
    return f'<cell{attr_str}>{content}</cell>'

# %% ../nbs/01_dialog.ipynb #62e97602
async def dialog_code(dname='', include='all'):
    "Return list of (id, source) tuples for code cells filtered by `include`"
    msgs = await find_msgs_x(dname=dname, msg_type='code', include_output=False)
    return [(m.id, m.content) for m in msgs if _include_filter[include](m)]

# %% ../nbs/01_dialog.ipynb #ff8e4558
def _disclose_srcs(srcs, level=1, strip_private=False, fmt='text', dname=''):
    "Disclose list of (id, source) tuples at `level`"
    chunks = [(mid, disclose(src, level, strip_private)) for mid,src in srcs]
    if fmt == 'xml':
        cells = '\n'.join(_xml_cell(escape(src), id=mid) for mid,src in chunks)
        return f'<dialog level="{level}" path="{dname or "."}">\n{cells}\n</dialog>'
    if fmt == 'json':
        cells = [dict(id=mid, source=src) for mid,src in chunks]
        return json.dumps(dict(level=level, path=dname or '.', cells=cells), indent=2)
    return _compact('\n\n'.join(src for _,src in chunks))

async def disclose_dialog(dname='', level=1, include='all', strip_private=False, fmt='text'):
    "Return disclosed code cells from dialog `dname` in text, XML, or JSON."
    srcs = await dialog_code(dname=dname, include=include)
    return _disclose_srcs(srcs, level=level, strip_private=strip_private, fmt=fmt, dname=dname)

def disclose_nb(path, level=1, strip_private=False, fmt='text'):
    "Return disclosed code cells from notebook `path` in text, XML, or JSON."
    nb = json.loads(Path(path).read_text())
    srcs = [(c.get('id',''), c['source'] if isinstance(c['source'], str) else ''.join(c['source']))
            for c in nb['cells'] if c['cell_type'] == 'code']
    return _disclose_srcs(srcs, level=level, strip_private=strip_private, fmt=fmt, dname=str(path))

# %% ../nbs/01_dialog.ipynb #643a905d
_pmark = '**🤖Reply🤖**<!-- SOLVEIT_SEPARATOR_7f3a9b2c -->\n'

# %% ../nbs/01_dialog.ipynb #d2685927
def _mk_tag(m, mtyp, ids):
    # parts = ([f'#{m.id}'] if ids else []) + [mtyp] + (['echo'] if echo else []) + (['skipped'] if m.skipped else []) + (['pinned'] if m.pinned else [])
    parts = ([f'#{m.id}'] if ids else []) + [mtyp]
    return ' '.join(parts)

# %% ../nbs/01_dialog.ipynb #d2bc045a
def output2md(c, langid='output'):
    return f'''```{langid}\n{c}\n```''' if c else '' 

# %% ../nbs/01_dialog.ipynb #ff4409be
def strip_directives(c): return ('\n'.join(l for l in c.splitlines() if not l.startswith('#|'))).strip()

# %% ../nbs/01_dialog.ipynb #9ba03aa3
_striptag_pats = (
    re.compile(r'^#\|\W*\w+: \w+\W*$\n?', re.MULTILINE),
    re.compile(r'^<!-- \w+: \w+ -->\s*\n?', re.MULTILINE))

def strip_tags(c):
    for pat in _striptag_pats: c = pat.sub('', c)
    return c.strip()

# %% ../nbs/01_dialog.ipynb #24b7596b
def _xml_msg(m:MsgX, ids, output, hdr_clamp):
    mtyp = m.msg_type
    c, attrs = '', (f' id="{m.id}"' if ids else '') + f' type="{mtyp}"'
    match mtyp:
        case 'note':
            clamp = not m.exported_x and m.header_x
            c = escape(strip_tags(clamp_note(m.content, hdr_clamp) if clamp else m.content))
            if c: c = f'<content>{c}</content>'
        case 'code':
            src = escape(strip_directives(m.content))
            out = f'\n  <output>{escape(m.output)}</output>' if output and m.output else ''
            if src or out: c = f'\n  <source>{src}</source>{out}\n'
        case 'prompt':
            p = escape(strip_tags(strip_directives(m.content)))
            r = f'\n  <response>{escape(m.output)}</response>' if m.output else ''
            if p or r: c = f'<prompt>{p}</prompt>{r}'
        case 'raw':
            c = escape(strip_tags(strip_directives(m.content)))
            if c: c = f'<msg{attrs}><content>{c}</content></msg>'
    return f'<msg{attrs}>{c}</msg>' if c else ''

# %% ../nbs/01_dialog.ipynb #d183b554
def _md_msg(m, ids, output, hdr_clamp):
    mtyp, c = m.msg_type, None
    match mtyp:
        case 'note':
            clamp = not m.exported_x and m.header_x
            c = strip_tags(clamp_note(m.content, hdr_clamp) if clamp else m.content)
        case 'code':
            c = f'```python\n{strip_directives(m.content)}\n```'
            if output and m.output: c += f'\n{output2md(m.output)}'
        case 'prompt':
            c = strip_tags(strip_directives(m.content))
            if output and m.output: c += f'\n{output2md(m.output, 'response')}'
        case 'raw': c = strip_tags(strip_directives(m.content))
    return f'<!-- {_mk_tag(m, mtyp, ids)} -->\n{c}\n' if c else ''

# %% ../nbs/01_dialog.ipynb #39d5c5d5
def _json_msg(m, expd, echo, ids, output, hdr_clamp):
    mtyp = m.msg_type
    d = dict(type=mtyp)
    if ids: d['id'] = m.id
    match mtyp:
        case 'note':
            clamp = not m.exported_x and m.header_x
            d['content'] = strip_tags(clamp_note(m.content, hdr_clamp) if clamp else m.content)
        case 'code':
            d['source'] = strip_directives(m.content)
            if output and m.output: d['output'] = m.output
        case 'prompt':
            d['prompt'] = strip_tags(strip_directives(m.content))
            d['response'] = m.output
        case 'raw': d['content'] = strip_tags(strip_directives(m.content))
    return d

# %% ../nbs/01_dialog.ipynb #1fe5afdb
_convs = dict(
    xml="msg elements have id and type attributes; source/output are child elements of code msgs; prompt/response are child elements of prompt msgs",
    json="msgs is a list of objects with type and id fields; code objects have source and output fields; prompt objects have prompt and response fields; others have content",
    md="<!-- #<msg_id> <msg_type> --> precedes each block; ```output blocks contain cell output; ```response blocks contain model response")

# %% ../nbs/01_dialog.ipynb #c02cd206
def mk_frontmatter(path='', description='', n_msgs=0, n_exported=0, fmt='xml'):
    from datetime import datetime, timezone
    return ("---\n"
"digest: solveit-dialog\n"
f"path: {path}\n"
f"exported_at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
f"description: {description!r}\n"
f"stats: {{total: {n_msgs}, exported: {n_exported}}}\n"
f"conventions: '{_convs[fmt]}'\n"
"---\n"
)

# %% ../nbs/01_dialog.ipynb #37710188
def exportmsgs(
    msgs:list[Msg],
    hdr_clamp='header+',  # header level
    output=True,  # include code messages output
    ids=True,  # include message ids in cell comments
    frontmatter:dict=None,  # if present, call `mk_frontmatter` with this dict as args
    fmt='xml',  # 'xml'|'md'|'json'
):
    "Serialize selected messages as an XML, Markdown, or JSON dialog digest."
    fn = {'xml': _xml_msg, 'md': _md_msg, 'json': _json_msg}[fmt]
    parts = [p for m in msgs if (p := fn(m, ids, output, hdr_clamp))]
    if fmt == 'json': res = json.dumps({'msgs': parts}, indent=2)
    else:
        body = '\n'.join(parts)
        res = f'<digest>\n{body}\n</digest>' if fmt=='xml' else body
    if frontmatter:
        frontmatter.update(n_exported=len(parts))
        fm = mk_frontmatter(**frontmatter)
    return f"{fm}\n{res}" if frontmatter else res

# %% ../nbs/01_dialog.ipynb #7800f21f
_meta_fns = dict(exported=is_exported, echo=is_echo, header=is_header, hidden=is_hidden, skipped=is_skipped)

# %% ../nbs/01_dialog.ipynb #391e0eb6
async def get_section(heading:str, msgs:list[MsgX]=None, dname='') -> list[MsgX]:
    "Return messages in section whose header matches heading"
    if not msgs: return await find_msgs_x(header_section=heading, include_skipped=True, dname=dname)
    lvl = len(re.match(r'^(#+)', heading)[1])
    for i,m in enumerate(msgs):
        c = strip_directives(m.content) if m.msg_type == 'note' else ''
        if not c.startswith(heading): continue
        res = [m]
        for m2 in msgs[i+1:]:
            c2 = strip_directives(m2.content) if m2.msg_type == 'note' else ''
            hs = re.match(r'^(#+)', c2)
            if hs and len(hs[1]) <= lvl: break
            res.append(m2)
        return res
    return []

# %% ../nbs/01_dialog.ipynb #c1f52e60
def _parse_terms(v):
    terms = ([v] if isinstance(v, str) else v) or []
    return [t for t in terms if not t.startswith('!')], [t[1:] for t in terms if t.startswith('!')]

# %% ../nbs/01_dialog.ipynb #67824193
def _content_match(m, pat, use_case, use_regex):
    flags = (re.DOTALL|re.MULTILINE)|(0 if use_case else re.IGNORECASE)
    return bool(re.search(pat, m.content, flags) if use_regex else (pat in m.content if use_case else pat.lower() in m.content.lower()))

# %% ../nbs/01_dialog.ipynb #00ff0767
def _header_content(m): return strip_directives(m.content) if m.msg_type == 'note' else ''

def _header_level(m):
    c = _header_content(m)
    return len(re.match(r'^(#+)', c)[1]) if c.startswith('#') else 0

# %% ../nbs/01_dialog.ipynb #56979fd2
def section_map(msgs):
    "Return dict mapping full header line -> list of msg ids in that section (inclusive of header)"
    res,cur_hdrs = {},[]
    for m in msgs:
        lvl = _header_level(m)
        if lvl:
            cur_hdrs = [(l,h) for l,h in cur_hdrs if l < lvl]
            hdr = _header_content(m).splitlines()[0]
            cur_hdrs.append((lvl, hdr))
        for _,h in cur_hdrs: res.setdefault(h, []).append(m.id)
    return res

# %% ../nbs/01_dialog.ipynb #16a9f89d
def _resolve_sections(msgs, patterns):
    "Return set of msg ids matching any of the section patterns (supports regex via section_map)"
    sm = section_map(msgs)
    ids = set()
    for p in patterns:
        for k, v in sm.items():
            if re.fullmatch(p, k, re.IGNORECASE): ids |= set(v)
    return ids

# %% ../nbs/01_dialog.ipynb #073fd07f
async def filter_msgs_v1(
    msgs:list[Msg]=None,
    ids:str|list=None,
    section:str|list=None,
    msg_type:str|list=None,
    metadata:str|list=None,
    re_pattern:str='',
    use_case:bool=False,
    use_regex:bool=True,
    dname:str='',
) -> list[MsgX]:
    "Filter messages with union semantics and ! negation; result in dialog order."
    if not any([ids, section, msg_type, metadata, re_pattern]): return []
    msgs = msgs or await find_msgs_x(include_skipped=True, dname=dname)
    ids_l = ([ids] if isinstance(ids, str) else ids) or []
    sec_pos, sec_neg = _parse_terms(section)
    mt_pos, mt_neg = _parse_terms(msg_type)
    md_pos, md_neg = _parse_terms(metadata)
    pat_pos, pat_neg = (re_pattern[1:], True) if re_pattern.startswith('!') else (re_pattern, False)
    has_pos = any([ids_l, sec_pos, mt_pos, md_pos, (pat_pos and not pat_neg)])
    pos = set(ids_l)
    pos |= _resolve_sections(msgs, sec_pos)
    if mt_pos: pos |= {m.id for m in msgs if m.msg_type in mt_pos}
    if md_pos: pos |= {m.id for m in msgs if any(_meta_fns[k](m) for k in md_pos)}
    if pat_pos and not pat_neg: pos |= {m.id for m in msgs if _content_match(m, pat_pos, use_case, use_regex)}
    neg = set()
    neg |= _resolve_sections(msgs, sec_neg)
    if mt_neg: neg |= {m.id for m in msgs if m.msg_type in mt_neg}
    if md_neg: neg |= {m.id for m in msgs if any(_meta_fns[k](m) for k in md_neg)}
    if pat_neg: neg |= {m.id for m in msgs if _content_match(m, pat_pos, use_case, use_regex)}
    base = pos if has_pos else {m.id for m in msgs}
    return [m for m in msgs if m.id in base - neg]

# %% ../nbs/01_dialog.ipynb #9899a2d5
def _scope_msgs(msgs, ids, section):
    "Narrow msgs to those matching ids and/or section patterns."
    if ids is None and not section: return msgs
    scoped = set()
    if ids is not None: scoped |= {ids} if isinstance(ids, str) else set(ids)
    if section:
        secs = [section] if isinstance(section, str) else section
        scoped |= _resolve_sections(msgs, secs)
    return [m for m in msgs if m.id in scoped]

# %% ../nbs/01_dialog.ipynb #db9f095e
def _filter_pos_neg(msgs, msg_type=None, metadata=None, re_pattern='', use_case=False, use_regex=True):
    "Apply union+negation filter to msgs. If no positive terms, return msgs as-is."
    mt_pos, mt_neg = _parse_terms(msg_type)
    md_pos, md_neg = _parse_terms(metadata)
    pat_pos, pat_neg = (re_pattern[1:], True) if re_pattern.startswith('!') else (re_pattern, False)
    has_pos = any([mt_pos, md_pos, pat_pos and not pat_neg])
    if not has_pos and not any([mt_neg, md_neg, pat_neg]): return msgs
    pos = set()
    if mt_pos: pos |= {m.id for m in msgs if m.msg_type in mt_pos}
    if md_pos: pos |= {m.id for m in msgs if any(_meta_fns[k](m) for k in md_pos)}
    if pat_pos and not pat_neg: pos |= {m.id for m in msgs if _content_match(m, pat_pos, use_case, use_regex)}
    neg = set()
    if mt_neg: neg |= {m.id for m in msgs if m.msg_type in mt_neg}
    if md_neg: neg |= {m.id for m in msgs if any(_meta_fns[k](m) for k in md_neg)}
    if pat_neg: neg |= {m.id for m in msgs if _content_match(m, pat_pos, use_case, use_regex)}
    base = pos if has_pos else {m.id for m in msgs}
    return [m for m in msgs if m.id in base - neg]

# %% ../nbs/01_dialog.ipynb #ad25c0ee
async def filter_msgs_v2(
    msgs:list[Msg]=None, # List of messages to filter or None to use all messages.
    ids:str|list=None, # Message ids to include (union with section).
    section:str|list=None, # Section patterns to include (union with ids).
    msg_type:str|list=None, # Message types to include.
    metadata:str|list=None, # Metadata keys to to filter on ('exported', 'echo', 'header', 'hidden').
    re_pattern:str='', # Optional regex to search for (re.DOTALL+re.MULTILINE is used).
    use_case:bool=False, # Use case-sensitive matching?
    use_regex:bool=True, # Use regex matching?
    dname:str='', # Dialog to get messages for; defaults to current dialog.
) -> list[MsgX]:
    "Scope by ids/sections, then union-filter by type, metadata, or content with `!` negation."
    if not any([ids is not None, section, msg_type, metadata, re_pattern]): return []
    msgs = msgs or await find_msgs_x(include_skipped=True, dname=dname)
    return _filter_pos_neg(_scope_msgs(msgs, ids, section), msg_type, metadata, re_pattern, use_case, use_regex)

# %% ../nbs/01_dialog.ipynb #e53fbfb6
def disclose_msgs(msgs:list[MsgX], note_level='header++', code_level=2, output=False) -> list[MsgX]:
    "Return copied messages with deterministically disclosed notes, code, and outputs."
    return [disclose_msg(m, note_level=note_level, code_level=code_level, output=output) for m in msgs]

# %% ../nbs/01_dialog.ipynb #74c4f9f0
_profiles = dict(
    discovery=dict(note_level='header', code_level=1, output=False), 
    compact=dict(note_level='header++', code_level=1, output=False), 
    handoff=dict(note_level='header++', code_level=2, output=False), 
    reuse=dict(note_level='header+', code_level=3, output=False), 
    archive=dict(note_level='full', code_level='full', output=True)
)

# %% ../nbs/01_dialog.ipynb #006ff5fb
def disclosure_kwargs(profile='handoff', **kwargs):
    "Return disclosure kwargs for `profile`."
    return {**_profiles[profile], **kwargs}

def disclose_profile(msgs:list[MsgX], profile='handoff', **kwargs) -> list[MsgX]:
    "Return disclosed copies of `msgs` using a named profile."
    return disclose_msgs(msgs, **disclosure_kwargs(profile, **kwargs))

# %% ../nbs/01_dialog.ipynb #85851a0b
def exportmsgs_profile(msgs:list[MsgX], profile='handoff', fmt='md', ids=True, frontmatter=None, **kwargs):
    "Export messages after applying a disclosure profile."
    kw = disclosure_kwargs(profile, **kwargs)
    if frontmatter is not None: frontmatter = {**frontmatter, 'profile':profile, 'disclosure':kw}
    return exportmsgs(disclose_msgs(msgs, **kw), hdr_clamp='full', output=kw['output'], ids=ids, frontmatter=frontmatter, fmt=fmt)

# %% ../nbs/01_dialog.ipynb #e9d7f92d
_digest_plans,_digest_seq = {},0

def _new_digest_id():
    global _digest_seq
    _digest_seq += 1
    return f'dg_{_digest_seq:03d}'

# %% ../nbs/01_dialog.ipynb #56637fcd
def _chunk_tok(c, profile='discovery'): return c.tokens.get(profile, c.tokens[min(c.tokens, key=c.tokens.get)]) if isinstance(c.tokens, dict) else c.tokens
def _chunk_title(c, i): return c.title or f'chunk {i}'

# %% ../nbs/01_dialog.ipynb #ed3bb29b
def disclose_msg(m:MsgX, note_level='header++', code_level=2, output=False) -> MsgX:
    "Return a disclosed copy of message `m`."
    res = msgx(AD(m.copy()))
    if res.msg_type == 'note' and note_level != 'full':
        res.content = clamp_note(res.content, note_level) or clamp_note(res.content, 'header')
    if res.msg_type == 'code' and code_level != 'full':
        res.content = disclose(strip_directives(res.content), code_level) or '...'
    if not output: res.output = ''
    return res

# %% ../nbs/01_dialog.ipynb #da3423b5
def _over_chunk_txt(p, i, profile):
    c,toks = p.chunks[i],_chunk_tok(p.chunks[i], profile)
    return '\n'.join([
        f'DIGEST CHUNK OVER BUDGET {p.id}',
        f'chunk: {i}',
        f'title: {_chunk_title(c, i)}',
        f'budget: {p.budget}',
        f'tokens: {toks}',
        f'profile: {profile}',
        f'force: digest_chunk({p.id!r}, {i}, profile={profile!r}, force=True)'])

def digest_chunk(digest_id, i, profile='discovery', fmt='md', force=False, **kwargs):
    "Return rendered chunk `i` from stored digest plan."
    p = _digest_plans[digest_id]
    if not force and _chunk_tok(p.chunks[i], profile) > p.budget: return _over_chunk_txt(p, i, profile)
    c = p.chunks[i]
    fm = dict(path=getattr(p, 'path', ''), description=f'{p.id} chunk {i}: {_chunk_title(c, i)}', n_msgs=len(c.msgs), fmt=fmt)
    return exportmsgs_profile(c.msgs, profile, fmt=fmt, frontmatter=fm, **kwargs)

# %% ../nbs/01_dialog.ipynb #c15da14e
def _r(m:dict, **kwargs):
    "Add kwargs to m and filter out key/value not compatible with add_msg or update_msg"
    if kwargs: m.update(kwargs)
    if m.msg_type == 'code': m.output = ''
    return dict(content=m.content, msg_type=m.msg_type, output=m.output, is_exported=m.is_exported, skipped=m.skipped, pinned=m.pinned, i_collapsed=m.i_collapsed, o_collapsed=m.o_collapsed, heading_collapsed=m.heading_collapsed)

# %% ../nbs/01_dialog.ipynb #45e21daf
def find_symbol_msg(msgs, sym:str) -> dict|None:
    "Find last message in msgs list containing symbol definition (module level)"
    for m in reversed(msgs):
        if m.msg_type != 'code': continue
        root = ast_py(m.content)
        for node in root.find_all(pattern='def $FUNC($$$)'):
            if node.field('name').text() == sym: return m
        for node in root.find_all(pattern='class $CLASS'):
            if node.field('name').text() == sym: return m
        for node in root.find_all(pattern='$VAR = $$$'):
            if node.field('left').text() == sym: return m
    return None

# %% ../nbs/01_dialog.ipynb #10fdfa3c
async def importdlg(
    dname:str='',  # dialog to import from; relative to solveit root (if starts with /) or current dialog; empty string for current dialog
    syms:list[str]=None,  # symbol names to import (finds last def/class/assignment); if provided, regex is ignored
    ids:list[str]=None,  # message ids to import; can combine with syms; if syms or ids provided, regex is ignored
    re_include:str=None,  # regex to filter messages (content+output); only used if no syms/ids; uses re.MULTILINE|re.DOTALL
    re_exclude:str=None,  # regex to exclude from re_include results; only used if no syms/ids
    run:bool=False,  # run imported messages after insertion
    header:bool=False,  # wrap imports in collapsed header with dialog name
    heading_collapsed:bool=False  # collapse the header after creation
):
    "Copy selected source-dialog messages below the current message in original order."
    msgs, to_import = await find_msgs(dname=dname, include_meta=True, include_output=True), []
    if not dname: msgs = msgs[:await msg_idx()]
    if syms or ids:
        id2idx, seen = {m.id:i for i,m in enumerate(msgs)}, set()
        if syms:
            for sym in syms:
                if (m := find_symbol_msg(msgs, sym)) and m.id not in seen: to_import.append(m); seen.add(m.id)
        if ids:
            for m in msgs:
                if m.id in ids and m.id not in seen: to_import.append(m); seen.add(m.id)
        to_import.sort(key=lambda m: id2idx[m.id])
    else:
        to_import = msgs
        if re_include: to_import = [m for m in to_import if re.search(re_include, m.content + m.output, re.MULTILINE | re.DOTALL)]
        if re_exclude: to_import = [m for m in to_import if not re.search(re_exclude, m.content + m.output, re.MULTILINE | re.DOTALL)]
    new_ids = [await add_msg(**_r(m)) for m in to_import]
    if header and new_ids:
        hdrid = await add_msg(f"## Imported from {dname}", placement='add_before', id=new_ids[0])
        new_ids.insert(0, hdrid)
        new_ids.append(await add_msg("## ----", id=new_ids[-1]))
    if run and new_ids: await run_msg(','.join(new_ids))
    if heading_collapsed and header: await toggle_header(hdrid)
    return new_ids
