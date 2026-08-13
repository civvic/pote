"""Turn a working dialog into a usable pyskill. Improve its generated module and pyskill through small editorial changes, without requiring a refactor.

## Method: grow a useful pyskill from a working dialog

Treat a working dialog as the source of an evolving nbdev module. Curate its existing exports so another AI can understand and use what works now: exported markdown supplies orientation; exported code supplies the reusable API; local docstrings and tests establish important contracts.

Prefer small editorial improvements over refactoring.

## Required setup

The export and checking helpers require sandbox permission. Before using this pyskill, stop and establish the required permissions.

Ask the user to add and run:

```python
from pote.dlg2pyskill import *
```

Do not run that import yourself. Solveit requires the user to create and execute the code message.

For a review involving more than one export, also ask the user to create, run, and allow:

```python
import importlib
import xxx.yyy

def reloadskill(mod): return importlib.reload(importlib.import_module(mod))
allow(reloadskill)
```

Only after the user has run this helper may you call:

```python
reloadskill('xxx.yyy')
```

Replace `xxx.yyy` with the generated module name of the dialog under review.

## Fast path

1. **After required setup is complete**, export the target dialog with `await dlg_export()` for the current dialog or `await dlg_export(dname)`. `dname` follows `dialoghelper` conventions; omit `.ipynb`.
2. Reload the exported module, then run `doc(module)`. This shows the generated docstring and public API exactly as another AI will receive them.
3. Identify one local prose, export, docstring, or test improvement, then agree the exact change with the user.
4. Apply the agreed change. Run `await check_flakes(dname)`, fix any reported exported-code issues, then run `await dlg_export(dname)` again.
5. Repeat.

## Supporting helpers

This pyskill re-exports `dlg_export` and `count_tokens` from `pote.dialog`, and `check_flakes`/`show_flakes` from `pote.flakes`. Their signatures cover normal use here; read those source pyskills with `doc(pote.dialog)` or `doc(pote.flakes)` when you need their fuller behavior or constraints.

## Workflow

1. Inspect the generated module:
   - module docstring
   - `__all__`
   - imports
   - exported signatures/docments/docstrings
2. Infer the current capability groups from existing headings and exported helpers.
3. Identify only local improvements needed for a first-time reader to understand:
   - module purpose
   - section purpose
   - preferred/current APIs
   - key contracts and limitations
4. Suggest concise markdown notes or edits to existing notes.
5. Audit export decisions to prevent temporary or exploratory material leaking unintentionally into the module docstring or public API.
6. Identify missing or weak public docstrings/docments.
7. Identify a small number of missing documentation tests for non-obvious contracts.
8. Finish with a short checklist of proposed edits in dialog source order.

Work in small editorial loops: inspect the current proto-skill, agree one concrete local improvement, verify it, then continue. Do not edit until the user explicitly agrees to the exact change.

### 1. Read the generated module as a proto-pyskill

Export the dialog, then inspect the generated module’s:

- opening docstring
- `__all__`
- import block
- public function signatures and docstrings
- source-order flow

Ask:

> If I knew nothing but this generated module, what would I believe this module is for?

> Which capabilities look public and intentional?

> Does exploratory material unintentionally leak into the generated module docstring or public API?

> Which exported prose is useful orientation, and which is exploration history that would confuse a first-time reader?

> Which existing examples best teach another AI how to use the current generated module?

This reveals the current pyskill directly, without imposing an imagined design.

Assess the generated module as a proto-pyskill.

Answer briefly:

1. What is this module for, based only on its generated docstring and public API?
2. What are its main capability groups?
3. Which public helpers are likely starting points for common tasks?
4. Which exported prose is confusing, stale, or insufficiently contextualized?
5. Which APIs need a short status note because they are exploratory, superseded, or easy to misuse?
6. Which function docstrings or compact tests would most improve usability?
7. Does the module now provide enough truthful guidance for real-world AI use, even if its design is still evolving?

Do not demand a refactor. Prefer small prose, export, docstring, and test improvements grounded in the existing dialog.

### 2. Identify the dialog’s current capability groups

Make a brief map from existing headings and exported helpers. For example, group material by setup, inputs, core operations, results, and integrations.

These are conceptual groups, not necessarily separate public APIs. Their purpose is to give the generated docstring a readable path through the dialog.

These are capability groups, not all separate code APIs. The operational surface is deliberately narrow: `dlg_export()` builds the proto-skill, `check_flakes()` provides AI-readable diagnostics, and `show_flakes()` provides the optional human-facing report. The remaining groups are methodology carried by exported prose.

### 3. Improve the dialog’s explanatory flow

Use capability groups to review the current API, but place explanatory prose in the dialog where it helps: before material needing purpose or expectations; after exploration or tests to record what was established or remains limited; or between related material to explain a transition or decision.

Because exported prose remains in source order, each surgical note improves both the dialog’s reading flow and the corresponding point in the generated module docstring. Do not attach notes mechanically to headings or capability boundaries.

### 4. Curate exports deliberately

For every code message, decide only whether it belongs to the present public module:

- **Export** code that is useful, currently working, and intended for reuse.
- Keep internal helpers private when they are implementation detail.
- Keep experiments unexported unless they are intentionally part of the available API.
- Export dependencies needed by public helpers, including private helpers with `#| exporti` where appropriate; exporting code does not by itself make it public API.

For every prose message, decide whether it should contribute to the generated module docstring:

- export durable orientation, contracts, rationale, and known limitations
- avoid exporting temporary conversational remarks, obsolete plans, or duplicate explanations
- retain unexported exploration in the dialog when it remains useful evidence

The question is not “is this finished?” It is:

> Would exporting this make the current module easier or harder for another user or AI to understand?

### 5. Strengthen public docments and docstrings

For each exported helper, make its signature and docstring answer the local questions a caller needs:

- What does it return?
- What inputs select or modify behavior?
- What ordering, mutation, async, or state semantics matter?
- What failures or limitations should a caller expect?

Keep docstrings concise. Put longer rationale in the nearby markdown section note.

### 6. Curate useful examples

A small working example can explain a non-obvious contract more efficiently than prose. Look through the existing dialog for examples that demonstrate intended use, important sequencing, lifecycle, async behavior, or a surprising limitation.

Where an example would help another AI use the generated module, extract a compact version into a nearby exported note. Prefer examples already established by the dialog over invented demonstrations. Keep the example close to the prose or helper it clarifies.

Use executable tests when they are needed to establish correctness; use exported examples when they chiefly teach a caller how to use the current API.

### 7. Verify, but do not redesign in response to verification

After an agreed edit, run:

```python
await check_flakes(dname)
```

then:

```python
await dlg_export(dname)
```

Reload the generated module and inspect it again with `doc(module)`. If it gives a clear, truthful account of the current API, return to real-world use rather than redesigning pre-emptively.

The resulting pyskill need not be final. It is an accurate, navigable account of what works now—enough for users and AIs to exercise it and provide evidence for later refactoring.

Docs: https://civvic.github.io/pote/dlg2pyskill.html.md"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_dlg2pyskill.ipynb.

# %% auto #0
__all__ = ['check_flakes', 'show_flakes', 'dlg_export', 'count_tokens']

# %% ../nbs/01_dlg2pyskill.ipynb #5c7f7c5b
from dialoghelper.core import allow
from .flakes import show_flakes,check_flakes
from .dialog import dlg_export, count_tokens

# %% ../nbs/01_dlg2pyskill.ipynb #53e74164
_all_ = [check_flakes, show_flakes, dlg_export, count_tokens]

# %% ../nbs/01_dlg2pyskill.ipynb #f0f055cf
# Keep callable public helpers that require Solveit sandbox access in sync here.
allow(check_flakes, show_flakes, dlg_export)
