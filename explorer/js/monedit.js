"use strict";

const htmlTag = document.documentElement;
let ctrlKeys, KeyMod, KeyCode, mainKeys, scrollTimer;

const DARK_THEME = 'one-dark-pro';
const LIGHT_THEME = 'one-light';

const __FRANKEN__ = JSON.parse(localStorage.getItem("__FRANKEN__") || "{}");
if (__FRANKEN__.mode === "dark" ||
  (!__FRANKEN__.mode && window.matchMedia("(prefers-color-scheme: dark)").matches)
) htmlTag.classList.add("dark");
else htmlTag.classList.remove("dark");

htmlTag.classList.add(__FRANKEN__.theme || "uk-theme-blue");
htmlTag.classList.add(__FRANKEN__.radii || "uk-radii-md");
htmlTag.classList.add(__FRANKEN__.shadows || "uk-shadows-sm");
htmlTag.classList.add(__FRANKEN__.font || "uk-font-sm");

const theme = htmlTag.classList.contains('dark') ? DARK_THEME : LIGHT_THEME;

function preloadModels() {
  htmx.findAll('[data-muri]').forEach(m => {
    const uri = m.dataset.muri;
    const typ = uri.endsWith('1') ? 'content' : 'output';
    const value = m.parentElement.querySelector(`[name="${typ}"]`).value || '';
    monaco.editor.createModel(value, 'markdown', monaco.Uri.parse(uri));
  });
}

async function loadMonaco(enter_comp, vim) {
  if (vim) {
    //const { VimMode, initVimMode } = await import('https://esm.sh/monaco-vim@0.4.4?deps=monaco-editor');
    const { VimMode, initVimMode } = await import("https://cdn.jsdelivr.net/npm/monaco-vim@0.4.4/dist/index.mjs/+esm");


    VimMode.Vim.defineEx('wq_submit', 'wq', function() {
      document.activeElement.blur();
      handleClick('#submit_btn');
    });

    VimMode.Vim.defineEx('q_cancel', 'q', function() {
      window.editor?.trigger('keyboard', 'cancelEditor', {});
    });

    VimMode.Vim.map('<CR>', ':wq<CR>');

    window.initVimMode = initVimMode;
  }
  /*
  const res = await Promise.allSettled([
    // Using esm.sh over jsdelivr -> avoids safari console errors
    import('https://esm.sh/@monaco-editor/loader@1.7.0'),
    import('https://esm.sh/@shikijs/monaco@3.20.0?exports=shikiToMonaco'),
    import('https://esm.sh/shiki@3.13.0?exports=createHighlighter,createJavaScriptRegexEngine'),
  ]);
  */
  const res = await Promise.allSettled([
    import('https://cdn.jsdelivr.net/npm/@monaco-editor/loader@1.7.0/+esm'),
    import('https://cdn.jsdelivr.net/npm/@shikijs/monaco@3.20.0/+esm'),
    import('https://cdn.jsdelivr.net/npm/shiki@3.13.0/+esm'),
  ]);

  const [{ default: loader }, { shikiToMonaco }, { createHighlighter, createJavaScriptRegexEngine }] = res.map(r => r.status === 'fulfilled' ? r.value : null);

  await loader.init();
  KeyMod = monaco.KeyMod;
  KeyCode = monaco.KeyCode;
  ctrlKeys = (window.navigator.userAgent.includes('Mac') ? KeyMod.WinCtrl : KeyMod.CtrlCmd) | KeyMod.Shift;
  mainKeys = KeyMod.CtrlCmd | KeyMod.Shift;

  /* According to shiki docs (https://shiki.style/guide/regex-engines#javascript-regexp-engine) using the javascript regex engine over wasm is recommended in a browser environment for performance reasons. */
  const jsEngine = createJavaScriptRegexEngine()
  const highlighter = await createHighlighter({
    themes: [LIGHT_THEME, DARK_THEME],
    langs: ['python', 'markdown'],
    engine: jsEngine
  });

  shikiToMonaco(highlighter, monaco);
  monaco.editor.setTheme(theme);

  if (vim) {
    monaco.editor.addEditorAction({
      id: 'vimMode',
      label: 'Toggle Vim Mode',
      keybindings: [mainKeys | KeyCode.Backslash],
      contextMenuGroupId: '1_modification',
      run: (ed) => {
        if (!ed.vimMode) {
          ed.vimMode = initVimMode(ed, document.getElementById('vi-status'));
        } else {
          ed.vimMode.dispose();
          ed.vimMode = null;
        }
      }
    });
  }

  monaco.languages.registerCompletionItemProvider("python", {
    triggerCharacters: [".", "(", "[", "{", "@", ",", " ", "+", "-", "/", "*", "@", "%", "^"],
    provideCompletionItems: async (model, position) => {
      try {
        const dlg_name = document.getElementById('dlg_name')?.value;
        if (!dlg_name || !_copts().scon) return;
        const code = model.getValue();
        if (!code) return;
        const { lineNumber: line_no, column: col_no } = position;
        const body = JSON.stringify({ code, line_no, col_no, dlg_name });
        await new Promise(r => setTimeout(r, 400));
        const r = await fetch("/complete_", { method: "POST", body, headers: { "Content-Type": "application/json" }, priority: "low" });
        if (!r.ok) return;
        const { completions } = await r.json();
        if (!Array.isArray(completions) || !completions.length || !model.isAttachedToEditor()) return;
        return {
          suggestions: completions.map(c => ({
            kind: monaco.languages.CompletionItemKind[c.kind] || monaco.languages.CompletionItemKind.Variable,
            label: c.text, detail: c.detail, insertText: c.text,
            sortText: String(c.rank), range: c.range,
          })),
          dispose: () => { },
        };
      } catch (err) {
        console.error("Error fetching completion items:", err);
        return;
      }
    }
  });

  monaco.editor.registerCommand('cancelEditor', () => handleClick('#cancel_btn'));
  monaco.editor.registerCommand('focusMsg', () => document.activeElement.blur());

  monaco.editor.registerCommand('selectAndAcceptFirstSuggestion', () => {
    const suggestController = window.editor.getContribution('editor.contrib.suggestController');
    suggestController.selectFirstSuggestion();
    suggestController.acceptSelectedSuggestion();
  })

  monaco.editor.registerCommand('insertLastOutputAsImg', () => {
    const currId = htmx.find('#id_').value;
    const tgt = currId ? document.getElementById(currId).previousElementSibling
      : htmx.find('.editable:last-child');
    const elm = tgt?.querySelector('.card-out');
    if (!elm) return;
    elm.scrollIntoView({ behavior: 'instant', block: 'nearest' });
    setTimeout(() => captureElement(elm), 0);
  });

  monaco.editor.addKeybindingRules([
    {
      keybinding: monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyB,
      command: 'editor.action.selectHighlights',
      when: 'editorTextFocus'
    },
    // select & accept first suggestion on enter
    {
      keybinding: enter_comp ? KeyCode.Enter : KeyCode.Tab,
      command: 'selectAndAcceptFirstSuggestion',
      when: 'suggestWidgetVisible && !suggestWidgetHasFocusedSuggestion'
    },
    // accept ghost text on tab
    {
      keybinding: enter_comp ? KeyCode.Tab : KeyCode.RightArrow,
      command: 'editor.action.inlineSuggest.commit',
      when: 'inlineSuggestionVisible'
    },
    // trigger ghost text on alt + period
    {
      keybinding: KeyMod.Alt | KeyCode.Period,
      command: 'editor.action.inlineSuggest.trigger',
      when: 'editorTextFocus'
    },
    {
      keybinding: KeyMod.Shift | KeyCode.Escape,
      command: 'focusMsg',
      when: 'editorTextFocus'
    },
    // cancel editor when escape pressed and no suggest widget visible
    {
      keybinding: KeyCode.Escape,
      command: 'cancelEditor',
      when: '!suggestWidgetVisible && !inlineSuggestionVisible && !findWidgetVisible && !parameterHintsVisible'
    },
    // trigger parameter hints on shift + tab
    {
      keybinding: KeyMod.Shift | KeyCode.Tab,
      command: 'editor.action.triggerParameterHints',
      when: '!parameterHintsVisible && !editorHasSelection && editorTextFocus'
    },
    // attach output screenshot within prompt message on ctrl + shift + comma
    {
      keybinding: mainKeys | KeyCode.Comma,
      command: 'insertLastOutputAsImg',
      when: 'editorTextFocus'
    }
  ])

  monaco.languages.registerSignatureHelpProvider("python", {
    provideSignatureHelp: (model, position) => {
      return new Promise(async (resolve) => {
        try {
          const fullContent = model.getValue();
          let dlg_name = document.getElementById('dlg_name').value;
          const body = JSON.stringify({ code: fullContent, line_no: position.lineNumber, col_no: position.column - 1, dlg_name });
          const res = await fetch("/sig_help_", { body, method: "POST", headers: { "Content-Type": "application/json" } });
          if (!res.ok) return resolve();
          const { values } = await res.json();
          if (!values.length) return resolve();
          window.editor.trigger('', 'hideSuggestWidget');
          resolve({
            value: {
              signatures: values.map((s) => ({
                label: s.label,
                documentation: {
                  value: "<small>" + `<span><b>Type: </b><kbd>${s.typ}</kbd><br></span>` + `<span><b>Module: </b><kbd>${s.mod}\n</kbd><br></span>` + `<span><b>Docstring: </b><pre>${s.doc}</pre>` + "</small>",
                  supportHtml: true
                },
                parameters: s.params.map((p) => ({ label: p.name, documentation: { value: p.desc } })),
                activeParameter: s.idx,
              })),
              activeSignature: 0,
            },
            dispose: () => { },
          });
        } catch (err) {
          console.error("Error fetching signature help:", err);
          resolve();
        }
      });
    }
  });

  monaco.languages.registerInlineCompletionsProvider(["markdown", "python"], {
    provideInlineCompletions: async (model, position, context) => {
      try {
        const triggerType = context.triggerKind === 1 ? 'explicit' : 'automatic';
        if (triggerType === 'automatic' && htmx.find('[name=mode]').value === 'learning') return;
        const dlg_name = document.getElementById('dlg_name')?.value;
        if (!dlg_name || !_copts().scon) return;
        const lineContent = model.getLineContent(position.lineNumber);
        const copts = _copts();
        if (context.selectedSuggestionInfo) return;

        const triggerChars = typeof copts.triggerc === 'string' ? JSON.parse(copts.triggerc) : copts.triggerc;
        if (triggerType === 'automatic' && !triggerChars?.some(c => lineContent.endsWith(c))) return;

        const pfx = _prefix(model, position), sfx = _suffix(model, position);
        const prevLine = model.getLineContent(Math.max(position.lineNumber - 1, 1));
        const req_id = Math.random().toString(36).slice(2);
        const body = JSON.stringify({ id_: _edVar('id_'), mtype: _edVar('msg_type'), pfx, sfx, req_id, dlg_name });
        const r = await fetch("/ghost_", { method: "POST", headers: { "Content-Type": "application/json" }, body, priority: "low" });
        if (!r.ok) return;
        const { completions } = await r.json();
        if (!Array.isArray(completions) || !completions.length || !model.isAttachedToEditor()) return;

        const first = completions[0].text;
        if (_isWhiteSpaceOnly(first) && copts.acceptichars && !sfx.length && !_isWhiteSpaceOnly(prevLine)) {
          window.editor.executeEdits('ghost_text_empty', [{ text: first, range: _range(position) }]);
          window.editor.executeCommand('aai.inlineSuggest.accepted', null);
          return;
        }
        return {
          items: completions.map(c => ({
            insertText: c.text,
            range: _range(position),
            command: { id: 'aai.inlineSuggest.accepted' },
          })),
          enableForwardStability: true,
        }
      } catch (err) {
        console.error("Error fetching inline completions:", err);
        return;
      }
    },
    disposeInlineCompletions: () => { },
    debounceDelayMs: 800,
  });

  // ghost text request
  monaco.editor.registerCommand('aai.inlineSuggest.accepted', () => {
    // we add a small delay to allow the editor to accept the ghost text suggestion and update its content.
    // if this delay isn't included we would pass the same data to our ghost text model and make the same suggestion.
    if (_copts().triggeronaccept && htmx.find('[name=mode]').value !== 'learning') {
      window.editor.trigger(null, 'editor.action.inlineSuggest.trigger', {});
    }
  });

  if ('scheduler' in window) {
    scheduler.postTask(preloadModels, { priority: 'background' });
  } else {
    setTimeout(preloadModels, 0);
  }
};

function toggleTheClasses(elid, anyClass, toggleClass) {
  any(anyClass).classRemove(toggleClass);
  document.getElementById(elid)?.classList.add(toggleClass);
}

function clickEdTab(id, msg_type, lang) {
  toggleTheClasses(id, ".tabh", "uk-active");
  const mt = me('#msg_type');
  if (mt) mt.value = msg_type;
  if (window.edmodel) {
    edmodel.setLanguage(lang);
    window.editor.focus();
  }
};

// Editor expand/ minimize button logic
function expandEd({ detail }, is_expanded = false) {
  if (detail.xhr.isError || !window.editor) return; // prevent expanded state not matching button
  const edelm = window.editor.getContainerDomNode();
  if (!edelm) return; // if editor element not found, return
  edelm.style.height = is_expanded ? `${window.editor.getContentHeight()}px` : '80svh';
  edelm.style.maxHeight = is_expanded ? '50svh' : '80svh'; // reset max-height to allow editor to expand
  window.editor.layout(); // re-layout the editor to apply the new height
}

// get all text before the cursor
function _prefix(model, position) {
  return model.getValueInRange({ startLineNumber: 1, startColumn: 1, endLineNumber: position.lineNumber, endColumn: position.column });
}
// get all text after the cursor
function _suffix(model, position) {
  return model.getValueInRange({
    startLineNumber: position.lineNumber, endLineNumber: model.getLineCount(),
    startColumn: position.column, endColumn: model.getLineMaxColumn(model.getLineCount()),
  }).trim();
}
// get variables from editor html like dialog id, message id, message type
function _edVar(s) { return me(`#${s}`).value }
// get completion options for the current message
function _copts() { return window.svCopts }
function _isWhiteSpaceOnly(s) { return /^\s*$/.test(s) }

function _range(p) { return new monaco.Range(p.lineNumber, p.column, p.lineNumber, p.column) }

const loader = document.createElement('div');
loader.setAttribute('data-uk-spinner', "ratio: 0.6");
const edLoader = {
  getId: () => 'editor.loader.widget',
  getDomNode: () => loader,
  getPosition: () => monaco.editor.OverlayWidgetPositionPreference.TOP_LEFT_CORNER
}

async function superComplete(hl, instr, pfx, sfx, rng) {
  try {
    window.editor.addOverlayWidget(edLoader);
    let rt = hl ? "/supere_" : "/superc_";
    let dlg_name = document.getElementById('dlg_name').value;
    const r = await fetch(rt, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_: _edVar('id_'), mtype: _edVar('msg_type'), pfx, sfx, hl, instr, dlg_name
      }),
    });
    const { completions } = await r.json();
    window.editor.updateOptions({ readOnly: false });
    if (completions.length) window.editor.executeEdits('superc', [{ text: completions[0].text, range: rng }]);
  } catch (err) {
    window.editor.updateOptions({ readOnly: false });
    console.error('Error fetching supercompletion: ', err);
  } finally { window.editor.removeOverlayWidget(edLoader) }
}

function getNodes() {
  const ctn = document.createElement('form');
  const aiInput = document.createElement('input');
  ctn.appendChild(aiInput);
  ctn.id = 'ai-form';
  ctn.style.cssText = 'box-sizing:border-box;z-index:10;padding:5px;background-color:oklch(0.95 0.01 0.1 / 0.2);border:1px solid hsl(var(--muted));';
  aiInput.name = 'query';
  aiInput.className = 'uk-input';
  aiInput.type = 'text';
  aiInput.autocomplete = 'off';
  aiInput.placeholder = 'Enter your query...';
  aiInput.id = 'ai-input';
  return { ctn, aiInput };
}

let viewZoneId;

/* Model Creation/ Fetching */
function getOrMakeModel(opts, id_) {
  const uri = monaco.Uri.parse(id_);
  let model = monaco.editor.getModel(uri);
  if (!model) model = monaco.editor.createModel(opts.value || '', opts.language || "python", uri);
  else { model.setLanguage(opts.language); }
  if (id_.endsWith('temp')) {
    model.setValue(''); // Clear temp model value to set height correctly
  } else if (opts.value !== model.getValue()) {
    model.pushEditOperations([], [{ range: model.getFullModelRange(), text: opts.value }]);
  }
  return model;
}

function createMonacoEditor(edid, opts = {}, copts = {}, logcomp = false, enter_comp = false, id_ = '', oob = true, vim = false) {
  window.svCopts = copts; // to avoid namespace clashes we use an obscure name.
  window.svLogcomp = logcomp;

  function _cme() {
    const container = document.getElementById(edid);
    window.edmodel = getOrMakeModel(opts, 'temp');
    window.editor = monaco.editor.create(container, {
      model: window.edmodel, wordWrap: "on", codeLens: false,
      scrollBeyondLastLine: false, quickSuggestionsDelay: 300, minimap: { enabled: false },
      lineNumbersMinChars: 3, // This removes excess padding from the line number column
      fontSize: htmlTag.classList.contains('uk-font-sm') ? 14 : 16,
      extraEditorClassName: 'nomath', suggest: { selectionMode: 'never' },
      inlineSuggest: { enabled: true, showToolbar: 'never' },
      padding: { top: 4, bottom: 4, }, autoSurround: true,
      ...opts
    });

    // super completion
    //window.editor.addCommand(KeyMod.Alt | KeyMod.Shift | KeyCode.Period, async function() {
    window.editor.addCommand(mainKeys | KeyCode.Period, async function() {
      window.editor.updateOptions({ readOnly: true });
      const model = window.editor.getModel();
      const selection = window.editor.getSelection();

      if (!selection.isEmpty()) {
        const { ctn, aiInput } = getNodes();

        // Add escape key handler to dismiss the popup
        const dismissPopup = () => {
          window.editor.changeViewZones(changeAccessor => changeAccessor.removeZone(viewZoneId));
          window.editor.updateOptions({ readOnly: false });
          // Restore original editor height after removing view zone
          const container = document.getElementById(edid);
          const newHeight = Math.max(window.editor.getContentHeight(), container.getBoundingClientRect().height);
          container.style.height = `${newHeight}px`;
          window.editor.layout();
          window.editor.focus();
        };

        ctn.onsubmit = async (event) => {
          event.preventDefault();
          const instr = aiInput.value;
          dismissPopup();
          await superComplete(model.getValueInRange(selection), instr,
            _prefix(model, selection.getStartPosition()), _suffix(model, selection.getEndPosition()), selection);
        }

        // Handle escape key in the input field
        aiInput.addEventListener('keydown', (event) => {
          if (event.key === 'Escape') {
            event.preventDefault();
            dismissPopup();
          }
        });

        window.editor.changeViewZones(changeAccessor => {
          viewZoneId = changeAccessor.addZone({
            afterLineNumber: selection.startLineNumber - 1,
            heightInLines: 2,
            domNode: ctn,
            onComputedHeight: (actualHeight) => {
              const container = document.getElementById(edid);
              const currentHeight = container.getBoundingClientRect().height;
              const newHeight = currentHeight + actualHeight;
              container.style.height = `${newHeight}px`;
              window.editor.layout();
              window.editor.applyFontInfo(aiInput);
              requestAnimationFrame(() => aiInput.focus());
            },
          });
        });
      } else {
        const pos = window.editor.getPosition();
        await superComplete('', '', _prefix(model, pos), _suffix(model, pos), _range(pos));
      }
    })

    // split message trigger
    window.editor.addCommand(ctrlKeys | KeyCode.Minus, async () => {
      const prefix = _prefix(window.edmodel, window.editor.getPosition());
      const suffix = _suffix(window.edmodel, window.editor.getPosition());
      const id_ = _edVar('id_');

      let dlg_name = document.getElementById('dlg_name').value;
      await htmx.ajax('POST', '/split_at_', {
        swap: 'none',
        values: {
          prefix, suffix, dlg_name,
          msg_type: _edVar('msg_type'), id_, is_input: _edVar('is_input')
        }
      });
    });

    const shortcuts = [
      { key: KeyCode.KeyJ, action: clickHandler("#tabh-code") },
      { key: KeyCode.KeyK, action: clickHandler("#tabh-note") },
      { key: KeyCode.KeyL, action: clickHandler("#tabh-prompt") },
      { key: KeyCode.Semicolon, action: clickHandler("#tabh-raw") },
      { key: KeyCode.KeyX, action: clickHandler("button[hx-on--before-swap^='expandEd']") },
      { key: KeyCode.KeyD, action: clickHandler("#use_thinking") },
    ];

    const registerCommand = (shortcut) => {
      const { key, action } = shortcut;
      window.editor.addCommand(mainKeys | key, action);
    };

    window.editor.addCommand(KeyMod.CtrlCmd | KeyCode.Enter, clickHandler('#submit_btn'));
    window.editor.addCommand(KeyMod.Shift | KeyCode.Enter, () => upsert_msg('upsert-shift-run'));
    window.editor.addCommand(KeyMod.Alt | KeyCode.Enter, () => upsert_msg('upsert-alt-run'));
    window.editor.addCommand(KeyMod.Shift | KeyMod.CtrlCmd | KeyCode.Enter, () => {
      upsert_msg('upsert-shift-run');
      _post('continue_prompt');
    });

    shortcuts.forEach(registerCommand);

    window.editor.addCommand(ctrlKeys | KeyCode.UpArrow, clickHandler(".editable:last-child div[hx-post^='/editor_']"));

    editor.onKeyDown(() => {
      if (editor.suppressed) {
        editor.updateOptions({ quickSuggestions: true });
        editor.suppressed = false;
      }
      if (editor._contextKeyService.getContextKeyValue('parameterHintsVisible')) {
        editor.trigger(null, 'closeParameterHints', {});
      }
    });

    editor.onDidScrollChange(({ scrollHeightChanged }) => {
      if (!scrollHeightChanged) return;
      const newHeight = Math.max(editor.getContentHeight(), editor.getLayoutInfo().height);
      setEditorHeight(newHeight);
    });

    editor.onDidChangeModel(({ newModelUrl }) => {
      editor.trigger('', 'closeFindWidget', {});
      editor.updateOptions({ quickSuggestions: false });
      editor.suppressed = true;
      if (!newModelUrl.path.endsWith('temp')) editor.focus();
      else if (editor.hasWidgetFocus()) document.activeElement.blur();
    })

    editor.onDidFocusEditorText(() => document.dispatchEvent(new Event("monaco:editorFocused")));
    editor.onMouseDown(() => document.dispatchEvent(new Event("monaco:editorClicked")));
    document.dispatchEvent(new Event("monaco:editorReady"));

    editor.vimMode = window.initVimMode?.(editor, document.getElementById('vi-status'));
  }

  if (!window.monaco || !oob) {
    loadMonaco(enter_comp, vim).then(() => _cme());
  } else {
    window.editor.trigger('', 'editor.action.inlineSuggest.hide', {});
    window.edmodel = getOrMakeModel(opts, id_);
    window.editor.setModel(window.edmodel);
    setEditorHeight(window.editor.getContentHeight());
    window.editor.setScrollPosition({ scrollTop: window.editor.getContentHeight() });
    window.editor.setPosition(window.editor.getModel().getFullModelRange().getEndPosition(), 'keyboard');
  }
};

function setEditorHeight(newHeight) {
  window.editor.getContainerDomNode().style.height = `${newHeight}px`;
  requestAnimationFrame(() => window.editor.layout());
};


if (window.htmx) htmx.on('htmx:configRequest', ({ detail }) => {
  if (!detail.parameters.get('content')?.length && !detail.elt.classList.contains('cursor-alias')) {
    detail.parameters.set('content', window.editor?.getValue() || '');
  }
});

function handleClick(id) { document.querySelector(id)?.click() };
function clickHandler(id) { return () => handleClick(id) };

// Persistent UI
// FrankenUI stores ui settings like theme, font, etc. in localStorage.
// LocalStorage data is only accessible to the subdomain that wrote it.
// We lose access to this data when a container restarts and is served on a different subdomain.
// Instead, we store these settings in a cookie which is accessible across subdomains.

// first page load after restarting solveit (IIFE to avoid polluting global scope)
(() => {
  const cui = JSON.parse(document.cookie.match(/ui=([^;]*)/)?.[1] || '{}');
  const lsui = localStorage.getItem('__FRANKEN__');

  if (Object.keys(cui).length !== 0 && !lsui) {
    localStorage.setItem('__FRANKEN__', JSON.stringify(cui));
    htmlTag.classList = Object.values(cui).join(' '); // Override the class list to make sure theme applies
  }
})();

function setThemeCookie(value) {
  const expires = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toUTCString();
  const domain = window.location.hostname.replace(/^[^.]+/, '') || 'localhost';
  document.cookie = `ui=${JSON.stringify(value)}; expires=${expires}; domain=${domain}; path=/`;
}

document.addEventListener('uk-theme-switcher:change', ({ detail }) => {
  monaco.editor.setTheme(detail.value.mode === 'dark' ? DARK_THEME : LIGHT_THEME);
  window.editor?.updateOptions({ fontSize: detail.value.font?.includes('sm') ? 14 : 16 });
  monaco.editor.remeasureFonts();

  setThemeCookie(detail.value);
});

window.addEventListener('resize', () => {
  window.editor?.layout();
}, { passive: true });

htmx.on("htmx:wsOpen", ({ detail: { event} }) => updateWSIndicator(event.type));
htmx.on("htmx:wsClose", ({ detail: { event } }) =>  updateWSIndicator(event.type));
htmx.on("htmx:wsError", () => updateWSIndicator('error'));

function updateWSIndicator(type) {
  if (window.editor) { htmx.find('#submit_btn').disabled = ['error', 'close'].includes(type); }
  const color = { error: "orange", open: "limegreen", close: "red" }[type] || 'grey';
  const elt = document.getElementById("ws-indicator");
  if (elt) elt.style.backgroundColor = color;
};

function handleRenameKey(event) {
  if (['Enter', 'Escape'].includes(event.key)) {
    event.preventDefault();
    event.currentTarget.blur();
  } else if (event.key === '\\') {
    event.preventDefault();
  }
}

htmx.config.wsReconnectDelay = function(retryCount) {
  var exp = Math.min(retryCount, 4)
  var maxDelay = 250 * Math.pow(2, exp)
  var delay = maxDelay * Math.random() // milliseconds
  console.log("Lost connection to solveit, retry: ", retryCount, "; delay: ", delay)
  return delay;
}

htmx.on('htmx:pushedIntoHistory', () => { window.editor?.dispose() })

function debounceScroll(elt, delay = 700) {
  // Don't scroll if message is still loading (ai streaming etc). Select will scroll to bottom of output after swaps.
  if (elt.querySelector('.animate-spin')) return;
  if (!scrollTimer) {
    elt.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    scrollTimer = setTimeout(() => { scrollTimer = null; }, delay);
  } else {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      elt.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      scrollTimer = null;
    }, delay);
  }
}

window.pushData = (id, data) => fetch('/push_data_blocking_', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ data_id: id, ...data })
});

function copy_snippet(el) {
  navigator.clipboard.writeText(el.dataset.code);
  const msg = el.nextElementSibling;
  msg.style.opacity = '1';
  setTimeout(() => msg.style.opacity = '0', 2000)
}
